import os,tempfile
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as tmp:
 os.environ['WAREHOUSE_DATA_DIR']=tmp
 os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
 from app import app,db,SCHEMA_VERSION
 assert SCHEMA_VERSION==11
 def ok(r):
  assert r.status_code==200,(r.status_code,r.text);return r.json()
 with TestClient(app) as admin, TestClient(app) as staff:
  ok(admin.post('/api/login',json={'username':'enki','password':'123'}));h={'X-CSRF-Token':ok(admin.get('/api/me'))['csrf']}
  payload={'username':'customstaff','full_name':'Custom Staff','password':'test_password123','role':'viewer','branch':'medication','custom_access':{'tabs':['inventory'],'actions':['receive']}}
  uid=ok(admin.post('/api/users',headers=h,json=payload))['id']
  ok(staff.post('/api/login',json={'username':'customstaff','password':'test_password123'}));me=ok(staff.get('/api/me'));sh={'X-CSRF-Token':me['csrf']};assert me['permissions']==['receive']
  for kind in ['OUT','RETURN','ADJUST_PLUS']:
   assert staff.post('/api/movements',headers=sh,json={'kind':kind}).status_code==403
  assert staff.post('/api/movements',headers=sh,json={'kind':'IN'}).status_code!=403
  assert staff.post('/api/items',headers=sh,json={}).status_code==403
  assert staff.get('/api/users').status_code==403
  assert admin.patch(f'/api/users/{uid}',headers=h,json={'custom_access':{'tabs':[],'actions':['users']}}).status_code==422
  ok(admin.patch(f'/api/users/{uid}',headers=h,json={'custom_access':None}));assert staff.get('/api/me').status_code==401
  ok(staff.post('/api/login',json={'username':'customstaff','password':'test_password123'}));assert ok(staff.get('/api/me'))['permissions']==[]
  print('PASS custom grants, denial, no admin escalation, session revocation, preset restore')
