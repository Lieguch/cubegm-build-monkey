#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""从 **门禁环境自己的** diff_exec 报告机械重建棘轮台账。

────────────────────────────────────────────────────────────────────────
为什么要有这个工具（2026-10-19 R211，一次真实事故换来的）：

  `tools/diff_exec.py` 的棘轮台账（`tools/diff_exec_pending.txt`）语义是
  「本轮发散 ∪ 本轮不可判」（见 `ledger_update`：keep = diverging ∪ undecidable），
  而**判定必须在门禁所在的环境里做** —— 换一个环境，尺子的观测力就变了。

  事故经过：R210 在 **CNB 云开发** 里重编产物后 `--rebaseline`，
  云端环境判别力明显弱于 GitHub Actions（不可判 45 vs 5、REFDEAD 34 vs 0）
  ⇒ 台账被写成 91 项；而 CI 侧实测只有 22 项 ⇒ CI 判定「★新增 6 项发散」
  ⇒ 门禁假红，且假红的原因看起来像"代码回退"，非常难查。

  根治：台账内容**只允许来自门禁自己的那一次测量**。本工具从 CI 上传的
  `report/diff_exec.txt`（+ `_rows.json` 取产物 sha）里**机械**解析出
  发散集与不可判集，按 `ledger_update` 的同一公式写出台账 —— 不做任何
  人工挑选、不做任何"我觉得它已经修好了"的删改。

  用法：
    python tools/ledger_from_report.py \
        --report  <CI 产出的 report/diff_exec.txt> \
        --rows    <CI 产出的 report/_rows.json>   \   # 取被测产物 sha256
        --old     <上一版台账>（取 ruler；缺省则必须 --ruler） \
        --out     <要写的台账路径> \
        --reason  "为什么重记账"

