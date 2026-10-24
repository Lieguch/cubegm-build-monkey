#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_r284_patch3.py —— R284 补丁（行尾无关版：自动适配 LF/CRLF）"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda rel: os.path.join(ROOT, rel)

def variants(pat):
    """生成同一模式的 LF / CRLF 两个变体。"""
    if '\r' in pat:
        return [pat]
    return [pat, pat.replace('\n', '\r\n')]

def edit(rel, pairs):
    p = P(rel)
    with io.open(p, encoding='utf-8', newline='') as f:
        old = f.read()
    txt = old
    for i, (a, b) in enumerate(pairs):
        done = False
        for av in variants(a):
            n = txt.count(av)
            if n == 1:
                # 替换串行尾与命中变体一致
                bv = b if av == a else b.replace('\n', '\r\n')
                txt = txt.replace(av, bv)
                done = True
                break
        if not done:
            print('FATAL %s pair#%d: no unique match\n  PAT: %r' % (rel, i, a[:90]))
            sys.exit(1)
    if txt == old:
        print('FATAL %s: no change' % rel)
        sys.exit(1)
    tmp = p + '.tmp_r284'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)
    os.replace(tmp, p)
    print('OK %s (%d edits)' % (rel, len(pairs)))

# ---- s05: run_game 定义（CRLF 文件） ----
edit('src/proprietary/core/FUN_002b7510_run_game.c', [(
    "gh_u4 run_game(char *param_1)\n\n{",
    "gh_u4 run_game(char *param_1, ...)   /* R284：变参原型（工厂 mui_run_game 传 2 参）；.text 与非变参一致 */\n\n{",
)])

# ---- s20: FilePreEmu ----
edit('src/proprietary/core/FUN_00016f08_FilePreEmu.c', [
    ("GetZipItemA(iVar3,0xffffffff,&local_158);\n        RARCH_LOG(\"zipcount",
     "GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：304B 缓冲（=sizeof(ZIPENTRY)）；cast 对齐严格原型 */\n        RARCH_LOG(\"zipcount"),
    ("iVar4 = GetZipItemA(iVar3,0,&local_158);",
     "iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */"),
])

# ---- s20: run_game GetZipItemA（单行模式） ----
edit('src/proprietary/core/FUN_002b7510_run_game.c', [
    ("GetZipItemA(iVar3,0xffffffff,&local_158);",
     "GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：ZIPENTRY* cast（304B 缓冲） */"),
    ("iVar4 = GetZipItemA(iVar3,0,&local_158);",
     "iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */"),
])

# ---- s20: UpdateROM / gpsp_unzip ----
edit('src/proprietary/flash/FUN_0000ac44_UpdateROM.c', [(
    "iVar2 = GetZipItemA(iVar1,0,auStack_158);",
    "iVar2 = GetZipItemA(iVar1,0,(ZIPENTRY *)auStack_158);   /* R284：ZIPENTRY* cast（zipent 304B 缓冲，字节偏移宏依赖字节数组形态） */",
)])
edit('src/proprietary/misc/FUN_002b4e20_gpsp_unzip.c', [(
    "iVar2 = GetZipItemA(iVar1,0,auStack_140);",
    "iVar2 = GetZipItemA(iVar1,0,(ZIPENTRY *)auStack_140);   /* R284：ZIPENTRY* cast（304B 缓冲） */",
)])

# ---- s20: mui_type / mui_search ----
edit('src/proprietary/mui/FUN_00023e10_mui_type.c', [
    ("GetZipItemA(hz,0xffffffff,ze);\n      zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);",
     "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：ze 是 304B 全局缓冲（globals.h:4606） */\n      zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);"),
    ("GetZipItemA(hz,0xffffffff,ze);\n          zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);",
     "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：同上 */\n          zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);"),
])
edit('src/proprietary/mui/FUN_00025094_mui_search.c', [(
    "GetZipItemA(hz,0xffffffff,ze);\n      zr = FindZipItemA(hz,\"fileinfo.txt\",1,(int *)&local_430,ze);",
    "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：ze 是 304B 全局缓冲 */\n      zr = FindZipItemA(hz,\"fileinfo.txt\",1,(int *)&local_430,ze);",
)])

# ---- s20: mui_setting 13 处（单行模式） ----
p = P('src/proprietary/mui/FUN_0002b2b4_mui_setting.c')
with io.open(p, encoding='utf-8', newline='') as f:
    txt = f.read()
a = "&DAT_002dd860"
n = txt.count(a)
if n != 13:
    print('FATAL mui_setting: count=%d (expect 13)' % n)
    sys.exit(1)
txt = txt.replace(a, "(char *)&DAT_002dd860")
tmp = p + '.tmp_r284'
with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
    f.write(txt)
os.replace(tmp, p)
print('OK mui_setting.c (13 casts)')

# ---- s48: stb noinline ----
p = P('src/upstream/stb/stb_truetype.h')
with io.open(p, encoding='utf-8', newline='') as f:
    txt = f.read()
pairs = [
    ("static void stbtt__csctx_rline_to(stbtt__csctx *ctx, float dx, float dy)\n{",
     "/* R204/R284：noinline —— 工厂 ELF 有 stbtt__csctx_rline_to 实体符号（72B）；\n"
     " * 不加则被 clang -Os 内联进 stbtt__run_charstring，符号消失 ⇒ s48 门禁 FAIL。 */\n"
     "static __attribute__((noinline)) void stbtt__csctx_rline_to(stbtt__csctx *ctx, float dx, float dy)\n{"),
    ("// directly AA rasterize edges w/o supersampling\nstatic void stbtt__rasterize_sorted_edges(stbtt__bitmap *result, stbtt__edge *e, int n, int vsubsample, int off_x, int off_y, void *userdata)\n{",
     "// directly AA rasterize edges w/o supersampling\n/* R204/R284：noinline —— 工厂 ELF 有 stbtt__rasterize_sorted_edges.isra.16 实体；v2 rasterizer 不加则被内联 ⇒ s48 FAIL。 */\n"
     "static __attribute__((noinline)) void stbtt__rasterize_sorted_edges(stbtt__bitmap *result, stbtt__edge *e, int n, int vsubsample, int off_x, int off_y, void *userdata)\n{"),
    ("static float stbtt__cuberoot( float x )\n{",
     "/* R204/R284：noinline —— 工厂 ELF 有 stbtt__cuberoot 实体符号（84B）；不加则被内联进 stbtt__solve_cubic ⇒ s48 FAIL。 */\n"
     "static __attribute__((noinline)) float stbtt__cuberoot( float x )\n{"),
]
for i, (a2, b2) in enumerate(pairs):
    done = False
    for av in variants(a2):
        if txt.count(av) == 1:
            bv = b2 if av == a2 else b2.replace('\n', '\r\n')
            txt = txt.replace(av, bv)
            done = True
            break
    if not done:
        print('FATAL stb noinline pair#%d' % i)
        sys.exit(1)
tmp = p + '.tmp_r284'
with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
    f.write(txt)
os.replace(tmp, p)
print('OK stb_truetype.h (3 noinline)')
print('=== ALL REMAINING PATCHES APPLIED ===')
