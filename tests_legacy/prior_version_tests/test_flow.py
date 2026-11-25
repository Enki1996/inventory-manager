"""End-to-end backend checks against a disposable database. Run: python test_flow.py"""
import os
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as temp:
    os.environ['WAREHOUSE_DATA_DIR'] = temp
    from fastapi.testclient import TestClient
    from app import app
    with TestClient(app) as client:
        assert client.get('/api/health').json()['ok']
        assert client.get('/dashboard.html', follow_redirects=False).status_code == 302
        assert client.get('/api/items').status_code == 401
        r=client.post('/api/login', json={'username':'enki','password':'123'})
        assert r.status_code==200,r.text
        me=client.get('/api/me').json();assert me['username']=='enki' and me['role']=='admin'
        csrf={'X-CSRF-Token':me['csrf']}
        assert client.post('/api/items',json={'sku':'X','name':'Test','category':'Medical','unit':'Box','min_stock':1}).status_code==403
        d=client.post('/api/departments',headers=csrf,json={'code':'ER','name':'Emergency'})
        assert d.status_code==200,d.text; dept=d.json()['id']
        d=client.post('/api/items',headers=csrf,json={'sku':'MED-101','name':'Test Vial','trade_name':'Test Trade','batch_no':'CATALOG-001','generic_name':'Example Generic','manufacturer':'Test manufacturer','manufacture_date':'2026-01-01','expiry_date':'2029-06-30','information':'مثال دواء, alternative, common name','category':'سجل الحياتية - قسم الصيدلة','branch':'medication','unit':'فيال'})
        assert d.status_code==200,d.text; item=d.json()['id']
        saved=next(x for x in client.get('/api/items').json() if x['id']==item)
        assert saved['generic_name']=='Example Generic'
        assert saved['manufacturer']=='Test manufacturer'
        assert saved['information']=='مثال دواء, alternative, common name'
        assert saved['expiry_date']=='2029-06-30' and saved['min_stock']==0
        d=client.post('/api/movements',headers=csrf,json={'kind':'IN','paper_ref':'GRN-2026-100','source':'Ministry medical supply','lines':[{'item_id':item,'batch_no':'BATCH-101','expiry_date':'2028-06-30','qty':100}]})
        assert d.status_code==200,d.text
        b=next(b['id'] for b in client.get('/api/batches').json() if b['on_hand']>0)
        assert next(b for b in client.get('/api/batches').json() if b['on_hand']>0)['expiry_date']=='2028-06-30'  # Batch expiry independent of catalog date.
        assert client.get('/api/items').json()[0]['stock']==100
        d=client.post('/api/movements',headers=csrf,json={'kind':'OUT','paper_ref':'REQ-2026-200','department_id':dept,'lines':[{'batch_id':b,'qty':23}]})
        assert d.status_code==200,d.text
        assert client.get('/api/items').json()[0]['stock']==77
        d=client.post('/api/movements',headers=csrf,json={'kind':'OUT','paper_ref':'REQ-EXCESS','department_id':dept,'lines':[{'batch_id':b,'qty':1000}]})
        assert d.status_code==409,d.text
        assert client.get('/api/items').json()[0]['stock']==77
        assert len(client.get('/api/movements').json())==2
        d=client.post('/api/users',headers=csrf,json={'username':'clerk1','full_name':'Test Clerk','role':'viewer','branch':'medication','password':'SafePass123'})
        assert d.status_code==200,d.text;uid=d.json()['id']
        download=client.get('/api/backup/export');assert download.status_code==200 and download.content[:2]==b'PK'
        # New user needs an isolated session, not to overwrite admin cookies.
        with TestClient(app) as clerk:
            r=clerk.post('/api/login',json={'username':'clerk1','password':'SafePass123'})
            assert r.status_code==200,r.text
            cme=clerk.get('/api/me').json();assert cme['role']=='viewer'
            r=clerk.post('/api/departments',headers={'X-CSRF-Token':cme['csrf']},json={'code':'ICU','name':'Intensive Care'})
            assert r.status_code==403,r.text
            assert clerk.get('/api/users').status_code==403
            assert clerk.get('/api/backup/export').status_code==403
        d=client.patch('/api/users/'+str(uid),headers=csrf,json={'role':'operator','is_active':True})
        assert d.status_code==200,d.text
        import io
        d=client.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},files={'backup':('warehouse.zip',download.content,'application/zip')})
        assert d.status_code==200,d.text
        assert client.get('/api/me').status_code==401
        assert client.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        assert client.get('/api/items').json()[0]['stock']==77
        assert len(client.get('/api/movements').json())==2
    print('PASS: login, CSRF, items, departments, receiving, issuing, oversell protection, roles, export and restore')
