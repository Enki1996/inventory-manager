"""V4.5 regression checks for branch-dependent Add Item form and books."""
import os, tempfile, json
from pathlib import Path
from fastapi.testclient import TestClient
from book_catalog import BOOKS_BY_BRANCH
from unit_catalog import UNITS_BY_BRANCH

ROOT=Path(__file__).resolve().parent
js=(ROOT/'static/live.js').read_text()
form=js[js.index('function editItem(it=null){'):js.index('function syncItemBranchFields(',js.index('function editItem(it=null){'))]
labels=['Warehouse branch','Trade name','Scientific name','Item name','Stock unit',
        'Book / register category','Batch number','Expiration date','Manufacture date (optional)',
        'Manufacturer company','Information / alternate names']
positions=[form.index("field('"+label+"'") for label in labels]
assert positions==sorted(positions),'Add Item code labels are not in requested order'
assert 'name="sku"' not in form,'SKU should be generated, not an Add Item input'
assert 'name="expiry_date" class="db-input" type="date" required' in form
assert 'data-med-trade' in form and 'data-med-scientific' in form and 'data-other-name' in form
assert 'window.HWLang?.apply()' in form
assert 'form.classList.add(\'item-form-grid\')' in form
assert 'V4.5' in form
assert len(BOOKS_BY_BRANCH['medication']) == 11
assert len(BOOKS_BY_BRANCH['medical_supplies']) == 7
assert len(BOOKS_BY_BRANCH['surgical_instruments']) == 2
assert 'سجل المغذيات - قسم الصيدلة' in BOOKS_BY_BRANCH['medication']
assert UNITS_BY_BRANCH['medication']==('حب','كبسول','بطل','امبول','فيال','انبوب','تحاميل','قطرات')
assert UNITS_BY_BRANCH['medical_supplies']==('قطعة','كيس','بطل','باكة','رولة','باكيت','درزن')
assert UNITS_BY_BRANCH['surgical_instruments']==('قطعة',)
assert all(v in json.loads((ROOT/'static/locales/ar.json').read_text()) for v in labels)
assert '?v=4.5.0' in (ROOT/'static/dashboard.html').read_text()

with tempfile.TemporaryDirectory() as tmp:
 os.environ['WAREHOUSE_DATA_DIR']=tmp
 os.environ.pop('WAREHOUSE_PUBLIC_DEPLOY',None)
 from app import app
 with TestClient(app) as client:
  assert client.get('/api/health').json()['release']=='4.5.0'
  assert client.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
  csrf={'X-CSRF-Token':client.get('/api/me').json()['csrf']}
  assert 'سجل المغذيات - قسم الصيدلة' in client.get('/api/books').json()['medication']
  p={'branch':'medication','name':'Paracetamol','trade_name':'Tylenol','unit':'حب',
     'category':'سجل المغذيات - قسم الصيدلة','batch_no':'PAR-B001','expiry_date':'2030-08-01',
     'manufacturer':'Example Labs','information':'بنادول','generic_name':'Legacy scientific synonym'}
  r=client.post('/api/items',json=p,headers=csrf)
  assert r.status_code==200,r.text
  iid=r.json()['id']
  before=next(i for i in client.get('/api/items').json() if i['id']==iid)
  assert before['generic_name']=='Legacy scientific synonym'
  # UI v4.5 does not display the older generic-name input. It must NOT erase the field.
  update={k:v for k,v in p.items() if k!='generic_name'}
  update['trade_name']='Updated Brand'
  r=client.patch('/api/items/'+str(iid),json=update,headers=csrf)
  assert r.status_code==200,r.text
  after=next(i for i in client.get('/api/items').json() if i['id']==iid)
  assert after['generic_name']=='Legacy scientific synonym' and after['trade_name']=='Updated Brand'
  for bad in [dict(p,expiry_date=''),dict(p,unit='قطعة'),dict(p,category='سجل الفاتورة')]:
   r=client.post('/api/items',json=bad,headers=csrf)
   assert r.status_code==422,r.text
  # A different branch may not take the new medication book.
  q={'branch':'medical_supplies','name':'Gloves','unit':'قطعة','category':'سجل المغذيات - قسم الصيدلة',
     'batch_no':'G001','expiry_date':'2030-09-01'}
  assert client.post('/api/items',json=q,headers=csrf).status_code==422
print('PASS V4.5: form order, fields/units, book count, mandatory expiry, saved legacy data, cache release marker')
