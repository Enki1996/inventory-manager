# Google Drive Auto Backups — Hospital Warehouse IMS V4.21

**Prepared but not connected to your Google account yet.** Do not put OAuth credentials, administrator passwords, or encryption keys into GitHub or chat.

## What this update does

- Creates a transactionally consistent SQLite snapshot using the existing SQLite online backup mechanism (not a live copy of a WAL database file).
- Produces the same database ZIP + SHA-256 manifest already accepted by **Settings → Backup & Restore**.
- Encrypts the ZIP with **AES-256-GCM** using a fresh random nonce *before* uploading it to Google Drive.
- Stores Google OAuth refresh token locally, encrypted with the backup key in `/data/gdrive_private_state.enc`; that file is excluded from the downloadable database ZIP.
- Creates a folder **IMS_SECURE_BACKUPS / YEAR / MONTH** in the selected Google Drive account, and uploads `HWIMS_..._scheduled.hwenc` files.
- Adds **Connect Google Drive**, **Back up now**, **Refresh status**, **Disconnect**, and a list of recent backups with **Download restorable ZIP** for admins.
- Runs two scheduled backups at **10:00 AM and 2:00 PM (Asia/Baghdad)** via a separate Railway Cron service. Scheduled requests require a secret; duplicate requests in a given scheduled slot cannot upload twice.
- All cloud backups are **download-only/restore manually**, never automatic restoration.
- Logs successful/failed backups in the existing app audit log and shows the last error in the admin backup screen.

## Step 1 — Keep your current Railway service and data

1. Download a fresh local database backup using the V4.20 admin screen first.
2. Update the *same private GitHub repository* with the extracted V4.21 package.
3. Redeploy the *existing* Railway web-app service. **Do not delete or replace the existing `/data` volume.** The schema remains **V9**.
4. Confirm `https://YOUR-RAILWAY-DOMAIN/api/health` reports `"release":"4.21.0"`.

## Step 2 — Create a Google Cloud OAuth app

Use a **dedicated hospital-owned Google account** for the backups, with MFA. Do not use a staff member's personal account.

