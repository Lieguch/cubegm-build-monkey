#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diverge_cluster.py —— 把"逐条发散"聚成**类别**（GAP 17.14）。

为什么要它（这是"跳出来"的机械形式）
------------------------------------
差分执行器把 `DIVERGE` 逐**函数**列出来（当前 113 个）。逐个修 = 打地鼠；
而上一轮已经证明：**一次根因能同时消掉 9 个函数**（`.data.rel.ro.local` 白名单漏一个后缀）。
⇒ 正确的读法不是"113 个缺陷"，而是"**113 个观测 → 若干类别**"。本工具做这个归约：

  * 对每条 `DIVERGE` 的差异文本做**符号化归一**：把裸地址/地址元组换成
    `<符号名>+<偏移>:<宽度>:<读写>`（两侧各自用自己的符号表）——
    这样"同一根因在不同函数上落在不同地址"也能聚成一类，而"不同根因"不会误并。
  * 按归一后的签名分组，按组大小排序，打印每组的成员与代表差异。

用法
----
  python tools/diverge_cluster.py                 # 用棘轮台账（默认 tools/diff_exec_pending.txt）
  python tools/diverge_cluster.py --all           # 全部共有函数（慢）
  python tools/diverge_cluster.py --self-test     # 自证
退出码：0 = 分析完成；2 = 自证失败；11 = 缺输入
"""
import argparse
import bisect
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import diff_exec as D                                   # noqa: E402

TUP = re.compile(r"\((\d+),\s*(\d+),\s*'([RW])'\)")
HEX = re.compile(r"0x[0-9a-fA-F]+")


# --------------------------------------------------------------------------- #
def sym_at(b, addr, _cache={}):
    """地址 → `<符号名>+<偏移>`（单一真源：委托给 `diff_exec.Bin.nearest_sym`）。

    ★ 归因规则必须与 `diff_exec` 的访存指纹归一**用同一套**，否则聚类出来的类别
      与实际判据不对应。规则见 `Bin.nearest_sym` 与 `diff_exec.fp_key`。
    """
    key = (id(b), addr)
    if key in _cache:
        return _cache[key]
    hit = b.nearest_sym(addr)
    out = ('%s+%d' % (hit[0], addr - hit[1])) if hit else ('0x%08x' % addr)
    _cache[key] = out
    return out


def normalize(txt, bf, bo):
    """把一条差异文本符号化。`b` 选哪一侧由文本里的 `F=`/`O=` 标记决定。"""
    if not isinstance(txt, str):
        txt = str(txt)

    def rep(m):
        addr, width, rw = int(m.group(1)), m.group(2), m.group(3)
        # 该元组出现在 `仅F=` 段还是 `仅O=` 段，由它前面最近的标记决定
        head = txt[:m.start()]
        side = 'O' if head.rfind('仅O=') > head.rfind('仅F=') else 'F'
        b = bf if side == 'F' else bo
        return '%s:%s:%s' % (sym_at(b, addr), width, rw)

    return TUP.sub(rep, txt)


def signature(rows, bf, bo):
    """一组 (组名, 判定, ...) 行 → 归一化签名（组内去重、组间保序去重）。"""
    per_group = []
    for r in rows:
        if r[1] != 'DIVERGE' or len(r) < 9 or not r[8]:
            continue
        toks = sorted(set(normalize(x, bf, bo) for x in r[8]))
        per_group.append((r[0], tuple(toks)))
    uniq = []
    for cname, toks in per_group:
        if toks not in uniq:
            uniq.append(toks)
    return '\n'.join('  ' + ' ; '.join(t) for t in uniq)


def cluster(items):
    """items = [(name, signature)] → {signature: [names...]}（保序）。"""
    out = {}
    for n, s in items:
        out.setdefault(s, []).append(n)
    return out


# --------------------------------------------------------------------------- #
def self_test():
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    # ---- 归一化：纯函数性质（用真实二进制做符号表）----
    if not (os.path.exists(D.FACTORY) and os.path.exists(D.OURS)):
        c('前置 两侧产物存在', False, True)
        return chk
    BF, BO = D.Bin(D.FACTORY), D.Bin(D.OURS)
    c('前置 工厂 sym_list 保留同名多份（ArchivePath 两条）',
      sum(1 for a, sz, n, ty in BF.sym_list if n == 'ArchivePath') >= 2, True)

    # 同一符号内的两个不同地址 ⇒ 归一成"同符号不同偏移"（能聚成一类）
    t1 = normalize('data-reads 仅F=[(3860048, 4, R)]'.replace(', R', ", 'R'"), BF, BO)
    t2 = normalize('data-reads 仅F=[(3860052, 4, R)]'.replace(', R', ", 'R'"), BF, BO)
    c('正例 同符号两地址 ⇒ 前缀相同（仅偏移不同）',
      t1.split('+')[0] == t2.split('+')[0] and t1 != t2, True)
    # 不同符号 ⇒ 不得误并
    t3 = normalize("data-reads 仅F=[(3031144, 4, 'R')]", BF, BO)
    c('反例 不同符号 ⇒ 归一结果不同', t1 != t3, True)
    # 侧别判定：F / O 用各自的符号表
    t4 = normalize("data-reads 仅F=[] 仅O=[(4069652, 4, 'R')]", BF, BO)
    c('正例 仅O 的地址用**我方**符号表归因（不再是工厂符号）',
      'key2' in t4 or 'GamePath' in t4 or '0x003e1914' in t4, True)
    # 宽度与读写必须保留（窄化类缺陷靠它区分）
    c('正例 宽度/读写保留', (':4:R' in t1) and (':4:R' in t3), True)

    # ---- 聚类：同签名合并 / 异签名不合并 ----
    g = cluster([('a', 'S1'), ('b', 'S1'), ('c', 'S2')])
    c('正例 同签名两函数聚成一组', sorted(g['S1']), ['a', 'b'])
    c('正例 不同签名不合并', g['S2'], ['c'])

    # ---- 端到端锚点 ----------------------------------------------------------
    # ★ 锚点必须是**机制稳定**的事实，不能是"某函数当前判为发散"这种仪器相关观测：
    #   旧锚点写的是"DequantBlock 判 DIVERGE"，而它其实是仪器盲区造成的**假发散**（见 GAP 17.14.E）
    #   ⇒ 修好仪器后锚点自己红了。现在改用**两条互相独立的稳定锚点**：
    #   ① `DequantBlock` 必须 **PASS**（防 E1"只取单侧区间"的盲区回归）；
    #   ② `GetFilenameExt` 必须 **DIVERGE**（工厂返回 / 我方 UC_ERR_READ_UNMAPPED，语义级差异）。
    v_ok, rows_ok = D.compare(BF, BO, 'DequantBlock', 3000)
    c('正例 曾因仪器盲区**误报**的 DequantBlock 必须 PASS（防 E1 回归）', v_ok, 'PASS')
    v_bad, rows_bad = D.compare(BF, BO, 'GetFilenameExt', 3000)
    c('正例 语义级真实发散 GetFilenameExt 必须 DIVERGE', v_bad, 'DIVERGE')
    sig = signature(rows_bad, BF, BO)
    c('正例 其签名可读且被归因（含 stop/ret 或符号名）',
      any(t in sig for t in ('stop', 'ret', '+', '0x')), True)
    c('反例 签名里不应残留"两侧都空"的无信息差异（多重集展示修复的回归锚点）',
      '仅F=[] 仅O=[]' in sig, False)
    return chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', default=os.path.join(HERE, 'diff_exec_pending.txt'))
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--steps', type=int, default=3000)
    ap.add_argument('--top', type=int, default=15)
    ap.add_argument('--out')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        chk = self_test()
        bad = 0
        for tag, got, want, ok in chk:
            print('   %s  %-52s got=%s' % ('✓' if ok else '★FAIL', tag, got))
            bad += 0 if ok else 1
        print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
        return 2 if bad else 0

    for p in (D.FACTORY, D.OURS):
        if not os.path.exists(p):
            sys.stderr.write('★ 缺 %s —— fail-closed\n' % p)
            return 11
    BF, BO = D.Bin(D.FACTORY), D.Bin(D.OURS)
    common = sorted(set(BF.funcs) & set(BO.funcs))
    if a.all:
        names = common
    else:
        names = [x for x in (y.strip() for y in open(a.ledger, encoding='utf-8'))
                 if x and not x.startswith('#')]
        names = [n for n in names if n in common]
    esc = a.steps * D.ESCALATE_FACTOR

    items, n_div, n_other = [], 0, 0
    for i, n in enumerate(names):
        v, rows = D.compare(BF, BO, n, a.steps)
        if v == 'TRUNC':
            v, rows = D.compare(BF, BO, n, esc)
        if v == 'DIVERGE':
            n_div += 1
            items.append((n, signature(rows, BF, BO)))
        else:
            n_other += 1
        if (i + 1) % 10 == 0:
            import gc
            gc.collect()
            sys.stderr.write('   ... %d/%d\n' % (i + 1, len(names)))

    groups = cluster(items)
    order = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    L = ['=' * 96,
         'diff_exec 发散**类别**归约（符号化归一后聚类）',
         '=' * 96,
         '  输入 %d 个函数（%s）⇒ 发散 %d / 其他 %d ；聚成 **%d 类**（--steps %d）'
         % (len(names), '台账' if not a.all else '全部共有', n_div, n_other,
            len(order), a.steps)]
    for k, (sig, members) in enumerate(order[:a.top]):
        L.append('')
        L.append('  【第 %d 类】%d 个函数：%s' % (k + 1, len(members),
                                              ', '.join(members[:8]) +
                                              (' …' if len(members) > 8 else '')))
        for ln in sig.split('\n')[:6]:
            L.append('      ' + ln.strip()[:150])
    tail = [g for g in order[a.top:]]
    if tail:
        L.append('')
        L.append('  其余 %d 类（各 1~%d 个函数）：%s'
                 % (len(tail), max(len(g[1]) for g in tail),
                    ', '.join('%s(%d)' % (g[1][0], len(g[1])) for g in tail[:12])))
    txt = '\n'.join(L)
    print(txt)
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
