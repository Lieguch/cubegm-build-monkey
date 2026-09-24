#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_ci_reach —— 防「CI 可达的工具依赖宿主绝对路径」这一类**静默假绿**。

为什么需要它（GAP 16.86 / 16.87 的**第三次复发**）
--------------------------------------------------
同一根因已经烧掉三轮 CI：
  ① `prop_equiv.py` 只找 `golden/factory.funcs.json`，而 CI 里只有 `.gz`；
  ② `mmio_width_audit.py` 只找 `.json`（同上，1to1-qemu-behav exit 15）；
  ③ **2026-09-24** `src_transcript_parity.py` 把语料路径**硬编成本机 `D:/…`** ⇒
     GitHub Actions 上 `os.listdir` 抛 `FileNotFoundError` ⇒ 整个 job 红，
     且**紧随其后的那道门禁被 skipped**（连带的观测损失比这道门禁本身更大）。
三次都不是"逻辑错"，而是"**判据的输入在 CI 里不存在**"。所以判据不能靠复查，必须是机械门禁。

本门禁的判据（单一、可机械验证）
--------------------------------
  1. 先从 workflow YAML 解出 **CI 可达的工具集**（显式调用 + 经 `.sh`/`.py` 的**传递闭包**；
     注释行不算调用 —— 否则注释里提到的名字会造出假可达）。
  2. 对每个可达工具，扫描**宿主绝对路径**字符串字面量（驱动盘形式，如 `D:/…`、`C:\\…`）。
     `/dev` `/proc` `/mnt` `/tmp` 等**设备/沙箱路径天然合法**，不在判据内。
  3. 每个命中必须"自动合法"或"被台账显式豁免"：
     * 行内含 `environ` / `getenv` ⇒ `env`（可被环境变量覆盖）
     * 行首是 `#`（注释/文档）     ⇒ `comment`
     * 命中在 `tools/ci_local_paths_allow.txt` 里 ⇒ 台账豁免（每条必须带理由）
  4. **双向棘轮**：台账里过期（已不再命中）的条目必须删掉 ⇒ FAIL；
     理由写成 `devonly:` 的条目，若该文件**其实可达 CI** ⇒ FAIL（理由本身是假的）。

★ 本门禁只读仓内文件 ⇒ **它自身没有"CI 里不存在的输入"**（这正是要推广的性质）。

自证（--self-test）
-------------------
正例：仓内相对路径 / 行内 `environ` / 注释里的宿主路径 / 台账已豁免  ⇒ PASS
反例：可达工具里的裸宿主路径 ⇒ FAIL；台账过期条目 ⇒ FAIL；`devonly:` 但实际可达 ⇒ FAIL
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, '.github', 'workflows')
ALLOW = os.path.join(ROOT, 'tools', 'ci_local_paths_allow.txt')

RE_TOOLNAME = re.compile(r'tools/([A-Za-z0-9_][A-Za-z0-9_.-]*\.(?:py|sh))')
# ★ 裸模块导入（`from ghidra_corpus import …` / `import ghidra_corpus`）没有 `tools/` 前缀
#   ⇒ 只靠 RE_TOOLNAME 会漏边（实测：`ghidra_corpus.py` 明明是 CI 路径上的模块却没被判可达）。
RE_BARE_IMPORT = re.compile(r'^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)')
RE_HOSTPATH = re.compile(r'''["']([A-Za-z]:[\\/][^"'\n]*)["']''')
# ★ 精度：`.py` 里对别的工具的引用**只有在"会真的执行它"的上下文里**才算可达边。
#   否则一句文档字符串里的 `tools/foo.py` 就会把不可达工具判成可达 ⇒ 台账被迫堆满假条目。
PY_EDGE_HINTS = ('import', 'subprocess', 'os.system', 'Popen', 'run(', 'executable', 'check_call')


def _strip_comment_lines(txt, comment='#'):
    return '\n'.join(('' if l.lstrip().startswith(comment) else l) for l in txt.splitlines())


def read(p):
    return open(p, encoding='utf-8', errors='replace').read()


