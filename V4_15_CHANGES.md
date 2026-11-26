# Hospital Warehouse IMS V4.15 — Monthly need statements

## Calculation rules (موقف المواد الشحيحة / موقف المواد الفائضة)

The registered **كمية الاحتياج السنوي** stays on each item, unchanged.
For each eligible item:

- `monthly_need = annual_need / 12`
- `stock_percent_of_monthly_need = (usable_warehouse_stock / monthly_need) × 100`
- **موقف المواد الشحيحة:** usable stock **strictly below 20%** of monthly need by default (`scarce_pct=20`).
- **موقف المواد الفائضة:** usable stock **strictly above 120%** of monthly need by default (`surplus_pct=120`).
- Both thresholds can be changed independently in the report, and reset to the defaults with **استعادة النسبة الافتراضية**. User-custom values are per current browser session/report interaction, not permanent company-wide policy.
- Exactly 20% does *not* count as scarce; exactly 120% does *not* count as surplus.
- This release interprets the requested 120% threshold as **120% of monthly need (1.2×)**, not 120% *above* monthly need (2.2×).

### Example
Annual need = 1,200 vials; monthly need = 100 vials.

| Usable stock | % of monthly need | Result at defaults |
|---:|---:|---|
| 19 | 19% | Scarce |
| 20 | 20% | Neither (boundary) |
| 100 | 100% | Neither |
| 120 | 120% | Neither (boundary) |
| 121 | 121% | Surplus |

**Usable stock** means remaining units from dated, unexpired lots. Expired lots and lots without an expiry date are not counted in these two statements. They remain visible elsewhere in Inventory. An item without a positive annual need is excluded from scarce/surplus and included in the "requirement not entered" count. Zero usable stock **is** scarce if the annual need is positive; missing (zero physical stock) is separately available under موقف المواد المفقودة.

## Interface

- Scarce and surplus cards show their matching counts and active percentages.
- The report input uses **النسبة من الاحتياج الشهري (%)**, defaults to 20 / 120, and permits a temporary custom percentage (positive, max 1000, two decimal places) with a reset button.
- Tables now offer the **الاحتياج الشهري** and **نسبة الاحتياج الشهري** columns in the Show/Hide Columns dialog, in addition to the existing annual requirement. Expand item rows to view per-lot expiry, amounts, and prices.
- All other المواقف and all existing inventory, shipment and FEFO operations are unchanged.

## Database / deployment

- **SQLite schema remains 8.** There is no migration, database replacement, or stock modification in this release. Monthly need is *derived* from stored annual need (not stored as another editable field).
- `/api/health` reports `release: 4.15.0`, `version: 8`.
- To deploy: backup your current live data, update your existing private GitHub repository with extracted source files, redeploy the same Railway service, and keep `/data` connected. Do **not** upload a demo restore backup for a code update.

## Validation

Tests include default 20/120 thresholds, custom overrides, strict boundary values, fractional monthly requirements, missing annual needs, expired-but-physically-present lots, existing inventory/FEFO/shipments, and restore compatibility. The browser environment blocked local navigation, so visual inspection on the live Railway app remains necessary.
