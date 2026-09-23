#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刻度 A（源码级）：对**工厂符号**的依赖普查。

为什么要在源码级而不是二进制级
--------------------------------
`tools/fidelity_audit.py` 的二进制口径（扫 `.text` 里落在 `.fimg_*` 区间的 4 字节值）
已被证明**不可用**（PROJECT-MEMORY §0.1「关于刻度 A 的一次公开更正」）：
  ① 把 `.text` 的 vaddr 当文件偏移用 → 读的位置就是错的；
  ② 「4 字节值落在大区间」会**大量误报**（任意常量恰好落在 2.9 MB 的 `.fimg_text` 区间）。
它报 10007，而真值口径是**源码里对工厂符号的引用数** = 175 个符号 / 2,548 处。

本工具的口径（与 PROJECT-MEMORY §0.1 刻度 A 一致）
--------------------------------------------------
* 符号集 = `src/data/factory_image.S` 里 `.set NAME, __f_<sec>_base + 0xoff` 定义的符号
  ⇒ 每个符号自带**所属段**（这正是"落在 `.fimg_text` 的仅 3 个符号"能算出来的原因）。
* 引用点 = `src/` 下源码文件里出现的该符号名。
* **排除**：`globals.h`（声明表，2897 个 `extern` —— 它是"目录"不是"依赖"）、
  `factory_image.S`（定义文件本身）、本工具的 `--self-test` 临时文件。
* 区分**代码口径**（去掉注释与字符串后的引用）与**原始口径**：前者是真实依赖，后者含注释。
  ★ 两者都报，并显式标注差异 —— 不把"注释里提了一次"算成依赖。

