#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mmio_access_audit —— 「设备寄存器访存」类级检测器（取代旧的白名单式 W1）。

判据（单向、可判定）
--------------------
对**每一个**我们在工厂里有反汇编的函数，按 **立即数偏移** 建索引：
  · 只取基址不是 `sp` / `lr` 的访存（栈访问与设备无关）
  · 对同一偏移，比较两侧的 **访存宽度**
  · **判决：我们不得比工厂"更窄"** —— 窄于工厂 = 编译器把 32 位设备读窄化成了
    16/8 位（真机 SIGBUS 的确切成因：`ldrh r1,[r0,#44]` vs 工厂 `ldr r3,[r2,#44]`）
  · 更宽（如 `ldrd`）不算缺陷，只提示（多为编译器对成对变量的合并）

为什么"单向"就够
----------------
真机故障只发生在"比工厂更窄"这一侧（窄访问打到只接受 32 位的寄存器 ⇒ 总线错误）。
反向（更宽）不会产生非法访问。⇒ 判据窄而硬，避免制造假 FAIL（历史上"辅助判据太脆
烧掉整轮 CI"的教训，见 GAP 16.57）。

用法：
    python tools/mmio_access_audit.py <我们的产物> [工厂ELF]
    python tools/mmio_access_audit.py --selftest <我们的产物> [工厂ELF]
