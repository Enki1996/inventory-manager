# Hospital Warehouse IMS V4.9 — Railway instructions

## Already deployed on Railway? (your normal situation)

You DO NOT need a new Railway project, volume, or database. This release is an in-place source-code update:

1. Download a current backup from the live application and keep the ZIP private.
2. Verify your existing database is stored under the same Railway service's persistent volume at `/data` (`WAREHOUSE_DATA_DIR=/data`).
3. Extract the V4.9 ZIP and commit the **source** files to the ROOT of your EXISTING private GitHub repository. Don't upload the ZIP itself, SQLite files, backup files or secrets.
4. Update/redeploy the existing Railway service from the same GitHub repository. Keep your existing volume attached. Don't reset the database.
5. Verify `/api/health` responds with `"release":"4.10.0"` and `"version":7`.
6. Log in and verify the added departments and outgoing priced-lot form. A one-time seed adds the 59 starter departments only if not previously added; all existing department records remain.

## New Railway project (only if needed)

- Create a PRIVATE GitHub repository and upload the extracted source files.
- Deploy from GitHub using a single Railway service and **one worker/replica** (`railway.json`).
- Add a **persistent volume** mounted at `/data` BEFORE running real tests.
- In Railway's private Variables panel, set:

```env
WAREHOUSE_PUBLIC_DEPLOY=1
WAREHOUSE_DATA_DIR=/data
COOKIE_SECURE=1
WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD=<a strong secret of at least 14 characters>
```

- Do not paste the password into chat, GitHub, or screenshots.
- Generate a Railway HTTPS domain. Create individual staff accounts in the application; do not share the administrator login.

## Data integrity and backups

- Changes to code do not replace the database if the Railway persistent volume is attached correctly.
- Downloaded backups are unencrypted and contain sensitive data, including password hashes. Store them securely. Arrange off-site backup copies and regularly test recovery.
- SQLite requires one server worker with a single writable database; multiple replicas are not supported by this build. For broader hospital-wide use, migrate to a managed PostgreSQL database with carefully tested migrations.
- Do not enter patient or confidential hospital data into this test build; this has not undergone production security and clinical inventory validation.

## V4.11 update

Only application code changes. The persistent SQLite schema remains **7**. Keep the existing mounted `/data` volume. After deploying from GitHub, check `/api/health` for release **4.11.0**, then open **المواقف**. Details: `V4_11_WAREHOUSE_STATEMENTS.md`.
