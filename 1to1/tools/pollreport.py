import urllib.request, urllib.error, json, ssl, sys, time, os

CT = ssl._create_unverified_context()
TOK = os.environ.get('GH_TOKEN', '')   # 从环境变量读取，禁止硬编码
REPO = 'Lieguch/cubegm-build-monkey'


class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=CT), NR())


def api(path, raw=False):
    r = urllib.request.Request('https://api.github.com/repos/%s/%s' % (REPO, path),
                               headers={'Accept': 'application/vnd.github+json',
                                        'User-Agent': 'x', 'Authorization': 'Bearer ' + TOK})
    try:
        with op.open(r, timeout=60) as x:
            b = x.read()
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            loc = e.headers.get('Location')
            with urllib.request.urlopen(urllib.request.Request(loc, headers={'User-Agent': 'curl/8'}),
                                        timeout=180, context=CT) as x:
                b = x.read()
        else:
            raise
    return b if raw else json.loads(b)


sha = sys.argv[1]
mark = sys.argv[2] if len(sys.argv) > 2 else None
rid = None
for _ in range(40):
    for r in api('actions/runs?per_page=8')['workflow_runs']:
        if r['head_sha'].startswith(sha) and r['name'] == '1to1-verify':
            rid = r['id']
            break
    if rid:
        break
    time.sleep(6)
print('run', rid)
for _ in range(60):
    j = api('actions/runs/%d/jobs' % rid)
    st = [(x['status'], str(x.get('conclusion'))) for x in j['jobs']]
    if all(s[0] == 'completed' for s in st):
        print('DONE', st)
        break
    time.sleep(8)
jid = j['jobs'][0]['id']
t = api('actions/jobs/%d/logs' % jid, True)
if t[:2] == b'PK':
    import io, zipfile
    z = zipfile.ZipFile(io.BytesIO(t))
    t = ''.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist()).encode()
t = t.decode('utf-8', 'replace').replace('\ufeff', '')
i = t.find('原厂 stb_truetype 可比函数')
if i < 0:
    i = t.find('结构语义指纹')
print(t[max(0, i - 200):i + 1600] if i >= 0 else t[-2200:])
