#!/usr/bin/env python3
"""取 GitHub 上某 ref 的文件内容到本地路径。用法: _getfile.py <path> <ref> <out>"""
import base64
import json
import ssl
import sys
import urllib.request

REPO = "Lieguch/cubegm-build-monkey"
CT = ssl._create_unverified_context()
TOK = open(".pat").read().strip()

path, ref, out = sys.argv[1], sys.argv[2], sys.argv[3]
req = urllib.request.Request("https://api.github.com/repos/%s/contents/%s?ref=%s"
                             % (REPO, path, ref))
req.add_header("Authorization", "Bearer " + TOK)
req.add_header("Accept", "application/vnd.github+json")
with urllib.request.urlopen(req, context=CT) as r:
    d = json.loads(r.read().decode("utf-8"))
data = base64.b64decode(d["content"])
with open(out, "wb") as fh:
    fh.write(data)
print("%s @ %s -> %s (%d bytes)" % (path, ref, out, len(data)))
