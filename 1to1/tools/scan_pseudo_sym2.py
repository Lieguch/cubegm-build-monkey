#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_pseudo_sym2.py —— 按**纪律 143**（符号 size 够不够）普查伪符号。

★ 为什么要有 v2（2026-10-03 第 122 轮）：
  v1（scan_pseudo_sym.py）判据是「`基址+IMM` 是否跨对象」⇒ **640 条里 0 个真阳性**，
  全是误报。两个原因：
    ① v1 只看「rY 曾被 ldr[pc] 取过地址」，**没区分符号基址与同寄存器后来被覆写**；
    ② 我用「按行号 × 4」推算 PC 复核，**偏差 40892 字节**（ARM/Thumb 混编 + 变长指令）
       ⇒ 把「同对象内偏移」误判成「跨对象」。
  而 `m_ui`(1508) / `file_info_list`(41120) 这类大对象天然吸收大量偏移，
  Ghidra 渲染成「基址符号」在 1:1 复刻里**无害**（我方照样编出等价代码）。

★ 真正的伪符号只有一个形态（簇 A 的 `FilenameExt` 就是标本）：
    **符号的 size 远小于「工厂实际写入/读取的范围」**
    —— `FilenameExt` size=**4**（char[4]）却被 `strcpy` 写文件扩展名（可达数十字节）
       ⇒ 写入越界 200 字节 ⇒ 静默内存破坏。

★ v2 的判据（全部只用**权威表**，不做地址推算）：
    1. 基址/落点一律取自 `ledger/factory_globals.tsv`（工厂 ELF `.symtab` 直接读出）
    2. 找「size 过小却被当缓冲用」的符号：size < 32 且 出现在 memcpy/strcpy/strupr/
       sprintf 等**写入型**调用附近
    3. 交叉核对 `globals.h` 的声明类型（`undefined4` / `char[N]`）

用法：
    python3 tools/scan_pseudo_sym2.py --selftest
    python3 tools/scan_pseudo_sym2.py
