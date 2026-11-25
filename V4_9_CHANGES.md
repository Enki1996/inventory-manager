# V4.9 — Outgoing lot details, returns consolidation, 59 department defaults

## Outgoing item rows (تجهيز طلبية)

For each outgoing product, the row contains (in exactly this order):

1. **الصنف — Product:** select an existing inventory item; inline item creation remains available.
2. **الوجبة — Lot:** select an existing received lot of that product. The list displays the batch number, expiry date, quantity available and original received-lot price, distinguishing lots with identical batch numbers but different prices/expiry.
3. **تاريخ الصلاحية — Expiration:** displayed read-only from the selected lot. This is NOT a new editable expiry date for an existing stock lot.
4. **الكمية — Quantity:** enter outgoing quantity; available stock and expired-lot rules remain enforced server-side.
5. **السعر — دينار — Dinars:** defaults to selected lot's recorded price; editable for the current outgoing movement.
6. **السعر — فلس — Fils:** 0–999; same snapshot semantics.

**Database behavior:** outgoing `movement_lines.unit_price_fils` is a historical value for this movement. It may differ from `batches.unit_price_fils` (the original receipt lot price). Changing an outgoing price does not change the stock lot's price or any earlier movements. All values are exact integer fils. The server ensures `item_id` matches `batch_id`, validates price components, rejects expired stock/over-issues, and applies all branch permissions. Legacy clients that send just `batch_id` keep working and automatically use the lot price. No new database column is required.

## Returns and corrections

There is exactly one internal departmental return workflow: **استلام الشحنات → إرجاع طلبية داخلية**. It records kind `RETURN` in the existing movement ledger and adds stock to the selected lot. The duplicate return form was removed from the **Stock Adjustments / تعديلات المخزون** tab; administrator/manager adjustment forms are retained unchanged. Historical return movements remain visible in the movement ledger.

## Starter departments

The `department_catalog.py` module contains **59 official names**, in the exact user-provided order, from `طابق اول - ردهة كسور رجال` to `دار الاطباء`.

On the first startup with V4.9:

- Existing department names are checked first; no identical name is duplicated.
- Missing starter names are inserted with automatically generated internal `DEP-000...` codes.
- `app_meta.starter_departments_v49_done` is saved in the same transaction. Later renames are **not reversed or duplicated** on restart.
- Previously created/edited departments and their historical movement references remain unchanged.
- Staff can continue adding, renaming, or deactivating departments with their existing permissions.

An older compatible database backup restored into V4.9 also receives the seed if it has never received it.

## Department picker

The receiving internal-return and outgoing hospital-department forms now have a dropdown that opens to a **searchable menu**, with a text search box at the top. Names are filtered with normalized Arabic text (hamza/diacritics tolerant). Only an actual saved department ID can be submitted. Keyboard `ArrowDown`, `Enter` and `Escape` are supported. The Department Management page has a quick search filter.

## Tests

`python test_v49_regression.py`: verifies initial seeding, department rename persistence, manual addition, receipt lots with different prices, price overrides on outgoing movement only, over-issue rollback, product/lot mismatch rejection, internal returns, legacy outgoing clients, backup restore and `/api/health` release `4.9.0`.

Manually visually checked in an isolated browser (due to local network/navigation restrictions) with Arabic RTL layouts: six outgoing row fields; searchable department picker; returning route and adjustment tab; department management; mobile 412px layout with no horizontal overflow.

**Deployment**: update existing private GitHub repository, redeploy same Railway service and retain the same `/data` volume. Back up first.
