# V4.5 — exact Add Item form and new Medication register

**This version changes code only, not the existing database structure.** It does not reset inventory, batches, departments, users, or movement history.

## What to expect

- **Branch is always the first field.** Staff see their own assigned branch locked; admins can choose.
- **Medication:** Branch → Trade name (الاسم التجاري) → Scientific name (الاسم العلمي) → Unit (الوحدة) → Official book (السجل المعتمد) → Batch (الوجبة) → **Required** expiry (تاريخ الصلاحية) → Manufacture date (تاريخ الإنتاج) → Manufacturer (الشركة المصنعة) → Information/alternate names.
- **Medical Supplies and Surgical Instruments:** same order, but only Item name (اسم المادة), no Trade/Scientific-name pair.
- Units are dropdowns: Medication **حب، كبسول، بطل، امبول، فيال، انبوب، تحاميل، قطرات**; Medical Supplies **قطعة، كيس، بطل، باكة، رولة، باكيت، درزن**; Surgical Instruments **قطعة** only.
- Books are branch-specific required dropdowns: 11 Medication, 7 Medical Supplies, 2 Surgical Instruments.
- Added under Medication: **سجل المغذيات - قسم الصيدلة**.
- SKU/product code is generated automatically and not displayed as an Add Item input.
- New item records have zero quantity until an actual received shipment is recorded. Received batches maintain their own actual expiry dates.
- Old data survives. Existing legacy unit values remain untouched when editing an old item; new items must use the approved dropdown values.

## Deploy safely to the same Railway project

1. From the existing app, **Settings → Backup & Restore**, download a full backup first (for precaution).
2. **Do not delete or replace the Railway volume.** If your app uses `/data`, keep the same volume attached to the same Railway service.
3. Extract the ZIP **on your PC**. Upload/commit **the contents** at the root of your *existing private GitHub repository*: `app.py`, `book_catalog.py`, `unit_catalog.py`, `static/`, `requirements.txt`, `railway.json`, etc. Do not upload the ZIP as the only repository file, and do not accidentally put the project in an extra nested folder.
4. Deploy that same GitHub repository's newest commit in the same Railway service. Confirm Railway says **Success**.
5. Open `https://YOUR-RAILWAY-SITE/api/health` in a browser. You should see `"release":"4.5.0"`. `"version":4` is the SQLite **schema** version and is expected; it is not the app release.
6. Return to the dashboard, press **Ctrl+Shift+R** (hard refresh), then **Inventory → Add Item**. The modal title will contain **V4.5**. First input: **Warehouse branch**. It must not show a Product code/SKU input.
7. Test the three branches and their unit/book dropdowns. Do not use real patient records in the testing environment.

## If you still see the old field order from the screenshot

- If `/api/health` doesn't show `"release":"4.5.0"`, Railway is running an old commit, a different service/repository/branch, or an incorrectly nested upload. Check the Railway deployment source and deployment commit.
- If health says 4.5.0 but the modal doesn't show **V4.5**, try a hard refresh or a private browsing tab, then check the browser Network tab for `/static/live.js?v=4.5.0`.
- Keep any existing database volume intact while investigating. A code update must not require wiping `/data`.
