#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dce_ref_diff —— 检测「源码引用的工厂符号被优化器消除」（Δ 门禁）。

为什么需要它（GAP 16.99 的根因）
--------------------------------
重建源码来自 Ghidra 反编译，而 Ghidra 会按**类型推断**把工厂栈上的**一个连续缓冲**拆成
若干独立局部量。典型形态：

    char *local_150;          /* -0x150 */
    char *local_14c[4];       /* -0x14c…-0x140 */
    gh_u4 uStack_13c;         /* -0x13c */
    ...
    ppcVar4 = &local_150;     /* 取标量地址 */
    ppcVar4 = ppcVar4 + 1;    /* ★ 跨对象步进 = C 的未定义行为 */

GCC/clang 允许假定「越界指针不被解引用」，于是把**后续槽的写入整体删除**。
后果：原厂跑 10 条候选路径的循环退化成 1 条 —— **产物能链接、能启动，但语义发散**，
而且**任何静态门禁都不会报**（符号只是"少了一个"，不是"未定义"）。

判据（可机械执行、无需人判断语义）
----------------------------------
对同一个 .c **只改优化级别**编译两次，比较 UNDEF 里的工厂符号（`DAT_*` / `UNK_*`）：

    Δ = UNDEF(-O0) 减去 UNDEF(-Os)

Δ 非空 ⇒ 源码里那些工厂数据引用**在 -Os 下消失了**。两种可能：
  (a) UB 被消除（缺陷，见 GAP 16.99）；
  (b) 存储确实是死的（合法优化，例如值从未被使用、或被常量折叠掉）。
★ 因此 Δ 是**待核清单**，不是缺陷证明：默认按 (a) 处理（硬失败），
  确认属于 (b) 的必须在 ALLOW 里登记，并在 GAP.md 写明「为什么语义不变」。
★ 2026-09-23 交叉对照（两个独立仪器）：13 个存量 Δ 文件**全部**在 `tools/prop_equiv.py`
  里判为 **OK**（size 比 0.895–1.448，健康带 p95=1.33），且用 `tools/factory_fn_stack.py`
  对工厂函数反汇编可见「该槽写了但从未按常量位移读回」⇒ 判定为**低风险（不阻塞替代）**，
  但**保守保留在债务表**并逐条标注证据 —— 待有更强判据（帧指针别名数据流）时再清。
★ 工具会给每个 Δ 文件附一个 `[UB?]` 提示（源码里出现「取标量地址 + 步进」形态），
  仅用于分诊排序，不作为判据。

★ 为什么用 `-O0` 当参照：`-O0` 不做 DCE，它最接近「源码字面写了什么引用」。
★ 为什么是 UNDEF：工厂数据/代码符号在 .o 里必然是 UNDEF（由 .set 别名供应），
  所以 UNDEF 集合就是「这个 TU 引用了哪些工厂符号」的精确清单。

自证（`--self-test`，先自证再信数）
----------------------------------
* 正例：人造「拆局部量 + 跨对象步进」样本 ⇒ Δ 必须非空
* 反例：人造「同一个数组内正常步进」样本 ⇒ Δ 必须为空
* 回归：真实文件 `core/FUN_002b6c14_FBA_Load.c` 修复后 ⇒ Δ 必须为空（防复发）

用法
----
    CC="<zig> cc" python tools/dce_ref_diff.py            # 全量扫描
    CC="<zig> cc" python tools/dce_ref_diff.py --self-test
    CC="<zig> cc" python tools/dce_ref_diff.py --limit 20  # 只扫前 N 个（调试）

退出码：0 = 无 Δ（或全在 ALLOW 里）；2 = 存在未登记的 Δ
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'proprietary')
INC = os.path.join(ROOT, 'src', 'compat')

