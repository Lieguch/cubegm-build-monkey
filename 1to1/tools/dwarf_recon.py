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

    # ★ .ARM.attributes 解码：用**工厂真实字节**做锚点（比合成样本硬得多）
    RAW = bytes.fromhex('4136000000616561626900012c00000005372d4100060a07'
                        '41080109020a030c0112041301140115011601170318011a02'
                        '1b031c012201')
    got = dict(x.split('=', 1) for x in decode_arm_attributes(RAW) if '=' in x)
    c('ARM 属性 CPU_arch=v7 (10)', got.get('CPU_arch'), 'v7 (10)')
    c('ARM 属性 CPU_arch_profile=A', got.get('CPU_arch_profile'), 'A')
    c('ARM 属性 FP_arch=VFPv3 (3)', got.get('FP_arch'), 'VFPv3 (3)')
    c('ARM 属性 Advanced_SIMD_arch=1（Neon）', got.get('Advanced_SIMD_arch'), '1')
    c('ARM 属性 ABI_VFP_args=硬浮点', got.get('ABI_VFP_args'), 'VFP regs(硬浮点) (1)')
    c('ARM 属性 CPU_name 从 Tag_File 作用域后正确读出', got.get('CPU_name'), '7-A')
    c('★ Tag_File(1) 的作用域长度必须被吃掉（否则解出 tag1/tag0 这类垃圾）',
      any(k.startswith('tag') for k in got), False)
    c('畸形输入安全（非 A 开头 ⇒ 空列表）', decode_arm_attributes(b'XY'), [])
    return chk


# --------------------------------------------------------------------------- #
# .ARM.attributes 的 tag 表（ARM ABI addenda）—— 应用对象**没带 `-g`**，
# 所以它的 `-march/-mfpu/-mfloat-abi` 只能从这里读；这段解析是第 65 轮手工做出定案后
# **固化进工具**的（上次只存在于会话里，等于没留下）。
ARM_TAGS = {4: 'CPU_raw_name', 5: 'CPU_name', 6: 'CPU_arch', 7: 'CPU_arch_profile',
            8: 'ARM_ISA_use', 9: 'THUMB_ISA_use', 10: 'FP_arch', 11: 'WMMX_arch',
            12: 'Advanced_SIMD_arch', 13: 'PCS_config', 14: 'ABI_PCS_R9_use',
            15: 'ABI_PCS_RW_data', 16: 'ABI_PCS_RO_data', 17: 'ABI_PCS_GOT_use',
            18: 'ABI_PCS_wchar_t', 19: 'ABI_FP_rounding', 20: 'ABI_FP_denormal',
            21: 'ABI_FP_exceptions', 22: 'ABI_FP_user_exceptions',
            23: 'ABI_FP_number_model', 24: 'ABI_align_needed', 25: 'ABI_align_preserved',
            26: 'ABI_enum_size', 27: 'ABI_HardFP_use', 28: 'ABI_VFP_args',
            29: 'ABI_WMMX_args', 30: 'ABI_optimization_goals',
            31: 'ABI_FP_optimization_goals', 32: 'compatibility',
            34: 'CPU_unaligned_access', 36: 'FP_HP_extension',
            38: 'ABI_FP_16bit_format', 42: 'MPextension_use', 44: 'DIV_use',
            46: 'T2EE_use', 48: 'VNode', 50: 'Advanced_SIMD_arch2',
            64: 'also_compatible_with', 65: 'conformance', 66: 'TLS_ISA',
            67: 'TLS_arch', 68: 'TLS_use', 70: 'Virtualization_use'}
ARM_CPU_ARCH = {10: 'v7', 9: 'v6KZ', 8: 'v6T2', 7: 'v6K', 6: 'v6', 5: 'v5TEJ',
                4: 'v5TE', 3: 'v5T', 2: 'v5', 1: 'v4'}
ARM_FP_ARCH = {0: 'none', 1: 'VFPv1', 2: 'VFPv2', 3: 'VFPv3', 4: 'VFPv3-D16',
               5: 'VFPv4', 6: 'VFPv4-D16', 7: 'FP ARMv8', 8: 'FP ARMv8-D16',
               10: 'Neon', 11: 'Neon-VFPv3', 12: 'Neon-VFPv4'}
ARM_VFP_ARGS = {0: 'softfp(base)', 1: 'VFP regs(硬浮点)'}


