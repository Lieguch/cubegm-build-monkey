#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_r284_patch.py —— R284 批量源码修复（s05 调用点 / s20 类型 / s48 noinline）
精确字符串替换 + 逐条断言；任何一条不命中即整体失败（不落半截状态）。
"""
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

# ============ s05: 恢复工厂 2 参调用点 ============
edit('src/proprietary/mui/FUN_000229f8_mui_run_game.c', [(
    "uVar3 = run_game(acStack_52c);   /* R267：run_game 只有 1 个形参 */",
    "uVar3 = run_game(acStack_52c,0);   /* R284：恢复工厂调用点（语料 mui_run_game.c:242 = 2 参）；run_game 为变参原型 */",
)])
edit('src/proprietary/misc/FUN_000266e4_Mp3DecodeLoop.c', [(
    "SoundClose(param_1);   /* R267：SoundClose 只有 1 个形参（多传的第二个实参被丢弃） */",
    "SoundClose(param_1,piVar4 + 1);   /* R284：恢复工厂调用点（语料 Mp3DecodeLoop.c:34 = 2 参）；SoundClose 为变参原型 */",
)])
edit('src/proprietary/core/FUN_002b7510_run_game.c', [(
    "FBA_Load(param_1);   /* R268：FBA_Load 只有 1 个形参（多传的 Filetype 被丢弃） */",
    "FBA_Load(param_1,Filetype);   /* R284：恢复工厂调用点（语料 run_game.c:50 = 2 参）；FBA_Load 为变参原型 */",
)])

# ============ s05: proto.h / proto.h.strict 三函数改变参原型 ============
for hdr in ('src/compat/proto.h', 'src/compat/proto.h.strict'):
    edit(hdr, [
        ("extern void SoundClose(int);  /* R267：原 K&R 空参 → 精确原型（形参取自定义；编译器从此校验实参个数） */",
         "extern void SoundClose(int param_1, ...);  /* R284：原 K&R → 变参原型。工厂调用点 1 参/2 参并存（语料：ui_deinit/filelist_run_game/mui_run_game 均 1 参，Mp3DecodeLoop 2 参）⇒ 非变参无法同时兼容；.text 实测与非变参一致（zig cc -Os ARM32 对拍） */"),
        ("extern gh_u4 FBA_Load(char *);  /* R267：原 K&R 空参 → 精确原型（形参取自定义；编译器从此校验实参个数） */",
         "extern gh_u4 FBA_Load(char *param_1, ...);  /* R284：原 K&R → 变参原型。工厂 run_game.c:35 传 1 参、:50 传 2 参（Filetype）⇒ 变参兼容 */"),
        ("extern gh_u4 run_game(char *);  /* R267：原 K&R 空参 → 精确原型（形参取自定义；编译器从此校验实参个数） */",
         "extern gh_u4 run_game(char *param_1, ...);  /* R284：原 K&R → 变参原型。工厂 mui_run_game.c:242 传 2 参（acStack_52c,0）⇒ 变参兼容 */"),
    ])

# ============ s05: 三个定义改变参（.text 中立，已实测） ============
edit('src/proprietary/hw/FUN_00022404_SoundClose.c', [(
    "void SoundClose(int param_1)\n",
    "void SoundClose(int param_1, ...)   /* R284：变参原型（工厂调用点 1/2 参并存）；.text 与非变参一致 */\n",
)])
edit('src/proprietary/core/FUN_002b6c14_FBA_Load.c', [(
    "gh_u4 FBA_Load(char *param_1)\n",
    "gh_u4 FBA_Load(char *param_1, ...)   /* R284：变参原型（工厂调用点 1/2 参并存）；.text 与非变参一致 */\n",
)])
edit('src/proprietary/core/FUN_002b7510_run_game.c', [(
    "gh_u4 run_game(char *param_1)\n",
    "gh_u4 run_game(char *param_1, ...)   /* R284：变参原型（工厂 mui_run_game 传 2 参）；.text 与非变参一致 */\n",
)])

# ============ s20: 9 处 GetZipItemA ZIPENTRY* cast ============
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

# ============ s20: mui_setting 13 处 &DAT_002dd860 → (char *) ============
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

# ============ s48: v1.22 重打 R204 noinline 补丁 ============
p = P('src/upstream/stb/stb_truetype.h')
with io.open(p, encoding='utf-8', newline='') as f:
    txt = f.read()
pairs = [
    ("static void stbtt__csctx_rline_to(stbtt__csctx *ctx, float dx, float dy)\n{",
     "/* R204/R284：noinline —— 工厂 ELF 有 stbtt__csctx_rline_to 实体符号（72B）；\n"
     " * 不加则被 clang -Os 内联进 stbtt__run_charstring，符号消失 ⇒ s48 门禁 FAIL。\n"
     " * .text 形态：v1.26 同款补丁，实测与工厂对拍通过。 */\n"
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
print('=== ALL PATCHES APPLIED ===')
