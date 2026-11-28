#!/usr/bin/env python3
"""Check that optional, user-uploaded fonts are being served by the deployed IMS."""
import sys
import urllib.error
import urllib.request

if len(sys.argv) != 2 or not sys.argv[1].startswith('https://'):
    sys.exit('Usage: python check_font_deployment.py https://YOUR-RAILWAY-APP-DOMAIN')
base = sys.argv[1].rstrip('/')
for name in ('Alexandria-VariableFont_wght.ttf', 'CairoPlay-VariableFont_slntwght.ttf', 'ReadexPro-Regular.ttf', 'IBMPlexSansArabic-ExtraLight.ttf'):
    url = f'{base}/static/fonts/{name}?v=4271-local'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Range':'bytes=0-64'}),timeout=12) as resp:
            sig = resp.read(4)
            ok = sig in (b'\x00\x01\x00\x00', b'true', b'OTTO', b'typ1')
            print(f'{name}: {"OK" if ok else "WRONG FILE RESPONSE"} (HTTP {resp.status})')
    except (urllib.error.URLError,TimeoutError) as exc:
        print(f'{name}: NOT AVAILABLE — {exc}')
