"""V4.4 branch-specific item entry, validations, stock history, and legacy migration."""
import os, tempfile, importlib.util, sqlite3, zipfile
from pathlib import Path
from fastapi.testclient import TestClient
from book_catalog import BOOKS_BY_BRANCH
from unit_catalog import UNITS_BY_BRANCH
ROOT=Path(__file__).resolve().parent

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

def login(c):
    assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
    return {'X-CSRF-Token':c.get('/api/me').json()['csrf']}

def payload(branch, sku):
    return {'branch':branch,'name':'Name '+sku,
        'trade_name':'Trade '+sku if branch=='medication' else '',
        'unit':UNITS_BY_BRANCH[branch][0], 'category':BOOKS_BY_BRANCH[branch][0],
        'batch_no':'REG-'+sku,'expiry_date':'2029-09-30',
        'manufacture_date':'2026-06-01','manufacturer':'Test Inc','information':'اسم شعبي, alias'}

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR']=tmp
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
    app=load('fresh_v44_app',ROOT/'app.py')
    with TestClient(app.app) as cl:
        csrf=login(cl)
        assert cl.get('/api/units').json()=={b:list(x) for b,x in UNITS_BY_BRANCH.items()}
        ids={}
        for b in UNITS_BY_BRANCH:
            p=payload(b,b)
            resp=cl.post('/api/items',json=p,headers=csrf)
            assert resp.status_code==200,resp.text
            ids[b]=resp.json()['id']
            assert resp.json()['sku'].startswith({'medication':'MED','medical_supplies':'SUP','surgical_instruments':'SUR'}[b])
            record=next(x for x in cl.get('/api/items').json() if x['id']==ids[b])
            assert record['name']==p['name']
            assert record['trade_name']==p['trade_name']
            assert record['initial_batch_no']==p['batch_no'] and record['display_batch_no']==p['batch_no']
            assert record['expiry_date']==p['expiry_date'] and record['stock']==0
            batch=next(x for x in cl.get('/api/batches').json() if x['item_id']==ids[b])
            assert batch['on_hand']==0 and batch['batch_no']==p['batch_no'] and batch['expiry_date']==p['expiry_date']
            for field in ('expiry_date','batch_no','name','unit'):
                bad={**p};bad.pop(field)
                assert cl.post('/api/items',json=bad,headers=csrf).status_code==422,field
            if b=='medication':
                bad={**p};bad.pop('trade_name')
                assert cl.post('/api/items',json=bad,headers=csrf).status_code==422
            bad={**p,'unit':'box'}
            assert cl.post('/api/items',json=bad,headers=csrf).status_code==422
            bad={**p,'manufacture_date':'2030-01-01'}
            assert cl.post('/api/items',json=bad,headers=csrf).status_code==422
        # For non-medical branches, a supplied trade name is ignored.
        alt={**payload('medical_supplies','EXTRA'), 'trade_name':'Should disappear'}
        assert cl.post('/api/items',json=alt,headers=csrf).status_code==200
        assert next(i for i in cl.get('/api/items').json() if i['name']==alt['name'])['trade_name']==''
        # Receive registered zero-stock batch and distribute it with full movement history.
        med=ids['medication']
        incoming=cl.post('/api/movements',json={'kind':'IN','paper_ref':'IN-001','source':'Test supplier',
           'lines':[{'item_id':med,'batch_no':'REG-medication','expiry_date':'2029-09-30','qty':40}]},headers=csrf)
        assert incoming.status_code==200,incoming.text
        batches=[b for b in cl.get('/api/batches').json() if b['item_id']==med]
        assert len(batches)==1 and batches[0]['on_hand']==40
        dept=cl.post('/api/departments',json={'code':'LAB','name':'Laboratory'},headers=csrf).json()['id']
        outgoing=cl.post('/api/movements',json={'kind':'OUT','paper_ref':'REQ-101','department_id':dept,
            'lines':[{'batch_id':batches[0]['id'],'qty':15}]},headers=csrf)
        assert outgoing.status_code==200,outgoing.text
        assert next(i for i in cl.get('/api/items').json() if i['id']==med)['stock']==25
        edit={**payload('medication','medication'),'trade_name':'Updated commercial',
            'batch_no':'NEW-REFERENCE','expiry_date':'2029-11-01'}
        result=cl.patch(f'/api/items/{med}',json=edit,headers=csrf)
        assert result.status_code==200,result.text
        after=[b for b in cl.get('/api/batches').json() if b['item_id']==med]
        assert len(after)==2
        assert next(b for b in after if b['batch_no']=='REG-medication')['expiry_date']=='2029-09-30'
        assert next(b for b in after if b['batch_no']=='REG-medication')['on_hand']==25
        assert next(b for b in after if b['batch_no']=='NEW-REFERENCE')['on_hand']==0
        assert any(m['paper_ref']=='REQ-101' for m in cl.get('/api/movements').json())
        bk=cl.get('/api/backup/export')
        assert bk.status_code==200
        with zipfile.ZipFile(__import__('io').BytesIO(bk.content)) as z:
            assert __import__('json').loads(z.read('manifest.json'))['schema_version']==4
        assert cl.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},
                       files={'backup':('warehouse.zip',bk.content,'application/zip')}).status_code==200
        login(cl)
        assert next(i for i in cl.get('/api/items').json() if i['id']==med)['trade_name']=='Updated commercial'

