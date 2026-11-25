# Deploy V4.7 to the EXISTING Railway service

**Same private GitHub repository, same Railway service, same persistent `/data` volume.** Export a backup before updating code. `/api/health` must show `release: 4.7.0` and `version: 6` after redeploy. The additive migration adds shipment route, trusted pharmacist, and emergency paperwork fields without deleting old stock or history. See `V4_7_SHIPMENT_ROUTES.md` for all three outgoing and four incoming routes.

---

# Deploy V4.6 to your EXISTING Railway service

**Do not create a new service or a new database.** Keep the same private GitHub repository, Railway service, and existing `/data` volume. Upload only the updated source code. Before deployment, export a database backup from the existing app.

Run the current release check at `https://YOUR-DOMAIN/api/health` and confirm **`release: 4.6.0` / `version: 5`**. This update adds item prices, outgoing destination and paperwork fields, and movement price snapshots in place. Existing records remain intact. For the exact new behavior and migration notes, read `V4_6_CHANGES.md`.

---

## Prior deployment instructions (V4.5)

# V4.5: fixed Add Item UI, one new Medication book; no database-schema changes.

For detailed verification of your Railway deployment, read **V4_5_DEPLOY_AND_VERIFY.md**.

# V4.4 deployment note

Replace the code in the same PRIVATE GitHub repository and redeploy the SAME Railway service without replacing or detaching the persistent `/data` volume. Back up the live database first. V4.4 originally added two nullable-compatible/defaulted columns to the existing `items` table (`trade_name` and `initial_batch_no`); existing items and movement history are preserved. New items require batch number, expiration date, an approved unit and a matching book for their branch. A V4.5 tag appears in the Add Item modal. Do not commit `.env`, a live SQLite file, or backup files.

# Railway shared testing setup — Hospital Warehouse IMS V4.5

This package contains the Home, Login, Dashboard, API, SQLite schema and bilingual Arabic/English interface (Arabic default). Version 4.2 adds fixed warehouse branches, a book/register category field, and per-employee branch permissions using an additive database migration. **Download and safely store a current database backup before updating an existing Railway deployment.** Keep the `/data` volume attached to the same service.

## Before you start
- This is a **testing environment**, not a production-ready medical inventory service. Use fictitious data, no real credentials or confidential records.
- Public deployments do **not** accept the old local `enki / 123` password. On an empty database, the admin username is `enki` and its **initial password is the strong secret you set as an environment variable**.
- The local test package uses `enki / 123` for offline testing; it should NEVER be deployed publicly.

## 1. Make a code repository

A. Extract the provided ZIP. Create a new **private** GitHub repository. Upload the contents of the extracted V4.5 project to the repository root (not its enclosing folder).

B. In Railway -> New Project -> Deploy from GitHub Repo -> select the repository.

Alternatively, connect the Railway app in ChatGPT and request deployment from there once your account is connected.

## 2. Set Railway variables (service -> Variables)

```
WAREHOUSE_PUBLIC_DEPLOY=1
WAREHOUSE_DATA_DIR=/data
COOKIE_SECURE=1
WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD=<your-unique-secret-of-at-least-14-characters>
```

**Do NOT** paste your password into ChatGPT, code, GitHub, or screenshots. Enter it into Railway's private Variables panel.

## 3. Attach permanent storage BEFORE using the app

Railway -> your service -> Add Volume -> mount path: `/data`.

This is essential: SQLite is currently stored in `/data/warehouse.sqlite3`. Without a persistent volume, Railway's container filesystem is ephemeral and new data may disappear after a redeploy.

For initial testing, configure a single running replica and only **one server worker** (already set via `railway.json`). A single-volume SQLite instance is fine for small friend-group tests; for hospital-wide use migrate to PostgreSQL.

## 4. Deploy and generate a public URL

Once the deployment succeeds: Service -> Settings -> Networking -> Generate Domain. Open that Railway URL over HTTPS. Sign in as `enki` using your private bootstrap admin password.

After login, create a test operator and test viewer from Users & Permissions, then give each tester their own username and unique password. Don't share the admin account.

## 5. Verify persistence and permissions

1. Create Department `ER` / Emergency.
2. Add a dummy Medication item with trade and scientific names; choose the **Medication** branch and the official book **سجل الحياتية - قسم الصيدلة**.
3. Receive 100 units with a fabricated batch and expiry date, using an incoming document reference.
4. Issue 20 to ER using a fabricated paper requisition number.
5. Refresh, sign out, sign in and verify 80 remain.
6. Re-deploy and verify the records still exist.
7. Create a Manager in the Medication branch and verify they cannot edit or issue stock belonging to the Surgical Instruments branch. Also test a Viewer (read only).
8. Export a backup ZIP in Backup & Restore, store it privately.

## 6. Backups

Enable Railway service volume backups in the Railway Backups panel (if available on your plan). Also make manual encrypted/off-site copies of downloaded database ZIPs. The app's current backup ZIP downloads contain user password **hashes** and operational records; app-generated ZIPs are **not encrypted**. Do not send them over chats or store them in public folders. Test restores only in a noncritical test environment.

## Known limits

This is not production-ready: no full security audit, no centralized rate-limiting, no encrypted application backup exports, no scheduled off-site external backup automation, and no multi-instance support. Never rely on it for critical clinical inventory without additional engineering, test coverage and authorization.

## Troubleshooting

- *Deployment fails with PUBLIC DEPLOYMENT BLOCKED*: configure a strong `WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD` variable, and don't deploy a local V3 database still using `123`.
- *Application failed to respond*: check Railway deployment logs; it must bind to `0.0.0.0:$PORT`.
- *My data disappeared*: verify Railway has a volume mounted at `/data` and the environment variable `WAREHOUSE_DATA_DIR=/data` matches.
- *I can log in but cookies fail*: ensure the domain uses HTTPS and `COOKIE_SECURE=1`.

## Updating an existing V4.1 Railway test deployment

**Download a backup first.** Do not remove or replace the attached `/data` volume, and do not upload a database file to GitHub. Update the existing private GitHub repository with the V4.5 code. Railway redeploys the application, which automatically adds `items.trade_name` and `items.initial_batch_no` to the SQLite database without deleting records. Existing historical items and staff cannot be assigned a branch automatically without guessing; the admin must edit them and choose one of the fixed branches. See `ITEM_FIELDS_V4_4.md` for the new fields and unit rules.

### Bilingual UI

- Default for new browsers: **العربية**, with right-to-left page layout.
- **EN** switches to English, with left-to-right layout.
- Language preference is browser-local, and medical product names or user-entered data remain exactly as saved.
- Interface terminology is editable at `static/locales/ar.json`.
