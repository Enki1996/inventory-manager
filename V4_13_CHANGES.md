# V4.13 — Detailed inventory & statements

- Inventory and Batches & Expiry are combined in one Inventory tab; old `#batches` URLs redirect to Inventory.
- Inventory defaults to **available, unexpired dated** stock. Other options: zero stock, items with expired stock, stock lacking an expiry date, and all records. Inactive products can be displayed optionally.
- Product tables support search (including batches/aliases), branch and book filters, sorting, and show/hide columns (settings stored only in the local browser).
- Expand a product to inspect all catalog fields and **every current stock lot**, including zero-stock/expired lots, batch numbers, expiry dates, and individual lot prices.
- Read full recorded movements via the **authenticated, read-only, paginated** `/api/items/{item_id}/history?limit=50&offset=0` endpoint. Unlike the dashboard's last-500 movements list, it can retrieve the full saved movement-line history in pages.
- All four مواقف reports now display detailed grouped item rows with column toggles; near-expiry report groups matching lots under their product and allows expanding to inspect its other lots.
- No database migration: SQLite schema remains V8, and historical records and existing accounts are unchanged.
- Column hiding is only a presentation control and does not restrict the user's authorization to see those fields.
- This release is a code-only update. Deploy on the same Railway service, retaining the /data persistent volume. Back up the database first.
- Verify `/api/health` reports release `4.13.0`, schema `8`.
