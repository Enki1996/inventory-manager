# IMS V4.23 — New Home, official logo, Privacy & Terms

- Rebuilt the public, one-page Home experience with working anchor navigation: Home, Features, Workflow, Data Protection. Responsive and Arabic-first.
- Featured the user-supplied official المذخر IMS logo. Optimized logo artwork for header, login, dashboard sidebar, footer and favicon.
- Added **separate bilingual** `privacy.html` and `terms.html` pages linked from the Home footer. The policy text is an administrative draft that must be reviewed/approved by the responsible hospital; no invented hospital contact details or legal guarantees.
- Homepage includes interactive sample Lots / Movements / Statements preview (illustrative only).
- No changes to the database schema, authentication, inventory, shipments, reports or cloud-backup logic. Existing database remains in `/data`.
- `GET /api/health` now shows release `4.23.0`, schema remains V9.

## Deployment
1. Export a manual backup first.
2. Replace code in the **existing private GitHub repository** and deploy the **same Railway service**.
3. Keep the existing `/data` volume and all secret Railway variables untouched.
4. Verify `/`, `/login.html`, `/privacy.html`, `/terms.html`, `/dashboard.html` (requires login) and `/api/health`.
5. Review legal text before treating it as a hospital-adopted policy.

The home page anchors and legal text can be edited in `static/index.html`, `static/privacy.html`, `static/terms.html`; Arabic terms in `static/locales/ar.json`, design in `static/marketing.css`.