1. Open [Google Cloud Console](https://console.cloud.google.com/), create/select a Google Cloud project and enable the **Google Drive API**.
2. In **Google Auth Platform**, configure app branding, audience and data access. Request only the narrow `https://www.googleapis.com/auth/drive.file` scope. This allows access to files created by the IMS, not general access to all Drive content.
3. Create **OAuth Client ID → Web application**. Add this *exact* authorized redirect URI:
   `https://YOUR-RAILWAY-DOMAIN/api/gdrive/callback`.
4. Copy the OAuth client ID and client secret to Railway **Variables** (not source control).
5. If the OAuth audience is External, note that **Testing** mode normally produces refresh tokens that expire after about **7 days** for Drive scopes. Configure a suitable production/published OAuth consent status for ongoing automated backups, following Google's publication/verification rules. Reconnect if Google later revokes the refresh token.
6. The *Google account that will own the backups* must use the **Connect Google Drive** authorization button inside the app (as an IMS administrator). The OAuth screen verifies the target account.

Google official documentation:
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth
- https://developers.google.com/identity/protocols/oauth2

## Step 3 — Set Railway variables in the EXISTING web-app service

Set these in the service's **Variables** section:

```
GOOGLE_OAUTH_CLIENT_ID=<your actual OAuth web client ID>
GOOGLE_OAUTH_CLIENT_SECRET=<your actual OAuth client secret>
GOOGLE_OAUTH_REDIRECT_URI=https://YOUR-RAILWAY-DOMAIN/api/gdrive/callback
WAREHOUSE_BACKUP_ENCRYPTION_KEY=<URL-safe base64 of 32 random bytes>
WAREHOUSE_BACKUP_CRON_SECRET=<at least 32 random characters>
```

Generate **independent** values on your own computer (Python commands):

```
python -c "import secrets,base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Store **both the backup encryption key and its recovery instructions** in a separate hospital-controlled secure password manager/offline recovery record, **outside Railway**. If you lose the backup encryption key, no one can decrypt those Google Drive backups—even if you still have the Drive files. Do not change the key after backups exist without a tested key-rotation/re-encryption plan.

**Do not paste the generated values in this chat, in a browser field, or in GitHub.** Use the Railway Variables editor.

## Step 4 — Connect and prove manual backup works

1. Sign in as an administrator and open **النسخ الاحتياطي والاستعادة / Backup & Restore**.
2. Click **Connect Google Drive** and sign into the intended hospital-owned Google account. Accept Google's permission request.
3. Back in the app, click **Back up now**. Watch the status for a successful `.hwenc` upload.
4. Open `IMS_SECURE_BACKUPS` in the connected Drive account; see the `YEAR / MONTH` subfolders.
5. In the app's backup list, click **Download restorable ZIP**. Use **Browse Drive backups** to retrieve older files, even after reconnecting on a new server with the same Google OAuth client and key. The server decrypts it only for a logged-in administrator. **Test restoring the ZIP on a separate testing deployment/volume.** Do not test restore by overwriting the active warehouse database.

The cloud files are intentionally *not* plain `.zip`; they are encrypted `.hwenc` and must be downloaded/decrypted through the admin screen using the same encryption key. Do not upload `.hwenc` directly into the existing Restore form.

## Step 5 — Enable 10 AM + 2 PM automatic backups

Set up a **second Railway service** within your existing Railway project, sourced from a **separate private GitHub repository**. The main app already uses `railway.json` to start the website; using a separate repository prevents that server start command from accidentally overriding the cron worker command.

1. Download the **separate `Hospital_Warehouse_Backup_Cron_V4_21.zip`** included with this delivery, extract it, and upload `worker.py`, `requirements.txt` and `README.md` to a new private GitHub repository, e.g. `hospital-warehouse-backup-cron`.
2. In the same Railway project, create a second service from that cron-only GitHub repository.
3. Service start command: `python worker.py`.
4. Settings → Cron Schedule (UTC): `0 7,11 * * *`.
5. Railway Cron evaluates in **UTC**; the above means **10:00 AM and 2:00 PM in Baghdad** (Iraq UTC+3), every day.
6. Cron service variables:

```
WAREHOUSE_APP_URL=https://YOUR-RAILWAY-DOMAIN
WAREHOUSE_BACKUP_CRON_SECRET=<same secret set on the main web-app service>
```

The Cron service must **exit on completion**. Do not set the web-app service itself to Cron. Do **not** give the cron service Google OAuth credentials, encryption keys or a database volume; it only makes an authenticated HTTPS call to your existing app.

You may trigger the Cron service once manually from Railway at a scheduled window to test it; **Back up now** in the admin panel works at any time. Failed Cron runs show in Railway logs and the **last error** in the IMS backup screen. The app allows scheduled triggers within 45 minutes of the 10:00/14:00 slot to tolerate slight Railway delays and refuses duplicate runs for a completed slot.

Railway official docs: https://docs.railway.com/cron-jobs

## Backup retention and safety

- Agreed target policy: **keep all daily backups 30 days; then weekly backups for six months; monthly backups for two years**.
- **This first connected version deliberately does not automatically delete any Google Drive backups.** We will enable pruning only after confirming remote uploads, restore tests, and a safe dry-run retention report. Until then, monitor Drive storage capacity and prune manually only if necessary.
- Backups are supplemental to Railway's volume snapshots; keeping both methods protects against distinct failure types. Add a monthly restore drill on a separate service.
- Each manual or scheduled backup excludes active staff login sessions; user accounts/permission data, stock, prices, expiry lots, documents, movements and audit history remain in the ZIP.
- The encrypted Google connection-state file lives on the persistent `/data` volume but is **not** included in database restores. The Drive account may need to be reconnected after moving hosts.

## Troubleshooting

| Symptom | Cause / action |
|---|---|
| “Requires Railway credentials” | Set all OAuth and key variables on the **main app** service, then redeploy. |
| OAuth error | Verify exact HTTPS redirect URI, Drive API enabled, correct consent account/test-user settings. |
| Works for 7 days then fails | External/Testing OAuth refresh token expiration; arrange appropriate Google production consent and reconnect. |
| “Google Drive authorization failed” | Token revoked/expired; reconnect as an administrator. |
| Failed upload | Check Drive storage quota, API access, and Railway logs; no local database changes were made. |
| `Cannot decrypt backup` | Wrong/changed encryption key or damaged backup; retrieve the securely stored original key. |
| No backups at 10/14 | Confirm second Railway Cron service start command, UTC schedule, secrets and recent logs. |
| Duplicate Cron trigger | Only the first upload for that Baghdad date+slot is kept. |

## What this update does NOT do

This feature does **not** access Google Drive automatically until you authorize the account, and it cannot be considered live until both Railway services are configured. It does not implement Undo/Redo (that remains a separate future change), does not auto-restore, and does not auto-prune older cloud backups yet.
