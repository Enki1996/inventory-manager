# V4.14 – Interface fixes (no database migration)

- Replaced the broken inline Show / hide columns dropdown with a responsive, searchable, accessible centered dialog, selection controls and Apply/Cancel. Settings remain per browser; the item-name column stays visible.
- Explicit Show lots / Hide lots buttons next to each product's stored lot count. Expand rows to see ALL batches first (lot ID, batch number, expiry, remaining quantity, unit price, status), then all catalog fields and complete paginated movement history. Includes zero-balance and expired lots. This is a read-only presentation change.
- History badges renamed **Warehouse intake / إدخال مخزني** (light green) and **Warehouse dispatch / إخراج مخزني** (light red). Returns and adjustments retain distinct meanings and colors.
- Removed the note below the Incoming Shipment form that explained internal returns. No other warning or FEFO safeguards have changed.
- Arabic remains the default, with English switch; labels are editable under static/locales/ar.json.
- SQLite **schema remains V8**; release `/api/health` is **4.14.0**. No database files in the ZIP.

## Safe upgrade

1. Download a complete database backup first.
2. Replace SOURCE files only in the existing private GitHub repository (do not upload a database file).
3. Redeploy the same Railway service with the existing `/data` volume attached.
4. Verify `/api/health` shows `release: 4.14.0` and `version: 8`.
5. Hard refresh the browser (Ctrl+Shift+R) if it still displays old assets.

Do not restore this ZIP through the app's Backup & Restore screen: it is source code, not a database snapshot.
