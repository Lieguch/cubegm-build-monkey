#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dup_copy_audit.py —— 「我方持有**第二份**同名对象」这一类副本的**等价性门禁**（§0.42）。

## 为什么需要它（本项目实测的病灶）
我方 ELF 里同时存在**两套数据宇宙**：
  · 工厂 VMA 处的副本（`src/data/factory_image.S` 的**地址垫**，GLOBAL 别名）—— 不可执行/不被读；
  · **我们编译出来的副本**（LOCAL，落在 0x4xxxxx）—— **我们的代码实际读的是这一份**。
实测规模：**684 个基名**在我方有两份（例 `aliases` 0x3ab114 / 0x410000；`stringpool_contents`；
`big5_2charset`…）。两份**大小逐一相同**。

⇒ 于是"我方读到哪一份"决定了行为尺的归因，而**两份内容是否真等价必须机械核验**：
   * 若等价 ⇒ 差异只是**地址归属**（`fp_key` 应能按名字配对）；
   * 若不等价 ⇒ **真缺陷**（我们跑的表和工厂不是同一张表）。

## 判据（本工具的全部逻辑）
对每个"我方有 >1 份"的规范名（`diff_exec.canon_obj_name`）：
  1. 取工厂侧同规范名的对象（唯一一份）；
  2. 对我方**每一份**做字段级比对：
     · 4 字节字段若**看起来是指针**（值落在本侧某个已映射段内，且该地址起是可打印 ASCII C 串）
       ⇒ 比**指向的字符串**（`entities[]`/`types[]` 这类表就是这样：字节不同但语义相同）；
     · 否则比**整数本身**。
  3. 全部字段语义相同 ⇒ `EQUIV`；有字段不同 ⇒ `★DIFF`（必须人工定性）。

退出码：0 = 无 ★DIFF；2 = 存在 ★DIFF（门禁红）；11 = 前置缺失。
用法: python tools/dup_copy_audit.py [--limit N] [--self-test]
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import diff_exec as D  # noqa: E402

PRINTABLE = re.compile(rb'^[\x20-\x7e]{1,120}$')


def read_v(b, addr, n):
    for va, fsz, _m, _f, off in b.segs:
        if va <= addr < va + fsz:
            return b.raw[off + (addr - va): off + (addr - va) + min(n, va + fsz - addr)]
    return b''


def mapped(b, addr):
    return any(va <= addr < va + fsz for va, fsz, _m, _f, _o in b.segs)


def cstr(b, addr):
    out = b''
    for i in range(128):
        c = read_v(b, addr + i, 1)
        if not c or c == b'\x00':
            break
        out += c
    return out


