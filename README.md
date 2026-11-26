# Hospital Warehouse IMS — V4.14

Read V4_13_CHANGES.md for the combined inventory, expandable lot details, configurable columns and per-item movement history.

# Hospital Warehouse IMS — V4.12

Arabic-first bilingual, single-warehouse inventory application for testing on Railway. Home, Login, Dashboard, inventory, department and staff accounts, permissions, branches/books, multiple priced lots and expiries, 7 shipment routes, FEFO issuing safeguards, movement history, and administrator Backup & Restore remain available.

## V4.12 — What changed

- **كمية الاحتياج السنوي (Annual requirement quantity)** is now stored per registered item, as a whole-number quantity in that item's existing unit. Create/Edit Item contains the new field after the Iraqi dinar/fils price fields; inventory lists the saved quantity. Older items are marked **not entered** (`NULL`), never silently treated as zero. Existing records, receipt lots, movement prices, and stock counts are unchanged.
- **موقف المواد قريبة النفاذ** keeps the V4.11 default reporting window (through the last day of the current month in the next year), but staff can select any **expiration before** cutoff date and reset to the default. The specified cutoff is *exclusive*: e.g., "before 2027-12-01" includes dates through Nov 30, 2027. Expired lots are excluded.
- **موقف المواد الشحيحة** and **موقف المواد الفائضة** are available with **user-entered percentages**. There are NO assumed official thresholds. For an item with annual need 1000, a scarcity threshold of 25% flags usable stock below 250; a surplus threshold of 125% flags usable stock above 1250. Comparisons are strict (< for scarce, > for surplus). Reports display remaining quantity, annual need, and calculated percentage.
- To avoid presenting expired stock as available, percentage reports count only dated, **unexpired** lots. Lots with no recorded expiry are excluded pending verification. Catalog items without a positive saved annual requirement are excluded from percentage classifications and counted separately in the report notice.
- **موقف المواد المفقودة** remains a separate report for items with zero *physical* balance, including items never received. It is not the same as scarcity.
- Data structure migrated additively to **SQLite schema V8**; no reset or overwrite is needed. V4.11 database upgrades and V4.11 backup restore were tested.

Detailed change and calculation notes: `V4_12_CHANGES.md`.

## Deploying updates safely on your current Railway service

1. Sign in as an administrator and **export a database backup**. Store it securely: backup ZIPs contain operational data and password hashes and are not encrypted by this build.
2. Confirm your existing Railway service has the persistent database volume attached at `/data` and `WAREHOUSE_DATA_DIR=/data`. Do **not** create a new database or detach/delete the current volume.
3. Extract this ZIP and push the **source files** to the root of your **existing private GitHub repository**. Do not upload backup ZIPs, SQLite files, `data/`, or passwords.
4. Redeploy the **same Railway service** from GitHub.
5. Verify `https://YOUR-SITE/api/health` includes `"release":"4.12.0"` and `"version":8`. Open Inventory → Add Item and المواقف to confirm the updated fields and report controls.
6. Check some pre-existing items, accounts, departments, lots and outgoing movements after deployment before testing new entries.

This is a test build, **not** a validated production clinical inventory system. Keep one Railway worker/replica with SQLite; secure the public administrator credentials and backups, and do not enter patient-identifiable or confidential hospital data during testing.

## Tests

When dependencies from `requirements.txt` are installed:

```bash
python test_v412.py
python test_v412_fefo.py
python test_v412_regression.py
```

Each test uses its own temporary data directory; the scripts must not be run against a live Railway database. A V4.11 in-place migration and V4.11 ZIP backup restoration were also tested separately. The local browser preview was blocked in this environment, so review the live visual layout after deployment.

See V4_14_CHANGES.md for the latest UI fixes.
