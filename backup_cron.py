"""Run once, from the separate Railway scheduled service.
Schedule (UTC): 0 7,11 * * * = 10:00 and 14:00 Asia/Baghdad.
Cron service needs only WAREHOUSE_APP_URL and WAREHOUSE_BACKUP_CRON_SECRET.
"""
import os
import sys
from urllib.parse import urlparse
import requests

site = os.getenv('WAREHOUSE_APP_URL','').rstrip('/')
secret = os.getenv('WAREHOUSE_BACKUP_CRON_SECRET','')
if urlparse(site).scheme != 'https' or len(secret) < 32:
    print('Missing secure WAREHOUSE_APP_URL or WAREHOUSE_BACKUP_CRON_SECRET',file=sys.stderr)
    sys.exit(2)
try:
    response=requests.post(site+'/api/gdrive/scheduled-run',
        headers={'x-warehouse-cron-secret':secret},timeout=240)
    response.raise_for_status()
    outcome=response.json()
    if outcome.get('ok'):
        print('Encrypted Google Drive backup complete' if not outcome.get('already_done') else 'Backup already completed for this slot')
    else:
        print('Backup endpoint returned incomplete status',file=sys.stderr)
        sys.exit(1)
except (requests.RequestException, ValueError) as exc:
    print('Backup failed; check warehouse Backup & Restore status',file=sys.stderr)
    sys.exit(1)
