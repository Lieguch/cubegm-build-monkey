#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_r284_patch2.py —— R284 补充补丁（run_game 定义格式修正 + 剩余 s20/s48 编辑）"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda rel: os.path.join(ROOT, rel)

def edit(rel, pairs):
    p = P(rel)
    with io.open(p, encoding='utf-8', newline='') as f:
        old = f.read()
    txt = old
    for i, (a, b) in enumerate(pairs):
        n = txt.count(a)
        if n != 1:
            print('FATAL %s pair#%d: count=%d (expect 1)\n  PAT: %r' % (rel, i, n, a[:90]))
            sys.exit(1)
        txt = txt.replace(a, b)
    if txt == old:
        print('FATAL %s: no change' % rel)
        sys.exit(1)
    tmp = p + '.tmp_r284'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(txt)
    assert io.open(tmp, encoding='utf-8', newline='').read() == txt
    os.replace(tmp, p)
    print('OK %s (%d edits)' % (rel, len(pairs)))

# ============ s05: run_game 定义（空行格式） ============
edit('src/proprietary/core/FUN_002b7510_run_game.c', [(
    "gh_u4 run_game(char *param_1)\n\n{",
    "gh_u4 run_game(char *param_1, ...)   /* R284：变参原型（工厂 mui_run_game 传 2 参）；.text 与非变参一致 */\n\n{",
)])

# ============ s20: 剩余 ZIPENTRY* cast ============
edit('src/proprietary/core/FUN_00016f08_FilePreEmu.c', [
    ("GetZipItemA(iVar3,0xffffffff,&local_158);\n        RARCH_LOG(\"zipcount",
     "GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：local_158 是 304B 缓冲（=sizeof(ZIPENTRY)），Ghidra 渲染成字节数组；cast 对齐 GetZipItemA 严格原型 */\n        RARCH_LOG(\"zipcount"),
    ("iVar4 = GetZipItemA(iVar3,0,&local_158);",
     "iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */"),
])
edit('src/proprietary/core/FUN_002b7510_run_game.c', [
    ("GetZipItemA(iVar3,0xffffffff,&local_158);",
     "GetZipItemA(iVar3,0xffffffff,(ZIPENTRY *)&local_158);   /* R284：ZIPENTRY* cast（304B 缓冲） */"),
    ("iVar4 = GetZipItemA(iVar3,0,&local_158);",
     "iVar4 = GetZipItemA(iVar3,0,(ZIPENTRY *)&local_158);   /* R284：同上 */"),
])
edit('src/proprietary/flash/FUN_0000ac44_UpdateROM.c', [(
    "iVar2 = GetZipItemA(iVar1,0,auStack_158);",
    "iVar2 = GetZipItemA(iVar1,0,(ZIPENTRY *)auStack_158);   /* R284：ZIPENTRY* cast（zipent 304B 缓冲，字节偏移宏依赖字节数组形态） */",
)])
edit('src/proprietary/misc/FUN_002b4e20_gpsp_unzip.c', [(
    "iVar2 = GetZipItemA(iVar1,0,auStack_140);",
    "iVar2 = GetZipItemA(iVar1,0,(ZIPENTRY *)auStack_140);   /* R284：ZIPENTRY* cast（304B 缓冲） */",
)])
edit('src/proprietary/mui/FUN_00023e10_mui_type.c', [
    ("GetZipItemA(hz,0xffffffff,ze);\n      zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);",
     "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：ze 是 304B 全局缓冲（globals.h:4606），cast 对齐严格原型 */\n      zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);"),
    ("GetZipItemA(hz,0xffffffff,ze);\n          zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);",
     "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：同上 */\n          zr = FindZipItemA(hz,\"filelist.txt\",1,&local_434,ze);"),
])
edit('src/proprietary/mui/FUN_00025094_mui_search.c', [(
    "GetZipItemA(hz,0xffffffff,ze);\n      zr = FindZipItemA(hz,\"fileinfo.txt\",1,(int *)&local_430,ze);",
    "GetZipItemA(hz,0xffffffff,(ZIPENTRY *)ze);   /* R284：ze 是 304B 全局缓冲，cast 对齐严格原型 */\n      zr = FindZipItemA(hz,\"fileinfo.txt\",1,(int *)&local_430,ze);",
)])

# ============ s20: mui_setting 13 处 ============
p = P('src/proprietary/mui/FUN_0002b2b4_mui_setting.c')
with io.open(p, encoding='utf-8', newline='') as f:
    txt = f.read()
a = "&DAT_002dd860"
n = txt.count(a)
if n != 13:
    print('FATAL mui_setting: &DAT_002dd860 count=%d (expect 13)' % n)
    sys.exit(1)
txt = txt.replace(a, "(char *)&DAT_002dd860")
tmp = p + '.tmp_r284'
with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
    f.write(txt)
os.replace(tmp, p)
print('OK mui_setting.c (13 dir_serial_list 2nd-arg casts)')

# ============ s48: v1.22 noinline ============
p = P('src/upstream/stb/stb_truetype.h')
with io.open(p, encoding='utf-8', newline='') as f:
    txt = f.read()
pairs = [
    ("static void stbtt__csctx_rline_to(stbtt__csctx *ctx, float dx, float dy)\n{",
     "/* R204/R284：noinline —— 工厂 ELF 有 stbtt__csctx_rline_to 实体符号（72B）；\n"
     " * 不加则被 clang -Os 内联进 stbtt__run_charstring，符号消失 ⇒ s48 门禁 FAIL。\n"
     " * v1.26 同款补丁，实测与工厂对拍通过。 */\n"
     "static __attribute__((noinline)) void stbtt__csctx_rline_to(stbtt__csctx *ctx, float dx, float dy)\n{"),
    ("// directly AA rasterize edges w/o supersampling\nstatic void stbtt__rasterize_sorted_edges(stbtt__bitmap *result, stbtt__edge *e, int n, int vsubsample, int off_x, int off_y, void *userdata)\n{",
     "// directly AA rasterize edges w/o supersampling\n/* R204/R284：noinline —— 工厂 ELF 有 stbtt__rasterize_sorted_edges.isra.16 实体；\n"
     " * v2 rasterizer（本块）不加则被内联 ⇒ 符号消失 ⇒ s48 门禁 FAIL。 */\n"
     "static __attribute__((noinline)) void stbtt__rasterize_sorted_edges(stbtt__bitmap *result, stbtt__edge *e, int n, int vsubsample, int off_x, int off_y, void *userdata)\n{"),
    ("static float stbtt__cuberoot( float x )\n{",
     "/* R204/R284：noinline —— 工厂 ELF 有 stbtt__cuberoot 实体符号（84B）；\n"
     " * 不加则被内联进 stbtt__solve_cubic ⇒ 符号消失 ⇒ s48 门禁 FAIL。 */\n"
     "static __attribute__((noinline)) float stbtt__cuberoot( float x )\n{"),
]
for i, (a2, b2) in enumerate(pairs):
    c = txt.count(a2)
    if c != 1:
        print('FATAL stb noinline pair#%d: count=%d\n  PAT: %r' % (i, c, a2[:80]))
        sys.exit(1)
    txt = txt.replace(a2, b2)
tmp = p + '.tmp_r284'
with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
    f.write(txt)
os.replace(tmp, p)
print('OK stb_truetype.h (3 noinline re-applied on v1.22)')
print('=== ALL REMAINING PATCHES APPLIED ===')
