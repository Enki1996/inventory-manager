# Add / Edit Item — V4.3

## Fields

| English interface | Arabic interface | Database column |
|---|---|---|
| Product code / SKU | رمز الصنف | `items.sku` |
| Scientific item name (previous item name) | الاسم العلمي للصنف | `items.name` |
| Generic name | الاسم الجنيس / العام | `items.generic_name` |
| Manufacturer company | الشركة المصنّعة | `items.manufacturer` |
| Warehouse branch (fixed) | فرع المخزن | `items.branch` |
| Book / Register Category | التصنيف حسب السجل أو الدفتر | `items.category` (approved branch-specific dropdown) |
| Stock unit | وحدة المخزون | `items.unit` |
| Manufacture date (optional) | تاريخ التصنيع (اختياري) | `items.manufacture_date` |
| Expiration date (optional) | تاريخ انتهاء الصلاحية (اختياري) | `items.expiry_date` |
| Information / alternate names | معلومات وأسماء أخرى متداولة | `items.information` |

`name` remains the existing database field: previous item names and links to receipt/issue history are not changed. New optional text fields default to empty; optional dates default to null. Manufacture date cannot be later than expiration date if both are provided. The information field supports up to 2000 characters and accepts any mix of comma/newline-separated alternative names, local slang, search keywords and notes. Inventory search checks the SKU, scientific name, generic name, manufacturer, category, and the full information text (with Arabic diacritic/hamza normalization), and global search routes to the inventory search.

**Low-stock threshold:** Removed from Add/Edit Item UI as requested. Newly created items use the existing database default of zero. Historic thresholds are retained, so older low-stock reports and alerts still behave as before.

**Important batch rule:** The catalog expiration and manufacturing dates are *reference metadata* only. Every incoming shipment line still registers the batch number and batch-specific expiration date independently. Distribution blocks expired lots based on `batches.expiry_date`, never on `items.expiry_date`. Editing reference dates does not edit batches, warehouse balance, or movement history.

**Updates:** V4 uses schema version 1; V4.1 uses schema version 2; V4.2 and V4.3 use schema version 3. At startup, `migrate_item_details` adds older missing columns as needed. V4.3 introduces no new database columns and validates the Book / Register Category against the official branch list in `book_catalog.py`. Older compatible database backups can be uploaded to the V4.3 Restore screen and are migrated during restoration. Fresh V4.3 backups include the new fields and branch assignments.

**Deployment:** Extract the ZIP to a private GitHub repository's root and let Railway deploy; keep existing Railway persistent `/data` volume. Never commit a real SQLite database, passwords, or sensitive exported backup files.

**Book dropdown:** V4.3 replaces the arbitrary text field with the 19 approved books grouped by the three warehouse branches. Existing item categories are not overwritten; choose an approved book when editing old items. See `BRANCHES_AND_BOOKS_V4_3.md`.
