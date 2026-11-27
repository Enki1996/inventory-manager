# IMS V4.27 — Print & Report Designer (تصميم وطباعة المواقف)

## What is new

- **All four المواقف:** each detailed statement now includes **Design & print statement / تصميم وطباعة الموقف**.
- The print designer opens as a **separate authenticated, read-only page** (`/print-report.html`) and imports the currently selected report, search text, branch, register/book, sorting, expiry cutoff, and monthly-need percentage threshold.
- **Complete report, not current screen:** prints every record matching those conditions, without paginating the source report UI (المواقف stays one uninterrupted report).
- Select printed columns from 20 existing item/lot fields. A sequential row number is fixed; other columns are optional. Supports Select All, Defaults and Compact choices.
- Switch A4 portrait/landscape; show **individual qualifying lots** (own batch, manufacturing date, expiry, remaining quantity and price) or **one summary row per item**.
- Live Arabic-first A4 page preview, optional logo, filters and signature line; separate PDF/print action opens the browser print dialog (choose **Save as PDF** to download a PDF).
- Printed pages have repeated table headers, an IMS report heading, data-as-of date, filter summary, responsible operator, and page numbers.
- Existing Arabic/English language support is retained; the designer can switch languages without changing inventory data.

## Important report rules

- **Near expiry:** detailed mode prints *only* lots satisfying the current expiry cutoff and current balance rules, never every unrelated lot merely because it belongs to the same item. Expired lots are excluded as in the live report.
- **Scarce/surplus:** comparison uses usable, dated stock against **annual need ÷ 12** and the current selected percentage. The report uses the same authenticated `/api/positions` calculation as the existing المواقف view.
- **Missing:** registered items with zero stock remain visible even if they have no physical stock lots.
- **Summary mode:** shows matching report quantity per item. Where an item has multiple lots, no arbitrary single lot price is fabricated. A registered *reference* price may be displayed where recorded; detailed mode uses each lot's own stored price.
- Printed content is **read only**. It does not create shipments, reverse transactions, change item records, or store personal/patient information in another service.
- For readability, use landscape orientation or fewer columns when selecting many fields. A warning appears for more than 10 columns.
- Nothing is uploaded to a PDF service: printing and Save as PDF use the browser's native print renderer. Test print scaling on the target browser/printer.

## How to use

1. Sign in to IMS, then open **المواقف**.
2. Choose a statement, adjust report cutoff or scarce/surplus percentage, and use any search, branch, book and sorting filters.
3. Click **تصميم وطباعة الموقف**.
4. Pick the printed columns, A4 direction, per-lot versus one-item view, optional signature and heading.
5. Review the live Arabic page preview, then click **طباعة / حفظ PDF**.
6. Select a physical printer or **Save as PDF** in the browser dialog.

## Deployment / safety

- Update the same private GitHub repository and redeploy the same Railway web service.
- **Database Schema V10 is unchanged; no migration or restoration is needed.** Keep `/data` persistent storage and all variables as they are. Download a verified backup before any deployment.
- The existing encrypted Google Drive backup functionality and Undo/Redo remain unchanged.
- The ZIP contains application source but no live database, credentials, private keys, or proprietary font binaries.
- Verify `/api/health` reports `release: 4.27.0`, `version: 10`.

## Test coverage

- Existing warehouse backend regression scripts (inventory, FEFO, transactions, permissions, Undo/Redo, backup, migration, Google Drive mocks) passed.
- New route is inaccessible before sign-in, while underlying report APIs still require authentication.
- Browser component tests using fictional records passed for all four report types, Arabic/English, A4 portrait/landscape, summary/detailed rows and multi-page PDF generation.
- Print output was checked as a true multi-page A4 landscape PDF. Live Railway deployment/printers still require final testing by the user.
