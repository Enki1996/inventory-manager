# Hospital Warehouse IMS V4.0 — Arabic-first bilingual test app

**New in V4:** Arabic is the default interface language on Home, Login and every Dashboard screen. An العربية / EN switch appears across these pages, stores the browser preference, and changes layout direction (RTL ↔ LTR). The warehouse terminology is editable at `static/locales/ar.json`. No inventory database migration is required.

Read `TRANSLATIONS.md` for Arabic wording changes. See `RAILWAY_SETUP.md` for live deployment.

**For Internet testing on Railway, follow [`RAILWAY_SETUP.md`](RAILWAY_SETUP.md) first. The default local `enki / 123` credentials are BLOCKED on public deployments; use a strong private Railway bootstrap secret.**

# Hospital Warehouse IMS — V4.0 Railway-Ready Shared Testing Prototype

This is the **first database-connected test build** of the same home, login and light-themed dashboard. It is a **web application**, not a standalone static HTML website. The local FastAPI server handles accounts and permissions and stores actual records in a SQLite database file.

## Start on Windows

1. Install Python 3.11 or later from python.org (select **Add Python to PATH**).
2. Extract the full ZIP. Double-click **run_windows.bat**.
3. Let the command window remain open while using the app.
4. Open **http://127.0.0.1:8000** in Chrome/Edge.
5. Click Login. **Test administrator: `enki` / `123`**.

Mac/Linux: `./run_mac_linux.sh`. Alternatively, `python -m pip install -r requirements.txt` followed by `python -m uvicorn app:app --host 127.0.0.1 --port 8000`.

**Do not open the HTML files directly by double-clicking.** They communicate with local server API endpoints, and will not function as a static file-only site.

## Try the workflow

1. Add a department in **Departments** (e.g. `ER`, Emergency).
2. Add an item in **Inventory** (e.g. `MED-001`, Paracetamol 500mg, unit Tablet).
3. Receive an incoming shipment and enter a **receipt paper reference, batch number, expiration date and quantity**.
4. Distribute items to a department using **Distribute to Departments** and its **paper requisition number**.
5. Inspect **Movement History** and **Batches & Expiry**.
6. In **Users & Permissions**, create a staff account and choose a role. Test logging out and signing in as the staff member. Their navigation and server permissions differ.
7. In **Settings**, change the initial admin password. Export a full database ZIP under **Backup & Restore**.

## Real data storage

Created automatically when the application first runs:

`data/warehouse.sqlite3`

Do not delete the file if you want to preserve the data. All save actions go through the backend, and the database persists between restarts. The `data/` folder is intentionally not included in the downloadable project, so each new installation starts clean.

Passwords are salted and hashed with PBKDF2-SHA256. Auth uses an HTTP-only SameSite session cookie and mutation-specific CSRF tokens. Server permissions:

| Role | Rights |
| ---- | ------ |
| Admin | All records, staff/roles, database export/restore |
| Manager | Manage items/departments, receipts, distribution, returns, corrections |
| Operator | View items and departments; record receipt, issue, returns |
| Viewer | Read-only warehouse records and reports |

Admin accounts cannot deactivate themselves, and the last active administrator is protected.

## Portable backups

**Backup & Restore** uses a full database snapshot packaged as a ZIP with a SHA-256 checksum and schema version. Administrator can download the file to a PC/phone and later upload it. The restore process checks integrity and schema, makes a safety copy in `data/safety_backups/`, replaces the database and signs out all sessions.

Backups are **not encrypted** in this early build. Treat the exported ZIP as sensitive: it includes warehouse records and hashed credentials. Do not share it casually. This initial test build does **not** yet offer scheduled off-site backups. Please store downloaded backups in a safe place, and avoid restoring over newer entries casually.

## Hosting

This runs locally for testing; it is **not connected to an internet-hosted database yet**. To deploy it to Railway for testing, use a Python service, set a persistent volume for `WAREHOUSE_DATA_DIR=/data`, run `uvicorn app:app --host 0.0.0.0 --port $PORT`, set `COOKIE_SECURE=1`, protect the database and secure the public URL with HTTPS. For serious multi-user hospital usage, migrate from this single-process SQLite prototype to PostgreSQL, add scheduled off-site backups, conduct security checks, and replace the test password.

### Security notice

The user-requested initial password `123` is **not safe**. Use only with fake test data in a trusted local environment, change it from Settings immediately and **never expose this initial account publicly**. Never use real hospital inventory records or staff secrets in this prototype until production-hardening, data protections and validation have been completed.

## Development verification

`python test_flow.py` uses a disposable database and tests login, CSRF, receiving, issue, oversell prevention, user permissions, backup export and restore. The test file never alters your live `data/warehouse.sqlite3`.
