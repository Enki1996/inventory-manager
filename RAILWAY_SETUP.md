## V4.20 update

See `V4_20_CHANGES.md`. Schema V9 unchanged. Keep existing `/data` volume and back up before updating.

## V4.19 upgrade note
This release changes interface code only. Schema remains **9**. Redeploy to the same service, retain `/data`, and check `/api/health` reports `4.19.0`. Do not restore or replace the database for this update.

**V4.18: no database migration. Keep the existing `/data` volume attached. Back up current records before deploying.**

# Hospital Warehouse IMS V4.15 — Railway deployment

## Already online: update your EXISTING service

1. Create and download a current backup using **Backup & Restore**. Store it privately.
2. Confirm your existing Railway service has a persistent volume mounted at `/data`, and the environment variable `WAREHOUSE_DATA_DIR=/data`.
3. Extract `Hospital_Warehouse_IMS_V4_15_Monthly_Statements_Railway.zip` and commit its **source files**, not the ZIP itself, to the **same private GitHub repository**.
4. Redeploy/update the **same Railway service**. **Do not detach, delete or reset `/data`**, and do not create a new service/database for an ordinary code update.
5. Open `/api/health` on your Railway URL. Expected fields: `"ok":true`, `"release":"4.15.0"`, `"version":8`.
6. Verify your older departments, accounts, stock and movements are still present, then test the 20% scarce and 120% surplus monthly defaults, a custom percentage and the reset control.

V4.15 uses existing `items.annual_need` values and derives monthly need on the fly. No schema changes, database reset or restore are required. Earlier backups remain supported by the existing restore logic and safety controls.

## New deployments (only if necessary)

- Create a **private** GitHub repository and connect it to one Railway service.
- Mount a Railway **persistent volume** at `/data` before entering inventory data.
- Set private Railway Variables (do not put secrets in the GitHub repository or chat):

```env
WAREHOUSE_PUBLIC_DEPLOY=1
WAREHOUSE_DATA_DIR=/data
COOKIE_SECURE=1
WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD=<strong unique password at least 14 characters>
```

- Deploy the included `railway.json`, using a single worker/replica for SQLite. Then generate your HTTPS Railway domain.
- Create a distinct account and appropriate branch permissions for each colleague. Do not share the admin password.

## Safety

This application is for collaborative testing. It does not yet have the security and audit validation expected for real clinical/hospital operations. Downloaded backups are not encrypted and include password hashes: store them securely and test recovery. Keep independent off-site backups and protect the Railway account. For future multi-worker or hospital-wide use, plan a managed PostgreSQL migration.


## V4.14 deployment
This is a frontend/read-only API update. Keep the existing Railway application service and `/data` persistent volume. No database migration is required; `schema version = 8`. Verify `/api/health` includes `"release":"4.14.0"`.

See V4_14_CHANGES.md for the latest UI fixes.


## V4.15 deployment
Keep the same Railway service and `/data` volume. Schema is still **V8**. `/api/health` must report `"release":"4.15.0"`. See `V4_15_CHANGES.md`.


## V4.16 opening balance update

This update uses the existing schema V8. It only adds application logic and the optional opening-stock fields. Keep the same Railway service and persistent `/data` volume; do **not** overwrite or upload a database file during the code deployment. Make a backup first. Check `/api/health` for `release: 4.16.0`. See `V4_16_CHANGES.md`.


## V4.17 — upgrade the same Railway service

1. Download an admin backup of your **current live database** and save it to a secure computer.
2. Keep the existing Railway volume mounted at `/data` and keep `WAREHOUSE_DATA_DIR=/data`.
3. Replace the application **source files** in your existing private GitHub repository; do not upload any `.sqlite3` file, backup ZIP, or passwords to GitHub.
4. Redeploy the existing Railway service. On startup, V4.17 adds optional per-lot manufacture dates and employee profile fields; existing stock, accounts and movements stay intact.
5. Open `https://YOUR-DOMAIN/api/health` and check `"release":"4.17.0"` and `"version":9`.
6. Verify **رصيد افتتاحي**, **حركة المواد**, **Departments → Shipment history**, and **My account** with test records.

Note: This is a **code update**, not a database restore. Do not restore a demo backup when upgrading your live app.

## V4.21 — Google Drive automatic off-site backup

See [`GOOGLE_DRIVE_AUTOBACKUP_SETUP.md`](GOOGLE_DRIVE_AUTOBACKUP_SETUP.md) for required OAuth Web client setup, the encrypted key, the new variables on this service, **10AM and 2PM Baghdad** Cron service deployment from the same private repository, manual backup test, and recovery instructions.

Keep the existing Railway `/data` volume; this version does not change schema V9. No OAuth secret, Drive tokens, admin password or backup encryption key belongs in GitHub.


## V4.23 Home/Logo/Legal Pages

Update your existing GitHub repository with V4.23 and redeploy the **same** Railway web service. Keep `/data` (persistent volume) and the existing environment variables untouched. No database restoration or scheduler changes are needed. Check `/api/health` for `"release":"4.23.0"` and `"version":9`. Verify `/`, `/login.html`, `/privacy.html` and `/terms.html` and review the policy draft before official use.
