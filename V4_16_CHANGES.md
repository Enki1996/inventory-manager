# V4.16 — رصيد افتتاحي (Opening Stock)

## Add new item — two paths

1. **Default: no opening balance.** The Add Item form displays the usual branch, names, unit, approved book, manufacture date, manufacturer, annual need, and alternative names. It hides batch/lot number, expiration date, unit price and quantity. The database creates the catalog record with a zero stock balance **and no new stock lot or movement**. Those values can be recorded later via an incoming shipment.
2. **Tick رصيد افتتاحي.** The checkbox reveals five required fields: opening quantity, batch number, expiration date, price in dinars, and price in fils. The backend validates positive integer quantity, the branch/book/unit rules, a supplied lot/expiry, and 0–999 fils. It atomically creates an item, a priced stock lot with the opening balance, an `OPEN-######` movement record, and an audit record. This does *not* require a fictitious incoming receipt. It remains visible in stock history and downloadable database backups.

## Accounting and history

The existing schema V8 does not support an additional movement-kind enum without a table rebuild. To protect production data, an opening balance is stored as an `ADJUST_PLUS` movement with an unambiguous `route='opening_balance'`, reference `OPENING-BALANCE`, a unique code `OPEN-######`, and action `OPENING_BALANCE_CREATED` in the audit log. The interface displays it as **رصيد افتتاحي / Opening balance**, not a supplier receipt. It is added exactly once in the item-creation transaction.

Editing product reference information never overwrites a historical lot or its movement price. New received batches continue using the existing receiving workflow, including their own expiry dates and prices. A new product registered as part of an outgoing shipment can immediately be selected if its opening balance has been created; otherwise it still requires a documented receipt.

## Deployment

- **Schema:** V8 (unchanged)
- **App release:** `4.16.0` at `/api/health`
- **Upgrade:** push the extracted files to the same private GitHub repository, redeploy the existing Railway service, retain its existing `/data` volume, and never upload a demo `.sqlite3` file with code.
- **Safety:** export a backup before deploying; do not restore a backup for this UI/API update. Confirm accounts, balances, and movements after redeployment.
- **Verification:** open **المخزون → صنف جديد**; the opening stock fields must remain hidden until the checkbox is selected. Add one catalog-only item and one opening-balance item; confirm the former has zero stock and the latter has a uniquely recorded `OPEN-` movement.

## Tests

```
python test_v416_opening.py
python test_v415_monthly.py
python test_v414_release.py
python test_v413_details.py
python test_v412_regression.py
python test_v412_fefo.py
python test_v412.py
```

These tests create isolated temporary local databases. A separate isolated browser/component check verified the checked/unchecked form layout at desktop and mobile sizes, but a live Railway browser walkthrough has not been performed.
