#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐函数对拍「调用点个数」—— 源码级计数，与编译器 codegen 无关。

## 为什么需要这个门禁（第 42 轮实测的教训）

在场景 E 的执行集合差集里，我们发现 `mui_setting -> mui_outputxy_t` 的
**二进制 bl 数 工厂 13 / 我们 8**，一度以为"漏了 5 次字符串绘制调用"。核查结果：

| 层 | 工厂 | 我们 | 判定 |
|---|---|---|---|
| **源码**（Ghidra per-function C vs `src/proprietary`） | **13** | **13** | ✓ 完全一致 |
| 二进制 `bl` 指令数 | 13 | **8** | ✗ 但这**不是缺陷** |

机制：两者都编译同一份源码，但 **clang 把重复的调用序列做了 cross-jumping** ——
我们的反汇编里能看到 `mvn r7,#9`（= -10）/ `mvneq r7,#5`（= -6）后接**共享的**
`add r2,r2,r7` + `bl mui_outputxy_t`，即把工厂那两处（`sub r2,#10` 与 `sub r2,#6`）
合并成**一处**调用点。函数体积反而更大（多出寄存器调度）。

⇒ **二进制层的调用点计数不是保真度指标**（编译器有权合并/复制/内联）。
   真正与 codegen 无关的尺子是 **源码级调用表达式计数**，本工具就是它。

## 口径

* 两侧都是「一个函数一个文件」：Ghidra `03-per-function/FUN_<addr>_<name>.c`
  vs 我们的 `src/proprietary/**/FUN_<addr>_<name>.c` ⇒ 用 **`FUN_<addr>` 前缀做配对键**。
* 只数**调用表达式**（`callee(`），排除：函数定义/声明行、控制关键字、宏。
* 只报 **`工厂 > 我们`**（= 我们漏调用）。反方向（我们多）不报，避免把
  Ghidra 的内联展开噪声当成缺陷（Ghidra 会把内联进来的调用渲染在调用者体内）。
* 自证锚点（人工逐行核对过）：
    `mui_setting -> mui_outputxy_t`  = 13 / 13
    `get_items_from_zipfile -> FindZipItemA` = 1 / 1
  两者任一对不上 ⇒ 解析器不可信，拒绝出结论（铁律 101）。

