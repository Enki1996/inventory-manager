# V4.12 — Annual requirements and flexible warehouse statements

## Item catalog

Field: **كمية الاحتياج السنوي** / Annual requirement quantity

- New nullable SQLite `items.annual_need` INTEGER, non-negative; annual quantity is expressed in the product's own registered stock unit.
- Field is included in Add/Edit Item and shown in the inventory table. Existing items have `NULL` (not entered); blank new entries also remain `NULL`.
- Edits preserve this field when omitted by an older client, or save an explicit blank as `NULL`.
- Create/update and backups include this value. Older database contents, batches, lot prices, and ledger movements remain intact.

## Near-expiry report

- Default: same calendar window as V4.11 — from the current Baghdad date to the **first day of the same month next year**, *exclusive*. For Nov 2026, the cutoff is **2027-12-01**; Nov 30, 2027 is included.
- Users can pick a different cutoff date using the date picker in **المواقف → موقف المواد قريبة النفاذ**. The *cutoff itself is not included*.
- A reset button returns to the original default.
- Already-expired lots are excluded and separately counted. Batches stay independent by expiry and price.

## Scarce and surplus positions

- The user enters a percentage on each report; no official percentage is hardcoded.
- Eligible products must have positive `annual_need`.
- Counted stock is the sum of lots with **known expiry on or after today**, to avoid treating expired or unverified stock as usable. Both unknown-expiry and expired lots are excluded from percentage calculations; physical quantities remain in the database unchanged.
- `percent = usable_remaining / annual_need * 100`.
- Scarce condition: `percent < scarce_threshold` (strictly below).
- Surplus condition: `percent > surplus_threshold` (strictly above).
- Example: yearly need 1,000 and usable stock 200 => 20%. Enter 25% for scarcity and it appears. Yearly need 1,000 and usable stock 1,500 => 150%. Enter 125% for surplus and it appears.
- The missing-materials report is unchanged: active items whose **total physically recorded** stock is zero, including items without receipts.
- All four statements remain authenticated and read-only. This update does not affect stock quantities or movement history.

## API

`GET /api/positions?expiry_before=2027-12-01&scarce_pct=25&surplus_pct=125`

All three query parameters are optional. `expiry_before` is a valid ISO date and is exclusive. Percentages must be >0 and <=1000 with up to two fractional decimal places. Without a percentage, its report returns no classification rather than assuming an official rule.

## Schema and compatibility

- `APP_RELEASE = 4.12.0`; SQLite `SCHEMA_VERSION = 8`.
- Additive migration checks for `items.annual_need`, adding it if missing, with no replacement of database files.
- V4.11 database migration and V4.11 backup import were tested; older data remains intact.
- No new hosting architecture. Keep the existing Railway `/data` volume and private repository.
