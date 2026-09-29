"""XUnzip 换源实验器 —— ★★ 结论已被行为尺**证伪**，默认不要跑。

## 现状（2026-09-27）

把 `src/upstream/xunzip/unzip.cpp` 换成 `zip_utils.zip!unzip.cpp`（Wischik 2004 原版）
会让**产物更差**：

| 指标 | 现用变体 | 换成原版 |
|---|---|---|
| 共有函数 | 778 | 775 |
| PASS | **729** | 708 |
| **DIVERGE** | **44** | **62（+18 净回归）** |

新引入的分歧**集中在 zip 内部读写/寻址链**（`unzlocal_SearchCentralDir` /
`unzlocal_getByte` / `lufseek` / `CheckCurrentFileCoherencyHeader` / `TUnzip::Find` / `OpenZipU`）
—— 恰恰是**体积最接近工厂**的那几个 ⇒ **体积接近 ≠ 语义一致**。

⇒ 已回退；回退后的产物与换源前**逐字节相同**（sha256 `6737fd22…`）。
完整证据链见 **`XUNZIP-VERSION-FORENSICS.md`**。

## 但**没有**被证伪的部分

工厂 zip 源自 Wischik 这条**血脉**是硬事实（`FormatZipMessageU`、`lasterrorU` 只在原版里有）
⇒ 工厂用的可能是同血脉的**中间版本**，而不是这一份 2004 快照。

## 什么时候才该跑它

只有当**新的、带行为鉴别力的**证据指向"另一个快照"时；跑完必须用
`python tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf`
验收，`DIVERGE` 必须下降，否则立刻按下面的 `--revert` 回退。

## 用法

    python tools/xunzip_source_swap.py             # 换源 + 重编 XUnzip.o
    python tools/xunzip_source_swap.py --revert    # 回退到现用变体

（换源时自动施加 3 处有工厂证据的适配：上游 `L"..."` 笔误、`lasterrorU` 改 extern
由工厂镜像供给、`TUnzip::Find` 参数 `bool`→`unsigned char`。）
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


def do_revert():
    """回退到现用变体（源 + 重编 XUnzip.o）。"""
    if not os.path.isfile(BAK):
        print("  !! 没有备份，无法回退"); return 2
    shutil.copy2(BAK, SRC)
    print("  已回退源 %d B sha %s" % (os.path.getsize(SRC), sha(SRC)[:16]))
    return compile_obj()


def compile_obj():
    env = dict(os.environ)
    env["ZIG_GLOBAL_CACHE_DIR"] = os.path.join(ROOT, "build", "_zigcache_xu")
    out = OBJ + ".new"
    cmd = ([ZIG, "cc"] + CFLAGS + ["-std=gnu++98", "-fno-exceptions",
           "-I" + os.path.join(XU, "posix"), SRC, "-o", out])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        print("  ★★ 编译失败 rc=%s\n%s" % (r.returncode, (r.stderr or "")[:600]))
        return 2
    shutil.move(out, OBJ)
    io.open(HASH, "w", newline="\n").write(sha(SRC) + "\n")
    print("  XUnzip.o 重编完成 %d B" % os.path.getsize(OBJ))
    return 0


def main():
    if "--revert" in sys.argv:
        return do_revert()
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
        "/* 1:1: 定义由工厂数据镜像供给（工厂 symtab 里 lasterrorU=4B） */\n"
        "extern ZRESULT lasterrorU;".encode("utf-8"))
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
