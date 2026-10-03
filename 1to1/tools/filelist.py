#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filelist.py —— **文件清单的唯一真源**（无任何token）。

★ 为什么要有这个模块（2026-10-03 第 121 轮，判据见 FILELIST-TOOLCHAIN.md）：
  `push_1to1.py` 的 `EXCLUDE = {'tools/push_1to1.py'}`（脚本自身含 token，永不推送）
  ⇒ **它不会同步到云端/远端**；
  而 `sync_mirror.py` 的 `file_list()` 复用 `push_1to1.py --list-only` 取清单
  ⇒ **在云工作区必然失败**（实测：`can't open file .../push_1to1.py`）。
  这是**结构性循环依赖**，不是偶发。

★ 根治：把挑选规则抽到这里（本文件**不含 token** ⇒ 可入库、可上云），
  由 `push_1to1.py`（GitHub）与 `sync_mirror.py`（CNB 镜像）**共同 import**
  ⇒ 规则仍只写一处（纪律：同一规则禁止写两处），两边不会漂移，
  同时循环依赖解除。

用法：
    python3 tools/filelist.py --list-only        # 打印 FILELIST 头 + 每行 "rel\tremote"
    python3 -c "import sys;sys.path.insert(0,'tools');import filelist;print(len(filelist.build()))"
