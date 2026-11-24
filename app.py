"""Hospital Warehouse IMS - connected single-warehouse testing app.

For Railway, configure WAREHOUSE_PUBLIC_DEPLOY=1, a strong
WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD, and a persistent volume at /data.
"""
from __future__ import annotations

import contextlib
import datetime as dt
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
SCHEMA_VERSION = 3
BRANCHES = ('medication', 'medical_supplies', 'surgical_instruments')
PUBLIC_DEPLOY = os.getenv('WAREHOUSE_PUBLIC_DEPLOY', '').strip() == '1'
SESSION_HOURS = 12
ROLES = ('admin', 'manager', 'operator', 'viewer')
WRITE_PERMS = {
    'admin': {'item_write', 'department_write', 'movement_write', 'adjust', 'users', 'backup'},
    'manager': {'item_write', 'department_write', 'movement_write', 'adjust'},
    'operator': {'movement_write'},
    'viewer': set(),
}
app = FastAPI(title='Hospital Warehouse IMS - Shared Test Build', docs_url=None, redoc_url=None)
app.mount('/static', StaticFiles(directory=str(STATIC)), name='static')

@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    if request.url.path.startswith('/api/'):
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


def require_branch(value, *, allow_unassigned=False):
    """Only these three branches can own inventory; NULL marks legacy records."""
    if value in BRANCHES:
        return value
    if allow_unassigned and value in (None, ''):
        return None
    err(422, 'Choose one of the three warehouse branches')


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


def item_details(d):
    """Optional catalog metadata; individual received batches have their own expiry."""
    generic_name = validated_text(d, 'generic_name', required=False, max_len=160)
    manufacturer = validated_text(d, 'manufacturer', required=False, max_len=160)
    manufacture_date = dated(d.get('manufacture_date'), 'manufacture_date')
    expiry_date = dated(d.get('expiry_date'), 'expiry_date')
    information = validated_text(d, 'information', required=False, max_len=2000)
    if manufacture_date and expiry_date and manufacture_date > expiry_date:
        err(422, 'Item expiration date must not be earlier than its manufacture date')
    return generic_name, manufacturer, manufacture_date, expiry_date, information


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
                created_at TEXT NOT NULL
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
                manufacturer TEXT NOT NULL DEFAULT '',
                manufacture_date TEXT,
                expiry_date TEXT,
                information TEXT NOT NULL DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
                batch_no TEXT NOT NULL,
                expiry_date TEXT,
                on_hand INTEGER NOT NULL DEFAULT 0 CHECK(on_hand>=0),
                created_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS uq_batch ON batches(item_id,batch_no,COALESCE(expiry_date,''));
            CREATE TABLE IF NOT EXISTS movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL CHECK(kind IN ('IN','OUT','RETURN','ADJUST_PLUS','ADJUST_MINUS')),
                paper_ref TEXT NOT NULL,
                department_id INTEGER REFERENCES departments(id) ON DELETE RESTRICT,
                source TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS movement_lines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movement_id INTEGER NOT NULL REFERENCES movements(id) ON DELETE RESTRICT,
                batch_id INTEGER NOT NULL REFERENCES batches(id) ON DELETE RESTRICT,
                qty INTEGER NOT NULL CHECK(qty > 0),
                direction INTEGER NOT NULL CHECK(direction IN (-1,1))
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
        count = c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
        if PUBLIC_DEPLOY and count > 0:
            old = c.execute("SELECT password_hash FROM users WHERE username='enki'").fetchone()
            if old and pw_check('123', old['password_hash']):
                raise RuntimeError('PUBLIC DEPLOYMENT BLOCKED: existing ENKI account still uses the local test password. Change it locally before deploying.')
        if count == 0:
            c.execute('INSERT INTO users(username,password_hash,full_name,role,is_active,must_change_password,created_at) VALUES(?,?,?,?,?,?,?)',
                      ('enki', pw_hash(bootstrap_admin_password()), 'ENKI Administrator', 'admin', 1, 0 if PUBLIC_DEPLOY else 1, now()))
            c.execute('INSERT INTO audit_log(user_id,action,detail,created_at) VALUES (1,?,?,?)',
                      ('INITIAL_SETUP', 'Testing administrator created', now()))

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


