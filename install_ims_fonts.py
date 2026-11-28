"""Install open-source IMS fonts from Google Fonts at deployment time."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent / 'static' / 'fonts'
BASE = 'https://raw.githubusercontent.com/google/fonts/main/ofl/'
JOBS = [
 ('Alexandria.ttf', 'alexandria', ['Alexandria[wght].ttf']),
 ('ReadexPro.ttf', 'readexpro', ['ReadexPro[HEXP,wght].ttf','ReadexPro[wght].ttf']),
 *[(f'IBMPlexSansArabic-{s}.ttf','ibmplexsansarabic',[f'IBMPlexSansArabic-{s}.ttf']) for s in ('Regular','Medium','SemiBold','Bold')],
 *[(f'{family}-OFL.txt',family,['OFL.txt']) for family in ('alexandria','readexpro','ibmplexsansarabic')],
]
def valid(data, name):
    return (len(data)>1000 and (data[:4] in (b'\x00\x01\x00\x00',b'OTTO') if name.endswith('.ttf') else b'OPEN FONT LICENSE' in data.upper()))
def install(job):
    name, family, candidates = job
    dest = ROOT / name
    if dest.exists() and valid(dest.read_bytes(),name): return True
    for candidate in candidates:
        try:
            with urlopen(Request(BASE+family+'/'+quote(candidate),headers={'User-Agent':'IMS-font-installer/1'}),timeout=8) as r:
                data = r.read(8*1024*1024)
            if not valid(data,name): raise ValueError('Unexpected file content')
            tmp=dest.with_suffix(dest.suffix+'.tmp'); tmp.write_bytes(data); tmp.replace(dest)
            print('Installed', name, flush=True); return True
        except Exception as exc: print(f'{name}: {exc}', flush=True)
    return False
if __name__=='__main__':
    ROOT.mkdir(parents=True,exist_ok=True)
    with ThreadPoolExecutor(max_workers=9) as pool: results=list(pool.map(install,JOBS))
    print(f'IMS fonts: {sum(results)}/{len(results)} files ready; fallbacks remain available.',flush=True)