# Upgrade actual legacy V4.3 database/backup without modifying existing units, stock or history.
with tempfile.TemporaryDirectory() as tmp:
    import sys
    os.environ['WAREHOUSE_DATA_DIR']=tmp
    old=load('old_v43_app',ROOT/'tests_legacy'/'v43_app.py')
    with TestClient(old.app) as cl:
        csrf=login(cl)
        p={'sku':'LEG-01','name':'Legacy Medic','unit':'vial','category':BOOKS_BY_BRANCH['medication'][0],
           'branch':'medication'}
        r=cl.post('/api/items',json=p,headers=csrf)
        assert r.status_code==200,r.text
        iid=r.json()['id']
        r=cl.post('/api/movements',json={'kind':'IN','paper_ref':'LEGACY-REC','source':'Existing supplier',
           'lines':[{'item_id':iid,'batch_no':'OLD','expiry_date':'2029-12-01','qty':16}]},headers=csrf)
        assert r.status_code==200,r.text
        original_backup=cl.get('/api/backup/export').content
    new=load('upgraded_v44_app',ROOT/'app.py')
    with TestClient(new.app) as cl:
        csrf=login(cl)
        rec=cl.get('/api/items').json()[0]
        assert rec['stock']==16 and rec['unit']=='vial' and rec['trade_name']=='' and rec['expiry_date'] is None
        assert rec['display_batch_no']=='OLD'
        # No unsupported unit can be newly created; old unit can be retained in-place while classifying.
        p={'name':'Legacy Medic','trade_name':'Now branded','unit':'vial',
           'category':BOOKS_BY_BRANCH['medication'][0], 'branch':'medication',
           'batch_no':'OLD','expiry_date':'2029-12-01'}
        r=cl.patch('/api/items/'+str(iid),json=p,headers=csrf)
        assert r.status_code==200,r.text
        assert next(x for x in cl.get('/api/items').json() if x['id']==iid)['stock']==16
        restored=cl.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},
             files={'backup':('old-v43.zip',original_backup,'application/zip')})
        assert restored.status_code==200,restored.text
        csrf=login(cl)
        rec=cl.get('/api/items').json()[0]
        assert rec['stock']==16 and rec['trade_name']=='' and rec['unit']=='vial'
        assert cl.get('/api/health').json()['version']==4
print('PASS: V4.4 all branches and units, field requirements, zero-stock initial batch, movement history, backups, V4.3 migration')
