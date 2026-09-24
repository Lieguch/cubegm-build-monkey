#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_types.py — 生成物「类型可解析性」自检（**语句级**解析，非行级）。

目的：终止「改一处 -> 推一次 -> CI 报下一个错」的往返试错。
     在本地就把 src/compat 下三个 header 里出现的**类型 token** 校验一遍。

校验对象：src/compat/{ghidra_compat.h, globals.h, proto.h}
判定：`extern` / `typedef` 语句里出现在**声明符之前**的每个 token 必须属于
      ① gh_* 等自定义 typedef ② 标准 C 类型 ③ 已出现的 struct/union/enum 标签。

用法: python tools/check_types.py [--self-test]

────────────────────────────────────────────────────────────────────────────
修复史（两次，都是"判据的输入/口径在别处不成立"这一类）
────────────────────────────────────────────────────────────────────────────
① 2026-09-24（判据的**输入**不存在）：原先硬编码本机路径
   `D:/output/rkgame-1to1/src/compat`，而下面两个循环都是
   `if not os.path.exists(p): continue` ⇒ 在 CI 上三个文件**全不在** ⇒ 校验集合为空
   ⇒ 输出「未解析 0 个」⇒ 该步骤在 CI 里**看起来 PASS、其实一个文件都没查**
   （实测：CI run 35954789674 的"类型可解析性自检"步骤 success，扫了 0 个文件）。
   修法：路径从 `__file__` 推（仓内自洽，本地/CI 同解）+ **存在性硬失败 exit 2**。

② 2026-09-24（判据的**口径**不成立）：修好路径后本地立刻报出 23 个"未解析"。
   逐个回原文核对，**23 个全是行级解析器的伪影，零个真缺口**：
     · `typedef int gh_code();`        —— 函数指针型 typedef，`[\w\s\*]+?(\w+)\s*;` 匹配不到
                                         （名字后面跟的是 `()` 而不是 `;`）⇒ 该类型永远"未定义"
     · `proto.h:129`                   —— 原型**跨两行**（行尾是 `,`）⇒ `\([^)]*\)` 折叠不掉
                                         ⇒ 参数名 `font/codepoint/scale_x…` 被当成类型
     · `globals.h:4651`                —— 块注释**跨两行**（`/* …` 开在行尾、下一行才 `*/`）
                                         ⇒ 单行 `re.sub` 剥不掉 ⇒ 注释正文 `★ / GAP / ⇒` 被当成类型
     · `typedef union { gh_u4 _u32; …` —— union 体与 typedef 同行 ⇒ `{ } _u32 _0_1_` 被当成类型
     · `timezone`                      —— 文档声称支持"③ 已知 struct/union 标签"，**代码根本没实现**
   修法：改成**整文剥离注释 → 按 `;` 切语句 → 语句内自内向外折叠括号**的语句级解析，
   并把 ③ 真正实现（收集 `struct/union/enum` 标签加入 KNOWN）。

自证（--self-test）：构造性样本，正反双向
  正例：三个真实 header 全解析 ⇒ 0 未解析
  反例：合成 header 里放一个真·未定义类型 ⇒ 必须被检出
  反例：缺输入（目录不存在）⇒ 必须 exit 2，不得静默跳过