退出码：0 = 无新增；1 = 有新增漏调用；2 = 自证失败。
"""
import argparse
import glob
import os
import re
import sys

# 控制关键字 / 非函数调用
KEYWORDS = {
    'if', 'while', 'for', 'switch', 'return', 'sizeof', 'do', 'else', 'case',
    'goto', 'break', 'continue', 'typeof', '__typeof__', 'defined', 'and', 'or',
    'not', 'static', 'const', 'unsigned', 'signed', 'void', 'int', 'char', 'long',
    'short', 'float', 'double', 'struct', 'union', 'enum', 'extern', 'register',
    'volatile', 'inline', 'restrict',
}

# ★★ 必须捕获**前导下划线**：mangled 名以 `_` 开头，而 `_?` 会把 `_` 吃掉、只捕获到 `Znwj`
#   ⇒ canon() 判定不出 `_Z` 前缀 ⇒ 归一化整体失效（实测踩坑，8 项误报仍在）。
CALL_RE = re.compile(r'(?<![A-Za-z0-9_>.])([A-Za-z_]\w*)\s*\(')

# 形如 `gh_u4 f(...)` / `void f(...)` / `undefined4 f(...)` 的行 = 定义或声明
DEF_RE = re.compile(
    r'^\s*(?:static\s+|extern\s+|inline\s+|__inline\s+)*'
    r'(?:gh_u[124]|gh_byte|gh_uint|undefined[1248]|byte|void|int|char|long|short|'
    r'float|double|unsigned|signed|code|uint|ulong|ushort|uchar|bool|size_t)\b'
    r'[^;=(){}]*?'
    r'\b([A-Za-z_]\w*)\s*\(')

def canon(name):
    """把调用名归一到**两侧可比的规范名**。

    ★★ 为什么必须归一（第 42 轮实测的第二次教训）：
      我们的专有 C 重建里，C++ 调用写成 **mangled 名**：
        `_Znwj(0x240)` / `_ZN6TUnzip4OpenEPvjj(this,...)` / `_ZdlPv(this)`
      而 Ghidra 的 per-function C 把同样的调用渲染成 **C++ 语法**：
        `operator_new(0x240)` / `TUnzip::Open(this,...)` / `operator_delete(this)`
      ⇒ 不做归一，这 8 处会被误报成"漏调用"（实测就是这 8 项）。
      归一规则（只做**结构性**映射，不做语义推断）：
        `_Znw*`→`operator_new`；`_Zna*`→`operator_new[]`；
        `_Zdl*`/`_Zda*`→`operator_delete`；
        `_ZN…E…`→取 `E` 前最后一个长度前缀段（= 方法短名，如 `Open`/`Close`/`Get`）。
    """
    if not name.startswith('_Z'):
        return name
    if name.startswith('_Znw'):
        return 'operator_new'
    if name.startswith('_Zna'):
        return 'operator_new[]'
    if name.startswith('_Zdl') or name.startswith('_Zda'):
        return 'operator_delete'
    m = re.match(r'_ZN((?:\d+[A-Za-z_]\w*)+)E', name)
    if m:
        head, parts, i = m.group(1), [], 0
        while i < len(head):
            j = i
            while j < len(head) and head[j].isdigit():
                j += 1
            if j == i:
                break
            ln = int(head[i:j])
            parts.append(head[j:j + ln])
            i = j + ln
        if parts:
            return parts[-1]
    return name


ANCHORS = [
    ('mui_setting', 'mui_outputxy_t', 13),
    ('get_items_from_zipfile', 'FindZipItemA', 1),
]

# ★ 负向锚点（铁律 110：锚点必须正负双向）：这些对**必须两侧相等**，
#   用来证明「mangled 名归一化」真的生效 —— 若归一化失效，它们会变成
#   「工厂 N / 我们 0」的误报（实测就是这么被发现的 8 项）。
ANCHORS_NEG = [
    ('openzipu', 'operator_new', 2),
    ('openzipu', 'Open', 1),
    ('closezipu', 'operator_delete', 2),
    ('findzipitema', 'Find', 1),
]


def func_key_from_path(path):
    """配对键 = 文件名（去扩展名、小写）。

    ★ 必须**带函数名**而不是只有 `FUN_<addr>`：两侧文件名是
    `FUN_0002b2b4_mui_setting.c`（Ghidra per-function 与我们 src/proprietary 同名），
    只有 addr 会让锚点按名字匹配不到（实测踩坑）。"""
    b = os.path.basename(path)
    if not re.match(r'(?i)FUN_[0-9a-f]{6,8}', b):
        return None
    return os.path.splitext(b)[0].lower()


def strip_comments(src):
    out = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            j = src.find('\n', i)
            i = n if j < 0 else j
        elif c == '/' and i + 1 < n and src[i + 1] == '*':
            j = src.find('*/', i + 2)
            i = n if j < 0 else j + 2
        elif c == '"':
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == '"':
                    break
                j += 1
            out.append('"' + ' ' * max(0, j - i - 1) + '"')
            i = j + 1
        elif c == "'":
            j = i + 1
            while j < n:
                if src[j] == '\\':
                    j += 2
                    continue
                if src[j] == "'":
                    break
                j += 1
            out.append(' ')
            i = j + 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def defs_in(src):
    """本文件里被**定义/声明**的函数名（这些不算调用）。"""
    return {m.group(1) for m in DEF_RE.finditer(src)}


def count_calls(src):
    src = strip_comments(src)
    black = {canon(d) for d in defs_in(src)} | KEYWORDS
    counts = {}
    for m in CALL_RE.finditer(src):
        name = canon(m.group(1))
        if name in black:
            continue
        counts[name] = counts.get(name, 0) + 1
    return counts


def index(dirpath, pattern):
    out = {}
    for p in glob.glob(os.path.join(dirpath, pattern), recursive=True):
        k = func_key_from_path(p)
        if k is None:
            continue
        try:
            txt = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        c = count_calls(txt)
        if k in out:                      # 同一 key 多个文件 ⇒ 合并
            for n, v in c.items():
                out[k][n] = out[k].get(n, 0) + v
        else:
            out[k] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--ghidra', default=r'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--ledger', default=None,
                    help='已知项台账（每行 "CALLER CALLEE"）：台账内不判失败；新增一律失败')
    ap.add_argument('--write-ledger', action='store_true')
    ap.add_argument('--selfcheck', action='store_true', default=True)
    a = ap.parse_args()

    root = a.root
    # ★★ CI 上**没有**本地 Ghidra 反编译目录（它是本机产物，不进仓库）⇒ 必须像
    #   `tools/scan_call_args.py` 一样**优雅跳过**，而不是 FATAL 退出把 CI 打红。
    #   实测踩坑：本门禁首跑在 CI 上红（本地是绿的），原因就是缺这个守卫。
    if not os.path.isdir(a.ghidra):
        print('  [SKIP] 找不到工厂反编译目录 %s' % a.ghidra)
        print('         （该目录是本机逆向产物、不进仓库；CI 上本步骤自动跳过）')
        return 0
    fa = index(a.ghidra, '*.c')
    ours = index(os.path.join(root, 'src', 'proprietary'), '**/*.c')
    if not fa or not ours:
        sys.exit('  [FATAL] 索引为空（ghidra=%d ours=%d）' % (len(fa), len(ours)))
    print('  工厂函数文件 %d 个 / 我们 %d 个' % (len(fa), len(ours)))

    # ---- 自证（铁律 101）：人工核对过的锚点必须量对 ----
    if a.selfcheck:
        ok = True
        for caller, callee, want in ANCHORS:
            def counts_of(idx, nm):
                return [c.get(callee, 0) for k, c in idx.items() if nm in k]
            fh = counts_of(fa, caller)
            oh = counts_of(ours, caller)
            print('  [selfcheck] %s -> %s : 工厂 %s / 我们 %s（期望 %d）'
                  % (caller, callee, fh, oh, want))
            if not fh or max(fh) != want or not oh or max(oh) != want:
                ok = False
        for caller, callee, want in ANCHORS_NEG:
            def c2(idx, nm):
                return [c.get(callee, 0) for k, c in idx.items() if nm in k]
            fh = c2(fa, caller)
            oh = c2(ours, caller)
            same = bool(fh) and bool(oh) and max(fh) == want and max(oh) == want
            print('  [selfcheck-neg] %s -> %s : 工厂 %s / 我们 %s（应相等=%d）%s'
                  % (caller, callee, fh, oh, want, '✓' if same else '✗'))
            if not same:
                ok = False
        if not ok:
            sys.exit('  [FATAL] 自证失败：锚点计数不符 ⇒ 调用计数解析不可信，拒绝出结论')
        print('  [selfcheck] 锚点全部量对 ✓')

    # ---- 逐函数比较：只报「工厂有、我们没有」的调用 ----
    bad = []
    common = 0
    for k in sorted(set(fa) & set(ours)):
        common += 1
        fc, oc = fa[k], ours[k]
        for callee, cnt in fc.items():
            if cnt > oc.get(callee, 0):
                bad.append((k, callee, cnt, oc.get(callee, 0)))
    bad.sort(key=lambda x: -(x[2] - x[3]))
    print('  可比对函数 %d 对' % common)

    if a.write_ledger:
        path = a.ledger or 'tools/call_counts_pending.txt'
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 逐函数「调用点个数」差异台账（棘轮）\n')
            f.write('# 格式: <caller_key> <callee> <工厂数> <我们数>\n')
            f.write('# 含义：工厂反编译 C 里该调用出现 N 次，我们源码里只出现 M<N 次\n')
            f.write('#   ⇒ 疑似漏调用（与 codegen 无关：源码级计数）。逐项核对修正后删行。\n')
            for k, callee, fn_, on in bad:
                f.write('%s %s %d %d\n' % (k, callee, fn_, on))
        print('  已写入台账：%d 项（%s）' % (len(bad), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend = set()
        for ln in open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                q = ln.split()
                if len(q) >= 2:
                    pend.add((q[0], q[1]))
        newv = [b for b in bad if (b[0], b[1]) not in pend]
        gone = sorted(pend - {(b[0], b[1]) for b in bad})
        if gone:
            print('  ★ 台账条目已消失（= 已修好）⇒ 请删行：')
            for c, ce in gone[:10]:
                print('     %s -> %s' % (c, ce))
        if newv:
            print('  ★★ 新增「漏调用」%d 项（不在台账内 ⇒ 判失败）：' % len(newv))
            for k, callee, fn_, on in newv[:a.top]:
                print('     %-24s -> %-30s 工厂 %d / 我们 %d' % (k, callee, fn_, on))
            return 1
        print('  [PASS] 无新增漏调用（台账剩余 %d 项）' % len(pend))
        return 0

    if bad:
        print('  ★ 工厂调用次数多于我们 %d 项（前 %d）：' % (len(bad), a.top))
        for k, callee, fn_, on in bad[:a.top]:
            print('     %-24s -> %-30s 工厂 %d / 我们 %d' % (k, callee, fn_, on))
        return 1
    print('  ✓ 未发现漏调用')
    return 0


if __name__ == '__main__':
    sys.exit(main())
