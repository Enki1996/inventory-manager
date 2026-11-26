# Hospital Warehouse IMS — V4.17

## What changed

### 1. رصيد افتتاحي — multi-lot opening balance
- Add Item defaults to **no opening balance**: no initial quantity, price, batch number, expiry date or manufacture date fields appear.
- Tick **رصيد افتتاحي** to reveal one opening-lot row.
- Click **+ Add another batch** to enter up to 40 separate opening lots in the same new-item registration.
- Each lot records `batch_no`, `manufacture_date` (optional), `expiry_date` (required), `opening_qty` (positive integer), `price_dinars` and `price_fils_component` (both required, can be zero).
- All lots are created **atomically**, along with one `رصيد افتتاحي` movement that has a separate line for each lot and an audit record. Invalid input rolls back the entire transaction.
- Expiry dates and manufacture dates belong to each individual lot. A catalog-level reference date does **not** overwrite multiple actual lot dates.
- Legacy single-opening fields sent by older clients remain accepted.

### 2. حركة المواد
- New dedicated sidebar tab **حركة المواد** lists registered items and supports searching by name, batch, SKU and alternate names.
- Click **Track movements** to see a read-only popup with **all recorded shipment documents involving that item** (not just the latest 500 global movements).
- Each document displays its date, movement ID, direction, route, paperwork references, source/recipient, operator, pharmacist/authorization when applicable, and **every line on the shipment** with lot, expiry, manufacture date, quantity and saved movement price.
- Loading is paginated to avoid a huge response on active warehouses. No stock quantities are changed by opening a history popup.

### 3. الملف الشخصي
- New self-service My account page accessible in the sidebar and account menu.
- Staff may edit **full name, phone, email, age and job title**. All are optional except full name.
- Role, username, assigned warehouse branch, password, account activation and sessions cannot be changed through this route.
- Only the logged-in staff member can read/update their own contact fields. Updates are audited without recording the actual contact information in the audit detail.

### 4. Departments
- Each department row shows the **last recorded department shipment date**, its total shipment count, and a **Shipment history** button.
- The button opens a read-only, paginated document timeline with all line details and document references.
- Movement badges retain the requested colors: **إدخال مخزني = light red** and **إخراج مخزني = light blue**; opening balances have a separate amber badge.
- Creating, renaming and deactivating departments still work as before.

## Database migration / deployment

**App release:** 4.17.0  
**Schema version:** 9

V4.17 adds nullable `batches.manufacture_date` and optional profile columns on `users`, plus performance indexes for the read-only shipment timelines. It does not delete or replace existing items, stock lots, movement records, accounts, branches, books or requisition references.

Upgrade is automatic on startup using the existing `/data/warehouse.sqlite3` attached to your **same** Railway service. A database backup from schema V8 can also be restored and migrated to V9. Restoring a demo/test database is unnecessary and would overwrite your live records.

**Before deployment:** export a full backup of the existing database and keep a copy off Railway. Do not upload the database file to GitHub. Update the application source files, keep the existing `/data` volume attached, and redeploy. Check `/api/health` for `"release":"4.17.0"` and `"version":9`.

**Testing:** V4.12–V4.16 regression tests, V4.17 backend integration tests, in-place V8 → V9 upgrade, and restore of an original V4.16 backup passed. JavaScript syntax passed. A full browser UI test was not possible because local browser navigation was blocked; verify screens on Railway with fictional data before operational use.

This remains a shared warehouse test build. Personal employee information must be handled as private data, and real hospital use requires production security review, encryption/off-site backups and tested restore procedures.
