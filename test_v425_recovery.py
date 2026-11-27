"""V4.25 recovery behavior + permission tests, isolated ephemeral database."""
import os,tempfile,json,zipfile,hashlib,io
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as temp:
 os.environ['WAREHOUSE_DATA_DIR']=temp
 os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
 from app import app,db,APP_RELEASE,SCHEMA_VERSION
 assert (APP_RELEASE,SCHEMA_VERSION)==('4.25.0',10)
 with TestClient(app) as c:
  def good(r):
   assert r.status_code==200,(r.status_code,r.text[:1400]);return r.json()
  good(c.post('/api/login',json={'username':'enki','password':'123'}))
  csrf=good(c.get('/api/me'))['csrf'];h={'X-CSRF-Token':csrf}
  base={'branch':'medication','trade_name':'Recovery testing brand','name':'Recovery testing generic','category':'سجل الحبوب - قسم الصيدلة','unit':'حب','annual_need':1200,'opening_balance':True,'opening_lots':[
    {'batch_no':'REC-A','expiry_date':'2029-01-01','manufacture_date':'2026-01-01','opening_qty':100,'price_dinars':150,'price_fils_component':250},
    {'batch_no':'REC-B','expiry_date':'2030-02-01','manufacture_date':'2026-06-01','opening_qty':40,'price_dinars':200,'price_fils_component':500},
  ]}
  added=good(c.post('/api/items',headers=h,json=base))
  bids=added['opening_batch_ids'];open_mid=int(added['opening_movement_code'].split('-')[-1])
  dept=good(c.get('/api/departments'))[0]['id']
  issue=good(c.post('/api/movements',headers=h,json={'kind':'OUT','route':'department_issue','department_id':dept,'paper_ref':'REQ-REC-1','dispatch_ref':'DIS-REC-1','fefo_override_reason':'Two different lot lines for application integration test','lines':[{'batch_id':bids[0],'qty':20},{'batch_id':bids[1],'qty':5}]}))
  mid=issue['id'];summary=good(c.get('/api/recovery/movement/'+str(mid)))
  lineids=[x['id'] for x in summary['lines']];assert len(lineids)==2
  def stock():
   return {x['id']:x['on_hand'] for x in good(c.get('/api/batches')) if x['id'] in bids}
  assert stock()=={bids[0]:80,bids[1]:35}
  payload={'movement_id':mid,'line_ids':[lineids[0]],'reason':'Correction of mistaken first line','password':'123','confirmation':'UNDO'}
  undo=good(c.post('/api/recovery/undo',headers=h,json=payload))
  assert stock()=={bids[0]:100,bids[1]:35}
  assert c.post('/api/recovery/undo',headers=h,json=payload).status_code==409
  assert c.post('/api/recovery/redo',headers=h,json={'undo_movement_id':undo['undo_movement_id'],'reason':'Attempt without password','password':'WRONG','confirmation':'REDO'}).status_code==403
  redo=good(c.post('/api/recovery/redo',headers=h,json={'undo_movement_id':undo['undo_movement_id'],'reason':'Correct previous mistake','password':'123','confirmation':'REDO'}))
  assert stock()=={bids[0]:80,bids[1]:35}
  assert c.post('/api/recovery/redo',headers=h,json={'undo_movement_id':undo['undo_movement_id'],'reason':'Repeated duplicate action','password':'123','confirmation':'REDO'}).status_code==409
  # Entire shipment undo after first line has been redone (a new cycle is permitted).
  whole=good(c.post('/api/recovery/undo',headers=h,json={'movement_id':mid,'reason':'Correct complete shipment entry','password':'123','confirmation':'UNDO'}))
  assert stock()=={bids[0]:100,bids[1]:40}
  good(c.post('/api/recovery/redo',headers=h,json={'undo_movement_id':whole['undo_movement_id'],'reason':'Transaction was actually valid','password':'123','confirmation':'REDO'}))
  assert stock()=={bids[0]:80,bids[1]:35}
  # Trying to reverse initial stock would make balances negative; no partial changes.
  conflict=c.post('/api/recovery/undo',headers=h,json={'movement_id':open_mid,'reason':'Cannot reverse stock already used','password':'123','confirmation':'UNDO'})
  assert conflict.status_code==409,conflict.text
  assert stock()=={bids[0]:80,bids[1]:35}
  # The last ITEM_UPDATED log stores before and after states.
  item=next(x for x in good(c.get('/api/items')) if x['id']==added['id'])
  edit={'branch':item['branch'],'category':item['category'],'name':'Recovery generic edited','trade_name':'Recovery new brand','unit':item['unit'],'manufacturer':'Recovery Manufacturer','active':True}
  good(c.patch('/api/items/'+str(added['id']),headers=h,json=edit))
  audit=good(c.get('/api/audit'))
  item_audit=next(x for x in audit if x['action']=='ITEM_UPDATED' and json.loads(x['detail']).get('id')==added['id'])
  assert json.loads(item_audit['detail'])['before']['name']!=json.loads(item_audit['detail'])['after']['name']
  au=good(c.post('/api/recovery/audit/'+str(item_audit['id'])+'/undo',headers=h,json={'reason':'Undo erroneous catalog rename','password':'123','confirmation':'UNDO'}))
  assert next(x for x in good(c.get('/api/items')) if x['id']==added['id'])['name']==item['name']
  good(c.post('/api/recovery/audit/'+str(item_audit['id'])+'/redo',headers=h,json={'reason':'Catalog rename was intended','password':'123','confirmation':'REDO'}))
  assert next(x for x in good(c.get('/api/items')) if x['id']==added['id'])['name']=='Recovery generic edited'
  # An audit-based Undo can reverse a movement recorded by the app.
  audit=good(c.get('/api/audit'))
  move_audit=next(x for x in audit if x['action']=='MOVEMENT_CREATED' and json.loads(x['detail']).get('id')==mid)
  via_audit=good(c.post('/api/recovery/audit/'+str(move_audit['id'])+'/undo',headers=h,json={'line_ids':[lineids[1]],'reason':'Erroneous second receipt line','password':'123','confirmation':'UNDO'}))
  assert stock()[bids[1]]==40
  # A read-only user cannot undo or redo, or call audit undo.
  good(c.post('/api/users',headers=h,json={'username':'recoveryviewer','password':'test_password_123456','full_name':'Read only','role':'viewer','branch':'medication'}))
  good(c.post('/api/logout',headers=h))
  good(c.post('/api/login',json={'username':'recoveryviewer','password':'test_password_123456'}))
  csrf2=good(c.get('/api/me'))['csrf'];h2={'X-CSRF-Token':csrf2}
  assert c.get('/api/recovery/movement/'+str(mid)).status_code==403
  assert c.post('/api/recovery/undo',headers=h2,json=payload).status_code==403
  assert c.post('/api/recovery/redo',headers=h2,json={'undo_movement_id':undo['undo_movement_id'],'reason':'Not permitted','confirmation':'REDO','password':'test_password_123456'}).status_code==403
  with db(readonly=True) as conn:
   assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
   assert not conn.execute('PRAGMA foreign_key_check').fetchall()
   assert conn.execute('SELECT COUNT(*) FROM movement_reversals').fetchone()[0]>=4
   actions={x[0] for x in conn.execute("SELECT action FROM audit_log")}
   assert {'MOVEMENT_UNDO','MOVEMENT_REDO','AUDIT_EDIT_UNDO','AUDIT_EDIT_REDO'}<=actions
 print('PASS V4.25: selective & entire Undo, Redo, duplicate protection, dependent-stock check, audited item edit undo/redo, and viewer permissions')
