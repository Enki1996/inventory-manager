# Hospital Warehouse IMS — V4.6 (Arabic-first)

This release **updates the existing V4.5 application**. No new Railway service or database replacement is needed.

## 1. Item price (سعر الوحدة)

All newly created items and edited items use two mandatory inputs:

- **دينار** — whole Iraqi dinars (0 to 999,999,999).
- **فلس** — 0 through 999. **1,000 fils = 1 IQD**.

The app saves the exact combined integer amount in SQLite as `items.price_fils`, avoiding floating-point rounding. The price is **per catalog stock unit**. Existing items receive NULL (`—`, unknown) and are **not assumed to cost zero**. An administrator or authorized employee can enter prices when editing those records. New movement lines also retain a unit-price snapshot in `movement_lines.unit_price_fils`, so historical movement prices are not silently changed when an item price is edited later.

No selling, purchasing, billing, or payment calculation has been added.

## 2. تجهيز طلبية — Outgoing shipment

The Outgoing / Distribution screen now has two **mutually exclusive** destinations:

**أقسام المستشفى — Hospital department**
- Choose the department.
- Enter **رقم ورقة الطلبية** (request/order paper number, required).
- Enter **رقم ورقة التجهيز** (warehouse dispatch paper number, required).

**مناقلة خارجية — External transfer**
- Enter receiving hospital or external sector / organization (required).
- Enter a transfer document number (required for traceability).
- Optional dispatch paper number.

Both modes use a permanent internal OUT movement ID, deduct selected available batches **atomically**, and appear in movement history. The new outgoing record stores `destination_type`, `external_destination`, and `dispatch_ref` separately from `paper_ref`. Existing pre-V4.6 department issues remain visible; their historical second dispatch references are left blank rather than fabricated.

## 3. Item not found in an outgoing shipment

Authorized item editors see **+ تسجيل صنف غير موجود** beneath the batch selector. Clicking it:

1. Opens the same branch-aware Add Item form (including 20 approved books, official units, compulsory expiry and price).
2. Saves the item with a zero-stock batch. The unfinished OUT shipment and entered paperwork numbers remain untouched.
3. Offers a mini **incoming receipt** form (real incoming paper number, supplier, quantity, batch, expiry). If physically received, this saves an ordinary IN movement with complete audit history and then auto-selects the available batch on the OUT form.
4. If the receipt is cancelled, the catalog item remains registered but cannot be issued until a documented IN receipt is recorded.

The same inline Add Item option is available on the incoming receipt product selector. Users without item-write permission cannot create catalog records, even via inline buttons.

## Deployment and verification

1. Sign in to the currently live instance and download a backup using **Backup & Restore**. Keep the downloaded backup securely and separately from Railway.
2. Upload this ZIP's **contents**, not the ZIP itself or its parent folder, to the **existing private GitHub repository**. Do **not** upload database (`.sqlite3`) files, `/data`, `.env`, or backups.
3. Redeploy the **same Railway service**, without removing or replacing the mounted `/data` volume. Keep `WAREHOUSE_DATA_DIR=/data`.
4. Check `https://YOUR-DOMAIN/api/health`. It must return `"release":"4.6.0"` and `"version":5`. The version 5 database migration adds columns and does not remove existing tables.
5. Hard refresh with Ctrl+Shift+R (or open a private tab). Test Add Item prices, both outgoing destination types and the inline registration flow with sample records.

**Important:** This remains a shared test application. Use fictitious hospital records until backups, authentication, logging and security have been reviewed for real operational use. The unchanged local-only `enki`/`123` demo password is not permitted for public deployment; set and protect a strong production password in Railway.
