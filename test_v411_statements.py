"""V4.11 positions: zero stock, precise calendar window and separate lots."""
import os, tempfile, datetime as dt
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR']=tmp
    from app import app, DB, APP_RELEASE, SCHEMA_VERSION, position_window
    assert APP_RELEASE=='4.11.0' and SCHEMA_VERSION==7
    today=dt.datetime.now(ZoneInfo('Asia/Baghdad')).date()
    first_excluded=dt.date(today.year+1+(today.month==12), today.month%12+1, 1)
    last_included=first_excluded-dt.timedelta(days=1)
    assert position_window()==(today.isoformat(),first_excluded.isoformat(),last_included.isoformat())
    with TestClient(app) as client:
        r=client.get('/api/positions')
        assert r.status_code==401,(r.status_code,r.text)
        def ok(r):
            assert r.status_code==200,(r.status_code,r.text)
            return r.json()
        ok(client.post('/api/login',json={'username':'enki','password':'123'}))
        hdr={'X-CSRF-Token':ok(client.get('/api/me'))['csrf']}
        empty=ok(client.get('/api/positions'))
        assert empty['near_expiry']==[] and empty['missing']==[]
        item=ok(client.post('/api/items',headers=hdr,json={
            'branch':'medication','category':'سجل الحبوب - قسم الصيدلة',
            'name':'Statements test medication','trade_name':'Sample drug',
            'unit':'حب','batch_no':'FIRST-EMPTY','expiry_date':'2035-02-18',
            'price_dinars':100,'price_fils_component':0}))['id']
        empty=ok(client.get('/api/positions'))
        assert len(empty['missing'])==1 and empty['missing'][0]['item_id']==item
        assert empty['missing'][0]['stock']==0
        assert empty['near_expiry']==[]
        # A newer-priced lot of same item does NOT overwrite another lot.
        inputs=[('REC-TODAY',today,30,125),('REC-END',last_included,15,175),('REC-AFTER',first_excluded,8,200),('REC-EXPIRED',today-dt.timedelta(days=1),5,275)]
        for lot,expires,qty,price in inputs:
            ok(client.post('/api/movements',headers=hdr,json={
                'kind':'IN','route':'purchase_receipt','source':'Test supplier','paper_ref':lot,
                'lines':[{'item_id':item,'batch_no':lot,'expiry_date':expires.isoformat(),
                          'qty':qty,'price_dinars':price,'price_fils_component':500}]}))
        data=ok(client.get('/api/positions'))
        assert not data['missing'],data['missing']
        assert [r['batch_no'] for r in data['near_expiry']]==['REC-TODAY','REC-END'],data['near_expiry']
        assert [r['unit_price_fils'] for r in data['near_expiry']]==[125500,175500]
        assert data['expired_lot_count']==1
        assert data['pending_calculations']==['scarce','surplus']
        assert data['expiry_before']==first_excluded.isoformat()
        assert data['expiry_last_included']==last_included.isoformat()
        # A second item with no receipts is included and branch stays explicit.
        second=ok(client.post('/api/items',headers=hdr,json={
            'branch':'medical_supplies','category':'سجل النبيذة - مشتريات',
            'name':'Missing gloves','unit':'قطعة','batch_no':'FIRST-EMPTY-2',
            'expiry_date':'2035-02-18','price_dinars':1,'price_fils_component':0}))['id']
        data=ok(client.get('/api/positions'))
        assert [i['item_id'] for i in data['missing']]==[second]
        assert data['missing'][0]['branch']=='medical_supplies'
        assert ok(client.get('/api/health'))['release']=='4.11.0'
        # Verify no changes to the batch schema or aggregate balances.
        rows=ok(client.get('/api/batches'))
        assert len([b for b in rows if b['item_id']==item and b['on_hand']>0])==4
        assert sum(b['on_hand'] for b in rows if b['item_id']==item)==58
        frontend=client.get('/static/live.js').text
        html=client.get('/dashboard.html').text
        assert 'data-statement' in frontend and 'function warehouseStatements' in frontend
        assert 'data-view="positions"' in html
        assert 'statementBranch' in frontend and 'statementSearch' in frontend
        assert 'Warehouse Statements' in html
print('PASS V4.11: missing stock, near-expiry inclusive/exclusive, expired separate, multiple lots/prices, authentication, front-end markers')
