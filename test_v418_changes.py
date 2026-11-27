"""V4.18 account profile, administrative permissions and UI contract smoke tests."""
import os,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
root=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as tmp:
 os.environ['WAREHOUSE_DATA_DIR']=tmp
 from app import app,SCHEMA_VERSION,APP_RELEASE
 assert (SCHEMA_VERSION,APP_RELEASE)==(9,'4.23.0')
 with TestClient(app) as t:
  def ok(r):assert r.status_code==200,(r.status_code,r.text[:400]);return r.json()
  ok(t.post('/api/login',json={'username':'enki','password':'123'}))
  csrf=ok(t.get('/api/me'))['csrf'];head={'X-CSRF-Token':csrf}
  created=ok(t.post('/api/users',json={'username':'tester418','full_name':'Test Profile','password':'strongPassword123','role':'viewer','branch':'medication'},headers=head))
  uid=created['id'];assert ok(t.get(f'/api/users/{uid}/profile'))['email'] in (None,'')
  assert 'password_hash' not in ok(t.get(f'/api/users/{uid}/profile'))
  ok(t.get('/api/audit'))
  ok(t.post('/api/logout',headers=head))
  ok(t.post('/api/login',json={'username':'tester418','password':'strongPassword123'}))
  assert t.get(f'/api/users/{uid}/profile').status_code==403
  assert t.get('/api/audit').status_code==403
  assert 'staff' not in ok(t.get('/api/profile'))
  csrf=ok(t.get('/api/me'))['csrf']
  ok(t.patch('/api/profile',headers={'X-CSRF-Token':csrf},json={'full_name':'Changed','email':'tester@example.test','phone':'07701234567','age':30,'job_title':'Warehouse officer'}))
  assert ok(t.get('/api/profile'))['email']=='tester@example.test'
  ok(t.post('/api/change-password',headers={'X-CSRF-Token':csrf},json={'current_password':'strongPassword123','new_password':'newSecurePassword321'}))
  assert t.get('/api/users').status_code==403
  ok(t.post('/api/logout',headers=head|{'X-CSRF-Token':csrf}))
  ok(t.post('/api/login',json={'username':'enki','password':'123'}))
  assert ok(t.get(f'/api/users/{uid}/profile'))['phone']=='07701234567'
  assert 'password_hash' not in ok(t.get(f'/api/users/{uid}/profile'))
 js=(root/'static/live.js').read_text();html=(root/'static/dashboard.html').read_text()
 for phrase in ('data-issue-expiry-picker','data-issue-same-date-lot','data-qty-warning','function openNotifications','data-user-details','function syncIssueExpiry'):
  assert phrase in js,phrase
 assert 'Return home</a>' not in html
 assert 'id="notificationModal"' in html
 assert 'id="passwordForm"' in js
 assert '4.23.0' in html
 print('PASS V4.18: profile admin access, password changes, audit authorization, UI selectors and version')
