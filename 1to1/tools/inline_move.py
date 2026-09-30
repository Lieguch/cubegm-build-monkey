#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inline_move.py —— 「访存内联等价」判据的**唯一真源**（纪律 69）。

## 这个判据要解决什么
`calls_ext` 早有一条**对称**判据（`diff_exec.compare` 内）：工厂把某个**调用**内联掉了
⇒ 只是"少调了工厂侧的某些调用"，其余观测量全一致 ⇒ 降级为 `内联等价` INFO。

**访存**没有对应判据，于是"工厂把共享子过程内联进调用方、我们保留成独立函数"这种
**几何搬家**会被算成 `DIVERGE` ⇒ 假发散（§0.29-D 的 `INLINE-MOVE` 类）。
本模块给出与 `calls_ext` 那条**对称**的判据。

## 判据（全程 fail-closed，只允许**保守**降级）
输入：某函数的**一侧访存键**集合 `KF`（只在 F 侧出现）、`KO`（只在 O 侧出现），
     以及**全局索引** `idx[side][(dim,key)] = {函数名}`。
  * **FULL** ⟺ `KF` 与 `KO` **都不空**（确有搬家）**且**
     · `KF` 的**每一个** key 都在 **O 侧别的函数**里出现（`- {本函数}`），
     · `KO` 的**每一个** key 都在 **F 侧别的函数**里出现（`- {本函数}`）。
  * 否则 **PARTIAL**（列出未解释的键）。
★ 为什么必须"每一个"而不是"存在一个"：`diverge_cluster` 原判据是**存在性**的
  ⇒ 一个函数 30 条一侧键里只有 1 条被解释也判"候选假发散" ⇒ **把真差异洗白**。
  （实测 `mui_video_setting`：30 条一侧键，21 条未解释，却仍被归入 INLINE-MOVE。）
★ 为什么"都不空"也要：两侧都空 ⇒ 根本不是搬家问题（是 `calls_ext`/`ret`/`stop` 类）。

## 键的形态（**不要再做二次折叠**）
`_fp_str` 的输出就是键的身份：
  · LN 形（具名对象+偏移）→ `名字+偏移:宽度:读写`
  · A  形（裸地址）      → `0x%08x:宽度:读写`
★★ 2026-09-30 修（真缺陷）：旧实现在这之后再跑一遍 `_norm_key`，而它会把**裸地址**
  折叠成 `<ADDR>` ⇒ **不同地址变成同一个键** ⇒ 存在性反查**凭空命中**。
  实测：`spi_printf` 的 `0x003e1a70`（F 侧独有）在旧口径下"被解释了"，其实对侧没人读它。
  ⇒ 折叠规则已删；`_norm_key` 只保留"去掉展示用的 `@地址` 与 `×计数`"。

