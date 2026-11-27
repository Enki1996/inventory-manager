# IMS V4.27.1 — Home & Login Typography

- `SC_DUBAI.ttf`: headline font used for Arabic Home hero, features, workflow, privacy/terms, login hero and sign-in title; major dashboard and print-designer headings.
- `VIP Rawy Thin Thin.otf`: lightweight accents on Arabic Home and Login, at sizes large enough to remain legible.
- `Cairo`: retains body text, controls, tables, reports and numerical data where readability is critical.
- English styling stays unchanged; the bilingual language switch still works.
- `Amine_mod` and `banda` styles have been removed from the Home page CSS.
- No migrations. SQLite schema remains V10. All stock, accounts, backup and restore functionality remains unchanged.
- This distribution does not contain font files. Use your own uploaded font originals as described in `static/fonts/README.md`.

Deployment: back up first, extract ZIP over your existing private GitHub repository while preserving any font files as appropriate, copy both new fonts into `static/fonts`, push to GitHub, and redeploy the same Railway service with the existing `/data` volume. `/api/health` should report release 4.27.1, schema 10.
