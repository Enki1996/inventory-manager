"""Encrypted Google Drive off-site backups for Hospital Warehouse IMS.

Only a narrowly scoped (drive.file) OAuth token is used. The credential file
and the backup encryption key are never committed to source control.

Scheduled runs are triggered by a separate Railway Cron service through the
protected endpoint in app.py, not by an unreliable browser timer.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import zipfile
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCOPE = 'https://www.googleapis.com/auth/drive.file'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
DRIVE_URL = 'https://www.googleapis.com/drive/v3/files'
UPLOAD_URL = 'https://www.googleapis.com/upload/drive/v3/files'
ENVELOPE = b'HWIMS-GDRIVE-AES256GCM-V1\n'
TIMEZONE = ZoneInfo('Asia/Baghdad')
SLOTS = (10, 14)
_ROOT = 'IMS_SECURE_BACKUPS'
_MUTEX = threading.RLock()

class CloudBackupError(Exception):
    pass


def config():
    return {
        'client_id': os.getenv('GOOGLE_OAUTH_CLIENT_ID', '').strip(),
        'client_secret': os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '').strip(),
        'redirect_uri': os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '').strip(),
        'key': os.getenv('WAREHOUSE_BACKUP_ENCRYPTION_KEY', '').strip(),
        'runner_secret': os.getenv('WAREHOUSE_BACKUP_CRON_SECRET', '').strip(),
    }


def encryption_key():
    encoded = config()['key']
    if not encoded:
        raise CloudBackupError('Missing WAREHOUSE_BACKUP_ENCRYPTION_KEY')
    try:
        raw = base64.urlsafe_b64decode(encoded + '=' * ((-len(encoded)) % 4))
    except Exception as exc:
        raise CloudBackupError('Backup encryption key is invalid') from exc
    if len(raw) != 32:
        raise CloudBackupError('Backup encryption key must contain 32 random bytes (URL-safe base64)')
    return raw


def ready():
    c = config()
    return bool(c['client_id'] and c['client_secret'] and c['redirect_uri'] and c['key'])


def encode_secure(data: bytes) -> bytes:
    nonce = secrets.token_bytes(12)
    encrypted = AESGCM(encryption_key()).encrypt(nonce, data, ENVELOPE)
    return ENVELOPE + nonce + encrypted


def decode_secure(payload: bytes) -> bytes:
    if not payload.startswith(ENVELOPE) or len(payload) <= len(ENVELOPE) + 28:
        raise CloudBackupError('Not an encrypted IMS Google Drive backup')
    idx = len(ENVELOPE)
    try:
        return AESGCM(encryption_key()).decrypt(payload[idx:idx+12], payload[idx+12:], ENVELOPE)
    except Exception as exc:
        raise CloudBackupError('Cannot decrypt backup: wrong encryption key or damaged backup') from exc


def state_path(data_dir: Path):
    return data_dir / 'gdrive_private_state.enc'


def load_state(data_dir: Path):
    file = state_path(data_dir)
    if not file.exists():
        return {}
    try:
        value = json.loads(decode_secure(file.read_bytes()).decode('utf-8'))
        if not isinstance(value, dict):
            raise ValueError('state is not a dictionary')
        return value
    except Exception as exc:
        raise CloudBackupError('Encrypted Google Drive connection state is inaccessible. Check the encryption key.') from exc


def save_state(data_dir: Path, data: dict):
    data_dir.mkdir(parents=True, exist_ok=True)
    content = encode_secure(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    with tempfile.NamedTemporaryFile(dir=data_dir, prefix='.gdrive-state-', delete=False) as fh:
        path = Path(fh.name)
        os.chmod(path, 0o600)
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.replace(path, state_path(data_dir))
    finally:
        path.unlink(missing_ok=True)


def oauth_url(data_dir: Path, user_id: int):
    c = config()
    if not ready():
        raise CloudBackupError('Configure Google OAuth variables and the encryption key on Railway first')
    if not c['redirect_uri'].startswith('https://') and os.getenv('WAREHOUSE_PUBLIC_DEPLOY') == '1':
        raise CloudBackupError('Google OAuth redirect URI must be HTTPS on Railway')
    state_token = secrets.token_urlsafe(40)
    with _MUTEX:
        s = load_state(data_dir)
        s['oauth'] = {
            'digest': hashlib.sha256(state_token.encode()).hexdigest(),
            'user_id': user_id,
            'created': dt.datetime.now(dt.timezone.utc).timestamp(),
        }
        save_state(data_dir, s)
    params = dict(client_id=c['client_id'], redirect_uri=c['redirect_uri'],
                  response_type='code', scope=SCOPE, access_type='offline',
                  prompt='consent', state=state_token)
    return AUTH_URL + '?' + urlencode(params)


def exchange_code(data_dir: Path, state_token: str, code: str, user_id: int):
    if len(state_token) > 200 or len(code) > 4096:
        raise CloudBackupError('Invalid Google OAuth response')
    with _MUTEX:
        s = load_state(data_dir)
        pending = s.get('oauth') or {}
        expected = pending.get('digest') or ''
        if not expected or not hmac.compare_digest(expected, hashlib.sha256(state_token.encode()).hexdigest()):
            raise CloudBackupError('Invalid Google OAuth session; start connection again')
        if pending.get('user_id') != user_id or dt.datetime.now(dt.timezone.utc).timestamp() - pending.get('created', 0) > 600:
            raise CloudBackupError('Google OAuth request expired or belongs to a different user')
        del s['oauth']
        save_state(data_dir, s)  # State is single-use even if token exchange fails.
    c = config()
    try:
        response = requests.post(TOKEN_URL, data={
            'code': code, 'client_id': c['client_id'], 'client_secret': c['client_secret'],
            'redirect_uri': c['redirect_uri'], 'grant_type': 'authorization_code',
        }, timeout=25)
        response.raise_for_status()
        token_data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CloudBackupError('Google OAuth authorization failed; check the client and redirect URI') from exc
    refresh = token_data.get('refresh_token', '')
    if not refresh:
        raise CloudBackupError('Google did not provide offline access. Reconnect and approve consent.')
    with _MUTEX:
        s = load_state(data_dir)
        s['refresh_token'] = refresh
        s['connected_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        s.pop('last_error', None)
        save_state(data_dir, s)


def disconnect(data_dir: Path):
    with _MUTEX:
        s = load_state(data_dir)
        refresh = s.pop('refresh_token', None)
        s.pop('oauth', None)
        s.pop('root_folder_id', None)
        save_state(data_dir, s)
    if refresh:
        with __import__('contextlib').suppress(requests.RequestException):
            requests.post('https://oauth2.googleapis.com/revoke',
                          data={'token': refresh}, headers={'Content-Type':'application/x-www-form-urlencoded'}, timeout=10)


def access_token(data_dir: Path):
    s = load_state(data_dir)
    refresh = s.get('refresh_token')
    if not refresh:
        raise CloudBackupError('Google Drive is not connected. An administrator must authorize the account.')
    c = config()
    try:
        r = requests.post(TOKEN_URL, data={
            'grant_type': 'refresh_token', 'refresh_token': refresh,
            'client_id': c['client_id'], 'client_secret': c['client_secret'],
        }, timeout=25)
        r.raise_for_status()
        token = r.json().get('access_token')
    except (requests.RequestException, ValueError) as exc:
        raise CloudBackupError('Google Drive authorization failed. Reconnect the account if the refresh token expired.') from exc
    if not token:
        raise CloudBackupError('Google did not return an access token')
    return token


def drive_request(method, url, token, *, params=None, json_data=None, data=None, timeout=50, stream=False):
    try:
        r = requests.request(method, url, params=params, json=json_data, data=data,
            headers={'Authorization':f'Bearer {token}'}, timeout=timeout, stream=stream)
        r.raise_for_status()
        return r
    except requests.RequestException as exc:
        raise CloudBackupError('Google Drive API request failed. Check account access, storage space and Railway logs.') from exc


def find_folder(token: str, name: str, parent_id: str | None):
    safe = name.replace("'", "\\'")
    q = f"name = '{safe}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    q += f" and '{parent_id}' in parents" if parent_id else " and 'root' in parents"
    response = drive_request('GET', DRIVE_URL, token,
        params={'q':q,'pageSize':100,'fields':'nextPageToken,files(id,name)'})
    found = response.json().get('files', [])
    if found:
        return found[0]['id']
    metadata={'name':name,'mimeType':'application/vnd.google-apps.folder'}
    if parent_id:
        metadata['parents']=[parent_id]
    created = drive_request('POST', DRIVE_URL, token, json_data=metadata,
                            params={'fields':'id,name'})
    return created.json()['id']


def ensure_folder(token, state, when):
    root = state.get('root_folder_id')
    if not root:
        root = find_folder(token, _ROOT, None)
        state['root_folder_id'] = root
    year = find_folder(token, str(when.year), root)
    month = find_folder(token, f'{when.month:02d}', year)
    return root, month


def existing_by_name(token, name, folder):
    q = "name = '%s' and '%s' in parents and trashed=false" % (name.replace("'", "\\'"), folder)
    return drive_request('GET', DRIVE_URL, token, params={
        'q':q,'pageSize':20,'fields':'files(id,name,size,createdTime)'
    }).json().get('files',[])


def upload_encrypted(token: str, content: bytes, filename: str, folder: str, *, category: str):
    metadata = {'name':filename, 'parents':[folder], 'mimeType':'application/octet-stream',
                'appProperties': {'warehouse_ims':'1','kind':category}}
    # Drive resumable upload: retries can safely reuse the name after lookup.
    try:
        start = requests.post(UPLOAD_URL, params={'uploadType':'resumable','fields':'id,name,size,createdTime'},
            headers={'Authorization':f'Bearer {token}', 'Content-Type':'application/json; charset=UTF-8',
                     'X-Upload-Content-Type':'application/octet-stream',
                     'X-Upload-Content-Length':str(len(content))},
            json=metadata,timeout=40)
        start.raise_for_status()
        location = start.headers.get('Location')
        if not location or not location.startswith('https://'):
            raise CloudBackupError('Google Drive did not provide a secure upload location')
        result=requests.put(location,data=content,headers={'Content-Type':'application/octet-stream'},timeout=180)
        result.raise_for_status()
        return result.json()
    except requests.RequestException as exc:
        raise CloudBackupError('Encrypted backup upload failed; check Google Drive quota and service logs') from exc


def snapshot_zip_bytes(produce_snapshot, schema_version):
    """Create the same restorable ZIP structure as the IMS manual export."""
    with tempfile.TemporaryDirectory() as tmp:
        sqlite_file=Path(tmp)/'warehouse.sqlite3'
        produce_snapshot(sqlite_file)
        database=sqlite_file.read_bytes()
    manifest={'application':'Hospital Warehouse IMS','schema_version':schema_version,
              'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
              'database_file':'warehouse.sqlite3',
              'sha256':hashlib.sha256(database).hexdigest()}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
        z.writestr('warehouse.sqlite3',database)
    return buf.getvalue()


def baghdad_slot(utc_now=None):
    utc_now=utc_now or dt.datetime.now(dt.timezone.utc)
    local=utc_now.astimezone(TIMEZONE)
    if local.hour not in SLOTS or local.minute > 45:
        raise CloudBackupError('Scheduled backup runs only at 10:00 or 14:00 Baghdad time')
    return local, f'{local:%Y-%m-%d}-{local.hour:02d}'


def run_backup(data_dir: Path, produce_snapshot, schema_version: int, *, kind: str='manual', utc_now=None):
    if kind not in ('manual','scheduled'):
        raise CloudBackupError('Unknown backup kind')
    if not ready():
        raise CloudBackupError('Google Drive OAuth and encryption variables are not configured')
    if not _MUTEX.acquire(blocking=False):
        raise CloudBackupError('Another Google Drive backup is already running')
    try:
        when=utc_now or dt.datetime.now(dt.timezone.utc)
        local=when.astimezone(TIMEZONE)
        slot=None
        if kind=='scheduled':
            local,slot=baghdad_slot(when)
        with __import__('contextlib').ExitStack() as stack:
            # Cross-process lock on the existing Railway /data volume.
            fh=stack.enter_context(open(data_dir/'gdrive_backup.lock','a+b'))
            try:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as exc:
                raise CloudBackupError('Backup already running on this service') from exc
            s=load_state(data_dir)
            if not s.get('refresh_token'):
                raise CloudBackupError('Google Drive account is not connected')
            name=f'HWIMS_{local:%Y-%m-%d_%H-%M-%S}_{kind}.hwenc'
            if slot:
                name=f'HWIMS_{local:%Y-%m-%d}_{local.hour:02d}-00_Baghdad_scheduled.hwenc'
            if slot and slot in s.get('completed_slots',[]):
                return {'ok':True,'already_done':True,'slot':slot}
            try:
                token=access_token(data_dir)
                root,folder=ensure_folder(token,s,local)
                save_state(data_dir,s)
                if slot:
                    existing=existing_by_name(token,name,folder)
                    if existing:
                        result=existing[0]
                    else:
                        result=upload_encrypted(token,encode_secure(snapshot_zip_bytes(produce_snapshot,schema_version)),name,folder,category=kind)
                else:
                    result=upload_encrypted(token,encode_secure(snapshot_zip_bytes(produce_snapshot,schema_version)),name,folder,category=kind)
                s['last_success_utc']=when.isoformat(timespec='seconds')
                s['last_file_name']=name
                s['last_file_id']=result['id']
                s['last_error']=''
                if slot:
                    s['completed_slots']=(s.get('completed_slots',[])+[slot])[-120:]
                recent=s.get('recent',[])
                recent.insert(0,{'id':result['id'],'name':name,'created_utc':when.isoformat(timespec='seconds'),'kind':kind})
                s['recent']=recent[:100]
                save_state(data_dir,s)
                return {'ok':True,'name':name,'id':result['id'],'slot':slot}
            except Exception as exc:
                s['last_error']=str(exc)[:300]
                s['last_failure_utc']=when.isoformat(timespec='seconds')
                save_state(data_dir,s)
                raise
    finally:
        _MUTEX.release()


def status(data_dir: Path):
    if not config()['key']:
        return {'configured':ready(),'connected':False,'last_error':'Backup encryption key is not configured'}
    state=load_state(data_dir)
    return {'configured':ready(), 'connected':bool(state.get('refresh_token')),
        'last_success_utc':state.get('last_success_utc'),
        'last_failure_utc':state.get('last_failure_utc'),
        'last_error':state.get('last_error',''),
        'last_file_name':state.get('last_file_name'),
        'root_folder_id':state.get('root_folder_id'),
        'recent':state.get('recent',[])[:20],
        'schedule':'10:00 and 14:00 Asia/Baghdad',
        'retention':'30 days daily, 6 months weekly, 2 years monthly (policy planned; pruning disabled until separately verified)',
        'completed_today':[x for x in state.get('completed_slots',[]) if x.startswith(dt.datetime.now(TIMEZONE).strftime('%Y-%m-%d'))]}


def download_file(data_dir: Path, file_id: str):
    if not 8 <= len(file_id) <= 128 or not all(c.isalnum() or c in '_-' for c in file_id):
        raise CloudBackupError('Invalid Drive file identifier')
    token=access_token(data_dir)
    metadata=drive_request('GET',f'{DRIVE_URL}/{file_id}',token,
        params={'fields':'id,name,size,mimeType,appProperties,trashed'}).json()
    if metadata.get('trashed') or (metadata.get('appProperties') or {}).get('warehouse_ims')!='1':
        raise CloudBackupError('This file is not an IMS-created backup')
    if int(metadata.get('size') or 0) > 230*1024*1024:
        raise CloudBackupError('Backup is too large for browser download')
    r=drive_request('GET',f'{DRIVE_URL}/{file_id}',token,params={'alt':'media'},stream=True,timeout=180)
    try:
        size=0; chunks=[]
        for ch in r.iter_content(chunk_size=1024*1024):
            size+=len(ch)
            if size>230*1024*1024:
                raise CloudBackupError('Backup exceeded safe size limit')
            chunks.append(ch)
        clear=decode_secure(b''.join(chunks))
    finally:
        r.close()
    if not zipfile.is_zipfile(io.BytesIO(clear)):
        raise CloudBackupError('Decrypted content is not a valid ZIP')
    return clear,metadata['name'].removesuffix('.hwenc')+'.zip'


def list_remote_backups(data_dir: Path, limit: int = 200):
    """Find app-created backups even if the local /data history was lost.

    Re-authorizing the same Google account and OAuth client restores access to
    application-created files under Google's narrow drive.file scope.
    """
    token=access_token(data_dir)
    found=[];next_page=None
    while len(found)<limit:
        params={'q':"name contains 'HWIMS_' and trashed = false",
                'pageSize':min(1000,limit*2),
                'orderBy':'createdTime desc',
                'fields':'nextPageToken,files(id,name,size,createdTime,appProperties,mimeType)'}
        if next_page:params['pageToken']=next_page
        doc=drive_request('GET',DRIVE_URL,token,params=params).json()
        for file in doc.get('files',[]):
            if (file.get('appProperties') or {}).get('warehouse_ims')!='1':
                continue
            if file.get('name','').endswith('.hwenc'):
                found.append({'id':file['id'],'name':file['name'],
                              'created_utc':file.get('createdTime',''),
                              'size':file.get('size','')})
                if len(found)>=limit:break
        next_page=doc.get('nextPageToken')
        if not next_page:break
    return found
