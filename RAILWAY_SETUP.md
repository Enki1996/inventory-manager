# Hospital Warehouse IMS V4.12 — Railway deployment

## Already online: update your EXISTING service

1. Create and download a current backup using **Backup & Restore**. Store it privately.
2. Confirm your existing Railway service has a persistent volume mounted at `/data`, and the environment variable `WAREHOUSE_DATA_DIR=/data`.
3. Extract `Hospital_Warehouse_IMS_V4_12_Annual_Need_Statements_Railway.zip` and commit its **source files**, not the ZIP itself, to the **same private GitHub repository**.
4. Redeploy/update the **same Railway service**. **Do not detach, delete or reset `/data`**, and do not create a new service/database for an ordinary code update.
5. Open `/api/health` on your Railway URL. Expected fields: `"ok":true`, `"release":"4.12.0"`, `"version":8`.
6. Verify your older departments, accounts, stock and movements are still present, then test one new item's **كمية الاحتياج السنوي**, the custom cutoff date, and a scarce/surplus percentage.

V4.12 applies a non-destructive SQLite migration that adds the optional `items.annual_need` column. Existing items' values remain unset until entered. Earlier backups are still supported by the restore function, subject to its existing access controls and safety confirmation.

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
