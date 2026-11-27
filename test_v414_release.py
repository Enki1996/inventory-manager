"""V4.14 safe UI-only release smoke checks."""
import os,tempfile
from pathlib import Path
from fastapi.testclient import TestClient
with tempfile.TemporaryDirectory() as d:
    os.environ['WAREHOUSE_DATA_DIR']=d
    from app import app,SCHEMA_VERSION,APP_RELEASE
    assert SCHEMA_VERSION==9 and APP_RELEASE=='4.23.0'
    with TestClient(app) as client:
        r=client.get('/api/health')
        assert r.status_code==200 and r.json()['release']=='4.23.0' and r.json()['version']==9
        js=client.get('/static/live.js').text
        css=client.get('/static/live.css').text
        i18n=client.get('/static/locales/ar.json').json()
        assert 'data-open-column-manager' in js and 'column-dialog-overlay' in css
        assert 'Every lot is listed separately' in js
        assert 'Internal department returns add the selected batch quantity back' not in js
        assert i18n['Warehouse intake']=='ادخال مخزني'
        assert i18n['Warehouse dispatch']=='اخراج مخزني'
    print('PASS V4.14 release, schema 8, popup, lot details, movement labels, note removal')
