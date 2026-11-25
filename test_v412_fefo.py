"""Regression test for FEFO recommendations, safety and multi-lot storage."""
import os, tempfile, datetime as dt
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR'] = tmp
    from app import app, SCHEMA_VERSION, APP_RELEASE
    assert SCHEMA_VERSION == 8 and APP_RELEASE == '4.12.0'
    with TestClient(app) as c:
        def ok(r):
            assert r.status_code==200,(r.status_code,r.text)
            return r.json()
        ok(c.post('/api/login',json={'username':'enki','password':'123'}))
        headers={'X-CSRF-Token':ok(c.get('/api/me'))['csrf']}
        dept=ok(c.get('/api/departments'))[0]['id']
        years=[2027,2028,2031]
        expiry=[f'{y}-10-10' for y in years]
        med=ok(c.post('/api/items',headers=headers,json={
            'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','name':'FEFO item',
            'trade_name':'FEFO brand','unit':'حب','batch_no':'CAT-REF','expiry_date':expiry[-1],
            'price_dinars':300,'price_fils_component':250}))['id']
        # Receive deliberately out of FEFO order. Different lot numbers/prices & expiries remain separate.
        for batch,date,qty,price in [('LATE',expiry[2],8,400),('EARLY',expiry[0],5,300),('MID',expiry[1],3,350)]:
            ok(c.post('/api/movements',headers=headers,json={
                'kind':'IN','route':'purchase_receipt','paper_ref':'REC-'+batch,'source':'Distributor',
                'lines':[{'item_id':med,'batch_no':batch,'expiry_date':date,'qty':qty,
                          'price_dinars':price,'price_fils_component':250}]}))
        lots={b['batch_no']:b for b in ok(c.get('/api/batches')) if b['item_id']==med and b['on_hand']>0}
        assert len(lots)==3
        assert len({b['unit_price_fils'] for b in lots.values()})==3
        assert len({b['expiry_date'] for b in lots.values()})==3
        issue={'kind':'OUT','route':'department_issue','department_id':dept,
               'paper_ref':'ORD-FEFO','dispatch_ref':'OUT-FEFO','lines':[
               {'item_id':med,'batch_id':lots['LATE']['id'],'qty':2,'price_dinars':400,'price_fils_component':250}]}
        bad=c.post('/api/movements',headers=headers,json=issue)
        assert bad.status_code==409 and 'FEFO' in bad.text, (bad.status_code,bad.text)
        assert {x['batch_no']:x['on_hand'] for x in ok(c.get('/api/batches')) if x['item_id']==med and x['on_hand']>0} == {b:lots[b]['on_hand'] for b in lots}
        override=ok(c.post('/api/movements',headers=headers,json={**issue,'fefo_override_reason':'Older lot under quality review'}))
        assert override['fefo_override'] is True
        saved=next(m for m in ok(c.get('/api/movements')) if m['id']==override['id'])
        assert 'FEFO override:' in saved['notes'] and 'quality review' in saved['notes']
        # FEFO allocation across one shipment. Earlier and middle exhausted before late lot.
        compliant=ok(c.post('/api/movements',headers=headers,json={**issue,'paper_ref':'ORD-FEFO-OK','dispatch_ref':'OUT-FEFO-OK',
            'lines':[{'batch_id':lots['EARLY']['id'],'qty':5}, {'batch_id':lots['MID']['id'],'qty':3},
                     {'batch_id':lots['LATE']['id'],'qty':2}]}))
        assert compliant['fefo_override'] is False
        after={x['batch_no']:x['on_hand'] for x in ok(c.get('/api/batches')) if x['item_id']==med and x['on_hand']>0}
        assert after=={'LATE':4},after
        health=ok(c.get('/api/health'))
        assert health['release']=='4.12.0' and health['version']==8
        frontend= c.get('/static/live.js').text
        assert 'eligibleLots' in frontend and 'fefoWarningDetails' in frontend and 'fefo_override_reason' in frontend
        assert 'data-fefo-notice' in frontend and 'data-fefo-summary' in frontend
print('PASS V4.10: distinct lots/prices, FEFO rejection, audited override, planned multi-line allocations, existing schema')
