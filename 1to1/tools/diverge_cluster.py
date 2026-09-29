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
    # ★★ 2026-09-29 **二次替换锚点**：旧锚点写的是"`GetFilenameExt` 必须 DIVERGE
    #   （工厂 `return` / 我方 `UC_ERR_READ_UNMAPPED`）"。实测该**前提已不成立**：
    #   三组输入的停止方式**两侧完全一致**（[zero] 两侧 READ_UNMAPPED，[strs]/[misc] 两侧 return）
    #   ⇒ 正确判 **PASS**。原因是中间几轮把 `libc_model` 的**指针返回型语义**修对了
    #   （原先一律 `r0=0` ⇒ 我方一解引用就崩 ⇒ 假发散）。
    #   ⇒ 这又是"拿**仪器相关观测**当锚点"（本函数 docstring 开头点名过同一个坑，DequantBlock 已替换过一次）。
    #   现改为**机制稳定**的锚点：① 停止方式一致 ⇒ 判 PASS；② 明细里**必须真有停止类别**
    #   （防"全空 ⇒ 其实什么都没测却报 PASS"）。
    v_gf, rows_gf = D.compare(BF, BO, 'GetFilenameExt', 3000)
    c('正例 GetFilenameExt：两侧停止方式一致 ⇒ 判 PASS（libc_model 指针返回语义的回归锚点）',
      v_gf, 'PASS')
    _stops = [r[i] for r in rows_gf for i in (6, 7) if len(r) > i and r[i]]
    c('正例 其明细必须**有停止类别**（不是"全空 ⇒ 什么都没测"）', len(_stops) > 0, True)
    # ★ 同一次替换：旧锚点用 `GetFilenameExt` 的签名测"可读且被归因"。
    #   既然它已正确判 PASS（无差异 ⇒ 签名为空），该锚点在**这个函数**上不再有意义。
    #   改为**纯函数锚点**：直接喂一条差异文本给 `normalize()`（只依赖 `nearest_sym` 与格式化），
    #   这才是"格式化器可读可归因"的机制稳定判据。
    _t_sig = normalize("data-reads 仅F=[(3860052, 4, 'R')]", BF, BO)
    c('正例 归一化输出可读且被归因（含 +偏移 与 :宽度:读写）',
      ('+' in _t_sig) and (':4:R' in _t_sig), True)
    sig = signature(rows_gf, BF, BO)
    c('反例 签名里不应残留"两侧都空"的无信息差异（多重集展示修复的回归锚点）',
      '仅F=[] 仅O=[]' in sig, False)

    # ---- 2026-09-29 新增：`--rows` 离线归类（纯函数锚点，不依赖尺子重跑）----
    c('归一化 去掉 @地址', _norm_key('m_ui+56:4:R@0x3af29c ×1'), 'm_ui+56:4:R')
    c('归一化 裸地址降级为 <ADDR>', _norm_key('0x003cfa94:4:R ×1'), '<ADDR>:4:R')
    sf = {('data-reads', 'm_ui+56:4:R'): {'A'}}
    so = {('data-reads', 'm_ui+56:4:R'): {'B'}}
    _d, mv = _dims_and_moves("data-reads 仅F=['m_ui+56:4:R@0x3af29c ×1'] 仅O=[]", sf, so, 'A')
    c('正例 仅F访存且**对侧别的函数**也访存该地址 ⇒ 判 INLINE-MOVE 候选', bool(mv), True)
    _d2, mv2 = _dims_and_moves("data-reads 仅F=['zzz+0:4:R@0x1 ×1'] 仅O=[]", sf, so, 'A')
    c('反例 对侧**没有**该地址 ⇒ 不得判 INLINE-MOVE（防止把真差异洗白）', bool(mv2), False)
    c('维度识别 calls_ext', _dims_and_moves("calls_ext F=['strlen'] O=[]", sf, so, 'A')[0], {'ca'})
    # ★ 2026-09-29 修：指纹条目 → 与差异文本**同形**（不同形 ⇒ 反查恒不命中 ⇒ INLINE-MOVE 归零）
    c('指纹→文本同形 LN 形', _fp_str(['LN', 'm_ui', 56, 4, 'R']), 'm_ui+56:4:R')
    c("指纹→文本同形 A 形（**前导 A** 的真实形态）",
      _fp_str(['A', 3860052, 4, 'R']), '0x003ae654:4:R')
    c('反例 缺前导 A 的旧假设形态也能兜住（向后兼容）',
      _fp_str([3860052, 4, 'R']), '0x003ae654:4:R')
    _sf = {('data-reads', _fp_str(['LN', 'm_ui', 56, 4, 'R'])): {'A'}}
    _so = {('data-reads', _fp_str(['LN', 'm_ui', 56, 4, 'R'])): {'B'}}
    _d3, mv3 = _dims_and_moves("data-reads 仅F=['m_ui+56:4:R@0x3af29c ×1'] 仅O=[]", _sf, _so, 'A')
    c('正例 指纹建的索引 与 差异文本的键 能互相命中（这次的坑的回归锚点）', bool(mv3), True)
    return chk


