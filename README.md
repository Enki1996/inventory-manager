# Hospital Warehouse IMS V4.2 — Three branches and book/register categories

This is the **Arabic-first bilingual** hospital warehouse test app with a real backend and SQLite database. The application includes Home, Login, Dashboard, Inventory, Department destinations, Incoming/Outgoing Shipments, Batches, Returns, Movement History, Accounts & Permissions, and portable Backup & Restore.

## New in V4.2

- Exactly three fixed branches: **Medication (الأدوية)**, **Medical Supplies (المستلزمات الطبية)**, **Surgical Instruments (الأدوات الجراحية)**.
- Every new item belongs to one fixed branch. Its independent **Book / Register Category (التصنيف حسب السجل)** is a flexible text field (e.g. **سجل الحياتية**) with suggestions and inventory search/filtering.
- When creating a staff account, an admin assigns exactly one branch to each non-admin employee. Admins have all-branch access.
- Add/Edit Item shows a disabled, fixed branch selector for staff. The server enforces the same restriction on item writes, incoming receipts, outgoing distributions, returns, and stock corrections.
- Existing V4.1 item details, Arabic/English language switching, movement history, batches, expiry dates, backup exports and restores remain in place.

Details and migration behavior: **[`BRANCHES_AND_BOOKS_V4_2.md`](BRANCHES_AND_BOOKS_V4_2.md)**. Arabic wording can be updated at `static/locales/ar.json`; see `TRANSLATIONS.md`.

## Run locally (demo only)

Extract the project. On Windows, double-click `run_windows.bat` with Python 3.11+ installed. For macOS/Linux run `./run_mac_linux.sh`. Alternatively run `pip install -r requirements.txt` and `uvicorn app:app --host 127.0.0.1 --port 8000`.

Open `http://127.0.0.1:8000`, log in as `enki / 123` **only for local demo testing**, then change the password. Do not use this password on a public Railway server. The application must be served by Python; double-clicking HTML files alone will not work.

## Testing workflow

1. Create a department destination (e.g. ER).
2. Create an item. Select Medication (or another branch) and enter a book category such as `سجل الحياتية`.
3. Receive a shipment with a paper reference, batch number and actual batch expiry.
4. Distribute part of the stock to a department using its paper requisition serial number.
5. Create a **Manager** account assigned to Medication; confirm it cannot edit or move Surgical Instruments.
6. Try filtering the inventory by branch and by book/register classification.
7. Download a full database backup to your PC or phone and keep it securely.

Data is stored in `data/warehouse.sqlite3` locally, or in `/data/warehouse.sqlite3` on Railway when a volume is attached. Never commit a live SQLite file to GitHub.

## Deployment and preservation

See **[`RAILWAY_SETUP.md`](RAILWAY_SETUP.md)** for private GitHub -> Railway instructions. Updating V4.1 to V4.2 changes the database **additively**, preserving items, movements, users and stock. Old items/staff must be assigned to a branch by the administrator before branch-restricted editing is possible. **Back up first and retain the existing Railway volume.**

The app currently uses one FastAPI worker and one SQLite database on a persistent volume, suitable only for controlled multi-user testing. Before real hospital use, strengthen the architecture, deploy operational backups off-site, audit permissions and recoveries, and complete security review. Database backup ZIPs are not encrypted.

## Developer verification

`python test_flow.py`, `python test_item_details.py`, `python test_branches.py`, `python test_upgrade_from_v41.py` verify stock operations, branch enforcement, migration and backup compatibility using temporary databases. They don't change your actual warehouse database.
