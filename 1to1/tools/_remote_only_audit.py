#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_remote_only_audit.py —— 只读审计：GitHub main 上「清单外」文件的去向分类。

背景（R306 发现）：`_verify_remote_match.py` 报 1027/1027 清单文件与远端一致，
但有 540 个远端 blob 不在 `filelist.FILES` 清单内。必须分类：
  · 本地也存在  ⇒ **清单漂移**：`sync_mirror.py`（CNB 镜像）复用同一份清单
    ⇒ 这些文件**到不了 CNB 云工作区** ⇒ 云端复现可能缺文件（潜在坑，须记录）。
  · 本地已删     ⇒ 远端残留，无害（Git Data API 推送不会自动删远端条目）。
"""
import os, sys, json, urllib.request, ssl, inspect
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from filelist import FILES  # noqa: E402

REPO = "Lieguch/cubegm-build-monkey"
CTX = ssl._create_unverified_context()
TOK = os.environ.get("GITHUB_TOKEN") or (
    open(os.path.join(ROOT, ".pat"), encoding="utf-8").read().strip()
    if os.path.exists(os.path.join(ROOT, ".pat")) else "")


def gh(path):
    req = urllib.request.Request(
        "https://api.github.com/repos/%s%s" % (REPO, path),
        headers={"Authorization": "token " + TOK,
                 "User-Agent": "rkgame-verify"})
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    base = gh("/git/refs/heads/main")["object"]["sha"]
    tree = gh("/git/trees/%s?recursive=1" % base)
    REMOTE = {t["path"]: t["sha"] for t in tree.get("tree", [])
              if t.get("type") == "blob"}
    listed = {rem for _, rem in FILES}
    extra = [p for p in REMOTE if p.startswith("1to1/") and p not in listed]

    loc_exist = [p for p in extra
                 if os.path.exists(os.path.join(ROOT, p[len("1to1/"):]))]
    loc_missing = [p for p in extra
                   if not os.path.exists(os.path.join(ROOT, p[len("1to1/"):]))]

    print("remote main = %s ；远端 blob %d" % (base[:12], len(REMOTE)))
    print("清单外远端文件 = %d" % len(extra))
    print("  本地也存在（清单漂移 ⇒ CNB 镜像会漏）= %d" % len(loc_exist))
    print("  本地已删（远端残留，无害）            = %d" % len(loc_missing))

    def top(lst, n=10):
        c = Counter("/".join(p.split("/")[1:3]) if p.count("/") >= 2 else p
                    for p in lst)
        return c.most_common(n)

    print("\n[本地也存在] top dirs:")
    for d, c in top(loc_exist):
        print("   %-40s %d" % (d, c))
    print("\n[本地已删] top dirs:")
    for d, c in top(loc_missing):
        print("   %-40s %d" % (d, c))

    print("\n[本地也存在] 抽样:")
    for p in loc_exist[:12]:
        print("   %s" % p)
    print("\n[本地已删] 抽样:")
    for p in loc_missing[:12]:
        print("   %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