def _fp_key(e):
    """`--dump-rows` 指纹条目 → 跨函数可比较的键。

    ★ 两种**真实**形态（2026-09-29 从明细里统计出来的，不要凭印象）：
        `["LN", 名字, 偏移, 宽度, 读写]`  （16662 条）
        `["A",  地址, 宽度, 读写]`       （20222 条）
      第一版把 A 形当成 `[地址, 宽度, 读写]`（没有前导 `'A'`）⇒ `%x` 收到字符串直接 TypeError。
    """
    if isinstance(e, list) and e and e[0] == 'LN':
        return ('LN', e[1], e[2])
    if isinstance(e, list) and e and e[0] == 'A':
        return ('A', e[1])
    if isinstance(e, list) and len(e) >= 3:
        return ('A', e[0])
    return ('?', repr(e))


def _fp_str(e):
    """`--dump-rows` 指纹条目 → **与报告差异文本同形**的键串。

    ★ 为什么必须同形（2026-09-29 踩到的坑）：反查索引是从**指纹条目**建的，
      而"仅F/仅O"的键是从**差异文本**里抠的；两者若不归一成同一形态，
      反查**永远命中不了** ⇒ 全部落进 `ONLY-ONE-SIDE` ⇒ 把 `INLINE-MOVE` 一整类误判成真差异
      （实测：误得 ONLY-ONE-SIDE 27 个、INLINE-MOVE 0 个；修好后 INLINE-MOVE 才现形）。
      形态由 `diff_exec.norm_fp` 的展示决定：
        · `'LN'` 形（具名对象+偏移）→ `名字+偏移:宽度:读写`
        · `'A'`  形（裸地址）      → `0x%08x:宽度:读写`
    """
    if isinstance(e, list) and e and e[0] == 'LN':
        return '%s+%d:%d:%s' % (e[1], e[2], e[3], e[4])
    if isinstance(e, list) and e and e[0] == 'A':
        return '0x%08x:%d:%s' % (e[1], e[2], e[3])
    if isinstance(e, list) and len(e) >= 3:
        return '0x%08x:%d:%s' % (e[0], e[1], e[2])
    return str(e)


LIST = re.compile(r"'([^']+)'")


def _dims_and_moves(body, side_f, side_o, fn):
    """从一组差异文本里取：维度集合 + "仅一侧访存"的反查落点。"""
    dims, moved, kf, ko = set(), [], set(), set()
    for part in [x.strip() for x in body.split(';')]:
        if part.startswith('data-reads'):
            dims.add('rd')
        elif part.startswith('data-writes'):
            dims.add('wr')
        elif part.startswith('calls_ext'):
            dims.add('ca')
        elif part.startswith('ret '):
            dims.add('ret')
        elif part.startswith('stop '):
            dims.add('stop')
        elif part.startswith('data-final'):
            dims.add('final')
        m = re.match(r'(data-reads|data-writes)\s+(.*)$', part)
        if not m:
            continue
        mf = re.search(r"仅F=\[(.*?)\]\s*仅O=\[(.*?)\]", m.group(2))
        if not mf:
            continue
        for k in LIST.findall(mf.group(1)):
            kf.add((m.group(1), _norm_key(k)))
        for k in LIST.findall(mf.group(2)):
            ko.add((m.group(1), _norm_key(k)))
    for dim, k in kf:
        o = side_o.get((dim, k), set()) - {fn}
        if o:
            moved.append((k, sorted(o)[:3]))
    for dim, k in ko:
        o = side_f.get((dim, k), set()) - {fn}
        if o:
            moved.append((k, sorted(o)[:3]))
    return dims, moved


def _norm_key(s):
    """报告的键形如 `sym+off:2:R@0x3acf76 ×3` ⇒ 去掉地址与计数，留 `sym+off:2:R`。"""
    s = re.sub(r'@0x[0-9a-fA-F]+', '', s)
    s = re.sub(r'\s*×\d+', '', s)
    return re.sub(r'0x[0-9a-fA-F]{8}', '<ADDR>', s)


