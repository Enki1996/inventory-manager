"""Hospital Warehouse IMS - connected single-warehouse testing app.

For Railway, configure WAREHOUSE_PUBLIC_DEPLOY=1, a strong
WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD, and a persistent volume at /data.
"""
from __future__ import annotations

import contextlib
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
from book_catalog import BOOKS_BY_BRANCH, valid_book
from unit_catalog import UNITS_BY_BRANCH, valid_unit
from department_catalog import DEFAULT_DEPARTMENTS
import google_drive_backup as gdrive

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
PUBLIC_REQUESTED = os.getenv('WAREHOUSE_PUBLIC_DEPLOY', '').strip() == '1'
DATA = Path(os.getenv('WAREHOUSE_DATA_DIR', str(ROOT / 'data'))).resolve()
if PUBLIC_REQUESTED:
    if 'WAREHOUSE_DATA_DIR' not in os.environ:
        raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: configure WAREHOUSE_DATA_DIR=/data and attach a persistent volume.')
    volume_mount = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
    if os.getenv('RAILWAY_ENVIRONMENT') and not volume_mount:
        raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: attach a Railway persistent volume before starting this app.')
    if volume_mount and DATA != Path(volume_mount).resolve():
        raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: WAREHOUSE_DATA_DIR must match the mounted Railway volume path.')
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / 'warehouse.sqlite3'
BACKUPS = DATA / 'safety_backups'
BACKUPS.mkdir(exist_ok=True)
DB_LOCK = threading.RLock()
SCHEMA_VERSION = 10
# App release is distinct from the SQLite schema version (no destructive migration).
APP_RELEASE = '4.27.1'
# The installation owner is selected by server configuration, never by staff role editing.
OWNER_USERNAME = os.getenv('WAREHOUSE_ULTRA_ADMIN_USERNAME', 'enki').strip().lower() or 'enki'
BRANCHES = ('medication', 'medical_supplies', 'surgical_instruments')
assert set(BOOKS_BY_BRANCH) == set(BRANCHES)
assert set(UNITS_BY_BRANCH) == set(BRANCHES)
PUBLIC_DEPLOY = os.getenv('WAREHOUSE_PUBLIC_DEPLOY', '').strip() == '1'
SESSION_HOURS = 12
ROLES = ('admin', 'manager', 'operator', 'viewer')
WRITE_PERMS = {
    'admin': {'item_write', 'department_write', 'movement_write', 'adjust', 'users', 'backup'},
    'manager': {'item_write', 'department_write', 'movement_write', 'adjust'},
    'operator': {'movement_write'},
    'viewer': set(),
}
app = FastAPI(title='Hospital Warehouse IMS', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.url.path.startswith('/api/') or request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-store'
    if PUBLIC_DEPLOY:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def connection():
    c = sqlite3.connect(DB, timeout=20, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA busy_timeout=20000')
    return c


@contextlib.contextmanager
def db(readonly=False):
    with DB_LOCK:
        c = connection()
        try:
            if not readonly:
                c.execute('BEGIN IMMEDIATE')
            yield c
            if not readonly:
                c.commit()
        except Exception:
            if not readonly:
                c.rollback()
            raise
        finally:
            c.close()


def pw_hash(password):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 350_000)
    return 'pbkdf2_sha256$350000$' + salt.hex() + '$' + h.hex()


def pw_check(password, encoded):
    try:
        algo, rounds, salt, expected = encoded.split('$')
        if algo != 'pbkdf2_sha256':
            return False
        value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(value, bytes.fromhex(expected))
    except Exception:
        return False


def bootstrap_admin_password():
    """Never put a known default password on a public deployment."""
    if not PUBLIC_DEPLOY:
        return '123'  # Local-only backwards-compatible demonstration account.
    password = os.getenv('WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD', '')
    if len(password) < 14 or len(password) > 128 or password in ('123', 'password', 'admin123'):
        raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: set WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD to a unique password of at least 14 characters.')
    return password


def migrate_item_details(c: sqlite3.Connection):
    """Additive V1 -> V2 migration, safe for existing records and backup imports."""
    columns = {row[1] for row in c.execute('PRAGMA table_info(items)')}
    for name, definition in (
        ('generic_name', "TEXT NOT NULL DEFAULT ''"),
        ('manufacturer', "TEXT NOT NULL DEFAULT ''"),
        ('manufacture_date', 'TEXT'),
        ('expiry_date', 'TEXT'),
        ('information', "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in columns:
            c.execute(f'ALTER TABLE items ADD COLUMN {name} {definition}')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def migrate_annual_need(c: sqlite3.Connection):
    """V8: catalog-level annual requirements, NULL means never entered.

    Neither old stock lots nor their historical movement records are modified.
    """
    columns = {row[1] for row in c.execute('PRAGMA table_info(items)')}
    if 'annual_need' not in columns:
        c.execute('ALTER TABLE items ADD COLUMN annual_need INTEGER CHECK(annual_need >= 0)')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def annual_need_from_fields(data, *, prior=None):
    """No fabricated annual need: omitted edits preserve their previous value."""
    if 'annual_need' not in data:
        return prior
    raw = data.get('annual_need')
    if raw in (None, ''):
        return None
    return integer(data, 'annual_need', 0, 1_000_000_000)


def percent_parameter(raw, field):
    """Positive, adjustable percentage with at most two decimal places."""
    if raw in (None, ''):
        return None
    s = str(raw).strip()
    if not re.fullmatch(r'\d{1,4}(?:\.\d{1,2})?', s):
        err(422, f'{field} must be a positive percentage with at most two decimal places')
    try:
        value = Decimal(s)
    except InvalidOperation:
        err(422, f'{field} is invalid')
    if not Decimal('0') < value <= Decimal('1000'):
        err(422, f'{field} must be above zero and at most 1000%')
    return value



def migrate_v9(c: sqlite3.Connection):
    """Add lot-specific manufacture date and private employee profile fields.

    Existing lots and log records are never rewritten; all columns are optional.
    """
    lot_cols = {r[1] for r in c.execute('PRAGMA table_info(batches)')}
    if 'manufacture_date' not in lot_cols:
        c.execute('ALTER TABLE batches ADD COLUMN manufacture_date TEXT')
    user_cols = {r[1] for r in c.execute('PRAGMA table_info(users)')}
    for name, definition in (
        ('email', "TEXT NOT NULL DEFAULT ''"),
        ('phone', "TEXT NOT NULL DEFAULT ''"),
        ('age', 'INTEGER CHECK(age >= 0 AND age <= 120)'),
        ('job_title', "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in user_cols:
            c.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
    # Read-only movement timelines need indexed lookups as the ledger grows.
    c.execute('CREATE INDEX IF NOT EXISTS idx_batches_item_v9 ON batches(item_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_lines_batch_v9 ON movement_lines(batch_id,movement_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_lines_movement_v9 ON movement_lines(movement_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_movements_department_v9 ON movements(department_id,created_at)')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def opening_lot_details(data):
    """Validate each physical opening lot before starting a DB transaction."""
    raw = data.get('opening_lots')
    if raw is None:
        # Preserve the original V4.16 one-lot request for old clients.
        raw = [data]
    if not isinstance(raw, list) or not (1 <= len(raw) <= 40):
        err(422, 'Opening balance needs between 1 and 40 lots')
    result = []
    for index, row in enumerate(raw, 1):
        if not isinstance(row, dict):
            err(422, f'Opening lot {index} is invalid')
        batch = validated_text(row, 'batch_no', max_len=90)
        expiry = dated(row.get('expiry_date'), f'Opening lot {index} expiry_date')
        manufacture = dated(row.get('manufacture_date'), f'Opening lot {index} manufacture_date')
        if not expiry:
            err(422, f'Opening lot {index} requires an expiry date')
        if manufacture and manufacture > expiry:
            err(422, f'Opening lot {index}: manufacture date is after expiry')
        qty = integer(row, 'opening_qty', 1, 100_000_000)
        price = price_from_fields(row)
        result.append({'batch_no':batch, 'expiry_date':expiry,
                       'manufacture_date':manufacture, 'qty':qty,
                       'unit_price_fils':price})
    return result


def validate_profile(data):
    name = validated_text(data, 'full_name', max_len=100)
    email = validated_text(data, 'email', required=False, max_len=200)
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        err(422, 'Enter a valid email address')
    phone = validated_text(data, 'phone', required=False, max_len=35)
    if phone and not re.fullmatch(r'[+0-9\s()\-]{5,35}', phone):
        err(422, 'Phone number contains unsupported characters')
    age = None
    if data.get('age') not in (None, ''):
        age = integer(data, 'age', 0, 120)
    job_title = validated_text(data, 'job_title', required=False, max_len=100)
    return name,email,phone,age,job_title

def require_branch(value, *, allow_unassigned=False):
    """Only these three branches can own inventory; NULL marks legacy records."""
    if value in BRANCHES:
        return value
    if allow_unassigned and value in (None, ''):
        return None
    err(422, 'Choose one of the three warehouse branches')


def require_book(branch, value):
    """Never allow a category from another branch or an arbitrary title."""
    book = validated_text({'category': value}, 'category', max_len=80)
    if not valid_book(branch, book):
        err(422, 'Select an approved book / register for the chosen warehouse branch')
    return book


def restrict_branch(user, branch):
    """Permission scope is checked server-side for every individual item/line."""
    if user['role'] == 'admin':
        return
    if not user['branch'] or branch != user['branch']:
        err(403, 'Your account may modify items only in its assigned warehouse branch')


def user_branch_from_request(role, value):
    if role == 'admin':
        return None  # Administrative account is the explicit cross-branch exception.
    return require_branch(value)


def migrate_branches(c: sqlite3.Connection):
    """Additive migration: leave old items/staff unassigned, never guess a branch."""
    users_cols = {row[1] for row in c.execute('PRAGMA table_info(users)')}
    if 'branch' not in users_cols:
        c.execute('ALTER TABLE users ADD COLUMN branch TEXT')
    item_cols = {row[1] for row in c.execute('PRAGMA table_info(items)')}
    if 'branch' not in item_cols:
        c.execute('ALTER TABLE items ADD COLUMN branch TEXT')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def migrate_item_form(c: sqlite3.Connection):
    """V4.3 -> V4.4: additive only; do not rewrite legacy medicine names or batches."""
    columns = {row[1] for row in c.execute('PRAGMA table_info(items)')}
    for name, definition in (
        ('trade_name', "TEXT NOT NULL DEFAULT ''"),
        ('initial_batch_no', "TEXT NOT NULL DEFAULT ''"),
    ):
        if name not in columns:
            c.execute(f'ALTER TABLE items ADD COLUMN {name} {definition}')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def require_unit(branch, value, *, legacy_unit=None):
    unit = validated_text({'unit': value}, 'unit', max_len=30)
    if not valid_unit(branch, unit) and (legacy_unit is None or unit != legacy_unit):
        err(422, 'Choose an approved stock unit for the selected warehouse branch')
    return unit


def item_name_fields(d, branch, *, old=None):
    """Medicine: display trade + scientific; supplies/tools: display item name only.
    `items.name` remains the stable scientific/item name for old databases.
    """
    name = validated_text(d, 'name', max_len=160)
    if branch == 'medication':
        trade = validated_text(d, 'trade_name', max_len=160)
    else:
        trade = ''
    return name, trade


def item_batch_no(d):
    # No batch exists merely because a product is registered in the catalog.
    return validated_text(d, 'batch_no', required=False, max_len=90)


def make_sku(branch):
    return {'medication':'MED','medical_supplies':'SUP','surgical_instruments':'SUR'}[branch] + '-' + secrets.token_hex(6).upper()


def item_details(d):
    """Item reference dates; actual received batches keep their own expiry."""
    generic_name = validated_text(d, 'generic_name', required=False, max_len=160)
    manufacturer = validated_text(d, 'manufacturer', required=False, max_len=160)
    manufacture_date = dated(d.get('manufacture_date'), 'manufacture_date')
    expiry_date = dated(d.get('expiry_date'), 'expiry_date')
    # Stock-less catalog registration has no known lot or expiry yet.
    # Opening-balance registration validates the real lot expiry separately.
    information = validated_text(d, 'information', required=False, max_len=2000)
    if manufacture_date and expiry_date and manufacture_date > expiry_date:
        err(422, 'Item expiration date must not be earlier than its manufacture date')
    return generic_name, manufacturer, manufacture_date, expiry_date, information



def migrate_outgoing_and_price(c: sqlite3.Connection):
    """V4 -> V5 additive migration; legacy prices remain unknown (NULL)."""
    item_cols = {r[1] for r in c.execute('PRAGMA table_info(items)')}
    if 'price_fils' not in item_cols:
        c.execute('ALTER TABLE items ADD COLUMN price_fils INTEGER CHECK(price_fils >= 0)')
    line_cols = {r[1] for r in c.execute('PRAGMA table_info(movement_lines)')}
    if 'unit_price_fils' not in line_cols:
        c.execute('ALTER TABLE movement_lines ADD COLUMN unit_price_fils INTEGER CHECK(unit_price_fils >= 0)')
    movement_cols = {r[1] for r in c.execute('PRAGMA table_info(movements)')}
    for field, definition in (
        ('destination_type', "TEXT CHECK(destination_type IN ('department','external') OR destination_type IS NULL)"),
        ('external_destination', "TEXT NOT NULL DEFAULT ''"),
        ('dispatch_ref', "TEXT NOT NULL DEFAULT ''"),
    ):
        if field not in movement_cols:
            c.execute(f'ALTER TABLE movements ADD COLUMN {field} {definition}')
    # Old OUT movements are department distributions, but do not invent a missing dispatch reference.
    c.execute("UPDATE movements SET destination_type='department' WHERE kind='OUT' AND department_id IS NOT NULL AND destination_type IS NULL")
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))



# Explicit, auditable shipment routes (one central warehouse).
OUT_ROUTES = ('department_issue', 'external_transfer_out', 'pharmacy_transfer_out')
IN_ROUTES = ('pharmacy_receipt', 'purchase_receipt', 'external_transfer_in', 'internal_return')
PHARMACY_DESTINATION = 'قسم الصيدلة'


def migrate_shipment_routes(c: sqlite3.Connection):
    """Add new route and delayed-paperwork metadata; preserve every legacy movement."""
    columns = {row[1] for row in c.execute('PRAGMA table_info(movements)')}
    for name, definition in (
        ('route', 'TEXT'),
        ('trusted_pharmacist_id', 'INTEGER REFERENCES users(id) ON DELETE RESTRICT'),
        ('paperwork_pending', 'INTEGER NOT NULL DEFAULT 0 CHECK(paperwork_pending IN (0,1))'),
        ('paperwork_completed_at', 'TEXT'),
        ('paperwork_completed_by', 'INTEGER REFERENCES users(id) ON DELETE RESTRICT'),
    ):
        if name not in columns:
            c.execute(f'ALTER TABLE movements ADD COLUMN {name} {definition}')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def migrate_per_receipt_pricing_and_transfer_authorization(c: sqlite3.Connection):
    # V7: independently priced/dated inventory lots, text pharmacist and authorization.

    # Existing balances and movement prices preserved; use legacy catalog price if known.
    batch_cols = {r[1] for r in c.execute('PRAGMA table_info(batches)')}
    if 'unit_price_fils' not in batch_cols:
        c.execute('ALTER TABLE batches ADD COLUMN unit_price_fils INTEGER CHECK(unit_price_fils >= 0)')
        c.execute('''UPDATE batches SET unit_price_fils=(
            SELECT items.price_fils FROM items WHERE items.id=batches.item_id)''')
    # An item can have many lots with the same batch reference but distinct
    # expiration dates and/or purchase prices. A lot is the indivisible stock unit.
    c.execute('DROP INDEX IF EXISTS uq_batch')
    c.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_batch_lot_v7 ON batches(
        item_id, batch_no, COALESCE(expiry_date,''), COALESCE(unit_price_fils,-1))''')
    move_cols = {r[1] for r in c.execute('PRAGMA table_info(movements)')}
    for key,definition in (
        ('trusted_pharmacist_name', "TEXT NOT NULL DEFAULT ''"),
        ('authorization_ref', "TEXT NOT NULL DEFAULT ''"),
    ):
        if key not in move_cols:
            c.execute(f'ALTER TABLE movements ADD COLUMN {key} {definition}')
    c.execute("INSERT INTO app_meta(key,value) VALUES ('schema_version',?) "
              "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def receipt_line_price(line, catalog_price):
    # Zero is valid, missing legacy prices remain unknown (NULL).
    a = line.get('price_dinars')
    b = line.get('price_fils_component')
    if a is None and b is None:
        return catalog_price
    if a in (None, '') or b in (None, ''):
        err(422, 'Enter both dinar and fils values for the received item')
    return price_from_fields(line)


def boolean_flag(value, field):
    if value in (True, 1, '1'):
        return True
    if value in (False, 0, '0', '', None):
        return False
    err(422, f'{field} must be a checkbox value')


def active_pharmacist(c, user_id):
    if user_id is None:
        return None
    row = c.execute('SELECT id,username,full_name FROM users WHERE id=? AND is_active=1', (user_id,)).fetchone()
    if not row:
        err(422, 'Choose an active trusted pharmacist from registered accounts')
    return dict(row)


def price_from_fields(d):
    """Store price per catalog stock unit as exact integer fils (1 IQD = 1000 fils)."""
    dinars = integer(d, 'price_dinars', 0, 999_999_999)
    fils = integer(d, 'price_fils_component', 0, 999)
    return dinars * 1000 + fils

def seed_default_departments(c: sqlite3.Connection):
    """One-time, additive seed. Never recreate a department the user renamed."""
    flag = 'starter_departments_v49_done'
    if c.execute('SELECT 1 FROM app_meta WHERE key=?', (flag,)).fetchone():
        return
    added = 0
    for name in DEFAULT_DEPARTMENTS:
        if c.execute('SELECT 1 FROM departments WHERE name=? COLLATE NOCASE', (name,)).fetchone():
            continue
        temp_code = 'SEED-' + secrets.token_hex(8).upper()
        cur = c.execute('INSERT INTO departments(code,name,created_at) VALUES(?,?,?)', (temp_code, name, now()))
        c.execute('UPDATE departments SET code=? WHERE id=?', (f'DEP-{cur.lastrowid:06d}', cur.lastrowid))
        added += 1
    c.execute('INSERT INTO app_meta(key,value) VALUES(?,?)', (flag, str(added)))
    if added:
        c.execute('INSERT INTO audit_log(user_id,action,detail,created_at) VALUES(NULL,?,?,?)',
                  ('DEPARTMENTS_SEEDED', json.dumps({'number_added': added, 'release': APP_RELEASE}, ensure_ascii=False), now()))


def migrate_recovery_v10(c: sqlite3.Connection):
    """Append-only correction links. Never alter the original movement or audit entry."""
    c.executescript("""
      CREATE TABLE IF NOT EXISTS movement_reversals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_line_id INTEGER NOT NULL REFERENCES movement_lines(id) ON DELETE RESTRICT,
        undo_line_id INTEGER NOT NULL UNIQUE REFERENCES movement_lines(id) ON DELETE RESTRICT,
        redo_line_id INTEGER UNIQUE REFERENCES movement_lines(id) ON DELETE RESTRICT,
        undone_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
        undone_at TEXT NOT NULL,
        undo_reason TEXT NOT NULL,
        redone_by INTEGER REFERENCES users(id) ON DELETE RESTRICT,
        redone_at TEXT,
        redo_reason TEXT
      );
      CREATE UNIQUE INDEX IF NOT EXISTS one_active_undo_per_line
        ON movement_reversals(original_line_id) WHERE redo_line_id IS NULL;
      CREATE TABLE IF NOT EXISTS audit_field_reversals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_audit_id INTEGER NOT NULL UNIQUE REFERENCES audit_log(id) ON DELETE RESTRICT,
        undo_audit_id INTEGER NOT NULL UNIQUE REFERENCES audit_log(id) ON DELETE RESTRICT,
        redo_audit_id INTEGER UNIQUE REFERENCES audit_log(id) ON DELETE RESTRICT,
        object_type TEXT NOT NULL,
        object_id INTEGER NOT NULL
      );
    """)
    c.execute("INSERT INTO app_meta(key,value) VALUES('schema_version',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))


def init_db():
    with db() as c:
        c.executescript('''
            CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','manager','operator','viewer')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
                must_change_password INTEGER NOT NULL DEFAULT 0,
                branch TEXT CHECK(branch IN ('medication','medical_supplies','surgical_instruments') OR branch IS NULL),
                created_at TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL DEFAULT '',
                age INTEGER CHECK(age >= 0 AND age <= 120),
                job_title TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                csrf TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE COLLATE NOCASE,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                branch TEXT CHECK(branch IN ('medication','medical_supplies','surgical_instruments') OR branch IS NULL),
                unit TEXT NOT NULL,
                min_stock INTEGER NOT NULL DEFAULT 0 CHECK(min_stock >= 0),
                generic_name TEXT NOT NULL DEFAULT '',
                trade_name TEXT NOT NULL DEFAULT '',
                initial_batch_no TEXT NOT NULL DEFAULT '',
                manufacturer TEXT NOT NULL DEFAULT '',
                manufacture_date TEXT,
                expiry_date TEXT,
                information TEXT NOT NULL DEFAULT '',
                price_fils INTEGER CHECK(price_fils >= 0),
                annual_need INTEGER CHECK(annual_need >= 0),
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
                batch_no TEXT NOT NULL,
                expiry_date TEXT,
                on_hand INTEGER NOT NULL DEFAULT 0 CHECK(on_hand>=0),
                created_at TEXT NOT NULL,
                unit_price_fils INTEGER CHECK(unit_price_fils >= 0),
                manufacture_date TEXT
            );
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL CHECK(kind IN ('IN','OUT','RETURN','ADJUST_PLUS','ADJUST_MINUS')),
                paper_ref TEXT NOT NULL,
                department_id INTEGER REFERENCES departments(id) ON DELETE RESTRICT,
                source TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                destination_type TEXT CHECK(destination_type IN ('department','external') OR destination_type IS NULL),
                external_destination TEXT NOT NULL DEFAULT '',
                dispatch_ref TEXT NOT NULL DEFAULT '',
                route TEXT,
                trusted_pharmacist_id INTEGER REFERENCES users(id) ON DELETE RESTRICT,
                trusted_pharmacist_name TEXT NOT NULL DEFAULT '',
                authorization_ref TEXT NOT NULL DEFAULT '',
                paperwork_pending INTEGER NOT NULL DEFAULT 0 CHECK(paperwork_pending IN (0,1)),
                paperwork_completed_at TEXT,
                paperwork_completed_by INTEGER REFERENCES users(id) ON DELETE RESTRICT,
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS movement_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_id INTEGER NOT NULL REFERENCES movements(id) ON DELETE RESTRICT,
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
                qty INTEGER NOT NULL CHECK(qty > 0),
                direction INTEGER NOT NULL CHECK(direction IN (-1,1)),
                unit_price_fils INTEGER CHECK(unit_price_fils >= 0)
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                detail TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        ''')
        migrate_item_details(c)
        migrate_branches(c)
        migrate_item_form(c)
        migrate_outgoing_and_price(c)
        migrate_shipment_routes(c)
        migrate_per_receipt_pricing_and_transfer_authorization(c)
        migrate_annual_need(c)
        migrate_v9(c)
        migrate_recovery_v10(c)
        seed_default_departments(c)
        count = c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        if PUBLIC_DEPLOY and count > 0:
            old = c.execute("SELECT password_hash FROM users WHERE username='enki'").fetchone()
            if old and pw_check('123', old['password_hash']):
                raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: existing ENKI account still uses the local test password. Change it locally before deploying.')
        if count == 0:
            c.execute('INSERT INTO users(username,password_hash,full_name,role,is_active,must_change_password,created_at) VALUES(?,?,?,?,?,?,?)',
                      ('enki', pw_hash(bootstrap_admin_password()), 'ENKI Administrator', 'admin', 1, 0 if PUBLIC_DEPLOY else 1, now()))
            c.execute('INSERT INTO audit_log(user_id,action,detail,created_at) VALUES (1,?,?,?)',
                      ('INITIAL_SETUP', 'Installation administrator created', now()))

init_db()


def err(code, msg):
    raise HTTPException(status_code=code, detail=msg)


def validated_text(obj, key, *, required=True, max_len=120):
    value = str(obj.get(key, '') or '').strip()
    if required and not value:
        err(422, f'{key} is required')
    if len(value) > max_len:
        err(422, f'{key} must be {max_len} characters or less')
    return value


def integer(obj, key, minimum=0, maximum=100_000_000):
    value = obj.get(key)
    if isinstance(value, bool) or value is None or not re.fullmatch(r'-?\d+', str(value).strip()):
        err(422, f'{key} must be a whole number')
    val = int(value)
    if not minimum <= val <= maximum:
        err(422, f'{key} must be between {minimum} and {maximum}')
    return val


def dated(s, field='expiry_date'):
    if s in ('', None):
        return None
    try:
        return dt.date.fromisoformat(str(s)).isoformat()
    except Exception:
        err(422, f'{field} must be YYYY-MM-DD or empty')


def audit(c, user_id, action, detail):
    c.execute('INSERT INTO audit_log(user_id,action,detail,created_at) VALUES (?,?,?,?)',
              (user_id, action, json.dumps(detail, separators=(',', ':'), ensure_ascii=False), now()))


def get_user(request: Request, *, require_csrf=False):
    sid = request.cookies.get('wh_session', '')
    if len(sid) != 64:
        err(401, 'Sign in required')
    with db(readonly=True) as c:
        row = c.execute('''SELECT u.id,u.username,u.full_name,u.role,u.is_active,u.must_change_password,u.branch,s.csrf
                           FROM sessions s JOIN users u ON s.user_id=u.id
                           WHERE s.token_hash=? AND s.expires_at>?''',
                        (hashlib.sha256(sid.encode()).hexdigest(), now())).fetchone()
    if not row or not row['is_active']:
        err(401, 'Session expired. Sign in again.')
    if require_csrf and not hmac.compare_digest(request.headers.get('x-csrf-token', ''), row['csrf']):
        err(403, 'Invalid request token. Reload this page.')
    return dict(row)


def permit(user, permission):
    if permission not in WRITE_PERMS[user['role']]:
        err(403, f'Your role ({user["role"]}) cannot perform this action')


def is_ultra_admin(user):
    return user['role'] == 'admin' and user['username'] == OWNER_USERNAME


def permit_cloud(user):
    if not is_ultra_admin(user):
        err(403, 'Only the ultra administrator can manage Google Drive backups')


def local_backup_signature(manifest):
    # Domain-separated HMAC, using existing private key; no new Railway secret.
    try:
        key = gdrive.encryption_key()
    except gdrive.CloudBackupError:
        return None
    fields = {k: manifest[k] for k in ('application','schema_version','created_utc','database_file','sha256')}
    return hmac.new(key, b'IMS-local-backup-v1\0' + json.dumps(fields,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()


def allow_password_change_only(user, endpoint):
    if user['must_change_password'] and endpoint not in ('change_password', 'logout'):
        # For the testing '123' login we do not lock the account; warn via UI instead.
        pass


@app.get('/')
def home():
    return FileResponse(STATIC / 'index.html')


@app.get('/index.html')
def home_alias():
    return FileResponse(STATIC / 'index.html')


@app.get('/privacy.html')
def privacy_policy_page():
    return FileResponse(STATIC / 'privacy.html')


@app.get('/terms.html')
def terms_of_use_page():
    return FileResponse(STATIC / 'terms.html')


@app.get('/login.html')
def login_page():
    return FileResponse(STATIC / 'login.html')


@app.get('/print-report.html')
def print_report_page(request: Request):
    # The template itself has no patient or inventory data; all report data
    # is fetched through authenticated, read-only IMS endpoints.
    try:
        get_user(request)
    except HTTPException:
        return RedirectResponse('/login.html', status_code=302)
    return FileResponse(STATIC / 'print-report.html', headers={'Cache-Control':'no-store'})


@app.get('/dashboard.html')
def dashboard_page(request: Request):
    try:
        get_user(request)
    except HTTPException:
        return RedirectResponse('/login.html', status_code=302)
    return FileResponse(STATIC / 'dashboard.html', headers={'Cache-Control': 'no-store'})


# This is a temporary single-worker throttle for testing. Replace with durable rate
# limiting and security monitoring before a real hospital rollout.
LOGIN_FAILURES = {}
LOGIN_FAILURES_LOCK = threading.Lock()


def login_throttle(username: str):
    import time
    key = username.lower().strip()
    epoch = time.monotonic()
    with LOGIN_FAILURES_LOCK:
        # simple 15-minute rolling window per username
        attempts = [t for t in LOGIN_FAILURES.get(key, []) if epoch - t < 900]
        LOGIN_FAILURES[key] = attempts
        if len(attempts) >= 10:
            err(429, 'Too many sign-in attempts for this account. Try again in 15 minutes.')


def login_failed(username: str):
    import time
    with LOGIN_FAILURES_LOCK:
        LOGIN_FAILURES.setdefault(username.lower().strip(), []).append(time.monotonic())


def login_success(username: str):
    with LOGIN_FAILURES_LOCK:
        LOGIN_FAILURES.pop(username.lower().strip(), None)


@app.post('/api/login')
async def login(request: Request):
    d = await request.json()
    name = validated_text(d, 'username', max_len=80)
    password = str(d.get('password', ''))
    login_throttle(name)
    with db() as c:
        user = c.execute('SELECT * FROM users WHERE username=?', (name,)).fetchone()
        # Consume PBKDF2 cycles even for unknown username to reduce obvious user enumeration.
        if not user or not user['is_active'] or not pw_check(password, user['password_hash']):
            login_failed(name)
            err(401, 'Incorrect username or password')
        login_success(name)
        sid, csrf = secrets.token_hex(32), secrets.token_hex(24)
        expire = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=SESSION_HOURS)).isoformat(timespec='seconds')
        c.execute('INSERT INTO sessions(token_hash,user_id,csrf,expires_at) VALUES (?,?,?,?)',
                  (hashlib.sha256(sid.encode()).hexdigest(), user['id'], csrf, expire))
        audit(c, user['id'], 'LOGIN', {'username': name})
    res = JSONResponse({'ok': True, 'user': name})
    res.set_cookie('wh_session', sid, max_age=SESSION_HOURS*3600, secure=PUBLIC_DEPLOY or os.getenv('COOKIE_SECURE') == '1',
                   httponly=True, samesite='lax', path='/')
    return res


@app.get('/api/me')
def me(request: Request):
    u = get_user(request)
    return {'id': u['id'], 'username': u['username'], 'full_name': u['full_name'], 'role': u['role'],
            'must_change_password': bool(u['must_change_password']), 'branch': u['branch'], 'branches': BRANCHES, 'csrf': u['csrf'], 'is_ultra_admin': is_ultra_admin(u), 'permissions': sorted(WRITE_PERMS[u['role']])}



@app.get('/api/profile')
def get_profile(request: Request):
    u = get_user(request)
    with db(readonly=True) as c:
        row = c.execute('''SELECT id,username,full_name,role,branch,email,phone,age,job_title
            FROM users WHERE id=?''', (u['id'],)).fetchone()
        if not row:
            err(404, 'Account no longer exists')
        return dict(row)


@app.patch('/api/profile')
async def save_profile(request: Request):
    u = get_user(request, require_csrf=True)
    data = await request.json()
    name,email,phone,age,job_title = validate_profile(data)
    with db() as c:
        c.execute('''UPDATE users SET full_name=?,email=?,phone=?,age=?,job_title=? WHERE id=?''',
                  (name,email,phone,age,job_title,u['id']))
        audit(c,u['id'],'PROFILE_UPDATED', {'updated_fields':['full_name','email','phone','age','job_title']})
    return {'ok':True,'full_name':name}

@app.post('/api/logout')
def logout(request: Request):
    u = get_user(request, require_csrf=True)
    sid_hash = hashlib.sha256(request.cookies['wh_session'].encode()).hexdigest()
    with db() as c:
        c.execute('DELETE FROM sessions WHERE token_hash=?', (sid_hash,))
        audit(c, u['id'], 'LOGOUT', {})
    response = JSONResponse({'ok': True})
    response.delete_cookie('wh_session', path='/')
    return response


@app.post('/api/change-password')
async def change_password(request: Request):
    u = get_user(request, require_csrf=True)
    d = await request.json()
    current = str(d.get('current_password', ''))
    new = str(d.get('new_password', ''))
    if len(new) < 8 or len(new) > 128:
        err(422, 'New password must contain 8 to 128 characters')
    with db() as c:
        row = c.execute('SELECT password_hash FROM users WHERE id=?', (u['id'],)).fetchone()
        if not pw_check(current, row['password_hash']):
            err(403, 'Current password is incorrect')
        c.execute('UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?', (pw_hash(new), u['id']))
        # Keep current session but revoke any others.
        current_sid = hashlib.sha256(request.cookies['wh_session'].encode()).hexdigest()
        c.execute('DELETE FROM sessions WHERE user_id=? AND token_hash<>?', (u['id'], current_sid))
        audit(c, u['id'], 'PASSWORD_CHANGED', {})
    return {'ok': True}


@app.get('/api/departments')
def list_departments(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT d.*,
            (SELECT MAX(m.created_at) FROM movements m WHERE m.department_id=d.id AND m.kind IN ('IN','OUT','RETURN')) AS last_shipment_at,
            (SELECT COUNT(*) FROM movements m WHERE m.department_id=d.id AND m.kind IN ('IN','OUT','RETURN')) AS shipment_count
            FROM departments d ORDER BY d.active DESC,d.name''')]


