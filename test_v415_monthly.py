"""V4.15: monthly thresholds are the source of truth; no production DB touched."""
import datetime as dt
import os
import tempfile
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as workspace:
    os.environ['WAREHOUSE_DATA_DIR'] = workspace
    from app import app, APP_RELEASE, SCHEMA_VERSION
    assert (APP_RELEASE, SCHEMA_VERSION) == ('4.22.0', 9)
    future = (dt.datetime.now(ZoneInfo('Asia/Baghdad')).date() + dt.timedelta(days=340)).isoformat()
    expired = (dt.datetime.now(ZoneInfo('Asia/Baghdad')).date() - dt.timedelta(days=1)).isoformat()
    with TestClient(app) as c:
        def ok(response):
            assert response.status_code == 200, (response.status_code, response.text[:300])
            return response.json()
        ok(c.post('/api/login', json={'username':'enki', 'password':'123'}))
        csrf = ok(c.get('/api/me'))['csrf']
        headers = {'X-CSRF-Token':csrf}
        def item(name, annual):
            payload = {'name':name, 'trade_name':name, 'branch':'medication',
                 'category':'سجل الحبوب - قسم الصيدلة', 'unit':'حب',
                 'batch_no':f'CAT-{name}', 'expiry_date':future,
                 'price_dinars':5, 'price_fils_component':0}
            if annual is not None:
                payload['annual_need'] = annual
            return ok(c.post('/api/items', headers=headers, json=payload))['id']
        def receive(item_id, qty, batch, date=future):
            return ok(c.post('/api/movements', headers=headers,
                json={'kind':'IN','route':'purchase_receipt', 'source':'Demo Supplier',
                    'paper_ref':f'IN-{batch}', 'lines':[
                      {'item_id':item_id,'batch_no':batch,'expiry_date':date,
                       'qty':qty,'price_dinars':20,'price_fils_component':0}]}))
        ids={}
        for qty in (19,20,21,119,120,121,150,151):
            ids[f'qty{qty}'] = item(f'qty{qty}', 1200)  # Monthly requirement exactly 100
            receive(ids[f'qty{qty}'], qty, f'LOT-{qty}')
        ids['unknown_annual'] = item('unknown_annual', None)
        ids['frac120'] = item('frac120', 100)  # Monthly need 8.333...; qty10=120%
        ids['frac121'] = item('frac121', 100)
        receive(ids['frac120'], 10, 'FRACT-120')
        receive(ids['frac121'], 11, 'FRACT-132')
        ids['expired_stock'] = item('expired_stock', 1200)
        receive(ids['expired_stock'], 99, 'EXPIRED', expired)
        ids['no_stock'] = item('no_stock', 1200)
        r=ok(c.get('/api/positions'))
        scarce={x['name']:x for x in r['scarce']}
        surplus={x['name']:x for x in r['surplus']}
        assert r['scarce_pct']=='20' and r['surplus_pct']=='120' and r['percent_basis']=='monthly'
        assert {'qty19','expired_stock','no_stock'} <= scarce.keys(), scarce.keys()
        assert not ({'qty20','qty21'} & scarce.keys())
        assert {'qty121','qty150','qty151','frac121'} <= surplus.keys()
        assert 'qty120' not in surplus and 'frac120' not in surplus
        assert r['annual_need_unset_count'] == 1
        assert scarce['qty19']['monthly_need'] == 100.0
        assert scarce['qty19']['percent_of_monthly_need'] == 19.0
        assert scarce['expired_stock']['stock'] == 0 and scarce['expired_stock']['physical_stock'] == 99
        assert surplus['qty121']['percent_of_monthly_need'] == 121.0
        assert r['monthly_need_formula'] == 'annual_need / 12'
        custom=ok(c.get('/api/positions?scarce_pct=25&surplus_pct=150'))
        sc={x['name'] for x in custom['scarce']};su={x['name'] for x in custom['surplus']}
        assert {'qty19','qty20','qty21'} <= sc and 'qty25' not in sc
        assert 'qty150' not in su and 'qty151' in su
        assert custom['scarce_pct']=='25' and custom['surplus_pct']=='150'
        assert ok(c.get('/api/positions'))['scarce_pct']=='20', 'Custom filters must not change defaults on server'
        assert c.get('/api/positions?scarce_pct=0').status_code==422
        assert c.get('/api/positions?surplus_pct=1001').status_code==422
        assert ok(c.get('/api/health'))['release']=='4.22.0'
        print('PASS V4.15: defaults, custom %, exact 20/120 boundaries, fractional monthly need, expired vs usable, missing yearly need, release')
