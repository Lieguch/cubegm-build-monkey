#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fake_impl_audit.py —— 「假实现 / 假代码 / 假桩」专项 + `.dynsym` 差异（§0.19-F.3，长期未曾做）。

判据（全部机械、可复算）：
  A. **空壳函数**：我方 `st_size <= 4` 的函数 —— 逐个与**工厂同名函数**比大小；
     工厂也 ≤4 ⇒ 忠实（工厂本身就是空函数）；工厂明显更大 ⇒ **疑似缺体**。
  B. **恒返回常量**：正文形如 `mov(s) r0,#imm; bx lr`（Thumb/ARM 都认）——同样与工厂比。
  C. **桩符号**：`src/compat/*.c` 与 `build/stub/*` 提供的符号，在**产物**里必须是
     `SHN_UNDEF`（运行期由设备自己的 DSO 解析）；一旦被我们的桩满足 ⇒ **假桩进入了产物**。
  D. **源码级占位扫描**：`src/` 里 `TODO|FIXME|XXX|placeholder|stub|dummy|占位|未实现|未做`。
  E. **`.dynsym` 差异**：两侧动态符号表的**名字集合**逐条对拍（§0.19-F.3 点名的 28 项）。
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import diff_exec as D  # noqa: E402
import capstone  # noqa: E402

STUB_SYMS = ['compress', 'uncompress', 'compress2', 'uncompress2',
             '_Znwj', '_ZdlPv', '_Znaj', '_ZdaPv', 'malloc', 'free']


def read_v(b, addr, n):
    for va, fsz, _m, _f, off in b.segs:
        if va <= addr < va + fsz:
            return b.raw[off + (addr - va): off + (addr - va) + min(n, va + fsz - addr)]
    return b''


def disasm(b, name):
    a, sz = b.funcs[name]
    base = a & ~1
    code = read_v(b, base, sz or 8)
    for thumb in (bool(a & 1), not bool(a & 1)):
        md = capstone.Cs(capstone.CS_ARCH_ARM,
                         capstone.CS_MODE_THUMB if thumb else capstone.CS_MODE_ARM)
        out = list(md.disasm(code, base))
        bad = sum(1 for i in out if i.mnemonic.startswith('.') or i.mnemonic == 'invalid')
        if bad == 0 and out:
            return out
    return out


def is_const_ret(insns):
    """→ (是否恒返回常量, 常量值)。容忍 `movs/mov r0,#imm` (+ 可选 `bx lr`)。"""
    if not insns or len(insns) > 3:
        return False, None
    txt = ['%s %s' % (i.mnemonic, i.op_str) for i in insns]
    m = re.match(r'^movs? r0, #(\d+)$', txt[0])
    if not m:
        m = re.match(r'^movw r0, #(\d+)$', txt[0])
    if not m:
        return False, None
    if len(txt) > 1 and not txt[1].startswith('bx'):
        return False, None
    return True, int(m.group(1))


def dynsym(b):
    st = b.elf.get_section_by_name('.dynsym')
    out = {}
    if st is None:
        return out
    for s in st.iter_symbols():
        if s.name:
            out[s.name] = (s['st_info']['type'], s['st_info']['bind'],
                           s['st_shndx'], s['st_size'])
    return out


