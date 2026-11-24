"""Security and migration tests for one-branch-per-employee warehouse permissions.
Run: python test_branches.py
"""
import os
import tempfile
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as path:
    os.environ['WAREHOUSE_DATA_DIR'] = path
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY', None)
    from app import app
    with TestClient(app) as admin:
        assert admin.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        info=admin.get('/api/me').json()
        assert info['role']=='admin' and info['branch'] is None
        a={'X-CSRF-Token':info['csrf']}
        dep=admin.post('/api/departments',headers=a,json={'code':'ER','name':'Emergency'})
        assert dep.status_code==200,dep.text
        dept=dep.json()['id']
        def item(sku, branch, category):
            return {'sku':sku,'name':sku+' (scientific)','generic_name':'Generic',
                    'manufacturer':'Supplier','category':category,'unit':'box','branch':branch,
                    'information':'local alias, alternative'}
        ids={}
        for b in ('medication','medical_supplies','surgical_instruments'):
            books={'medication':'سجل الحياتية - قسم الصيدلة','medical_supplies':'سجل النبيذة - قسم الصيدلة','surgical_instruments':'سجل الفاتورة'}
            r=admin.post('/api/items',headers=a,json=item(b.upper(),b,books[b]))
            assert r.status_code==200,r.text
            ids[b]=r.json()['id']
        assert admin.post('/api/items',headers=a,json=item('NO_BRANCH',None,'x')).status_code==422
        assert admin.post('/api/items',headers=a,json=item('INVALID','medical','x')).status_code==422
        for b,iid in ids.items():
            r=admin.post('/api/movements',headers=a,json={'kind':'IN','paper_ref':'RECEIPT-'+b,
                   'source':'Test supplier','lines':[{'item_id':iid,'batch_no':'B-'+b,'expiry_date':'2029-12-01','qty':40}]})
            assert r.status_code==200,r.text
        batches={b['branch']:b['id'] for b in admin.get('/api/batches').json()}
        assert set(batches)==set(ids)
        assert admin.post('/api/users',headers=a,json={'username':'nobranch','full_name':'Unassigned',
               'password':'TestPW123','role':'manager'}).status_code==422
        for name,role,branch in [('med_manager','manager','medication'),('med_operator','operator','medication'),
                                 ('surgical_manager','manager','surgical_instruments')]:
            r=admin.post('/api/users',headers=a,json={'username':name,'full_name':name,
                                 'role':role,'branch':branch,'password':'TestPW123'})
            assert r.status_code==200,r.text
        user_id={u['username']:u['id'] for u in admin.get('/api/users').json()}
        assert next(u for u in admin.get('/api/users').json() if u['username']=='med_manager')['branch']=='medication'
        with TestClient(app) as staff:
            assert staff.post('/api/login',json={'username':'med_manager','password':'TestPW123'}).status_code==200
            u=staff.get('/api/me').json();h={'X-CSRF-Token':u['csrf']}
            assert u['branch']=='medication'
            assert staff.post('/api/items',headers=h,json=item('ONLY_MED','medication','سجل الحياتية - قسم الصيدلة')).status_code==200
            assert staff.post('/api/items',headers=h,json=item('NO_SURG','surgical_instruments','سجل الحياتية - قسم الصيدلة')).status_code==403
            assert staff.patch('/api/items/'+str(ids['surgical_instruments']),headers=h,
                               json=item('HACK','medication','سجل الحياتية - قسم الصيدلة')).status_code==403
            assert staff.patch('/api/items/'+str(ids['medication']),headers=h,
                               json=item('MOVE_BRANCH','surgical_instruments','سجل الحياتية - قسم الصيدلة')).status_code==403
            assert staff.patch('/api/items/'+str(ids['medication']),headers=h,
                               json=item('MODIFIED_MED','medication','سجل الحياتية - قسم الصيدلة')).status_code==200
            assert staff.post('/api/movements',headers=h,json={'kind':'IN','paper_ref':'NO_ACCESS','source':'Supplier',
                               'lines':[{'item_id':ids['medical_supplies'],'batch_no':'B-OTHER','qty':5}]}).status_code==403
            assert staff.post('/api/movements',headers=h,json={'kind':'OUT','paper_ref':'OTHER','department_id':dept,
                               'lines':[{'batch_id':batches['surgical_instruments'],'qty':1}]}).status_code==403
            assert staff.post('/api/movements',headers=h,json={'kind':'RETURN','paper_ref':'OTHER','department_id':dept,
                               'lines':[{'batch_id':batches['surgical_instruments'],'qty':1}]}).status_code==403
            assert staff.post('/api/movements',headers=h,json={'kind':'ADJUST_MINUS','paper_ref':'OTHER',
                               'notes':'Test denial','lines':[{'batch_id':batches['surgical_instruments'],'qty':1}]}).status_code==403
            # Mixed movements must be wholly rolled back: no partial deduction.
            r=staff.post('/api/movements',headers=h,json={'kind':'OUT','paper_ref':'MIXED','department_id':dept,
                               'lines':[{'batch_id':batches['medication'],'qty':2},
                                        {'batch_id':batches['surgical_instruments'],'qty':2}]})
            assert r.status_code==403,r.text
            assert next(b for b in staff.get('/api/batches').json() if b['id']==batches['medication'])['on_hand']==40
            assert staff.post('/api/movements',headers=h,json={'kind':'OUT','paper_ref':'REAL','department_id':dept,
                               'lines':[{'batch_id':batches['medication'],'qty':3}]}).status_code==200
            assert staff.get('/api/users').status_code==403
            # An admin reassigns the branch; current session is revoked and a new login uses the new scope.
            r=admin.patch('/api/users/'+str(user_id['med_manager']),headers=a,
                json={'role':'manager','branch':'medical_supplies','is_active':True})
            assert r.status_code==200,r.text
            assert staff.get('/api/me').status_code==401
            assert staff.post('/api/login',json={'username':'med_manager','password':'TestPW123'}).status_code==200
            h={'X-CSRF-Token':staff.get('/api/me').json()['csrf']}
            assert staff.post('/api/items',headers=h,json=item('OLD_BRANCH','medication','سجل الحياتية - قسم الصيدلة')).status_code==403
            assert staff.post('/api/items',headers=h,json=item('NEW_BRANCH','medical_supplies','سجل النبيذة - قسم الصيدلة')).status_code==200
        # Even admins cannot reclassify items after activity has been recorded.
        assert admin.patch('/api/items/'+str(ids['medication']),headers=a,
                          json=item('MOVE_ADMIN','medical_supplies','سجل النبيذة - قسم الصيدلة')).status_code==409
        download=admin.get('/api/backup/export')
        assert download.status_code==200
        assert download.content.startswith(b'PK')
        r=admin.post('/api/backup/restore',headers={**a,'X-Restore-Confirmation':'RESTORE'},
                     files={'backup':('test.zip',download.content,'application/zip')})
        assert r.status_code==200,r.text
        assert admin.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        assert next(i for i in admin.get('/api/items').json() if i['id']==ids['medication'])['category']=='سجل الحياتية - قسم الصيدلة'
    print('PASS: three branches, staff scope, multi-line atomicity, account reassignment, admin protections, backup roundtrip')