def _workflow_dir(base):
    """定位 workflow 目录：本层优先，其次**上一层**（CI 的真实布局）。

    ★ 这里踩过一次「CI 近似态」坑（正是 GAP 16.86 记的纪律）：
      CI 里仓库把 workflow 放在**仓库根** `.github/workflows/`，而步骤的 CWD / 本工具 ROOT
      是 `1to1/` ⇒ 只查本层会**找不到 workflow** ⇒ 可达集为空 ⇒ 门禁**空转 PASS**。
      所以：本层没有就查上一层；两边都没有 ⇒ 返回 None，由调用方 **fail-closed**。
    """
    for cand in (os.path.join(base, '.github', 'workflows'),
                 os.path.join(base, '..', '.github', 'workflows')):
        if os.path.isdir(cand) and any(f.endswith(('.yml', '.yaml')) for f in os.listdir(cand)):
            return os.path.normpath(cand)
    return None


def reachable(base=None):
    """返回 CI 可达的工具相对路径集合（相对 ROOT，`/` 分隔）；找不到 workflow ⇒ None（fail-closed）。"""
    base = base or ROOT
    wf = _workflow_dir(base)
    if wf is None:
        return None
    seen, queue = set(), []
    for f in sorted(os.listdir(wf)):
        if f.endswith(('.yml', '.yaml')):
            for m in RE_TOOLNAME.finditer(_strip_comment_lines(read(os.path.join(wf, f)))):
                queue.append('tools/' + m.group(1))
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        seen.add(rel)
        p = os.path.join(base, rel.replace('/', os.sep))
        if not os.path.exists(p):
            continue
        if rel.endswith(('.sh', '.py')):
            for line in _strip_comment_lines(read(p)).splitlines():
                if rel.endswith('.py') and not any(h in line for h in PY_EDGE_HINTS):
                    continue
                for m in RE_TOOLNAME.finditer(line):
                    queue.append('tools/' + m.group(1))
                if rel.endswith('.py'):
                    m = RE_BARE_IMPORT.match(line)
                    if m and os.path.exists(os.path.join(base, 'tools', m.group(1) + '.py')):
                        queue.append('tools/' + m.group(1) + '.py')
    return seen


def load_allow(path=None):
    """台账：`relpath<TAB>字面量<TAB>理由`。返回 [(rel, lit, reason)]。"""
    p = path or ALLOW
    out = []
    if not os.path.exists(p):
        return out
    for i, line in enumerate(read(p).splitlines(), 1):
        line = line.rstrip('\n')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) != 3:
            raise ValueError('%s 第 %d 行格式错（应 rel<TAB>字面量<TAB>理由）: %r' % (p, i, line[:80]))
        out.append(tuple(x.strip() for x in parts))
    return out


def scan(base=None, allow_path=None):
    base = base or ROOT
    reach = reachable(base)
    if reach is None:
        return None, load_allow(allow_path), None
    allow = load_allow(allow_path)
    hits = []          # (rel, lineno, literal, kind)
    for rel in sorted(reach):
        p = os.path.join(base, rel.replace('/', os.sep))
        if not os.path.exists(p):
            continue
        lines = read(p).splitlines()
        for i, line in enumerate(lines, 1):
            for m in RE_HOSTPATH.finditer(line):
                lit = m.group(1)
                # 邻域窗口：多行写法 `SYMTAB = os.environ.get('FACTORY_SYMTAB',\n  r'D:/…')`
                # 里，`environ` 在**上一行** ⇒ 只看本行会漏判（实测 factory_fn_stack.py:39）。
                win = '\n'.join(lines[max(0, i - 2):i + 1])
                if line.lstrip().startswith('#'):
                    kind = 'comment'
                elif 'environ' in win or 'getenv' in win:
                    kind = 'env'
                else:
                    kind = 'need-allow'
                hits.append((rel, i, lit, kind))
    return reach, allow, hits


