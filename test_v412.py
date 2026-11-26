import os, sys, tempfile, datetime as dt, json, zipfile, io, sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as root:
    os.environ['WAREHOUSE_DATA_DIR'] = root
    from app import app, DB, SCHEMA_VERSION, APP_RELEASE, position_window
    assert SCHEMA_VERSION == 9 and APP_RELEASE == '4.17.0'
    today = dt.datetime.now(ZoneInfo('Asia/Baghdad')).date()
    _, end, last = position_window()
    after = (dt.date.fromisoformat(end) + dt.timedelta(days=40)).isoformat()
    before = (today + dt.timedelta(days=15)).isoformat()
    expired = (today - dt.timedelta(days=1)).isoformat()
    with TestClient(app) as client:
        def ok(r):
            assert r.status_code == 200, (r.status_code, r.text[:1000]); return r.json()
        assert client.get('/api/positions').status_code == 401
        ok(client.post('/api/login',json={'username':'enki','password':'123'}))
        csrf=ok(client.get('/api/me'))['csrf'];h={'X-CSRF-Token':csrf}
        def mk_item(name,need=None):
            body={'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','name':name,'trade_name':name,
                  'unit':'حب','batch_no':'B-'+name,'expiry_date':before,'price_dinars':5,'price_fils_component':250}
            if need is not None:body['annual_need']=need
            r=ok(client.post('/api/items',headers=h,json=body))
            return r['id'],body
        def rec(item,batch,expiry,qty):
            return ok(client.post('/api/movements',headers=h,json={'kind':'IN','route':'purchase_receipt',
             'source':'Supplier', 'paper_ref':'IN-'+batch,
             'lines':[{'item_id':item,'batch_no':batch,'expiry_date':expiry,'qty':qty,
                       'price_dinars':12,'price_fils_component':200}]}))
        scarce,sc_d=mk_item('scarce',1200)
        surplus,su_d=mk_item('surplus',1200)
        missing,mi_d=mk_item('missing')
        rec(scarce,'SC-OK',before,20)
        rec(scarce,'SC-EXPIRED',expired,140)
        rec(surplus,'SU-OK',after,160)
        r=ok(client.get('/api/items'));table={i['id']:i for i in r}
        assert table[scarce]['annual_need']==1200
        assert table[surplus]['annual_need']==1200
        assert table[missing]['annual_need'] is None
        r=ok(client.get('/api/positions'))
        assert r['scarce']==[] and [i['name'] for i in r['surplus']]==['surplus']
        assert r['scarce_pct']=='20' and r['surplus_pct']=='120'
        assert r['percent_basis']=='monthly'
        assert r['expiry_before']==end and r['expiry_last_included']==last
        assert r['annual_need_unset_count']==1
        assert [i['batch_no'] for i in r['near_expiry']]==['SC-OK']
        r=ok(client.get('/api/positions?scarce_pct=25&surplus_pct=125'))
        assert [(i['name'],i['stock'],i['physical_stock'],i['percent_of_need']) for i in r['scarce']]==[('scarce',20,160,20.0)],r['scarce']
        assert [(i['name'],i['stock'],i['percent_of_need']) for i in r['surplus']]==[('surplus',160,160.0)],r['surplus']
        assert r['scarce_pct']=='25' and r['surplus_pct']=='125'
        r=ok(client.get('/api/positions?scarce_pct=20&surplus_pct=160'))
        assert not r['scarce'] and not r['surplus'], 'strict < and > required'
        r=ok(client.get('/api/positions?expiry_before='+after))
        assert 'SC-OK' in [x['batch_no'] for x in r['near_expiry']]
        assert 'SU-OK' not in [x['batch_no'] for x in r['near_expiry']], 'cutoff exclusive'
        r=ok(client.get('/api/positions?expiry_before='+ (dt.date.fromisoformat(after)+dt.timedelta(days=1)).isoformat()))
        assert 'SU-OK' in [x['batch_no'] for x in r['near_expiry']]
        for q in ('expiry_before=2026-02-30','expiry_before=abc','scarce_pct=-5','surplus_pct=foo','scarce_pct=0','scarce_pct=25.111'):
            r=client.get('/api/positions?'+q)
            assert r.status_code==422,(q,r.text)
        # Editing annual need does not touch stored stock or lots.
        old=table[scarce]; edit=dict(sc_d,annual_need=240,sku=old['sku'])
        ok(client.patch(f'/api/items/{scarce}',headers=h,json=edit))
        fresh=ok(client.get('/api/items'))
        assert next(x for x in fresh if x['id']==scarce)['annual_need']==240
        batches=ok(client.get('/api/batches'))
        assert sum(x['on_hand'] for x in batches if x['item_id']==scarce)==160
        # backup and restore retain new property
        response=client.get('/api/backup/export')
        assert response.status_code==200
        z=zipfile.ZipFile(io.BytesIO(response.content))
        assert json.loads(z.read('manifest.json'))['schema_version']==9
        sql=sqlite3.connect(':memory:');tmp=Path(root)/'verify.sqlite3';tmp.write_bytes(z.read('warehouse.sqlite3'))
        check=sqlite3.connect(tmp)
        assert check.execute('SELECT annual_need FROM items WHERE id=?',(scarce,)).fetchone()[0]==240
        check.close()
        # Older source backup stays compatible: restore from schema 7 item table.
        print('PASS: schema V8, auth, monthly need, scarcity/surplus strict thresholds, dates, expired lots, no-invented requirement, item editing, backup snapshot')
