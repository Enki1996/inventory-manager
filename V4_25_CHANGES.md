# IMS V4.25 — Controlled Undo/Redo and neutral public pages

## Recovery: append-only stock movements

- **Movement History**: Administrators can undo an entire shipment or selected lines, after choosing the lines and providing a reason (at least 8 characters), their own password and the confirmation `UNDO`.
- **Audit Logs**: Ultra Administrator (`WAREHOUSE_ULTRA_ADMIN_USERNAME`, default `enki`) can perform the same Undo from eligible original movement audit entries, and Redo a completed Undo after entering a reason, password, and `REDO`.
- The system writes new `UNDO-...` and `REDO-...` **adjustment movement records** to the original lots, with matching movement lines and permanent, linked audit events. Original documents and movement lines are never deleted, replaced or hidden.
- Reversal status is tracked **per original movement line**, preventing a second active Undo of the same line. An entire shipment can be undone atomically (or not at all). Redo replays the group of lines in a single Undo movement atomically.
- Undo of an IN/RETURN/opening-positive line is rejected if later active outgoing movements depend on that lot, or if the quantity would make stock negative. Redo of any negative stock movement requires sufficient current stock; Redo of an OUT line also rejects expired stock. A previous failed Undo has no Redo.
- Controlled medicines in `سجل المخدرات` and `سجل المؤثرات العقلية` require Ultra Admin for Undo.
- **Physical returns must still use a proper return receipt**. Undo is for erroneous entries; it is not a substitute for actual physical returns.
- New edits of items, departments and staff permissions now include **before/after snapshots in their audit events**. Ultra Admin can undo or redo these eligible newer edits only if the record is still in the expected state; otherwise the action is blocked. Deleting items, creating accounts, credential resets and older audit edits without snapshots are **not automatically reversible**.
- Password confirmation and server-side role checks protect every recovery endpoint. Administrators can view audit history as before; only Ultra Admin may perform redo and audit-driven reversals.
- **Safety note**: This feature is designed for evaluation with synthetic data. Before operational use, test corrections against your real procedures, especially controlled drugs, physical custody and approvals.

## Schema and preservation

- SQLite schema **V10**, additive tables `movement_reversals`, `audit_field_reversals` plus an index blocking duplicate active Undo. Existing product, batch, movement, account and document records are preserved.
- Older V9 (and earlier supported) backup ZIPs are migrated during a restore. The existing Google Drive encrypted backup integration remains unchanged; the separate Railway cron service need not be redeployed.
- `GET /api/health` returns `release: 4.25.0`, `version: 10`.

## Home/legal pages

- Privacy Policy and Terms of Use now use neutral, general application language with **no draft badge** and **no attribution of legal obligations to a named hospital**. They do not imply that any deployment automatically complies with legal requirements. Operators must still determine applicable obligations.
- Font review: **Amine_mod** suits large Arabic headings; **banda** is reserved for very brief decorative hero/kicker text. **B-Arabic-Style-1** is not used due to poor fit for dense application text. Everyday labels and tables retain the readable base fonts.
- Font binaries are **not included in the package**. To activate optional heading fonts, copy your own `Amine_mod.ttf` and `banda.ttf` into `static/fonts/` in your private project before deployment. Keep this usage subject to the licenses for those fonts. The site has fallback fonts until supplied.

## Deployment

1. **Download a fresh database backup** from the currently running app and keep it securely outside Railway.
2. Extract the code ZIP and commit the source files to the **same private GitHub repository** as the current IMS app.
3. In Railway, redeploy the **existing service**, leaving its `/data` volume, environment variables, Google OAuth and secret keys intact. **Do not upload or restore a database file** merely to update the code.
4. Verify `/api/health`: `{"ok":true,"database":"sqlite","version":10,"release":"4.25.0"}`.
5. With synthetic data, try Undo of one shipment line and a whole shipment, then Redo from Audit Logs. Check stock, original history, linked audit entries, and access from a restricted role.
6. Check `/privacy.html`, `/terms.html`, Arabic/English switching, and headings (once your private font files are added).

Automated regression tests (existing suite + new recovery/audit tests) passed, an original V9 demo backup restored into schema V10, and the Undo/Redo dashboard interaction was checked in an isolated Chromium browser with backend requests passed through a test database. Live Railway was not modified or verified.
