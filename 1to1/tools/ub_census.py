#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ub_census —— 量化"编译期 UB 警告"这一类有多大（因为它会让优化器**静默删代码**）。

## 为什么必须做（2026-09-27 实证根因）

`UpdateROM`：源码 139 行完整，但 `-O1/-Os/-O2` 下只剩 **112 B**（工厂 976 B）。
`-O0` 下 **2660 B**（完整）⇒ 不是源码缺，是**优化器利用了 UB**。

UB 来源（编译器原话）：
    warning: 'memset' will always overflow; destination buffer has size 4,
             but size argument is 304
       58 |   memset(auStack_158,0,0x130);
`auStack_158` 被 Ghidra 反编译成 `gh_u1 auStack_158[4]` —— **`[4]` 是假尺寸**，
真实对象 0x130 字节。写越界 ⇒ UB ⇒ clang 可判定其后不可达 ⇒ **把闪写/CRC/reboot 整段删掉**。

而我们的构建**一直用 `-w` 屏蔽全部警告** ⇒ 这类 UB 从来没人看见。
⇒ 本脚本用 `-fsyntax-only`（不产对象，快）把全部专有源文件过一遍，
   统计**高信号 UB 类**警告的文件数与位置。

## 为什么只挑这几类（而不是开全部 -Wall）

Ghidra 反编译产物**天然**有大量 `-Wuninitialized`（它的 `local_XX` 语义就是"未知槽"），
全部打开会淹没信号。**会诱发优化器删代码**的才是高危：
  · `-Wfortify-source`      对象越界（本例；clang 会当 UB）
  · `-Warray-bounds`        数组下标越界
  · `-Wstringop-overflow`   memcpy/memset/str* 的越界
"""
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★★★ 2026-09-29 修（根因，同类第 3 次）：**门禁不得依赖本机专有路径**。
#   旧实现把 Windows 的 `zig.exe` 绝对路径**写死**，在 Linux（CNB 云开发 / GitHub CI）上
#   必然 `FileNotFoundError` ⇒ 本门禁**必然 FAIL（exit 18）** ⇒ 直接判定"产物禁止上机"。
#   实证：云开发跑编译器对齐实验时，链接本身成功（elf 5,442,408 B 已产出），却被本门禁拦死，
#        `link rc=18` ⇒ 整轮实验白跑。这与 §0.4 的 `src_transcript_parity.py` 硬编码语料路径同族。
#   现改为**多级解析 + 找不到就 fail-closed（并指名）**，与 `check_obj_fresh.py` 同一套口径。
# ★★★ 2026-09-29 修（根因，同类第 4 次）：**删掉宿主专有兜底路径**。
#   旧实现在链尾多写了一个 Windows venv 的绝对路径 `_ZIG_FALLBACK`。它是**纯冗余**：
#   上面的 `import ziglang; dirname(ziglang.__file__)` 分支在 Windows 上解析出的就是
#   同一路径，同时还能覆盖 Linux（包内二进制名是 `zig` 而非 `zig.exe`）。
#   留着它的唯一效果 = 让「CI 可达性 / 宿主绝对路径门禁」(s08) 判 FAIL(exit 17)。
#   ⇒ 判据：**凡"只在本机成立"的候选，一律不写进代码**；本机路径应由环境变量 `ZIG`/`ZIG_BIN` 提供。


def resolve_zig():
    """多级解析 zig —— **委托给唯一解析器** `tools/zig_resolve.py`（纪律 69）。

    ★ 为什么改成薄封装（同类第 3 次在本文件复发）：
      本文件曾各写一份解析链，第一次把 Windows 的 `zig.exe` 绝对路径**写死**（Linux 上必然
      FAIL，云开发整轮实验白跑）；修完又在**链尾**多留了一个"本机 Windows 默认路径"兜底
      （纯冗余）⇒ CI 的「CI 可达性 / 宿主绝对路径门禁」判 FAIL(exit 17)，`1to1-verify` 红。
      ⇒ **解析规则只允许有一处**；这里只做转发，返回 `(路径|None, 来源|候选清单)`。
    """
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        'zig_resolve', os.path.join(ROOT, 'tools', 'zig_resolve.py'))
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
    return _m.resolve_zig()


ZIG, ZIG_WHY = resolve_zig()
if not ZIG:
    print('!! ub_census：找不到 zig 编译器 ⇒ **fail-closed**（不得退化成 no-op，'
          '那会让 UB 门禁静默失效）', file=sys.stderr)
    print('   试过的候选：%s' % (' ; '.join(ZIG_WHY) if isinstance(ZIG_WHY, list) else ZIG_WHY),
          file=sys.stderr)
    print('   修：设 ZIG=<zig 路径>，或 pip install ziglang（Linux 下二进制名是 zig，不是 zig.exe）',
          file=sys.stderr)
    sys.exit(2)

SRCDIR = os.path.join(ROOT, "src", "proprietary")
COMPAT = os.path.join(ROOT, "src", "compat")
ARCH = "-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"
FID = "-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
WARN = ["-Wno-everything", "-Wfortify-source", "-Warray-bounds",
        "-Wstringop-overflow", "-Wstringop-overread"]
PAT = re.compile(r"warning:.*(always overflow|array bounds|will always|overread|overflow)",
                 re.I)
LOC = re.compile(r"^(\S+?):(\d+):(\d+): warning:")


def main():
    files = []
    for d in sorted(os.listdir(SRCDIR)):
        dd = os.path.join(SRCDIR, d)
        if os.path.isdir(dd):
            files += [os.path.join(dd, f) for f in sorted(os.listdir(dd)) if f.endswith(".c")]
    hits = {}
    for f in files:
        cmd = ([ZIG, "cc", "-fsyntax-only", "-Os",
                "-Wno-error=implicit-function-declaration",
                "-I" + os.path.normpath(COMPAT)] + ARCH.split() + FID.split()
               + WARN + [f])
        env = dict(os.environ)
        env["ZIG_GLOBAL_CACHE_DIR"] = os.path.join(ROOT, "build", "_zigcache_ub")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=120)
        except subprocess.TimeoutExpired:
            hits[os.path.basename(f)] = ["TIMEOUT"]
            continue
        lines = [l for l in (r.stderr or "").splitlines() if PAT.search(l)]
        if lines:
            hits[os.path.basename(f)] = lines
    print("=" * 96)
    print("编译期 UB 高危警告普查（%d 个专有源文件）" % len(files))
    print("  编译器：%s（来源：%s）" % (ZIG, ZIG_WHY))
    print("=" * 96)
    print("命中文件数 = %d" % len(hits))
    for fn in sorted(hits):
        print("\n-- %s" % fn)
        for l in hits[fn][:4]:
            print("     " + l.strip()[:150])
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
