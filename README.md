# Hospital Warehouse IMS — V4.16

Arabic-first bilingual, single-warehouse inventory web app with role and branch permissions, multiple batches/expiry dates/prices, receiving and distribution, FEFO stock-issuing recommendations, full movement history, 59 preloaded departments, inventory inspection, warehouse statements, and administrator backup/restore.

## V4.16: Optional opening balance (رصيد افتتاحي)

- Add Item normally without a lot, expiry, unit price, or quantity: this creates a zero-stock catalog item.
- Tick **رصيد افتتاحي** to reveal quantity, batch number, required expiry, and dinar/fils price; this records real existing stock immediately in a separate auditable opening-balance movement.
- The stock and movement are saved in one atomic database transaction; historical lots remain independent.
- No schema change or database reset; the same Railway volume remains attached. See **V4_16_CHANGES.md**.

## V4.15: Monthly requirement reports

- **الاحتياج الشهري = كمية الاحتياج السنوي ÷ 12**. This is derived, so the database's existing annual need entries are reused unchanged.
- **موقف المواد الشحيحة** shows items with usable stock **below 20% of their monthly requirement**, by default.
- **موقف المواد الفائضة** shows items with usable stock **above 120% of their monthly requirement**, by default.
- A percentage input in each report lets staff temporarily choose their own threshold; **استعادة النسبة الافتراضية** resets it to 20% or 120%. Comparisons are strict.
- Monthly requirement and the ratio appear in the configurable report columns; expand any item for lots, dates, prices, and movement history.
- Items without annual requirement are excluded. Expired and undated lots do not count as usable stock. The missing-stock and custom near-expiry reports retain their existing logic.

Full examples, boundary rules, and verification steps: **V4_15_CHANGES.md**.

## Update an existing Railway service

1. Export a full backup from the currently running warehouse before changing code. Backup ZIPs are sensitive (contain data and password hashes); store privately.
2. Confirm the current Railway service retains its persistent volume at `/data`, with `WAREHOUSE_DATA_DIR=/data`. Do **not** detach, delete, reset, or replace it.
3. Extract this ZIP. Push its *files* to the root of your **existing private GitHub repository** (not the ZIP, not the demo database, not `/data`).
4. Redeploy that same Railway service. The app still uses **schema V8**, so there is no database migration for V4.16.
5. Visit `https://YOUR-SITE/api/health` to verify `"release":"4.16.0"` and `"version":8`.
6. Open **المواقف**, verify the 20% / 120% defaults, try a custom percentage, then use the Reset button. Check the existing stock, users, departments, and movements are still intact.

New deployment setup is documented in **RAILWAY_SETUP.md**.

## Local tests

```bash
pip install -r requirements.txt
python test_v416_opening.py
python test_v415_monthly.py
python test_v412.py
python test_v412_fefo.py
python test_v412_regression.py
python test_v413_details.py
python test_v414_release.py
```

Tests create temporary databases; never run tests with production data. This remains a **testing version**, not a validated hospital production system. Use test data; do not enter sensitive medical or patient data. Secure accounts and backups. SQLite requires a single Railway worker/replica.