def run(base=None, allow_path=None, verbose=False):
    reach, allow, hits = scan(base, allow_path)
    print('=' * 100)
    print('CI 可达性 / 宿主绝对路径门禁')
    print('=' * 100)
    if reach is None:
        print('  ★ FAIL：找不到 workflow 目录（试过 <base>/.github/workflows 与 <base>/../.github/workflows）')
        print('     ⇒ 可达集无法确定 ⇒ **拒绝出结论**（fail-closed：空转 PASS = 假绿）。')
        return 17
    print('  CI 可达工具数 = %d' % len(reach))
    print('  命中宿主绝对路径 = %d 处（其中 注释 %d / 可 env 覆盖 %d / 需台账 %d）' % (
        len(hits),
        sum(1 for h in hits if h[3] == 'comment'),
        sum(1 for h in hits if h[3] == 'env'),
        sum(1 for h in hits if h[3] == 'need-allow')))
    allow_keys = {(a[0], a[1]) for a in allow}
    used = set()
    bad = []
    for rel, ln, lit, kind in hits:
        if kind in ('comment', 'env'):
            continue
        # 台账里允许用**字面量前缀**匹配（含通配 `*` 的简单 glob 语义）
        match = None
        for a in allow:
            if a[0] == rel and (a[1] == lit or (a[1].endswith('*') and lit.startswith(a[1][:-1]))):
                match = a
                break
        if match:
            used.add((match[0], match[1]))
        else:
            bad.append((rel, ln, lit, kind, None))
    # 棘轮：过期条目
    stale = [a for a in allow if (a[0], a[1]) not in used
             and not any(h[0] == a[0] and (h[2] == a[1] or (a[1].endswith('*') and h[2].startswith(a[1][:-1])))
                         for h in hits)]
    # 理由自证：devonly 条目不得可达
    lying = [a for a in allow if a[2].startswith('devonly:') and a[0] in reach]
    if verbose:
        for h in hits:
            print('    %-38s:%-4d [%s] %s' % (h[0], h[1], h[3], h[2][:60]))
    if bad:
        print()
        print('  ★ FAIL：%d 处「CI 可达的工具里的宿主绝对路径」未被台账豁免：' % len(bad))
        for rel, ln, lit, kind, _ in bad:
            print('     %-38s:%-4d %s' % (rel, ln, lit[:70]))
    if stale:
        print()
        print('  ★ FAIL：台账 %d 条已过期（不再命中）⇒ 必须删掉，防止台账变成"免死金牌"：' % len(stale))
        for a in stale:
            print('     %-38s %s' % (a[0], a[1][:60]))
    if lying:
        print()
        print('  ★ FAIL：台账理由写 `devonly:`，但该文件**可达 CI** ⇒ 理由不成立：')
        for a in lying:
            print('     %-38s' % a[0])
    if bad or stale or lying:
        return 17
    print()
    print('  PASS：CI 可达工具里的每一处宿主绝对路径，要么可被 env 覆盖、要么在注释里、要么有台账理由。')
    print('  台账 %d 条，本次实际用到 %d 条。' % (len(allow), len(used)))
    return 0


