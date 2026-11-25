# Hospital Warehouse IMS V4.7 — Seven Shipment Routes

One central hospital warehouse, three fixed warehouse branches, twenty approved registers, full item pricing in Iraqi dinar and fils, batch-level stock and expiration tracking, scoped employee permissions, audit history, and portable database backup/restore.

**New V4.7 workflow:** Three outgoing shipment routes and four incoming shipment routes. Emergency department issues may be recorded before paper references are available; both document numbers can be added afterward with an audit entry and without repeating the stock movement. External transfer forms use a trusted pharmacist selected from active employee accounts.

See **[V4_7_SHIPMENT_ROUTES.md](V4_7_SHIPMENT_ROUTES.md)** for exact route fields, deployment, migration and testing. Previous version notes remain in `V4_6_CHANGES.md` and `V4_5_DEPLOY_AND_VERIFY.md`.

## Release verification

`/api/health` returns `{"ok":true,"database":"sqlite","version":6,"release":"4.7.0"}`.

## Local testing

```sh
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8000
```

For **local-only testing**, the initial account is `enki` with password `123`. This password is **blocked for public deployment**. Configure the strong private `WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD` in Railway. Do not place credentials in GitHub or chat.

Run current automated tests from this folder with `python test_v47_routes.py`. Historic tests from older versions are archived under `tests_legacy/` because their previous two-route API contract no longer applies.

## Deployment

Keep the same private GitHub repository, Railway service, and persistent `/data` volume. Export a backup before deploying. Copy V4.7 code onto the same repository and redeploy; the database schema migration is additive and preserves existing inventory and movement history. Never upload the live SQLite file to GitHub.

The interface defaults to Arabic with an English toggle. Edit Arabic translations in `static/locales/ar.json`; product and account names retain exactly the values employees enter.

This is a collaborative testing tool, **not** yet a fully validated clinical inventory system. Use fictitious inventory, not confidential hospital data, until security, operational controls, and backup recovery are reviewed.
