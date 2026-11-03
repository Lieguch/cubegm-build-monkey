#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_verify_remote_match.py —— **只读**核对：本地工作区 vs GitHub main（权威线）。

为什么需要（R306 发现）：
  本地 git `master` HEAD 停在 R282（`5a9919f6`），而工作区内容已是 R305f 态
  （1347 个条目相对 HEAD 为 modified/untracked）⇒ **本地 git 历史不是真源**。
  权威线是 GitHub main（`1e41a1c8d35f`，经 Git Data API 推送）。
  ⇒ 必须证明"工作区内容 ≡ GitHub main"，否则下游一切结论都建在沙上。

与 `push_1to1.py` 的关系：
  push 脚本的"无变更早退"分支正是这个判据，但它**在存在差异时会真的推送**。
  本脚本只发 GET（ref/commit/tree），绝不 POST ⇒ 可安全用于核对。

铁律复用：清单规则只写一处 —— 直接 import `tools/filelist.py`（同一份 FILES）。
"""
import os, sys, json, hashlib, urllib.request, ssl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from filelist import FILES, is_build_artifact  # noqa: E402

REPO = "Lieguch/cubegm-build-monkey"
CTX = ssl._create_unverified_context()
TOK = os.environ.get("GITHUB_TOKEN") or (
    open(os.path.join(ROOT, ".pat"), encoding="utf-8").read().strip()
    if os.path.exists(os.path.join(ROOT, ".pat")) else "")


def gh(path):
    req = urllib.request.Request(
        "https://api.github.com/repos/%s%s" % (REPO, path),
        headers={"Authorization": "token " + TOK,
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "rkgame-verify"})
    with urllib.request.urlopen(req, context=CTX, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if not TOK:
        raise SystemExit("missing token: set GITHUB_TOKEN or create .pat")

    ref = gh("")            # repo metadata -> default_branch
    base = None
    try:
        head = gh("/git/refs/heads/main")
        base = head["object"]["sha"]
    except Exception as e:
        print("!! 取 main ref 失败: %s" % e)
        raise SystemExit(2)
    print("remote main = %s" % base[:12])

    tree = gh("/git/trees/%s?recursive=1" % base)
    REMOTE = {t["path"]: t["sha"] for t in tree.get("tree", [])
              if t.get("type") == "blob"}
    print("远端 blob 数 = %d" % len(REMOTE))

    keep = [(rel, rem) for rel, rem in FILES if not is_build_artifact(rel)]
    same, diff, gone, extra = [], [], [], []   # extra: 远端有、清单无

    for rel, rem in keep:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            gone.append(rem)
            continue
        data = open(p, "rb").read()
        # 与 push_1to1.py 同一口径：文本类提交前统一 LF
        if rel.endswith((".sh", ".yml", ".S", ".ld")) and b"\r\n" in data:
            data = data.replace(b"\r\n", b"\n")
        loc = hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()
        if REMOTE.get(rem) == loc:
            same.append(rem)
        else:
            diff.append((rem, REMOTE.get(rem, "<absent>")[:12], loc[:12]))

    listed = {rem for _, rem in keep}
    # 远端 1to1/ 下不在本次清单里的 blob（可能是已被移除的文件，或清单漏项）
    for rp in REMOTE:
        if rp.startswith("1to1/") and rp not in listed:
            extra.append(rp)

    print("\n=== 结论文本（可贴入 PROGRESS.md） ===")
    print("清单文件 %d ：一致 %d / 不一致 %d / 本地缺失 %d" %
          (len(keep), len(same), len(diff), len(gone)))
    if diff:
        print("不一致明细：")
        for rem, r, l in diff:
            print("   %-56s remote=%s local=%s" % (rem, r, l))
    if gone:
        print("本地缺失（清单列了但磁盘上没有）：")
        for rem in gone:
            print("   %s" % rem)
    if extra:
        print("远端多出（不在清单内，需人工判断是否清单漂移）：%d 个" % len(extra))
        for rp in extra[:25]:
            print("   %s" % rp)
    if not diff and not gone:
        print("VERIFY %d/%d blobs match（工作区 ≡ GitHub main %s）"
              % (len(keep), len(keep), base[:12]))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