"""
import os, re, sys

LOCAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 远端前缀：镜像到 CNB/GitHub 时，本仓内容挂在 `1to1/` 下
REMOTE_PREFIX = '1to1'

FILES = [
    ("README.md",                      "1to1/README.md"),
    ("STATUS.md",                      "1to1/STATUS.md"),
    # ★★ 差距分析报告：仓库根的文件**不在**下面的 os.walk 目录里（src/upstream/ledger/tools/docs/linker）
    #   ⇒ 必须显式登记，否则**静默漏推**（本轮实测：GAP.md 首次推送被漏，靠"上传 5 个 blob"里没有它才发现）。
    ("GAP.md",                         "1to1/GAP.md"),
    # ★ 替代差距评估报告（2026-09-21）：回答"还差多少能直接替代" —— 供跨 agent 交接。
    ("GAP-TO-REPLACEMENT.md",          "1to1/GAP-TO-REPLACEMENT.md"),
    # ★ 路线决策（2026-09-22）：回答"是否在转圈 / 根本性方向"；根级文件不在 walk 目录，
    #   不显式登记就会**静默漏推**（同 GAP.md 的坑）。
    ("ROUTE-DECISION.md",              "1to1/ROUTE-DECISION.md"),
    # ★ 设备端诊断仪工程手册（2026-09-21）：设备无命令行 ⇒ 只能靠自写日志取信息。
    ("DIAG-RUNBOOK.md",                "1to1/DIAG-RUNBOOK.md"),
    # ★★★ 项目**权威长期记忆**（2026-09-22 由工作记忆迁入）：
    #   为什么迁：`D:\output\.workbuddy\memory\MEMORY.md` 每轮被自动注入且限 ~3,000 字符，
    #   超长**从尾部静默截断** ⇒ 导致反复压缩、丢上下文、做出错误判断（用户明确要求迁出）。
    #   本文件在**项目文件夹内**，不受注入限制 ⇒ **只增不删、不再压缩**。
    ("PROJECT-MEMORY.md",              "1to1/PROJECT-MEMORY.md"),
    # ★ 根级逐日日志同样**不在** walk 目录内 ⇒ 必须显式登记（同 GAP.md 的坑）。
    ("2026-09-17.md",                  "1to1/2026-09-17.md"),
    ("2026-09-18.md",                  "1to1/2026-09-18.md"),
    ("2026-09-19.md",                  "1to1/2026-09-19.md"),
    ("2026-09-20.md",                  "1to1/2026-09-20.md"),
    ("2026-09-21.md",                  "1to1/2026-09-21.md"),
    ("2026-09-22.md",                  "1to1/2026-09-22.md"),
    ("2026-09-23.md",                  "1to1/2026-09-23.md"),
    ("tools/getjoblog.py",             "1to1/tools/getjoblog.py"),
    ("tools/pollreport.py",            "1to1/tools/pollreport.py"),
    ("tools/behav_capture.sh",         "1to1/tools/behav_capture.sh"),
    ("tools/behav_diff.py",            "1to1/tools/behav_diff.py"),
    ("tools/abi_check.py",             "1to1/tools/abi_check.py"),
    ("docs/verification-strategy.md",  "1to1/docs/verification-strategy.md"),
    ("tools/funcdump.py",              "1to1/tools/funcdump.py"),
    ("tools/funcdiff.py",              "1to1/tools/funcdiff.py"),
    ("tools/structsig.py",             "1to1/tools/structsig.py"),
    ("tools/vermatch.py",              "1to1/tools/vermatch.py"),
    ("tools/stb_range.py",             "1to1/tools/stb_range.py"),
    ("tools/extract_factory_funcs.py", "1to1/tools/extract_factory_funcs.py"),
    ("tools/build_workspace.py",       "1to1/tools/build_workspace.py"),
    ("tools/ci_p2a_stb.py",            "1to1/tools/ci_p2a_stb.py"),
    ("tools/elf_syms.py",              "1to1/tools/elf_syms.py"),
    ("tools/link_audit.py",            "1to1/tools/link_audit.py"),
    ("tools/link_audit.sh",            "1to1/tools/link_audit.sh"),
    ("ledger/functions.csv",           "1to1/ledger/functions.csv"),
    ("golden/factory.funcs.json.gz",   "1to1/golden/factory.funcs.json.gz"),
    # ★ 2026-09-24：Ghidra 逐函数原始 C 语料（812 文件 / 3.3 MB / 打包 253 KB）。
    #   它是 tools/src_transcript_parity.py 门禁的**权威对照**；原先是本机绝对路径 ⇒
    #   CI 上 FileNotFoundError ⇒ 门禁红。仓内化后必须在这里**显式登记**：
    #   golden/ 刻意不参与 walk（原厂只读资产、人工控制），不登记就会被**静默漏推**。
    ("golden/ghidra-perfn.tar.gz",     "1to1/golden/ghidra-perfn.tar.gz"),
    # ★ P5 行为差分的**参考端**：差分要求两侧在同一环境各跑一次，
    #   拿到本地工厂指纹去比 CI 重建指纹等于在比环境差异 —— 故工厂二进制必须入库。
    #   （与 golden/ 里的指纹同源；3.9 MB，sha256 见 STATUS.md）
    ("golden/factory.rkgame.bin",      "1to1/golden/factory.rkgame.bin"),
    # ★ P5 最小真机环境（原厂 SD 只读拷贝）：工厂 rkgame 用 /proc/self/exe 的目录当
    #   work_path 拼出 setting.xml / cores/config.xml / menu.log / joystick.zip 等路径。
    #   差分必须两侧**同一路径**跑，故这层环境要随仓库走；带 MANIFEST.sha256 核验，
    #   防止"环境被悄悄换掉"导致差分结论失真。（共 ~355 KB；ui_*.zip/font.ttf 等
    #   数 MB 的大件不需要 —— 启动阶段不会走到 main_Menu。）
    ("golden/sdcard_min/MANIFEST.sha256",  "1to1/golden/sdcard_min/MANIFEST.sha256"),
    ("golden/sdcard_min/setting.xml",      "1to1/golden/sdcard_min/setting.xml"),
    ("golden/sdcard_min/menu.log",         "1to1/golden/sdcard_min/menu.log"),
    ("golden/sdcard_min/favorites.lst",    "1to1/golden/sdcard_min/favorites.lst"),
    ("golden/sdcard_min/recent.lst",       "1to1/golden/sdcard_min/recent.lst"),
    ("golden/sdcard_min/fileinfo",         "1to1/golden/sdcard_min/fileinfo"),
    ("golden/sdcard_min/joystick.zip",     "1to1/golden/sdcard_min/joystick.zip"),
    ("golden/sdcard_min/cores/config.xml", "1to1/golden/sdcard_min/cores/config.xml"),
    # ★ main_Menu() 的第一批动作就需要这两个：mui_LoadSetting() 读 cores/filelist.xml、
    #   mui_InitFont() 读 font.ttf（缺 font.ttf 会打印 "Open font file failed." 并**提前 return**，
    #   于是后面所有字体调用都跑在未初始化的 font 结构上 ⇒ 观测窗口在菜单入口就断掉）。
    #   两侧加载同一份 ⇒ 差分公平。
    ("golden/sdcard_min/cores/filelist.xml", "1to1/golden/sdcard_min/cores/filelist.xml"),
    ("golden/sdcard_min/font.ttf",         "1to1/golden/sdcard_min/font.ttf"),
    # ★ main_Menu() 实测在 `open <work>/ui_cn.zip fail` 处**停住**（setting.xml 的
    #   `<ui filename="ui_cn.zip" gamelist="1"/>` + language=1 ⇒ 菜单要这个包里的资源与字体）；
    #   音频同理来自 setting.xml 的 `<sound>`（BGM + 两个音效）。缺哪个都会在日志里显形。
    ("golden/sdcard_min/ui_cn.zip",        "1to1/golden/sdcard_min/ui_cn.zip"),
    ("golden/sdcard_min/chord.wav",        "1to1/golden/sdcard_min/chord.wav"),
    ("golden/sdcard_min/Button1.wav",      "1to1/golden/sdcard_min/Button1.wav"),
    ("golden/sdcard_min/Back_In_The_City.mp3", "1to1/golden/sdcard_min/Back_In_The_City.mp3"),
    # ★ 真机环境完整性：rkgame 会 dlopen("<work_path>/driver.so")。缺文件时它会打印
    #   `open driver.so fail` 并跳过图形/驱动初始化 ⇒ 可观测窗口极浅（env 缺陷，不是实现差异）。
    #   两侧加载**同一份** ⇒ 差分仍是"同环境比实现"。
    ("golden/sdcard_min/driver.so",        "1to1/golden/sdcard_min/driver.so"),
    (".github/workflows/1to1-verify.yml", ".github/workflows/1to1-verify.yml"),
    (".github/workflows/1to1-qemu-behav.yml", ".github/workflows/1to1-qemu-behav.yml"),
    # ★ 2026-09-28：仓库根 `.cnb.yml`（CNB 云原生构建的声明式流水线）。
    #   为什么必须显式登记：CNB **只读仓库根**的 `.cnb.yml`；本项目镜像到
    #   `lieguch/cubeGM` 时其余文件都带 `1to1/` 前缀 ⇒ 不登记就永远不会被 CNB 读到。
    #   本文件新增了 `1to1-linux-gates` 流水线（手动/API 触发），用于跑**本机跑不了**
    #   的 11 道门禁（依赖 arm-linux-gnueabihf-objdump / readelf）。
    (".cnb.yml", ".cnb.yml"),
    # ★ 判决实验（2026-09-23）：GCC vs clang 谁更接近工厂。
    #   ⚠ 坑：walk 目录**不含** `.github`，而 `_validate_yaml()` 是 glob 全部 workflow
    #   ⇒ 会出现"YAML 自检通过 3 个文件，但只上传 2 个 blob"的**静默漏推**。
    #   新增 workflow 必须在这里**显式登记**，否则推上去也永远不会触发。
    (".github/workflows/gcc-vs-clang-fidelity.yml",
     ".github/workflows/gcc-vs-clang-fidelity.yml"),
    # ★ 第 66 轮：工具链 A/B 判决（**用行为尺 diff_exec 判**，取代旧的体积/直方图代理指标）。
    #   同上一行的坑：新增 workflow 必须显式登记，否则推上去也永不触发。
    (".github/workflows/toolchain-ab.yml",
     ".github/workflows/toolchain-ab.yml"),
]

# ★ 可执行位是「执行语义」的一部分，不是元数据。
#   github 树条目默认 100644 ⇒ git 检出后是 0644 ⇒ qemu-user 对不可执行目标
#   会走 execve 回退 → EACCES → **静默 exit 1、零输出、零 syscall**（曾误判整轮）。
#   凡是要在 CI 里被执行的仓库文件，必须在树里标成 100755。
MODE755 = {"1to1/golden/factory.rkgame.bin"}

# ★ 根治「新建文件忘了登记」这类 bug：递归纳入 src/ ledger/ tools/ docs/ 全部文件。
#   并内置 token 自检 —— 含 ghp_ 的文件一律不推送（避免 GitHub 422 密钥拦截）。
EXCLUDE = {'tools/push_1to1.py'}          # 本脚本自身含 token，永不推送
# ★ 2026-10-02（第 117 轮 P0）：**目录级**排除。`src/upstream/libiconv-legacy-stub/` 是遗留手写桩
#   （`iconv_engine.c` 自称"简化核心引擎"，不参与编译，编译入口用 `libiconv17/`），
#   不入库以免与远端既有 `libiconv/` 产生 251 文件冗余。
EXCLUDE_DIRS = {'src/upstream/libiconv-legacy-stub'}

# ★★★ 2026-10-03（第 121 轮，FILELIST-TOOLCHAIN.md F2）：**token 自检从"裸子串"改为"token 形状"**。
#   病灶（实测）：原规则是 `if b'ghp_' in content: skip`
#   ⇒ **任何"需要写出检测串"的工具都会被自己误杀**
#   （本轮 `filelist.py` 因为规则里写着字面量，被判成"含 token"而**拒绝入库**，
#     于是它上不了云 ⇒ 循环依赖根本没解除 ⇒ 修复无效）。
#   判据（与历史行为等价且更准）：GitHub PAT 有**固定形状**
#     Classic  `ghp_/gho_/ghu_/ghs_/ghr_` + 36位base62
#     Fine-grained `github_pat_` + 22位base62 + `_` + 59位base62
#   实测：`filelist.py` 按形状 **0 命中**（按裸子串 3 命中，全是字面量）⇒ 判定正确。
_TOKEN_RE = re.compile(rb'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}')

def has_real_token(path):
    """文件里是否含**真实形态**的 GitHub token（而非规则里引用的字面量）。"""
    try:
        with open(path, 'rb') as fh:
            return _TOKEN_RE.search(fh.read()) is not None
    except OSError:
        return False

# ★★ 2026-09-29（§0.33）：**跳过规则只写一处**。
#   病灶（结构性）：同一条"构建产物不入库"的规则此前**同时写在两处** ——
#   `--list-only` 的 `_skip` 与 `upload_one()` 的 if。只改一处就产生
#   "清单说会推 / 实际不推"（或反之）的**静默漂移**，而这正是历史上"漏推/多发"的源头。
#   现在两处都调用 `is_build_artifact()`，规则只有一份。
_BAD_EXT = (".pyc", ".o", ".bin.tmp")


def is_build_artifact(rel):
    """`rel` 是否为**不入库**的文件（构建产物 / 备份 / 缓存）。

    ★ 2026-09-29 新增 `.bak_` 判据：我在调试仪器时用
      `cp tools/diff_exec.py tools/diff_exec.py.bak_premachine` 之类造了几个备份，
      它们出现在 `--list-only` 清单里 —— **调试垃圾差点被推上仓库**。
      **纪律：备份一律放 `build/_exp/`，不放 `tools/`。**
    """
    if "__pycache__" in rel or rel.endswith(_BAD_EXT):
        return True
    for _d in EXCLUDE_DIRS:                        # ★ 目录级排除（前缀匹配）
        if rel == _d or rel.startswith(_d + '/'):
            return True
    base = os.path.basename(rel)
    return ".bak_" in base or base.endswith(".bak")

_existing = {r for _, r in FILES}
_token_hits = []
# ★ golden/ 整体刻意不进 walk（原厂只读资产，人工控制），但 **device_rootfs_min 要进**：
#   它是"设备精确 sysroot"（glibc 2.29 + 设备真实运行库，13 文件 / 3.8 MB），
#   是差分判据的依据 ⇒ 必须随仓库分发到 CI，否则 CI 只能用 Ubuntu jammy 当替代品。
for _d in ('src', 'upstream', 'ledger', 'tools', 'docs', 'linker', 'golden/device_rootfs_min'):
    _base = os.path.join(LOCAL, _d)
    for _dp, _dn, _fn in os.walk(_base):
        for _f in _fn:
            _rel = os.path.relpath(os.path.join(_dp, _f), LOCAL).replace('\\', '/')
            _remote = '1to1/' + _rel
            if _rel in EXCLUDE or _remote in _existing:
                continue
            if has_real_token(os.path.join(LOCAL, _rel)):   # ★ 形状匹配，非裸子串
                _token_hits.append(_rel)
                continue
            FILES.append((_rel, _remote))
            _existing.add(_remote)

# ★★ 2026-09-30（§0.43）：**根级 `.md` 改为自动纳入**，不再逐个登记。
#   病灶（本轮实测）：仓库根有 30 个 `.md`，逐个手工登记只登记了 **14 个**
#   ⇒ **16 个从未进过仓库**（含 `AUDIT-1TO1.md`、`PRE-DELIVERY-AUDIT.md`、`DROP7-DELIVERY.md`、
#     `ROOTCAUSE-ABI-SHIFT.md`、`UB-CODE-DELETION.md` 等交接/取证关键件）。
#   这与本文件顶部为 `GAP.md` 写下的告诫是**同一个坑**，只是那次只补了那一个文件
#   ⇒ 说明"逐个登记"这种规则**必然再漏**。
#   ⇒ 改成"按扩展名自动收"：规则只写一处，不再依赖记性。
#   ★ 只收 `.md`：根目录还有大量 `_*.txt` / 沙箱回收产生的 4 字节碎文件，不能一并扫进来。
for _f in sorted(os.listdir(LOCAL)):
    _p = os.path.join(LOCAL, _f)
    if not (os.path.isfile(_p) and _f.endswith('.md')):
        continue
    _rel, _remote = _f, '1to1/' + _f
    if _rel in EXCLUDE or _remote in _existing:
        continue
    if has_real_token(_p):        # ★ 形状匹配，非裸子串
        _token_hits.append(_rel)
        continue
    FILES.append((_rel, _remote))
    _existing.add(_remote)

# ★ 2026-09-23：`--list-only` —— 只打印"会推送哪些文件"，不做任何网络操作。
#   用途：把同一份文件清单复用到**其它镜像目标**（如 AC Git / git.acwing.com），
#   避免"再写一遍挑选规则"从而两边漂移（那正是历史上"静默漏推/多发"的源头）。
#   跳过规则与 `upload_one()` 保持一致（构建产物不入库）。

def build():
    """返回 (FILES, token_hits)。规则与历史版本**逐行等价**（由FILELIST-TOOLCHAIN.md F1 把关）。"""
    return FILES, _token_hits

def kept():
    """返回 [(rel, remote)]，已剔除构建产物/备份（与上传侧共用同一份规则）。"""
    return [(a, b) for a, b in FILES if not is_build_artifact(a)]

if __name__ == '__main__':
    _k = kept()
    print("FILELIST\t%d\t(跳过构建产物/备份 %d)" % (len(_k), len(FILES) - len(_k)))
    for _a, _b in sorted(_k, key=lambda x: x[1]):
        print("%s\t%s" % (_a, _b))