@app.post('/api/departments')
async def create_department(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'department_write')
    d = await request.json()
    name = validated_text(d, 'name')
    try:
        with db() as c:
            # Existing code column stays for old databases; the employee enters only a name.
            provisional = 'NEW-' + secrets.token_hex(8).upper()
            q = c.execute('INSERT INTO departments(code,name,created_at) VALUES(?,?,?)', (provisional, name, now()))
            code = f'DEP-{q.lastrowid:06d}'
            c.execute('UPDATE departments SET code=? WHERE id=?', (code, q.lastrowid))
            audit(c, u['id'], 'DEPARTMENT_CREATED', {'id': q.lastrowid, 'code': code, 'name': name})
            return {'ok': True, 'id': q.lastrowid, 'name': name}
    except sqlite3.IntegrityError:
        err(409, 'Department name or code already exists')


@app.patch('/api/departments/{department_id}')
async def update_department(department_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'department_write')
    d = await request.json()
    name = validated_text(d, 'name')
    try:
        with db() as c:
            old = c.execute('SELECT code,name,active FROM departments WHERE id=?', (department_id,)).fetchone()
            if not old:
                err(404, 'Department not found')
            c.execute('UPDATE departments SET name=?,active=? WHERE id=?',
                      (name, 1 if d.get('active', True) else 0, department_id))
            audit(c, u['id'], 'DEPARTMENT_UPDATED', {'id': department_id, 'name': name, 'code': old['code'], 'active': bool(d.get('active', True)), 'before': {'name': old['name'], 'active': old['active']}, 'after': {'name': name, 'active': 1 if d.get('active', True) else 0}})
        return {'ok': True}
    except sqlite3.IntegrityError:
        err(409, 'Department name or code already exists')


