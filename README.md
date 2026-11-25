# Hospital Warehouse IMS — Version 4.9

Arabic-first, bilingual, single-warehouse inventory testing application. Includes the existing Home, Login, Dashboard, FastAPI backend, SQLite database, user permissions, batch/lot-based stock, prices in Iraqi dinars/fils, 3 outgoing routes, 4 incoming routes, a permanent movement ledger, and administrator Backup & Restore.

**This is an incremental code update for your EXISTING private GitHub repository and Railway service, NOT a replacement database.**

## V4.9 changes

1. **تجهيز طلبية — outgoing item lines:** Product, **specific received lot / الوجبة**, lot expiry (automatically displayed), quantity, **دينار**, and **فلس**. The selectable lot determines the true batch/expiry and available balance. The outgoing unit price defaults to its received-lot price but may be changed **for that outgoing movement only**. Both the original receipt lot price and the outgoing historical price are preserved separately.
2. **تعديلات المخزون:** The duplicate department return form is removed. Department returns are still available through **استلام الشحنات → إرجاع طلبية داخلية**. The audited inventory adjustments screen remains.
3. **59 starter departments:** All names provided by the warehouse are preloaded once into any current database that has not received this V4.9 seed. Existing departments are not deleted or overwritten. Users can **add, rename or deactivate** departments. A one-time seed marker prevents a renamed default department from reappearing on subsequent restarts.
4. **Department search:** A searchable dropdown with a search field at the **top of the open menu** is used when selecting departments for outgoing issues and incoming internal returns. The Departments management page has an additional search filter.
5. Arabic remains the default. The approved light theme and all existing branches, books, authorization documents and permissions remain unchanged.

See `V4_9_CHANGES.md` and `department_catalog.py` for implementation details and the exact 59 department names.

## Updating Railway safely

1. Download an administrator backup from the running app's **Backup & Restore** page, and store the archive privately (it contains sensitive operational data and password hashes; it is not encrypted).
2. Verify the same Railway service has its existing persistent volume mounted at `/data`, with `WAREHOUSE_DATA_DIR=/data`.
3. Update **source files only** in the root of the existing private GitHub repository. Do not upload SQLite data files, database backups, or environment secrets to GitHub.
4. Redeploy the **same** Railway service. Do not delete, replace, or detach the existing volume.
5. Visit `https://YOUR-DOMAIN/api/health` and verify `"release":"4.10.0"` and `"version":7`.
6. Check a pre-existing movement, a pre-existing department, the 59 preloaded department names, the searchable department picker, and an outgoing transaction using a test batch with two distinct receipt prices. Inspect its historical outgoing price.

**Database schema version remains 7.** The new departments are added non-destructively. V4.8 backups remain compatible.

## Local test

```bash
pip install -r requirements.txt
python test_v49_regression.py
uvicorn app:app --host 127.0.0.1 --port 8000
```

Local demonstration-only initial login is `enki` / `123`. **Never use that password on an internet-facing Railway service.** Public deployments require a strong admin bootstrap password stored privately in Railway variables; see `RAILWAY_SETUP.md`.

For Arabic wording edits, use `static/locales/ar.json`. Product/department names entered into the database are not translated automatically.

## Important operational limits

This is still a multi-user **testing build**, not a validated clinical inventory system. Use fictitious stock while testing. The manual exported backups are unencrypted; keep them off public drives/chats. Implement production-grade access auditing, rate limits, encrypted off-site backups and restore drills before relying on this software for actual hospital operations.

## V4.11 — المواقف / Warehouse Statements

Added a dedicated read-only dashboard tab with functioning **Missing materials** (zero stock) and **Materials nearing expiry** (dated, stocked lots through the last day of this month next year), plus intentionally disabled **Scarce materials** and **Surplus materials** buttons pending calculation rules. See `V4_11_WAREHOUSE_STATEMENTS.md`. No database schema change; keep the existing Railway volume and data.
