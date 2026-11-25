"""V4.6 end-to-end scenarios for exact IQD/Fils pricing and two-target outgoing workflow."""
import os, tempfile, io, json, zipfile
from pathlib import Path
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as folder:
    os.environ['WAREHOUSE_DATA_DIR'] = folder
    from app import app, connection, SCHEMA_VERSION
    with TestClient(app) as cl:
        assert cl.get('/api/health').json() == {'ok':True,'database':'sqlite','version':5,'release':'4.6.0'}
        assert cl.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        csrf={'X-CSRF-Token':cl.get('/api/me').json()['csrf']}
        item={'branch':'medication','category':'سجل المغذيات - قسم الصيدلة','name':'Saline solution','trade_name':'Salino','batch_no':'SAL-001','unit':'بطل','expiry_date':'2029-09-30','manufacturer':'Example manufacturer','price_dinars':'12345','price_fils_component':'250'}
        for field,value in [('price_dinars',''),('price_dinars','-10'),('price_dinars','12.5'),('price_fils_component','1000'),('price_fils_component','1.5'),('price_fils_component','-1')]:
            r=cl.post('/api/items',headers=csrf,json={**item,field:value})
            assert r.status_code==422,(field,value,r.text)
        item_id=cl.post('/api/items',headers=csrf,json=item).json()['id']
        saved=next(x for x in cl.get('/api/items').json() if x['id']==item_id)
        assert saved['price_fils']==12_345_250
        assert saved['stock']==0
        # Item creation alone never creates usable quantity.
        dep=cl.post('/api/departments',headers=csrf,json={'code':'ER','name':'Emergency'}).json()['id']
        initial_batch=next(b for b in cl.get('/api/batches').json() if b['item_id']==item_id)
        assert initial_batch['on_hand']==0
        bad=cl.post('/api/movements',headers=csrf,json={'kind':'OUT','destination_type':'department','paper_ref':'REQ-001','dispatch_ref':'DISP-001','department_id':dep,'lines':[{'batch_id':initial_batch['id'],'qty':1}]})
        assert bad.status_code==409,bad.text
        r=cl.post('/api/movements',headers=csrf,json={'kind':'IN','paper_ref':'GRN-004','source':'Central supply','lines':[{'item_id':item_id,'batch_no':'SAL-001','expiry_date':'2029-09-30','qty':90}]})
        assert r.status_code==200,r.text
        for d in (
            {'destination_type':'department','paper_ref':'REQ-002','department_id':dep},
            {'destination_type':'department','paper_ref':'REQ-002','dispatch_ref':'DISP-003'},
            {'destination_type':'external','paper_ref':'TR-001','external_destination':''},
            {'destination_type':'external','paper_ref':'TR-001','external_destination':'Second Hospital','department_id':dep},
            {'destination_type':'unexpected','paper_ref':'TR-001'},
        ):
            r=cl.post('/api/movements',headers=csrf,json={'kind':'OUT',**d,'lines':[{'batch_id':initial_batch['id'],'qty':2}]})
            assert r.status_code in (422,409),(d,r.status_code,r.text)
            assert next(i for i in cl.get('/api/items').json() if i['id']==item_id)['stock']==90
        r=cl.post('/api/movements',headers=csrf,json={'kind':'OUT','destination_type':'department','paper_ref':'REQ-002','dispatch_ref':'DISP-003','department_id':dep,'lines':[{'batch_id':initial_batch['id'],'qty':15}]})
        assert r.status_code==200,r.text
        r=cl.post('/api/movements',headers=csrf,json={'kind':'OUT','destination_type':'external','external_destination':'Hospital Ibn Sina','paper_ref':'TRANSFER-01','dispatch_ref':'DELIVERY-01','lines':[{'batch_id':initial_batch['id'],'qty':20}]})
        assert r.status_code==200,r.text
        rows=cl.get('/api/movements').json()
        assert rows[0]['external_destination']=='Hospital Ibn Sina' and rows[0]['department_id'] is None and rows[0]['dispatch_ref']=='DELIVERY-01'
        assert rows[1]['department_id']==dep and rows[1]['paper_ref']=='REQ-002' and rows[1]['dispatch_ref']=='DISP-003'
        assert next(i for i in cl.get('/api/items').json() if i['id']==item_id)['stock']==55
        edit={**item,'price_dinars':'3','price_fils_component':'999','manufacturer':'Amended'}
        assert cl.patch(f'/api/items/{item_id}',headers=csrf,json=edit).status_code==200
        assert next(i for i in cl.get('/api/items').json() if i['id']==item_id)['price_fils']==3_999
        # No staff member may issue an external transfer from another branch.
        supply={'branch':'medical_supplies','category':'سجل الضمادات - مشتريات','name':'Gauze','unit':'قطعة','batch_no':'GAU-9','expiry_date':'2031-01-30','price_dinars':'5','price_fils_component':'0'}
        supply_id=cl.post('/api/items',headers=csrf,json=supply).json()['id']
        receive=cl.post('/api/movements',headers=csrf,json={'kind':'IN','paper_ref':'IN-SUP','source':'Central supply','lines':[{'item_id':supply_id,'batch_no':'GAU-9','expiry_date':'2031-01-30','qty':10}]})
        assert receive.status_code==200,receive.text
        supply_batch=next(x['id'] for x in cl.get('/api/batches').json() if x['item_id']==supply_id and x['on_hand']==10)
        reg=cl.post('/api/users',headers=csrf,json={'username':'medstaff','full_name':'Medical Staff','role':'manager','branch':'medication','password':'PassWord01'})
        assert reg.status_code==200,reg.text
        with TestClient(app) as scoped:
            scoped.post('/api/login',json={'username':'medstaff','password':'PassWord01'})
            scope_csrf={'X-CSRF-Token':scoped.get('/api/me').json()['csrf']}
            cross=scoped.post('/api/movements',headers=scope_csrf,json={'kind':'OUT','destination_type':'external','external_destination':'Other Hospital','paper_ref':'TR-MIX','lines':[{'batch_id':initial_batch['id'],'qty':1},{'batch_id':supply_batch,'qty':1}]})
            assert cross.status_code==403,cross.text
        assert next(x for x in cl.get('/api/batches').json() if x['id']==supply_batch)['on_hand']==10
        assert next(x for x in cl.get('/api/batches').json() if x['id']==initial_batch['id'])['on_hand']==55
        # Outgoing price snapshot must remain unchanged when the catalog price changes.
        outgoing=next(x for x in cl.get('/api/movements').json() if x['code']==rows[0]['code'])
        assert outgoing['lines'][0]['unit_price_fils']==12_345_250
        # Backup includes exact prices and outgoing paper fields.
        snap=cl.get('/api/backup/export');assert snap.status_code==200
        with zipfile.ZipFile(io.BytesIO(snap.content)) as z:
            assert json.loads(z.read('manifest.json'))['schema_version']==5
        # Password-safe public restore not relevant to the local test; restore revokes sessions.
        restore=cl.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},files={'backup':('warehouse.zip',snap.content,'application/zip')})
        assert restore.status_code==200,restore.text
        assert cl.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        assert next(i for i in cl.get('/api/items').json() if i['id']==item_id)['price_fils']==3_999
        assert len(cl.get('/api/movements').json())==4
        # Read-only account may inspect records but cannot perform outgoing changes.
        csrf2={'X-CSRF-Token':cl.get('/api/me').json()['csrf']}
        cl.post('/api/users',headers=csrf2,json={'username':'viewer1','full_name':'Reader','role':'viewer','branch':'medication','password':'PassWord01'})
        with TestClient(app) as viewer:
            assert viewer.post('/api/login',json={'username':'viewer1','password':'PassWord01'}).status_code==200
            c={'X-CSRF-Token':viewer.get('/api/me').json()['csrf']}
            assert viewer.post('/api/movements',headers=c,json={'kind':'OUT','destination_type':'external','external_destination':'Other Hospital','paper_ref':'M-4','lines':[{'batch_id':initial_batch['id'],'qty':1}]}).status_code==403
print('PASS V4.6: price integer fils, two outgoing types, dual department refs, stock validation, backups, role control')
