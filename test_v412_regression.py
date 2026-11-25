"""V4.9 additive migration + searchable departments + outgoing lot price snapshots."""
import os, tempfile, json, zipfile, io, sqlite3
from fastapi.testclient import TestClient
from department_catalog import DEFAULT_DEPARTMENTS

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR'] = tmp
    from app import app, DB, init_db, SCHEMA_VERSION, APP_RELEASE
    assert SCHEMA_VERSION == 8 and APP_RELEASE == '4.13.0'
    with TestClient(app) as t:
        def good(r):
            assert r.status_code == 200, (r.status_code, r.text)
            return r.json()
        good(t.post('/api/login', json={'username':'enki','password':'123'}))
        h={'X-CSRF-Token':good(t.get('/api/me'))['csrf']}
        all_departments=good(t.get('/api/departments'))
        assert len(all_departments)==59
        assert set(x['name'] for x in all_departments) == set(DEFAULT_DEPARTMENTS)
        assert all(x['code'].startswith('DEP-') for x in all_departments)
        old=next(d for d in all_departments if d['name']=='وحدة المفراس')
        good(t.patch(f"/api/departments/{old['id']}",headers=h,json={'name':'وحدة المفراس الجديدة'}))
        good(t.post('/api/departments',headers=h,json={'name':'قسم مستحدث'}))
        init_db()  # repeated application restart must NOT recreate renamed default
        after=good(t.get('/api/departments'))
        assert len(after)==60 and 'وحدة المفراس' not in {x['name'] for x in after}
        assert 'وحدة المفراس الجديدة' in {x['name'] for x in after}
        # New item and two same-batch/different-priced incoming lots.
        new=good(t.post('/api/items',headers=h,json={
            'branch':'medication','category':'سجل الحبوب - قسم الصيدلة','name':'Ibuprofen',
            'trade_name':'Brufen','unit':'حب','batch_no':'LOT-2027','expiry_date':'2032-09-01',
            'price_dinars':1500,'price_fils_component':125}))
        iid=new['id']
        for price,qty in [(100,20),(250,12)]:
            good(t.post('/api/movements',headers=h,json={
                'kind':'IN','route':'purchase_receipt','paper_ref':f'REC-{price}','source':'مخزن أدوية',
                'lines':[{'item_id':iid,'batch_no':'LOT-2027','expiry_date':'2032-09-01','qty':qty,'price_dinars':1200,'price_fils_component':price}]}))
        lots=[x for x in good(t.get('/api/batches')) if x['item_id']==iid and x['on_hand']>0]
        assert len(lots)==2 and len({x['unit_price_fils'] for x in lots})==2
        lot=next(x for x in lots if x['unit_price_fils']==1200100)
        department=after[0]['id']
        draft={'kind':'OUT','route':'department_issue','department_id':department,'paper_ref':'REQ-115',
               'dispatch_ref':'DSP-115','lines':[{'item_id':iid,'batch_id':lot['id'],'qty':4,'price_dinars':1350,'price_fils_component':500}]}
        invalid={**draft,'lines':[{'item_id':iid+3,'batch_id':lot['id'],'qty':1,'price_dinars':1,'price_fils_component':0}]}
        assert t.post('/api/movements',headers=h,json=invalid).status_code==422
        after_bad=next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])
        assert after_bad['on_hand']==20
        invalid={**draft,'lines':[{'item_id':iid,'batch_id':lot['id'],'qty':400,'price_dinars':1,'price_fils_component':0}]}
        assert t.post('/api/movements',headers=h,json=invalid).status_code==409
        assert next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])['on_hand']==20
        issue=good(t.post('/api/movements',headers=h,json=draft))
        issued=next(m for m in good(t.get('/api/movements')) if m['id']==issue['id'])
        assert issued['lines'][0]['unit_price_fils']==1350500,issued
        assert next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])['unit_price_fils']==1200100
        assert next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])['on_hand']==16
        with sqlite3.connect(DB) as c:
            a=c.execute("select detail from audit_log where action='MOVEMENT_CREATED' order by id desc limit 1").fetchone()[0]
            assert json.loads(a)['outgoing_price_overrides']==1
        # A regular staff account must never issue another branch's stock, even
        # with a guessed batch ID or edited outgoing price fields.
        good(t.post('/api/users',headers=h,json={'username':'supplies_test','password':'PassWord01234',
              'full_name':'Medical Supplies Tester','role':'operator','branch':'medical_supplies'}))
        with TestClient(app) as employee:
            good(employee.post('/api/login',json={'username':'supplies_test','password':'PassWord01234'}))
            sh={'X-CSRF-Token':good(employee.get('/api/me'))['csrf']}
            denied=employee.post('/api/movements',headers=sh,json={**draft,'paper_ref':'X-BRANCH-ISSUE'})
            assert denied.status_code==403,(denied.status_code,denied.text)
        assert next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])['on_hand']==16
        # RETURN remains available only from incoming route, not from duplicate return form.
        restored=good(t.post('/api/movements',headers=h,json={
            'kind':'RETURN','route':'internal_return','department_id':department,'paper_ref':'REQ-115',
            'dispatch_ref':'RET-115','lines':[{'batch_id':lot['id'],'qty':2}]}))
        assert restored['code'].startswith('RET-')
        assert next(x for x in good(t.get('/api/batches')) if x['id']==lot['id'])['on_hand']==18
        # Explicit legacy clients that send only a batch_id continue to work.
        good(t.post('/api/movements',headers=h,json={**draft,'paper_ref':'OLD-REQ','lines':[{'batch_id':lot['id'],'qty':1}]}))
        # Exports and restores preserve renamed departments, batch prices, issue snapshots.
        backup=t.get('/api/backup/export');assert backup.status_code==200
        with zipfile.ZipFile(io.BytesIO(backup.content)) as z:
            assert json.loads(z.read('manifest.json'))['schema_version']==8
        good(t.post('/api/backup/restore',headers={**h,'X-Restore-Confirmation':'RESTORE'},files={'backup':('w.zip',backup.content,'application/zip')}))
        good(t.post('/api/login',json={'username':'enki','password':'123'}))
        deps=good(t.get('/api/departments'))
        assert len(deps)==60 and 'وحدة المفراس' not in {x['name'] for x in deps}
        assert next(m for m in good(t.get('/api/movements')) if m['id']==issue['id'])['lines'][0]['unit_price_fils']==1350500
        assert good(t.get('/api/health'))['release']=='4.13.0'
        js=good(t.get('/api/health'))
        assert js['version']==8
        html=t.get('/static/live.js').text
        assert 'data-issue-product' in html and 'data-issue-expiry' in html and 'data-dept-search' in html
        assert 'returnForm' not in html and 'deptOptions()' not in html
print('PASS V4.9: seeded 59, rename persists, new department, priced lots, outgoing price snapshots, rollback, restore, UI controls')