────────────────────────────────────────────────────────────────────────
"""
import argparse
import json
import os
import re
import sys

# ---- 正则（只认门禁报告里**真实出现**的行形，见 __selfcheck 的反例） ----------
# 1) 信号强度分档行：`    [REAL       ] DrawFrame   跑完组 ...`
RE_SIG = re.compile(r'^\s*\[(REAL|ABI|NOISE|UNDECIDABLE)\s*\]\s+(\S+)\s')
# 2) 桶标题行：`  --- TRUNC：两侧均触步数上限 ... ---`
RE_BUCKET = re.compile(r'^\s*---\s*(TRUNC|REFDEAD|DEADEQ|SKIP)\s*[:：]')
# 3) 判据强度行：`  判据强度：--steps 3000；触上限者按 20× 放大重试一次（本轮 2 个靠放大才判出）`
RE_STEPS = re.compile(r'--steps\s+(\d+)')
RE_ESC = re.compile(r'按\s+(\d+)\s*[×x]\s*放大')
# 4) 汇总行（用于**交叉核对**解析出来的集合大小是否自洽）
RE_SUM = re.compile(
    r'汇总：PASS\s+(\d+)\s*[｜|]\s*DIVERGE\s+(\d+)\s*[｜|]\s*TRUNC.*?(\d+)\s*[｜|]\s*'
    r'DEADEQ.*?(\d+)\s*[｜|]\s*REFDEAD.*?(\d+)\s*[｜|]\s*SKIP\s+(\d+)')

BUCKET_TITLES = ('TRUNC', 'REFDEAD', 'DEADEQ', 'SKIP')


def parse_report(txt):
    """解析门禁报告 → (div_names, buckets, steps, esc_factor, stats)。"""
    div, buckets, stats = [], {k: [] for k in BUCKET_TITLES}, None
    steps = esc = None
    cur = None
    for ln in txt.splitlines():
        s = ln.strip()
        m = RE_SIG.match(ln)
        if m:
            div.append(m.group(2))
            continue
        m = RE_BUCKET.match(ln)
        if m:
            cur = m.group(1)
            continue
        if cur and s.startswith('---'):
            cur = None
            continue
        if cur:
            # 桶内条目：一行一个函数名；`（无）` = 空桶
            if s and s != '（无）' and not s.startswith('（'):
                buckets[cur].append(s.split()[0])
            continue
        if RE_STEPS.search(ln):
            steps = int(RE_STEPS.search(ln).group(1))
        if RE_ESC.search(ln):
            esc = int(RE_ESC.search(ln).group(1))
        m = RE_SUM.search(ln)
        if m:
            stats = dict(zip(('PASS', 'DIVERGE', 'TRUNC', 'DEADEQ', 'REFDEAD', 'SKIP'),
                             (int(x) for x in m.groups())))
    return sorted(set(div)), buckets, steps, esc, stats


def read_ruler(path):
    """从旧台账头部取 ruler（口径指纹）。"""
    if not path or not os.path.exists(path):
        return None
    for ln in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^#\s*ruler\s*=\s*([0-9a-fA-F]{8,64})\s*$', ln.strip())
        if m:
            return m.group(1)
    return None


def atomic_write(path, text):
    """★ 原子写（用户铁律）：先写 .tmp → 校验 → os.replace。
    直接 open(p,'w') 一旦中途异常就会把唯一副本截断成 0 字节。"""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)
    # 写后校验：能被读回、且行数与内容一致
    back = open(tmp, encoding='utf-8').read()
    if back != text:
        os.unlink(tmp)
        raise SystemExit('原子写校验失败：回读不一致（未动原文件）')
    os.replace(tmp, path)


def __selfcheck():
    """自证：解析器必须在**人工构造的小型报告**上抓对，且反例不得误抓。"""
    fixture = '\n'.join([
        '  判据强度：--steps 3000；触上限者按 20× 放大重试一次（本轮 2 个靠放大才判出）',
        '  汇总：PASS 768 ｜ DIVERGE 2 ｜ TRUNC(不可判) 1 ｜ DEADEQ(共同早死等价) 1 '
        '｜ REFDEAD(参照侧早死) 0 ｜ SKIP 1',
        '  --- DIVERGE 明细（前 80）---',
        '  foo                                    [strs] ret F=0x1 O=0x2',
        '  foo                                    [core] ret F=0x1 O=0x2',
        '',
        '  --- DIVERGE 信号强度（派生，不改判据）：REAL 1 ｜ ABI 1 ｜ NOISE 0 ｜ UNDECIDABLE 0 ｜ 合计 2 ---',
        '    [REAL       ] foo                          跑完组 core,misc,strs 两侧观测不同',
        '    [ABI        ] bar                          ret-only 且两侧 ret 都落在沙箱人造区',
        '',
        '  --- TRUNC：两侧均触步数上限 ---',
        '  t1',
        '',
        '  --- REFDEAD：参照侧早死 ---',
        '  （无）',
        '',
        '  --- DEADEQ：两侧同一个野地址早死 ---',
        '  d1',
        '',
        '  --- SKIP：一侧执行环境报错 ---',
        '  s1',
    ])
    div, bk, steps, esc, stats = parse_report(fixture)
    ok = []

    def c(label, got, want):
        ok.append((label, got == want, got, want))
    c('解析 steps', steps, 3000)
    c('解析 放大倍数', esc, 20)
    c('发散集（明细重复行去重）', div, ['bar', 'foo'])
    c('TRUNC 桶', bk['TRUNC'], ['t1'])
    c('REFDEAD 桶（（无）⇒ 空）', bk['REFDEAD'], [])
    c('DEADEQ 桶', bk['DEADEQ'], ['d1'])
    c('SKIP 桶', bk['SKIP'], ['s1'])
    c('汇总交叉核对 DIVERGE', stats['DIVERGE'], 2)
    c('★ 解析出的发散集大小 == 汇总 DIVERGE', len(div), stats['DIVERGE'])
    und = set(bk['TRUNC']) | set(bk['REFDEAD']) | set(bk['DEADEQ']) | set(bk['SKIP'])
    c('★ 不可判集大小 == 汇总 TRUNC+REFDEAD+DEADEQ+SKIP', len(und),
      stats['TRUNC'] + stats['REFDEAD'] + stats['DEADEQ'] + stats['SKIP'])
    # 反例：桶外的内容不得被抓进来
    c('反例  明细行里的函数名不得混入发散集（只认信号强度分档行）',
      'foo' in div and 'ret' not in div, True)
    nfail = sum(1 for _, g, _, _ in ok if not g)
    for label, good, got, want in ok:
        print('  %s  %-52s got=%r' % ('✓' if good else '★FAIL', label, got))
    print('  合计 %d 条，失败 %d 条' % (len(ok), nfail))
    return 0 if nfail == 0 else 2


def main():
    if '--selfcheck' in sys.argv:
        return __selfcheck()
    ap = argparse.ArgumentParser()
    ap.add_argument('--report', required=True, help='门禁产出的 report/diff_exec.txt')
    ap.add_argument('--rows', default=None, help='门禁产出的 report/_rows.json（取被测产物 sha256）')
    ap.add_argument('--old', default=None, help='上一版台账（取 ruler）')
    ap.add_argument('--ruler', default=None, help='口径指纹（缺省从 --old 读）')
    ap.add_argument('--out', required=True)
    ap.add_argument('--reason', required=True, help='为什么重记账（留痕，必填）')
    a = ap.parse_args()

    txt = open(a.report, encoding='utf-8', errors='replace').read()
    div, bk, steps, esc, stats = parse_report(txt)
    und = set()
    for k in BUCKET_TITLES:
        und |= set(bk[k])

    # ★ 自洽核对：解析出的集合必须与报告汇总行一致，否则**拒绝写台账**
    if stats:
        if len(div) != stats['DIVERGE']:
            raise SystemExit('★ 不自洽：解析出发散 %d ≠ 汇总 DIVERGE %d ⇒ 拒绝写台账'
                             % (len(div), stats['DIVERGE']))
        n_und = stats['TRUNC'] + stats['REFDEAD'] + stats['DEADEQ'] + stats['SKIP']
        if len(und) != n_und:
            raise SystemExit('★ 不自洽：解析出不可判 %d ≠ 汇总 %d ⇒ 拒绝写台账'
                             % (len(und), n_und))
    if not steps or not esc:
        raise SystemExit('★ 报告里没解析到 steps / 放大倍数 ⇒ 拒绝写台账')

    ours = ''
    if a.rows and os.path.exists(a.rows):
        meta = json.load(open(a.rows, encoding='utf-8'))['meta']
        ours = meta['ours']['sha256']
    ruler = a.ruler or read_ruler(a.old)
    if not ruler:
        raise SystemExit('★ 拿不到 ruler（口径指纹）：传 --ruler 或 --old <旧台账>')

    keep = sorted(set(div) | und)     # ★ 与 diff_exec.ledger_update 同一公式
    old = []
    if a.old and os.path.exists(a.old):
        old = [l.strip() for l in open(a.old, encoding='utf-8', errors='replace')
               if l.strip() and not l.startswith('#')]

    body = ['# diff_exec 发散棘轮台账（只允许减少）',
            '# steps=%d' % steps,
            '# escalate=%d' % (steps * esc)]
    if ours:
        body.append('# ours=%s' % ours)
    body.append('# ruler=%s' % ruler)
    body.append('# rebaseline: %s' % a.reason)
    body.append('# ★ 本台账由 tools/ledger_from_report.py 从**门禁环境自己的**测量报告'
                '机械重建（不人工挑选）—— 见文件头注释里的事故经过。')
    body.append('# 生成：python tools/diff_exec.py --batch --steps %d --ledger <本文件> '
                '--update-ledger' % steps)
    body.append('# ★ 评测时必须用**相同的 steps/escalate/ruler**，否则本工具 '
                'fail-closed (exit 3) —— 见 GAP 17.10 / §0.36')
    body.extend(keep)
    atomic_write(a.out, '\n'.join(body) + '\n')

    print('台账已重建（原子写）：%s' % a.out)
    print('  发散 %d ∪ 不可判 %d ⇒ 共 %d 项' % (len(div), len(und), len(keep)))
    print('  steps=%d escalate=%d ruler=%s' % (steps, steps * esc, ruler[:16]))
    if ours:
        print('  ours=%s' % ours[:16])
    print('  ★新增（相对旧台账）：%s' % sorted(set(keep) - set(old)))
    print('  ✓已收敛（旧台账里本轮不再发散/不可判）：%s' % sorted(set(old) - set(keep)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
