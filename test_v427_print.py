"""V4.27: authenticated read-only statement print designer, unchanged warehouse schema."""
import os,tempfile
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as tmp:
 os.environ['WAREHOUSE_DATA_DIR']=tmp
 from app import app,APP_RELEASE,SCHEMA_VERSION
 assert APP_RELEASE=='4.27.1' and SCHEMA_VERSION==10
 with TestClient(app) as c:
  assert c.get('/print-report.html',follow_redirects=False).status_code==302
  assert c.get('/api/positions').status_code==401
  assert c.post('/api/login',json={'username':'enki','password':'123'}).status_code==200
  p=c.get('/print-report.html');assert p.status_code==200
  assert 'تصميم وطباعة المواقف' in p.text
  assert 'print-report.js' in p.text
  for x in ['print-report.js','print-report.css','ims-icon.png']:
   assert c.get('/static/'+x).status_code==200,x
  js=c.get('/static/print-report.js').text
  assert "'/api/positions'" in js and "'/api/items'" in js and "'/api/batches'" in js
  assert 'window.print()' in js
  assert 'near_expiry' in js and 'missing' in js and 'scarce' in js and 'surplus' in js
  assert c.get('/api/health').json()['release']=='4.27.1'
print('PASS V4.27: authenticated designer, assets, report API integration, A4 print, database untouched')
