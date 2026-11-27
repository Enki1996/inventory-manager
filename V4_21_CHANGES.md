# V4.21 Changes — Encrypted Google Drive auto backup

1. Added admin-only OAuth web flow requesting Google Drive `drive.file` permission.
2. Added server-side refresh token persistence encrypted on the existing Railway `/data` volume. Google Drive access credentials are never returned to the browser.
3. Added encrypted AES-256-GCM upload of SQLite online snapshots, preserving the V9 ZIP restore format and SHA-256 manifest inside the encrypted envelope.
4. Added a manual **Back up now** action and an authenticated **Download restorable ZIP** cloud backup action.
5. Added a protected scheduled endpoint and separate Railway Cron entry script, two slots daily (10:00 and 14:00 Asia/Baghdad). Each slot is idempotent. These scheduled backups only run once Cron is deployed and configured.
6. Added admin backup status including last success, failure and recent uploaded files, plus success/failure audit events.
7. No database schema change, no changes to existing inventory movement logic, and no data reset.
8. Current scope intentionally excludes destructive cloud retention/pruning and automated restore.
