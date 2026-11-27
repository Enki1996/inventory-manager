"""V4.13 read-only detailed stock history + report compatibility smoke test."""
import os, tempfile, datetime as dt
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as root:
    os.environ['WAREHOUSE_DATA_DIR']=root
    from app import app, SCHEMA_VERSION, APP_RELEASE
    assert (SCHEMA_VERSION,APP_RELEASE)==(9,'4.20.0')
    today=dt.datetime.now(ZoneInfo('Asia/Baghdad')).date()
    early=(today+dt.timedelta(days=45)).isoformat()
    late=(today+dt.timedelta(days=340)).isoformat()
    expired=(today-dt.timedelta(days=1)).isoformat()
    with TestClient(app) as client:
        def good(r):assert r.status_code==200,(r.status_code,r.text[:800]);return r.json()
        assert client.get('/api/items/1/history').status_code==401
        good(client.post('/api/login',json={'username':'enki','password':'123'}))
        csrf=good(client.get('/api/me'))['csrf']
        h={'X-CSRF-Token':csrf}
        item=good(client.post('/api/items',headers=h,json={'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','name':'Paracetamol 500','trade_name':'Panadol','unit':'حب','batch_no':'START','expiry_date':early,'price_dinars':1,'price_fils_component':100,'annual_need':250}))['id']
        def rec(batch,exp,qty,dinar,fils):return good(client.post('/api/movements',headers=h,json={'kind':'IN','route':'purchase_receipt','source':'Test','paper_ref':'TEST-'+batch,'lines':[{'item_id':item,'batch_no':batch,'expiry_date':exp,'qty':qty,'price_dinars':dinar,'price_fils_component':fils}]}))
        rec('LOTS-01',early,30,12,100)
        rec('LOTS-02',late,60,18,950)
        rec('LOTS-03',expired,10,9,0)
        b=good(client.get('/api/batches'))
        lots=[x for x in b if x['item_id']==item and x['on_hand']>0]
        assert len(lots)==3 and set(x['unit_price_fils'] for x in lots)=={12100,18950,9000}
        assert sum(x['on_hand'] for x in lots)==100
        first=good(client.get(f'/api/items/{item}/history?limit=2&offset=0'))
        second=good(client.get(f'/api/items/{item}/history?limit=2&offset=2'))
        assert first['total']==3 and len(first['rows'])==2 and len(second['rows'])==1
        ids=[x['id'] for x in first['rows']+second['rows']]
        assert len(set(ids))==3
        assert set(r['unit_price_fils'] for r in first['rows']+second['rows'])=={12100,18950,9000}
        assert all(x['batch_no'].startswith('LOTS-') for x in first['rows']+second['rows'])
        assert client.get(f'/api/items/{item}/history?limit=101').status_code==422
        assert client.get('/api/items/99999/history').status_code==404
        positions=good(client.get('/api/positions'))
        assert any(x['item_id']==item for x in positions['near_expiry'])
        assert good(client.get('/api/health'))['release']=='4.20.0'
        print('PASS V4.13: item detailed history pagination, multiple priced lots, expiry reports, read-only access, auth, schema compatibility')
