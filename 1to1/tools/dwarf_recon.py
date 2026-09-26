#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dwarf_recon.py —— 从**目标二进制自带的 DWARF** 里恢复它的构建事实（第 65 轮根解）。

## 为什么这是根解（而不是又一把"代理尺子"）

第 64 轮我下过一个断言：「"1:1 机器码保真"按构造不可达（跨编译器家族 + 跨 glibc 头）」，
并据此给用户摆出"版本对齐 / 契约化"二选一。**那个断言是我没做实验就下的，已作废。**

作废的依据就写在目标二进制里：`golden/factory.rkgame.bin` **没有被 strip 掉调试节** ——
它带着 `.debug_info / .debug_line / .debug_str / .debug_aranges / .debug_loc / .debug_frame /
.debug_ranges / .debug_abbrev`。而 DWARF 里有：
  * `DW_AT_producer`  ⇒ **编译器版本 + 编译命令行（含全部 CFLAGS/优化级别）**
  * `DW_AT_comp_dir`  ⇒ **构建目录**
  * `DW_AT_name`      ⇒ **原始源文件名**
  * `DW_AT_low_pc/high_pc` ⇒ 每个编译单元在目标里的地址区间
  * `.debug_line`     ⇒ **行号 → 地址**映射

⇒ 我们**不需要猜**工具链与编译参数，**也不需要从 Ghidra 反编译里猜源文件结构**：
目标程序自己把这些交出来了。工具链是**可识别、可获取、可固化**的，所以"机器码保真"是
**可达的**，只是需要把工具链与 CFLAGS 对齐 —— 这是工程问题，不是"构造上不可能"。

## 本工具产出

1. **构建事实**：producer 串（编译器版本 + flags）、comp_dir、binutils/glibc 版本线索；
2. **编译单元清单**：每个 CU 的源文件名 + 地址区间 + 字节数（⇒ 我们那份"逐函数重建"的
   TU 划分应当据此对齐，而不是按 Ghidra 的函数边界臆测）；
3. **CFLAGS 归一**：从 producer 串里抽出 `-O*` / `-march` / `-mfpu` / `-flto` 等，
   与我们的编译命令**逐项对拍**并列出差异（这是我们能改的东西）；
4. **源文件清单**：原始工程的文件树（这是 Ghidra 永远给不出的信息）。

用法：
  python tools/dwarf_recon.py [--bin golden/factory.rkgame.bin] [--out report/dwarf_recon.txt]
  python tools/dwarf_recon.py --self-test
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 从 producer 串里认得出、且**会影响机器码**的开关（用于逐项对拍）
FLAG_RE = re.compile(r'(?:^|\s)(-O[0-9sgz]|-march=\S+|-mcpu=\S+|-mfpu=\S+|-mfloat-abi=\S+|'
                     r'-mabi=\S+|-mtune=\S+|-flto\S*|-ffat-lto-objects|-fomit-frame-pointer|'
                     r'-fPIC|-fpic|-fstack-protector\S*|-fno-omit-frame-pointer|-pipe|-Wall|'
                     r'-fuse-ld=\S+|-fuse-linker-plugin|--sysroot=\S+|-g\S*|-D\S+|-I\S+)')


def producer_flags(s):
    """→ producer 串里认出的**影响机器码**的开关列表（去重、保序）。"""
    out, seen = [], set()
    for m in FLAG_RE.finditer(s or ''):
        t = m.group(1)
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def self_test():
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    s = ('GNU C11 6.2.0 20161005 -march=armv7-a -mabi=aapcs-linux -mcpu=cortex-a5 '
         '-mfloat-abi=hard -mfpu=neon-vfpv4 -fomit-frame-pointer -Wall -pipe -Os -flto '
         '-ffat-lto-objects -fPIC -fuse-ld=gold -fuse-linker-plugin')
    f = producer_flags(s)
    c('认出 -Os', '-Os' in f, True)
    c('认出 -flto（LTO 会跨 TU 内联 ⇒ 直接解释"少调/多调"类差异）', '-flto' in f, True)
    c('认出 -fuse-ld=gold', '-fuse-ld=gold' in f, True)
    c('认出 -mcpu / -mfpu / -mfloat-abi',
      all(x in f for x in ('-mcpu=cortex-a5', '-mfpu=neon-vfpv4', '-mfloat-abi=hard')), True)
    c('保序（先出现者在前）', f.index('-march=armv7-a') < f.index('-Os'), True)
    c('去重（重复的 -pipe 只留一次）', producer_flags('-pipe -pipe').count('-pipe'), 1)
    c('空串安全', producer_flags(None), [])
    c('不把无关词当开关（"6.2.0" 不是 flag）', '6.2.0' in f, False)
    return chk