# ★ 已登记待核债务：{相对路径: (符号元组, 理由)}。
#
# 纪律：这是一张**必须缩小**的债务表，不是豁免。
#   · 每一条都必须能追溯到 GAP.md 的条目；
#   · 已判定为「合法 DCE」的写明为什么语义不变；
#   · 已判定为「缺陷」的必须修掉并从此表移除（修掉即证据）。
# 门禁只对**表外新增**的 Δ 硬失败 —— 这样既立刻拦住回归，又不掩盖存量。
#
# 判定方法（两种，都要落到原厂反汇编）：看该局部量在**原厂**是否被读。
#   ① 重建源码里「只赋值、从不读」⇒ 大概率合法 DCE（见 #4 的 local_32c）；
#   ② 重建源码里「被跨对象步进读」⇒ UB-DCE，是真缺陷（见已修的 core/FUN_002b6c14_FBA_Load.c）。
ALLOW = {
    'src/proprietary/input/FUN_0000b014_TestUSBJoy.c':
        (('DAT_003af00c', 'DAT_003af010', 'DAT_003af014'), '低风险（GAP 17.00）：prop_equiv size 比 TestUSBJoy 708/688=0.972 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/misc/FUN_0002187c_DisplayPage_list.c':
        (('DAT_003af2a0',), '低风险（GAP 17.00）：prop_equiv size 比 DisplayPage_list 248/272=1.097 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0001bf80_mui_DisplayGameSum.c':
        (('DAT_0020202d',), '低风险（GAP 17.00）：prop_equiv size 比 mui_DisplayGameSum 232/336=1.448 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_00023204_mui_menu.c':
        (('DAT_003b2320',), '低风险（GAP 17.00）：prop_equiv size 比 mui_menu 2840/3488=1.228 OK；且 local_32c 只赋值从不读；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_00023e10_mui_type.c':
        (('DAT_003b2320',), '低风险（GAP 17.00）：prop_equiv size 比 mui_type 4380/5332=1.217 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_00025094_mui_search.c':
        (('DAT_003b2320',), '低风险（GAP 17.00）：prop_equiv size 比 mui_search 5356/7188=1.342 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_000277bc_mui_recent.c':
        (('DAT_003b2320',), '低风险（GAP 17.00）：prop_equiv size 比 mui_recent 4492/4932=1.098 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_00028a74_mui_shoucang.c':
        (('DAT_003b2320',), '低风险（GAP 17.00）：prop_equiv size 比 mui_shoucang 3600/4176=1.160 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0002d0d4_mui_joystick_setting.c':
        (('DAT_003af820', 'DAT_003af824', 'DAT_003af828', 'DAT_003af82c'), '低风险（GAP 17.00）：prop_equiv size 比 mui_joystick_setting 3684/3604=0.978 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0002e040_mui_video_setting.c':
        (('DAT_003af820', 'DAT_003af824', 'DAT_003af828', 'DAT_003af82c'), '低风险（GAP 17.00）：prop_equiv size 比 mui_video_setting 2552/2756=1.080 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0002eac8_mui_load_state.c':
        (('DAT_003af820', 'DAT_003af824'), '低风险（GAP 17.00）：prop_equiv size 比 mui_load_state 2020/1852=0.917 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0002f320_mui_save_state.c':
        (('DAT_003af820', 'DAT_003af824'), '低风险（GAP 17.00）：prop_equiv size 比 mui_save_state 2704/2420=0.895 OK；工厂侧该槽属「写了不读」'),
    'src/proprietary/mui/FUN_0002ff8c_PauseMenu.c':
        (('DAT_003af820', 'DAT_003af824', 'DAT_003af82c'), '低风险（GAP 17.00）：prop_equiv size 比 PauseMenu 1564/1400=0.895 OK；工厂侧该槽属「写了不读」'),
}
FACTORY_PREFIX = ('DAT_', 'UNK_')

# 仅用于分诊排序的"UB 形态"提示：
#   形态 A = 取**局部标量**的地址（Ghidra 拆出来的 local_XXX / uStack_XXX / acStack_XXX …）
#   形态 B = 同一个指针变量做 `p = p + n` 步进
RE_UB_A = re.compile(r'&\s*(?:local_|uStack_|iStack_|auStack_|acStack_|stack_|pStack_|uVar|iVar)')
RE_UB_B = re.compile(r'\b([A-Za-z_]\w*)\s*=\s*\1\s*\+\s*\d')


def ub_hint(path):
    try:
        t = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return False
    return bool(RE_UB_A.search(t)) and bool(RE_UB_B.search(t))


def cflags(opt):
    cc = os.environ.get('CC', 'arm-linux-gnueabihf-gcc')
    if 'zig' in cc:
        arch = ['-target', 'arm-linux-gnueabihf', '-mfloat-abi=hard', '-mfpu=neon']
    else:
        arch = ['-march=armv7-a', '-mfloat-abi=hard', '-mfpu=neon', '-fno-pic']
    return [opt, '-c', '-w', '-Wno-error=implicit-function-declaration',
            '-I' + INC] + arch + ['-fno-stack-protector', '-U_FORTIFY_SOURCE',
                                  '-D_FORTIFY_SOURCE=0']


def undef_factory(obj):
    """读 ELF32 .o 的 .symtab，返回 UNDEF 里的工厂符号集合。"""
    if not os.path.exists(obj) or os.path.getsize(obj) < 64:
        return None                      # 编译失败
    b = open(obj, 'rb').read()
    if b[:4] != b'\x7fELF':
        return None
    e_shoff, = struct.unpack_from('<I', b, 0x20)
    ents, shn, shx = struct.unpack_from('<HHH', b, 0x2e)
    sh = [struct.unpack_from('<10I', b, e_shoff + i * ents) for i in range(shn)]
    names = []
    st = sh[shx]
    for s in sh:
        t = b[st[4] + s[0]:]
        names.append(t[:t.index(b'\x00')].decode('ascii', 'replace'))
    if '.symtab' not in names or '.strtab' not in names:
        return None
    S = names.index('.symtab')
    T = names.index('.strtab')
    tb = b[sh[T][4]:sh[T][4] + sh[T][5]]
    out = set()
    for i in range(sh[S][5] // 16):
        o = sh[S][4] + i * 16
        no, va, sz, info, oth, shnd = struct.unpack_from('<IIIBBH', b, o)
        if not no or shnd != 0:
            continue
        n = tb[no:tb.index(b'\x00', no)].decode('ascii', 'replace')
        if n.startswith(FACTORY_PREFIX):
            out.add(n)
    return out


def compile_one(src, opt, out):
    cc = os.environ.get('CC', 'arm-linux-gnueabihf-gcc').split()
    cmd = cc + cflags(opt) + [src, '-o', out]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0


def delta_of(src, tmpd):
    o0 = os.path.join(tmpd, 'a.o')
    os_ = os.path.join(tmpd, 'b.o')
    for p in (o0, os_):
        if os.path.exists(p):
            os.remove(p)
    ok0 = compile_one(src, '-O0', o0)
    ok1 = compile_one(src, '-Os', os_)
    if not ok0 or not ok1:
        return None, None            # 编译失败 → 交给别的门禁管
    a = undef_factory(o0)
    c = undef_factory(os_)
    if a is None or c is None:
        return None, None
    return a, c


def self_test():
    print('=' * 96)
    print('自证：先用已知答案的样本验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-22s %s' % (tag, got, '✓' if good else '★ FAIL'))

    tmpd = tempfile.mkdtemp(prefix='dce_')
    hdr = os.path.join(tmpd, 'globals.h')
    with open(hdr, 'w') as fh:
        for n in ('DAT_003b0130', 'DAT_003b0134', 'DAT_003b0140'):
            fh.write('extern unsigned int %s;\n' % n)

    # ① 正例：拆局部量 + 跨对象步进（UB）⇒ 期望 Δ 非空
    pos = os.path.join(tmpd, 'pos.c')
    with open(pos, 'w') as fh:
        fh.write('''#include "globals.h"
char *walk(char **p);
/* 单个缓冲被拆成两个局部量，然后用 &标量 + k 跨对象步进 —— 与原厂 Ghidra 输出同形态 */
int pos(void){
  char *local_150;
  char *local_14c[2];
  char **ppcVar4;
  unsigned acc = 0;
  local_150 = (char *)DAT_003b0130;
  local_14c[0] = (char *)DAT_003b0134;
  ppcVar4 = &local_150;
  ppcVar4 = ppcVar4 + 1;
  acc += (unsigned)(unsigned long)ppcVar4[0];
  return (int)acc;
}
''')
    a, c = delta_of(pos, tmpd)
    chk('正例  拆局部量+跨对象步进 → Δ 非空',
        (sorted(a - c) != []) if (a is not None and c is not None) else '编译失败',
        True)

    # ② 反例：同一个数组内正常步进 + **运行时下标**（强制两个引用都存活）⇒ Δ 必须为空
    neg = os.path.join(tmpd, 'neg.c')
    with open(neg, 'w') as fh:
        fh.write('''#include "globals.h"
char *pick(char **slots, int i);   /* 运行时下标 ⇒ 不能常量折叠 */
char *neg(int i){
  char *slots[3];
  slots[0] = (char *)DAT_003b0130;
  slots[1] = (char *)DAT_003b0134;
  slots[2] = 0;
  return pick(slots, i);
}
''')
    a, c = delta_of(neg, tmpd)
    chk('反例  同一数组内步进(运行时下标) → Δ 为空',
        (sorted(a - c) == []) if (a is not None and c is not None) else '编译失败',
        True)

    # ③ 回归：真实文件修复后 Δ 必须为空（防复发）
    real = os.path.join(SRC, 'core', 'FUN_002b6c14_FBA_Load.c')
    if os.path.exists(real):
        a, c = delta_of(real, tmpd)
        chk('回归  FUN_002b6c14_FBA_Load.c → Δ 为空',
            (sorted(a - c) == []) if (a is not None and c is not None) else '编译失败',
            True)

    # ④ 反例：非法输入必须返回 None（不能把失败当"无 Δ"）
    chk('反例  不存在的文件 → 视为不可判（None）',
        delta_of(os.path.join(tmpd, 'nope.c'), tmpd)[0], None)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--out', help='报告输出路径')
    a = ap.parse_args()

    if a.self_test and not self_test():
        return 2

    files = []
    for dp, dn, fn in os.walk(SRC):
        for f in fn:
            if f.endswith('.c'):
                files.append(os.path.join(dp, f))
    files.sort()
    if a.limit:
        files = files[:a.limit]

    tmpd = tempfile.mkdtemp(prefix='dce_scan_')
    lines = []
    hits = []
    skipped = []
    for p in files:
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        aa, cc = delta_of(p, tmpd)
        if aa is None:
            skipped.append(rel)
            continue
        d = sorted(aa - cc)
        allow = set(ALLOW.get(rel, ([], ''))[0])
        real = [x for x in d if x not in allow]
        if real:
            hits.append((rel, real, ub_hint(p)))
        lines.append('%-70s Δ=%-3d %s%s' % (rel, len(d), '[UB?] ' if (d and ub_hint(p)) else '      ',
                                            ' '.join(d[:10])))

    hdr = ['=' * 96,
           'DCE 引用差门禁（Δ = UNDEF(-O0) 减去 UNDEF(-Os) 的工厂符号）',
           '=' * 96,
           '扫描 %d 个文件；编译失败跳过 %d 个；★ 表外新增 Δ 的文件 %d 个'
           % (len(files), len(skipped), len(hits)),
           '已登记待核债务 %d 条（该表必须缩小，见 GAP 17.00）' % len(ALLOW), '']
    if hits:
        hdr.append('【★ 表外新增 Δ】—— 这些文件里的工厂数据引用在 -Os 下消失了（硬失败）：')
        hdr.append('   %-66s %-6s %s' % ('文件', 'UB?', 'Δ 符号'))
        for rel, d, hint in hits:
            hdr.append('   %-66s %-6s %s' % (rel, '★' if hint else '-', ' '.join(d)))
        hdr.append('')
        hdr.append('   ★ 带 [UB?] 的优先查：源码里有「取局部标量地址 + p = p + n」形态，')
        hdr.append('     这是 C 未定义行为，-Os 会据此删除后续槽的写入（GAP 16.99）。')
        hdr.append('')
    else:
        hdr.append('【结论】无表外新增 Δ ⇒ 通过（存量债务见下表）')
        hdr.append('')
    hdr.append('【已登记待核债务】')
    hdr.append('   %-66s %s' % ('文件', '理由'))
    for rel in sorted(ALLOW):
        hdr.append('   %-66s %s' % (rel, ALLOW[rel][1]))
    hdr.append('')
    hdr.append('【全部明细】（Δ=0 也列出，便于看出扫描确实跑到了）')
    txt = '\n'.join(hdr + lines) + '\n'
    sys.stdout.write(txt)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, 'w', encoding='utf-8').write(txt)
    if skipped:
        print('\n  （跳过 = 编译失败，不属于本门禁职责）')
    return 2 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