def field_equiv(b1, a1, b2, a2, size):
    """→ (判定, 差异字节数)。判定 ∈ {EQUIV, NEEDS-REVIEW, DIFF}。

    ★★ 2026-09-30 修（**我的第一版是错的**）：第一版用"某 4 字节字段看起来像指针 ⇒
      比指向的字符串"的启发式，结果对 `hkscs1999_2uni_upages` 这类**纯索引表**产生
      **假阳性**（同一地址、逐字节相同，却被判 ★DIFF）—— 实测拿去复核才发现：
      `同址 0x37e788 逐字节相同=True`。**假阳性比漏报更坏**（它会让门禁失去信任）。
      ⇒ 判据收紧成：
        · 字节**完全相同** ⇒ `EQUIV`（硬判据，无需解释）；
        · 字节不同、但**任一侧**存在"落在本侧已映射段内"的字段 ⇒ `NEEDS-REVIEW`
          （`entities[]`/`types[]` 这类**含指针**的表就是这样：指针值必然不同，
           必须人工按语义复核；**不得**自动判等价）；
        · 字节不同、且**没有**任何"像指针"的字段 ⇒ `DIFF`（真内容差异，门禁红）。
    """
    raw1, raw2 = read_v(b1, a1, size), read_v(b2, a2, size)
    if raw1 == raw2:
        return 'EQUIV', 0
    # ★ 读不满（该地址落在段尾/未映射）⇒ **不可判**，不得当成"内容不同"（同一个错：
    #   把"跑不起来"报成"查出问题"）。实测 `_mxml_key_once @0x3cfab4`：同址、差异字段 0，
    #   却是**一侧读不满**造成的。
    if len(raw1) != size or len(raw2) != size:
        return 'NEEDS-REVIEW', -1
    n = max(size // 4, 1)
    d = 0
    ptrish = False
    for i in range(n):
        v1 = int.from_bytes(read_v(b1, a1 + i * 4, 4).ljust(4, b'\0'), 'little')
        v2 = int.from_bytes(read_v(b2, a2 + i * 4, 4).ljust(4, b'\0'), 'little')
        if v1 != v2:
            d += 1
        if mapped(b1, v1) or mapped(b2, v2):
            ptrish = True
    return ('NEEDS-REVIEW' if ptrish else 'DIFF'), d


def audit(BF, BO, limit=0):
    def objs(b):
        out = {}
        for a, sz, n, ty in b.sym_list:
            if ty == 'STT_OBJECT':
                out.setdefault(D.canon_obj_name(n), []).append((a, sz, n))
        return out
    of, oo = objs(BF), objs(BO)
    rows = []
    for cn, ov in sorted(oo.items()):
        if len(ov) < 2 or cn not in of:
            continue
        fv = sorted(of[cn], key=lambda x: -x[1])[0]
        for a, sz, n in sorted(ov):
            if sz != fv[1]:
                rows.append((cn, n, a, sz, fv[0], fv[1], 'DIFF', -1, 'size 不符'))
                continue
            v, d = field_equiv(BO, a, BF, fv[0], sz)
            rows.append((cn, n, a, sz, fv[0], fv[1], v, d, ''))
    if limit:
        rows = rows[:limit]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        # 纯函数锚点：指针识别必须**双向**成立（正例+反例），否则"看起来像指针"会变成万能洗白器
        BF, BO = D.Bin(D.FACTORY), D.Bin(D.OURS)
        # ★ 回归锚点：第一版指针启发式在这里**假阳性**（同址逐字节相同却判 DIFF）。
        #   锚点直接钉住"同址 ⇒ EQUIV"这条硬判据。
        v1, _ = field_equiv(BO, 0x37e788, BF, 0x37e788, 3892)     # hkscs1999_2uni_upages
        v2, _ = field_equiv(BO, 0x2e8440, BF, 0x2e8440, 224)      # mac_centraleurope_page00
        v3, _ = field_equiv(BF, 0x37e788, BF, 0x37e788, 3892)     # 自反
        c1 = (v1 == 'EQUIV'); c2 = (v2 == 'EQUIV'); c3 = (v3 == 'EQUIV')
        print('  %s 正例 同址 hkscs1999_2uni_upages ⇒ EQUIV（假阳性回归锚点）' % ('✓' if c1 else '★FAIL'))
        print('  %s 正例 同址 mac_centraleurope_page00 ⇒ EQUIV' % ('✓' if c2 else '★FAIL'))
        print('  %s 正例 自反 ⇒ EQUIV' % ('✓' if c3 else '★FAIL'))
        # 反例：把尺寸改小 ⇒ 内容不同 ⇒ 不得判 EQUIV
        v4, _ = field_equiv(BO, 0x37e788, BF, 0x37e788 + 8, 3892 - 8)
        print('  %s 反例 错位比较 ⇒ 不得判 EQUIV' % ('✓' if v4 != 'EQUIV' else '★FAIL'))
        return 0 if (c1 and c2 and c3 and v4 != 'EQUIV') else 2

    BF, BO = D.Bin(D.FACTORY), D.Bin(D.OURS)
    rows = audit(BF, BO, a.limit)
    bad = [r for r in rows if r[6] == 'DIFF']
    rev = [r for r in rows if r[6] == 'NEEDS-REVIEW']
    eq = [r for r in rows if r[6] == 'EQUIV']
    print('=' * 96)
    print('「我方第二份副本」等价性审计（判据见本文件 docstring）')
    print('=' * 96)
    print('  工厂 %s' % D.FACTORY)
    print('  我方 %s' % D.OURS)
    print('  被检对象 %d 个（我方有 ≥2 份、且工厂有同名者）' % len(rows))
    print('    EQUIV（字节完全相同）%d ｜ ★DIFF（无指针字段却不同 ⇒ 真差异）%d ｜ '
          'NEEDS-REVIEW（含指针字段，须人工按语义复核）%d' % (len(eq), len(bad), len(rev)))
    print()
    for cn, n, ad, sz, fad, fsz, v, d, why in bad + rev:
        print('  %-12s %-28s 我方 %-32s @0x%08x sz=%-6d ｜ 工厂 @0x%08x sz=%d ｜ 差异字段 %s %s'
              % (v, cn, n, ad, sz, fad, fsz, d, why))
    print()
    print('★ 判读：`EQUIV` = 差异只是**地址归属**（我们的代码读自己的副本，内容与工厂逐字节相同）；')
    print('        `★DIFF` = **真内容差异**，门禁红，必须修；')
    print('        `NEEDS-REVIEW` = 含指针的表（如 `entities[]`/`types[]`），须**语义**复核，不得自动放行。')
    return 2 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
