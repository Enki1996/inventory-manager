"""V4.26: database-backed paging, security, filtering, and access beyond old history limits."""
import os,tempfile
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as temp:
 os.environ['WAREHOUSE_DATA_DIR']=temp
 from app import app,db,APP_RELEASE,SCHEMA_VERSION
 assert (APP_RELEASE,SCHEMA_VERSION)==('4.27.1',10)
 with TestClient(app) as client:
  def okay(response):
   assert response.status_code==200,(response.status_code,response.text[:600]);return response.json()
  assert client.get('/api/audit-page').status_code==401
  assert client.get('/api/movements-page').status_code==401
  okay(client.post('/api/login',json={'username':'enki','password':'123'}))
  owner=okay(client.get('/api/me'));auth={'X-CSRF-Token':owner['csrf']}
  item=okay(client.post('/api/items',headers=auth,json={
    'branch':'medication','name':'Pager Test Amoxicillin','trade_name':'Pager Amox','unit':'حب',
    'category':'سجل الحبوب - قسم الصيدلة','opening_balance':True,
    'opening_lots':[{'batch_no':'PAGER-LOT','expiry_date':'2029-08-01','opening_qty':1000,'price_dinars':100,'price_fils_component':250}]}))
  with db() as c:
   uid=owner['id'];lot=item['opening_batch_ids'][0]
   for i in range(551):
    mid=c.execute('INSERT INTO movements(code,kind,route,created_by,created_at,paper_ref) VALUES(?,?,?,?,?,?)',
       (f'PAGE-{i:04}','IN','purchase_receipt',uid,'2026-11-25T07:00:00+00:00',f'TEST-PAPER-{i:04}')).lastrowid
    c.execute('INSERT INTO movement_lines(movement_id,batch_id,qty,direction,unit_price_fils) VALUES(?,?,?,?,?)',(mid,lot,1,1,100250))
   for i in range(340):
    c.execute('INSERT INTO audit_log(user_id,action,detail,created_at) VALUES(?,?,?,?)',
        (uid,'PAGINATION_TEST','{"reference":"pagination"}','2026-11-25T09:00:00+00:00'))
  first=okay(client.get('/api/movements-page?limit=20&offset=0'))
  assert first['total']>=552 and len(first['rows'])==20
  assert first['rows'][0]['lines'][0]['batch_no']=='PAGER-LOT'
  later=okay(client.get('/api/movements-page?limit=20&offset=520'))
  assert len(later['rows'])==20, len(later['rows'])
  assert later['rows'][0]['code'].startswith('PAGE-')
  match=okay(client.get('/api/movements-page',params={'q':'PAGER-LOT','limit':100}))
  assert match['total']>=551 and len(match['rows'])==100
  match2=okay(client.get('/api/movements-page',params={'q':'TEST-PAPER-0500'}))
  assert match2['total']==1 and match2['rows'][0]['code']=='PAGE-0500'
  matchedKind=okay(client.get('/api/movements-page',params={'kind':'OUT'}))
  assert matchedKind['total']==0
  a=okay(client.get('/api/audit-page',params={'limit':100,'offset':300}))
  assert a['total']>340 and len(a['rows'])>=40
  assert a['rows'][0]['action']=='PAGINATION_TEST'
  okay(client.post('/api/users',headers=auth,json={'username':'pageviewer','password':'secure_test_password987','full_name':'ReadOnly','role':'viewer','branch':'medication'}))
  okay(client.post('/api/logout',headers=auth))
  okay(client.post('/api/login',json={'username':'pageviewer','password':'secure_test_password987'}))
  assert client.get('/api/audit-page').status_code==403
  assert client.get('/api/movements-page').status_code==200
print('PASS V4.26: 551 movement pages, 340+ audit entries, cross-page search, line details, and viewer restrictions')
