# Hospital Warehouse IMS V4.28 — Analytics

See `V4_28_ANALYTICS.md`. Existing schema V10 and Railway volume remain unchanged. All four supplied fonts are already bundled.

# Hospital Warehouse IMS V4.27.1 — Typography Refresh

See [`V4_27_1_TYPOGRAPHY.md`](V4_27_1_TYPOGRAPHY.md). The new Arabic font styling applies to Home and Login as well as major headings on related pages. All four supplied fonts are included in `static/fonts/`. Schema V10 unchanged.

# Hospital Warehouse IMS V4.27 — Print & Report Designer

The **المواقف** section now has a dedicated, authenticated print designer with column selection, A4 Arabic preview, portrait/landscape, item or lot level rows, and native PDF/physical printing. **No stock database migration is required (Schema V10).** See [`V4_27_CHANGES.md`](V4_27_CHANGES.md) for the full workflow and how existing report filters are carried into print.

## V4.26 — List Pagination and Recovery Colors

- Paginated inventory, item movements, departments, staff accounts, movement register, audit log, and reports. Page sizes: 20 / 50 / 100.
- Movement and audit logs now page through the complete database, not only the most recent 500 / 300 records.
- Item and department shipment histories and per-item movement ledgers use pagination.
- **المواقف** reports deliberately remain unpaginated.
- Undo is lavender; Redo is peach/terracotta, without changing stock receipt/dispatch colors.
- Database Schema V10 unchanged. No restore required.

**Current release: V4.25.1** — Arabic headline typography/cache-busting fix. See `FONT_FIX_V4_25_1.md`; database Schema V10 unchanged.

## Current release: V4.25 — Controlled Undo/Redo

See **V4_25_CHANGES.md**. This is an additive migration to **Schema V10**, with selective shipment Undo, Ultra Admin Redo and eligible audit-edit recovery, plus neutral legal pages and optional supplied-font styling. **Back up first, redeploy the same Railway service, and keep `/data` attached. Do not restore a database as part of an ordinary code update.** Verify `/api/health` reports `release: 4.25.1`, `version: 10`.

## V4.20 update

See `V4_20_CHANGES.md`. Schema V9 unchanged. Keep existing `/data` volume and back up before updating.

## V4.19 update
See `V4_19_CHANGES.md` for numbered item lists, nested item details, and deployment instructions. Use the same Railway service and existing persistent database volume. This ZIP contains no database.

## V4.18 update
See `V4_18_CHANGES.md` for account, audit log, notification dialog, and expiry-first outgoing changes. Deploy to the **same** Railway service with the existing `/data` volume attached. This ZIP contains **code only**, not a database.

# Hospital Warehouse IMS — V4.17

Arabic-first bilingual, single-warehouse inventory web app with role and branch permissions, multiple batches/expiry dates/prices, receiving and distribution, FEFO stock-issuing recommendations, full movement history, 59 preloaded departments, inventory inspection, warehouse statements, and administrator backup/restore.

## V4.17: Multiple opening lots, item timelines, department shipments and staff profiles

See **V4_17_CHANGES.md** for exact behavior and deployment notes.

- **رصيد افتتاحي** now accepts multiple batch/expiry/manufacture/quantity/price rows at once.
- New **حركة المواد** tab shows every historical shipment for the selected item.
- The **Departments** list displays the last shipment date and offers each department's full shipment history.
- New **My account / الملف الشخصي** page for an employee's own name, phone, email, age and job title.
- Auto-upgrades the existing SQLite database to **schema V9** without resetting stock; tests and original V4.16 restore were verified.

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
4. Redeploy that same Railway service. V4.17 **adds optional schema V9 columns automatically**, keeping your existing inventory history.
5. Visit `https://YOUR-SITE/api/health` to verify `"release":"4.17.0"` and `"version":9`.
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

## V4.21 — Encrypted Google Drive backups (opt-in)

- Admin-only Google OAuth connection, encrypted `.hwenc` backups, manual encrypted cloud backup, and manual download/decryption back into standard restore ZIP.
- Two scheduled backups **10:00 and 14:00 Baghdad time** using a separate Railway Cron service (deploy the cron-only ZIP from a second private GitHub repository).
- Existing SQLite database schema V9 and current Railway volume remain unchanged.
- **First read `GOOGLE_DRIVE_AUTOBACKUP_SETUP.md`**. Cloud backups do **not** begin until an administrator authorizes a dedicated Google account and configures the Cron service.
- Automated pruning of old Drive files is **not active** pending the first verified restore and dry-run retention tests.

## V4.22 — Owner-controlled cloud restoration and interface refinement

Read `V4_22_CHANGES.md` before updating. The existing V4.21 cron worker and all Google/Railway credentials remain unchanged. SQLite schema stays at V9.


## V4.24 — Official IMS branding and public pages

The supplied **المذخر IMS** brand is now used on the responsive Home page, Login, dashboard sidebar and favicon. The public Home page remains **one page** with working smooth-scroll anchors for Home, Features, Workflow and Data Protection. The interactive preview uses illustrative data only.

Separate bilingual pages are served at `/privacy.html` and `/terms.html`. The V4.23 legal text was superseded by the neutral V4.25 version; see **V4_25_CHANGES.md**. The Arabic text is editable in `static/locales/ar.json`; Home/Legal HTML in `static/`; shared marketing styles in `static/marketing.css`.

**No database migration is required**: application release V4.24.0, database schema V9. Keep the existing persistent Railway volume and all environment variables unchanged. Export a backup before redeploying. Google Drive backups require their existing authorization and scheduler setup; this release does not enable them automatically.


## V4.24 hero update
See `V4_24_CHANGES.md`.

Local typography: see V4_27_1_TYPOGRAPHY.md; all four supplied fonts are bundled.
