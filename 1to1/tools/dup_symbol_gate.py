#!/usr/bin/env python3
"""
dup_symbol_gate.py — 「重复实现」门禁：同名全局函数在多个 TU 各自定义即失败。

═══ 为什么要有这个门禁（第 144 轮血泪引入）════════════════════════════════════

本项目对原厂 rkgame 做 1:1 复刻，工厂二进制里 `ClearBuffer` **只有一个**
GLOBAL 符号（`002bdefc`，32B）。而我方代码库里它有**两份独立实现**：

    src/proprietary/misc/FUN_002bdefc_ClearBuffer.c   ← Ghidra 1:1 复刻版
    src/upstream/mp3/real/buffers.c                   ← 上游版，原为 static

两份靠 `static` 回避了链接冲突，**表面能过**，但代价是：

  ① 两份实现的 codegen 各走各的 —— 上游那份被 clang 识别成 memset 尾调用，
     复刻那份被内联掉，两边**都不是**工厂的 32B 逐字节 strb 循环；
  ② 改了一处另一处不会跟着变 ⇒ 「同一规则写两处」，是长期发散源；
  ③ batch 判据把 `xmp3_AllocateBuffers` / `MP3InitDecoder` 打成 DIVERGE，
     根因却完全不在这两个函数上（真正的差异是"调自己的 ClearBuffer"还是"调 memset"）。

修法是**删掉重复实现、复用唯一真源**（上游改 `extern` 声明），
DIVERGE 17 → 16、`xmp3_AllocateBuffers` 的 8 个 `bl` 全部指回 `ClearBuffer`。
**但那一次是人工发现的** —— 所以把它固化成门禁。

═══ 判据（两侧双向，故障闭合）═════════════════════════════════════════════

  源侧：扫 `src/**/*.c` 的**非 static 全局函数定义**（含 C++ mangled 名），
        按符号名聚合；同一名字出现在 **≥2 个文件** ⇒ 报 FAIL。
        —— 覆盖面最广，能抓出比工厂多出来的重复。

  产物侧：比对我方 `build/rkgame.rebuilt.elf` 与工厂 `golden/factory.rkgame.bin`
        的**已定义 FUNC 符号集合**；凡是「工厂有定义、我方却没有」的符号
        单独列出（提示：可能被 static 化 / 被内联掉 / 漏复刻）。
        —— 这是"漏实现"方向，与源侧"多实现"互补，两者合起来方向完整。

排除名单（**必须显式列出，不许静默跳过**）：
  * `main` / `_start` / `__libc_csu_*` 等 CRT 入口 —— 本就不止一个 TU 涉及。
  * C++ 的 Itanium 特殊定义（`operator new/delete`、`_Z*Thn*_ZTV*` 等 vtable/thunk），
    它们**天然同名多份**，不是缺陷。

用法:
  dup_symbol_gate.py [--factory golden/factory.rkgame.bin]
                     [--ours build/rkgame.rebuilt.elf] [--json]
退出: 0 = 全通过 / 2 = 有失败

═══ 判据必须绑定真实构建口径（v1 踩坑后修正）════════════════════════════════

v1 直接扫整个 `src/`，结果**误报 31 个**：
  * `src/upstream/libiconv-legacy-stub/**` —— 历史遗留，**从不参与构建**
    （`build_upstream.sh:217` 只编 `libiconv17`）；
  * `src/upstream/libiconv17/genaliases*.c` / `genflags.c` / `gentranslit.c`
    —— GNU **源码生成器**，不在任何组件的编译循环里；
  * `src/probe/probe*.c` —— 独立探针工程；
  * `src/diag/**` —— 诊断仪（走 `DIAG_EXTRA`，是**另一个**可执行文件，不是 rkgame）；
  * 还把 `int` / `and` / `or` / `__typeof` / `__asm__` 当成了函数名。

⇒ 教训与 `abi_check.py` 里那条"不许再用全文件子串搜索"同源：
**判据口径必须与构建脚本同源，不能自己另立一套"看起来像"的扫描范围**。
现在 `BUILD_DIRS` 直接对应构建脚本里的真实目录，**改动时必须同步改构建脚本那边**。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ 参与 rkgame 链接的源目录（与 link_audit.sh:19 / build_upstream.sh 各组件循环同源）
BUILD_DIRS = [
    'src/proprietary',        # link_audit.sh:19  SRCDIR → build/obj/*.o
    'src/upstream/mxml',      # build_upstream.sh:179
    'src/upstream/mp3',       # build_upstream.sh:195
    'src/upstream/libiconv17',  # build_upstream.sh:217（**不是** libiconv-legacy-stub）
    'src/upstream/stb',       # stb truetype
    'src/upstream/xunzip',    # C++，link_audit.sh:149
]
# 生成器 / 探针：不参与编译，显式列出以免"静默跳过"（纪律：排除必须有名有据）
SUBTREE_SKIP = {
    'src/upstream/libiconv-legacy-stub': '历史遗留，从不参与构建（build_upstream.sh 只编 libiconv17）',
    'src/probe': '独立探针工程，不是 rkgame 的一部分',
    'src/diag': '板上诊断仪（另一个可执行文件，走 DIAG_EXTRA）',
    'src/tools': '构建期工具',
}
SKIP_FILE_RE = re.compile(r'^(genaliases|genflags|gentranslit)\.c$')

# ── 显式排除名单（每条都要写清理由；静默跳过是本门禁最要避免的失败模式）────────
EXCLUDE = {
    'main': '程序入口，唯一',
    '_start': 'CRT 入口，唯一',
    '__libc_csu_init': 'GCC CRT 兼容层',
    '__libc_csu_fini': 'GCC CRT 兼容层',
}
EXCLUDE_PREFIX = (
    '_ZTV', '_ZTI', '_ZTS', '_ZThn', '_ZTv',       # C++ vtable / typeinfo / thunk
    '_ZdlPv', '_ZdaPv', '_Znam', '_ZSt3',          # operator delete/new / containers
)
# ★ C/C++ 关键字与编译器内建：绝不能被当成函数名（v1 误抓 int/and/or/__typeof/__asm__）
KEYWORDS = {
    'int', 'char', 'short', 'long', 'float', 'double', 'void', 'signed', 'unsigned',
    'const', 'volatile', 'struct', 'union', 'enum', 'typedef', 'static', 'extern',
    'inline', 'return', 'if', 'else', 'for', 'while', 'do', 'switch', 'case',
    'default', 'break', 'continue', 'goto', 'sizeof', 'and', 'or', 'not', 'xor',
    '__typeof', '__typeof__', '__asm__', '__attribute__', '__extension__',
    '__inline', '__inline__', '__restrict', '__const', '__volatile__',
    'operator', 'template', 'typename', 'class', 'public', 'private', 'protected',
}


def is_excluded(name):
    return (name in EXCLUDE or name.startswith(EXCLUDE_PREFIX)
            or name in KEYWORDS)


# ── 源侧：扫非 static 全局函数定义（**只扫参与构建的目录**）──────────────────
# 形如 `type name(...)` 出现在行首（前面没有 static 修饰）
DEF_RE = re.compile(
    r'^(?P<full>[A-Za-z_][A-Za-z0-9_ \t\*&:<>,]*?\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*)\(',
    re.M)
STATIC_RE = re.compile(r'\bstatic\b')


def _in_skipped_subtree(rel):
    for sub, _why in SUBTREE_SKIP.items():
        if rel == sub or rel.startswith(sub + '/'):
            return sub
    return None


def _arglist(s):
    """取配平括号内的参数表，**归一为「类型序列」**（去参数名、去空白）。

    ★ 为什么要归一（第 144 轮自证实测 —— 这是判别力的关键）：
      同一个函数在两处的**参数名可以完全不同**，例如
        复刻版：`void ClearBuffer(gh_u1 *param_1, int param_2)`
        上游版：`void ClearBuffer(void *buf, int nBytes)`
      若把参数名算进键，两者会被判成"不同函数" ⇒ **门禁对真重复完全失明**
      （实测：注入上游那份重复定义后，退出码仍是 0 = 没抓到）。
      ⇒ 只保留**类型**：`gh_u1 *` 与 `void *` 归一为 `P`，
        `int param_2` 与 `int nBytes` 归一为 `i`。

    ★ 为什么要带类型（第 144 轮自证实测）：
      `CloseZipU(gh_u4*)` 与 `CloseZipU(HZIP,int,DWORD,const char*)`
      是**不同**的重载（工厂侧 `readelf` 实测定义数 = 1），
      只按名字聚合会误判成"重复实现"。

    归一规则（唯一真源，别处只许调用本函数）：
      1. 去参数名：每个参数只保留**最后一个**类型词（指针/引用前缀保留）；
      2. 指针/引用/数组后缀折叠成 `P` / `R`；
      3. 空白全部压成单空格。
    """
    i = s.find('(')
    if i < 0:
        return '()'
    depth = 0
    end = -1
    for j in range(i, len(s)):
        if s[j] == '(':
            depth += 1
        elif s[j] == ')':
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    inner = s[i + 1:(end - 1 if end > 0 else len(s))]
    if not inner.strip() or inner.strip() == 'void':
        return '()'
    out = []
    for part in inner.split(','):
        p = part.strip()
        if not p:
            continue
        toks = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\*+|&+|\[\s*\]|\.\.\.', p)
        if not toks:
            continue
        # ★ 指针/引用/可变参数标记**必须单独保留**（第 144 轮自证实测踩到：
        #   先把 `*` 从 token 列表里过滤掉、后面又只用 `words` 重建字符串
        #   ⇒ `gh_u1 *param_1` 被归一成 `gh_u1`，指针信息丢失，
        #   于是 `gh_u1*` 与 `void*` 键不相等 ⇒ 门禁对真重复失明）。
        ptr = '*' in toks
        ref = '&' in toks
        va = '...' in toks
        words = [t for t in toks if t not in ('*', '&', '[ ]', '...')]
        if not words:
            out.append('P' if ptr else ('R' if ref else '?'))
            continue
        # 末尾若是标识符且前面还有词，则它是参数名
        if len(words) >= 2 and re.match(r'^[A-Za-z_]', words[-1]) \
                and not re.match(r'^(const|unsigned|signed|struct|union|enum|long|short)$',
                                 words[-1]):
            typ = words[:-1]
        else:
            typ = words
        t = ' '.join(typ) if typ else '?'
        t = re.sub(r'\s*\[\s*\]\s*', '', t)
        # ★ 指针 / 引用一律折叠成 `P` / `R`，**不区分被指类型**。
        #   理由（第 144 轮自证实测）：本项目按 Ghidra 复刻时，同一个函数在不同 TU 里
        #   用的是**各自本地的 typedef 名**（复刻版 `gh_u1 *param_1` vs 上游版 `void *buf`），
        #   而 ARM EABI 下两者都是 32 位指针、链接器只认**符号名**（C 无重载）⇒ 必须是同一个键。
        if va:
            t = 'V'
        elif ptr:
            t = 'P'
        elif ref:
            t = 'R'
        out.append(t)
    return '(' + ','.join(out) + ')'


def scan_sources():
    """返回 {符号名: [定义所在文件, ...]}。**范围 = BUILD_DIRS**（与构建脚本同源）。"""
    hits = {}
    for base in BUILD_DIRS:
        root = os.path.join(ROOT, base)
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__')]
            for fn in filenames:
                if not fn.endswith(('.c', '.cpp', '.cc')):
                    continue
                if SKIP_FILE_RE.match(fn):
                    continue      # GNU 源码生成器，不参与编译
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, ROOT).replace('\\', '/')
                if _in_skipped_subtree(rel):
                    continue
                try:
                    text = open(path, 'r', encoding='utf-8', errors='replace').read()
                except OSError:
                    continue
                # ★ 整块注释必须先剥掉：否则注释里写的
                #   `ClearBuffer = 0x002bdefc ...` 会被当成定义（v2 实测踩到）。
                #   逐行处理（而非三引号正则）以兼容 /* */ 与 // 混排的文件。
                in_block = False
                for raw in text.splitlines():
                    s = raw.strip()
                    if in_block:
                        if '*/' in s:
                            s = s.split('*/', 1)[1]
                            in_block = False
                        else:
                            continue
                    # 行注释只剥一次，且要处理 "code /* ... */" 同行闭合的情况
                    while True:
                        a = s.find('/*')
                        b = s.find('//')
                        if b != -1 and (a == -1 or b < a):
                            s = s[:b]
                            break
                        if a != -1:
                            e = s.find('*/', a + 2)
                            if e == -1:
                                s = s[:a]
                                in_block = True
                                break
                            s = s[:a] + ' ' + s[e + 2:]
                            continue
                        break
                    ln = s
                    if '(' not in ln or not ln:
                        continue
                    if ln.startswith('#'):
                        continue
                    if STATIC_RE.search(ln):
                        continue
                    # ★★ 以 `;` 收尾的是**声明**不是定义，两类都要排除（第 144 轮自证实测）：
                    #   ① `extern void ClearBuffer(void*, int);` —— 第 144 轮修法本身就把
                    #      上游那份改成了 extern 声明；只判名字会**把正确做法判成失败**。
                    #   ② C++ 类内成员声明 `ZRESULT Close();` —— 与 `zip.cpp` 的类外定义
                    #      `ZRESULT TZip::Close()` 聚成同名 ⇒ 误报。
                    #   类外**定义**以 `{` 开头（可跨行），本行不以 `;` 收尾。
                    #   （唯一真源就在这里，别处不要再单独判 `extern`。）
                    if ln.rstrip().endswith(';'):
                        continue
                    s = ln
                    # 关键守卫：排除「函数调用 / 控制语句」造成的误判
                    if s.startswith(('return ', 'if ', 'for ', 'while ',
                                     'switch ', 'else', 'do')):
                        continue
                    # ★ C++ 成员定义（`ZRESULT TUnzip::Close()`）**必须先判**：
                    #   DEF_RE 会先匹配出 `name='Close'`，若不优先处理就会把
                    #   `TUnzip::Close` 与 `TZip::Close` 聚成同名（第 144 轮自证实测）。
                    #   ⚠ 两条约束（第 144 轮自证实测踩到）：
                    #     ① 不能用 `^` 锚行首 —— 定义行前面有返回类型；
                    #     ② 不能用裸 `re.search` —— 会把函数体里的 `p->TUnzip::Close()`
                    #        调用也当成定义 ⇒ 用「:: 之前不得出现 `(` / `.` / `->`」守卫。
                    mm = None
                    _cm = re.search(
                        r'([A-Za-z_][A-Za-z0-9_]*)\s*::\s*([A-Za-z_~][A-Za-z0-9_]*)\s*\(',
                        s)
                    if _cm and not re.search(r'[(\.]|->', s[:_cm.start()]):
                        mm = _cm
                    if mm:
                        cls, name = mm.group(1), mm.group(2)
                        # 同名方法分属不同类 ⇒ 键必须带类名
                        key = '%s::%s%s' % (cls, name, _arglist(s))
                    else:
                        m = DEF_RE.match(s)
                        name = m.group('name') if m else None
                        if name is None:
                            continue
                        # ★ 键必须含**参数表**（第 144 轮自证实测）：
                        #   `CloseZipU(gh_u4*)` 与 `CloseZipU(HZIP,int,DWORD,const char*)`
                        #   是不同函数，链接期各占一个符号（工厂侧实测定义数=1），
                        #   只按名字聚合会误判成"重复实现"。
                        key = '%s%s' % (name, _arglist(s))
                    if not name or is_excluded(name):
                        continue
                    hits.setdefault(key, [])
                    if rel not in hits[key]:
                        hits[key].append(rel)
    return hits


# ── 产物侧：ELF 已定义 FUNC 符号 ───────────────────────────────────────────
def elf_defined_funcs(path):
    try:
        from elftools.elf.elffile import ELFFile
    except ImportError:
        return None, 'missing pyelftools'
    if not os.path.exists(path):
        return None, 'no such file: %s' % path
    out = set()
    with open(path, 'rb') as fh:
        e = ELFFile(fh)
        for s in e.iter_sections():
            st = s['sh_type']
            if st not in ('SHT_SYMTAB', 'SHT_DYNSYM'):
                continue
            for sym in s.iter_symbols():
                if sym['st_info']['type'] != 'STT_FUNC':
                    continue
                if sym['st_shndx'] == 'SHN_UNDEF':
                    continue
                nm = sym.name
                if nm:
                    out.add(nm)
    return out, None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    dup = scan_sources()
    multi = {k: v for k, v in dup.items() if len(v) >= 2}

    ours, e1 = elf_defined_funcs(a.ours)
    factory, e2 = elf_defined_funcs(a.factory)
    prod_err = [x for x in (e1, e2) if x]
    missing = sorted((factory - ours)) if (ours and factory) else []

    if a.json:
        print(json.dumps({
            'scan_dirs': BUILD_DIRS,
            'dup_global_defs': multi,
            'missing_in_ours': missing[:200],
            'missing_count': len(missing),
            'product_error': prod_err,
        }, indent=2, ensure_ascii=False))
    else:
        print('== 重复实现门禁（第 144 轮引入）==')
        print('  扫描范围（与构建脚本同源）:')
        for b in BUILD_DIRS:
            print('      %s' % b)
        print('  非 static 全局函数定义: %d 个符号' % len(dup))
        print('  ★ 出现在 >=2 个文件的（重复实现）: %d' % len(multi))
        for k in sorted(multi):
            print('      %-34s %s' % (k, '  <-  '.join(multi[k])))
        if not multi:
            print('      （无）')
        print('  产物侧: 工厂已定义 FUNC = %s / 我方 = %s'
              % (len(factory) if factory is not None else 'ERR',
                 len(ours) if ours is not None else 'ERR'))
        print('  ★ 工厂有定义、我方缺失: %d' % len(missing))
        for k in missing[:20]:
            print('      %s' % k)
        if len(missing) > 20:
            print('      ...（另 %d 个，见 --json）' % (len(missing) - 20))
        for e in prod_err:
            print('  [产物侧不可用] %s' % e)

    # 判据：**只对"重复实现" fail-closed**；产物侧不可用时降级为只报不算失败
    # （否则缺 pyelftools / 缺产物就会把门禁变成"假红"，那是本项目最忌的失败模式）。
    if multi:
        print('\n★FAIL：存在同名全局函数的重复实现（工厂侧每个符号只有一份）')
        return 2
    print('\nOK：未发现重复实现。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
