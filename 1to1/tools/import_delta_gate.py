#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""import_delta_gate.py —— 导入表全集对照门禁（防"口径污染"与"静默缺功能"）

## 为什么需要它（真实事故）
1) `bcmp` 污染（R285）：clang 把 `strcmp(x,"lit")==0` 变成 `bcmp`，工厂（GCC 6.2）不做。
   当用**无 `-fno-builtin-strcmp` 口径**编出的陈旧 `build/obj` 链接时，产物多出 `bcmp`
   ⇒ 不仅导入表与工厂不同，diff_exec 还会把 `mui_InitFont` 误判为发散（伪影）。
   单看"单侧未建模"门禁抓不到它（那条只查**工厂导入**里我们没建模的，方向相反）。
2) 只查一个探针（bcmp）是治标：任何"工厂无、我方有"的导入都应被逐个定性。

## 判据
|A| = 我方 `.dynsym` 未定义符号，|F| = 工厂 `.dynsym` 未定义符号。
- **A\\F（我方多出）**：默认 FAIL —— 多出即意味着多一条外部依赖，必须显式定性
  （典型：编译器别名、fortify 变体、错误的 libc 选择）。
- **F\\A（工厂多出）**：默认 FAIL —— 可能是我们少了某条路径（如 `_ITM_*` 属 crt 样板，
  与行为无关，但也要**登记**而不是默认豁免）。
- 两处豁免都必须走台账 `tools/import_delta_pending.txt`：
    `<符号>            # 说明`            —— 任意侧豁免
    `<A> ~ <B>         # 别名等价说明`     —— 两侧别名归一（如 `__strdup ~ strdup`）

## 自证（双向）
`--self-test` 用**独立于本项目 ELF 的合成集合**验证判据两个方向都能区分：
  反例：ours 多出 bcmp ⇒ 必须报 FAIL
  反例：factory 多出未知符号 ⇒ 必须报 FAIL
  正例：`__strdup ~ strdup` 别名对 ⇒ 不报
  正例：台账登记过的 `_ITM_*` ⇒ 不报
"""
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, 'import_delta_pending.txt')


def load_ledger(path=LEDGER):
    """返回 (豁免符号集, 别名对列表)。行内 `#` 之后是说明。"""
    if not os.path.exists(path):
        return set(), []
    exempt, aliases = set(), []
    for line in open(path, encoding='utf-8'):
        s = line.split('#', 1)[0].strip()
        if not s:
            continue
        if '~' in s:
            a, b = [x.strip() for x in s.split('~', 1)]
            aliases.append((a, b))
        else:
            exempt.add(s)
    return exempt, aliases


def norm(sets, aliases):
    """把别名对折叠成同一代表（取字典序小者），使两侧可直接比较。"""
    rep = {}
    for a, b in aliases:
        r = min(a, b)
        rep[a] = r
        rep[b] = r
    return {rep.get(s, s) for s in sets}


def judge(ours, factory, exempt=None, aliases=None):
    """返回 (ok, ours_only, factory_only, 说明行列表)。纯函数 ⇒ 可被自证直接调用。"""
    exempt = exempt or set()
    aliases = aliases or []
    o = norm(ours, aliases) - exempt
    f = norm(factory, aliases) - exempt
    ours_only = sorted(o - f)
    factory_only = sorted(f - o)
    ok = not ours_only and not factory_only
    return ok, ours_only, factory_only


def imports(path):
    from elftools.elf.elffile import ELFFile
    e = ELFFile(open(path, 'rb'))
    sec = e.get_section_by_name('.dynsym')
    if sec is None:
        return set()
    return set(s.name for s in sec.iter_symbols()
               if s.name and s['st_shndx'] == 'SHN_UNDEF')


def self_test():
    """反向用例必须红、正向用例必须绿。"""
    cases = []
    # 反例 1：我方多出 bcmp
    ok, oo, fo = judge({'strcmp', 'bcmp'}, {'strcmp'})
    cases.append(('反例 我方多出 bcmp ⇒ FAIL', (ok, oo), (False, ['bcmp'])))
    # 反例 2：工厂多出未知符号
    ok, oo, fo = judge({'strcmp'}, {'strcmp', 'some_unknown'})
    cases.append(('反例 工厂多出未知 ⇒ FAIL', (ok, fo), (False, ['some_unknown'])))
    # 正例 3：别名对不报
    ok, oo, fo = judge({'strdup'}, {'__strdup'}, aliases=[('__strdup', 'strdup')])
    cases.append(('正例 __strdup ~ strdup ⇒ PASS', ok, True))
    # 正例 4：台账豁免不报
    ok, oo, fo = judge({'_ITM_x', 'strcmp'}, {'strcmp'}, exempt={'_ITM_x'})
    cases.append(('正例 台账豁免 ⇒ PASS', ok, True))
    # 反例 5：豁免不覆盖别名两侧（防止台账写错方向）
    ok, oo, fo = judge({'bcmp'}, {'strcmp'}, exempt={'strcmp'})
    cases.append(('反例 豁免无关符号不掩盖 bcmp', ok, False))
    bad = 0
    for name, got, want in cases:
        good = got == want
        bad += 0 if good else 1
        print('  %-36s got=%-22r %s' % (name, got, 'OK' if good else '**MISMATCH**'))
    print('  self-test: %d 条，失败 %d 条' % (len(cases), bad))
    return bad == 0


def main():
    if '--self-test' in sys.argv:
        sys.exit(0 if self_test() else 1)
    ours_p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
    fac_p = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
    exempt, aliases = load_ledger()
    o, f = imports(ours_p), imports(fac_p)
    ok, ours_only, factory_only = judge(o, f, exempt, aliases)
    print('== 导入表全集对照（.dynsym UND）==')
    print('  我方 %d ｜ 工厂 %d ｜ 台账豁免 %d ｜ 别名对 %d' % (len(o), len(f), len(exempt), len(aliases)))
    if ours_only:
        print('  ★ 我方多出（%d，未登记 ⇒ FAIL）：' % len(ours_only))
        for s in ours_only:
            print('     %s' % s)
        print('    定性方法：若是编译器别名（bcmp/__*_chk）⇒ 检查编译口径（-fno-builtin-strcmp 等）；')
        print('              若是错误的 libc 选择 ⇒ 改源码；确属无害 ⇒ 登记到 tools/import_delta_pending.txt 并写理由。')
    if factory_only:
        print('  ★ 工厂多出（%d，未登记 ⇒ FAIL）：' % len(factory_only))
        for s in factory_only:
            print('     %s' % s)
    if ok:
        print('  结论：PASS —— 两侧导入集合在台账口径下完全一致')
    else:
        print('  结论：FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
