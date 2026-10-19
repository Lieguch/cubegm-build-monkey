#!/usr/bin/env python3
"""给定 commit（可短 sha），列出该 commit 上所有 workflow run 的每个 job 状态。"""
import json
import ssl
import sys
import urllib.request

REPO = "Lieguch/cubegm-build-monkey"
CT = ssl._create_unverified_context()
TOK = open(".pat").read().strip()


def api(path):
    req = urllib.request.Request("https://api.github.com/repos/%s/%s" % (REPO, path))
    req.add_header("Authorization", "Bearer " + TOK)
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, context=CT) as r:
        return json.loads(r.read().decode("utf-8"))


ref = sys.argv[1]
full = api("commits/%s" % ref)["sha"]
print("full sha =", full)
runs = api("actions/runs?head_sha=%s&per_page=50" % full)
print("runs total =", runs.get("total_count"))
for r in runs.get("workflow_runs", []):
    print("\n== %s  %s/%s  run=%d" % (r["name"], r["status"], r["conclusion"], r["id"]))
    print("   url:", r["html_url"])
    jobs = api("actions/runs/%d/jobs?per_page=100" % r["id"])
    for j in jobs.get("jobs", []):
        print("   - %-52s %-9s %-9s job=%d"
              % (j["name"], j["status"], str(j["conclusion"]), j["id"]))
