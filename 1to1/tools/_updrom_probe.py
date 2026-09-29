#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单变量探针：UpdateROM 的缺体到底是"优化档伪影"还是"编译/源码问题"。

背景（本轮发现）：产物里 `UpdateROM` 只有 **112 B**，工厂 **976 B**（0.115x），
而源码 139 行是完整的（含 sync / reboot）。行为尺判 PASS 只是因为输入没走进那段代码。
⇒ 本脚本按**单一变量**（优化档）逐个复编同一份源码，看 `UpdateROM` 的大小与指令形态。
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIG = (r"C:\Users\Administrator\.workbuddy\binaries\python\envs\default"
       r"\Lib\site-packages\ziglang\zig.exe")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "src", "proprietary", "flash", "FUN_0000ac44_UpdateROM.c")
TARGET = sys.argv[2] if len(sys.argv) > 2 else "UpdateROM"
BASE = int(sys.argv[3]) if len(sys.argv) > 3 else 976
COMPAT = os.path.join(ROOT, "src", "compat")
OUTD = os.path.join(ROOT, "build", "_updrom_probe")
ARCH = "-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"
FID = "-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"


def run(opt):
    os.makedirs(OUTD, exist_ok=True)
    out = os.path.join(OUTD, "probe_%s_%s.o" % (TARGET, opt.strip("-").replace("-", "")))
    cmd = [ZIG, "cc", "-c", opt, "-w", "-Wno-error=implicit-function-declaration",
           "-I" + os.path.normpath(COMPAT)] + ARCH.split() + FID.split() + [SRC, "-o", out]
    env = dict(os.environ)
    env["ZIG_GLOBAL_CACHE_DIR"] = os.path.join(ROOT, "build", "_zigcache_updrom")
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return out, r.returncode, (r.stderr or "")[:400]


def sym_sizes(obj):
    from elftools.elf.elffile import ELFFile
    e = ELFFile(open(obj, "rb"))
    st = e.get_section_by_name(".symtab")
    out = {}
    for s in st.iter_symbols():
        if s.name and s["st_info"]["type"] == "STT_FUNC":
            out[s.name] = s["st_size"]
    return out


def main():
    print("目标 %s：工厂 = %d B（基准）" % (TARGET, BASE))
    print("%-6s %-10s %-10s %s" % ("优化档", "UpdateROM", "比值", "编出的函数名"))
    for opt in ("-O0", "-O1", "-Os", "-O2"):
        obj, rc, err = run(opt)
        if rc != 0 or not os.path.exists(obj):
            print("%-6s 编译失败 rc=%s %s" % (opt, rc, err[:120]))
            continue
        sz = sym_sizes(obj)
        u = sz.get(TARGET, 0)
        names = sorted(n for n in sz if sz[n] > 0)
        print("%-6s %-10d %-10.3f %s" % (opt, u, u / float(BASE), " ".join(n for n in names if n == TARGET or n not in names)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
