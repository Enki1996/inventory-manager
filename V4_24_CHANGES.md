# IMS V4.24 — Interactive hero refresh

- Replaced the large logo in the hero with a lightweight, illustrative warehouse operations network (incoming → central warehouse → distribution and movement tracking).
- Added very slow animated architectural guidelines, subtle flowing connection paths and a soft scanner highlight. Pointer movement adds restrained lighting and a small perspective tilt. Respects prefers-reduced-motion and coarse-touch devices.
- Official supplied IMS logo remains in navigation, footer, login, dashboard and favicon, but is **not the oversized hero graphic**.
- Preserved the anchored single-page Home, sections, bilingual content, Privacy Policy, Terms of Use, authentication, database, FEFO, shipments, audit/backup logic.
- UI-only change. Database Schema V9 unchanged; existing Railway `/data` volume and environment variables must stay attached.
- Static assets cache-busted to 4.24.0. `GET /api/health` reports `release: 4.24.0`.

## Deploy
Export a backup, replace the existing private GitHub repository files with these extracted files, and redeploy the **same Railway service**. Do not upload or restore a database file. Verify Home on desktop/mobile with and without animation, language switch, anchor navigation, Login, legal routes and `/api/health`.