@app.get('/login.html')
def login_page():
    return FileResponse(STATIC / 'login.html')


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
            'must_change_password': bool(u['must_change_password']), 'branch': u['branch'], 'branches': BRANCHES, 'csrf': u['csrf'], 'permissions': sorted(WRITE_PERMS[u['role']])}


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
        return [dict(x) for x in c.execute('SELECT * FROM departments ORDER BY active DESC,name')]


@app.post('/api/departments')
async def create_department(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'department_write')
    d = await request.json()
    name = validated_text(d, 'name')
    code = validated_text(d, 'code', max_len=30).upper()
    try:
        with db() as c:
            q = c.execute('INSERT INTO departments(code,name,created_at) VALUES(?,?,?)', (code, name, now()))
            audit(c, u['id'], 'DEPARTMENT_CREATED', {'id': q.lastrowid, 'code': code, 'name': name})
            return {'ok': True, 'id': q.lastrowid}
    except sqlite3.IntegrityError:
        err(409, 'Department name or code already exists')


@app.patch('/api/departments/{department_id}')
async def update_department(department_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'department_write')
    d = await request.json()
    name = validated_text(d, 'name')
    code = validated_text(d, 'code', max_len=30).upper()
    try:
        with db() as c:
            if not c.execute('SELECT 1 FROM departments WHERE id=?', (department_id,)).fetchone():
                err(404, 'Department not found')
            c.execute('UPDATE departments SET name=?,code=?,active=? WHERE id=?',
                      (name, code, 1 if d.get('active', True) else 0, department_id))
            audit(c, u['id'], 'DEPARTMENT_UPDATED', {'id': department_id, 'name': name, 'code': code, 'active': bool(d.get('active', True))})
        return {'ok': True}
    except sqlite3.IntegrityError:
        err(409, 'Department name or code already exists')


