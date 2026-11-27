"""V4.21 cloud-backup tests; all Google calls are mocked, no real credentials needed."""
import base64
import datetime as dt
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR']=tmp
    os.environ['GOOGLE_OAUTH_CLIENT_ID']='fake-test-client'
    os.environ['GOOGLE_OAUTH_CLIENT_SECRET']='fake-test-secret'
    os.environ['GOOGLE_OAUTH_REDIRECT_URI']='https://ims.example/api/gdrive/callback'
    os.environ['WAREHOUSE_BACKUP_ENCRYPTION_KEY']=base64.urlsafe_b64encode(b'1'*32).decode()
    os.environ['WAREHOUSE_BACKUP_CRON_SECRET']='s'*64
    from app import app, APP_RELEASE, SCHEMA_VERSION, produce_sqlite_snapshot
    import google_drive_backup as gd
    assert APP_RELEASE=='4.25.0' and SCHEMA_VERSION==10

    class Response:
        def __init__(self, content=None,headers=None):
            self._content=content or {}
            self.headers=headers or {}
        def raise_for_status(self): pass
        def json(self): return self._content
        def close(self): pass
        def iter_content(self,chunk_size=1024*1024): yield self._bytes

    drive_files=[];upload_pending={};calls={'upload':0}
    def fake_post(url, **kwargs):
        if url==gd.TOKEN_URL:
            if kwargs['data']['grant_type']=='authorization_code':
                return Response({'refresh_token':'test-refresh','access_token':'test-access'})
            return Response({'access_token':'test-access'})
        if url==gd.UPLOAD_URL:
            serial=str(len(upload_pending)+1)
            upload_pending[serial]=kwargs['json']
            return Response(headers={'Location':'https://test-upload.example/'+serial})
        if 'revoke' in url: return Response()
        raise AssertionError(url)
    def fake_request(method,url,**kwargs):
        assert url.startswith(gd.DRIVE_URL)
        if method=='GET' and url==gd.DRIVE_URL:
            q=kwargs.get('params',{}).get('q','')
            if 'mimeType' in q:
                # Lookup by folder name + parent, sufficient for mocked test.
                name=q.split("name = '")[1].split("'")[0]
                parent='root' if "'root' in parents" in q else q.split(" and '")[-1].split("' in parents")[0]
                return Response({'files':[{'id':f['id'],'name':f['name']} for f in drive_files if f['name']==name and f.get('parent')==parent and f.get('folder')]})
            name=q.split("name = '")[1].split("'")[0]
            parent=q.split(" and '")[-1].split("' in parents")[0]
            return Response({'files':[{'id':f['id'],'name':f['name']} for f in drive_files if f['name']==name and f.get('parent')==parent]})
        if method=='POST' and url==gd.DRIVE_URL:
            obj=kwargs['json']; fid='folder-'+str(len(drive_files)+1)
            drive_files.append({'id':fid,'name':obj['name'],'folder':True,'parent':obj.get('parents',['root'])[0]})
            return Response({'id':fid,'name':obj['name']})
        if method=='GET' and url.startswith(gd.DRIVE_URL+'/'):
            ident=url.rsplit('/',1)[1]
            f=next((f for f in drive_files if f['id']==ident),None)
            if f is None:
                import requests
                raise requests.exceptions.HTTPError('404 not found')
            if kwargs.get('params',{}).get('alt')=='media':
                response=Response();response._bytes=f['payload'];return response
            return Response({'id':f['id'],'name':f['name'],'size':len(f['payload']),
                             'trashed':False,'appProperties':{'warehouse_ims':'1'}})
        raise AssertionError((method,url))
    def fake_put(url,**kwargs):
        serial=url.rsplit('/',1)[1];obj=upload_pending.pop(serial)
        fid='file-identifier-'+str(len(drive_files)+1)
        drive_files.append({'id':fid,'name':obj['name'],'folder':False,'parent':obj['parents'][0],
                            'payload':kwargs['data']})
        calls['upload']+=1
        return Response({'id':fid,'name':obj['name'],'size':len(kwargs['data'])})

    with patch.object(gd.requests,'post',side_effect=fake_post), patch.object(gd.requests,'request',side_effect=fake_request), patch.object(gd.requests,'put',side_effect=fake_put):
        with TestClient(app) as c:
            assert c.get('/api/gdrive/status').status_code==401
            assert c.post('/api/gdrive/scheduled-run').status_code==403
            assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
            csrf=c.get('/api/me').json()['csrf']
            assert c.get('/api/gdrive/status').json()['connected'] is False
            r=c.post('/api/gdrive/connect',headers={'x-csrf-token':csrf});assert r.status_code==200,r.text
            url=r.json()['url'];p=parse_qs(urlparse(url).query)
            assert p['scope']==[gd.SCOPE] and p['access_type']==['offline']
            callback=c.get('/api/gdrive/callback',params={'code':'mockcode','state':p['state'][0]},follow_redirects=False)
            assert callback.status_code==303 and 'gdrive=connected' in callback.headers['location']
            assert c.get('/api/gdrive/status').json()['connected']
            owner=c.get('/api/me').json(); assert owner['is_ultra_admin']
            ordinary=c.post('/api/users',headers={'x-csrf-token':csrf},json={'username':'ordinaryadmin','password':'strong-test-123','full_name':'Regular Admin','role':'admin'});assert ordinary.status_code==200,ordinary.text
            with TestClient(app) as staff:
                assert staff.post('/api/login',json={'username':'ordinaryadmin','password':'strong-test-123'}).status_code==200
                sh={'x-csrf-token':staff.get('/api/me').json()['csrf']}
                assert not staff.get('/api/me').json()['is_ultra_admin']
                local_export=staff.get('/api/backup/export'); assert local_export.status_code==200
                for path in ('status','files','download/testfile123'):
                    assert staff.get('/api/gdrive/'+path).status_code==403,path
                for path in ('connect','backup-now','disconnect','restore/testfile123'):
                    assert staff.post('/api/gdrive/'+path,headers=sh,json={}).status_code==403,path
                assert staff.post('/api/users/'+str(owner['id'])+'/reset-password',headers=sh,json={'password':'attacker-reset-123'}).status_code==403
                assert staff.patch('/api/users/'+str(owner['id']),headers=sh,json={'role':'viewer'}).status_code==403
            manual=c.post('/api/gdrive/backup-now',headers={'x-csrf-token':csrf})
            assert manual.status_code==200,manual.text
            fid=manual.json()['id']
            restored=c.get('/api/gdrive/download/'+fid)
            import io,zipfile,json
            assert restored.status_code==200, (restored.status_code, restored.text[:500]); z=zipfile.ZipFile(io.BytesIO(restored.content))
            assert json.loads(z.read('manifest.json'))['schema_version']==10
            assert z.read('warehouse.sqlite3').startswith(b'SQLite format 3')
            assert not drive_files[-1]['payload'].startswith(b'PK')
            assert gd.decode_secure(gd.encode_secure(b'hello'))==b'hello'
            try:gd.decode_secure(gd.encode_secure(b'hello')[:-1]+b'x')
            except gd.CloudBackupError:pass
            else:raise AssertionError('Tampering must fail AEAD verification')
            point=dt.datetime(2026,11,27,7,0,tzinfo=dt.timezone.utc)
            scheduled=gd.run_backup(Path(tmp),produce_sqlite_snapshot,9,kind='scheduled',utc_now=point)
            assert scheduled['slot']=='2026-11-27-10' and calls['upload']==2
            repeated=gd.run_backup(Path(tmp),produce_sqlite_snapshot,9,kind='scheduled',utc_now=point)
            assert repeated['already_done'] and calls['upload']==2
            assert c.get('/api/gdrive/status').json()['last_success_utc']
            assert c.get('/api/gdrive/download/nonsense').status_code==409
            assert c.post('/api/gdrive/restore/'+fid,headers={'x-csrf-token':csrf},json={'confirmation':'RESTORE','password':'wrong'}).status_code==403
            assert c.post('/api/gdrive/restore/'+fid,headers={'x-csrf-token':csrf},json={'confirmation':'RESTORE','password':'123'}).status_code==200
            assert c.get('/api/me').status_code==401
            assert list((Path(tmp)/'safety_backups').glob('before_restore_*.sqlite3'))
            assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
            csrf=c.get('/api/me').json()['csrf']
            assert c.post('/api/gdrive/disconnect',headers={'x-csrf-token':csrf},json={'confirmation':'DISCONNECT'}).status_code==200
            assert not c.get('/api/gdrive/status').json()['connected']
            staff_record=c.post('/api/users',headers={'x-csrf-token':csrf},json={'username':'localadmin','password':'strong-test-123','full_name':'Local Admin','role':'admin'});assert staff_record.status_code==200
            with TestClient(app) as staff:
                assert staff.post('/api/login',json={'username':'localadmin','password':'strong-test-123'}).status_code==200
                sh={'x-csrf-token':staff.get('/api/me').json()['csrf'],'X-Restore-Confirmation':'RESTORE'}
                signed=staff.get('/api/backup/export');assert signed.status_code==200
                assert staff.post('/api/backup/restore',headers=sh,files={'backup':('old.zip',restored.content,'application/zip')}).status_code==403
                assert staff.post('/api/backup/restore',headers=sh,files={'backup':('signed.zip',signed.content,'application/zip')}).status_code==200
                assert staff.get('/api/me').status_code==401
print('PASS V4.22: owner authorization, protected account, direct restore, OAuth state, CSRF/admin checks, encrypted snapshots, Drive upload, decrypt/restore ZIP, idempotent scheduled slot, disconnected status')