def cluster_rows(rows_json):
    """`--dump-rows` 的 JSON → (类别 → [(函数, 证据)], 覆盖统计)。

    ★ 与 `--ledger/--all` 模式的差别：本模式**离线**（不需要再跑尺子），
      且用的是**不截断**的明细 ⇒ 报告里"前 80 行"的抽样问题被消除。
    """
    meta, rows = rows_json['meta'], rows_json['rows']
    side_f, side_o = {}, {}
    from collections import defaultdict
    side_f, side_o = defaultdict(set), defaultdict(set)
    for r in rows:
        fn = r['fn']
        # ★ 必须用 `_fp_str`（与差异文本同形），不能用 `str(e)`：
        #   否则反查永远命中不了 ⇒ INLINE-MOVE 整类被误判成真差异（本轮实测）。
        for e in (r.get('rd_f') or []):
            side_f[('data-reads', _norm_key(_fp_str(e)))].add(fn)
        for e in (r.get('rd_o') or []):
            side_o[('data-reads', _norm_key(_fp_str(e)))].add(fn)
        for e in (r.get('wr_f') or []):
            side_f[('data-writes', _norm_key(_fp_str(e)))].add(fn)
        for e in (r.get('wr_o') or []):
            side_o[('data-writes', _norm_key(_fp_str(e)))].add(fn)

    byfn = defaultdict(list)
    for r in rows:
        if r['kind'] == 'DIVERGE':
            byfn[r['fn']].append(r.get('diffs') or r.get('note') or '')

    cat = defaultdict(list)
    for fn in sorted(byfn):
        dims, moved, body = set(), [], []
        for b in byfn[fn]:
            body.extend(b if isinstance(b, list) else [str(b)])
        d, moved = _dims_and_moves(' ; '.join(map(str, body)), side_f, side_o, fn)
        dims |= d
        if not dims:
            c = 'UNKNOWN'
        elif 'stop' in dims and len(dims) > 1:
            c = 'STOP+MORE'
        elif dims == {'stop'}:
            c = 'STOP-ONLY'
        elif dims <= {'rd', 'wr'} and moved:
            c = 'INLINE-MOVE(候选假发散)'
        elif dims <= {'rd', 'wr'}:
            c = 'ONLY-ONE-SIDE(真差异第一嫌疑池)'
        elif dims == {'ca'}:
            c = 'CALLS-EXT'
        elif dims == {'ret'}:
            c = 'RET'
        elif dims == {'final'}:
            c = 'DATA-FINAL'
        else:
            c = 'MIXED(%s)' % '+'.join(sorted(dims))
        cat[c].append((fn, moved))
    return meta, cat


def report_rows(meta, cat, out=None):
    L = ['=' * 96,
         'DIVERGE 机制归类（数据源 = `diff_exec --dump-rows`，**不截断**）',
         '=' * 96,
         '  被测产物 %s sha256 %s' % (meta['ours']['path'], meta['ours']['sha256'][:16]),
         '  对照产物 %s sha256 %s' % (meta['factory']['path'], meta['factory']['sha256'][:16]),
         '  判据强度 steps=%s escalate=%s ｜ 共有 %d ｜ 本轮 %d ｜ 汇总 %s'
         % (meta['steps'], meta['escalate_factor'], meta['shared'], meta['judged'], meta['stats'])]
    tot = sum(len(v) for v in cat.values())
    L.append('')
    L.append('  %-38s %6s %7s' % ('类别', '函数数', '占比'))
    L.append('  ' + '-' * 54)
    for c in sorted(cat, key=lambda x: -len(cat[x])):
        L.append('  %-38s %6d %6.1f%%' % (c, len(cat[c]), 100.0 * len(cat[c]) / max(tot, 1)))
    L.append('  %-38s %6d' % ('合计（发散函数）', tot))
    for c in sorted(cat, key=lambda x: -len(cat[x])):
        L.append('')
        L.append('  --- %s（%d 个）---' % (c, len(cat[c])))
        for fn, moved in cat[c]:
            ex = ('  ↔对侧=%s' % (moved[0][1],)) if moved else ''
            L.append('      %-46s%s' % (fn, ex[:74]))
    L.append('')
    L.append('  ★ 判读纪律：`INLINE-MOVE` 是**候选假发散**（几何上"搬家"，不是少了行为）——')
    L.append('    修法**不是**改这些函数，而是给尺子加一条与 `calls_ext` 内联等价**对称的访存判据**；')
    L.append('    上线前必须**先写死预期降级数**并做三态自证（§2.18），不得先改结果。')
    txt = '\n'.join(L)
    print(txt)
    if out:
        with open(out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(txt + '\n')
    return txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ledger', default=os.path.join(HERE, 'diff_exec_pending.txt'))
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--rows', help='用 `diff_exec --dump-rows` 的 JSON 做**离线**归类（不截断）')
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

    if a.rows:
        import json
        if not os.path.exists(a.rows):
            sys.stderr.write('★ 缺明细 %s —— fail-closed\n' % a.rows)
            return 11
        with open(a.rows, encoding='utf-8') as fh:
            d = json.load(fh)
        meta, cat = cluster_rows(d)
        # ★ 明细必须自带"它读的是哪一版产物"，且与当前产物一致 —— 否则归类无意义
        if os.path.exists(D.OURS):
            cur = __import__('hashlib').sha256(open(D.OURS, 'rb').read()).hexdigest()[:16]
            if cur != meta['ours']['sha256'][:16]:
                sys.stderr.write('★ 明细 sha %s ≠ 当前产物 sha %s ⇒ 结果不可用\n'
                                 % (meta['ours']['sha256'][:16], cur))
                return 11
        report_rows(meta, cat, a.out)
        return 0

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
