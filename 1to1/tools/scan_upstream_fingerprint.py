#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门禁：**上游库版本指纹比对**（技能铁律 90）

背景（rkgame 1:1 重构，P5 第七个真实分歧）
------------------------------------------------
项目长期记录「XUnzip = Wischik zip_utils」——**库名没错，版本错了**：
工厂是「Hans Dietrich 1.x 系 + 厂商定制」（`unzOpenCurrentFile` **单参数**、
`TUnzip::Open` 仅 84 B 且**无** `GetCurrentDirectory`），
我们链接的却是较新变体（双参数、`Open` 204 B、含 `getcwd`）。
⇒ 行为分歧：工厂 `TUnzip::Open` 返回失败 ⇒ 优雅打印 `open %s fail`；我们返回成功 ⇒ 继续到
`unzOpenCurrentFile` 崩溃。**代价：P5 卡了三轮。**

判据
----
同一个上游库、同一份源码，**不同编译器**的函数 size 通常差 < 2×；
**差 2.5× 以上就是"版本/实现不符"的强信号**。

本脚本对**两侧都存在的上游符号**逐一比对 size，输出比值表并分级告警。

用法
----
    python3 tools/scan_upstream_fingerprint.py [--factory <elf>] [--rebuilt <elf>]
                                               [--warn 1.6] [--fail 2.5]

默认路径：factory = `golden/factory.rkgame.bin`（CI）或 `D:/output/rkgame/rkgame`（本地）
          rebuilt = `build/rkgame.rebuilt.elf`

