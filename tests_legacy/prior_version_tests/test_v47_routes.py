"""Version 4.7 regressions: seven routes, emergency paperwork, role checks, history and backup."""
import io, json, os, sqlite3, tempfile, zipfile
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as path:
    os.environ['WAREHOUSE_DATA_DIR'] = path
    from app import app, SCHEMA_VERSION
    with TestClient(app) as admin:
        assert admin.get('/api/health').json()['release'] == '4.7.0'
        assert SCHEMA_VERSION == 6
        assert admin.post('/api/login', json={'username':'enki','password':'123'}).status_code==200
        csrf={'X-CSRF-Token':admin.get('/api/me').json()['csrf']}
        users=admin.get('/api/staff-directory').json()
        assert any(x['username']=='enki' for x in users)
        pharmac=users[0]['id']
        assert not any('password' in x or 'hash' in x for x in users)
        dep=admin.post('/api/departments',headers=csrf,json={'code':'ER','name':'Emergency'}).json()['id']
        for branch,cat,name,unit,sku in [
            ('medication','سجل الحبوب - قسم الصيدلة','Med A','حب','AA'),
            ('medical_supplies','سجل الضمادات - مشتريات','Supply B','قطعة','BB')]:
            payload={'branch':branch,'category':cat,'name':name,'trade_name':name if branch=='medication' else '',
                'batch_no':sku,'unit':unit,'expiry_date':'2031-01-30','price_dinars':'100','price_fils_component':'250'}
            r=admin.post('/api/items',headers=csrf,json=payload)
            assert r.status_code==200,r.text
        items=admin.get('/api/items').json()
        med=next(i for i in items if i['branch']=='medication')
        supp=next(i for i in items if i['branch']=='medical_supplies')
        # Every incoming route is validated, including the documented internal return.
        def receive(route, ref, source='', pharma=None, item=None, qty=50):
            it=item or med
            data={'kind':'IN','route':route,'paper_ref':ref,'source':source,'lines':[{'item_id':it['id'],'batch_no':it['initial_batch_no'],'expiry_date':'2031-01-30','qty':qty}]}
            if pharma:data['trusted_pharmacist_id']=pharma
            return admin.post('/api/movements',headers=csrf,json=data)
        assert receive('pharmacy_receipt','PH-1').status_code==200
        assert receive('purchase_receipt','BUY-1','Al Bayan Drugstore').status_code==200
        assert receive('external_transfer_in','EXTIN-1','Other hospital',pharmac).status_code==200
        assert receive('purchase_receipt','BUY-2','Supplier',item=supp,qty=20).status_code==200
        assert receive('purchase_receipt','MISSING','').status_code==422
        assert receive('external_transfer_in','MISSING','Another hospital').status_code==422
        batches=admin.get('/api/batches').json()
        medbatch=next(x for x in batches if x['item_id']==med['id'])['id']
        supplybatch=next(x for x in batches if x['item_id']==supp['id'])['id']
        lines=[{'batch_id':medbatch,'qty':12}]
        def outgoing(route,ref='REQ-1',dispatch='',dest=None,pharma=None,dept=None,pending=False,ship_lines=None):
            data={'kind':'OUT','route':route,'paper_ref':ref,'dispatch_ref':dispatch,
                  'lines':ship_lines or lines,'emergency_pending':pending}
            if dest is not None:data['external_destination']=dest
            if pharma is not None:data['trusted_pharmacist_id']=pharma
            if dept is not None:data['department_id']=dept
            return admin.post('/api/movements',headers=csrf,json=data)
        # Missing documents cannot be disguised as ordinary issue.
        assert outgoing('department_issue',dept=dep).status_code==422
        assert outgoing('department_issue',dept=dep,dispatch='DISP-1').status_code==200
        # Emergency issue can proceed without paper numbers, then must be completed later.
        emerg=outgoing('department_issue',ref='',dispatch='',dept=dep,pending=True)
        assert emerg.status_code==200,emerg.text
        emergency_id=emerg.json()['id']
        saved=next(m for m in admin.get('/api/movements').json() if m['id']==emergency_id)
        assert saved['paperwork_pending']==1 and not saved['paper_ref'] and saved['route']=='department_issue'
        assert outgoing('external_transfer_out',ref='',dest='H-2',pharma=pharmac,pending=True).status_code==422
        assert outgoing('external_transfer_out',dest='H-2').status_code==422
        assert outgoing('external_transfer_out',dest='H-2',pharma=999999).status_code==422
        out=outgoing('external_transfer_out',dest='H-2',pharma=pharmac)
        assert out.status_code==200,out.text
        pharm=outgoing('pharmacy_transfer_out',pharma=pharmac)
        assert pharm.status_code==200,pharm.text
        row=next(m for m in admin.get('/api/movements').json() if m['id']==pharm.json()['id'])
        assert row['route']=='pharmacy_transfer_out' and row['external_destination']=='قسم الصيدلة'
        assert row['trusted_pharmacist_name']=='ENKI Administrator'
        assert outgoing('badroute',dept=dep).status_code==422
        assert outgoing('external_transfer_out',dest='H-2',pharma=pharmac,dept=dep).status_code==422
        before=next(x for x in admin.get('/api/items').json() if x['id']==med['id'])['stock']
        # Emergency paperwork update cannot change stock (or be completed twice).
        wrong=admin.patch(f'/api/movements/{emergency_id}/paperwork',headers=csrf,json={'paper_ref':'REQ-99'})
        assert wrong.status_code==422
        done=admin.patch(f'/api/movements/{emergency_id}/paperwork',headers=csrf,json={'paper_ref':'REQ-99','dispatch_ref':'DISP-99'})
        assert done.status_code==200,done.text
        assert admin.patch(f'/api/movements/{emergency_id}/paperwork',headers=csrf,json={'paper_ref':'AA','dispatch_ref':'BB'}).status_code==409
        after=next(x for x in admin.get('/api/items').json() if x['id']==med['id'])['stock']
        assert before==after
        assert any(x['action']=='EMERGENCY_PAPERWORK_COMPLETED' for x in admin.get('/api/audit').json())
        # Incoming return actually adds stock to existing batch.
        total_before=next(x for x in admin.get('/api/items').json() if x['id']==med['id'])['stock']
        ret=admin.post('/api/movements',headers=csrf,json={'kind':'RETURN','route':'internal_return','department_id':dep,
                'paper_ref':'REQ-1','dispatch_ref':'RET-1','lines':[{'batch_id':medbatch,'qty':7}]})
        assert ret.status_code==200,ret.text
        assert next(x for x in admin.get('/api/items').json() if x['id']==med['id'])['stock']==total_before+7
        assert admin.post('/api/movements',headers=csrf,json={'kind':'RETURN','route':'internal_return','department_id':dep,'paper_ref':'REQ-1','lines':[{'batch_id':medbatch,'qty':1}]}).status_code==422
        assert admin.post('/api/movements',headers=csrf,json={'kind':'IN','route':'internal_return','paper_ref':'X','source':'X','lines':[{'item_id':med['id'],'batch_no':'AA','qty':1}]}).status_code==422
        # Cannot use a receipt or adjustment to bypass branch restrictions.
        created=admin.post('/api/users',headers=csrf,json={'username':'medstaff','full_name':'Med User','role':'operator','branch':'medication','password':'PassWord01'})
        assert created.status_code==200
        with TestClient(app) as staff:
            assert staff.post('/api/login',json={'username':'medstaff','password':'PassWord01'}).status_code==200
            c={'X-CSRF-Token':staff.get('/api/me').json()['csrf']}
            assert staff.get('/api/staff-directory').status_code==200
            wrong=staff.post('/api/movements',headers=c,json={'kind':'OUT','route':'pharmacy_transfer_out','paper_ref':'X',
                           'trusted_pharmacist_id':pharmac,'lines':[{'batch_id':supplybatch,'qty':2}]})
            assert wrong.status_code==403,(wrong.status_code,wrong.text)
            assert staff.patch(f'/api/movements/{emergency_id}/paperwork',headers=c,json={'paper_ref':'A','dispatch_ref':'B'}).status_code==409
        exported=admin.get('/api/backup/export')
        assert exported.status_code==200
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            manifest=json.loads(z.read('manifest.json'))
            assert manifest['schema_version']==6
        restored=admin.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},files={'backup':('backup.zip',exported.content,'application/zip')})
        assert restored.status_code==200,restored.text
        admin.post('/api/login',json={'username':'enki','password':'123'})
        assert any(m['route']=='external_transfer_in' for m in admin.get('/api/movements').json())
        assert any(m['paperwork_completed_at'] for m in admin.get('/api/movements').json() if m['id']==emergency_id)
        assert next(x for x in admin.get('/api/items').json() if x['id']==med['id'])['stock']==total_before+7
print('PASS V4.7: all 7 routes, pending documents, finalization, pharmacist IDs, role isolation, stock and backup')