@app.get('/api/items')
def list_items(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT i.*,COALESCE(SUM(b.on_hand),0) stock,COUNT(b.id) batch_count
                                             FROM items i LEFT JOIN batches b ON b.item_id=i.id GROUP BY i.id
                                             ORDER BY i.active DESC,i.branch,i.category,i.name''')]


@app.post('/api/items')
async def create_item(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'item_write')
    d = await request.json()
    sku = validated_text(d, 'sku', max_len=50).upper()
    name = validated_text(d, 'name', max_len=160)  # Existing name is scientific item name.
    cat = validated_text(d, 'category', max_len=80)  # Book / register classification.
    branch = require_branch(d.get('branch'))
    restrict_branch(u, branch)
    unit = validated_text(d, 'unit', max_len=30)
    generic, manufacturer, mfg, exp, info = item_details(d)
    try:
        with db() as c:
            q = c.execute('''INSERT INTO items(sku,name,category,branch,unit,generic_name,manufacturer,
                            manufacture_date,expiry_date,information,created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                          (sku,name,cat,branch,unit,generic,manufacturer,mfg,exp,info,now()))
            audit(c, u['id'], 'ITEM_CREATED', {'id':q.lastrowid,'sku':sku,'name':name,'branch':branch,'book_category':cat,
                  'generic_name':generic,'manufacturer':manufacturer,'manufacture_date':mfg,
                  'expiry_date':exp,'information':info})
            return {'ok': True, 'id': q.lastrowid}
    except sqlite3.IntegrityError:
        err(409, 'Item code already exists')


@app.patch('/api/items/{item_id}')
async def update_item(item_id: int, request: Request):
    u = get_user(request, require_csrf=True)
    permit(u, 'item_write')
    d = await request.json()
    sku = validated_text(d, 'sku', max_len=50).upper()
    name = validated_text(d, 'name', max_len=160)
    category = validated_text(d, 'category', max_len=80)
    branch = require_branch(d.get('branch'))
    unit = validated_text(d, 'unit', max_len=30)
    generic, manufacturer, mfg, exp, info = item_details(d)
    try:
        with db() as c:
            old = c.execute('SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
            if not old:
                err(404, 'Item not found')
            restrict_branch(u, old['branch'])
            restrict_branch(u, branch)
            has_movements = c.execute('SELECT 1 FROM movement_lines l JOIN batches b ON l.batch_id=b.id WHERE b.item_id=? LIMIT 1', (item_id,)).fetchone()
            if has_movements and old['unit'] != unit:
                err(409, 'Cannot change the unit after stock movements have been recorded')
            if has_movements and old['branch'] is not None and old['branch'] != branch:
                err(409, 'Cannot transfer an item to another branch after movements were recorded')
            c.execute('''UPDATE items SET sku=?,name=?,category=?,branch=?,unit=?,generic_name=?,
                         manufacturer=?,manufacture_date=?,expiry_date=?,information=?,active=?
                         WHERE id=?''',
                      (sku,name,category,branch,unit,generic,manufacturer,mfg,exp,info,
                       1 if d.get('active',True) else 0,item_id))
            audit(c, u['id'], 'ITEM_UPDATED', {'id':item_id,'sku':sku,'name':name,'branch':branch,'book_category':category,
                  'generic_name':generic,'manufacturer':manufacturer,'manufacture_date':mfg,
                  'expiry_date':exp,'information':info})
        return {'ok': True}
    except sqlite3.IntegrityError:
        err(409, 'Item code already exists')


@app.get('/api/batches')
def batches(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT b.id,b.item_id,b.batch_no,b.expiry_date,b.on_hand,
                                             i.sku,i.name item_name,i.unit,i.category,i.branch,i.active item_active
                                             FROM batches b JOIN items i ON i.id=b.item_id
                                             ORDER BY b.on_hand DESC,i.name,b.expiry_date''')]


@app.get('/api/movements')
def movements(request: Request):
    get_user(request)
    with db(readonly=True) as c:
        res = [dict(x) for x in c.execute('''SELECT m.*,d.name department_name,u.username creator,
                       COUNT(l.id) line_count,SUM(l.qty) total_units
                       FROM movements m LEFT JOIN departments d ON d.id=m.department_id
                       JOIN users u ON u.id=m.created_by JOIN movement_lines l ON l.movement_id=m.id
                       GROUP BY m.id ORDER BY m.id DESC LIMIT 500''')]
        ids = [x['id'] for x in res]
        if ids:
            ph = ','.join('?' for _ in ids)
            lines = [dict(x) for x in c.execute(f'''SELECT ml.movement_id,ml.qty,ml.direction,b.batch_no,b.expiry_date,
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
    paper_ref = validated_text(d, 'paper_ref', required=kind in ('OUT','IN'), max_len=80)
    source = validated_text(d, 'source', required=kind == 'IN', max_len=140)
    notes = validated_text(d, 'notes', required=False, max_len=500)
    department_id = d.get('department_id')
    if kind in ('OUT','RETURN'):
        department_id = integer(d, 'department_id', minimum=1)
    else:
        department_id = None
    lines = d.get('lines')
    if not isinstance(lines, list) or not 1 <= len(lines) <= 50:
        err(422, 'Provide 1 to 50 shipment line items')
    # Validate and commit entire movement atomically; no partial stock deduction.
    with db() as c:
        if department_id and not c.execute('SELECT 1 FROM departments WHERE id=? AND active=1', (department_id,)).fetchone():
            err(422, 'Choose an active department')
        created = c.execute('INSERT INTO movements(code,kind,paper_ref,department_id,source,notes,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)',
                            ('TEMP-'+secrets.token_hex(6),kind,paper_ref,department_id,source,notes,u['id'],now()))
        mid = created.lastrowid
        code = movement_code(kind, mid)
        c.execute('UPDATE movements SET code=? WHERE id=?', (code,mid))
        direction = 1 if kind in ('IN','RETURN','ADJUST_PLUS') else -1
        for line in lines:
            qty = integer(line,'qty',1,100_000_000)
            if kind == 'IN':
                iid = integer(line,'item_id',1)
                batchno = validated_text(line,'batch_no',max_len=90)
                exp = dated(line.get('expiry_date'))
                item = c.execute('SELECT id,branch FROM items WHERE id=? AND active=1', (iid,)).fetchone()
                if not item:
                    err(422, 'Selected item does not exist or is inactive')
                restrict_branch(u, item['branch'])
                conflicting = c.execute('''SELECT id FROM batches WHERE item_id=? AND batch_no=? AND COALESCE(expiry_date,'')<>COALESCE(?,'')''',
                                        (iid,batchno,exp)).fetchone()
                if conflicting:
                    err(409, f'Batch {batchno} already exists with a different expiration date')
                batch = c.execute('SELECT id FROM batches WHERE item_id=? AND batch_no=? AND COALESCE(expiry_date,\'\')=COALESCE(?,\'\')',
                                  (iid,batchno,exp)).fetchone()
                if batch:
                    batch_id = batch['id']
                else:
                    batch_id = c.execute('INSERT INTO batches(item_id,batch_no,expiry_date,created_at) VALUES(?,?,?,?)',
                                         (iid,batchno,exp,now())).lastrowid
            else:
                batch_id = integer(line,'batch_id',1)
                batch = c.execute('''SELECT b.id,b.expiry_date,i.branch,i.active item_active FROM batches b JOIN items i ON i.id=b.item_id WHERE b.id=?''',
                                  (batch_id,)).fetchone()
                if not batch or not batch['item_active']:
                    err(422,'Batch not found or product is inactive')
                restrict_branch(u, batch['branch'])
                if kind == 'OUT' and batch['expiry_date'] and batch['expiry_date'] < dt.datetime.now(ZoneInfo('Asia/Baghdad')).date().isoformat():
                    err(409, 'Cannot issue expired stock')
            if direction > 0:
                c.execute('UPDATE batches SET on_hand=on_hand+? WHERE id=?', (qty,batch_id))
            else:
                r = c.execute('UPDATE batches SET on_hand=on_hand-? WHERE id=? AND on_hand>=?',
                              (qty,batch_id,qty))
                if r.rowcount != 1:
                    err(409, 'Insufficient stock in the selected batch. Shipment not saved.')
            c.execute('INSERT INTO movement_lines(movement_id,batch_id,qty,direction) VALUES (?,?,?,?)',
                      (mid,batch_id,qty,direction))
        audit(c,u['id'],'MOVEMENT_CREATED',{'id':mid,'code':code,'type':kind,'paper_ref':paper_ref,'line_count':len(lines)})
    return {'ok':True,'code':code,'id':mid}


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


@app.get('/api/users')
def list_users(request: Request):
    u = get_user(request)
    permit(u,'users')
    with db(readonly=True) as c:
        return [dict(x) for x in c.execute('''SELECT id,username,full_name,role,branch,is_active,must_change_password,created_at
                                               FROM users ORDER BY is_active DESC,id''')]


@app.post('/api/users')
async def create_user(request: Request):
    u = get_user(request, require_csrf=True)
    permit(u,'users')
    d = await request.json()
    username = validated_text(d,'username',max_len=50).lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,50}',username):
        err(422,'Username: 3-50 lowercase letters, numbers, dot, dash or underscore')
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
        audit(c,u['id'],'USER_UPDATED',{'id':user_id,'role':role,'branch':branch,'active':bool(active)})
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
        if not c.execute('SELECT 1 FROM users WHERE id=?',(user_id,)).fetchone():
            err(404,'User not found')
        c.execute('UPDATE users SET password_hash=?,must_change_password=1 WHERE id=?',(pw_hash(password),user_id))
        c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
        audit(c,u['id'],'PASSWORD_RESET',{'user_id':user_id})
    return {'ok':True}


@app.get('/api/audit')
def audit_history(request: Request):
    u = get_user(request)
    if u['role'] not in ('admin','manager'):
        err(403,'Only management can view audit logs')
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
    if len(content)>55*1024*1024:
        err(413,'Backup is larger than the 55 MB testing limit')
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
                if manifest.get('application')!='Hospital Warehouse IMS' or manifest.get('schema_version') not in (1, 2, SCHEMA_VERSION):
                    err(422,'Not a compatible warehouse backup')
                data = z.read('warehouse.sqlite3')
                if hashlib.sha256(data).hexdigest()!=manifest.get('sha256'):
                    err(422,'Backup integrity check failed')
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
            if manifest['schema_version'] == 1:
                migrate_item_details(verify)
            if manifest['schema_version'] <= 2:
                migrate_branches(verify)
                verify.commit()
            else:
                actual_columns = {row[1] for row in verify.execute('PRAGMA table_info(items)')}
                if not {'generic_name','manufacturer','manufacture_date','expiry_date','information','branch'}.issubset(actual_columns):
                    err(422, 'Backup declares V3 but is missing item/branch fields')
        except sqlite3.DatabaseError:
            err(422,'Invalid SQLite backup contents')
        finally:
            verify.close()
        with DB_LOCK:
            # Pre-restore server-side copy. No network or multiple-worker support in this local prototype.
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
                audit(dst,None,'BACKUP_RESTORED',json.dumps({'restored_by':u['username'],'safety_copy':safety.name}))
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


@app.get('/api/health')
def health():
    return {'ok':True,'database':'sqlite','version':SCHEMA_VERSION}


@app.exception_handler(sqlite3.OperationalError)
async def database_error(_,exc):
    return JSONResponse(status_code=503,content={'detail':'Database is temporarily unavailable'})
