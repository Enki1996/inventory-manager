# Hospital Warehouse IMS V4.26 — Pagination & Recovery Color Update

1. Undo and Redo buttons and correction badges now use distinct lavender and peach palettes, separate from stock intake/dispatch indicators. The recovery validation and permissions are unchanged.
2. Inventory, Item Movement, Departments, Users, Reports, Movement History and Audit Logs use 20 / 50 / 100-row pagination, previous/next and number controls.
3. Movement History and Audit Logs have secure server-side paging endpoints so older records beyond the previous 500/300 caps remain reachable; full movement document lines are retained.
4. Shipment history popups and per-product movement ledgers page in place, preserving search and filter context.
5. **المواقف** remains a full, unpaginated table for all reports.
6. Existing database Schema V10, user accounts, backup/restore, FEFO, Undo/Redo and Google Drive integration preserved. No database reset.
