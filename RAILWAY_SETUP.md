# Railway shared testing setup — Hospital Warehouse IMS V4.1

This package contains the Home, Login, Dashboard, API, SQLite schema and bilingual Arabic/English interface (Arabic default). Version 4.1 expands item details and performs an additive database migration on startup. **Download and safely store a current database backup before updating an existing Railway deployment.** Keep the `/data` volume attached to the same service.

## Before you start
- This is a **testing environment**, not a production-ready medical inventory service. Use fictitious data, no real credentials or confidential records.
- Public deployments do **not** accept the old local `enki / 123` password. On an empty database, the admin username is `enki` and its **initial password is the strong secret you set as an environment variable**.
- The local test package uses `enki / 123` for offline testing; it should NEVER be deployed publicly.

## 1. Make a code repository

A. Extract the provided ZIP. Create a new **private** GitHub repository. Upload the contents of the extracted V4.1 project to the repository root (not its enclosing folder).

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
2. Add Item `MED-TEST-001` / Sample Vial.
3. Receive 100 units with a fabricated batch and expiry date, using an incoming document reference.
4. Issue 20 to ER using a fabricated paper requisition number.
5. Refresh, sign out, sign in and verify 80 remain.
6. Re-deploy and verify the records still exist.
7. Sign in as a Viewer and verify they cannot create or edit items.
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

## Updating an existing V3.1 Railway test deployment

If the V3.1 app is already deployed, **do not delete the attached /data volume** and do not upload a database file into GitHub. Commit the V4 files into the same private GitHub repository and Railway can redeploy the code. The SQLite schema is unchanged and existing records remain on the persistent volume. Make a fresh Backup & Restore export first.

### Bilingual UI

- Default on new browsers: **العربية**, with right-to-left page layout.
- Switch to **EN** on Home, Login or Dashboard for left-to-right English.
- Language preference is stored in that browser. It is not a shared account setting.
- Change UI terms and labels in `static/locales/ar.json`, not in `app.py` and not in the database.
- Item names, department names, requisition codes and user-entered notes remain exactly as staff entered them. Bilingual data fields for product and department names can be added in a later database version.
