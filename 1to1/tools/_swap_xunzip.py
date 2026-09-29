#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单变量实验：把 XUnzip 的候选源换成 **Wischik 2004 原版**，看行为尺是否收敛。

## 依据（先复现，再行动）

`tools/zipver_sweep.py`（已于 2026-09-21 定案，本轮**重新复现**）：

| 候选 | 在 ±33% 内命中工厂 st_size |
|---|---|
| **A. `src/upstream/zip_utils.zip!unzip.cpp`（Wischik 原版，2004-06-25，144,408 B）** | **20 / 25** |
| B. 现用 `src/upstream/xunzip/unzip.cpp`（tomyqg 变体，151,019 B） | ≈ 0 / 25（几乎每行偏 2×） |

原版有 6 个符号**精确到字节**：`unzStringFileNameCompare` 16=16 · `unzClose` 60=60 ·
`unzGetGlobalInfo` 32=32 · `unzGoToFirstFile` 96=96 · `unzlocal_DosDateToTmuDate` 64=64 ·
`unzGetCurrentFileInfo` 64=64。

## 为什么这算根因修复而不是补丁

`src/upstream/xunzip/` 本身就是**混合状态**：`unzip.h` / `zip.cpp` / `zip.h` 是 2004-06-25 原版，
只有 `unzip.cpp` 是 2018 变体。把 `unzip.cpp` 换回同批原版 ⇒ 四个文件同源，
这是**上游版本对齐**（与 mxml 3.x→2.9、libiconv 1.17→1.16 同一手段）。

用 `tools/zipver_sweep.py` 复跑即可验收；行为验收用 `tools/diff_exec.py`。
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XU = os.path.join(ROOT, "src", "upstream", "xunzip")
SRC = os.path.join(XU, "unzip.cpp")
ZIP = os.path.join(ROOT, "src", "upstream", "zip_utils.zip")
BAK = os.path.join(ROOT, "build", "_xunzip_variant_bak.cpp")
OBJ = os.path.join(XU, "XUnzip.o")
HASH = os.path.join(XU, ".XUnzip.src.sha256")

ZIG = (r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default"
       r"\Lib\site-packages\ziglang\zig.exe")
CFLAGS = ("-c -Os -w -Wno-error=implicit-function-declaration "
          "-I" + os.path.join(ROOT, "src", "compat") +
          " -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon "
          "-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0").split()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    if not os.path.isfile(BAK):
        shutil.copy2(SRC, BAK)
        print("  备份变体 -> %s (%d B, sha %s)" % (BAK, os.path.getsize(BAK), sha(BAK)[:16]))
    print("  现用源 %d B sha %s" % (os.path.getsize(SRC), sha(SRC)[:16]))

    with zipfile.ZipFile(ZIP) as z:
        data = z.read("unzip.cpp")
    # ★ 上游原版自带一处笔误：ANSI 构建下 `const TCHAR *msg=L"...";` 是**宽字面量配窄 TCHAR**，
    #   只在 `_UNICODE` 下才编得过（该函数其余分支全都用 `_T(...)`）。
    #   工厂是 ANSI 构建（`TUnzip::Find` 取 `char`，且导入 `FormatZipMessageU(…, char*, …)`）
    #   ⇒ 必须把这**唯一一处**改成 `_T("…")`。这是**修上游笔误**，不改语义。
    n = data.count(b'const TCHAR *msg=L"unknown zip result code";')
    data = data.replace(b'const TCHAR *msg=L"unknown zip result code";',
                        b'const TCHAR *msg=_T("unknown zip result code");')
    print("  上游笔误修正 %d 处（L\"...\" -> _T(\"...\")）" % n)

    # ★ `lasterrorU` 的**定义由工厂数据镜像供给**（与 libiconv 的 `_libiconv_version` 同一手法）。
    #   证据：工厂 symtab 里**恰好有** `lasterrorU`（4 B，无 ANSI 版 `lasterror`），
    #   而原版第 3968 行 `ZRESULT lasterrorU=ZR_OK;` 正是它；
    #   `build/factory_local.o`（工厂数据镜像）已定义该符号 ⇒ 会 `duplicate symbol`。
    #   ZR_OK == 0，镜像侧零初始化 ⇒ **取值等价**，改为 extern 不改语义。
    m = data.count(b"ZRESULT lasterrorU=ZR_OK;")
    data = data.replace(
        b"ZRESULT lasterrorU=ZR_OK;",
        b"/* 1:1\uff1a\u5b9a\u4e49\u7531\u5de5\u5382\u6570\u636e\u955c\u50cf\u4f9b\u7ed9\uff08symtab \u91cc lasterrorU=4B\uff09*/\n"
        b"extern ZRESULT lasterrorU;")
    print("  lasterrorU 改为 extern %d 处（由工厂镜像供给）" % m)

    # ★ 第 2 处已知改动（`zipver_sweep.py` 早已记录，方向明确）：
    #   工厂 `TUnzip::Find` 取 **unsigned char**（mangled `…PKch…`），
    #   原版取 **bool**（`…PKcb…`）⇒ 我方 `FindZipItemA` 调的 `PKch` 形式在链接期找不到。
    #   两者都是 1 字节 ⇒ ABI 相同，改类型即对齐工厂。
    k = 0
    for old, new in (
        (b"ZRESULT Find(const TCHAR *name,bool ic,int *index,ZIPENTRY *ze);",
         b"ZRESULT Find(const TCHAR *name,unsigned char ic,int *index,ZIPENTRY *ze);"),
        (b"ZRESULT TUnzip::Find(const TCHAR *tname,bool ic,int *index,ZIPENTRY *ze)",
         b"ZRESULT TUnzip::Find(const TCHAR *tname,unsigned char ic,int *index,ZIPENTRY *ze)"),
    ):
        c = data.count(old)
        data = data.replace(old, new)
        k += c
    print("  TUnzip::Find 参数 bool -> unsigned char %d 处（对齐工厂 PKch）" % k)
    with open(SRC, "wb") as fh:
        fh.write(data)
    print("  已换为原版 %d B sha %s" % (len(data), sha(SRC)[:16]))

    env = dict(os.environ)
    env["ZIG_GLOBAL_CACHE_DIR"] = os.path.join(ROOT, "build", "_zigcache_xu")
    out = OBJ + ".new"
    cmd = ([ZIG, "cc"] + CFLAGS + ["-std=gnu++98", "-fno-exceptions",
           "-I" + os.path.join(XU, "posix"), SRC, "-o", out])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        print("  ★★ 编译失败 rc=%s\n%s" % (r.returncode, (r.stderr or "")[:800]))
        # 回退
        shutil.copy2(BAK, SRC)
        print("  已回退到变体源")
        return 2
    shutil.move(out, OBJ)
    io.open(HASH, "w", newline="\n").write(sha(SRC) + "\n")
    print("  XUnzip.o 重编完成 %d B" % os.path.getsize(OBJ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
