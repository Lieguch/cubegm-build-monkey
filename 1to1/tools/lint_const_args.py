#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""lint_const_args —— 硬门禁：抓「Ghidra 把**立即数**误反编译成**符号名**」这一类缺陷。

为什么必须存在（GAP 16.72，真机实证）：
  工厂 `InitSound` 的机器码是 `movw r1, #44100`（采样率），而 **44100 == 0xAC44**，
  **恰好等于**工厂里 `UpdateROM` 的函数地址 0x0000ac44 ⇒ Ghidra 把它反编译成 `UpdateROM`，
  我们的重建原样抄下。工厂布局下这个错误"碰巧无害"（两者数值相同），但我们的产物把
  `UpdateROM` 链接到别处 ⇒ 传给 `driver.so` 的采样率变成 ≈5,128,288 Hz ⇒ 真机
  `failed to apply hwparams: -22(EINVAL)` ⇒ 音频初始化失败（原厂同一处只是无害的 -32）。
  ★ 这类缺陷的判据只能是**机器码 vs 源码**对拍：静态等价性/符号尺寸全都看不出来。

判据（每条独立缺陷态，见 --selftest）：
  C1  对每个 `src/proprietary/**/FUN_<addr>_*.c`：若该工厂函数体内存在立即数 V，
      且 V 等于某个工厂符号名 N 的地址，而我们的源码里把 `N` 当**值**用了（不是调用、
      不是取址 `&N`、不是函数指针强转）⇒ FAIL（应为立即数 V）
  C2  反向自证：把已修好的 `InitSound.c` 还原成 `UpdateROM` 必须被抓到

