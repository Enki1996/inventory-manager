# IMS V4.22 — Release notes and deployment

## Access and recovery
- The installation owner (default existing username `enki`) is the only account permitted to access Google Drive APIs and controls, including OAuth, browsing, export, manual cloud backup and direct restore. Optional Railway variable `WAREHOUSE_ULTRA_ADMIN_USERNAME` must only be set to the actual existing owner account, and is not editable from the website. Other administrators cannot reset or modify the owner account. The existing cron secret remains the machine-only authorization for scheduled backups.
- Administrators retain local ZIP export and restore. Non-owner admins may restore only newly signed local exports. Older/unsigned ZIPs require the owner. The current owner's password and account identity are preserved during restores. The signing key is derived via domain-separated HMAC from the configured existing backup key, not a new secret. Protect exported ZIPs, which contain sensitive database contents including password hashes.
- Cloud direct restoration downloads and decrypts on the backend, asks for RESTORE and the current owner password, requires a valid CSRF token, validates ZIP and SQLite integrity, saves a local server-side safety snapshot before replacing records, records restoration in the restored database and signs out all users. Local and cloud recovery are destructive operations; test on isolated data. The 55 MB compressed / 220 MB uncompressed restore limits are unchanged.
- Keep the same encryption key, OAuth credentials, cron secret, service and persistent /data volume. No cron-worker update or schema migration is required.

## Interface
- Stock receipt/issue voucher terminology, shared stacked-label spacing, localized formerly mixed-language UI labels, fixed-unit display translations, removal of testing/demo wording from the live app chrome; the landing page still labels illustrative dashboard examples as previews. Data entries and official stored register names remain unchanged.
- The opening balance dialog retains a separate “Add another opening lot” label because this adds a lot of the same material, not a different product.

## Deploy
1. Create a manual encrypted Drive backup and download a secure local copy before updating.
2. Extract this archive and replace the main IMS GitHub source files only. Keep the existing Railway services and /data volume. Never upload secrets or database backups to GitHub.
3. Redeploy the existing main service and check `/api/health` for release 4.22.0 and database version 9.
4. Verify the actual owner username. Default `enki` should match the existing account; if not, configure the correct existing username via the Railway variable above.
5. Check owner and ordinary admin accounts, language switch, receipt/issue workflow, manual backup, and the next scheduled backup. Verify direct restoration against a separate test deployment, not active inventory.

## Validation and limitations
- Local mocked Google Drive API tests cover owner access, denial for ordinary admins, signed local restore, rejection of unsigned local restore by staff, encrypted upload/download, password confirmation, direct restore and session invalidation. Existing opening balance, staff/warehouse functionality and two-line receipt tests passed.
- Python and JavaScript syntax checks passed. Browser smoke test could not run because the environment blocked localhost browser navigation; complete visual and bilingual QA remains necessary. Real Google and Railway integration were not exercised. No independent security audit, durable rate limiting, full maintenance-mode write drain, off-volume immutable audit archive or retention policy is included. Schedule backups and restore testing independently of deployment.