自证（`--self-test`，先自证再信数）
----------------------------------
* 正例：人造一行 `x = DAT_002dbd74;`      ⇒ 代码口径必须 = 1
* 反例：人造注释 `/* DAT_002dbd74 */`     ⇒ 代码口径必须 = 0，原始口径 = 1
* 反例：声明表 / 定义文件                ⇒ 贡献必须 = 0（排除规则生效）
* 反例：不在符号表里的假名 `DAT_deadbeef` ⇒ 必须 = 0（不误收）
"""
import os
import re
import sys
import struct
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_FILE = os.path.join(ROOT, 'src', 'data', 'factory_image.S')
DECL_FILE = os.path.join(ROOT, 'src', 'compat', 'globals.h')
ELF_FILE = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
SRC_ROOTS = [os.path.join(ROOT, 'src')]
SRC_EXT = ('.c', '.h', '.S', '.s', '.cpp', '.cc')

# `.set NAME, __f_<sec>_base + 0xoff`
RE_SET = re.compile(r'^\s*\.set\s+([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(__f_[A-Za-z0-9_]*_base)\s*\+\s*(0x[0-9a-fA-F]+|\d+)')
RE_SYM = re.compile(r'\b(?:DAT|UNK)_[0-9a-fA-F]{6,8}\b')


def parse_defined_from_asm():
    """从 factory_image.S 的 `.set` 取 {符号: 段名}（段名取 __f_XXX_base 的 XXX）。"""
    out = {}
    if not os.path.exists(DEF_FILE):
        return out
    with open(DEF_FILE, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = RE_SET.match(line)
            if not m:
                continue
            name, base, _off = m.groups()
            out[name] = '.fimg_' + base[len('__f_'):-len('_base')]
    return out


def parse_defined_from_elf(path=ELF_FILE):
    """★ 权威口径：从**链接产物**的符号表取落在 `.fimg_*` 段的符号 {名: 段}。

    为什么以产物为准：`.set` 只是"装配期别名"，可能漏（例如某个 UNK_ 定义在别的 .S 里）；
    而链接器只会把**真正落到 `.fimg_*` 段**的符号的 shndx 指过去 —— 这是事实。
    """
    out = {}
    if not os.path.exists(path):
        return out
    b = open(path, 'rb').read()
    e_shoff, = struct.unpack_from('<I', b, 0x20)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', b, 0x2e)
    sh = [struct.unpack_from('<10I', b, e_shoff + i * e_shentsize) for i in range(e_shnum)]
    st = sh[e_shstrndx]

    def snm(o):
        s = b[st[4] + o:]
        return s[:s.index(b'\x00')].decode('ascii', 'replace')

    names = [snm(s[0]) for s in sh]
    symtab = None
    strtab = None
    for i, n in enumerate(names):
        if n == '.symtab':
            symtab = sh[i]
        if n == '.strtab':
            strtab = sh[i]
    if symtab is None or strtab is None:
        return out
    stx = b[strtab[4]:strtab[4] + strtab[5]]
    for i in range(symtab[5] // 16):
        o = symtab[4] + i * 16
        no, va, sz, info, oth, shx = struct.unpack_from('<IIIBBH', b, o)
        if not no or shx == 0 or shx >= len(names):
            continue
        sec = names[shx]
        if not sec.startswith('.fimg'):
            continue
        nm = stx[no:stx.index(b'\x00', no)].decode('ascii', 'replace')
        if nm:
            out[nm] = sec
    return out


def parse_declared():
    """globals.h 声明表里的名字（只用于诊断，不参与刻度）。"""
    out = set()
    if not os.path.exists(DECL_FILE):
        return out
    with open(DECL_FILE, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            for m in RE_SYM.finditer(line):
                out.add(m.group(0))
    return out


def parse_defined():
    """兼容旧调用：优先 ELF（权威），缺失则回退 .set。"""
    e = parse_defined_from_elf()
    if e:
        return e
    return parse_defined_from_asm()


def strip_comments_and_strings(text):
    """粗粒度去掉 /*..*/、//..、'..'、".."，用于"代码口径"。

    ★ 故意保持简单可审计：只做状态机，不做全 C 语法分析。
    判据宁可**偏向保守**（少计），也不要把注释算成依赖。
    """
    out = []
    i, n = 0, len(text)
    state = 0  # 0=代码 1=块注释 2=行注释 3=字符串 4=字符
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ''
        if state == 0:
            if c == '/' and nxt == '*':
                state = 1; out.append('  '); i += 2; continue
            if c == '/' and nxt == '/':
                state = 2; out.append('  '); i += 2; continue
            if c == '"':
                state = 3; out.append(' '); i += 1; continue
            if c == "'":
                state = 4; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if state == 1:
            if c == '*' and nxt == '/':
                state = 0; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if state == 2:
            if c == '\n':
                state = 0; out.append('\n'); i += 1; continue
            out.append(' '); i += 1; continue
        if state == 3:
            if c == '\\':
                out.append('  '); i += 2; continue
            if c == '\n':
                state = 0; out.append('\n'); i += 1; continue
            if c == '"':
                state = 0; out.append(' '); i += 1; continue
            out.append(' '); i += 1; continue
        # state == 4（字符字面量）
        if c == '\\':
            out.append('  '); i += 2; continue
        if c == "'":
            state = 0; out.append(' '); i += 1; continue
        out.append(' '); i += 1
    return ''.join(out)


def iter_sources():
    for root in SRC_ROOTS:
        for dp, dn, fn in os.walk(root):
            for f in fn:
                if not f.endswith(SRC_EXT):
                    continue
                p = os.path.join(dp, f)
                if os.path.abspath(p) in (os.path.abspath(DEF_FILE),
                                          os.path.abspath(DECL_FILE)):
                    continue
                yield p


def census(verbose=True):
    defined = parse_defined()
    declared = parse_declared()
    per_sym_raw = {}
    per_sym_code = {}
    per_file_code = {}
    per_file_raw = {}
    orphan = {}          # 被引用但**不在**符号清单里（更严重：连定义都没有）
    for p in iter_sources():
        try:
            raw = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        code = strip_comments_and_strings(raw)
        hits_raw = [m.group(0) for m in RE_SYM.finditer(raw) if m.group(0) in defined]
        hits_code = [m.group(0) for m in RE_SYM.finditer(code) if m.group(0) in defined]
        if hits_raw:
            rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            per_file_raw[rel] = len(hits_raw)
            per_file_code[rel] = len(hits_code)
            for s in hits_raw:
                per_sym_raw[s] = per_sym_raw.get(s, 0) + 1
            for s in hits_code:
                per_sym_code[s] = per_sym_code.get(s, 0) + 1
        # 诊断：引用了、也在声明表里、却不在符号清单 ⇒ 说明了但没落地
        for m in RE_SYM.finditer(code):
            s = m.group(0)
            if s in defined:
                continue
            orphan[s] = orphan.get(s, 0) + 1
    return dict(defined=defined, declared=declared, raw=per_sym_raw, code=per_sym_code,
                file_raw=per_file_raw, file_code=per_file_code, orphan=orphan)


def report(c):
    defined = c['defined']
    declared = c['declared']
    elf_inv = parse_defined_from_elf()
    asm_inv = parse_defined_from_asm()
    print('=' * 100)
    print('刻度 A（源码级）—— 对工厂符号的依赖')
    print('=' * 100)
    print('  符号清单来源：%s' % ('链接产物 ELF 的 .fimg_* 段符号（权威）' if elf_inv
                                else 'factory_image.S 的 .set（回退）'))
    print('     ELF 清单 %4d 个   .set 清单 %4d 个   globals.h 声明 %4d 个'
          % (len(elf_inv), len(asm_inv), len(declared)))
    only_elf = sorted(set(elf_inv) - set(asm_inv))
    only_asm = sorted(set(asm_inv) - set(elf_inv))
    print('     ★ 只在 ELF 清单里（.set 漏掉）：%d 个 %s' % (len(only_elf), only_elf[:8]))
    print('     ★ 只在 .set 里（未落进产物）：%d 个 %s' % (len(only_asm), only_asm[:8]))
    print()
    by_sec = {}
    for s, sec in defined.items():
        by_sec[sec] = by_sec.get(sec, 0) + 1
    print('  --- 符号清单按段 ---')
    for sec, n in sorted(by_sec.items(), key=lambda kv: -kv[1]):
        print('        %-26s %4d 个定义' % (sec, n))
    print()
    print('  被引用的符号（原始口径 / 含注释）           : %4d 个 / %5d 处'
          % (len(c['raw']), sum(c['raw'].values())))
    print('  被引用的符号（★代码口径 / 去注释与字符串）  : %4d 个 / %5d 处'
          % (len(c['code']), sum(c['code'].values())))
    print('  ⇒ 收敛目标：两个口径都到 0')
    print()
    if c['orphan']:
        print('  ★ 诊断：被引用但**不在符号清单**里的名字（%d 个 / %d 处）—— 说明"声明了却没落地"'
              % (len(c['orphan']), sum(c['orphan'].values())))
        for s, n in sorted(c['orphan'].items(), key=lambda kv: -kv[1])[:10]:
            in_decl = '在 globals.h 声明' if s in declared else '连声明都没有'
            print('     %-16s %4d 处   （%s）' % (s, n, in_decl))
        print()
    # 按段统计（代码口径）
    sec_of = {}
    for s in c['code']:
        sec_of[c['defined'][s]] = sec_of.get(c['defined'][s], 0) + c['code'][s]
    print('  --- 代码口径：按符号所属段 ---')
    for sec, n in sorted(sec_of.items(), key=lambda kv: -kv[1]):
        nsym = len([s for s in c['code'] if c['defined'][s] == sec])
        print('     %-26s %4d 个符号 / %5d 处' % (sec, nsym, n))
    print()
    print('  --- 代码口径：Top 20 文件 ---')
    for f, n in sorted(c['file_code'].items(), key=lambda kv: -kv[1])[:20]:
        print('     %-58s %4d 处' % (f, n))
    print()
    print('  --- 代码口径：Top 20 符号 ---')
    for s, n in sorted(c['code'].items(), key=lambda kv: -kv[1])[:20]:
        print('     %-16s %-24s %4d 处' % (s, c['defined'][s], n))
    print()
    ft = [s for s in c['code'] if c['defined'][s] == '.fimg_text']
    print('  ★ 落在 .fimg_text（工厂**机器码**区）的符号：%d 个——这些是"是否执行工厂机器码"的判据' % len(ft))
    for s in sorted(ft, key=lambda x: -c['code'][x]):
        print('     %-16s %4d 处' % (s, c['code'][s]))
    return len(c['code']), sum(c['code'].values())


def self_test():
    print('=' * 100)
    print('自证：先用已知答案的样本验仪器，再看它的数')
    print('=' * 100)
    defined = parse_defined()
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-56s got=%-4s want=%-4s %s' % (tag, got, want, '✓' if good else '★ FAIL'))

    # 准备一个已知符号
    sample = 'DAT_002dbd74'
    if sample not in defined:
        sample = sorted(defined)[0]
    print('   选用样本符号 %s（属于 %s）' % (sample, defined[sample]))

    # ① 正例：代码里引用一次
    code1 = 'void f(void){ volatile char *p = %s; (void)p; }\n' % sample
    hits = [m.group(0) for m in RE_SYM.finditer(strip_comments_and_strings(code1))
            if m.group(0) in defined]
    chk('正例  代码中 1 次引用 → 代码口径', len(hits), 1)

    # ② 反例：只在注释里
    code2 = 'void f(void){ /* %s */ }\n' % sample
    chk('反例  仅块注释 → 代码口径', len([m.group(0) for m in RE_SYM.finditer(strip_comments_and_strings(code2)) if m.group(0) in defined]), 0)
    chk('反例  仅块注释 → 原始口径', len([m.group(0) for m in RE_SYM.finditer(code2) if m.group(0) in defined]), 1)

    # ③ 反例：只在字符串里
    code3 = 'void f(void){ printf("%s\\n"); }\n' % sample
    chk('反例  仅在字符串 → 代码口径', len([m.group(0) for m in RE_SYM.finditer(strip_comments_and_strings(code3)) if m.group(0) in defined]), 0)

    # ④ 反例：行注释
    code4 = 'int x; // %s\n' % sample
    chk('反例  仅行注释 → 代码口径', len([m.group(0) for m in RE_SYM.finditer(strip_comments_and_strings(code4)) if m.group(0) in defined]), 0)

    # ⑤ 反例：假名不入账
    code5 = 'void f(void){ char *p = DAT_deadbeef; }\n'
    chk('反例  不在符号表的假名 → 计数', len([m.group(0) for m in RE_SYM.finditer(code5) if m.group(0) in defined]), 0)

    # ⑥ 反例：排除规则（声明表与定义文件不参与）
    files = [os.path.relpath(p, ROOT).replace(os.sep, '/') for p in iter_sources()]
    chk('反例  globals.h 不在扫描集内',
        sum(1 for f in files if f.endswith('compat/globals.h')), 0)
    chk('反例  factory_image.S 不在扫描集内',
        sum(1 for f in files if f.endswith('data/factory_image.S')), 0)

    # ⑦ 正例：扫描集非空且有内容
    chk('正例  扫描文件数 > 100 时为真', len(files) > 100, True)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信，先修仪器'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true', help='先跑正反双向自证')
    ap.add_argument('--json', help='把结果写到 JSON（供其它工具消费）')
    a = ap.parse_args()
    if a.self_test:
        ok = self_test()
        print()
        if not ok:
            return 2
    c = census()
    nsym, nuse = report(c)
    if a.json:
        import json
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump({'nsym': nsym, 'nuse': nuse,
                       'code': c['code'], 'raw': c['raw'],
                       'file_code': c['file_code'], 'defined': c['defined']},
                      fh, ensure_ascii=False, indent=1, sort_keys=True)
        print('\n  （已写 %s）' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
