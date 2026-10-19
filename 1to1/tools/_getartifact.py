#!/usr/bin/env python3
"""下载某个 workflow run 的 artifact zip（本机 FastGithub：NoRedirect + 无 auth 跟 Location）。

用法: python tools/_getartifact.py <artifact_id> <outdir>
"""
import io
import os
import ssl
import sys
import urllib.error
import urllib.request
import zipfile

CT = ssl._create_unverified_context()
TOK = open('.pat').read().strip()
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


aid, outdir = sys.argv[1], sys.argv[2]
d = fetch('https://api.github.com/repos/%s/actions/artifacts/%s/zip' % (REPO, aid), True)
z = zipfile.ZipFile(io.BytesIO(d))
os.makedirs(outdir, exist_ok=True)
z.extractall(outdir)
print('下载 %d B -> %s' % (len(d), outdir))
for n in z.namelist():
    print('   %-60s %d B' % (n, z.getinfo(n).file_size))
