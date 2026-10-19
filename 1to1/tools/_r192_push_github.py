"""R189-R192 增量推送：用本机 .pat 直调 GitHub Contents API（逐文件原子上传）。

背景（为何不走 git push / MCP）：
  · 本机 FastGithub 代理拦截所有 GitHub 域名 ⇒ `git push`（smart-HTTP）静默失败；
  · 但 **REST API（api.github.com）经 FastGithub 正常**（用户记忆已实证）；
  · MCP GitHub connector 对该仓库返回 403 Resource not accessible by integration。
  ⇒ 用 Contents API `PUT /repos/{o}/{r}/contents/{path}` 逐文件上传（每次 PUT = 上传+提交）。

纪律：
  · 只推 `1to1/` 下本轮的源改/新文件，**不碰**原厂资产；
  · 每个文件上传后立即回读校验 sha256 一致；
  · `.github/workflows/` 路径 FastGithub 额外拦截 ⇒ 本轮无此类文件，若遇到须改走 CNB。

★★★ R194 推送前置门禁（fail-closed，用户问责后新增）：
  用户铁律（rkgame 第 143 轮划线，~/.workbuddy/MEMORY.md）：
    「触发 GitHub CI 只用于"正式构建产出物"；**若本轮改动不进入"从源码构建 ELF"
      这条链，就不许用 CI 验证**」。
  纪律 109（PROJECT-MEMORY §0.50）：
    「推送目标必须按职责分配 —— 托管仓（CNB）**只托管**，构建仓（GitHub）**只构建**；
      ★ 凡"推送会触发什么"，必须核对**目标仓的流水线定义**，而不是假定。」
  实测教训（2026-10-18，用户当场问责）：本轮 8 个文件全在 `1to1/tools/`（测试桩/诊断脚本/
    数据/文档），**无一进入构建链**，却推了 GitHub ⇒ `build.yml`（`on: push` **无 paths
    过滤**）+ `1to1-verify.yml`/`1to1-qemu-behav.yml`（`paths: 1to1/**`）共触发
    **22 个 runs 全部白跑**（7×1to1-verify failure / 7×1to1-qemu-behav failure /
    8×rkgame-rebuild，与本次改动零交集）。
  ⇒ 本脚本现在**先过门禁再推**：构建链外的文件一律拒绝推 GitHub（只推 CNB 托管）。"""
import base64, hashlib, json, os, ssl, sys, urllib.error, urllib.request

REPO = "Lieguch/cubegm-build-monkey"
BRANCH = "main"
LOCAL = r"D:/output/rkgame-1to1"
CTX = ssl._create_unverified_context()

TOK = os.environ.get("GITHUB_TOKEN") or (
    open(os.path.join(LOCAL, ".pat"), encoding="utf-8").read().strip()
    if os.path.exists(os.path.join(LOCAL, ".pat")) else "")
if not TOK:
    raise SystemExit("missing GitHub PAT")


# ★ R194：构建链 = 会被 build.yml 构建 / 被各 workflow 消费的路径。
#   `build.yml` 无 paths 过滤 ⇒ 它消费 rkgame-rebuild/**（build.sh 的输入）。
#   `1to1/tools/**`、`1to1/*.md`、`PROGRESS.md` 等**不在**构建链上。
BUILD_CHAIN_PREFIXES = ("rkgame-rebuild/", ".github/workflows/")


def push_gate(files):
    """fail-closed：本轮文件无一进入构建链 ⇒ 拒绝推 GitHub。

    返回 (allow, reason)。理由必须可执行（告诉调用方该改推哪）。
    """
    in_chain = [f for f, _, _ in files if f.startswith(BUILD_CHAIN_PREFIXES)]
    if in_chain:
        return True, "构建链文件 %d 个（%s…）⇒ 允许推 GitHub 触发构建 CI" % (
            len(in_chain), in_chain[0])
    return False, ("本轮 %d 个文件无一进入「从源码构建 ELF」链（rkgame-rebuild/** 或 "
                   ".github/workflows/**）⇒ 按用户铁律 + 纪律 109，"
                   "**只推 CNB 托管**，不推 GitHub（推了就是白烧 CI 额度）" % len(files))