"""
import os
import re
import shutil
import sys
import tempfile

FILES = ['ghidra_compat.h', 'globals.h', 'proto.h']

STD = {
    'void', 'int', 'char', 'short', 'long', 'float', 'double', 'unsigned', 'signed',
    'size_t', 'ssize_t', 'const', 'volatile', 'struct', 'union', 'enum', 'void',
    'FILE', 'time_t', 'pthread_t', 'va_list', '__gnuc_va_list', 'bool', '_Bool',
    'int8_t', 'int16_t', 'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 'uint32_t',
    'uint64_t', 'intptr_t', 'uintptr_t', 'ptrdiff_t', 'wchar_t', 'mode_t', 'off_t',
    'sig_atomic_t', 'clock_t', 'DIR', 'struct_timeval', 'tm', 'tm_unz_s', 'unz_s',
    'unz_file_info_s', 'unz_file_info_internal_s', 'unz_global_info_s', 'ZIPENTRY',
    'ZIPENTRYW', 'HZIP__', 'inflate_huft_s', 'z_stream_s', 'inflate_blocks_state',
    'inflate_codes_state', 'pthread_attr_t', '__int32_t', '__timezone_ptr_t',
    'longlong', 'ulonglong', 'code', 'byte', 'uint', 'ulong', 'ushort', 'uchar',
    'undefined', 'undefined1', 'undefined2', 'undefined4', 'undefined8',
    # 变参/退出/属性等关键字与标记
    'restrict', 'inline', '__attribute__', '__asm__', '__inline__',
}


def strip_comments(t):
    """整文剥离注释（★ 必须整文：块注释可以跨行，单行 `re.sub` 会漏）。"""
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    t = re.sub(r'//[^\n]*', ' ', t)
    return t


def _fold_parens(x):
    """自内向外折叠所有括号组（参数表 / 函数指针 / 宏参数），直到不动点。"""
    prev = None
    while prev != x:
        prev = x
        x = re.sub(r'\([^()]*\)', ' ', x)
    return x


def core_tokens(stmt):
    """语句 → 去掉 `extern/typedef` 前缀、参数表、数组维度、指针星号后的 token 列表。"""
    x = re.sub(r'^\s*(?:extern|typedef)\b', ' ', stmt)
    x = _fold_parens(x)
    x = re.sub(r'\[[^\]]*\]', ' ', x)
    x = x.replace('*', ' ')
    x = re.sub(r'[,;{}()]', ' ', x)
    return x.split()


def decl_name(stmt):
    """取语句声明的名字。

    ★ 函数/函数指针形式的名字在**第一个 `(` 之前**；若先折叠括号再取末 token，
      `typedef void (*fp_t)(int);` 会被折叠成 `typedef void` ⇒ 名字错成 `void`。
    """
    body = re.sub(r'^\s*typedef\b', ' ', stmt)
    m = re.search(r'([A-Za-z_]\w*)\s*\(', body)
    if m:
        return m.group(1)
    toks = core_tokens(stmt)
    return toks[-1] if toks else None


def analyse(texts):
    """texts: [文件正文]。返回 (defined, tags, unresolved)。

    类型段识别：语句 token 里**第一个"不在 KNOWN 且前面已出现过 KNOWN 类型"的 token**
    就是声明符起点，其前为类型段。这样 `extern int a, b;` 的 `a`/`b` 不会被当类型，
    同时 `extern gh_code * p;` 的 `gh_code` 仍会被校验。
    """
    stmts = []
    for t in texts:
        for s in strip_comments(t).split(';'):
            s = re.sub(r'\s+', ' ', s).strip()
            if s.startswith(('extern', 'typedef')):
                stmts.append(s)

    defined, tags = set(), set()
    for s in stmts:
        tags.update(re.findall(r'\b(?:struct|union|enum)\s+([A-Za-z_]\w*)', s))
        if s.startswith('typedef'):
            n = decl_name(s)
            if n and re.match(r'^[A-Za-z_]\w*$', n):
                defined.add(n)
        m = re.search(r'\}\s*([A-Za-z_]\w*)\s*$', s)   # `} NAME`（union 体结束）
        if m:
            defined.add(m.group(1))

    known = STD | defined | tags
    unresolved = {}
    for s in stmts:
        if '{' in s or '}' in s:
            continue                     # struct/union 体片段由编译器负责，本启发式不碰
        toks = core_tokens(s)
        if not toks:
            continue
        end = len(toks)
        for i, tok in enumerate(toks):
            if tok not in known and not tok.isdigit() and any(t in known for t in toks[:i]):
                end = i                  # 第一个"跟在类型后面"的未知 token = 声明符
                break
        for tok in toks[:end]:
            if tok in known or tok.isdigit():
                continue
            unresolved.setdefault(tok, []).append(s[:90])
    return defined, tags, unresolved


def load(root):
    return [open(os.path.join(root, f), encoding='utf-8', errors='replace').read() for f in FILES]


def self_test():
    print('=' * 100)
    print('自证：用已知答案的样本验仪器')
    print('=' * 100)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-56s got=%-10s %s' % (tag, got, '✓' if good else '★ FAIL'))

    # 正例①：三个**真实** header 必须 0 未解析（这是本工具的"已知答案"）
    _d, _t, un = analyse(load(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'compat')))
    chk('正例 真实 3 个 header → 0 未解析', len(un), 0)
    if un:
        for k, v in sorted(un.items(), key=lambda x: -len(x[1]))[:10]:
            print('        %-24s x%-3d 例: %s' % (k, len(v), v[0][:70]))

    # 反例①：真·未定义类型必须被检出
    _d, _t, un2 = analyse(['extern volatile tUndefType * g_x;\n'])
    chk('反例 未定义类型 → 检出', sorted(un2), ['tUndefType'])

    # 反例②：函数指针型 typedef 必须先被登记，其使用不得误报
    _d3, _t3, un3 = analyse(['typedef int gh_code();\n/* @x u4 */ extern gh_code * p;\n'])
    chk('正例 函数指针 typedef 的使用 → 0 误报', len(un3), 0)

    # 反例③：跨行块注释的正文不得被当成类型
    _d4, _t4, un4 = analyse(['extern int a;   /* ★ 注释跨行 ⇒\n * 下一行才结束 ⇒ 这段不是类型 */\n'])
    chk('正例 跨行块注释 → 0 误报', len(un4), 0)

    # 反例④：跨行原型的参数名不得被当成类型
    _d5, _t5, un5 = analyse(['extern void f(void *font, int codepoint,\n                 float scale_x);\n'])
    chk('正例 跨行原型参数名 → 0 误报', len(un5), 0)

    # 反例⑤：多声明符 `extern int a, b;` 的 a/b 不得被当成类型
    _d6, _t6, un6 = analyse(['extern int a, b;\n'])
    chk('正例 多声明符 → 0 误报', len(un6), 0)

    # 反例⑥：union 体同行不得被当成类型
    _d7, _t7, un7 = analyse(['typedef union { gh_u4 u; struct { gh_u1 a, b; } f; } T;\n'
                             'extern T * g_t;\n'])
    chk('正例 union typedef 同行 → 0 误报', len(un7), 0)

    # 反例⑦：struct 标签必须被认可（文档判据 ③ 真正实现）
    _d8, _t8, un8 = analyse(['typedef struct timezone *__timezone_ptr_t;\n'])
    chk('正例 struct 标签 → 0 误报', len(un8), 0)

    # 反例⑧：缺输入必须 fail-closed（不得静默跳过）
    d = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(d, 'src'))
        rc = main_prepare(os.path.join(d, 'src', 'compat'))
        chk('反例 目录不存在 → exit 2（fail-closed）', rc, 2)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main_prepare(root):
    """校验对象存在性硬失败。缺任一文件 ⇒ 返回 2（跳过 ≠ 通过）。"""
    missing = [f for f in FILES if not os.path.exists(os.path.join(root, f))]
    if missing:
        sys.stderr.write(
            '★ 校验对象缺失 %s：%s\n  本自检**不做静默跳过**（跳过 = 假绿 ⇒ 看起来 PASS 其实没查）。\n'
            % (root, missing))
        return 2
    return 0


def main(argv):
    if '--self-test' in argv:
        return 0 if self_test() else 17
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'compat')
    rc = main_prepare(root)
    if rc:
        return rc
    defined, tags, unresolved = analyse(load(root))
    print('typedef 定义: %d 个 | struct/union/enum 标签: %d 个' % (len(defined), len(tags)))
    print('未解析类型 token: %d 个' % len(unresolved))
    for tok, where in sorted(unresolved.items(), key=lambda x: -len(x[1]))[:30]:
        print('  %-28s x%-4d  例: %s' % (tok, len(where), where[0][:70]))
    if unresolved:
        print()
        print('  ★ FAIL：存在既非 typedef、也非标准类型、也非已声明标签的 token。')
        print('     注意：若报出的是**参数名/注释文字/结构体成员名**，说明是解析器伪影（见文件头修复史 ②），')
        print('     应修解析器而**不是**往 KNOWN 里塞白名单 —— 白名单会让这道门禁失效。')
        return 1
    print('  PASS：全部类型 token 均可解析。')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
