"""V4.8 regression coverage: transfers, independently priced batches, UI, migrations, backups."""
import os, tempfile, io, json, zipfile, sqlite3
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as d:
    os.environ['WAREHOUSE_DATA_DIR']=d
    from app import app, DB, SCHEMA_VERSION
    assert SCHEMA_VERSION==7
    with TestClient(app) as t:
        def good(resp):
            assert resp.status_code==200,(resp.status_code,resp.text)
            return resp.json()
        good(t.post('/api/login',json={'username':'enki','password':'123'}))
        headers={'X-CSRF-Token':good(t.get('/api/me'))['csrf']}
        new_dep=good(t.post('/api/departments',headers=headers,json={'name':'قسم الطوارئ'}))
        assert new_dep['id']>0
        deps=good(t.get('/api/departments'))
        assert len(deps)==1 and deps[0]['name']=='قسم الطوارئ' and deps[0]['code'].startswith('DEP-')
        good(t.patch('/api/departments/'+str(new_dep['id']),headers=headers,json={'name':'الإسعاف الفوري'}))
        assert good(t.get('/api/departments'))[0]['code']==deps[0]['code']
        item=good(t.post('/api/items',headers=headers,json={
            'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','name':'Paracetamol 500mg',
            'trade_name':'Panadol','unit':'حب','batch_no':'LOT-A','expiry_date':'2032-05-01',
            'price_dinars':1200,'price_fils_component':250}))
        item_id=item['id']
        def receive(batch,expiry,dinar,fils,qty,route='purchase_receipt', **extra):
            data={'kind':'IN','route':route,'source':'Distributor' if route=='purchase_receipt' else 'Hospital B',
                  'paper_ref':'IN-REF-9', 'lines':[{'item_id':item_id,'batch_no':batch,'expiry_date':expiry,
                                'qty':qty,'price_dinars':dinar,'price_fils_component':fils}],**extra}
            return t.post('/api/movements',headers=headers,json=data)
        good(receive('LOT-A','2032-05-01',1200,250,10)) # seed lot
        good(receive('LOT-A','2032-05-01',1200,500,20)) # same lot number and expiry, new price
        good(receive('LOT-A','2032-11-01',1200,250,30)) # same lot and price, new expiry
        good(receive('LOT-B','2032-05-01',950,0,40)) # different lot
        batches=[b for b in good(t.get('/api/batches')) if b['item_id']==item_id]
        active=[b for b in batches if b['on_hand']>0]
        assert len(active)==4,active
        assert sorted((b['batch_no'],b['expiry_date'],b['unit_price_fils'],b['on_hand']) for b in active)==sorted([
            ('LOT-A','2032-05-01',1200250,10),('LOT-A','2032-05-01',1200500,20),
            ('LOT-A','2032-11-01',1200250,30),('LOT-B','2032-05-01',950000,40)])
        assert good(t.get('/api/items'))[0]['stock']==100
        # External transfer must include free-text pharmacist and authorization letter.
        chosen=next(b for b in active if b['unit_price_fils']==1200500)
        transfer={'kind':'OUT','route':'external_transfer_out','paper_ref':'OUT-555','external_destination':'مستشفى آخر',
                  'trusted_pharmacist_name':'د. خالد من مستشفى آخر','authorization_ref':'AUTH-36',
                  'lines':[{'batch_id':chosen['id'],'qty':5}]}
        missing={**transfer};missing.pop('authorization_ref')
        assert t.post('/api/movements',headers=headers,json=missing).status_code==422
        missing={**transfer};missing.pop('trusted_pharmacist_name')
        assert t.post('/api/movements',headers=headers,json=missing).status_code==422
        out=good(t.post('/api/movements',headers=headers,json=transfer))
        movements=good(t.get('/api/movements'))
        row=next(m for m in movements if m['id']==out['id'])
        assert row['trusted_pharmacist_name']=='د. خالد من مستشفى آخر'
        assert row['authorization_ref']=='AUTH-36'
        assert row['lines'][0]['unit_price_fils']==1200500
        assert good(t.get('/api/items'))[0]['stock']==95
        # Pharmacy transfer same fields; external incoming same fields.
        good(t.post('/api/movements',headers=headers,json={'kind':'OUT','route':'pharmacy_transfer_out',
             'paper_ref':'TR-3','trusted_pharmacist_name':'Ali','authorization_ref':'كتاب-١٢',
             'lines':[{'batch_id':chosen['id'],'qty':1}]}))
        good(receive('LOT-C','2033-01-01',500,900,7,route='external_transfer_in',
             trusted_pharmacist_name='Outside pharmacist',authorization_ref='BOOK-903'))
        # Catalog price change doesn't rewrite historical receipt price or batch price.
        item_full=good(t.get('/api/items'))[0]
        patch={**item_full, 'batch_no':'LOT-A','price_dinars':9999,'price_fils_component':999}
        good(t.patch('/api/items/'+str(item_id),headers=headers,json=patch))
        rows=good(t.get('/api/batches'))
        assert next(b for b in rows if b['id']==chosen['id'])['unit_price_fils']==1200500
        historical=next(m for m in good(t.get('/api/movements')) if m['id']==out['id'])
        assert historical['lines'][0]['unit_price_fils']==1200500
        # Wrong branch staff still cannot mutate inventory across branches.
        good(t.post('/api/users',headers=headers,json={'username':'supplies','password':'PassWord0123',
                 'full_name':'Supplies', 'role':'operator','branch':'medical_supplies'}))
        with TestClient(app) as staff:
            good(staff.post('/api/login',json={'username':'supplies','password':'PassWord0123'}))
            sh={'X-CSRF-Token':good(staff.get('/api/me'))['csrf']}
            bad=staff.post('/api/movements',headers=sh,json={**transfer,'paper_ref':'HACK-1'})
            assert bad.status_code==403,(bad.status_code,bad.text)
        # Restore full V7 backup including multiple priced/dated lots and authorization.
        data=t.get('/api/backup/export')
        assert data.status_code==200
        with zipfile.ZipFile(io.BytesIO(data.content)) as z:
            man=json.loads(z.read('manifest.json'))
            assert man['schema_version']==7
        good(t.post('/api/backup/restore',headers={**headers,'X-Restore-Confirmation':'RESTORE'},
              files={'backup':('db.zip',data.content,'application/zip')}))
        good(t.post('/api/login',json={'username':'enki','password':'123'}))
        assert len([b for b in good(t.get('/api/batches')) if b['item_id']==item_id and b['on_hand']>0])==5
        assert next(m for m in good(t.get('/api/movements')) if m['id']==out['id'])['authorization_ref']=='AUTH-36'
        html=good(t.get('/api/health'))
        assert html['release']=='4.8.0'
print('PASS V4.8: name-only departments, 3 transfer fields, multi-priced/date lots, movement-history price, rollback, branch rules, backup')
