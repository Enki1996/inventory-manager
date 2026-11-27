import tempfile,os,json
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as d:
 os.environ['WAREHOUSE_DATA_DIR']=d
 from app import app,db
 with TestClient(app) as t:
  def ok(r):assert r.status_code==200,(r.status_code,r.text);return r.json()
  ok(t.post('/api/login',json={'username':'enki','password':'123'}));h={'X-CSRF-Token':ok(t.get('/api/me'))['csrf']}
  dep=ok(t.post('/api/departments',headers=h,json={'name':'Recovery test department'}))
  ok(t.patch(f'/api/departments/{dep["id"]}',headers=h,json={'name':'Recovery test department renamed','active':False}))
  a=ok(t.get('/api/audit'));entry=next(x for x in a if x['action']=='DEPARTMENT_UPDATED' and json.loads(x['detail'])['id']==dep['id'])
  ok(t.post(f'/api/recovery/audit/{entry["id"]}/undo',headers=h,json={'reason':'Rename was premature','password':'123','confirmation':'UNDO'}))
  row=next(x for x in ok(t.get('/api/departments')) if x['id']==dep['id']);assert row['name']=='Recovery test department' and row['active']==1
  ok(t.post(f'/api/recovery/audit/{entry["id"]}/redo',headers=h,json={'reason':'Rename was actually correct','password':'123','confirmation':'REDO'}))
  row=next(x for x in ok(t.get('/api/departments')) if x['id']==dep['id']);assert row['name']=='Recovery test department renamed' and row['active']==0
  user=ok(t.post('/api/users',headers=h,json={'username':'recoveryworker','password':'testworker_password_123','full_name':'Recovery Worker','role':'viewer','branch':'medication'}))
  users=ok(t.get('/api/users'));uid=next(x['id'] for x in users if x['username']=='recoveryworker')
  ok(t.patch(f'/api/users/{uid}',headers=h,json={'role':'operator','branch':'medical_supplies','is_active':True}))
  aud=ok(t.get('/api/audit'));record=next(x for x in aud if x['action']=='USER_UPDATED' and json.loads(x['detail'])['id']==uid)
  ok(t.post(f'/api/recovery/audit/{record["id"]}/undo',headers=h,json={'reason':'Wrong employee branch assigned','password':'123','confirmation':'UNDO'}))
  changed=next(x for x in ok(t.get('/api/users')) if x['id']==uid);assert changed['role']=='viewer' and changed['branch']=='medication'
  ok(t.post(f'/api/recovery/audit/{record["id"]}/redo',headers=h,json={'reason':'Employee role change was correct','password':'123','confirmation':'REDO'}))
  changed=next(x for x in ok(t.get('/api/users')) if x['id']==uid);assert changed['role']=='operator' and changed['branch']=='medical_supplies'
 print('PASS V4.25: audit department and staff permission edit undo/redo guarded by ultra-admin')