def self_test():
    import shutil
    import tempfile
    print('=' * 100)
    print('自证：用已知答案的样本验仪器')
    print('=' * 100)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-6s %s' % (tag, got, '✓' if good else '★ FAIL'))

    # ★ 夹具路径**运行时拼接**：源码里刻意不写 "D:/…" 这类字面量，否则本门禁会把自己扫出来
    #   （夹具与被判对象同文件）。这不是给自己开后门 —— 判据本身不留例外，只是夹具避开字面形式。
    # ★ 必须是「驱动器 + 分隔符」形式：`os.path.join('D:', 'x')` 在 Windows 上得到 `D:x`
    #   （驱动器**相对**路径，`D:` 后无分隔符）⇒ RE_HOSTPATH 永不命中 ⇒ 夹具自造假样本。
    FAKE_HOST = 'D' + ':' + '/' + 'output' + '/' + 'thing'
    d = tempfile.mkdtemp()
    d2 = d3 = None
    try:
        os.makedirs(os.path.join(d, '.github', 'workflows'))
        os.makedirs(os.path.join(d, 'tools'))
        wf = os.path.join(d, '.github', 'workflows', 'w.yml')
        t1 = os.path.join(d, 'tools', 'g1.py')
        t2 = os.path.join(d, 'tools', 'g2.py')
        ap = os.path.join(d, 'tools', 'allow.txt')
        open(ap, 'w').write('')

        # 反例① 可达工具里的裸宿主路径 ⇒ 命中 need-allow
        open(wf, 'w').write('run: python tools/g1.py\n')
        open(t1, 'w').write('P = %r\nprint(P)\n' % FAKE_HOST)
        _r, _a, hits = scan(d, ap)
        chk('反例 裸宿主路径 → need-allow', [h[3] for h in hits], ['need-allow'])

        # 正例① 行内含 environ ⇒ env
        open(t1, 'w').write("import os\nP = os.environ.get('X', %r)\n" % FAKE_HOST)
        _r, _a, hits = scan(d, ap)
        chk('正例 行内 environ → env', [h[3] for h in hits], ['env'])

        # 正例② 注释里的宿主路径 ⇒ comment（真实场景：注释掉的旧赋值，带引号）
        open(t1, 'w').write('# 旧写法: P = %r\nP = 1\n' % FAKE_HOST)
        _r, _a, hits = scan(d, ap)
        chk('正例 注释里的路径 → comment', [h[3] for h in hits], ['comment'])

        # 正例②b 注释里**不带引号**的路径 ⇒ 根本不命中（正则要求引号 ⇒ 噪声更低）
        open(t1, 'w').write('# 参见 %s 的说明\nP = 1\n' % FAKE_HOST)
        _r, _a, hits = scan(d, ap)
        chk('正例 注释无引号 → 0 命中', len(hits), 0)

        # 正例③ 不可达文件里的裸路径 ⇒ 不命中（注释行不算调用）
        open(t1, 'w').write('P = 1\n')
        open(t2, 'w').write('P = %r\n' % FAKE_HOST)
        _r, _a, hits = scan(d, ap)
        chk('正例 不可达文件 → 0 命中', len(hits), 0)
        open(wf, 'w').write('# run: python tools/g2.py\n')
        chk('正例 注释里提到 tools/g2.py 不算可达', 'tools/g2.py' in reachable(d), False)

        # 正例④ 台账豁免 ⇒ PASS
        open(wf, 'w').write('run: python tools/g1.py\n')
        open(t1, 'w').write('P = %r\n' % FAKE_HOST)
        open(ap, 'w').write('tools/g1.py\t%s\tresolver:仓内优先 + fail-closed\n' % FAKE_HOST)
        chk('正例 台账豁免 → run() = 0', run(d, ap), 0)

        # 反例② 台账过期 ⇒ FAIL(17)
        open(ap, 'w').write('tools/g1.py\tD:%s\tstale\n' % '/nonexistent')
        chk('反例 台账过期 → 17', run(d, ap), 17)

        # 反例③ devonly 但实际可达 ⇒ FAIL(17)
        open(ap, 'w').write('tools/g1.py\t%s\tdevonly:只在开发机用\n' % FAKE_HOST)
        chk('反例 devonly 却可达 → 17', run(d, ap), 17)

        # ★ 正例⑤ **CI 近似态**（GAP 16.86 的纪律）：workflow 在**上一层**、工具在其子目录
        #   —— CI 里 `cd 1to1` 正是这种布局。只查本层会找不到 workflow ⇒ 空转 PASS（假绿）。
        d2 = tempfile.mkdtemp()
        os.makedirs(os.path.join(d2, '.github', 'workflows'))
        os.makedirs(os.path.join(d2, '1to1', 'tools'))
        open(os.path.join(d2, '.github', 'workflows', 'w.yml'), 'w').write('run: python tools/g1.py\n')
        open(os.path.join(d2, '1to1', 'tools', 'g1.py'), 'w').write('P = %r\n' % FAKE_HOST)
        ap2 = os.path.join(d2, '1to1', 'tools', 'allow.txt')
        open(ap2, 'w').write('tools/g1.py\t%s\tresolver:仓内优先\n' % FAKE_HOST)
        chk('正例 CI 近似态（workflow 在上层）→ 可达',
            reachable(os.path.join(d2, '1to1')), {'tools/g1.py'})
        chk('正例 CI 近似态 → run() = 0', run(os.path.join(d2, '1to1'), ap2), 0)

        # 反例④ 任何一层都没有 workflow ⇒ 必须 fail-closed(17)，不得空转 PASS
        d3 = tempfile.mkdtemp()
        os.makedirs(os.path.join(d3, 'tools'))
        open(os.path.join(d3, 'tools', 'g1.py'), 'w').write('P = %r\n' % FAKE_HOST)
        chk('反例 无 workflow 任何一层 → 17', run(d3, os.path.join(d3, 'tools', 'a.txt')), 17)
    finally:
        for _x in (d, d2, d3):
            if _x:
                shutil.rmtree(_x, ignore_errors=True)
    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('-v', '--verbose', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 17
    return run(verbose=a.verbose)


if __name__ == '__main__':
    sys.exit(main())
