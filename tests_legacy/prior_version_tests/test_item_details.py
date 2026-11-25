"""Backward-compatibility and V4.1 item-details API checks on disposable SQLite databases.
Run: python test_item_details.py
"""
import importlib.util
import os
import sqlite3
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
LEGACY = HERE / 'tests_legacy' / 'v4_app.py'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR'] = tmp
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY', None)
    old = load('legacy_v4_for_test', LEGACY)
    with TestClient(old.app) as cl:
        assert cl.post('/api/login', json={'username':'enki','password':'123'}).status_code == 200
        h = {'X-CSRF-Token':cl.get('/api/me').json()['csrf']}
        data={'sku':'EXIST-01','name':'Existing Medicine','category':'Drugs','unit':'vial','min_stock':50}
        item=cl.post('/api/items',json=data,headers=h)
        assert item.status_code==200,item.text
        rid=item.json()['id']
        mv=cl.post('/api/movements',json={'kind':'IN','paper_ref':'GRN-OLD',
                'source':'Supplier','lines':[{'item_id':rid,'batch_no':'OLD1','expiry_date':'2028-12-01','qty':20}]},headers=h)
        assert mv.status_code==200,mv.text
        legacy_backup=cl.get('/api/backup/export').content
        assert legacy_backup[:2]==b'PK'
    # Import the updated build pointing at the *same* existing database.
    new = load('new_v41_for_test', HERE/'app.py')
    with TestClient(new.app) as cl:
        assert cl.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        h={'X-CSRF-Token':cl.get('/api/me').json()['csrf']}
        existing=cl.get('/api/items').json()
        assert len(existing)==1 and existing[0]['stock']==20
        assert existing[0]['name']=='Existing Medicine' and existing[0]['branch'] is None
        assert existing[0]['generic_name']==existing[0]['manufacturer']==existing[0]['information']==''
        assert existing[0]['min_stock']==50  # Older settings are preserved but not edited in Add Item.
        assert cl.get('/api/health').json()['version']==4
        new_item={'sku':'MED-001','name':'Amoxicillin Trihydrate','trade_name':'Amoxil','batch_no':'REF-AMOX','generic_name':'Amoxicillin',
                  'manufacturer':'Al Razi Pharmaceuticals','manufacture_date':'2026-01-15',
                  'expiry_date':'2029-01-15','information':'اموكسيل، موكس، Amoxil; مضاد حيوي',
                  'category':'سجل الحياتية - قسم الصيدلة','branch':'medication','unit':'كبسول'}
        r=cl.post('/api/items',json=new_item,headers=h)
        assert r.status_code==200,r.text
        new_id=r.json()['id']
        found=next(i for i in cl.get('/api/items').json() if i['id']==new_id)
        for key in ('name','generic_name','manufacturer','manufacture_date','expiry_date','information'):
            assert found[key]==new_item[key],(key,found[key])
        assert found['min_stock']==0  # No new low-stock threshold.
        bad={**new_item,'sku':'FAILDATE','manufacture_date':'2030-01-01'}
        assert cl.post('/api/items',json=bad,headers=h).status_code==422
        assert cl.post('/api/items',json={**new_item,'sku':'FAILFORMAT','expiry_date':'no-date'},headers=h).status_code==422
        edited={**new_item,'generic_name':'Amoxicillin / Amox','information':'موكسيلين، علاج بكتيري',
                'expiry_date':'2029-02-10'}
        r=cl.patch('/api/items/'+str(new_id),json=edited,headers=h)
        assert r.status_code==200,r.text
        updated=next(i for i in cl.get('/api/items').json() if i['id']==new_id)
        assert updated['generic_name']=='Amoxicillin / Amox' and updated['information']=='موكسيلين، علاج بكتيري'
        assert updated['expiry_date']=='2029-02-10'
        # A catalog expiry update must not mutate already received batch expiry.
        batch=cl.post('/api/movements',json={'kind':'IN','paper_ref':'RECEIPT-NEW',
            'source':'Supplier','lines':[{'item_id':new_id,'batch_no':'BN-1','expiry_date':'2028-02-05','qty':11}]},headers=h)
        assert batch.status_code==200,batch.text
        assert next(b for b in cl.get('/api/batches').json() if b['item_id']==new_id and b['on_hand']>0)['expiry_date']=='2028-02-05'
        latest_backup=cl.get('/api/backup/export').content
        assert latest_backup[:2]==b'PK'
        # Restore legacy V4 backup (schema=1) and migrate its item fields safely.
        restored=cl.post('/api/backup/restore',headers={**h,'X-Restore-Confirmation':'RESTORE'},
             files={'backup':('legacy.zip',legacy_backup,'application/zip')})
        assert restored.status_code==200,restored.text
        assert cl.get('/api/me').status_code==401
        assert cl.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        after=cl.get('/api/items').json()
        assert len(after)==1 and after[0]['stock']==20 and after[0]['generic_name']==''
        assert cl.get('/api/health').json()['version']==4
        # Restore V4.1 backup and ensure new metadata survives the round trip.
        h={'X-CSRF-Token':cl.get('/api/me').json()['csrf']}
        result=cl.post('/api/backup/restore',headers={**h,'X-Restore-Confirmation':'RESTORE'},
             files={'backup':('v41.zip',latest_backup,'application/zip')})
        assert result.status_code==200,result.text
        assert cl.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        after=cl.get('/api/items').json()
        record=next(i for i in after if i['sku']=='MED-001')
        assert record['generic_name']=='Amoxicillin / Amox' and record['information']=='موكسيلين، علاج بكتيري'
        assert record['expiry_date']=='2029-02-10'
        assert next(b for b in cl.get('/api/batches').json() if b['item_id']==record['id'] and b['on_hand']>0)['expiry_date']=='2028-02-05'
    with sqlite3.connect(Path(tmp)/'warehouse.sqlite3') as c:
        assert c.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()[0]=='4'
    print('PASS: V4 migration, item metadata, manufacture/expiry checks, independence of batches, V1/V2 backup restore')