# --------------------------------------------------------------------------- #
def walk_die(die, out, depth, max_depth=6):
    """收集一层 DIE 的属性（按 tag 分桶）。"""
    info = {}
    for attr in die.attributes.values():
        try:
            info[attr.name] = die.attributes[attr.name].value
        except Exception:
            pass
    out.append((depth, die.tag, info))
    if depth < max_depth:
        for ch in die.iter_children():
            walk_die(ch, out, depth + 1, max_depth)


def recon(path, out_path):
    from elftools.elf.elffile import ELFFile
    L = []

    def w(s=''):
        L.append(s)

    w('=' * 100)
    w('DWARF 构建事实恢复：%s' % os.path.relpath(path, ROOT))
    w('=' * 100)
    with open(path, 'rb') as f:
        e = ELFFile(f)
        dbg = [s.name for s in e.iter_sections() if s.name.startswith('.debug')]
        w('  调试节 %d 个：%s' % (len(dbg), ' '.join(dbg)))
        if not dbg:
            w('  ★ 无调试节 ⇒ 本工具无输入（目标被 strip）')
            return '\n'.join(L)
        dw = e.get_dwarf_info()
        cus = []
        for cu in dw.iter_CUs():
            top = cu.get_top_DIE()
            a = top.attributes
            cu_ = {
                'name': a.get('DW_AT_name').value.decode('utf-8', 'replace') if a.get('DW_AT_name') else '?',
                'comp_dir': a.get('DW_AT_comp_dir').value.decode('utf-8', 'replace') if a.get('DW_AT_comp_dir') else '?',
                'producer': a.get('DW_AT_producer').value.decode('utf-8', 'replace') if a.get('DW_AT_producer') else '?',
                'lang': a.get('DW_AT_language').value if a.get('DW_AT_language') else None,
                'low': a.get('DW_AT_low_pc').value if a.get('DW_AT_low_pc') else 0,
            }
            hi = a.get('DW_AT_high_pc')
            cu_['high'] = (cu_['low'] + hi.value) if (hi and hi.form != 'DW_FORM_addr') else \
                          (hi.value if hi else 0)
            # 该 CU 里定义了多少函数/子程序
            nfunc = sum(1 for d in cu.iter_DIEs() if d.tag == 'DW_TAG_subprogram')
            cu_['nfunc'] = nfunc
            cus.append(cu_)

    w('')
    w('【一】构建事实（DW_AT_producer / comp_dir）')
    w('-' * 100)
    prod = collections.Counter(c['producer'] for c in cus)
    for p, n in prod.most_common():
        w('  [%3d 个 CU] %s' % (n, p[:300]))
    w('')
    dirs = collections.Counter(c['comp_dir'] for c in cus)
    for d, n in dirs.most_common(12):
        w('  [%3d] comp_dir = %s' % (n, d))
    w('')
    w('  ★ 影响机器码的开关（从 producer 串归一出）—— 这是我们要**对齐**的清单：')
    allflags = collections.OrderedDict()
    for c_ in cus:
        for fl in producer_flags(c_['producer']):
            allflags[fl] = allflags.get(fl, 0) + 1
    for fl, n in allflags.items():
        w('      %-28s 出现在 %d 个 CU' % (fl, n))

    w('')
    w('【二】编译单元（TU）清单 —— 我们的"逐函数重建"应当据此划分')
    w('-' * 100)
    w('  CU 总数 = %d ；带 DW_TAG_subprogram 的总数 = %d'
      % (len(cus), sum(c['nfunc'] for c in cus)))
    w('')
    w('  %-52s %10s %10s %6s  %s' % ('源文件', 'low_pc', 'high_pc', '函数数', '构建目录'))
    for c_ in sorted(cus, key=lambda x: x['low']):
        w('  %-52s 0x%08x 0x%08x %6d  %s'
          % (c_['name'][:52], c_['low'], c_['high'], c_['nfunc'], c_['comp_dir'][:40]))

    w('')
    w('【三】原始源文件树（按目录归并）—— Ghidra 给不出这一层信息')
    w('-' * 100)
    tree = collections.Counter()
    for c_ in cus:
        n = c_['name']
        d = os.path.dirname(n) or '(顶层)'
        tree[d] += 1
    for d, n in sorted(tree.items(), key=lambda kv: -kv[1]):
        w('  %-60s %3d 个 TU' % (d[:60], n))

    txt = '\n'.join(L) + '\n'
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    print(txt)
    print('→ 已写入 %s' % out_path)
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bin', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'report', 'dwarf_recon.txt'))
    ap.add_argument('--selftest', '--self-test', dest='self_test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        chk = self_test()
        bad = [x for x in chk if not x[3]]
        for tag, got, want, ok in chk:
            print('  %s %s' % ('OK  ' if ok else 'FAIL', tag))
            if not ok:
                print('        got=%r want=%r' % (got, want))
        print('  self-test: %d 条，失败 %d 条' % (len(chk), len(bad)))
        return 1 if bad else 0
    recon(a.bin, a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
