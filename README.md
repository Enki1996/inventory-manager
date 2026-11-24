# Hospital Warehouse IMS V4.3 — Fixed books per warehouse branch

**Arabic is the default language**. The Home, Login and Warehouse Dashboard retain the approved white/icy-blue/teal styling. The app uses a Python/FastAPI backend and a persistent SQLite database for controlled multi-user *testing*, including stock receiving, distribution, accounts, access permissions, audit history and backup/restore.

## New in V4.3

- Each item still belongs to **exactly one** of the three fixed warehouse branches: Medication, Medical Supplies, or Surgical Instruments.
- The **Book / Register Category** field is now a **required dropdown**, not free text. It shows only the official register names for the item's branch: 10 Medication books, 7 Medical Supplies books, and 2 Surgical Instruments books.
- A branch-restricted employee sees their assigned branch locked; admins may select any branch. Regardless of role, the server rejects a book not authorized for that branch (HTTP 422), even when the API is called directly.
- Changing the selected branch refreshes the book list and clears an incompatible choice. The Inventory page includes branch and dependent book filters, and its text search still searches the book name.
- Previous items, batches, stock, accounts, paper requisition references, movements, and audit history remain untouched. **Previously entered book text is never renamed automatically**. Items with old/free-text classifications remain visible and can still be issued/received; their book must be selected from the new list when the item itself is next edited. There is an in-form warning on such legacy values.
- The official names are maintained in one source file: [`book_catalog.py`](book_catalog.py). The frontend reads the mapping from the authenticated `/api/books` endpoint to avoid two drifting lists.
- **No database schema migration is required for V4.2 → V4.3**: the existing `items.category` column stores the selected approved title. Schema stays at version 3, and V4.2 database backups remain compatible.

See [`BRANCHES_AND_BOOKS_V4_3.md`](BRANCHES_AND_BOOKS_V4_3.md) for the exact approved titles and [`RAILWAY_SETUP.md`](RAILWAY_SETUP.md) for deploying to the existing private GitHub/Railway project.

## Run locally for testing

Run `pip install -r requirements.txt` and `uvicorn app:app --host 127.0.0.1 --port 8000`, or use the provided Windows/macOS startup script. Open http://127.0.0.1:8000 and log in as `enki / 123` **only in a disposable local test environment**. For an internet-accessible Railway instance, configure a *different strong admin password in private environment variables*. Never use `123` online.

## Update existing Railway testing deployment

1. In the running app, download a manual backup and keep it securely, as a precaution.
2. Replace the code files in your existing **private** GitHub repository with the contents of this ZIP. Do not upload a database file, downloaded backup, or `.env` secrets.
3. Allow Railway to redeploy; **do not delete or replace the existing persistent volume at `/data`**.
4. After the update, verify you can sign in and that previous items, stocks, movements and accounts are still present. Open Add Item and confirm that choosing a branch shows only its own books.
5. Review older items whose book categories were typed freely in V4.2; update them to an official book when convenient.

This is a testing build, not a clinically certified inventory service. App-generated backup ZIPs are not encrypted. Before real hospital use, add off-site automated backups, stronger security measures and a tested disaster-recovery plan. Do not use patient/confidential records during testing.

## Verification

Run `python test_books.py`, `python test_flow.py`, `python test_branches.py`, `python test_item_details.py`, and `python test_upgrade_from_v41.py`. All tests use temporary disposable databases rather than the live inventory database.
