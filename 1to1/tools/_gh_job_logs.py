#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_gh_job_logs.py —— 正确读取 GitHub Actions job 日志（R309c 根修，防复发）。

## 病灶（2026-11-04 实测）
`GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` 返回 **302**，
Location 指向 Azure Blob 的短期 SAS URL（`productionresultssa*.blob.core.windows.net/...?...&sig=...`）。
Python `urllib` 默认跟随重定向时**会把 GitHub 的 `Authorization: Bearer` 头带到 Azure**，
Azure 用 SAS 认证、遇到 Bearer 就回：
    401 / Server: Microsoft-HTTPAPI/2.0 / <Code>InvalidAuthenticationInfo</Code>
    Server failed to authenticate the request. Please refer to the www-authenticate header.
历史记录把这条 401 误记成「本机 FastGithub 代理拦截（302 → 401）」，
后续轮次**直接沿用、零验证**，导致日志被误判为"读不到"，把一个 GitHub 服务端 500
（`[remote rejected] artifacts -> artifacts (Internal Server Error)`）晾了整轮。

## 修法（单变量对照已证）
不跟随重定向；拿到 Location 后用**不带任何认证头**的裸 GET 请求 SAS URL。
实测：同一 SAS URL 裸 GET = 200 / 306,068 B / 3128 行；带 Authorization = 401。

## 用法
  python3 tools/_gh_job_logs.py <run_id> [--out <file>] [--grep <keyword>] [--repo <owner/repo>]
  python3 tools/_gh_job_logs.py 41812275114 --grep "remote rejected"
token 来源：`GITHUB_TOKEN` 环境变量或仓库根 `.pat`（不入库）。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

REPO = "Lieguch/cubegm-build-monkey"
API = "https://api.github.com"


def token(root):
    t = os.environ.get("GITHUB_TOKEN", "")
    if t:
        return t
    p = os.path.join(root, ".pat")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    raise SystemExit("找不到 GitHub token：设 GITHUB_TOKEN 或创建 .pat")


def hdr(tok):
    return {"Authorization": "Bearer " + tok,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "wb-gh-job-logs"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """拦下 302，保存 Location；不自动跟随。"""

    def __init__(self):
        self.location = None

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.location = newurl
        return None


def get_json(path, tok):
    r = urllib.request.Request(API + path, headers=hdr(tok))
    with urllib.request.urlopen(r, timeout=60) as f:
        return json.load(f)


def job_logs(run_id, tok, repo):
    jobs = get_json("/repos/%s/actions/runs/%s/jobs" % (repo, run_id), tok)
    if not jobs.get("jobs"):
        raise SystemExit("run %s 没有 job" % run_id)
    job = jobs["jobs"][0]
    nr = NoRedirect()
    op = urllib.request.build_opener(nr)
    url = "%s/repos/%s/actions/jobs/%s/logs" % (API, repo, job["id"])
    try:
        op.open(urllib.request.Request(url, headers=hdr(tok)), timeout=60)
        raise SystemExit("未返回 302（日志可能已内联返回）")
    except urllib.error.HTTPError as e:
        if e.code != 302:
            raise SystemExit("job logs 端点返回 %s（期望 302）" % e.code)
        loc = e.headers.get("Location") or nr.location
    if not loc:
        raise SystemExit("302 无 Location")
    print("302 -> %s" % loc.split("?")[0])
    # ★ 关键：裸 GET，绝不带 Authorization
    req = urllib.request.Request(loc, headers={"User-Agent": "wb-gh-job-logs"})
    with urllib.request.urlopen(req, timeout=120) as f:
        txt = f.read().decode("utf-8", "replace")
        status = f.status
    return job, status, txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_id")
    ap.add_argument("--out")
    ap.add_argument("--grep")
    ap.add_argument("--repo", default=REPO)
    a = ap.parse_args()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tok = token(root)
    job, status, txt = job_logs(a.run_id, tok, a.repo)
    lines = txt.splitlines()
    print("job = %s (%s) | status = %s | %d B / %d 行"
          % (job["id"], job["name"][:40], status, len(txt.encode("utf-8")), len(lines)))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(txt)
        print("已保存:", a.out)
    if a.grep:
        hits = [l for l in lines if a.grep.lower() in l.lower()]
        print("=== grep %r：%d 命中 ===" % (a.grep, len(hits)))
        for l in hits[:40]:
            print("  ", l[:200])
    return 0


if __name__ == "__main__":
    sys.exit(main())
