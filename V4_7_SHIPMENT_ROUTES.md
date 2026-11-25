# Hospital Warehouse IMS — V4.7: Incoming and Outgoing Routes

This is an **additive update to the existing Railway app**, not a new service or database. Arabic remains the default language; English is available in every screen. The three warehouse branches, official register/book lists, item prices in dinar/fils, batch/expiry controls, and existing user permissions are unchanged.

## تجهيز طلبية — OUT (three routes)

1. **تجهيز أقسام المستشفى** (`department_issue`): Choose one of the active hospital departments; normally require **رقم ورقة الطلبية** and **رقم ورقة التجهيز**. For an actual emergency issue, select **تجهيز طارئ — استكمال الأوراق لاحقاً**. The paper numbers then become temporarily optional, but a permanent OUT movement is created and available stock is reduced immediately. It appears in Movement History and in a dedicated **Emergency shipments awaiting documents** panel. Authorized staff use **استكمال الأوراق الناقصة** to fill *both* numbers later. This action updates only the paper references and records a separate audit event; it never deducts stock a second time.
2. **مناقلات خارجية** (`external_transfer_out`): Enter the receiving hospital/organization name and the transfer order number. Select **الصيدلي المعتمد** from active employee accounts. No internal department is selected.
3. **مناقلات الى قسم الصيدلة** (`pharmacy_transfer_out`): Fixed receiving destination **قسم الصيدلة**. Enter the transfer order number and select an active registered account as the trusted pharmacist. No manual destination field.

All OUT routes issue selected batches atomically, enforce branch permissions, block expired batches and insufficient stock, and keep movement history and per-unit price snapshots.

## استلام شحنة واردة — IN (four routes)

1. **قسم الصيدلة** (`pharmacy_receipt`): Fixed source **قسم الصيدلة**, plus receipt/order paper number, line items with batches, expiry and quantities.
2. **مشتريات** (`purchase_receipt`): Drugstore/distributor name plus receipt number, line items with batches, expiry and quantities.
3. **مناقلات خارجية** (`external_transfer_in`): Sending hospital/external sector, transfer order number, trusted pharmacist chosen from active accounts, and received batches.
4. **إرجاع طلبية داخلية** (`internal_return`): Choose the original hospital department, record original requisition reference and warehouse return receipt number, then select *existing batches* and returned quantities. This creates a RETURN movement, adding those quantities back to the central warehouse. It does not create an independent department stock ledger.

The prior separate Returns & Adjustments screen continues to support the same internal return and manager-only adjustments. In the receiving page, switching to internal return changes batch lines to the existing-batch selector; switching back returns to incoming-batch entry. Be sure to re-enter any in-progress line items when switching route.

## Database change — schema 5 → 6

The migration adds the following *nullable or defaulted* columns to `movements` without changing historical quantities:

- `route` — explicit shipment route; older records remain `NULL` (legacy) rather than guessing their type.
- `trusted_pharmacist_id` — foreign key to an account in `users`, preserving staff identity.
- `paperwork_pending` — Boolean emergency marker (default false).
- `paperwork_completed_at` and `paperwork_completed_by` — audit metadata.

The previous paper fields `paper_ref` and `dispatch_ref` remain separate, and both are used for department distributions and returns. The existing `external_destination` supports external transfers and the fixed Pharmacy Department destination. An authenticated `/api/staff-directory` endpoint returns only active staff names, usernames, IDs, and branch labels—not password hashes or sessions.

`/api/health` must report `"release":"4.7.0"` and `"version":6` after deployment.

Old V4.6 backups are accepted and migrated on restore. V4.7 exports contain schema version 6. **Restore replaces the entire database:** it is unrelated to routine GitHub code updates. Do not restore backups just to update the website.

## Safe redeployment to Railway

1. While the existing live app is available, **export a database backup** and store it privately.
2. Unzip V4.7 and copy its contents into the **same private GitHub repository root**, replacing the previous code files; do not upload the ZIP or any `.sqlite3` files.
3. Railway redeploys the **same service**. Keep the existing `/data` volume attached and the same `WAREHOUSE_DATA_DIR=/data` variable; never delete or reattach the volume merely to update the code.
4. Open `https://YOUR-DOMAIN/api/health` and confirm release `4.7.0` and schema `6`.
5. Sign in, confirm old stock and history, then test all seven routes with fictitious data. Validate that pending emergency papers can be completed once, and that the item stock is unchanged by that completion.

### Test environment limitations

This is a collaborative **test** build, not a production-certified medical inventory system. Full operational review, audited security, backup encryption, scheduled off-site backups, and formal data reconciliation are still needed before clinical usage. The current internal-return workflow records a supplied original requisition number but does **not yet** enforce that returned quantity is less than or equal to the quantity originally issued on that particular requisition; this reconciliation can be added later. Trusted pharmacist selection checks for an active account but does not verify pharmacy professional qualifications independently.
