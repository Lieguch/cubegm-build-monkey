import urllib.request, urllib.error, json, ssl, io, zipfile, sys, os

CT = ssl._create_unverified_context()
TOK = os.environ.get('GH_TOKEN', '')   # 从环境变量读取，禁止硬编码
REPO = 'Lieguch/cubegm-build-monkey'


class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CT), NoRedir())


def fetch(url, auth):
    h = {'User-Agent': 'x', 'Accept': 'application/vnd.github+json'}
    if auth:
        h['Authorization'] = 'Bearer ' + TOK
    req = urllib.request.Request(url, headers=h)
    try:
        with op.open(req, timeout=60) as x:
            return x.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            loc = e.headers.get('Location')
            r2 = urllib.request.Request(loc, headers={'User-Agent': 'x'})
            with urllib.request.urlopen(r2, timeout=180, context=CT) as x:
                return x.read()
        raise


run = sys.argv[1] if len(sys.argv) > 1 else '34497858658'
j = json.loads(fetch('https://api.github.com/repos/%s/actions/runs/%s/jobs' % (REPO, run), True))
jid = j['jobs'][0]['id']
print('job', jid, j['jobs'][0]['conclusion'])
d = fetch('https://api.github.com/repos/%s/actions/jobs/%s/logs' % (REPO, jid), True)
if d[:2] == b'PK':
    z = zipfile.ZipFile(io.BytesIO(d))
    txt = ''.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist())
else:
    txt = d.decode('utf-8', 'replace')
txt = txt.replace('\ufeff', '')
i = txt.find('原厂 stb_truetype')
if i < 0:
    i = txt.find('stb_truetype')
print(txt[max(0, i - 400):i + 2000] if i >= 0 else txt[-2500:])
