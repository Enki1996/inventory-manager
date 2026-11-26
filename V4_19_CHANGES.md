# V4.19 — Numbered lists and two-stage item details

Updated from V4.18 without changing the SQLite database schema (V9).

1. Inventory and warehouse statements show a sequential `#` column starting at 1, recalculated after filters and sorting. The **حركة المواد** item list also numbers its visible rows starting at 1. Within each movement record **and** item/department shipment history popup, product lines are numbered for easier reading. The all-lots subtable was already numbered and remains so.
2. The row chevron appears when the item has more than one stored lot. Clicking it displays the lots table **only**, with each lot's batch, manufacturing date, expiry, quantity, price, and status.
3. A second chevron labeled **Full item information & movement history** reveals the reference details and paginated history; it starts closed every time the main row is opened. Clicking the first chevron again closes everything.
4. Removed the redundant **View lots / Hide lots** button in the lot-count column. For items with one or zero stored lots, users may click the item name to inspect its details without an unnecessary first-level chevron.
5. This is a presentation-only update. No database migration, no quantity changes, and no new tables.

**Deployment:** Back up the database from the admin dashboard, replace the source code in the same private GitHub repository, and redeploy the existing Railway service with the `/data` volume still attached. Check `/api/health` returns `release: 4.19.0` and `version: 9`. Hard-refresh the browser if cached assets persist.

**Validation:** Ran the existing 10 test scripts individually (they use isolated databases) and a JavaScript DOM-output structure check. Local Chromium could not access the test server or inject the isolated preview's CSS due to its administrator restrictions; manual visual verification on the live test site remains necessary.