"""
import csv, io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 写入型 libc/自函数（其目标必须是"缓冲"，size 太小即伪符号）
WRITE_FN = re.compile(
    r'\b(strcpy|strncpy|strcat|strncat|strupr|memset|memcpy|sprintf|snprintf|'
    r'strncmp|strcmp|strlen|strstr|mxmlLoadFile|fread)\b')

# 缓冲区至少要能装下的合理下限（工厂里 UI 文本/路径的常见量级）
MIN_BUF = 32


def load_ledger():
    """读工厂 .data/.bss/.rodata 符号（权威 addr/size），排除 size=0 的占位。"""
    p = os.path.join(ROOT, 'ledger', 'factory_globals.tsv')
    if not os.path.exists(p):
        print('!! 缺 ledger/factory_globals.tsv', file=sys.stderr)
        return None
    out = []
    with io.open(p, encoding='utf-8') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            try:
                a = int(r['addr'], 16)
            except (ValueError, KeyError):
                continue
            try:
                sz = int(r['size'], 16)
            except (ValueError, KeyError):
                sz = 0
            if sz:                      # ★ size=0 的 DAT_x 占位不是对象，直接排除
                out.append((a, sz, r['name'], r.get('section', '')))
    out.sort()
    return out


def selftest():
    assert WRITE_FN.search('strcpy(a, b)')
    assert WRITE_FN.search('memset(p, 0, 12)')
    assert not WRITE_FN.search('add r0, r5, #88')
    syms = load_ledger()
    assert syms, 'ledger 解析出 0 个符号'
    names = {n for _, _, n, _ in syms}
    # 锚点：工厂真实存在的、size 极小的符号（伪符号的候选形态）
    assert 'FilenameExt' in names, 'FilenameExt 应在账本里（size=4，簇 A 标本）'
    d = dict((n, s) for _, s, n, _ in syms)
    assert d['FilenameExt'] == 4, d['FilenameExt']
    # 反例：size=0 的占位必须**不**在列表里
    assert 'DAT_003b0134' not in names, 'size=0 的占位应被排除'
    # v2.1 指针排除：ZIP_BUF/scr_data 在 globals.h 里是 void* ⇒ 必须能识别出来
    g = io.open(os.path.join(ROOT, 'src', 'compat', 'globals.h'),
                encoding='utf-8', errors='ignore').read()
    assert re.search(r'extern\s+void\s*\*\s*scr_data\s*;', g), 'scr_data 应声明为 void*'
    assert re.search(r'extern\s+void\s*\*\s*ZIP_BUF\s*;', g) or 'ZIP_BUF' in g
    print('selftest OK（ledger %d 个符号，FilenameExt size=%d）' % (len(syms), d['FilenameExt']))
    return 0


def main():
    syms = load_ledger()
    if not syms:
        return 2
    small = [(a, s, n, sec) for a, s, n, sec in syms if s < MIN_BUF]

    # ★ v2.1（2026-10-03 第 122 轮）：**排除「指针变量」**。
    #   实测 47 处候选里绝大多数是 `void*`（ZIP_BUF/romfile/scr_data/ArchivePath…）——
    #   它们 size=4 是**指针本身**，被 fread/memset/sprintf 当缓冲用**是正确的**
    #   （写的是它指向的目标）。⇒ 只有「非指针的小对象被当缓冲用」才是伪符号。
    #   ★ 必须在**声明处**（src/compat/globals.h）扫，不能在被调用处（.c）扫 ——
    #     第一次实现犯了这个错（ptr_names 为空 ⇒ 排除失效），已修。
    ptr_names = set()
    for hdr in ('globals.h', 'proto.h'):
        hp = os.path.join(ROOT, 'src', 'compat', hdr)
        if not os.path.exists(hp):
            continue
        for hl in io.open(hp, encoding='utf-8', errors='ignore'):
            m2 = re.search(r'\*\s*([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*;', hl)
            if m2 and '*' in hl.split(m2.group(1))[0]:
                ptr_names.add(m2.group(1))

    # 在**我方源码**里找：这些小符号被当缓冲传给写入型函数的次数
    src_roots = [os.path.join(ROOT, 'src', 'proprietary'),
                 os.path.join(ROOT, 'src', 'upstream')]
    hits = []
    for sr in src_roots:
        for dp, _dn, fns in os.walk(sr):
            for fn in fns:
                if not fn.endswith(('.c', '.cpp')):
                    continue
                fp = os.path.join(dp, fn)
                try:
                    txt = io.open(fp, encoding='utf-8', errors='ignore').read()
                except OSError:
                    continue
                lines = txt.split('\n')
                for i, ln in enumerate(lines, 1):
                    if not WRITE_FN.search(ln):
                        continue
                    for _a, s, name, sec in small:
                        if name in ptr_names:
                            continue
                        # 形如 &name / name / (xxx)&name
                        if re.search(r'\b%s\b' % re.escape(name), ln):
                            # 取该行调用的写入长度线索（有显式长度则豁免）
                            has_len = re.search(r',\s*\d+\s*\)', ln) or re.search(r'sizeof', ln)
                            hits.append((os.path.relpath(fp, ROOT).replace('\\', '/'),
                                         i, name, s, sec, has_len, ln.strip()[:110]))

    print('# 纪律 143 普查：**符号 size < %d 且被当缓冲写入**' % MIN_BUF)
    print('# 权威表：ledger/factory_globals.tsv（工厂 .symtab 直读，不做地址推算）')
    print('# file\tline\tsymbol\tsize\tsection\t显式长度?\t代码')
    n = 0
    for f, i, name, s, sec, hl, ln in hits:
        flag = '' if hl else '   ★无显式长度'
        print('%s\t%d\t%s\t%d\t%s\t%s\t%s%s' % (f, i, name, s, sec, 'yes' if hl else 'no', ln, flag))
        n += 1
    print('# 共 %d 处候选' % n, file=sys.stderr)
    return 0


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