退出码：0 = 自证通过；2 = 自证失败。
"""
import re
import sys

# --------------------------------------------------------------------------- #
# 键格式化（唯一定义处；`diverge_cluster` 只许转发）


def fp_str(e):
    """`diff_exec --dump-rows` 的指纹条目 → **与报告差异文本同形**的键串。

    两种**真实**形态（2026-09-29 从明细里统计出来的，不要凭印象）：
        `["LN", 名字, 偏移, 宽度, 读写]`  ／  `["A", 地址, 宽度, 读写]`
    """
    if isinstance(e, list) and e and e[0] == 'LN':
        return '%s+%d:%d:%s' % (e[1], e[2], e[3], e[4])
    if isinstance(e, list) and e and e[0] == 'A':
        return '0x%08x:%d:%s' % (e[1], e[2], e[3])
    if isinstance(e, list) and len(e) >= 3:
        return '0x%08x:%d:%s' % (e[0], e[1], e[2])
    return str(e)


def norm_key(s):
    """**文本**键 → 去掉展示专用的 `@绝对地址` 与 `×计数`。

    ★ 只做这两件事。**不得**把裸地址折叠成 `<ADDR>`（见模块 docstring 的 ★★）。
    """
    s = re.sub(r'@0x[0-9a-fA-F]+', '', s)
    s = re.sub(r'\s*×\d+', '', s)
    return s


# --------------------------------------------------------------------------- #
def build_index(rows, include_fn=None):
    """`--dump-rows` 的 rows → `(side_f, side_o)`，值域 `(dim,key) -> {函数名}`。

    ★ 索引只收**可比**的访存维度（`rd`/`wr`）；调用/返回/停止不参与搬家判据
      （它们各自有自己的判据，混进来会把"搬家"和"少调"搅在一起）。
    """
    side = {'F': {}, 'O': {}}
    for r in rows:
        fn = r['fn']
        if include_fn is not None and not include_fn(fn):
            continue
        for dim, key in (('rd', 'rd_f'), ('wr', 'wr_f')):
            for e in (r.get(key) or []):
                side['F'].setdefault((dim, fp_str(e)), set()).add(fn)
        for dim, key in (('rd', 'rd_o'), ('wr', 'wr_o')):
            for e in (r.get(key) or []):
                side['O'].setdefault((dim, fp_str(e)), set()).add(fn)
    return side['F'], side['O']


def one_sided(row):
    """一条明细行 → `(KF, KO)`：只在 F / 只在 O 出现的 `(dim,key)` 集合。"""
    kf, ko = set(), set()
    for dim, a, b in (('rd', row.get('rd_f'), row.get('rd_o')),
                      ('wr', row.get('wr_f'), row.get('wr_o'))):
        sf = {fp_str(e) for e in (a or [])}
        so = {fp_str(e) for e in (b or [])}
        for k in sf - so:
            kf.add((dim, k))
        for k in so - sf:
            ko.add((dim, k))
    return kf, ko


def classify(fn, kf, ko, side_f, side_o):
    """→ `(verdict, unexp_f, unexp_o)`；verdict ∈ {FULL, PARTIAL, EMPTY}。"""
    if not kf and not ko:
        return 'EMPTY', [], []
    unexp_f = [(d, k) for (d, k) in sorted(kf) if not (side_o.get((d, k), set()) - {fn})]
    unexp_o = [(d, k) for (d, k) in sorted(ko) if not (side_f.get((d, k), set()) - {fn})]
    if not unexp_f and not unexp_o:
        return 'FULL', [], []
    return 'PARTIAL', unexp_f, unexp_o


def dims_are_mem_only(diffs):
    """本行的差异文本是否**只**由 `data-reads`/`data-writes` 组成。

    ★ 为什么必须加这一条：`calls_ext`/`ret`/`stop`/`data-final` 各自有**自己的**判据
      （例如调用侧已有"内联等价"规则）。若某函数的差异里夹着这些维度，
      拿"访存搬家"去降级它 = **用 A 判据洗白 B 判据的信号**。
      实测：`FilePreEmu` / `SeletEmuCore` 各有 38 条一侧访存键**全被解释**，
      但同时带 `calls_ext` 差异 ⇒ 只按访存判就必须判 **OTHER（不降级）**。
    """
    for part in (diffs or []):
        p = str(part).strip()
        if not p:
            continue
        if not (p.startswith('data-reads') or p.startswith('data-writes')):
            return False
    return True


def function_verdict(fn, rows_of_fn, side_f, side_o):
    """一个函数的**全部**明细行 → 整体判决。

    verdict ∈ {FULL, PARTIAL, EMPTY, OTHER}
      · FULL   = 逐行都是"纯访存 + 全量被解释"的搬家 ⇒ 可对称降级
      · PARTIAL= 有未解释的一侧键 ⇒ 不得洗白
      · OTHER  = 差异里含别的维度 ⇒ 不属本判据（各自按自己的判据判）
      · EMPTY  = 没有任何一侧访存键
    ★ 必须**逐行**都 FULL 才算整体 FULL（否则"某一组输入是搬家"会把
      "另一组输入真有差异"洗白）。
    """
    saw_full = False
    for r in rows_of_fn:
        if r.get('kind') != 'DIVERGE':
            continue
        if not dims_are_mem_only(r.get('diffs')):
            return 'OTHER', ([], [])
        kf, ko = one_sided(r)
        v, uf, uo = classify(fn, kf, ko, side_f, side_o)
        if v == 'PARTIAL':
            return 'PARTIAL', (uf, uo)
        if v == 'FULL':
            saw_full = True
    return ('FULL' if saw_full else 'EMPTY'), ([], [])


# --------------------------------------------------------------------------- #
def self_test():
    chk, bad = 0, 0

    def c(tag, got, want):
        nonlocal chk, bad
        chk += 1
        if got != want:
            bad += 1
            print('  ✗ %s  got=%r want=%r' % (tag, got, want))
        else:
            print('  ✓ %s' % tag)

    # ---- 键格式化：两种真实形态 + 向后兼容 ----
    c('LN 形', fp_str(['LN', 'm_ui', 56, 4, 'R']), 'm_ui+56:4:R')
    c("A 形（带前导 'A'）", fp_str(['A', 3860052, 4, 'R']), '0x003ae654:4:R')
    c('A 形（无前导，兜底）', fp_str([3860052, 4, 'R']), '0x003ae654:4:R')

    # ---- ★★ 本模块修掉的那个真缺陷：裸地址**不得**被折叠 ----
    c('裸地址键保持精确（不得折叠成 <ADDR>）', norm_key('0x003cfa94:4:R ×1'), '0x003cfa94:4:R')
    c('不同裸地址 ⇒ 不同键', norm_key('0x003cfa94:4:R') != norm_key('0x003cfa95:4:R'), True)
    c('LN 键仍去掉展示用的 @地址', norm_key('m_ui+56:4:R@0x3af29c ×1'), 'm_ui+56:4:R')

    # ---- 判据三态 ----
    sf, so = {}, {}
    sf[('rd', 'A+0:4:R')] = {'fn1'}
    so[('rd', 'A+0:4:R')] = {'fn2'}
    v, uf, uo = classify('fn1', {('rd', 'A+0:4:R')}, set(), sf, so)
    c('正例 仅F键在O侧别的函数里 ⇒ FULL', v, 'FULL')
    v, uf, uo = classify('fn1', {('rd', 'zzz+0:4:R')}, set(), sf, so)
    c('反例 对侧没有 ⇒ PARTIAL（不得洗白）', v, 'PARTIAL')
    c('反例 指出未解释的键', uf, [('rd', 'zzz+0:4:R')])
    v, _, _ = classify('fn1', set(), set(), sf, so)
    c('两侧都空 ⇒ EMPTY（不是搬家问题）', v, 'EMPTY')
    # 部分解释：3 条键只解释 1 条 ⇒ 必须 PARTIAL（旧"存在性"判据会误判 FULL）
    sf2 = {('rd', 'a:4:R'): {'g'}, ('rd', 'b:4:R'): {'g'}}
    so2 = {('rd', 'a:4:R'): {'h'}}
    v, _, _ = classify('f', {('rd', 'a:4:R'), ('rd', 'b:4:R'), ('rd', 'c:4:R')}, set(), sf2, so2)
    c('反例 只解释 1/3 条 ⇒ PARTIAL（旧判据的洗白回归锚点）', v, 'PARTIAL')
    # 侧别对称：仅O键在F侧别的函数里 ⇒ FULL
    v, _, _ = classify('g', set(), {('wr', 'b:4:W')},
                       {('wr', 'b:4:W'): {'h'}}, {('wr', 'b:4:W'): {'g'}})
    c('正例 仅O键在F侧别的函数里 ⇒ FULL（对称）', v, 'FULL')

    # ---- 整体判决：逐行都要 FULL ----
    rows = [dict(fn='f', kind='DIVERGE', rd_f=[['LN', 'x', 0, 4, 'R']], rd_o=[],
                 wr_f=None, wr_o=None),
            dict(fn='f', kind='DIVERGE', rd_f=[['LN', 'y', 0, 4, 'R']], rd_o=[],
                 wr_f=None, wr_o=None)]
    sf3 = {('rd', 'x+0:4:R'): {'g'}, ('rd', 'y+0:4:R'): {'h'}}
    so3 = {('rd', 'x+0:4:R'): {'h'}, ('rd', 'y+0:4:R'): {'g'}}
    c('正例 两行都 FULL ⇒ 整体 FULL', function_verdict('f', rows, sf3, so3)[0], 'FULL')
    so4 = {('rd', 'x+0:4:R'): {'h'}}          # y 无人解释
    c('反例 一行 PARTIAL ⇒ 整体 PARTIAL', function_verdict('f', rows, sf3, so4)[0], 'PARTIAL')
    # ★ 夹着别的维度 ⇒ OTHER（不得用访存判据洗白调用/返回/停止类信号）
    c('维度判据 纯访存 ⇒ True',
      dims_are_mem_only(["data-reads 仅F=['a']", "data-writes 仅F=['b'] 仅O=[]"]), True)
    c('维度判据 含 calls_ext ⇒ False',
      dims_are_mem_only(["data-reads 仅F=['a']", "calls_ext F=['x'] O=[]"]), False)
    c('维度判据 含 ret/stop/final ⇒ False',
      (dims_are_mem_only(['ret F=0x1 O=0x2'])
       or dims_are_mem_only(['stop F=return O=cap'])
       or dims_are_mem_only(['data-final 不同 2 项 [1, 2]'])), False)
    rows_ca = [dict(fn='f', kind='DIVERGE', rd_f=[['LN', 'x', 0, 4, 'R']], rd_o=[],
                    wr_f=None, wr_o=None,
                    diffs=["data-reads 仅F=['x'] 仅O=[]", "calls_ext F=['q'] O=[]"])]
    c('反例 全被解释但夹 calls_ext ⇒ OTHER（FilePreEmu 型）',
      function_verdict('f', rows_ca, sf3, so3)[0], 'OTHER')

    print('  合计 %d 条，失败 %d 条' % (chk, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        sys.exit(self_test())
    print(__doc__)