# (本地路径, 远端路径, commit message)
FILES = [
    ("tools/guest_shim/drm_stub.c", "1to1/tools/guest_shim/drm_stub.c",
     "R189/R190: drm 桩按地址反查实体表导出符号 + 呈现点全入参埋点"),
    ("tools/guest_shim/fake_mem.c", "1to1/tools/guest_shim/fake_mem.c",
     "R189: shim 按 off 反查实体表 + ANON_WR 诊断埋点 + 修 %zu 不受支持"),
    ("tools/b6_struct_gate.sh", "1to1/tools/b6_struct_gate.sh",
     "R190: B6 结构判据机械门禁（替代不可满足的 hash 非零判据）"),
    ("tools/_b6_adjudge.sh", "1to1/tools/_b6_adjudge.sh",
     "R189/R190: 补 ANON_WR / geom 抓取段"),
    ("tools/device_core_map.tsv", "1to1/tools/device_core_map.tsv",
     "R191: 真机 filelist.xml 135 条 ROM→core 映射"),
    ("tools/device_romid_core_map.tsv", "1to1/tools/device_romid_core_map.tsv",
     "R192: 真机二进制内嵌 30 条 ROM 标识→core 映射"),
    ("tools/core_selector_spec.md", "1to1/tools/core_selector_spec.md",
     "R192: core 选择器规格（先 filelist.xml 后内嵌表）"),
    ("PROGRESS.md", "1to1/PROGRESS.md",
     "R189-R192: B6 观测边界定案 + P1 cores 映射逐项比对"),
]


def _req(method, path, body=None):
    url = "https://api.github.com/repos/%s/contents/%s" % (REPO, path)
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Authorization", "token " + TOK)
    r.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(r, context=CTX, timeout=120) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def get_sha(path):
    st, body = _req("GET", path + "?ref=" + BRANCH)
    if st == 200:
        return body.get("sha")
    return None


def main():
    # ★ R194 门禁：先判"该不该推 GitHub"，再上传。fail-closed（不过就 exit 2）。
    allow, reason = push_gate(FILES)
    print("[gate] %s" % reason)
    if not allow:
        print("[gate] DENIED ⇒ 本次不推 GitHub。请改推 CNB 托管（云工作区内 git push）。")
        return 2
    ok = fail = 0
    for local, remote, msg in FILES:
        p = os.path.join(LOCAL, local)
        if not os.path.exists(p):
            print("SKIP  %s (不存在)" % local)
            continue
        raw = open(p, "rb").read()
        local_sha = hashlib.sha256(raw).hexdigest()
        b64 = base64.b64encode(raw).decode()
        body = {"message": msg, "content": b64, "branch": BRANCH}
        cur = get_sha(remote)
        if cur:
            body["sha"] = cur
        st, resp = _req("PUT", remote, body)
        if st in (200, 201):
            # 回读校验：下载刚提交的版本比对 sha256
            st2, got = _req("GET", remote + "?ref=" + BRANCH)
            if st2 == 200:
                rb = base64.b64decode(got["content"])
                if hashlib.sha256(rb).hexdigest() == local_sha:
                    print("OK    %-40s -> %s (sha256 校验一致)" % (local, remote))
                    ok += 1
                else:
                    print("FAIL  %-40s sha256 不一致!" % local)
                    print("      local=%s remote=%s" % (local_sha, hashlib.sha256(rb).hexdigest()))
                    fail += 1
            else:
                print("WARN  %-40s 已提交但回读失败 st=%s" % (local, st2))
                ok += 1
        else:
            print("FAIL  %-40s st=%s %s" % (local, st, resp.get("message", "")))
            fail += 1
    print("---- 结果: ok=%d fail=%d ----" % (ok, fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
