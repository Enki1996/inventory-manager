"""Version 4.17 integration and migration tests (isolated temporary SQLite database)."""
import os, tempfile, json, io, zipfile, sys
from pathlib import Path
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as temp:
    os.environ['WAREHOUSE_DATA_DIR']=temp
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
    from app import app, db, SCHEMA_VERSION, APP_RELEASE
    assert (SCHEMA_VERSION,APP_RELEASE)==(10,'4.26.0')
    with TestClient(app) as client:
        def ok(response):
            assert response.status_code==200,(response.status_code,response.text[:1200]); return response.json()
        ok(client.post('/api/login',json={'username':'enki','password':'123'}))
        csrf=ok(client.get('/api/me'))['csrf'];h={'X-CSRF-Token':csrf}
        base={'branch':'medication','trade_name':'Opening multi brand','name':'Opening generic','category':'سجل الحبوب - قسم الصيدلة','unit':'حب','annual_need':1200}
        rows=[
           {'batch_no':'LOT-A','manufacture_date':'2025-01-01','expiry_date':'2028-05-01','opening_qty':80,'price_dinars':1250,'price_fils_component':250},
           {'batch_no':'LOT-B','manufacture_date':'2025-09-01','expiry_date':'2028-10-01','opening_qty':45,'price_dinars':1500,'price_fils_component':500},
           {'batch_no':'LOT-A','manufacture_date':'2026-03-01','expiry_date':'2029-01-01','opening_qty':15,'price_dinars':1320,'price_fils_component':0},
        ]
        r=ok(client.post('/api/items',headers=h,json={**base,'opening_balance':True,'opening_lots':rows}))
        item_id=r['id'];assert len(r['opening_batch_ids'])==3
        batches=[x for x in ok(client.get('/api/batches')) if x['item_id']==item_id]
        assert len(batches)==3 and sum(x['on_hand'] for x in batches)==140
        assert {x['manufacture_date'] for x in batches}=={'2025-01-01','2025-09-01','2026-03-01'}
        assert len({x['unit_price_fils'] for x in batches})==3
        movs=[x for x in ok(client.get('/api/movements')) if x['route']=='opening_balance']
        assert len(movs)==1 and len(movs[0]['lines'])==3
        assert movs[0]['code']==r['opening_movement_code']
        with db(readonly=True) as c:
            assert c.execute('SELECT COUNT(*) n FROM audit_log WHERE action=?',('OPENING_BALANCE_CREATED',)).fetchone()['n']==1
        # Strict validations should roll back the catalog write itself.
        bad=dict(base, trade_name='Bad stock',opening_balance=True,opening_lots=rows+[dict(rows[0],manufacture_date='2030-01-01')])
        res=client.post('/api/items',headers=h,json=bad);assert res.status_code==422,(res.status_code,res.text)
        bad=dict(base,trade_name='Bad stock',opening_balance=True,opening_lots=[dict(rows[0],price_fils_component=1000)])
        assert client.post('/api/items',headers=h,json=bad).status_code==422
        assert client.post('/api/items',headers=h,json=dict(base,trade_name='Bad stock',opening_balance=True,opening_lots=[])).status_code==422
        assert client.post('/api/items',headers=h,json=dict(base,trade_name='Bad stock',opening_balance=True,opening_lots='wrong')).status_code==422
        # Opening-disabled must not fabricate any stock or movement.
        empty=ok(client.post('/api/items',headers=h,json=dict(base,trade_name='Zero-stock brand')))
        assert empty['opening_balance'] is False
        assert [x for x in ok(client.get('/api/batches')) if x['item_id']==empty['id']]==[]
        # Create actual department shipment with one line from the opening stock.
        deps=ok(client.get('/api/departments'));dep_id=deps[0]['id']
        issue=ok(client.post('/api/movements',headers=h,json={'kind':'OUT','route':'department_issue','department_id':dep_id,
              'paper_ref':'REQ-TEST-100','dispatch_ref':'DIS-TEST-100','lines':[{'batch_id':r['opening_batch_ids'][0], 'qty':12}]}))
        history=ok(client.get(f'/api/items/{item_id}/shipments'))
        assert history['total']==2 and len(history['shipments'])==2
        assert history['shipments'][0]['code']==issue['code'] and history['shipments'][0]['paper_ref']=='REQ-TEST-100'
        assert history['shipments'][0]['lines'][0]['item_id']==item_id
        assert history['shipments'][1]['route']=='opening_balance' and len(history['shipments'][1]['lines'])==3
        assert history['shipments'][1]['lines'][0]['manufacture_date']=='2025-01-01'
        pag=ok(client.get(f'/api/items/{item_id}/shipments?limit=1&offset=1'))
        assert pag['total']==2 and len(pag['shipments'])==1 and pag['shipments'][0]['route']=='opening_balance'
        assert client.get('/api/items/999999/shipments').status_code==404
        assert client.get(f'/api/items/{item_id}/shipments?limit=0').status_code==422
        dhist=ok(client.get(f'/api/departments/{dep_id}/shipments'))
        assert dhist['total']==1 and dhist['shipments'][0]['code']==issue['code']
        dep=next(x for x in ok(client.get('/api/departments')) if x['id']==dep_id)
        assert dep['shipment_count']==1 and dep['last_shipment_at']
        assert client.get('/api/departments/999999/shipments').status_code==404
        # Profile can edit own contact information, not account security settings.
        profile=ok(client.get('/api/profile'))
        assert profile['username']=='enki' and 'password_hash' not in profile
        updated=ok(client.patch('/api/profile',headers=h,json={'full_name':'Warehouse Admin', 'email':'warehouse@example.test',
                        'phone':'+964 770 123 4567', 'age':38,'job_title':'Pharmacist',
                        'role':'viewer','branch':'surgical_instruments','username':'hacker','is_active':False}))
        assert updated['ok']
        profile2=ok(client.get('/api/profile'))
        assert profile2['full_name']=='Warehouse Admin' and profile2['age']==38
        assert profile2['role']=='admin' and profile2['username']=='enki' and profile2['branch'] is None
        assert client.patch('/api/profile',headers=h,json={'full_name':'Bad mail','email':'not_an_email'}).status_code==422
        assert client.patch('/api/profile',headers=h,json={'full_name':'Bad age','age':125}).status_code==422
        assert client.patch('/api/profile',json={'full_name':'No token'}).status_code in (403,422)
        # Restore of V9 backup preserves profile, lot manufacturing dates and movement grouping.
        exported=client.get('/api/backup/export');assert exported.status_code==200
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            assert json.loads(z.read('manifest.json'))['schema_version']==10
        ok(client.post('/api/backup/restore',files={'backup':('V9.zip',exported.content,'application/zip')},headers={**h,'X-Restore-Confirmation':'RESTORE'}))
        ok(client.post('/api/login',json={'username':'enki','password':'123'}))
        assert ok(client.get('/api/profile'))['phone']=='+964 770 123 4567'
        assert len([x for x in ok(client.get('/api/batches')) if x['item_id']==item_id])==3
        assert ok(client.get(f'/api/items/{item_id}/shipments'))['total']==2
        newadmincsrf=ok(client.get('/api/me'))['csrf']
        staff=ok(client.post('/api/users',headers={'X-CSRF-Token':newadmincsrf},json={
            'username':'warehouseviewer','full_name':'Viewer account','password':'testPassword123',
            'role':'viewer','branch':'medication'}))
        ok(client.post('/api/logout',headers={'X-CSRF-Token':newadmincsrf}))
        ok(client.post('/api/login',json={'username':'warehouseviewer','password':'testPassword123'}))
        viewercsrf=ok(client.get('/api/me'))['csrf']
        assert ok(client.get('/api/items'))
        assert ok(client.get(f'/api/items/{item_id}/shipments'))['total']==2
        assert ok(client.get(f'/api/departments/{dep_id}/shipments'))['total']==1
        assert client.post('/api/items',headers={'X-CSRF-Token':viewercsrf},json=base).status_code==403
        assert client.get('/api/users').status_code==403
        ok(client.patch('/api/profile',headers={'X-CSRF-Token':viewercsrf},json={
            'full_name':'Viewer updated name','email':'viewer@example.test','phone':'','job_title':'','age':None,
            'role':'admin','branch':None}))
        assert ok(client.get('/api/me'))['role']=='viewer'
        assert ok(client.get('/api/profile'))['full_name']=='Viewer updated name'
        print('PASS V4.17: multi-lot opening, manufacture dates, transaction atomicity, read-only shipment timelines, department last shipment, secure self-profile, viewer role, restore')
