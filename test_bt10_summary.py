import os,tempfile,datetime as dt
from unittest.mock import patch
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as tmp:
 os.environ['WAREHOUSE_DATA_DIR']=tmp
 os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
 from app import app,gdrive
 with TestClient(app) as c:
  assert c.get('/api/backup-summary').status_code==401
  assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
  assert c.get('/api/health').json()['release']=='BT 1.0'
  with patch.object(gdrive,'ready',return_value=False):
   assert c.get('/api/backup-summary').json()['state']=='unconfigured'
  with patch.object(gdrive,'ready',return_value=True),patch.object(gdrive,'load_state',return_value={'refresh_token':'SECRET','last_error':'PRIVATE','last_success_utc':'2026-11-27T07:00:00+00:00'}):
   r=c.get('/api/backup-summary'); d=r.json(); assert d['state']=='error'; assert 'SECRET' not in r.text and 'PRIVATE' not in r.text
   assert dt.datetime.fromisoformat(d['next_utc'])>dt.datetime.fromisoformat(d['server_utc'])
  with patch.object(gdrive,'ready',return_value=True),patch.object(gdrive,'load_state',return_value={}):
   assert c.get('/api/backup-summary').json()['state']=='disconnected'
 print('PASS backup summary authentication, status, privacy and next scheduled time')
