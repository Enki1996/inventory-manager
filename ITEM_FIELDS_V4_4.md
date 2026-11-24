# V4.4 — Branch-specific Add Item layout

The order is intentionally **the actual tab/reading order**, not only visual CSS.

**Medication (الأدوية):**
1. Branch / الفرع
2. Trade name / الاسم التجاري (`items.trade_name`, required)
3. Scientific name / الاسم العلمي (`items.name`, required)
4. Unit / الوحدة (حب، كبسول، بطل، امبول، فيال، انبوب، تحاميل، قطرات)
5. Official book / السجل المعتمد (10 official medication books)
6. Batch number / الوجبة (`items.initial_batch_no`, required)
7. Expiration / تاريخ الصلاحية (`items.expiry_date`, required)
8. Manufacture date / تاريخ الإنتاج (optional)
9. Manufacturer / الشركة المصنعة (optional)
10. Information / names / معلومات / أسماء بديلة (optional)

**Medical supplies (المستلزمات الطبية):** Branch → Item name (`items.name`) → unit (قطعة، كيس، بطل، باكة، رولة، باكيت، درزن) → book (7 approved titles) → batch → required expiry → manufacture date → manufacturer → information. There is **no** scientific or trade name field.

**Surgical instruments (الأدوات الجراحية):** Same as medical supplies, but stock unit is **قطعة** only and the book list contains its 2 approved titles.

### Data modeling notes
- The catalog now has `trade_name` and `initial_batch_no` columns (additive migration; V4.3 records unchanged). The original `items.name` remains the scientific name for medications and the plain item name for other branches. Existing optional `generic_name` remains stored for older records but is no longer in the Add Item form.
- SKU still exists for links/history; for newly added items the server generates it if omitted. It is not an entry field, so Branch is the first field.
- New Add Item records a **zero-stock batch** with the batch number and expiry entered. Actual stock only increases via a received shipment movement. Editing a catalog record never rewrites the batch expiry of previously received items; if the reference batch number is new it adds another zero-stock batch.
- Existing legacy items may have no trade name, initial batch, or expiry. They remain unchanged during migration, but must be completed when edited. Historical English units remain usable **unchanged for existing records** only so older inventory operations and reclassification are not blocked; newly created items must use the exact approved Arabic unit strings.
- The backend checks the allowed unit per branch, expiry required, manufacture <= expiry, required names and batch, branch/book permissions, and immutability of the stock unit after movements. UI conditions alone are not security controls.
- The batch expiry used when receiving/shipping is always the **per-batch value**, not the catalog reference date. No existing movements are silently changed.
- Backups marked schema v1/v2/v3 migrate on restore. Schema version is 4; regular update requires only a code redeploy and the existing `/data` volume (plus a backup before deployment).
