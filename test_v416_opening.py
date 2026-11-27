"""V4.16 end-to-end opening-balance checks using an isolated temporary SQLite database."""
import os
import tempfile
import zipfile
import io
import json
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as work:
    os.environ['WAREHOUSE_DATA_DIR']=work
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
    from app import app, APP_RELEASE, SCHEMA_VERSION, db
    assert (APP_RELEASE, SCHEMA_VERSION) == ('4.24.0', 9)
    with TestClient(app) as c:
        def good(r):
            assert r.status_code == 200, (r.status_code,r.text[:600]); return r.json()
        good(c.post('/api/login',json={'username':'enki','password':'123'}))
        token=good(c.get('/api/me'))['csrf']
        h={'X-CSRF-Token':token}
        base={'branch':'medication','trade_name':'Demo test medicine','name':'Test ingredient',
              'category':'سجل الحبوب - قسم الصيدلة','unit':'حب',
              'annual_need':1200,'manufacturer':'Example Ltd','information':'demo test only'}
        # Catalog-only item: no phantom stock, lots or stock movements.
        a=good(c.post('/api/items',headers=h,json=base))
        items=good(c.get('/api/items')); catalog=next(i for i in items if i['id']==a['id'])
        assert catalog['stock']==0 and catalog['batch_count']==0
        assert catalog['initial_batch_no']=='' and catalog['expiry_date'] is None and catalog['price_fils'] is None
        assert not [b for b in good(c.get('/api/batches')) if b['item_id']==a['id']]
        assert not [m for m in good(c.get('/api/movements')) if m['code'].startswith('OPEN-')]
        # Validation: marking opening stock requires all five fields.
        opening={**base,'name':'Another ingredient','trade_name':'New brand','opening_balance':True,
                 'opening_qty':135,'batch_no':'OPEN-LOT-1','expiry_date':'2028-09-15',
                 'price_dinars':2350,'price_fils_component':750}
        for field in ('opening_qty','batch_no','expiry_date','price_dinars','price_fils_component'):
            missing=opening.copy();missing.pop(field)
            r=c.post('/api/items',headers=h,json=missing)
            assert r.status_code==422,(field,r.status_code,r.text[:300])
        assert c.post('/api/items',headers=h,json={**base,'opening_qty':10}).status_code==422
        assert c.post('/api/items',headers=h,json={**opening,'opening_qty':0}).status_code==422
        assert c.post('/api/items',headers=h,json={**opening,'price_fils_component':1000}).status_code==422
        # Opening is one atomic registration + stored lot + permanent movement.
        created=good(c.post('/api/items',headers=h,json=opening))
        assert created['opening_balance'] is True
        assert created['opening_movement_code'].startswith('OPEN-')
        batches=[b for b in good(c.get('/api/batches')) if b['item_id']==created['id']]
        assert len(batches)==1
        lot=batches[0]
        assert lot['id']==created['opening_batch_id']
        assert (lot['batch_no'],lot['expiry_date'],lot['on_hand'],lot['unit_price_fils'])==('OPEN-LOT-1','2028-09-15',135,2350750)
        movements=[m for m in good(c.get('/api/movements')) if m['code']==created['opening_movement_code']]
        assert len(movements)==1
        m=movements[0]
        assert m['kind']=='ADJUST_PLUS' and m['route']=='opening_balance'
        assert len(m['lines'])==1 and m['lines'][0]['qty']==135
        with db(readonly=True) as cx:
            audit=list(cx.execute("SELECT action,detail FROM audit_log WHERE action='OPENING_BALANCE_CREATED'"))
            assert len(audit)==1
            assert json.loads(audit[0]['detail'])['quantity']==135
        # Catalog edit cannot retroactively change the opening stock lot.
        edit={**base,'trade_name':'Edited brand','batch_no':'OPEN-LOT-1','expiry_date':'2029-01-01',
              'price_dinars':9999,'price_fils_component':0}
        good(c.patch(f'/api/items/{created["id"]}',headers=h,json=edit))
        lot_after=next(b for b in good(c.get('/api/batches')) if b['id']==lot['id'])
        assert lot_after['expiry_date']=='2028-09-15' and lot_after['unit_price_fils']==2350750 and lot_after['on_hand']==135
        # Another priced/dated receipt is still separate and stock is cumulative.
        good(c.post('/api/movements',headers=h,json={'kind':'IN','route':'purchase_receipt',
            'source':'Example supplier','paper_ref':'IN-100','lines':[{'item_id':created['id'],
            'batch_no':'OPEN-LOT-2','expiry_date':'2029-11-01','qty':25,'price_dinars':3400,'price_fils_component':250}]}))
        lots=[b for b in good(c.get('/api/batches')) if b['item_id']==created['id']]
        assert len(lots)==2 and sum(b['on_hand'] for b in lots)==160
        # Backup exports the ledger and restores successfully.
        export=c.get('/api/backup/export');assert export.status_code==200
        with zipfile.ZipFile(io.BytesIO(export.content)) as z:
            assert set(z.namelist())=={'manifest.json','warehouse.sqlite3'}
            assert json.loads(z.read('manifest.json'))['schema_version']==9
        restored=good(c.post('/api/backup/restore',files={'backup':('test_backup.zip',export.content,'application/zip')},headers={**h,'X-Restore-Confirmation':'RESTORE'}))
        assert restored['ok']
        # Restore resets login sessions.
        good(c.post('/api/login',json={'username':'enki','password':'123'}))
        newbatches=good(c.get('/api/batches'))
        assert sum(b['on_hand'] for b in newbatches if b['item_id']==created['id'])==160
        assert any(m['route']=='opening_balance' for m in good(c.get('/api/movements')))
        print('PASS V4.16 opening: blank catalog, required opening fields, atomic stock & audit, separate priced lots, edit safety, backup restore')
