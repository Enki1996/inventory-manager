# V4.8 changes and data model

## 1. Transfer pharmacist and authorization

Applies to the **incoming external transfer** and both **outgoing transfer** routes:

- **اسم الصيدلي المخوّل** / Trusted pharmacist name: required free-text field, up to 160 characters. It can be someone external to the hospital who has no IMS account.
- **رقم كتاب التخويل** / Authorization letter number: required text field, up to 90 characters.
- Both are stored directly in the `movements` table (`trusted_pharmacist_name`, `authorization_ref`). Legacy `trusted_pharmacist_id` is kept to preserve older records and is no longer used for new transfer submissions.
- Both are recorded in movement history and audit details. Their presence records the details provided by staff; it **does not independently validate** external pharmacist identity or authorization.

The other four routes and emergency paperwork follow the prior V4.7 behavior.

## 2. Prices at receiving

Every new incoming product row has:

- **السعر — دينار** (`price_dinars`)
- **السعر — فلس** (`price_fils_component`, 0–999)

One dinar = 1,000 fils. Money is stored as exact integer fils, not floating-point numbers.

An **item** still has a catalog reference price (`items.price_fils`), which serves as a suggested initial price. Each **batch lot** now also has `batches.unit_price_fils`, and each received/issued **movement line** retains a frozen price snapshot (`movement_lines.unit_price_fils`).

The unique batch-lot key is now **(item ID, batch number, expiration date, unit price)**. Thus the database supports:

- several different batch numbers for one product;
- several expiration dates, even when batch number is the same;
- several prices, even when batch number and expiration date are the same.

Selecting a lot for outgoing shipments also displays its saved price; stock is deducted from the selected lot only. Changing the item catalog price does **not** retroactively change those receipts or lot balances.

Two receipts with *identical* product, batch, expiry and price merge into the same stock lot, while retaining separate incoming movement records. Each incoming movement is fully auditable.

A new item initially creates one zero-stock lot for its first batch. Registering the item is **not** itself a stock receipt.

## 3. Department entry

The Add/Edit Department dialog asks for **name only**. The API generates an internal unique code for new departments (e.g. `DEP-000012`) to keep old database compatibility; existing department codes remain unchanged on edits. The warehouse staff do not need to enter or manage codes.

## 4. Safe migration and backup behavior

V4.8 uses **SQLite schema version 7**. An additive migration creates new movement metadata and per-lot price column, replaces the old unique batch index with the new lot uniqueness index, and keeps all existing rows, quantities, and movement history.

Older records before V4.8 cannot be separated retroactively by historic purchase prices if their stock was already pooled. Existing stock lots are assigned the *current item reference price at migration* where known; this is a legacy approximation, **not verified historic acquisition cost**. Existing movement price snapshots remain unchanged.

Backups exported from schema V1–V7 are accepted by the restore routine, validated for integrity and relationships, and upgraded as needed. Always export a backup before deploying database migrations or testing restoration.

## 5. Verification checklist

- `/api/health` returns `release: 4.8.0`, `version: 7`.
- Add a department by entering its name alone; confirm it appears in shipment selectors.
- External IN and OUT routes show text pharmacist + authorization-letter inputs; no pharmacist drop-down.
- Pharmacy OUT route shows the same fields.
- Receiving lines show two price fields alongside the batch, expiry and quantity.
- Receive the same item at two prices and dates, then check **Batches & Expiry** for separate lot rows and their amounts.
- Issue one lot and check the movement's recorded price; editing the item reference price must not change historic figures.
- Export a backup and verify the same records can be restored in a separate test deployment.

Automated backend regression suite: `python test_v48_regression.py`.
