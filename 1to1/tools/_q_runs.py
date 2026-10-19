#!/usr/bin/env python3
"""列出某 commit 上所有 workflow run 的状态（本机 FastGithub 环境专用：urllib + 不校验 SSL）。"""
import json
import ssl
import sys
import urllib.request

REPO = "Lieguch/cubegm-build-monkey"
CT = ssl._create_unverified_context()


def api(path):
    tok = open(".pat").read().strip()
    req = urllib.request.Request("https://api.github.com/repos/%s/%s" % (REPO, path))
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, context=CT) as r:
        return json.loads(r.read().decode("utf-8"))


sha = sys.argv[1]
d = api("commits/%s/check-runs?per_page=100" % sha)
print("commit %s  check-runs=%d" % (sha[:12], d.get("total_count")))
for c in d.get("check_runs", []):
    print("  %-28s %-12s %s" % (c["name"], c["status"] + "/" + str(c["conclusion"]), c["html_url"]))

d2 = api("actions/runs?head_sha=%s&per_page=100" % sha)
print("workflow-runs total=%d" % d2.get("total_count"))
for r in d2.get("workflow_runs", []):
    print("  %-24s %-12s %s  %s" % (r["name"], r["status"] + "/" + str(r["conclusion"]),
                                    r["head_sha"][:12], r["html_url"]))