def main():
    BF, BO = D.Bin(D.FACTORY), D.Bin(D.OURS)
    print('工厂 %s\n我方 %s\n' % (D.FACTORY, D.OURS))

    print('=' * 96)
    print('A. 空壳函数（我方 st_size<=4）与工厂同名对比')
    print('=' * 96)
    n_ok = n_sus = 0
    for n, (a, sz) in sorted(BO.funcs.items(), key=lambda kv: kv[1][1]):
        if sz > 4:
            continue
        fs = BF.funcs.get(n)
        if fs is None:
            print('  ★ %-40s 我方 %dB ｜ 工厂**无此函数**' % (n, sz))
            n_sus += 1
        elif fs[1] <= 4:
            n_ok += 1
        else:
            print('  ★ %-40s 我方 %dB ｜ 工厂 **%dB** ⇒ 疑似缺体' % (n, sz, fs[1]))
            n_sus += 1
    print('  ⇒ 我方空壳 %d 个：其中**工厂同样是空壳** %d 个（忠实），**工厂更大** %d 个（嫌疑）'
          % (n_ok + n_sus, n_ok, n_sus))

    print()
    print('=' * 96)
    print('B. 恒返回常量（正文只有 mov r0,#imm [+ bx lr]）')
    print('=' * 96)
    n_ok = n_sus = 0
    for n in sorted(BO.funcs):
        if n not in BF.funcs:
            continue
        try:
            ins = disasm(BO, n)
        except Exception:
            continue
        ok, v = is_const_ret(ins)
        if not ok:
            continue
        try:
            fins = disasm(BF, n)
        except Exception:
            fins = []
        fok, fv = is_const_ret(fins)
        if fok and fv == v:
            n_ok += 1
        else:
            print('  ★ %-40s 我方 return %s ｜ 工厂 %s'
                  % (n, v, ('return %s' % fv) if fok else '%d 条指令' % len(fins)))
            n_sus += 1
    print('  ⇒ 恒返回常量：**两侧一致** %d 个（忠实）；**不一致** %d 个（嫌疑）' % (n_ok, n_sus))

    print()
    print('=' * 96)
    print('C. 桩符号在**产物**里的落位（必须 SHN_UNDEF，否则=假桩进产物）')
    print('=' * 96)
    ds_o, ds_f = dynsym(BO), dynsym(BF)
    bad = 0
    for s in STUB_SYMS:
        e = ds_o.get(s)
        if e is None:
            continue
        ty, bind, shndx, sz = e
        verdict = 'SHN_UNDEF（正确：运行期由设备 DSO 解析）' if shndx == 'SHN_UNDEF' else \
                  '★ 被我方定义（shndx=%s）⇒ 假桩进入产物' % shndx
        if shndx != 'SHN_UNDEF':
            bad += 1
        print('  %-12s %-12s %s' % (s, '工厂: ' + str(ds_f.get(s, ('-',))[2]), verdict))
    print('  ⇒ ★异常 %d 个' % bad)

    print()
    print('=' * 96)
    print('D. 源码级占位扫描（src/）')
    print('=' * 96)
    pat = re.compile(r'TODO|FIXME|XXX|placeholder|占位|未实现|未做|\bstub\b|\bdummy\b',
                     re.IGNORECASE)
    hits = []
    for root, _dirs, files in os.walk('src'):
        for f in files:
            if not f.endswith(('.c', '.h', '.S', '.s')):
                continue
            p = os.path.join(root, f)
            try:
                for i, ln in enumerate(open(p, encoding='utf-8', errors='replace'), 1):
                    if pat.search(ln):
                        hits.append((p, i, ln.strip()[:110]))
            except Exception:
                pass
    print('  命中 %d 处（前 30）：' % len(hits))
    for p, i, ln in hits[:30]:
        print('    %s:%d  %s' % (p, i, ln))

    print()
    print('=' * 96)
    print('E. `.dynsym` 名字集合对拍（§0.19-F.3）')
    print('=' * 96)
    fo, oo = set(ds_f), set(ds_o)
    print('  工厂 %d 项 ｜ 我方 %d 项 ｜ 共有 %d' % (len(fo), len(oo), len(fo & oo)))
    print('  --- 仅工厂有（我方缺）%d 项 ---' % len(fo - oo))
    for s in sorted(fo - oo):
        print('    ★ %-44s %s' % (s, ds_f[s][:3]))
    print('  --- 仅我方有（多余）%d 项 ---' % len(oo - fo))
    for s in sorted(oo - fo):
        print('      %-44s %s' % (s, ds_o[s][:3]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
