#!/usr/bin/env python3
"""
ci_watch.py — CI 监控器：轮询指定 commit 的 workflow runs 直到完成，输出 job 级结果。

用法:
  python3 tools/ci_watch.py <commit_sha> [--timeout 3600] [--interval 60]
退出码: 0 = 全部 success；2 = 有 failure/cancelled；1 = 参数错误

需要环境变量 GITHUB_TOKEN（或本地 .pat 文件）。
"""
import json
import os
import ssl
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = "Lieguch/cubegm-build-monkey"


def tok():
    t = os.environ.get("GITHUB_TOKEN")
    if t:
        return t.strip()
    p = os.path.join(ROOT, ".pat")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    raise SystemExit("缺少 GITHUB_TOKEN / .pat")


CTX = ssl._create_unverified_context()


def get(p):
    r = urllib.request.Request("https://api.github.com/repos/%s/%s" % (REPO, p),
                               headers={"Authorization": "Bearer " + tok(),
                                        "Accept": "application/vnd.github+json",
                                        "User-Agent": "1to1-ci"})
    return json.loads(urllib.request.urlopen(r, context=CTX, timeout=60).read())


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 1
    sha = a[0]
    timeout = int(a[a.index("--timeout") + 1]) if "--timeout" in a else 3600
    interval = int(a[a.index("--interval") + 1]) if "--interval" in a else 60
    t0 = time.time()
    done = False
    while time.time() - t0 < timeout:
        runs = get("actions/runs?head_sha=%s&per_page=20" % sha)
        rows = runs.get("workflow_runs", [])
        if rows and all(r["status"] == "completed" for r in rows):
            done = True
            break
        st = ", ".join("%s:%s" % (r["name"], r["status"]) for r in rows)
        print("[%4ds] %s" % (time.time() - t0, st or "(尚无 run)"), flush=True)
        time.sleep(interval)

    runs = get("actions/runs?head_sha=%s&per_page=20" % sha)
    L = []
    A = L.append
    A("=" * 72)
    A("CI 结果  commit %s" % sha[:12])
    A("=" * 72)
    overall = "success"
    for r in runs.get("workflow_runs", []):
        A("%-18s %-12s %s" % (r["name"], r["conclusion"], r["html_url"]))
        if r["conclusion"] not in ("success", "skipped"):
            overall = "failure"
            for j in get("actions/runs/%s/jobs?per_page=50" % r["id"]).get("jobs", []):
                A("   job %-38s %s" % (j["name"], j["conclusion"]))
                for s in j.get("steps", []):
                    if s["conclusion"] not in ("success", "skipped", None):
                        A("      step %-40s %s" % (s["name"], s["conclusion"]))
    txt = "\n".join(L) + "\n"
    sys.stdout.write(txt)
    os.makedirs(os.path.join(ROOT, "report"), exist_ok=True)
    open(os.path.join(ROOT, "report", "ci_watch.txt"), "w", encoding="utf-8").write(txt)
    return 0 if (done and overall == "success") else 2


if __name__ == "__main__":
    sys.exit(main())
