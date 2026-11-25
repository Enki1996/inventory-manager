# Hospital Warehouse IMS — V4.11 المواقف

This version extends V4.10. **No SQLite schema migration is required** (schema remains version 7). The new `/api/positions` endpoint is read-only and requires an authenticated session.

## New dashboard navigation tab

**المواقف / Warehouse Statements** contains four buttons:

- **موقف المواد الشحيحة** — visible, disabled. No calculation defined yet.
- **موقف المواد المفقودة** — working report of all *active catalog items* with zero total warehouse balance. Items with no batches are included. This is not the same as low-stock threshold.
- **موقف المواد الفائضة** — visible, disabled. No calculation defined yet.
- **موقف المواد قريبة النفاذ** — working batch/lot-level report of currently available (>0) stock expiring soon. Separate lots with different batch references, expiry dates, prices, and quantities are preserved and shown independently.

## Expiry window

To match the explicit example, the expiry report includes stock that expires from **today in Asia/Baghdad** through the **last calendar day of the current month next year** (inclusive). E.g. on 25 November 2026 the report includes expiry dates from 2026-11-25 through 2027-11-30, but not December 2027.

Expired batches are not included in near expiry; they are counted in a **separate warning**, and remain blocked from ordinary outgoing issues by the existing FEFO safeguards. Batches without an expiry date are not included. These reports do not alter stock.

## Filtering and permissions

Search by item name, generic name, alternate/slang name, SKU, book/register and lot number, or select warehouse branch. Accessible by signed-in accounts with the same read visibility as Inventory. No write operation or permission change was added.

## Upgrading on Railway

1. Export a full database backup and keep a copy offline.
2. Upload the extracted V4.11 source files to your existing private GitHub repository and deploy the same Railway service.
3. Keep your **existing** persistent `/data` volume attached; do not create a fresh database.
4. Check `https://YOUR-DOMAIN/api/health` returns `"release":"4.11.0"` and `"version":7`.
5. Sign in and open **المواقف**. The scarce and surplus buttons are intentionally disabled until their rules are provided.

**Important:** This is a testing-stage application; do not use live clinical stock records until operational/security review and verified backup/restore drills are complete.