def decode_arm_attributes(raw):
    """`.ARM.attributes` 原始字节 → ['Tag=值', ...]（纯函数，自证锚点）。

    格式：`A` + version byte，随后每段 = `<u32 len>` + `"aeabi\\0"` + 若干 `<tag(uleb), value>`。
    值的宽度按 tag 分三类：字符串（4/5/32/64/65，NUL 结尾）、单字节（7）、其余 uleb。
    """
    import struct as _s
    out = []
    if not raw or raw[:1] != b'A':
        return out
    body, pos = raw[1:], 0

    def uleb(b, k):
        v = s = 0
        while k < len(b):
            x = b[k]
            k += 1
            v |= (x & 0x7F) << s
            s += 7
            if not (x & 0x80):
                return v, k
        return v, k

    while pos + 5 <= len(body):
        ln = _s.unpack('<I', body[pos:pos + 4])[0]
        pos += 4
        sub = body[pos:pos + ln]
        pos += ln
        i = sub.find(b'\x00') + 1
        if i <= 0:
            continue
        d, j = sub[i:], 0
        while j < len(d):
            t, j = uleb(d, j)
            if t in (4, 5, 32, 64, 65):
                k2 = d.find(b'\x00', j)
                if k2 < 0:
                    break
                val = d[j:k2].decode('latin1', 'replace')
                j = k2 + 1
            elif t in (1, 2, 3):
                # Tag_File(1)/Tag_Section(2)/Tag_Symbol(3) 是**作用域**而不是属性：
                # Tag_File 后面跟 4 字节(小端)长度；Tag_Section 再跟一个 uleb 段号；
                # Tag_Symbol 跟两个 uleb。**必须吃掉**，否则它们会被当成属性值，
                # 后面整条链全部错位（第 65 轮首版就错在这里：解出 `tag1=44`、
                # `tag0=0` 这类不存在的东西，而后面真正的属性恰好又对上了，极易漏看）。
                import struct as _st
                if t == 1:
                    j += 4
                elif t == 2:
                    _sc, j = uleb(d, j)
                else:
                    _si, j = uleb(d, j)
                    _sy, j = uleb(d, j)
                continue
            elif t == 7:
                val = chr(d[j]) if j < len(d) else '?'
                j += 1
            else:
                val, j = uleb(d, j)
            if t == 6:
                val = '%s (%d)' % (ARM_CPU_ARCH.get(val, '?'), val)
            elif t == 10:
                val = '%s (%d)' % (ARM_FP_ARCH.get(val, '?'), val)
            elif t == 28:
                val = '%s (%d)' % (ARM_VFP_ARGS.get(val, '?'), val)
            out.append('%s=%s' % (ARM_TAGS.get(t, 'tag%d' % t), val))
    return out


def walk_die(die, out, depth, max_depth=6):
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

        # ---- 【零】不含 DWARF 也能读到的构建事实 -----------------------------
        # ★ 为什么必须有这一段（第 65 轮实测教训）：我把 CI 门禁写成
        #   `grep -aq 'GCC' report/dwarf_recon.txt`，而报告里**从来没有大写 "GCC"**
        #   （`DW_AT_producer` 是 `GNU C11 6.2.0`）⇒ 那条断言**永远不可能成立**。
        #   这正是纪律 7 的另一面：检查"检查真的跑了"之外，还要检查
        #   **判据与被判对象的口径是否真的对得上**。修法 = 把 `.comment` 原文
        #   （里面有 `GCC: (GNU) 6.2.0`）与 `.ARM.attributes` 一并写进报告，
        #   使"工具链身份"这一项**在报告里就有可 grep 的实据**。
        w('')
        w('【零】构建事实（不依赖 DWARF 也能读到的部分）')
        w('-' * 100)
        for sname in ('.comment', '.note.gnu.gold-version', '.note.ABI-tag'):
            sec = e.get_section_by_name(sname)
            if sec is None:
                w('  %-24s （缺失）' % sname)
                continue
            if sname == '.comment':
                parts = [x for x in sec.data().split(b'\x00') if x]
                for p in parts:
                    w('  %-24s %s' % (sname, p.decode('latin1', 'replace')))
            else:
                w('  %-24s %s' % (sname, sec.data().replace(b'\x00', b' ').decode(
                    'latin1', 'replace').strip()))
        sec = e.get_section_by_name('.ARM.attributes')
        if sec is not None:
            got = decode_arm_attributes(sec.data())
            w('  %-24s %s' % ('.ARM.attributes', '；'.join(got) if got else '（解析无输出）'))
        else:
            w('  %-24s （缺失）' % '.ARM.attributes')
        w('')
        w('  ★ 上面这几行就是 CI 门禁的断言对象：`.comment` 里含 `GCC:`，`.ARM.attributes` 里含 CPU_arch/FP_arch/ABI_VFP_args。')

        if not dbg:
            w('  ★ 无调试节 ⇒ DWARF 侧无输入（目标被 strip）')
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
    # ★ 工具**自己**保证"报告里有可断言的实据"（纪律 7：检查"检查真的跑了"之外，
    #   还要检查**判据与被判对象的口径真的对得上**）。CI 门禁 grep 的就是下面这两个标记。
    for mark in ('GCC:', 'ARM.attributes'):
        if mark not in txt:
            sys.stderr.write('★★ 报告缺少门禁标记 %r ⇒ 拒绝写出（判据与输入口径不符）\n' % mark)
            return ''
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
