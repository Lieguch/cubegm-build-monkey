#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mmio_width_audit —— 硬门禁：**直接访问设备寄存器的函数里，访存宽度必须与工厂一致**。

为什么必须存在（GAP 16.76，真机实证）：
  真机 `t1` 交付版在 `sfc_init` 读 SFC 寄存器时 `SIGBUS(si_addr=<mmap基址>+0x2C)`。
  与工厂逐条对照后，**唯一差异是这个读的宽度**：
      工厂 0x2c4464:  ldr  r3, [r2, #44]     （32 位读）
                      uxth r3, r3
      我们（旧）     : ldrh r1, [r0, #44]     （★ 16 位读 —— 编译器把 `x & 0xffff` 窄化出来的）
  源码写的是 `gh_u4 *p; p[0xb] & 0xffff`，GCC 只用到低半字 ⇒ 合法地把 32 位加载窄化成 `ldrh`。
  **对普通内存是优化；对设备寄存器是改硬件行为**（宽度是 MMIO 契约的一部分，且窄访问可能直接总线报错）。
  顺带它还**调换了顺序**：工厂是「先写 [base]=0 再读 [base+0x2C]」，我们成了「先读后写」。

判据：
  W1（硬）**直接操作设备寄存器的函数**（名单见 MMIO_DIRECT）：
      我们产物里的 narrow（half/byte 的 ld/st）计数 **不得多于** 工厂的计数。
      当前两个函数的工厂 narrow 计数均为 0 ⇒ 等价于"我们一个都不许有"。
  W2（提示，不判 FAIL）其余使用映射指针的派生函数（spi_*/sfc_request/…）列出宽度差异供人工核对
      —— 它们的缓冲访问是普通内存，窄化通常无害，**故意不判 FAIL**（避免"脆门禁烧掉整轮"那类事故）。

退出码：0 = PASS / 1 = 有 FAIL / 11 = 读不到输入（**绝不允许静默通过**）
"""
import collections
import io
import importlib.util
import json
import os
import struct
import sys
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from factory_data import load_factory_funcs  # noqa: E402  共享加载器：.json / .json.gz

ROOT = os.environ.get('CGM_ROOT') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('ad', os.path.join(ROOT, 'tools/arm_dis.py'))
ad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ad)

# ★ 直接对设备寄存器做访存的函数（必须与工厂逐条等价）
MMIO_DIRECT = ['sfc_init', 'sunxi_gpio_init']
# 仅提示
MMIO_INFO = ['spi_read', 'spi_write', 'sfc_request', 'InitScr',
             'sunxi_gpio_output', 'sunxi_gpio_set_cfgpin', 'sunxi_gpio_input',
             'sunxi_gpio_get_cfgpin', 'sunxi_gpio_cleanup', 'sfc_uninit', 'snor_wait_busy']

WIDTHS = (('ldrd', 'double'), ('strd', 'double'), ('ldrh', 'half'), ('strh', 'half'),
          ('ldrsb', 'half'), ('ldrsh', 'half'), ('ldrb', 'byte'), ('strb', 'byte'),
          ('ldr', 'word'), ('str', 'word'))
CONDS = ('', 'eq', 'ne', 'cs', 'hs', 'cc', 'lo', 'mi', 'pl', 'vs', 'vc', 'hi', 'ls',
         'ge', 'lt', 'gt', 'le', 'al')


def _classify_op(op):
    for pfx, wid in WIDTHS:
        if op.startswith(pfx) and op[len(pfx):] in CONDS:
            return ('ld' if pfx.startswith('ldr') else 'st') + ':' + wid
    return None


def fac_hist(key):
    # ★ 2026-09-23：改走共享加载器 —— 本地有 .json、**CI 只有 .json.gz**，
    #   只找 .json 会"本地绿、CI 红"（1to1-qemu-behav exit 15 就是这个原因）。
    F = load_factory_funcs()
    if key not in F:
        return None
    c = collections.Counter()
    for x in F[key]['t1']:
        if x.startswith('.word') or '@plt' in x:
            continue
        r = _classify_op(x.split(' ')[0])
        if r:
            c[r] += 1
    return c


def elf_syms(path):
    d = open(path, 'rb').read()
    es = struct.unpack_from('<H', d, 46)[0]; sh = struct.unpack_from('<I', d, 32)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
    out = {}
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]; ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            out[d[stro + nmn:k].decode('utf-8', 'replace')] = (val, sz)
    return d, out


def elf_text_words(d):
    ph = struct.unpack_from('<I', d, 28)[0]; pn = struct.unpack_from('<H', d, 44)[0]
    words = {}
    for i in range(pn):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, ph + i * 32)
        if t != 1 or not (fl & 4):
            continue
        for k in range(0, fsz - 3, 4):
            words[va + k] = struct.unpack_from('<I', d, off + k)[0]
    return words


def our_hist(path, name):
    d, syms = elf_syms(path)
    if name not in syms:
        return None
    v, sz = syms[name]
    words = elf_text_words(d)

    class E:
        pass
    e = E(); e.d = d
    c = collections.Counter()
    for k in range(0, sz, 4):
        w = words.get(v + k)
        if w is None:
            continue
        try:
            txt = ad.dec(w, v + k, e)[0]
        except Exception:
            continue
        r = _classify_op(txt.split(' ')[0])
        if r:
            c[r] += 1
    return c


def narrow(c):
    return sum(n for k, n in c.items() if k.endswith(':half') or k.endswith(':byte'))


def audit(path, verbose=True):
    fails, infos = [], []
    for fn in MMIO_DIRECT:
        fh = fac_hist(fn)
        if fh is None:
            infos.append(('W0', '工厂符号表里没有 %s ⇒ 跳过' % fn))
            continue
        oh = our_hist(path, fn)
        if oh is None:
            fails.append(('W1', '产物里找不到 %s —— 无法核对访存宽度（禁止静默通过）' % fn))
            continue
        fnar, onar = narrow(fh), narrow(oh)
        if onar > fnar:
            fails.append(('W1', '%s：我们引入了 %d 处窄访问（工厂 %d 处）——MMIO 宽度不是自由变量\n'
                                '      工厂=%s\n      我们=%s'
                          % (fn, onar, fnar, dict(fh), dict(oh))))
        else:
            infos.append(('W1', '%s：窄访问 我们=%d / 工厂=%d ✓  工厂=%s 我们=%s'
                          % (fn, onar, fnar, dict(fh), dict(oh))))
    # W2：只看提示
    for fn in MMIO_INFO:
        fh = fac_hist(fn)
        oh = our_hist(path, fn)
        if not fh or not oh:
            continue
        if dict(fh) != dict(oh):
            infos.append(('W2', '派生函数 %s 宽度分布不同（提示，非判据）：工厂=%s 我们=%s'
                          % (fn, dict(fh), dict(oh))))
    if verbose:
        for t, m in infos:
            print('  [%s] %s' % (t, m))
        for t, m in fails:
            print('  [%s] ★ FAIL —— %s' % (t, m))
        print('  ---- 判决：%s ----' % ('FAIL' if fails else 'PASS'))
    return fails


def selftest(good):
    print('=== mmio_width_audit 三态自证 ===')
    rc = 0
    f = audit(good, verbose=True)
    print('① 修复后产物：%s' % ('PASS' if not f else '★ FAIL'))
    if f:
        rc = 1
    print()
    pre = os.path.join(ROOT, 'build/_prewidth.rebuilt.elf')
    if os.path.exists(pre):
        f2 = audit(pre, verbose=False)
        tags = {t for t, _ in f2}
        ok = 'W1' in tags
        print('② 修复前产物（build/_prewidth.rebuilt.elf）：%s'
              % ('抓到窄访问 ✓' if ok else '★ 门禁未生效'))
        if not ok:
            rc = 1
        else:
            for t, m in f2[:1]:
                print('      %s' % m.split('\n')[0])
    else:
        print('② 缺 build/_prewidth.rebuilt.elf（修复前快照）⇒ ★ 应报错')
        return 1
    print()
    try:
        audit(os.path.join(ROOT, 'build/_no_such_width.elf'), verbose=False)
        print('③ 缺文件：未抛错 ★')
        rc = 1
    except Exception:
        print('③ 缺文件：抛错 ✓（main 转 exit 11）')
    print('  结果：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        return selftest(sys.argv[2])
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    try:
        f = audit(sys.argv[1])
    except Exception as e:
        print('  ★ 读不到输入：%s ⇒ 硬失败' % e)
        return 11
    return 1 if f else 0


if __name__ == '__main__':
    sys.exit(main())