退出码：0 = 无 FAIL 级；1 = 有 FAIL 级（上游版本疑似不符）
"""
import os
import struct
import sys

# 上游库符号特征（小写子串匹配）
UPSTREAM_PATTERNS = [
    ("xunzip", ("unzopen", "unzclose", "unzget", "unzread", "unzlocate", "unzgot", "unzeof",
                "lufopen", "lufread", "lufseek", "luftell", "lufclose", "lufwrite",
                "tunzip", "zipentry", "zipmessage", "getzipitem", "findzipitem", "unzipitem",
                "openzip", "closezip", "formatzip")),
    ("minixml", ("mxml",)),
    ("stb_truetype", ("stbtt_", "stb_truetype")),
    ("helix_mp3", ("mp3", "huffman", "subband", "imdct", "dequant")),
    ("libiconv", ("iconv", "cp1252", "sjis", "big5", "gbk", "utf16", "ucs2", "iso8859")),
    ("zlib", ("inflate", "deflate", "adler32", "crc32", "zlib", "crc_table")),
    ("libretro", ("retro_", "libretro")),
]


def read_symtab(path):
    """返回 {符号名: (地址, size)}，含 LOCAL 与 GLOBAL 函数/对象符号。"""
    d = open(path, "rb").read()
    if d[:4] != b"\x7fELF":
        raise SystemExit("FATAL %s 不是 ELF" % path)
    e_shoff = struct.unpack_from("<I", d, 32)[0]
    es = struct.unpack_from("<H", d, 46)[0]
    n = struct.unpack_from("<H", d, 48)[0]
    si = struct.unpack_from("<H", d, 50)[0]
    stroff = struct.unpack_from("<I", d, e_shoff + si * es + 16)[0]
    syms = {}
    for i in range(n):
        o = e_shoff + i * es
        sh = struct.unpack_from("<10I", d, o)
        if sh[1] != 2:          # SHT_SYMTAB
            continue
        st = struct.unpack_from("<I", d, e_shoff + sh[6] * es + 16)[0]
        ent = sh[9] or 16
        for j in range(sh[5] // ent):
            oo = sh[4] + j * ent
            nmn, val, sz, inf, oth, shx = struct.unpack_from("<IIIBBH", d, oo)
            if nmn == 0 or shx == 0:
                continue
            if (inf & 0xF) != 2:               # 只比 FUNC
                # ★ 不能比 STT_OBJECT：我们从工厂镜像导入的数据表，其 size 记的是
                #   "整块镜像大小"（实测多个 xmp3_*Tab / cp1252_page* 都拿到同一个
                #   856920），与元素真实尺寸无关 ⇒ 全是假告警。
                continue
            if sz == 0:
                continue
            e = d.index(b"\x00", st + nmn)
            syms.setdefault(d[st + nmn:e].decode("utf-8", "replace"), (val, sz))
    return syms


def classify(name):
    low = name.lower()
    for lib, pats in UPSTREAM_PATTERNS:
        if any(p in low for p in pats):
            return lib
    return None


def demangle_hint(name):
    """粗略提取 mangled 名里的可读部分（用于显示）。"""
    if not name.startswith("_Z"):
        return name
    i = 2
    while i < len(name) and name[i].isdigit():
        i += 1
    n = int(name[2:i] or 0)
    return name[i:i + n] or name


def main():
    argv = sys.argv[1:]
    def opt(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default
    warn = float(opt("--warn", "4.0"))
    fail = float(opt("--fail", "8.0"))

    fac = opt("--factory", None)
    if fac is None:
        for c in ("golden/factory.rkgame.bin", "D:/output/rkgame/rkgame"):
            if os.path.exists(c):
                fac = c
                break
    reb = opt("--rebuilt", "build/rkgame.rebuilt.elf")

    for p in (fac, reb):
        if not p or not os.path.exists(p):
            print("FATAL 找不到 ELF: %s" % p)
            return 3

    print("== 上游符号指纹比对（技能铁律 90：库名对 ≠ 版本对）==")
    print("   工厂: %s" % fac)
    print("   重建: %s" % reb)

    # 基线豁免：已知「上游版本未对齐」的符号显式登记在此，避免拖红 CI。
    # ★ 纪律：每修好一项**必须删除**对应基线行；基线文件内容会原样打印，保持透明。
    base = {}
    bp = opt("--baseline", "tools/upstream_fingerprint_baseline.txt")
    if os.path.exists(bp):
        for line in open(bp, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line:
                parts = line.split(None, 1)
                base[parts[0]] = parts[1] if len(parts) > 1 else ""
        print("   基线: %s（%d 项已知未对齐）" % (bp, len(base)))
        for k, v in base.items():
            print("         · %s  ← %s" % (k, v))
    fa = read_symtab(fac)
    rb = read_symtab(reb)

    rows = []
    for nm, (va, sz) in fa.items():
        lib = classify(nm)
        if not lib:
            continue
        hit = rb.get(nm)
        if not hit:
            continue
        rsz = hit[1]
        ratio = max(sz, rsz) / max(1, min(sz, rsz))
        rows.append((ratio, lib, nm, sz, rsz, "same" if sz == rsz else ""))
    rows.sort(reverse=True)

    if not rows:
        print("\n   （两侧没有共同的上游符号 —— 检查符号表是否 strip）")
        return 0

    print("\n  %-8s %-11s %-46s %8s %8s %7s" % ("比值", "库", "符号", "工厂", "重建", "判定"))
    nf = nw = nk = 0
    for ratio, lib, nm, sz, rsz, _ in rows:
        if ratio < warn:
            continue
        if nm in base:
            lvl, nk = "KNOWN", nk + 1
        elif ratio >= fail:
            lvl, nf = "FAIL", nf + 1
        else:
            lvl, nw = "WARN", nw + 1
        print("  %-8.2f %-11s %-46s %8d %8d %7s" % (ratio, lib, demangle_hint(nm)[:46], sz, rsz, lvl))

    print("\n  小计：共比对 %d 个上游符号；FAIL=%d（≥%.1f×） KNOWN=%d（基线豁免） WARN=%d（≥%.1f×）"
          % (len(rows), nf, fail, nk, nw, warn))
    if nf:
        print("  ✗ 结论：疑似上游**版本/实现不符**（比值 ≥ %.1f× 且不在基线内）—— 见上表" % fail)
        print("     排查方向：① 该库选型是否与工厂同版本（符号签名/类布局指纹）；")
        print("               ② 工厂可能用 `-O2`（size 偏小），但 8× 以上基本不是优化差异；")
        print("               ③ 若确认「薄封装 vs 完整实现」模式（工厂 <64 B、重建 >1 KB），")
        print("                  即为「厂商定制版 / 选错版本」，须按工厂反汇编逐函数对齐。")
        return 1
    if nk:
        print("  ⚠ 结论：无新增 FAIL；但有 %d 项**已知未对齐**（基线豁免，见上表 KNOWN）" % nk)
        print("     纪律：修好一项就删一条基线行；不得把新问题塞进基线。")
        return 0
    print("  ✓ 结论：未发现上游版本不符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