@app.get('/api/books')
def list_books(request: Request):
    get_user(request)
    return {branch: list(BOOKS_BY_BRANCH[branch]) for branch in BRANCHES}


@app.get('/api/units')
def units(request: Request):
    get_user(request)
    return {branch: list(UNITS_BY_BRANCH[branch]) for branch in BRANCHES}


@app.get('/api/items')
def list_items(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT i.*,COALESCE(SUM(b.on_hand),0) stock,COUNT(b.id) batch_count,
                                             COALESCE(NULLIF(i.initial_batch_no,''),
                                                (SELECT batch_no FROM batches WHERE item_id=i.id ORDER BY id DESC LIMIT 1),'') display_batch_no
                                             FROM items i LEFT JOIN batches b ON b.item_id=i.id GROUP BY i.id
                                             ORDER BY i.active DESC,i.branch,i.category,i.name''')]


@app.post('/api/items')
async def create_item(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'item_write')
    d = await request.json()
    branch = require_branch(d.get('branch'))
    restrict_branch(u, branch)
    cat = require_book(branch, d.get('category'))
    name, trade = item_name_fields(d, branch)
    unit = require_unit(branch, d.get('unit'))
    batch_no = item_batch_no(d)
    sku = validated_text(d, 'sku', required=False, max_len=50).upper() or make_sku(branch)
    generic, manufacturer, mfg, exp, info = item_details(d)
    opening_balance = boolean_flag(d.get('opening_balance'), 'opening_balance')
    opening_lots = []
    if opening_balance:
        # All opening lots are validated up front and written atomically.
        opening_lots = opening_lot_details(d)
        # Multiple lot-specific values must not be misrepresented as one
        # catalog reference date or unit price.
        batch_no = opening_lots[0]['batch_no'] if len(opening_lots)==1 else ''
        exp = opening_lots[0]['expiry_date'] if len(opening_lots)==1 else None
        mfg = opening_lots[0]['manufacture_date'] if len(opening_lots)==1 else mfg
        unit_price = opening_lots[0]['unit_price_fils'] if len(opening_lots)==1 else None
    else:
        # New forms omit all lot details unless opening stock is checked.
        # Older API clients may still submit catalog *reference* lot/price
        # fields; accept them as zero-stock metadata for compatibility.
        if d.get('opening_qty') not in (None, ''):
            err(422, 'Enable Opening balance before entering an opening quantity')
        if d.get('price_dinars') in (None, '') and d.get('price_fils_component') in (None, ''):
            unit_price = None
        else:
            unit_price = price_from_fields(d)
    annual_need = annual_need_from_fields(d)
    try:
        with db() as c:
            q = c.execute('''INSERT INTO items(sku,name,category,branch,unit,generic_name,trade_name,initial_batch_no,
                            manufacturer,manufacture_date,expiry_date,information,price_fils,annual_need,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          (sku,name,cat,branch,unit,generic,trade,batch_no,manufacturer,mfg,exp,info,unit_price,annual_need,now()))
            opening_batch_id = None
            opening_batch_ids = []
            opening_code = None
            if not opening_balance and batch_no:
                # Legacy reference-only catalog registration with zero stock.
                c.execute('''INSERT INTO batches(item_id,batch_no,expiry_date,created_at,unit_price_fils)
                    VALUES(?,?,?,?,?)''', (q.lastrowid,batch_no,exp,now(),unit_price))
            if opening_balance:
                # One movement for the complete initial count, with one
                # movement line and stored stock lot per distinct lot entry.
                move = c.execute('''INSERT INTO movements(code,kind,paper_ref,source,notes,route,created_by,created_at)
                    VALUES(?,?,?,?,?,?,?,?)''', ('TEMP-'+secrets.token_hex(6),'ADJUST_PLUS','OPENING-BALANCE',
                    'رصيد افتتاحي','Initial counted inventory (multiple lots supported)',
                    'opening_balance',u['id'],now()))
                opening_code = f'OPEN-{move.lastrowid:06d}'
                c.execute('UPDATE movements SET code=? WHERE id=?', (opening_code,move.lastrowid))
                for lot in opening_lots:
                    bid = c.execute('''INSERT INTO batches(item_id,batch_no,expiry_date,on_hand,created_at,unit_price_fils,manufacture_date)
                        VALUES(?,?,?,?,?,?,?)''', (q.lastrowid,lot['batch_no'],lot['expiry_date'],
                        lot['qty'],now(),lot['unit_price_fils'],lot['manufacture_date'])).lastrowid
                    opening_batch_ids.append(bid)
                    c.execute('''INSERT INTO movement_lines(movement_id,batch_id,qty,direction,unit_price_fils)
                        VALUES(?,?,?,?,?)''', (move.lastrowid,bid,lot['qty'],1,lot['unit_price_fils']))
                opening_batch_id = opening_batch_ids[0]
                audit(c,u['id'],'OPENING_BALANCE_CREATED',{
                    'item_id':q.lastrowid,'movement_id':move.lastrowid,'code':opening_code,
                    'batch_id':opening_batch_id,'batch_ids':opening_batch_ids,
                    'batch_no':opening_lots[0]['batch_no'] if len(opening_lots)==1 else '',
                    'expiry_date':opening_lots[0]['expiry_date'] if len(opening_lots)==1 else None,
                    'quantity':sum(lot['qty'] for lot in opening_lots),
                    'unit_price_fils':opening_lots[0]['unit_price_fils'] if len(opening_lots)==1 else None,
                    'lot_count':len(opening_lots), 'lots':opening_lots,'branch':branch})
            audit(c, u['id'], 'ITEM_CREATED', {'id':q.lastrowid,'sku':sku,'name':name,'trade_name':trade,
                  'branch':branch,'book_category':cat,'unit':unit,'initial_batch_no':batch_no,
                  'manufacturer':manufacturer,'manufacture_date':mfg,'expiry_date':exp,'information':info,
                  'price_fils':unit_price,'annual_need':annual_need,'opening_balance':opening_balance,
                  'opening_movement_code':opening_code})
            return {'ok': True, 'id': q.lastrowid, 'sku':sku, 'opening_balance':opening_balance,
                    'opening_batch_id':opening_batch_id,'opening_batch_ids':opening_batch_ids,'opening_movement_code':opening_code}
    except sqlite3.IntegrityError:
        err(409, 'Item code or registered batch already exists')


@app.patch('/api/items/{item_id}')
async def update_item(item_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'item_write')
    d = await request.json()
    branch = require_branch(d.get('branch'))
    try:
        with db() as c:
            old = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
            if not old:
                err(404, 'Item not found')
            restrict_branch(u, old['branch'])
            restrict_branch(u, branch)
            category = require_book(branch, d.get('category'))
            name, trade = item_name_fields(d, branch)
            generic, manufacturer, mfg, exp, info = item_details(d)
            # Legacy products may not have a catalog reference price. Stock-lot
            # valuation is maintained independently and never modified here.
            if d.get('price_dinars') in (None, '') and d.get('price_fils_component') in (None, ''):
                unit_price = old['price_fils']
            else:
                unit_price = price_from_fields(d)
            annual_need = annual_need_from_fields(d, prior=old['annual_need'])
            # Hidden legacy generic-name field must survive an edit in the new form.
            if 'generic_name' not in d:
                generic = old['generic_name']
            batch_no = item_batch_no(d)
            unit = require_unit(branch, d.get('unit'), legacy_unit=old['unit'] if branch==old['branch'] or old['branch'] is None else None)
            sku = validated_text(d, 'sku', required=False, max_len=50).upper() or old['sku']
            has_movements = c.execute('SELECT 1 FROM movement_lines l JOIN batches b ON l.batch_id=b.id WHERE b.item_id=? LIMIT 1', (item_id,)).fetchone()
            if has_movements and old['unit'] != unit:
                err(409, 'Cannot change the unit after stock movements have been recorded')
            if has_movements and old['branch'] is not None and old['branch'] != branch:
                err(409, 'Cannot transfer an item to another branch after movements were recorded')
            # An edited reference batch NEVER changes expiry of a received/historical batch.
            # If it's a new batch, seed it at zero stock for future receiving.
            existing_batch = c.execute('SELECT id FROM batches WHERE item_id=? AND batch_no=?',
                                       (item_id,batch_no)).fetchone()
            if batch_no and not existing_batch:
                c.execute('INSERT INTO batches(item_id,batch_no,expiry_date,created_at,unit_price_fils) VALUES(?,?,?,?,?)',
                          (item_id,batch_no,exp,now(),unit_price))
            c.execute('''UPDATE items SET sku=?,name=?,category=?,branch=?,unit=?,generic_name=?,trade_name=?,initial_batch_no=?,
                         manufacturer=?,manufacture_date=?,expiry_date=?,information=?,price_fils=?,annual_need=?,active=? WHERE id=?''',
                      (sku,name,category,branch,unit,generic,trade,batch_no,manufacturer,mfg,exp,info,unit_price,annual_need,
                       1 if d.get('active',True) else 0,item_id))
            item_keys = ('sku','name','category','branch','unit','generic_name','trade_name','initial_batch_no',
                         'manufacturer','manufacture_date','expiry_date','information','price_fils','annual_need','active')
            new_snapshot = dict(c.execute('SELECT * FROM items WHERE id=?',(item_id,)).fetchone())
            audit(c, u['id'], 'ITEM_UPDATED', {'id':item_id,'sku':sku,'name':name,'trade_name':trade,
                  'branch':branch,'book_category':category,'unit':unit,'reference_batch_no':batch_no,
                  'manufacturer':manufacturer,'manufacture_date':mfg,'expiry_date':exp,'information':info,'price_fils':unit_price,'annual_need':annual_need,
                  'before':{k:old[k] for k in item_keys}, 'after':{k:new_snapshot[k] for k in item_keys}})
        return {'ok': True}
    except sqlite3.IntegrityError:
        err(409, 'Item code or registered batch already exists')


@app.get('/api/batches')
def batches(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT b.id,b.item_id,b.batch_no,b.expiry_date,b.manufacture_date,b.on_hand,b.unit_price_fils,
                                             i.sku,i.name item_name,i.unit,i.category,i.branch,i.active item_active
                                             FROM batches b JOIN items i ON i.id=b.item_id
                                             ORDER BY b.on_hand DESC,i.name,b.expiry_date''')]


@app.get('/api/items/{item_id}/history')
def item_full_history(item_id: int, request: Request, limit: int = 50, offset: int = 0):
    """Read-only, paginated stock ledger for one product; all recorded batches/prices.

    Kept separate from /api/movements (which deliberately limits its summary to
    the latest 500 transactions). This endpoint does not modify inventory.
    """
    get_user(request)
    if limit < 1 or limit > 100 or offset < 0:
        err(422, 'Invalid history page (limit 1–100 and offset >= 0)')
    with db(readonly=True) as c:
        if not c.execute('SELECT 1 FROM items WHERE id=?', (item_id,)).fetchone():
            err(404, 'Item not found')
        count = c.execute("""SELECT COUNT(*) AS n FROM movement_lines ml
                              JOIN batches b ON b.id=ml.batch_id
                              WHERE b.item_id=?""", (item_id,)).fetchone()['n']
        rows = c.execute("""SELECT ml.id,ml.qty,ml.direction,ml.unit_price_fils,
                                  b.batch_no,b.expiry_date,b.manufacture_date,m.code,m.kind,m.route,
                                  m.created_at,m.paper_ref,m.dispatch_ref,m.source,
                                  m.external_destination,d.name AS department_name,
                                  u.username AS operator
                           FROM movement_lines ml
                           JOIN batches b ON b.id=ml.batch_id
                           JOIN movements m ON m.id=ml.movement_id
                           LEFT JOIN departments d ON d.id=m.department_id
                           JOIN users u ON u.id=m.created_by
                           WHERE b.item_id=? ORDER BY ml.id DESC LIMIT ? OFFSET ?""",
                         (item_id, limit, offset)).fetchall()
        return {'item_id':item_id, 'total':count, 'offset':offset,
                'limit':limit,'rows':[dict(r) for r in rows]}



def shipment_history_page(c, *, item_id=None, department_id=None, limit=30, offset=0):
    """Return document headers with all their lines, ordered newest first."""
    if not isinstance(limit,int) or not isinstance(offset,int) or not 1<=limit<=100 or offset<0:
        err(422, 'Invalid history page')
    if item_id is not None:
        exists = c.execute('SELECT 1 FROM items WHERE id=?', (item_id,)).fetchone()
        if not exists: err(404, 'Item not found')
        where = """m.id IN (SELECT l.movement_id FROM movement_lines l
                        JOIN batches b ON l.batch_id=b.id WHERE b.item_id=?)"""
        args = (item_id,)
    else:
        exists = c.execute('SELECT 1 FROM departments WHERE id=?', (department_id,)).fetchone()
        if not exists: err(404, 'Department not found')
        where = 'm.department_id=?'
        args = (department_id,)
    total = c.execute(f'SELECT COUNT(*) AS n FROM movements m WHERE {where}', args).fetchone()['n']
    records = [dict(r) for r in c.execute(f"""SELECT m.*,d.name AS department_name,u.username AS operator
        FROM movements m LEFT JOIN departments d ON m.department_id=d.id
        JOIN users u ON m.created_by=u.id
        WHERE {where} ORDER BY m.id DESC LIMIT ? OFFSET ?""", (*args,limit,offset))]
    if records:
        ids = [r['id'] for r in records]
        placeholders = ','.join('?' for _ in ids)
        lines = c.execute(f"""SELECT ml.movement_id,ml.qty,ml.direction,ml.unit_price_fils,
            i.id AS item_id,i.sku,i.name AS item_name,i.trade_name,i.unit,
            b.id AS lot_id,b.batch_no,b.expiry_date,b.manufacture_date
            FROM movement_lines ml
            JOIN batches b ON b.id=ml.batch_id JOIN items i ON i.id=b.item_id
            WHERE ml.movement_id IN ({placeholders}) ORDER BY ml.id""", ids).fetchall()
        grouped = {}
        for row in lines:
            grouped.setdefault(row['movement_id'],[]).append(dict(row))
        for record in records:
            record['lines'] = grouped.get(record['id'],[])
    return {'total':total, 'limit':limit, 'offset':offset, 'shipments':records}


@app.get('/api/items/{item_id}/shipments')
def item_shipments(item_id: int, request: Request, limit: int = 30, offset: int = 0):
    get_user(request)
    with db(readonly=True) as c:
        return shipment_history_page(c, item_id=item_id, limit=limit, offset=offset)


@app.get('/api/departments/{department_id}/shipments')
def department_shipments(department_id: int, request: Request, limit: int = 30, offset: int = 0):
    get_user(request)
    with db(readonly=True) as c:
        return shipment_history_page(c, department_id=department_id, limit=limit, offset=offset)

@app.get('/api/movements-page')
def movements_page(request: Request, limit: int = 20, offset: int = 0, q: str = '', kind: str = ''):
    # Database-backed pagination without the legacy 500-row cap.
    get_user(request)
    limit = max(1, min(100, limit)); offset = max(0, offset)
    q = q.strip()[:160]
    conditions = ['EXISTS (SELECT 1 FROM movement_lines any_line WHERE any_line.movement_id = m.id)']
    args = []
    if kind in ('IN', 'OUT', 'RETURN', 'ADJUST_PLUS', 'ADJUST_MINUS'):
        conditions.append('m.kind=?'); args.append(kind)
    if q:
        like = '%' + q.lower() + '%'
        conditions.append('''(LOWER(COALESCE(m.code,'')) LIKE ? OR LOWER(COALESCE(m.paper_ref,'')) LIKE ?
            OR LOWER(COALESCE(m.dispatch_ref,'')) LIKE ? OR LOWER(COALESCE(m.source,'')) LIKE ?
            OR LOWER(COALESCE(m.external_destination,'')) LIKE ? OR LOWER(COALESCE(d.name,'')) LIKE ?
            OR LOWER(COALESCE(u.username,'')) LIKE ? OR EXISTS (
                SELECT 1 FROM movement_lines ml2 JOIN batches b2 ON b2.id=ml2.batch_id
                    JOIN items i2 ON i2.id=b2.item_id
                WHERE ml2.movement_id=m.id AND
                (LOWER(i2.name) LIKE ? OR LOWER(COALESCE(i2.trade_name,'')) LIKE ?
                  OR LOWER(COALESCE(i2.sku,'')) LIKE ? OR LOWER(b2.batch_no) LIKE ?)))''')
        args.extend([like] * 11)
    where = ' AND '.join(conditions)
    joins = '''FROM movements m LEFT JOIN departments d ON d.id=m.department_id
                    LEFT JOIN users p ON p.id=m.trusted_pharmacist_id
                    JOIN users u ON u.id=m.created_by'''
    with db(readonly=True) as c:
        total = c.execute(f'SELECT COUNT(*) {joins} WHERE {where}',args).fetchone()[0]
        rows = [dict(x) for x in c.execute(f'''SELECT m.*,d.name department_name,u.username creator,
                       p.full_name trusted_pharmacist_name,p.username trusted_pharmacist_username,
                       (SELECT COUNT(*) FROM movement_lines mlc WHERE mlc.movement_id=m.id) line_count,
                       (SELECT SUM(qty) FROM movement_lines mls WHERE mls.movement_id=m.id) total_units
                       {joins} WHERE {where} ORDER BY m.id DESC LIMIT ? OFFSET ?''',args+[limit,offset])]
        ids = [x['id'] for x in rows]
        if ids:
            placeholders = ','.join('?' for _ in ids)
            lines = [dict(x) for x in c.execute(f'''SELECT ml.id line_id,ml.movement_id,ml.qty,ml.direction,
                        ml.unit_price_fils,b.batch_no,b.expiry_date,b.manufacture_date,
                        i.sku,i.name item_name,i.unit FROM movement_lines ml
                        JOIN batches b ON b.id=ml.batch_id JOIN items i ON i.id=b.item_id
                        WHERE ml.movement_id IN ({placeholders}) ORDER BY ml.id''', ids)]
            grouped = {}
            for line in lines: grouped.setdefault(line['movement_id'],[]).append(line)
            for row in rows: row['lines'] = grouped.get(row['id'],[])
        return {'total':total,'rows':rows,'limit':limit,'offset':offset}


@app.get('/api/movements')
def movements(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        res = [dict(x) for x in c.execute('''SELECT m.*,d.name department_name,u.username creator,
                       p.full_name trusted_pharmacist_name,p.username trusted_pharmacist_username,
                       COUNT(l.id) line_count,SUM(l.qty) total_units
                       FROM movements m LEFT JOIN departments d ON d.id=m.department_id
                       LEFT JOIN users p ON p.id=m.trusted_pharmacist_id
                       JOIN users u ON u.id=m.created_by JOIN movement_lines l ON l.movement_id=m.id
                       GROUP BY m.id ORDER BY m.id DESC LIMIT 500''')]
        ids = [x['id'] for x in res]
        if ids:
            ph = ','.join('?' for _ in ids)
            lines = [dict(x) for x in c.execute(f'''SELECT ml.id line_id,ml.movement_id,ml.qty,ml.direction,ml.unit_price_fils,b.batch_no,b.expiry_date,b.manufacture_date,
                             i.sku,i.name item_name,i.unit FROM movement_lines ml
                             JOIN batches b ON b.id=ml.batch_id JOIN items i ON i.id=b.item_id
                             WHERE ml.movement_id IN ({ph}) ORDER BY ml.id''', ids)]
            by_id = {}
            for line in lines:
                by_id.setdefault(line['movement_id'], []).append(line)
            for m in res:
                m['lines'] = by_id.get(m['id'], [])
        return res


def movement_code(kind, mid):
    return {'IN':'IN','OUT':'OUT','RETURN':'RET','ADJUST_PLUS':'ADJ','ADJUST_MINUS':'ADJ'}[kind] + f'-{mid:06d}'



def fefo_deviations(c: sqlite3.Connection, lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect outgoing lots chosen while earlier-expiring usable stock is still available.

    All lines of the shipment are considered together: it is valid to issue from
    a later lot after the same outgoing document consumes every earlier lot.
    Equal-expiry lots are interchangeable; unknown-expiry lots rank last.
    """
    from collections import defaultdict
    chosen: dict[int, int] = defaultdict(int)
    item_ids: set[int] = set()
    today = dt.datetime.now(ZoneInfo('Asia/Baghdad')).date().isoformat()
    for line in lines:
        bid = integer(line, 'batch_id', 1)
        qty = integer(line, 'qty', 1, 100_000_000)
        batch = c.execute('SELECT item_id FROM batches WHERE id=?', (bid,)).fetchone()
        if not batch:
            err(422, 'Selected batch does not exist')
        chosen[bid] += qty
        item_ids.add(batch['item_id'])
    deviations = []
    for item_id in item_ids:
        lots = [dict(row) for row in c.execute("""SELECT b.id,b.batch_no,b.expiry_date,b.on_hand
            FROM batches b JOIN items i ON i.id=b.item_id
            WHERE b.item_id=? AND b.on_hand>0 AND i.active=1
              AND (b.expiry_date IS NULL OR b.expiry_date>=?)
            ORDER BY CASE WHEN b.expiry_date IS NULL THEN 1 ELSE 0 END,
                     b.expiry_date, b.id""", (item_id, today))]
        for selected in lots:
            if chosen.get(selected['id'], 0) <= 0:
                continue
            selected_date = selected['expiry_date'] or '9999-12-31'
            earlier = next((other for other in lots
                            if (other['expiry_date'] or '9999-12-31') < selected_date
                            and other['on_hand'] > chosen.get(other['id'], 0)), None)
            if earlier is not None:
                deviations.append({
                    'item_id': item_id,
                    'selected_batch_id': selected['id'],
                    'selected_batch_no': selected['batch_no'],
                    'earlier_batch_id': earlier['id'],
                    'earlier_batch_no': earlier['batch_no'],
                    'earlier_expiry': earlier['expiry_date'],
                    'earlier_remaining': earlier['on_hand'] - chosen.get(earlier['id'], 0),
                })
    return deviations

@app.post('/api/movements')
async def create_movement(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'movement_write')
    d = await request.json()
    kind = str(d.get('kind', ''))
    if kind not in ('IN','OUT','RETURN','ADJUST_PLUS','ADJUST_MINUS'):
        err(422, 'Invalid movement type')
    if kind.startswith('ADJUST'):
        permit(u, 'adjust')

    # Route is authoritative: old clients may omit it for legacy inbound receipts,
    # but all new outgoing transfers must choose one of three explicit routes.
    route = str(d.get('route') or '').strip()
    if kind == 'OUT':
        if route not in OUT_ROUTES:
            err(422, 'Choose one of the three outgoing shipment routes')
    elif kind == 'IN':
        route = route or 'purchase_receipt'  # Legacy quick-receipt compatibility.
        if route not in IN_ROUTES or route == 'internal_return':
            err(422, 'Choose a valid incoming receipt route')
    elif kind == 'RETURN':
        route = route or 'internal_return'
        if route != 'internal_return':
            err(422, 'Department returns must use the internal return route')
    elif route:
        err(422, 'Adjustment transactions do not have a shipment route')

    emergency = boolean_flag(d.get('emergency_pending'), 'emergency_pending')
    if emergency and not (kind == 'OUT' and route == 'department_issue'):
        err(422, 'Delayed paperwork is available only for emergency department issues')
    department_id = None
    destination_type = None
    external_destination = ''
    source = ''
    trusted_id = None  # Legacy linkage retained for older history rows.
    pharmacist_name = ''
    authorization_ref = ''
    if kind == 'OUT':
        if route == 'department_issue':
            destination_type = 'department'
            department_id = integer(d, 'department_id', minimum=1)
            if str(d.get('external_destination') or '').strip():
                err(422, 'Department issues cannot specify an external destination')
        else:
            destination_type = 'external'
            if d.get('department_id') not in (None, '', 0):
                err(422, 'Transfer routes cannot specify a hospital department ID')
            external_destination = (validated_text(d, 'external_destination', max_len=180)
                                    if route == 'external_transfer_out' else PHARMACY_DESTINATION)
            pharmacist_name = validated_text(d, 'trusted_pharmacist_name', max_len=160)
            authorization_ref = validated_text(d, 'authorization_ref', max_len=90)
    elif kind == 'IN':
        if route == 'pharmacy_receipt':
            source = PHARMACY_DESTINATION
        elif route == 'purchase_receipt':
            source = validated_text(d, 'source', max_len=180)
        elif route == 'external_transfer_in':
            source = validated_text(d, 'source', max_len=180)
            pharmacist_name = validated_text(d, 'trusted_pharmacist_name', max_len=160)
            authorization_ref = validated_text(d, 'authorization_ref', max_len=90)
    elif kind == 'RETURN':
        department_id = integer(d, 'department_id', minimum=1)
    else:
        source = validated_text(d, 'source', required=False, max_len=180)

    paper_required = kind in ('IN','OUT','RETURN') and not emergency
    paper_ref = validated_text(d, 'paper_ref', required=paper_required, max_len=80)
    dispatch_required = (kind == 'RETURN' or (kind == 'OUT' and route == 'department_issue')) and not emergency
    dispatch_ref = validated_text(d, 'dispatch_ref', required=dispatch_required, max_len=80)
    notes = validated_text(d, 'notes', required=False, max_len=500)
    fefo_override_reason = validated_text(d, 'fefo_override_reason', required=False, max_len=250) if kind == 'OUT' else ''
    lines = d.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
        err(422, 'Provide 1 to 50 shipment line items')

    # Database transaction is atomic: no partial issue if any line or document fails.
    with db() as c:
        if department_id and not c.execute('SELECT 1 FROM departments WHERE id=? AND active=1', (department_id,)).fetchone():
            err(422, 'Choose an active hospital department')
        fefo_warnings = fefo_deviations(c, lines) if kind == 'OUT' else []
        if fefo_warnings and not fefo_override_reason:
            first = fefo_warnings[0]
            err(409, f"FEFO: Earlier-expiring batch {first['earlier_batch_no']} "
                     f"(expiry {first['earlier_expiry'] or 'unknown'}) still has "
                     f"{first['earlier_remaining']} unit(s) available. "
                     'Select it first, or enter a documented FEFO override reason.')
        if fefo_warnings:
            notes = (notes + '\n' if notes else '') + 'FEFO override: ' + fefo_override_reason
        created = c.execute('''INSERT INTO movements(
                          code,kind,paper_ref,department_id,source,notes,destination_type,
                          external_destination,dispatch_ref,route,trusted_pharmacist_id,
                          trusted_pharmacist_name,authorization_ref,paperwork_pending,created_by,created_at)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                          ('TEMP-'+secrets.token_hex(6),kind,paper_ref,department_id,source,notes,
                           destination_type,external_destination,dispatch_ref,route,trusted_id,
                           pharmacist_name,authorization_ref,1 if emergency else 0,u['id'],now()))
        mid = created.lastrowid
        code = movement_code(kind, mid)
        c.execute('UPDATE movements SET code=? WHERE id=?', (code,mid))
        direction = 1 if kind in ('IN','RETURN','ADJUST_PLUS') else -1
        outgoing_price_overrides = 0
        for line in lines:
            qty = integer(line,'qty',1,100_000_000)
            if kind == 'IN':
                iid = integer(line,'item_id',1)
                batchno = validated_text(line,'batch_no',max_len=90)
                exp = dated(line.get('expiry_date'))
                item = c.execute('SELECT id,branch,price_fils FROM items WHERE id=? AND active=1', (iid,)).fetchone()
                if not item:
                    err(422, 'Selected item does not exist or is inactive')
                restrict_branch(u, item['branch'])
                # A receipt's price belongs to its own inventory lot, not to the
                # catalog-wide reference price and not to previous receipts.
                received_price = receipt_line_price(line, item['price_fils'])
                batch = c.execute("""SELECT id FROM batches WHERE item_id=? AND batch_no=?
                    AND COALESCE(expiry_date,'')=COALESCE(?,'')
                    AND COALESCE(unit_price_fils,-1)=COALESCE(?,-1)""",
                    (iid,batchno,exp,received_price)).fetchone()
                batch_id = batch['id'] if batch else c.execute(
                    'INSERT INTO batches(item_id,batch_no,expiry_date,created_at,unit_price_fils) VALUES(?,?,?,?,?)',
                    (iid,batchno,exp,now(),received_price)).lastrowid
            else:
                batch_id = integer(line,'batch_id',1)
                batch = c.execute('''SELECT b.id,b.expiry_date,b.item_id,b.batch_no,b.unit_price_fils,
                                          i.branch,i.active item_active
                                   FROM batches b JOIN items i ON i.id=b.item_id WHERE b.id=?''',
                                  (batch_id,)).fetchone()
                if not batch or not batch['item_active']:
                    err(422,'Batch not found or product is inactive')
                restrict_branch(u, batch['branch'])
                # If the outgoing UI sends a catalog product, it must match the
                # exact selected lot. Never let mismatched product/lot pairs pass.
                if kind == 'OUT' and line.get('item_id') not in (None, '') and integer(line, 'item_id', 1) != batch['item_id']:
                    err(422, 'Selected product does not match the selected stock lot')
                if kind == 'OUT' and batch['expiry_date'] and batch['expiry_date'] < dt.datetime.now(ZoneInfo('Asia/Baghdad')).date().isoformat():
                    err(409, 'Cannot issue expired stock')
            if direction > 0:
                c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=?', (qty,batch_id))
            else:
                r = c.execute('UPDATE batches SET on_hand=on_hand-? WHERE id=? AND on_hand>=?',
                              (qty,batch_id,qty))
                if r.rowcount != 1:
                    err(409, 'Insufficient stock in the selected batch. Shipment not saved.')
            original_price = c.execute('SELECT unit_price_fils FROM batches WHERE id=?', (batch_id,)).fetchone()['unit_price_fils']
            unit_price = original_price
            # A shipment may explicitly value the outgoing units at a different
            # price. Snapshot it on the movement line, NEVER on the received lot.
            if kind == 'OUT' and ('price_dinars' in line or 'price_fils_component' in line):
                if 'price_dinars' not in line or 'price_fils_component' not in line:
                    err(422, 'Provide both dinar and fils components for outgoing unit price')
                unit_price = price_from_fields(line)
                if unit_price != original_price:
                    outgoing_price_overrides += 1
            c.execute('INSERT INTO movement_lines(movement_id,batch_id,qty,direction,unit_price_fils) VALUES (?,?,?,?,?)',
                      (mid,batch_id,qty,direction,unit_price))
        audit(c,u['id'],'MOVEMENT_CREATED',{
            'id':mid,'code':code,'kind':kind,'route':route,'paper_ref':paper_ref,
            'dispatch_ref':dispatch_ref,'department_id':department_id,'source':source,
            'destination':external_destination,'trusted_pharmacist_name':pharmacist_name,
            'authorization_ref':authorization_ref,
            'emergency_pending':emergency,'line_count':len(lines),
            'outgoing_price_overrides':outgoing_price_overrides,
            'fefo_deviations':fefo_warnings,'fefo_override_reason':fefo_override_reason if fefo_warnings else ''})
    return {'ok':True,'code':code,'id':mid,'paperwork_pending':emergency,
            'fefo_override':bool(fefo_warnings)}


@app.patch('/api/movements/{movement_id}/paperwork')
async def complete_emergency_paperwork(movement_id: int, request: Request):
    # Append missing emergency paperwork while preserving the original issue and stock.
    u = get_user(request, require_csrf=True)
    permit(u, 'movement_write')
    d = await request.json()
    order_ref = validated_text(d, 'paper_ref', max_len=80)
    dispatch_ref = validated_text(d, 'dispatch_ref', max_len=80)
    with db() as c:
        movement = c.execute('SELECT * FROM movements WHERE id=?', (movement_id,)).fetchone()
        if not movement:
            err(404, 'Movement not found')
        if not (movement['kind'] == 'OUT' and movement['route'] == 'department_issue'
                and movement['paperwork_pending'] == 1):
            err(409, 'Only outstanding emergency department paperwork can be completed')
        rows = c.execute('''SELECT DISTINCT i.branch FROM movement_lines l JOIN batches b ON l.batch_id=b.id
                             JOIN items i ON b.item_id=i.id WHERE l.movement_id=?''', (movement_id,)).fetchall()
        for r in rows:
            restrict_branch(u, r['branch'])
        old = {'paper_ref':movement['paper_ref'],'dispatch_ref':movement['dispatch_ref']}
        c.execute('''UPDATE movements SET paper_ref=?,dispatch_ref=?,paperwork_pending=0,
                     paperwork_completed_at=?,paperwork_completed_by=? WHERE id=?''',
                  (order_ref,dispatch_ref,now(),u['id'],movement_id))
        audit(c,u['id'],'EMERGENCY_PAPERWORK_COMPLETED',{
            'movement_id':movement_id,'code':movement['code'],'previous':old,
            'paper_ref':order_ref,'dispatch_ref':dispatch_ref})
    return {'ok':True,'code':movement['code'],'paperwork_pending':False}


@app.get('/api/dashboard')
def dashboard_data(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        total_items = c.execute('SELECT COUNT(*) n FROM items WHERE active=1').fetchone()['n']
        total_units = c.execute('SELECT COALESCE(SUM(on_hand),0) n FROM batches').fetchone()['n']
        dept = c.execute('SELECT COUNT(*) n FROM departments WHERE active=1').fetchone()['n']
        movements_count = c.execute('SELECT COUNT(*) n FROM movements').fetchone()['n']
        low = c.execute('''SELECT COUNT(*) n FROM (SELECT i.id FROM items i LEFT JOIN batches b ON i.id=b.item_id
                           WHERE i.active=1 AND i.min_stock>0 GROUP BY i.id HAVING COALESCE(SUM(b.on_hand),0)<i.min_stock)''').fetchone()['n']
        soon = c.execute('''SELECT COUNT(*) n FROM batches WHERE on_hand>0 AND expiry_date IS NOT NULL
                            AND expiry_date>=date('now') AND expiry_date<=date('now','+60 days')''').fetchone()['n']
        return {'items':total_items,'stock':total_units,'departments':dept,'movements':movements_count,'low_stock':low,'expiry_soon':soon}


# V4.15 — Warehouse positions: adjustable cutoff and MONTHLY-requirement ratios.
# Default expiry window remains calendar-month based: through the last day
# of the current month *next year*, not a rolling 365-day period.
def position_window():
    today = dt.datetime.now(ZoneInfo('Asia/Baghdad')).date()
    year, month = today.year + 1, today.month
    next_month = dt.date(year + (month == 12), month % 12 + 1, 1)
    cutoff_exclusive = next_month.isoformat()
    last_included = (next_month - dt.timedelta(days=1)).isoformat()
    return today.isoformat(), cutoff_exclusive, last_included


@app.get('/api/positions')
def warehouse_positions(request: Request, expiry_before: str | None = None,
                        scarce_pct: str | None = None, surplus_pct: str | None = None):
    get_user(request)  # Same authenticated viewing rights as the inventory.
    today, default_end, _ = position_window()
    if expiry_before not in (None, ''):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', expiry_before):
            err(422, 'Expiry cutoff must be a date formatted YYYY-MM-DD')
        try:
            end_date = dt.date.fromisoformat(expiry_before)
        except ValueError:
            err(422, 'Expiry cutoff is not a valid date')
        if not 1900 <= end_date.year <= 2200:
            err(422, 'Expiry cutoff year is out of range')
        end_exclusive = end_date.isoformat()
    else:
        end_exclusive = default_end
    last_included = (dt.date.fromisoformat(end_exclusive) - dt.timedelta(days=1)).isoformat()
    # Monthly need is annual_need / 12. The default comparisons are strict:
    #   scarce: usable stock < 20% of monthly need
    #   surplus: usable stock > 120% of monthly need
    # Passing a percentage overrides only that report's default.
    scarce_limit = percent_parameter(scarce_pct, 'scarce_pct')
    surplus_limit = percent_parameter(surplus_pct, 'surplus_pct')
    if scarce_limit is None:
        scarce_limit = Decimal('20')
    if surplus_limit is None:
        surplus_limit = Decimal('120')
    with db(readonly=True) as c:
        missing = [dict(r) for r in c.execute('''
            SELECT i.id AS item_id, i.sku, i.name, i.trade_name, i.generic_name, i.information, i.branch,
                   i.category, i.unit, i.annual_need, COALESCE(SUM(b.on_hand), 0) AS stock,
                   COUNT(b.id) AS lot_count
            FROM items i LEFT JOIN batches b ON b.item_id = i.id
            WHERE i.active = 1
            GROUP BY i.id
            HAVING COALESCE(SUM(b.on_hand), 0) <= 0
            ORDER BY i.branch, i.name COLLATE NOCASE, i.id
        ''')]
        expiring = [dict(r) for r in c.execute('''
            SELECT b.id AS lot_id, i.id AS item_id, i.sku, i.name,
                   i.trade_name, i.generic_name, i.information, i.branch, i.category, i.unit,
                   b.batch_no, b.expiry_date, b.unit_price_fils,
                   b.on_hand AS stock
            FROM batches b JOIN items i ON i.id=b.item_id
            WHERE i.active=1 AND b.on_hand > 0
              AND b.expiry_date >= ? AND b.expiry_date < ?
            ORDER BY b.expiry_date ASC, i.name COLLATE NOCASE, b.id
        ''', (today, end_exclusive))]
        expired_stock = c.execute('''
            SELECT COUNT(*) AS lots FROM batches b JOIN items i ON i.id=b.item_id
            WHERE i.active=1 AND b.on_hand>0 AND b.expiry_date IS NOT NULL
              AND b.expiry_date < ?
        ''', (today,)).fetchone()['lots']
        # Ratio compares usable, dated, unexpired stock against MONTHLY need.
        # Expired and unknown-expiry lots are excluded from usable stock.
        balance_rows = [dict(r) for r in c.execute('''
            SELECT i.id AS item_id, i.sku, i.name, i.trade_name, i.generic_name,
                   i.information, i.branch, i.category, i.unit, i.annual_need,
                   COALESCE(SUM(CASE WHEN b.expiry_date >= ? THEN b.on_hand ELSE 0 END), 0) AS stock,
                   COALESCE(SUM(b.on_hand), 0) AS physical_stock
            FROM items i LEFT JOIN batches b ON b.item_id = i.id
            WHERE i.active=1
            GROUP BY i.id ORDER BY i.branch, i.name COLLATE NOCASE, i.id
        ''', (today,))]
    scarce, surplus, without_annual = [], [], 0
    for record in balance_rows:
        need = record['annual_need']
        if not need or need <= 0:
            without_annual += 1
            continue
        monthly_need = Decimal(need) / Decimal(12)
        percent = Decimal(record['stock']) * 100 / monthly_need
        record['monthly_need'] = round(float(monthly_need), 3)
        record['percent_of_monthly_need'] = round(float(percent), 2)
        # Retain the historical response key for older frontends, but its
        # value is now expressed relative to monthly requirement.
        record['percent_of_need'] = record['percent_of_monthly_need']
        if percent < scarce_limit:
            scarce.append(record.copy())
        if percent > surplus_limit:
            surplus.append(record.copy())
    scarce.sort(key=lambda x: (x['percent_of_need'], x['name'].casefold()))
    surplus.sort(key=lambda x: (-x['percent_of_need'], x['name'].casefold()))
    return {
        'as_of': today, 'expiry_before': end_exclusive,
        'expiry_default_before': default_end,
        'expiry_last_included': last_included,
        'missing': missing, 'near_expiry': expiring,
        'scarce': scarce, 'surplus': surplus,
        'scarce_pct': str(scarce_limit) if scarce_limit is not None else None,
        'surplus_pct': str(surplus_limit) if surplus_limit is not None else None,
        'percent_basis': 'monthly',
        'monthly_need_formula': 'annual_need / 12',
        'default_scarce_pct': '20', 'default_surplus_pct': '120',
        'annual_need_unset_count': without_annual,
        'expired_lot_count': expired_stock,
    }


@app.get('/api/staff-directory')
def staff_directory(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        # Public account directory only: never expose password hashes or session tokens.
        return [dict(r) for r in c.execute('''SELECT id,username,full_name,branch
                    FROM users WHERE is_active=1 ORDER BY full_name COLLATE NOCASE,username''')]


@app.get('/api/users')
def list_users(request: Request):
    u = get_user(request)
    permit(u,'users')
    with db(readonly=True) as c:
        return [dict(x) | {'is_ultra_admin': is_ultra_admin(x)} for x in c.execute('''SELECT id,username,full_name,role,branch,is_active,must_change_password,created_at
                                               FROM users ORDER BY is_active DESC,id''')]


@app.get('/api/users/{user_id}/profile')
def user_profile_for_admin(user_id: int, request: Request):
    u = get_user(request)
    if u['role'] != 'admin':
        err(403, 'Only administrators can view employee profile details')
    with db(readonly=True) as c:
        row = c.execute('''SELECT id,username,full_name,role,branch,email,phone,age,job_title,is_active
                             FROM users WHERE id=?''' , (user_id,)).fetchone()
        if row is None:
            err(404, 'User not found')
        return dict(row)


@app.post('/api/users')
async def create_user(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u,'users')
    d = await request.json()
    username = validated_text(d,'username',max_len=50).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,50}',username):
        err(422,'Username: 3-50 lowercase letters, numbers, dot, dash or underscore')
    if username == OWNER_USERNAME:
        err(403, 'The ultra administrator username is reserved')
    name = validated_text(d,'full_name',max_len=100)
    role = str(d.get('role',''))
    if role not in ROLES:
        err(422,'Select a valid role')
    branch = user_branch_from_request(role, d.get('branch'))
    password = str(d.get('password',''))
    if not 8<=len(password)<=128:
        err(422,'New account password must contain 8 to 128 characters')
    try:
        with db() as c:
            new_id = c.execute('''INSERT INTO users(username,password_hash,full_name,role,branch,created_at,must_change_password)
                                  VALUES (?,?,?,?,?,?,1)''', (username,pw_hash(password),name,role,branch,now())).lastrowid
            audit(c,u['id'],'USER_CREATED',{'id':new_id,'username':username,'role':role,'branch':branch})
            return {'ok':True,'id':new_id}
    except sqlite3.IntegrityError:
        err(409,'Username already exists')


@app.patch('/api/users/{user_id}')
async def edit_user(user_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u,'users')
    d = await request.json()
    with db() as c:
        target = c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        if not target:
            err(404,'User not found')
        if target['username'] == OWNER_USERNAME:
            err(403, 'The ultra administrator account cannot be modified here')
        if user_id == u['id']:
            err(409,'You cannot change your own role or disable your own account')
        role = str(d.get('role', target['role']))
        if role not in ROLES:
            err(422,'Invalid role')
        branch = user_branch_from_request(role, d.get('branch', target['branch']))
        active = 1 if d.get('is_active',bool(target['is_active'])) else 0
        if target['role']=='admin' and (role!='admin' or not active):
            active_admins = c.execute("SELECT COUNT(*) n FROM users WHERE role='admin' AND is_active=1").fetchone()['n']
            if active_admins<=1:
                err(409,'You cannot remove the last active administrator')
        c.execute('UPDATE users SET role=?,branch=?,is_active=? WHERE id=?',(role,branch,active,user_id))
        if role != target['role'] or branch != target['branch'] or not active:
            c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(c,u['id'],'USER_UPDATED',{'id':user_id,'role':role,'branch':branch,'active':bool(active), 'before': {'role':target['role'],'branch':target['branch'],'is_active':target['is_active']}, 'after':{'role':role,'branch':branch,'is_active':active}})
    return {'ok':True}


@app.post('/api/users/{user_id}/reset-password')
async def reset_user_password(user_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u,'users')
    d = await request.json()
    password = str(d.get('password',''))
    if not 8<=len(password)<=128:
        err(422,'Temporary password must contain 8 to 128 characters')
    with db() as c:
        target = c.execute('SELECT username FROM users WHERE id=?',(user_id,)).fetchone()
        if not target:
            err(404,'User not found')
        if target['username'] == OWNER_USERNAME:
            err(403, 'The ultra administrator password cannot be reset here')
        c.execute('UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?',(pw_hash(password),user_id))
        c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(c,u['id'],'PASSWORD_RESET',{'user_id':user_id})
    return {'ok':True}


@app.get('/api/audit-page')
def audit_history_page(request: Request, limit: int = 20, offset: int = 0):
    u = get_user(request)
    if u['role'] != 'admin':
        err(403, 'Only administrators can view audit logs')
    limit = max(1, min(100, limit)); offset = max(0, offset)
    with db(readonly=True) as c:
        total = c.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
        rows = [dict(x) for x in c.execute('''SELECT a.id,a.action,a.detail,a.created_at,u.username
                         FROM audit_log a LEFT JOIN users u ON a.user_id=u.id
                         ORDER BY a.id DESC LIMIT ? OFFSET ?''',(limit,offset))]
        # Recovery events must span pages so Undo/Redo status is never guessed from the visible page alone.
        recovery_events = [dict(x) for x in c.execute('''SELECT id,action,detail FROM audit_log
                   WHERE action IN ('MOVEMENT_UNDO','MOVEMENT_REDO','AUDIT_EDIT_UNDO','AUDIT_EDIT_REDO') ORDER BY id DESC''')]
        return {'total':total,'rows':rows,'recovery_events':recovery_events,'limit':limit,'offset':offset}


@app.get('/api/audit')
def audit_history(request: Request):
    u = get_user(request)
    if u['role'] != 'admin':
        err(403,'Only administrators can view audit logs')
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT a.id,a.action,a.detail,a.created_at,u.username
                                             FROM audit_log a LEFT JOIN users u ON a.user_id=u.id ORDER BY a.id DESC LIMIT 300''')]


def produce_sqlite_snapshot(target: Path):
    # SQLite online backup gives a transactionally consistent snapshot, even with WAL.
    with DB_LOCK:
        source = connection()
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
            dest.execute('DELETE FROM sessions')
            dest.commit()
        finally:
            dest.close()
            source.close()


@app.get('/api/backup/export')
def export_database(request: Request):
    u = get_user(request)
    permit(u,'backup')
    with tempfile.TemporaryDirectory() as tmp:
        sql = Path(tmp)/'warehouse.sqlite3'
        produce_sqlite_snapshot(sql)
        payload = sql.read_bytes()
        manifest = {'application':'Hospital Warehouse IMS','schema_version':SCHEMA_VERSION,
                    'created_utc':now(),'database_file':'warehouse.sqlite3',
                    'sha256':hashlib.sha256(payload).hexdigest()}
        signature = local_backup_signature(manifest)
        if signature:
            manifest['local_signature'] = signature
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('manifest.json',json.dumps(manifest,indent=2))
            z.writestr('warehouse.sqlite3',payload)
        buffer.seek(0)
    filename = f'warehouse_backup_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
    return StreamingResponse(buffer,media_type='application/zip',headers={
        'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})


@app.post('/api/backup/restore')
async def restore_database(request: Request, backup: UploadFile=File(...)):
    u = get_user(request,require_csrf=True)
    permit(u,'backup')
    if request.headers.get('x-restore-confirmation') != 'RESTORE':
        err(422,'Type RESTORE to confirm replacement of the database')
    content = await backup.read(55*1024*1024+1)
    return restore_backup_bytes(content, u)


def restore_backup_bytes(content, u, *, cloud_file_id=None):
    if len(content)>55*1024*1024:
        err(413,'Backup is larger than the 55 MB limit')
    with tempfile.TemporaryDirectory() as tmp:
        incoming = Path(tmp)/'incoming.sqlite3'
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                files = set(z.namelist())
                if files != {'manifest.json','warehouse.sqlite3'}:
                    err(422,'Unknown backup structure')
                info = z.getinfo('warehouse.sqlite3')
                if info.file_size > 220*1024*1024:
                    err(413,'Uncompressed backup is too large')
                manifest = json.loads(z.read('manifest.json'))
                if manifest.get('application')!='Hospital Warehouse IMS' or manifest.get('schema_version') not in range(1, SCHEMA_VERSION+1):
                    err(422,'Not a compatible warehouse backup')
                data = z.read('warehouse.sqlite3')
                if hashlib.sha256(data).hexdigest()!=manifest.get('sha256'):
                    err(422,'Backup integrity check failed')
                if not is_ultra_admin(u):
                    expected = local_backup_signature(manifest)
                    if not expected or not hmac.compare_digest(str(manifest.get('local_signature','')), expected):
                        err(403, 'Only the ultra administrator can restore an unsigned or older backup')
                incoming.write_bytes(data)
        except (zipfile.BadZipFile, ValueError, KeyError, OSError):
            err(422,'Cannot read this backup file')
        verify = sqlite3.connect(incoming)
        try:
            if verify.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                err(422,'Backup failed SQLite integrity check')
            verify.execute('PRAGMA foreign_keys=ON')
            if verify.execute('PRAGMA foreign_key_check').fetchone():
                err(422,'Backup has broken database relationships')
            required = {'users','sessions','items','batches','departments','movements','movement_lines','audit_log','app_meta'}
            tables = {r[0] for r in verify.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables):
                err(422,'Backup is missing required database tables')
            n_admin = verify.execute("SELECT count(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
            if n_admin < 1:
                err(422,'Backup has no active admin account')
            if PUBLIC_DEPLOY:
                admin = verify.execute('SELECT password_hash FROM users WHERE username=?', ('enki',)).fetchone()
                if admin and pw_check('123', admin[0]):
                    err(422, 'This older backup contains the insecure local admin password and cannot be restored to a public server. Change it before exporting.')
            version = manifest['schema_version']
            if version == 1:
                migrate_item_details(verify)
            if version <= 2:
                migrate_branches(verify)
            if version >= 3:
                actual_columns = {row[1] for row in verify.execute('PRAGMA table_info(items)')}
                if not {'generic_name','manufacturer','manufacture_date','expiry_date','information','branch'}.issubset(actual_columns):
                    err(422, 'Backup declares V3+ but is missing item/branch fields')
            if version < 4:
                migrate_item_form(verify)
            else:
                actual_columns = {row[1] for row in verify.execute('PRAGMA table_info(items)')}
                if not {'trade_name','initial_batch_no'}.issubset(actual_columns):
                    err(422, 'Backup declares V4 but is missing registered item fields')
            if version < 5:
                migrate_outgoing_and_price(verify)
            else:
                item_cols = {r[1] for r in verify.execute('PRAGMA table_info(items)')}
                move_cols = {r[1] for r in verify.execute('PRAGMA table_info(movements)')}
                if 'price_fils' not in item_cols or 'unit_price_fils' not in {r[1] for r in verify.execute('PRAGMA table_info(movement_lines)')} or not {'destination_type','external_destination','dispatch_ref'}.issubset(move_cols):
                    err(422, 'Backup declares V5 but is missing price/transfer fields')
            if version < 6:
                migrate_shipment_routes(verify)
            else:
                columns = {r[1] for r in verify.execute('PRAGMA table_info(movements)')}
                required_v6 = {'route','trusted_pharmacist_id','paperwork_pending',
                               'paperwork_completed_at','paperwork_completed_by'}
                if not required_v6.issubset(columns):
                    err(422, 'Backup declares V6 but is missing shipment route and paperwork fields')
            if version < 7:
                migrate_per_receipt_pricing_and_transfer_authorization(verify)
            else:
                batch_cols = {r[1] for r in verify.execute('PRAGMA table_info(batches)')}
                movement_cols = {r[1] for r in verify.execute('PRAGMA table_info(movements)')}
                if 'unit_price_fils' not in batch_cols or not {'trusted_pharmacist_name','authorization_ref'}.issubset(movement_cols):
                    err(422, 'Backup declares V7 but is missing priced lots or transfer authorization')
            if version < 8:
                migrate_annual_need(verify)
            else:
                if 'annual_need' not in {r[1] for r in verify.execute('PRAGMA table_info(items)')}:
                    err(422, 'Backup declares V8 but is missing annual requirement field')
            if version < 9:
                migrate_v9(verify)
            else:
                if 'manufacture_date' not in {r[1] for r in verify.execute('PRAGMA table_info(batches)')} or not {'email','phone','age','job_title'}.issubset({r[1] for r in verify.execute('PRAGMA table_info(users)')}):
                    err(422, 'Backup declares V9 but is missing lot manufacturing or profile columns')
            if version < 10:
                migrate_recovery_v10(verify)
            else:
                tables_v10 = {r[0] for r in verify.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {'movement_reversals','audit_field_reversals'}.issubset(tables_v10):
                    err(422, 'Backup declares V10 but is missing recovery tables')
            seed_default_departments(verify)  # Older backups gain starter departments without deleting user records.
            verify.commit()
        except sqlite3.DatabaseError:
            err(422,'Invalid SQLite backup contents')
        finally:
            verify.close()
        with DB_LOCK:
            # Preserve the configured owner identity and credentials on staff restores.
            with db(readonly=True) as current:
                owner = current.execute("SELECT * FROM users WHERE username=? AND role='admin' AND is_active=1", (OWNER_USERNAME,)).fetchone()
            if not owner:
                err(409, 'The configured ultra administrator account is unavailable')
            with contextlib.closing(sqlite3.connect(incoming)) as candidate, candidate:
                restored_owner = candidate.execute('SELECT id,role,is_active FROM users WHERE username=?', (OWNER_USERNAME,)).fetchone()
                if not restored_owner or restored_owner[0] != owner['id'] or restored_owner[1] != 'admin' or not restored_owner[2]:
                    err(422, 'Backup does not contain the matching active ultra administrator')
                candidate.execute('UPDATE users SET password_hash=?,must_change_password=? WHERE id=?',(owner['password_hash'],owner['must_change_password'],owner['id']))
            # Consistent pre-restore safety copy on the existing volume.
            safety = BACKUPS / f'before_restore_{dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.sqlite3'
            produce_sqlite_snapshot(safety)
            src = sqlite3.connect(incoming)
            dst = connection()
            try:
                src.backup(dst)
                dst.execute('DELETE FROM sessions')
                dst.commit()
                check = dst.execute('PRAGMA integrity_check').fetchone()[0]
                if check!='ok':
                    raise RuntimeError('Restore integrity failed')
                audit(dst,None,'BACKUP_RESTORED',{'restored_by':u['username'],'safety_copy':safety.name,'source':'google_drive' if cloud_file_id else 'local_zip','cloud_file_id':cloud_file_id})
                dst.commit()
            except Exception:
                # Recover from the safety copy if replacing fails.
                dst.close()
                with sqlite3.connect(safety) as rollback, connection() as recover:
                    rollback.backup(recover)
                raise
            finally:
                src.close()
                with contextlib.suppress(Exception):
                    dst.close()
    response = JSONResponse({'ok':True,'message':'Restore complete. All staff sessions were closed. Sign in again.'})
    response.delete_cookie('wh_session',path='/')
    return response



# V4.22 — off-site Google Drive backup, restricted to the configured owner.
# Automatic runs are triggered by a second Railway Cron service; no in-browser
# timer and no insecure account password or credentials inside the repository.

def gdrive_error(exc):
    if isinstance(exc, gdrive.CloudBackupError):
        err(409, str(exc))
    raise exc


@app.get('/api/gdrive/status')
def gdrive_status(request: Request):
    u=get_user(request)
    permit_cloud(u)
    try:
        return gdrive.status(DATA)
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)


@app.post('/api/gdrive/connect')
def gdrive_connect(request: Request):
    u=get_user(request, require_csrf=True)
    permit_cloud(u)
    try:
        return {'url':gdrive.oauth_url(DATA, u['id'])}
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)


@app.get('/api/gdrive/callback')
def gdrive_callback(request: Request, code: str='', state: str='', error: str=''):
    try:
        u=get_user(request)
        permit_cloud(u)
        if error or not code or not state:
            raise gdrive.CloudBackupError('Google OAuth was cancelled or incomplete')
        gdrive.exchange_code(DATA, state, code, u['id'])
        with db() as c:
            audit(c,u['id'],'GOOGLE_DRIVE_CONNECTED',{'scope':'drive.file'})
        return RedirectResponse('/dashboard.html?gdrive=connected#backup',status_code=303)
    except (HTTPException, gdrive.CloudBackupError):
        return RedirectResponse('/dashboard.html?gdrive=error#backup',status_code=303)


@app.post('/api/gdrive/disconnect')
async def gdrive_disconnect(request: Request):
    u=get_user(request,require_csrf=True)
    permit_cloud(u)
    data=await request.json()
    if data.get('confirmation')!='DISCONNECT':
        err(422,'Type DISCONNECT to revoke the connected account')
    try:
        gdrive.disconnect(DATA)
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)
    with db() as c:
        audit(c,u['id'],'GOOGLE_DRIVE_DISCONNECTED',{})
    return {'ok':True}


def perform_cloud_backup(kind, user_id=None):
    try:
        result=gdrive.run_backup(DATA,produce_sqlite_snapshot,SCHEMA_VERSION,kind=kind)
    except gdrive.CloudBackupError as exc:
        with db() as c:
            audit(c,user_id,'GOOGLE_DRIVE_BACKUP_FAILED',{'kind':kind,'error':str(exc)[:180]})
        gdrive_error(exc)
    if result.get('already_done'):
        return result
    with db() as c:
        audit(c,user_id,'GOOGLE_DRIVE_BACKUP_COMPLETED',{'kind':kind,'file_name':result['name'],'slot':result.get('slot')})
    return result


@app.post('/api/gdrive/backup-now')
def gdrive_backup_now(request: Request):
    u=get_user(request,require_csrf=True)
    permit_cloud(u)
    return perform_cloud_backup('manual',u['id'])


@app.post('/api/gdrive/scheduled-run')
def gdrive_scheduled_run(request: Request):
    secret=os.getenv('WAREHOUSE_BACKUP_CRON_SECRET','')
    presented=request.headers.get('x-warehouse-cron-secret','')
    if len(secret)<32 or not hmac.compare_digest(presented,secret):
        err(403,'Scheduled backup authorization failed')
    return perform_cloud_backup('scheduled',None)


@app.get('/api/gdrive/files')
def gdrive_files(request: Request):
    u=get_user(request)
    permit_cloud(u)
    try:
        return gdrive.list_remote_backups(DATA)
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)


@app.get('/api/gdrive/download/{file_id}')
def gdrive_backup_download(file_id: str, request: Request):
    u=get_user(request)
    permit_cloud(u)
    try:
        content,name=gdrive.download_file(DATA,file_id)
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)
    safe_name=re.sub(r'[^A-Za-z0-9_.-]','_',name)
    return StreamingResponse(io.BytesIO(content),media_type='application/zip',headers={
        'Content-Disposition':f'attachment; filename="{safe_name}"',
        'Cache-Control':'no-store'})


@app.post('/api/gdrive/restore/{file_id}')
async def gdrive_restore(file_id: str, request: Request):
    u = get_user(request, require_csrf=True)
    permit_cloud(u)
    payload = await request.json()
    if payload.get('confirmation') != 'RESTORE':
        err(422, 'Type RESTORE to confirm replacement of the database')
    login_throttle(u['username'])
    with db(readonly=True) as c:
        record = c.execute('SELECT password_hash FROM users WHERE id=?',(u['id'],)).fetchone()
    if not record or not pw_check(str(payload.get('password','')),record['password_hash']):
        login_failed(u['username'])
        err(403, 'Incorrect administrator password')
    login_success(u['username'])
    # Download and authenticate the encrypted file on the server, never in the browser.
    from starlette.concurrency import run_in_threadpool
    try:
        content, _ = await run_in_threadpool(gdrive.download_file, DATA, file_id)
    except gdrive.CloudBackupError as exc:
        gdrive_error(exc)
    # Recheck the session after the network request, before replacing data.
    u = get_user(request, require_csrf=True)
    permit_cloud(u)
    return restore_backup_bytes(content, u, cloud_file_id=file_id)


# V4.25 recovery endpoints: stock reversals are NEW movements and NEW audit
# records. Original movements and audit events are immutable.

def recovery_auth(c, user, data, action, *, owner=False):
    if owner:
        if not is_ultra_admin(user):
            err(403, 'Only the ultra administrator may perform this recovery')
    elif user['role'] != 'admin':
        err(403, 'Only administrators may undo recorded movements')
    if data.get('confirmation') != action:
        err(422, f'Type {action} to confirm the correction')
    reason = validated_text(data, 'reason', max_len=500)
    if len(reason) < 8:
        err(422, 'Explain the correction in at least 8 characters')
    password = str(data.get('password') or '')
    credentials = c.execute('SELECT password_hash FROM users WHERE id=? AND is_active=1', (user['id'],)).fetchone()
    if not credentials or not pw_check(password, credentials['password_hash']):
        err(403, 'Incorrect administrator password')
    return reason


def recovery_eligible_line(c, line_id):
    return c.execute('''SELECT l.*, m.id movement_id,m.code original_code,m.kind original_kind,m.route original_route,
                 b.on_hand,b.expiry_date,b.batch_no,i.name item_name,i.category book_category,i.branch
                 FROM movement_lines l JOIN movements m ON m.id=l.movement_id
                 JOIN batches b ON b.id=l.batch_id JOIN items i ON i.id=b.item_id WHERE l.id=?''', (line_id,)).fetchone()


def recovery_undo(c, user, movement_id, line_ids, reason, *, audit_source=None):
    original = c.execute('SELECT * FROM movements WHERE id=?', (movement_id,)).fetchone()
    if not original:
        err(404, 'Original movement not found')
    if original['route'] in ('recovery_undo','recovery_redo'):
        err(409, 'Recovery movements cannot be directly undone; use the linked Redo instead')
    available = c.execute('SELECT id FROM movement_lines WHERE movement_id=? ORDER BY id', (movement_id,)).fetchall()
    all_ids = [r['id'] for r in available]
    if not all_ids:
        err(409, 'No lines to undo')
    if line_ids is None:
        selected = all_ids
    elif isinstance(line_ids,list) and line_ids and all(type(x) is int for x in line_ids) and len(set(line_ids)) == len(line_ids) and set(line_ids).issubset(all_ids):
        selected = line_ids
    else:
        err(422, 'Choose one or more valid, nonduplicate shipment line IDs')
    original_lines = []
    for line_id in selected:
        line = recovery_eligible_line(c,line_id)
        active = c.execute('SELECT id FROM movement_reversals WHERE original_line_id=? AND redo_line_id IS NULL', (line_id,)).fetchone()
        if active:
            err(409, f'Line {line_id} already has an active Undo')
        if line['direction'] > 0:
            # An incoming/opening lot with later active issues has a dependent
            # movement. Removing that original receipt would falsify provenance,
            # even if subsequent receipts make the current balance sufficient.
            dependent=c.execute('''SELECT 1 FROM movement_lines newer
                 JOIN movements nm ON nm.id=newer.movement_id
                 LEFT JOIN movement_reversals active_reverse
                    ON active_reverse.original_line_id=newer.id AND active_reverse.redo_line_id IS NULL
                 WHERE newer.batch_id=? AND newer.id>? AND newer.direction=-1
                   AND nm.route NOT IN ('recovery_undo','recovery_redo')
                   AND active_reverse.id IS NULL LIMIT 1''',(line['batch_id'],line['id'])).fetchone()
            if dependent:
                err(409,'Later stock issues depend on this incoming/opening lot. Undo those dependent issues first, or record an approved stock adjustment.')
        if (('المخدرات' in (line['book_category'] or '')) or ('المؤثرات العقلية' in (line['book_category'] or ''))) and not is_ultra_admin(user):
            err(403, 'Controlled-medication corrections require ultra-administrator authorization')
        original_lines.append(line)
    changes = {}
    for line in original_lines:
        changes[line['batch_id']] = changes.get(line['batch_id'],0) - line['qty']*line['direction']
    for bid,delta in changes.items():
        if delta < 0:
            r = c.execute('SELECT on_hand FROM batches WHERE id=?',(bid,)).fetchone()
            if not r or r['on_hand'] < -delta:
                err(409,'Undo would result in negative stock. Later transactions have used this inventory; reconcile the physical balance first.')
    inverse_direction = -original_lines[0]['direction']
    if any(-l['direction'] != inverse_direction for l in original_lines):
        err(409, 'Cannot mix positive and negative movements in one Undo')
    correction_kind = 'ADJUST_PLUS' if inverse_direction==1 else 'ADJUST_MINUS'
    created = c.execute('''INSERT INTO movements(code,kind,paper_ref,source,notes,route,created_by,created_at)
              VALUES(?,?,?,?,?,?,?,?)''', ('TEMP-'+secrets.token_hex(7), correction_kind,
              ('UNDO-'+original['code'])[:80], 'Controlled reversal',
              'Undo of '+original['code']+' | '+reason,'recovery_undo',user['id'],now()))
    undo_mid=created.lastrowid
    code=f'UNDO-{undo_mid:06d}'
    c.execute('UPDATE movements SET code=? WHERE id=?',(code,undo_mid))
    output=[]
    for line in original_lines:
        delta=-line['direction']*line['qty']
        if delta<0:
            r=c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=? AND on_hand>=?',(delta,line['batch_id'],-delta))
            if r.rowcount!=1:
                err(409,'Stock changed while reversing the shipment')
        else:
            c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=?',(delta,line['batch_id']))
        undo_line=c.execute('''INSERT INTO movement_lines(movement_id,batch_id,qty,direction,unit_price_fils)
                             VALUES (?,?,?,?,?)''',(undo_mid,line['batch_id'],line['qty'],-line['direction'],line['unit_price_fils'])).lastrowid
        c.execute('''INSERT INTO movement_reversals(original_line_id,undo_line_id,undone_by,undone_at,undo_reason)
                     VALUES (?,?,?,?,?)''',(line['id'],undo_line,user['id'],now(),reason))
        output.append({'original_line_id':line['id'],'undo_line_id':undo_line,'batch_id':line['batch_id'],'qty':line['qty']})
    audit(c,user['id'],'MOVEMENT_UNDO',{'movement_id':movement_id,'original_code':original['code'],
          'undo_movement_id':undo_mid,'undo_code':code,'line_ids':selected,'reason':reason,
          'source_audit_id':audit_source,'lines':output})
    return {'ok':True,'undo_movement_id':undo_mid,'undo_code':code,'line_ids':selected}


def recovery_redo(c,user,undo_mid,reason):
    movement=c.execute('SELECT * FROM movements WHERE id=?',(undo_mid,)).fetchone()
    if not movement or movement['route']!='recovery_undo':
        err(404,'Original Undo movement was not found')
    reverse=c.execute('''SELECT r.*, l.batch_id,l.qty,l.direction,l.unit_price_fils,l.movement_id original_movement_id,
                                 m.kind original_kind,b.expiry_date,b.on_hand,i.category book_category
                          FROM movement_reversals r JOIN movement_lines l ON l.id=r.original_line_id
                          JOIN movements m ON m.id=l.movement_id JOIN batches b ON b.id=l.batch_id
                          JOIN items i ON i.id=b.item_id
                          JOIN movement_lines undo_line ON undo_line.id=r.undo_line_id
                          WHERE undo_line.movement_id=? ORDER BY r.id''',(undo_mid,)).fetchall()
    if not reverse or any(r['redo_line_id'] is not None for r in reverse):
        err(409,'This Undo is already redone or is incomplete')
    today=dt.datetime.now(ZoneInfo('Asia/Baghdad')).date().isoformat()
    change={}
    for r in reverse:
        if r['original_kind']=='OUT' and r['expiry_date'] and r['expiry_date']<today:
            err(409,'Cannot redo an outgoing issue of a now-expired lot')
        change[r['batch_id']]=change.get(r['batch_id'],0)+r['qty']*r['direction']
    for bid,delta in change.items():
        if delta<0:
            row=c.execute('SELECT on_hand FROM batches WHERE id=?',(bid,)).fetchone()
            if not row or row['on_hand'] < -delta:
                err(409,'Redo would make a stock balance negative; reconcile the batch first')
    directions={r['direction'] for r in reverse}
    if len(directions)!=1:err(409,'Mixed-direction correction requires manual review')
    kind='ADJUST_PLUS' if next(iter(directions))==1 else 'ADJUST_MINUS'
    rec=c.execute('''INSERT INTO movements(code,kind,paper_ref,source,notes,route,created_by,created_at)
                   VALUES(?,?,?,?,?,?,?,?)''',('TEMP-'+secrets.token_hex(7),kind,('REDO-'+movement['code'])[:80],
                      'Controlled reapplication','Redo of '+movement['code']+' | '+reason,'recovery_redo',user['id'],now()))
    mid=rec.lastrowid;code=f'REDO-{mid:06d}'
    c.execute('UPDATE movements SET code=? WHERE id=?',(code,mid))
    for r in reverse:
        delta=r['qty']*r['direction']
        if delta<0:
            updated=c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=? AND on_hand>=?',(delta,r['batch_id'],-delta))
            if updated.rowcount!=1:err(409,'Insufficient batch stock for Redo')
        else:
            c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=?',(delta,r['batch_id']))
        new_line=c.execute('''INSERT INTO movement_lines(movement_id,batch_id,qty,direction,unit_price_fils)
                VALUES(?,?,?,?,?)''',(mid,r['batch_id'],r['qty'],r['direction'],r['unit_price_fils'])).lastrowid
        c.execute('''UPDATE movement_reversals SET redo_line_id=?,redone_by=?,redone_at=?,redo_reason=? WHERE id=?''',
                  (new_line,user['id'],now(),reason,r['id']))
    audit(c,user['id'],'MOVEMENT_REDO',{'undo_movement_id':undo_mid,'undo_code':movement['code'],
          'redo_movement_id':mid,'redo_code':code,'reason':reason,'original_line_ids':[r['original_line_id'] for r in reverse]})
    return {'ok':True,'redo_movement_id':mid,'redo_code':code}


@app.get('/api/recovery/movement/{movement_id}')
def recovery_movement_status(movement_id:int,request:Request):
    u=get_user(request)
    if u['role']!='admin':err(403,'Administrator access required')
    with db(readonly=True) as c:
        movement=c.execute('SELECT id,code,kind,route FROM movements WHERE id=?',(movement_id,)).fetchone()
        if not movement:err(404,'Movement not found')
        lines=[]
        for row in c.execute('''SELECT l.id,l.qty,l.direction,b.batch_no,b.expiry_date,b.on_hand,i.name item_name,
                        i.unit,i.category book_category,
                        (SELECT COUNT(*) FROM movement_reversals r WHERE r.original_line_id=l.id AND r.redo_line_id IS NULL) active_undo
                        FROM movement_lines l JOIN batches b ON b.id=l.batch_id
                        JOIN items i ON i.id=b.item_id WHERE l.movement_id=? ORDER BY l.id''',(movement_id,)):
            details=dict(row);details['eligible']=not bool(details['active_undo']) and movement['route'] not in ('recovery_undo','recovery_redo')
            if ('المخدرات' in (details['book_category'] or '') or 'المؤثرات العقلية' in (details['book_category'] or '')) and not is_ultra_admin(u):
                details['eligible']=False
            lines.append(details)
        return {'movement':dict(movement),'lines':lines,'is_ultra_admin':is_ultra_admin(u)}


@app.post('/api/recovery/undo')
async def undo_movement(request:Request):
    u=get_user(request,require_csrf=True)
    data=await request.json()
    with db() as c:
        reason=recovery_auth(c,u,data,'UNDO')
        mid=integer(data,'movement_id',1)
        return recovery_undo(c,u,mid,data.get('line_ids'),reason)


@app.post('/api/recovery/redo')
async def redo_movement(request:Request):
    u=get_user(request,require_csrf=True)
    data=await request.json()
    with db() as c:
        reason=recovery_auth(c,u,data,'REDO',owner=True)
        mid=integer(data,'undo_movement_id',1)
        return recovery_redo(c,u,mid,reason)


RECOVER_EDIT_FIELDS={
    'ITEM_UPDATED':('items',('sku','name','category','branch','unit','generic_name','trade_name','initial_batch_no',
                           'manufacturer','manufacture_date','expiry_date','information','price_fils','annual_need','active')),
    'DEPARTMENT_UPDATED':('departments',('name','active')),
    'USER_UPDATED':('users',('role','branch','is_active')),
}


def audit_edit_reapply(c,user,original_audit_id,*,redo,reason):
    source=c.execute('SELECT * FROM audit_log WHERE id=?',(original_audit_id,)).fetchone()
    if not source or source['action'] not in RECOVER_EDIT_FIELDS:
        err(409,'This audit event is not eligible for field-level recovery')
    detail=json.loads(source['detail'])
    before,after=detail.get('before'),detail.get('after')
    if not isinstance(before,dict) or not isinstance(after,dict):
        err(409,'Older audit records have no trustworthy before/after snapshot; cannot reverse')
    table,keys=RECOVER_EDIT_FIELDS[source['action']]
    if any(k not in before or k not in after for k in keys):
        err(409,'Audit snapshots are incomplete')
    oid=int(detail['id'])
    tracked=c.execute('SELECT * FROM audit_field_reversals WHERE original_audit_id=?',(original_audit_id,)).fetchone()
    if redo:
        if not tracked or tracked['redo_audit_id'] is not None:err(409,'No active audit edit Undo to redo')
        expected,values=before,after
    else:
        if tracked:err(409,'This audit edit has already been undone; check its recovery events')
        expected,values=after,before
    row=c.execute(f'SELECT * FROM {table} WHERE id=?',(oid,)).fetchone()
    if not row:err(409,'The target record no longer exists')
    if any(row[k]!=expected[k] for k in keys):
        err(409,'The record has changed since this audit event; automatic recovery would overwrite newer edits')
    if table=='users':
        if row['username'].lower()==OWNER_USERNAME:err(403,'The installation owner cannot be changed through audit recovery')
        if row['role']=='admin' and (values['role']!='admin' or not values['is_active']):
            count=c.execute("SELECT COUNT(*) n FROM users WHERE role='admin' AND is_active=1").fetchone()['n']
            if count<=1:err(409,'Cannot remove the last active administrator')
        # Every branch or role change invalidates current sessions.
        c.execute('DELETE FROM sessions WHERE user_id=?',(oid,))
    if table=='items' and (values['branch']!=row['branch'] or values['unit']!=row['unit']):
        dependent=c.execute('SELECT 1 FROM movement_lines ml JOIN batches b ON b.id=ml.batch_id WHERE b.item_id=? LIMIT 1',(oid,)).fetchone()
        if dependent:err(409,'Cannot change branch or unit of an item with recorded movements')
    set_clause=','.join(k+'=?' for k in keys)
    try:
        c.execute(f'UPDATE {table} SET {set_clause} WHERE id=?', tuple(values[k] for k in keys)+(oid,))
    except sqlite3.IntegrityError:
        err(409,'Recovery conflicts with existing record constraints or names')
    new_event='AUDIT_EDIT_REDO' if redo else 'AUDIT_EDIT_UNDO'
    audit(c,user['id'],new_event,{'source_audit_id':original_audit_id,'source_action':source['action'],
                                 'object_type':table,'object_id':oid,'reason':reason,'before':expected,'after':values})
    event_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
    if redo:
        c.execute('UPDATE audit_field_reversals SET redo_audit_id=? WHERE id=?',(event_id,tracked['id']))
    else:
        c.execute('INSERT INTO audit_field_reversals(original_audit_id,undo_audit_id,object_type,object_id) VALUES(?,?,?,?)',
                  (original_audit_id,event_id,table,oid))
    return {'ok':True,'audit_event_id':event_id,'object_type':table,'object_id':oid}


@app.post('/api/recovery/audit/{audit_id}/undo')
async def undo_audit_event(audit_id:int,request:Request):
    u=get_user(request,require_csrf=True);data=await request.json()
    with db() as c:
        reason=recovery_auth(c,u,data,'UNDO',owner=True)
        original=c.execute('SELECT * FROM audit_log WHERE id=?',(audit_id,)).fetchone()
        if not original:err(404,'Audit event not found')
        if original['action'] in ('MOVEMENT_CREATED','OPENING_BALANCE_CREATED'):
            details=json.loads(original['detail']);movement_id=details.get('id') if original['action']=='MOVEMENT_CREATED' else details.get('movement_id')
            if not movement_id:err(409,'Audit entry has no linked shipment')
            return recovery_undo(c,u,int(movement_id),data.get('line_ids'),reason,audit_source=audit_id)
        return audit_edit_reapply(c,u,audit_id,redo=False,reason=reason)


@app.post('/api/recovery/audit/{audit_id}/redo')
async def redo_audit_edit(audit_id:int,request:Request):
    u=get_user(request,require_csrf=True);data=await request.json()
    with db() as c:
        reason=recovery_auth(c,u,data,'REDO',owner=True)
        return audit_edit_reapply(c,u,audit_id,redo=True,reason=reason)



@app.get('/api/health')
def health():
    return {'ok':True,'database':'sqlite','version':SCHEMA_VERSION,'release':APP_RELEASE}


@app.exception_handler(sqlite3.OperationalError)
async def database_error(_,exc):
    return JSONResponse(status_code=503,content={'detail':'Database is temporarily unavailable'})
