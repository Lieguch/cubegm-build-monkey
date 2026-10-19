#!/usr/bin/env python3
"""全量导出某个 workflow run 的所有 job 日志（不截断），并打印失败步骤摘要。

用法: python tools/_fulllog.py <run_id> [outdir]
本机 FastGithub 环境：urllib + 不校验 SSL + NoRedirect 取 Location。
"""
import io
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
import zipfile

CT = ssl._create_unverified_context()
TOK = os.environ.get('GH_TOKEN', '') or open('.pat').read().strip()
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


run = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else '/tmp'
jobs = json.loads(fetch('https://api.github.com/repos/%s/actions/runs/%s/jobs?per_page=100'
                        % (REPO, run), True))
for j in jobs.get('jobs', []):
    jid, name, concl = j['id'], j['name'], j['conclusion']
    d = fetch('https://api.github.com/repos/%s/actions/jobs/%s/logs' % (REPO, jid), True)
    if d[:2] == b'PK':
        z = zipfile.ZipFile(io.BytesIO(d))
        txt = ''.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist())
    else:
        txt = d.decode('utf-8', 'replace')
    txt = txt.replace('\ufeff', '')
    safe = ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)[:40]
    path = os.path.join(outdir, 'log_%s_%d.txt' % (safe, jid))
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    print('job %d %-40s %-9s  %d bytes -> %s' % (jid, name[:40], str(concl), len(txt), path))

    # 失败步骤摘要
    cur = ''
    errs = []
    for ln in txt.splitlines():
        s = ln.split('Z ', 1)[1] if 'Z ' in ln[:30] else ln
        if s.startswith('##[error]'):
            errs.append((cur, s[len('##[error]'):].strip()))
        elif s.startswith('Run ') or s.startswith('##[group]Run '):
            cur = s.replace('##[group]', '').strip()
        elif s.startswith('##[endgroup]'):
            pass
    if errs:
        print('   !! %d 条 ##[error]' % len(errs))
        for c, e in errs[:20]:
            print('      [%s] %s' % (c[:60], e[:160]))