exit: 0=PASS / 2=发现"更窄" / 11=仪器不可用
"""
import gzip
import importlib.util
import io
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 立即数偏移形式的访存：ldr/str 家族 + [reg, #imm] / [reg, reg, lsl #n] 归为无立即数
MEM = re.compile(r'^(ldr|str)(b|h|sb|sh|d|t|bt)?\s+(r\d+|sp|lr|ip|fp|sl|pc)\s*,\s*'
                 r'\[(r\d+|sp|ip|fp|sl|pc)\s*(?:,\s*#(-?\d+))?')
WIDTH = {'': 4, 'b': 1, 'h': 2, 'sb': 1, 'sh': 2, 'd': 8, 't': 4, 'bt': 1}


def load_factory_functions(path):
    if os.path.exists(path):
        return json.load(io.open(path, encoding='utf-8'))['functions']
    if os.path.exists(path + '.gz'):
        return json.loads(gzip.open(path + '.gz', 'rb').read().decode())['functions']
    raise IOError('找不到工厂反汇编数据: %s' % path)


def parse_mem(text):
    """从反汇编文本行提取 (偏移, 宽度)；无立即数或基址为栈则返回 None。"""
    m = MEM.match(text.strip())
    if not m:
        return None
    mnem, suf, _rd, base, imm = m.group(1), m.group(2) or '', m.group(3), m.group(4), m.group(5)
    if base in ('sp', 'lr') or imm is None:
        return None
    return (int(imm), WIDTH.get(suf, 4), mnem + suf)


def factory_index(funcs):
    """{函数名: {偏移: {宽度: 次数}}}"""
    idx = {}
    for nm, t in funcs.items():
        d = {}
        for x in t.get('t1', []):
            if x.startswith('.word'):
                continue
            p = parse_mem(x)
            if not p:
                continue
            off, w, _mn = p
            d.setdefault(off, {}).setdefault(w, 0)
            d[off][w] += 1
        if d:
            idx[nm] = d
    return idx


def ours_index(path):
    """反汇编我们的产物，返回 {函数名: {偏移: {宽度: 次数}}}"""
    spec = importlib.util.spec_from_file_location(
        'ad', os.path.join(ROOT, 'tools', 'arm_dis.py'))
    ad = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ad)

    d = open(path, 'rb').read()
    sh = struct.unpack_from('<I', d, 32)[0]
    sn = struct.unpack_from('<H', d, 48)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    SH = [struct.unpack_from('<10I', d, sh + i * es) for i in range(sn)]
    syms = {}
    for s in SH:
        if s[1] != 2:
            continue
        stro = SH[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            syms.setdefault(d[stro + nmn:k].decode('utf-8', 'replace'), (val, sz))
    segs = []
    ph = struct.unpack_from('<I', d, 28)[0]
    pn = struct.unpack_from('<H', d, 44)[0]
    for i in range(pn):
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, ph + i * 32)
        if t == 1 and fsz:
            segs.append((va, va + fsz, off))

    def foff(a):
        for lo, hi, o in segs:
            if lo <= a < hi:
                return o + (a - lo)
        return None

    class E:
        pass
    e = E()
    e.d = d
    idx = {}
    for nm, (v, sz) in syms.items():
        if not sz or sz > 60000:
            continue
        o = foff(v)
        if o is None:
            continue
        d2 = {}
        for k in range(0, sz, 4):
            if o + k + 4 > len(d):
                break
            w = struct.unpack_from('<I', d, o + k)[0]
            try:
                txt = ad.dec(w, v + k, e)[0]
            except Exception:
                continue
            if not txt:
                continue
            p = parse_mem(txt)
            if not p:
                continue
            off, ww, _mn = p
            d2.setdefault(off, {}).setdefault(ww, 0)
            d2[off][ww] += 1
        if d2:
            idx[nm] = d2
    return idx


def audit(ours, fac, verbose=True, scope=None):
    """scope=None ⇒ 不做硬判（只报告）。硬判只对 scope 内的函数生效。

    理由（GAP 16.57 的教训）："偏移 + 宽度"在**非设备内存**上无意义 ——
    结构体字段普遍是窄类型（`stbtt_*` / `xmp3_*` 有 19 处这种噪声）。
    若不做范围收敛，判据会造出十几个假 FAIL，比它防的风险更贵。
    """
    fails = []
    noise = 0
    checked_fn = 0
    checked_off = 0
    for nm, fo in fac.items():
        oo = ours.get(nm)
        if not oo:
            continue
        checked_fn += 1
        inscope = (scope is None) or any(
            nm == s or nm.endswith('_' + s) or s in nm for s in scope)
        for off, fw in fo.items():
            if off not in oo:
                continue
            checked_off += 1
            fmin = min(fw)
            omin = min(oo[off])
            if omin < fmin:
                if inscope:
                    fails.append((nm, off, fmin, omin,
                                  sorted(w for w in fw), sorted(w for w in oo[off])))
                else:
                    noise += 1
    if verbose:
        print('  比对函数 %d 个 / 共同偏移 %d 个' % (checked_fn, checked_off))
        if scope is not None:
            print('  设备访问函数集（机械推导）%d 个：%s' % (len(scope), ', '.join(sorted(scope)[:14])))
        if fails:
            print('  ★（范围内）发现 %d 处「我们比工厂更窄」的访存：' % len(fails))
            for nm, off, fmin, omin, fws, ows in fails[:24]:
                print('     %-42s +%-6d 工厂宽度%s(最窄%d)  我们宽度%s(最窄%d)'
                      % (nm[:42], off, fws, fmin, ows, omin))
        else:
            print('  ✓（范围内）全部共同偏移上，我们的访存宽度均 **不窄于** 工厂')
        if noise:
            print('  · 范围外的同类偏差 %d 处（结构体窄字段等噪声，仅登记不判决）' % noise)
    return fails


def device_function_set():
    """**机械推导**设备访问函数集（不是手写白名单）。

    步骤（全部来自源码，可复核）：
      ① 找 `X = mmap(..., 0x1xxxxxxx|0x2xxxxxxx)` ⇒ 得到"设备寄存器全局"G 与所属文件 F0
      ② 找所有引用 G 的 .c 文件 ⇒ F1（BFS 到不动点）
      ③ 文件 → 函数名（文件名 `FUN_xxxx_name.c` / `name.c` ⇒ `name`）
      ④ 再并上"反汇编里出现外设物理地址常量"的函数（本地信号，兜住没走全局的那类）
    """
    import glob
    prop = os.path.join(ROOT, 'src', 'proprietary')
    files = sorted(glob.glob(os.path.join(prop, '**', '*.c'), recursive=True))
    PERIPH = re.compile(r'0x1[0-9a-fA-F]{7}|0x2[0-9a-fA-F]{7}')
    MMAP_ASSIGN = re.compile(r'([A-Za-z_]\w*)\s*=\s*mmap\s*\([^;]*?(0x1[0-9a-fA-F]{7}|0x2[0-9a-fA-F]{7})')

    def fname(p):
        b = os.path.basename(p)[:-2]
        return b.split('_', 2)[-1] if b.startswith('FUN_') else b

    globals_dev = set()
    fset = set()
    txt = {}
    for p in files:
        t = io.open(p, encoding='utf-8', errors='replace').read()
        txt[p] = t
        hit = False
        for m in MMAP_ASSIGN.finditer(t):
            globals_dev.add(m.group(1))
            hit = True
        if hit or PERIPH.search(t):
            fset.add(fname(p))
    # ② BFS：引用设备全局的文件
    changed = True
    while changed:
        changed = False
        for p, t in txt.items():
            nm = fname(p)
            if nm in fset:
                continue
            for g in globals_dev:
                if re.search(r'\b%s\b' % re.escape(g), t):
                    fset.add(nm)
                    changed = True
                    break
    return fset, globals_dev


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('  用法: mmio_access_audit.py <我们的产物> [工厂ELF]')
        return 11
    ours_p = args[0]
    if not os.path.exists(ours_p):
        print('  ★ 读不到产物 %s —— 仪器不可用，硬失败（不允许"跳过即通过"）' % ours_p)
        return 11
    facjson = os.path.join(ROOT, 'golden', 'factory.funcs.json')
    try:
        fac = factory_index(load_factory_functions(facjson))
    except Exception as e:
        print('  ★ 读不到工厂反汇编数据：%s —— 硬失败' % e)
        return 11
    try:
        ours = ours_index(ours_p)
    except Exception as e:
        print('  ★ 反汇编失败：%s —— 硬失败' % e)
        return 11
    print('  [产物] %s' % ours_p)
    try:
        scope, gnames = device_function_set()
    except Exception as e:
        print('  ★ 无法机械推导设备函数集：%s —— 硬失败（不允许退化成"全函数硬判"）' % e)
        return 11
    print('  [设备全局] %s' % (', '.join(sorted(gnames)) or '(无)'))
    fails = audit(ours, fac, scope=scope)

    if '--selftest' in sys.argv:
        print()
        print('  ---- 自证 ①：喂"修复前"的产物（它确实含 ldrh）⇒ 必须报出 FAIL ----')
        pre = os.path.join(ROOT, 'build', '_prewidth.rebuilt.elf')
        if not os.path.exists(pre):
            print('  [!!] 缺 %s ⇒ 无法做缺陷态自证（这是仪器缺口，算 FAIL）' % pre)
            return 11
        pf = audit(ours_index(pre), fac, verbose=False, scope=scope)
        if pf:
            print('  ✓ 自证通过：修复前产物被报出 %d 处"更窄"' % len(pf))
            print('     例：%s' % (' / '.join('%s+%d 工厂%s→我们%s' % (x[0][:22], x[1], x[4], x[5])
                                              for x in pf[:2])))
        else:
            print('  [!!] 自证失败：修复前产物竟未报错 ⇒ 判据不成立')
            return 11
        print()
        print('  ---- 自证 ②：同一份数据自比 ⇒ 不得报差异（查假阳性）----')
        same = audit(fac, fac, verbose=False, scope=None)
        if same:
            print('  [!!] 自证失败：自比竟报差异 ⇒ 判据有假阳性')
            return 11
        print('  ✓ 自证通过：自比零差异（无假阳性）')

    print()
    if fails:
        print('  ---- 判决：FAIL（%d 处窄于工厂）----' % len(fails))
        return 2
    print('  ---- 判决：PASS ----')
    return 0


if __name__ == '__main__':
    sys.exit(main())
