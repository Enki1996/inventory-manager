# Hospital Warehouse IMS V4.8 — Shipment prices, authorization & departments

This is the complete source for the **existing** one-warehouse Railway test application (Home, Login, Dashboard, FastAPI backend, SQLite, and Arabic-first bilingual UI). It is an **incremental replacement for V4.7**, not a new database or a second service.

## New in V4.8

- **Incoming external transfers and outgoing external/pharmacy transfers:** Enter the **trusted pharmacist's name** as free text, including people who don't have staff accounts; additionally enter **رقم كتاب التخويل** (authorization letter number). Both are required for these transfers, recorded in movement history, and included in backups. Department issues and ordinary receipts do not require them.
- **Received item lines:** Enter **دينار** and **فلس** for each incoming line, independently of the catalog reference price. A new receipt can have a different price than earlier receipts of the same product.
- **Independent inventory lots:** One item may have many stored rows with different batch numbers, expiry dates, and unit prices. Stock is tracked by lot. Issuing a batch captures its stored lot price in movement history. Other lot prices don't change when the catalog price changes.
- **Departments:** Adding or editing requires only **the department name**. A code is generated automatically for new departments as an internal database key; previous department codes remain intact but no longer appear in the form.
- **Arabic and English:** Arabic remains the default. The light visual theme and the three outgoing / four incoming routes remain.

See [V4_8_CHANGES.md](V4_8_CHANGES.md) for database details and test instructions.

## Deployment to the existing Railway app

1. Export a backup of the current database through **Backup & Restore** (the download contains sensitive data and password hashes; keep it private).
2. Confirm your existing Railway service has a persistent volume mounted at `/data`, and `WAREHOUSE_DATA_DIR=/data`.
3. Extract this ZIP and replace the **source code** in your existing private GitHub repository. Do **not** upload or replace SQLite files, backups, your Railway volume, or secret variables.
4. Redeploy the **same Railway service**, with one replica and worker.
5. Open `https://your-app-domain/api/health` and confirm `"version":7,"release":"4.8.0"`.
6. Check that previously saved items, batches, incoming/outgoing movements, and departments remain unchanged. Test a dummy receipt at different price/expiry, an external transfer with outside pharmacist, and adding a department by name.

The database migrates automatically when the new version starts. Older V4.7 data remains in the persistent SQLite database, and the new columns/index are added without erasing historic movements.

**Important historical data limitation:** Earlier receipt rows already recorded a movement price snapshot, which remains unchanged. Existing legacy batch balances are initialized with the item's last saved catalog price *where known*, because the old schema did not track balances separately by receipt price. That inferred price cannot recover any forgotten original purchase prices. New receipts are accurately differentiated after V4.8.

## Local testing

```bash
pip install -r requirements.txt
python test_v48_regression.py
uvicorn app:app --host 127.0.0.1 --port 8000
```

Local test-only initial credentials are `enki` / `123`. **Do not deploy these credentials on the public internet.** The Railway app requires a secure admin bootstrap password stored privately in Railway variables; do not place credentials into GitHub.

Arabic interface strings: `static/locales/ar.json`.

This is an early collaborative warehouse **testing** build. Do not enter confidential hospital or patient data or depend on it for real clinical operations until security and operational validation are completed. The downloadable ZIP database backup is not encrypted.
