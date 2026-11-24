"""V4.3 official book/register integration and server authorization tests.
Run locally on a disposable SQLite database: python test_books.py
"""
import os
import tempfile
from fastapi.testclient import TestClient
from book_catalog import BOOKS_BY_BRANCH

assert len(BOOKS_BY_BRANCH['medication']) == 10
assert len(BOOKS_BY_BRANCH['medical_supplies']) == 7
assert len(BOOKS_BY_BRANCH['surgical_instruments']) == 2

with tempfile.TemporaryDirectory() as tmp:
    os.environ['WAREHOUSE_DATA_DIR'] = tmp
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY', None)
    from app import app, db

    with TestClient(app) as admin:
        assert admin.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        csrf={'X-CSRF-Token':admin.get('/api/me').json()['csrf']}
        resp=admin.get('/api/books');assert resp.status_code==200,resp.text
        assert resp.json()=={key:list(names) for key,names in BOOKS_BY_BRANCH.items()}

        def item(branch,book,sku):
            return {'branch':branch,'category':book,'name':'Example '+sku,'sku':sku,'unit':'box'}

        all_ids=[]
        for branch, books in BOOKS_BY_BRANCH.items():
            for idx,book in enumerate(books):
                r=admin.post('/api/items',headers=csrf,json=item(branch,book,f'{branch}-{idx}'))
                assert r.status_code==200,(branch,book,r.status_code,r.text)
                all_ids.append(r.json()['id'])
        assert len(all_ids)==19
        assert len(admin.get('/api/items').json())==19

        # Reject newly typed books and a book belonging to a different branch.
        bad=admin.post('/api/items',headers=csrf,json=item('medication','سجل الحياتية','MED-BAD'))
        assert bad.status_code==422,bad.text
        bad=admin.post('/api/items',headers=csrf,json=item('medication',BOOKS_BY_BRANCH['medical_supplies'][0],'MED-CROSS'))
        assert bad.status_code==422,bad.text
        bad=admin.post('/api/items',headers=csrf,json=item('surgical_instruments',BOOKS_BY_BRANCH['medication'][0],'SURG-CROSS'))
        assert bad.status_code==422,bad.text
        bad=admin.patch('/api/items/'+str(all_ids[0]),headers=csrf,json=item('medical_supplies',BOOKS_BY_BRANCH['medication'][0],'EDIT-BAD'))
        assert bad.status_code==422,bad.text
        assert len(admin.get('/api/items').json())==19  # rejected requests leave no records

        # A legacy V4.2 free-text category remains visible and unchanged until reclassified.
        with db() as c:
            c.execute('INSERT INTO items(sku,name,category,branch,unit,created_at) VALUES (?,?,?,?,?,?)',
                      ('LEGACY-1','Legacy stock','سجل قديم غير معتمد','medication','piece','2026-01-01'))
        legacy=next(x for x in admin.get('/api/items').json() if x['sku']=='LEGACY-1')
        assert legacy['category']=='سجل قديم غير معتمد'
        # A legacy category cannot be re-saved; employee must choose a valid book first.
        r=admin.patch(f"/api/items/{legacy['id']}",headers=csrf,json=item('medication','سجل قديم غير معتمد','LEGACY-1'))
        assert r.status_code==422
        r=admin.patch(f"/api/items/{legacy['id']}",headers=csrf,json=item('medication',BOOKS_BY_BRANCH['medication'][5],'LEGACY-1'))
        assert r.status_code==200,r.text

        u=admin.post('/api/users',headers=csrf,json={'username':'bookstaff','full_name':'Book Staff',
          'password':'BookPW1234','role':'manager','branch':'medical_supplies'})
        assert u.status_code==200,u.text
        with TestClient(app) as staff:
            assert staff.post('/api/login',json={'username':'bookstaff','password':'BookPW1234'}).status_code==200
            h={'X-CSRF-Token':staff.get('/api/me').json()['csrf']}
            ok=staff.post('/api/items',headers=h,json=item('medical_supplies',BOOKS_BY_BRANCH['medical_supplies'][1],'STAFF-GOOD'))
            assert ok.status_code==200,ok.text
            denied=staff.post('/api/items',headers=h,json=item('medication',BOOKS_BY_BRANCH['medication'][1],'STAFF-DENIED'))
            assert denied.status_code==403,denied.text
            denied=staff.post('/api/items',headers=h,json=item('medical_supplies',BOOKS_BY_BRANCH['medication'][1],'STAFF-CROSS'))
            assert denied.status_code==422,denied.text

        # Backup export / restore retains official books, stock categories and past records.
        saved=admin.get('/api/backup/export')
        assert saved.status_code==200,saved.text
        restored=admin.post('/api/backup/restore',headers={**csrf,'X-Restore-Confirmation':'RESTORE'},
           files={'backup':('test-v43.zip',saved.content,'application/zip')})
        assert restored.status_code==200,restored.text
        assert admin.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        rows=admin.get('/api/items').json()
        assert len(rows)==21  # 19 official, one reclassified legacy, one staff addition
        assert any(x['sku']=='LEGACY-1' and x['category']==BOOKS_BY_BRANCH['medication'][5] for x in rows)
print('PASS: 19 books, branch-book matching, staff permissions, legacy records, backup restore')
