"""V4.20: outgoing FEFO star and movement document detail safeguards."""
import os, tempfile
from pathlib import Path
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as d:
    os.environ['WAREHOUSE_DATA_DIR']=d
    from app import app, APP_RELEASE, SCHEMA_VERSION
    assert (APP_RELEASE,SCHEMA_VERSION)==('4.27.1',10)
    with TestClient(app) as c:
        def ok(r):
            assert r.status_code==200,(r.status_code,r.text[:700]);return r.json()
        ok(c.post('/api/login',json={'username':'enki','password':'123'}))
        csrf=ok(c.get('/api/me'))['csrf'];h={'X-CSRF-Token':csrf}
        item1=ok(c.post('/api/items',json={'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','unit':'حب','name':'Test 1','trade_name':'Demo 1'},headers=h))['id']
        item2=ok(c.post('/api/items',json={'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','unit':'حب','name':'Test 2','trade_name':'Demo 2'},headers=h))['id']
        record=ok(c.post('/api/movements',headers=h,json={'kind':'IN','route':'purchase_receipt','source':'Demo Supplier','paper_ref':'DEMO-V420', 'lines':[
          {'item_id':item1,'batch_no':'A1','qty':9,'expiry_date':'2027-06-01','price_dinars':105,'price_fils_component':500},
          {'item_id':item2,'batch_no':'B2','qty':12,'expiry_date':'2028-06-01','price_dinars':150,'price_fils_component':250}]}))
        row=next(m for m in ok(c.get('/api/movements')) if m['id']==record['id'])
        assert row['code']==record['code'] and len(row['lines'])==2
        assert [(l['batch_no'],l['qty']) for l in row['lines']]==[('A1',9),('B2',12)]
        assert [l['unit_price_fils'] for l in row['lines']]==[105500,150250]
        js=ok(c.get('/api/health'))
        assert js['release']=='4.27.1' and js['version']==10
        source=c.get('/static/live.js').text
        assert 'function movementDetailsRow' in source and 'data-expand-movement' in source
        assert '★ ' in source and 'fefo-recommended-select' in source
        assert 'function toggleMovementDetails' in source
print('PASS V4.20: complete two-line receipt and FEFO recommended expiry display source')