退出码：0 = PASS / 1 = 有 FAIL / 11 = 读不到输入（**绝不允许静默通过**）
"""
import glob
import io
import json
import os
import re
import sys

ROOT = os.environ.get('CGM_ROOT', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_factory():
    p = os.path.join(ROOT, 'golden/factory.funcs.json')
    if os.path.exists(p):
        return json.load(io.open(p, encoding='utf-8'))['functions']
    gz = p + '.gz'
    if os.path.exists(gz):
        import gzip
        return json.loads(gzip.open(gz, 'rb').read().decode())['functions']
    raise IOError('读不到 golden/factory.funcs.json(.gz)')


def factory_symbols():
    """工厂符号名 → 地址（函数与数据都要；去 mangle）"""
    d = open(os.path.join(ROOT, 'golden/factory.rkgame.bin'), 'rb').read()
    import struct
    sh = struct.unpack_from('<I', d, 32)[0]; n = struct.unpack_from('<H', d, 48)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    S = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
    out = {}
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]; ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or shx == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            nm = d[stro + nmn:k].decode('utf-8', 'replace')
            m = re.match(r'^_Z\d+(\w+)$', nm)
            if m:
                nm = m.group(1)
            if re.match(r'^[A-Za-z_]\w{3,}$', nm):
                out.setdefault(nm, val)
    return out


def immediates(rows):
    """从 t1 指令序列里抽出「写入某寄存器的立即数」（含 movw/movt 32 位合成）。"""
    vals = set()
    pending = {}
    for x in rows:
        s = x.strip()
        m = re.match(r'^movw\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)$', s)
        if m:
            reg, v = m.group(1), int(m.group(2), 0) & 0xFFFF
            pending[reg] = v
            vals.add(v)
            continue
        m = re.match(r'^movt\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)$', s)
        if m:
            reg, v = m.group(1), int(m.group(2), 0) & 0xFFFF
            if reg in pending:
                vals.add((v << 16) | pending[reg])
            continue
        m = re.match(r'^mov\s+(r\d+),\s*#(0x[0-9a-fA-F]+|\d+)$', s)
        if m:
            vals.add(int(m.group(2), 0))
    return vals


def mask(src):
    """等长掩掉注释与字符串字面量（★ 必须等长 —— 否则行号/列号会漂移，
    这正是我第一次写这个 lint 时踩的坑：位置错位导致输出张冠李戴）。"""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        if src.startswith('/*', i):
            j = src.find('*/', i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != '\n':
                    out[k] = ' '
            i = j
        elif src.startswith('//', i):
            j = src.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ' '
            i = j
        elif src[i] == '"' or src[i] == "'":
            q = src[i]
            j = i + 1
            while j < n and src[j] != q:
                j += 2 if src[j] == '\\' else 1
            j = min(j + 1, n)
            for k in range(i + 1, j - 1):
                if out[k] != '\n':
                    out[k] = ' '
            i = j
        else:
            i += 1
    return ''.join(out)


def lint(verbose=True):
    F = load_factory()
    SYM = factory_symbols()
    addr2name = {}
    for nm, a in SYM.items():
        addr2name.setdefault(a, nm)

    srcs = sorted(glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True))
    fails = []
    checked = 0
    for p in srcs:
        base = os.path.basename(p)
        m = re.match(r'^FUN_([0-9a-fA-F]{8})_', base)
        if not m:
            continue
        facaddr = int(m.group(1), 16)
        t = None
        for k, v in F.items():
            a = v.get('addr')
            a = int(a, 16) if isinstance(a, str) else a
            if a == facaddr:
                t = v
                break
        if not t:
            continue
        checked += 1
        imms = immediates([x for x in t['t1'] if not x.startswith('.word')])
        src = io.open(p, encoding='utf-8', errors='replace').read()
        masked = mask(src)
        for v in imms:
            nm = addr2name.get(v)
            if not nm:
                continue
            for mm in re.finditer(r'(?<![\w.$])%s(?![\w$(])' % re.escape(nm), masked):
                st = mm.start()
                pre = masked[max(0, st - 16):st]
                if re.search(r'&\s*$', pre):                    # &Name = 合法取址
                    continue
                if re.search(r'\(\s*[\w_]+\s*\*\s*\)\s*$', pre):  # (gh_code *)Name = 回调
                    continue
                line = src[:st].count('\n') + 1
                linetxt = src.split('\n')[line - 1].strip()
                if re.match(r'^\s*(extern|static)\b', linetxt):
                    continue
                if 'pthread_create' in linetxt:
                    continue
                fails.append(('C1', '%s:%d  工厂 @0x%08x 处是**立即数 0x%x (%d)**，'
                                     '源码却写成符号 `%s`（该符号在工厂里正好位于 0x%x）\n'
                                     '        %s'
                              % (os.path.relpath(p, ROOT).replace('\\', '/'), line,
                                 facaddr, v, v, nm, v, linetxt[:110])))
    if verbose:
        print('  已对拍 %d 个重建函数（工厂机器码立即数 vs 源码符号用法）' % checked)
        for tag, msg in fails:
            print('  [%s] ★ FAIL —— %s' % (tag, msg))
        print('  ---- 判决：%s ----' % ('FAIL' if fails else 'PASS'))
    return fails


def selftest():
    print('=== lint_const_args 三态自证 ===')
    rc = 0
    # ① 正常态
    f = lint(verbose=True)
    print('① 正常态：%s' % ('PASS' if not f else '★ FAIL'))
    if f:
        rc = 1
    print()
    # ② 缺陷态：把 InitSound.c 临时改回 UpdateROM
    tgt = os.path.join(ROOT, 'src/proprietary/hw/FUN_0000db08_InitSound.c')
    if not os.path.exists(tgt):
        print('② 缺陷态：找不到 %s ⇒ ★ 应报错' % tgt)
        return 1
    orig = io.open(tgt, encoding='utf-8').read()
    try:
        io.open(tgt, 'w', encoding='utf-8', newline='\n').write(
            orig.replace('(*sound_driver_init)(USE_HDMI_OUT,44100,2);',
                         '(*sound_driver_init)(USE_HDMI_OUT,UpdateROM,2);'))
        f2 = lint(verbose=False)
        ok = any(t == 'C1' for t, _ in f2)
        print('② 缺陷态（把 44100 还原成 UpdateROM）：%s' % ('被抓到 ✓' if ok else '★ 门禁未生效'))
        if not ok:
            rc = 1
        else:
            for t, m in f2[:2]:
                print('      命中：%s' % m.split('\n')[0])
    finally:
        io.open(tgt, 'w', encoding='utf-8', newline='\n').write(orig)
    print()
    # ③ 缺文件 ⇒ 抛错（main 转 exit 11）
    #   ★ 注意 ROOT 是模块级常量（import 时定值），改 env 无效 —— 必须直接改模块全局，
    #     否则这条自证会静默"通过"（我第一次就写成改环境变量，结果门禁没响）。
    g = globals()
    old = g['ROOT']
    g['ROOT'] = os.path.join(old, '_no_such_dir_xyz')
    try:
        lint(verbose=False)
        print('③ 缺 golden ⇒ 未抛错 ★')
        rc = 1
    except Exception:
        print('③ 缺 golden ⇒ 抛错 ✓（main 转 exit 11）')
    finally:
        g['ROOT'] = old
    print('  结果：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--selftest':
        return selftest()
    try:
        f = lint(verbose=True)
    except Exception as e:
        print('  ★ 读不到输入：%s  ⇒ 硬失败（不允许静默通过）' % e)
        return 11
    return 1 if f else 0


if __name__ == '__main__':
    sys.exit(main())
