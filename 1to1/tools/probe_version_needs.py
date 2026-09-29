#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取证：工厂 ELF 的 glibc 版本需求 + 候选 sysroot 里 mem*/str* 与 libstdc++ 的导出。

用法: python tools/_probe_vers.py
"""
import os
import sys

from elftools.elf.elffile import ELFFile

ZP = "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang"


def verneeds(path):
    e = ELFFile(open(path, "rb"))
    out = []
    sec = e.get_section_by_name(".gnu.version_r")
    if sec is None:
        return out
    try:
        for verneed, vernaux_iter in sec.iter_versions():
            out.append((verneed.name.decode("latin1") if isinstance(verneed.name, bytes)
                        else verneed.name,
                        sorted({a.name for a in vernaux_iter})))
    except Exception as ex:
        return [("parse-error", str(ex))]
    return out


def exports(path, names):
    e = ELFFile(open(path, "rb"))
    dyn = e.get_section_by_name(".dynsym")
    if dyn is None:
        return {}
    res = {}
    for s in dyn.iter_symbols():
        if s.name in names and s["st_shndx"] != "SHN_UNDEF":
            res[s.name] = (s["st_info"]["type"], s["st_size"])
    return res


def main():
    print("=== 工厂 .gnu.version_r（需求） ===")
    for name, vs in verneeds("golden/factory.rkgame.bin"):
        print("   %-24s %s" % (name, vs))
    print()
    print("=== 我方 .gnu.version_r ===")
    for name, vs in verneeds("build/rkgame.rebuilt.elf"):
        print("   %-24s %s" % (name, vs))
    print()
    WANT = ["memset", "memcpy", "memmove", "strlen", "memcmp",
            "__memcpy_chk", "_Znwj", "_ZdlPv", "_Znaj", "_ZdaPv",
            "sqrt", "cos", "floorf", "fmod", "raise", "reboot", "sync",
            "nl_langinfo", "getenv", "putc", "_IO_putc", "strdup", "__strdup"]
    CAND = {
        "bootlin63-sysroot/lib": "cache_tc/bootlin63/arm-buildroot-linux-gnueabihf/sysroot/lib/libc.so.6",
        "bootlin63-sysroot/usr/lib": "cache_tc/bootlin63/arm-buildroot-linux-gnueabihf/sysroot/usr/lib/libstdc++.so.6",
        "device/lib": "golden/device_rootfs_min/lib/libc.so.6",
        "device/usr/lib": "golden/device_rootfs_min/usr/lib/libstdc++.so.6",
    }
    for lab, p in CAND.items():
        if not os.path.exists(p):
            print("--- %-28s 不存在" % lab)
            continue
        r = exports(p, set(WANT))
        print("--- %-28s 命中 %d" % (lab, len(r)))
        if r:
            print("      ", sorted(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
