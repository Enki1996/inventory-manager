# Hospital Warehouse IMS V4.4 — Arabic-first, branch-specific Add Item forms

This is a **shared testing application** for a single hospital warehouse. It contains a FastAPI server, SQLite database, login and permission checks, home/login/dashboard UI, receiving/issuing/returns, movement and requisition history, branch-specific books, and backup/restore. The default language is Arabic, with an English switch. The approved white / icy-blue / teal design is unchanged.

## New in V4.4

The **first field is Warehouse Branch**. The rest of the Add/Edit Item form changes dynamically:

- **Medication**: Branch → Trade name (الاسم التجاري) → Scientific name (الاسم العلمي) → Unit (حب / كبسول / بطل / امبول / فيال / انبوب / تحاميل / قطرات) → Book → Batch number (الوجبة) → **Expiry (required)** → Manufacture date → Manufacturer → Information / alternate names.
- **Medical supplies**: Branch → Item name → Unit (قطعة / كيس / بطل / باكة / رولة / باكيت / درزن) → Book → Batch number → **Expiry (required)** → Manufacture date → Manufacturer → Information / alternate names.
- **Surgical instruments**: Same as supplies, with the **single unit قطعة** and only this branch's two approved books.

Branch and Book still enforce the V4.3 categories and V4.2 employee branch restrictions on the server. Each new item receives an **automatically generated SKU** rather than requiring the clerk to type a product code.

The batch number entered in Add Item creates a **zero-stock registered batch** (not a receipt); stock quantities change only when staff record incoming/outgoing shipments. The original batch expiry of existing movements is never silently overwritten. The Catalog's reference expiry is required for new items but independent from the actual per-batch expiry used to issue stock.

See [ITEM_FIELDS_V4_4.md](ITEM_FIELDS_V4_4.md) for implementation detail, schema compatibility, and all unit lists. The allowed units live in `unit_catalog.py`, official books in `book_catalog.py`, and editable Arabic UI strings in `static/locales/ar.json`.

## Deployment and preserving data

1. **Before changing code**, download a database backup from the running app and store it securely.
2. Extract the ZIP and update the **same private GitHub repository** with the files, not the ZIP archive itself.
3. Redeploy the **same Railway service** with its existing persistent `/data` volume and `WAREHOUSE_DATA_DIR=/data` unchanged. Never replace or detach that volume just to update code.
4. V4.4 safely adds two columns (`trade_name`, `initial_batch_no`) when the server starts; existing items, batches, departments, staff accounts, and movements remain in place. Previously registered items are *not* guessed or renamed; when edited, missing mandatory fields will need to be supplied.
5. After deployment, sign in, check existing stock and users, and create a **dummy** item under each branch to verify the new form before real data entry.

See [RAILWAY_SETUP.md](RAILWAY_SETUP.md) for first-time deployment details. Do not commit `.env`, `warehouse.sqlite3`, `/data`, or backup ZIPs to GitHub.

## Running locally

`pip install -r requirements.txt` then `uvicorn app:app --host 127.0.0.1 --port 8000`, and open `http://127.0.0.1:8000`. The **local demonstration only** creates the testing login `enki / 123`; public deployment **must** use a strong secret through `WAREHOUSE_BOOTSTRAP_ADMIN_PASSWORD`. Never expose `123` online.

## Automated regression tests

Run from this folder:

```sh
python test_v44_item_form.py
python test_flow.py
python test_books.py
python test_branches.py
python test_item_details.py
python test_upgrade_from_v41.py
```

All automated tests use temporary databases. This build is for collaborative testing, **not production hospital inventory**: backups currently are not encrypted and automated off-site recovery and operational security still need hardening. No patient-identifying data should be entered for testing.
