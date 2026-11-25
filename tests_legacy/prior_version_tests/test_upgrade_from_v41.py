"""Real V4.1 database upgrade and V4.1 backup restore regression test."""
import importlib.util,os,sqlite3,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
HERE=Path(__file__).resolve().parent
V41=HERE/'tests_legacy'/'v41_app.py'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
with tempfile.TemporaryDirectory() as path:
    os.environ['WAREHOUSE_DATA_DIR']=path
    os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
    old=load('v41_upgrade_test',V41)
    with TestClient(old.app) as c:
        assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        h={'X-CSRF-Token':c.get('/api/me').json()['csrf']}
        r=c.post('/api/items',headers=h,json={'sku':'OLD01','name':'Old item','category':'Drugs','unit':'vial'})
        assert r.status_code==200,r.text
        item=r.json()['id']
        m=c.post('/api/movements',headers=h,json={'kind':'IN','paper_ref':'OLDIN','source':'old supplier',
          'lines':[{'item_id':item,'batch_no':'OLDLOT','expiry_date':'2028-06-30','qty':12}]})
        assert m.status_code==200,m.text
        acc=c.post('/api/users',headers=h,json={'username':'oldmanager','full_name':'Manager Old','role':'manager','password':'OldGood123'})
        assert acc.status_code==200,acc.text
        backup=c.get('/api/backup/export').content
    new=load('v42_upgrade_test',HERE/'app.py')
    with TestClient(new.app) as c:
        assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        h={'X-CSRF-Token':c.get('/api/me').json()['csrf']}
        record=c.get('/api/items').json()[0]
        assert record['stock']==12 and record['branch'] is None
        assigned=c.patch('/api/items/'+str(item),headers=h,json={'sku':'OLD01','name':'Old item','category':'سجل الحياتية - قسم الصيدلة','branch':'medication','unit':'vial','trade_name':'Old trade','batch_no':'OLDLOT','expiry_date':'2028-06-30'})
        assert assigned.status_code==200,assigned.text
        updated=c.get('/api/items').json()[0]
        assert updated['branch']=='medication' and updated['stock']==12
        user=next(u for u in c.get('/api/users').json() if u['username']=='oldmanager')
        assert user['branch'] is None
        assert c.patch('/api/users/'+str(user['id']),headers=h,json={'role':'manager','branch':'medical_supplies','is_active':True}).status_code==200
        assert c.post('/api/backup/restore',headers={**h,'X-Restore-Confirmation':'RESTORE'},
          files={'backup':('v41.zip',backup,'application/zip')}).status_code==200
        assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
        recovered=c.get('/api/items').json()[0]
        assert recovered['stock']==12 and recovered['branch'] is None
        assert c.get('/api/health').json()['version']==4
    with sqlite3.connect(Path(path)/'warehouse.sqlite3') as db:
        assert db.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()[0]=='4'
    print('PASS: V4.1 -> V4.2 in-place migration, legacy item assignment, historical stock, V4.1 backup restore')
