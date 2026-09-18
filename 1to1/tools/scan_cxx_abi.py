#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C++ mangled 签名对拍门禁（工厂 vs 重建）。

背景（第 45 轮实测）
--------------------
`TUnzip::Find` / `unzOpenCurrentFile` 这类 **C++ 包装层**，此前只有"函数尺寸比"这一个
弱指标（180 B vs 288 B、0x13c vs 0x16c …… 而尺寸差多数来自"内联 vs 外调"，
**不能**当保真度指标 —— 铁律 112）。真实的签发差异只能靠人肉 diff 发现：

    · 工厂 `_Z18unzOpenCurrentFileP5unz_s`      （单参，无 password）
    · 我们 `_Z18unzOpenCurrentFileP5unz_sPKc`   （双参）   ← 2026-09-18 才修掉

而**参数的个数与类型全部编码在 mangled 名里**（Itanium C++ ABI）⇒ 只要把两侧的
mangled 名按"名字部分"配对、比较"参数编码部分"，就能**机械地**抓出这一类漂移，
且与编译器无关（clang / gcc 用的是同一套 Itanium mangling）。

判据（刻意收窄，宁可漏报）
--------------------------
1. 只取**函数**符号（objdump -t 的 F），且 mangled 名以 `_Z` 开头；
   排除内部链接（`_ZL…`）、函数局部（`_ZZ…`）、vtable/typeinfo/guard（非 F 已滤）。
2. 先**归一化后缀**：`.isra.N` / `.part.N` / `.constprop.N` / `.cold` / `.clone.N` / `.llvm.N` / `.N`
   —— 这些是编译器的分区/克隆命名，同一函数的不同分区必须合并。
3. 按**名字部分**（`_Z<len><name>` 或 `_ZN…E`）配对；两侧都有的名字才比。
4. 比较**参数编码集合**（去重后的 set）。不等 ⇒ 判失败（或入台账）。

自证（铁律 101 / 110）
----------------------
· 正向锚点：`_Z18unzOpenCurrentFile` / `_Z13unzLocateFile` / `_ZN6TUnzip4FindE`
  —— 必须被**检视到**（两侧都有），并**打印当前判定**（一致 / 不一致），状态感知。
· 归一化锚点：`_ZN6TUnzip3GetE` —— 工厂侧有 `Get` 与 `Get.part.5` 两个分区，
  归一后必须**只剩一个** sig 且两侧一致（证明 `.part.N` 剥离真的生效）。
"""
import argparse
import os
import re
import subprocess
import sys

SUFFIX_RE = re.compile(r'\.(?:isra|part|constprop|cold|clone|llvm|repro|localalias)\.\d+$|\.\d+$')

ANCHORS_POS = ['_Z18unzOpenCurrentFile', '_Z13unzLocateFile', '_ZN6TUnzip4FindE']
ANCHOR_NORM = ('_ZN6TUnzip3GetE', 1)


def find_objdump(explicit=None):
    import shutil
    if explicit:
        return explicit
    for name in ('arm-linux-gnueabihf-objdump', 'arm-none-eabi-objdump'):
        c = shutil.which(name)
        if c:
            return c
    return shutil.which('objdump') or 'objdump'


def func_mangled(path, objdump):
    """取函数符号的 mangled 名集合（objdump -t 第 6 列）。"""
    out = subprocess.run([objdump, '-t', path], capture_output=True, text=True).stdout
    names = set()
    for line in out.splitlines():
        q = line.split()
        if len(q) == 6 and q[2] == 'F' and q[5].startswith('_Z'):
            names.add(q[5])
    return names


def norm(name):
    return SUFFIX_RE.sub('', name)


def split_mangled(s):
    """把 Itanium mangled 名切成 (名字部分, 参数编码部分)。

    名字部分：
      `_Z<len><ident>`              → 全局函数
      `_ZN<components>E`            → 命名空间/类成员（组件可为 `<len><ident>`、
                                      `<len><ident>I<模板实参>E`、`C1/C2/D0/D1/D2`、`St` 等）
    参数编码部分：其余全部（含 `const` 等限定由编译器编码在参数区）。
    解析失败返回 None（该符号不参与对拍 —— 宁可漏报）。
    """
    if not s.startswith('_Z'):
        return None
    if s.startswith('_ZL') or s.startswith('_ZZ'):
        return None                      # 内部链接 / 函数局部：不与工厂配对
    i = 2
    if i < len(s) and s[i] == 'N':
        i += 1
        guard = 0
        while i < len(s) and s[i] != 'E':
            guard += 1
            if guard > 64:
                return None
            if s[i] in 'CD' and i + 1 < len(s) and s[i + 1].isdigit():
                i += 2
                continue
            if s[i] == 'S' and i + 1 < len(s) and s[i + 1] in 'tabisd':
                i += 2
                continue
            if s[i] == 'U' and i + 1 < len(s):      # unnamed type (vendor extension)
                i += 2
                continue
            if s[i].isdigit():
                j = i
                while j < len(s) and s[j].isdigit():
                    j += 1
                ln = int(s[i:j])
                i = j + ln
                if i < len(s) and s[i] == 'I':      # 模板实参：跳过配对的 I..E
                    depth = 0
                    while i < len(s):
                        if s[i] == 'I':
                            depth += 1
                        elif s[i] == 'E':
                            depth -= 1
                            if depth == 0:
                                i += 1
                                break
                        i += 1
                continue
            return None
        if i >= len(s):
            return None
        return s[:i + 1], s[i + 1:]
    j = i
    while j < len(s) and s[j].isdigit():
        j += 1
    if j == i:
        return None
    ln = int(s[i:j])
    if j + ln > len(s):
        return None
    return s[:j + ln], s[j + ln:]


def collect(path, objdump):
    """→ {名字部分: set(参数编码)}"""
    out = {}
    for raw in func_mangled(path, objdump):
        sp = split_mangled(norm(raw))
        if sp is None:
            continue
        name, sig = sp
        out.setdefault(name, set()).add(sig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', default='golden/factory.rkgame.bin')
    ap.add_argument('--ours', default='build/rkgame.rebuilt.elf')
    ap.add_argument('--objdump', default=None)
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--ledger', default=None,
                    help='已知待修台账（每行 "<名字部分> <工厂签名> <我方签名>"）：台账内不判失败，'
                         '新增一律失败（棘轮语义）')
    ap.add_argument('--write-ledger', action='store_true',
                    help='把当前不一致写成台账后退出 0')
    ap.add_argument('--root', default='.', help='仓库根（默认当前目录）')
    a = ap.parse_args()

    for p in (a.factory, a.ours):
        if not os.path.exists(p):
            raise SystemExit('  [SKIP] 找不到 %s（CI 上若无该产物则跳过）' % p)

    od = find_objdump(a.objdump)
    print('  objdump = %s' % od)
    F = collect(a.factory, od)
    O = collect(a.ours, od)
    print('  工厂 C++ 函数名 %d 个 / 我们 %d 个；两侧共有 %d 个'
          % (len(F), len(O), len(set(F) & set(O))))

    # ---- 自证 1：正向锚点必须被检视到，并打印当前判定（状态感知）----
    ok = True
    for name in ANCHORS_POS:
        if name not in F or name not in O:
            print('  [selfcheck-1] 锚点 %-28s 未同时出现在两侧（工厂=%s 我们=%s）'
                  % (name, name in F, name in O))
            ok = False
            continue
        same = F[name] == O[name]
        print('  [selfcheck-1] 锚点 %-28s 已被检视；当前判定 = %s  (工厂 %s / 我们 %s)'
              % (name, '一致' if same else '★ 不一致', sorted(F[name]), sorted(O[name])))
    # ---- 自证 2：归一化锚点（.part.N 必须被剥离）----
    nm, want = ANCHOR_NORM
    got_f = sorted(F.get(nm, []))
    got_o = sorted(O.get(nm, []))
    norm_ok = (len(got_f) == want and len(got_o) == want and got_f == got_o)
    print('  [selfcheck-2] 归一化锚点 %-22s 工厂 %s / 我们 %s（期望两侧各 %d 个 sig）%s'
          % (nm, got_f, got_o, want, 'ok' if norm_ok else '★ 失败'))
    if not ok or not norm_ok:
        raise SystemExit('  [FATAL] 自证失败 ⇒ mangled 名归一/解析不可信，拒绝出结论')

    # ---- 主判定 ----
    bad = []
    for name in sorted(set(F) & set(O)):
        if F[name] != O[name]:
            bad.append((name, sorted(F[name]), sorted(O[name])))
    onlyF = sorted(set(F) - set(O))
    onlyO = sorted(set(O) - set(F))

    print()
    print('  == 签名不一致（同名字、参数编码不同）==')
    if not bad:
        print('     ✓ 无')
    for name, fs, os_ in bad[:a.top]:
        print('     %-34s 工厂 %s' % (name[:34], fs))
        print('     %-34s 我们 %s' % ('', os_))
    if len(bad) > a.top:
        print('     ...（共 %d 个）' % len(bad))
    print()
    print('  == 仅一侧有（**不计入判定**：static/模板实例/改名，噪声大，仅作规模指标）==')
    print('     仅工厂 %d 个；仅我们 %d 个' % (len(onlyF), len(onlyO)))
    for n in onlyF[:6]:
        print('       工厂独有: %s' % n[:60])
    for n in onlyO[:6]:
        print('       我们独有: %s' % n[:60])
    print()
    print('  合计：签名不一致 = %d' % len(bad))

    if a.write_ledger:
        path = a.ledger or 'tools/cxx_abi_pending.txt'
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# C++ mangled 签名不一致 · 已知待修台账（棘轮）\n')
            f.write('# 格式: <名字部分> <工厂签名> <我方签名>\n')
            f.write('# 含义：同名的 C++ 函数在两侧的参数编码不同 ⇒ 参数个数/类型真的不同（Itanium ABI）。\n')
            f.write('# ★ 修好一项**删一行**；新增不在台账内 ⇒ 门禁失败。\n')
            for name, fs, os_ in bad:
                f.write('%s %s %s\n' % (name, '|'.join(fs), '|'.join(os_)))
            f.write('#\n# ---- 仅我们独有（工厂没有该 C++ 函数）：待删除或待解释 ----\n')
            for n in onlyO:
                f.write('ORPHAN %s\n' % n)
        print('  已写入台账：签名不一致 %d 项 / 独有 %d 项（%s）' % (len(bad), len(onlyO), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend, pend_orph = set(), set()
        for ln in open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if not ln or ln.startswith('#'):
                continue
            if ln.startswith('ORPHAN '):
                pend_orph.add(ln.split()[1])
            else:
                pend.add(ln.split()[0])
        newv = [x for x in bad if x[0] not in pend]
        newo = [n for n in onlyO if n not in pend_orph]
        gone = sorted(pend - {x[0] for x in bad})
        gone_orph = sorted(pend_orph - set(onlyO))
        if gone or gone_orph:
            print('  ★ 台账条目已消失（= 已修好/已删）⇒ 请删除以下行以保持棘轮语义：')
            for n in gone:
                print('     %s' % n)
            for n in gone_orph:
                print('     ORPHAN %s' % n)
        if newv:
            print()
            print('  ★★ 新增签名不一致 %d 个（不在台账内 ⇒ 判失败）：' % len(newv))
            for name, fs, os_ in newv[:a.top]:
                print('     %-34s 工厂 %s / 我们 %s' % (name[:34], fs, os_))
        if newo:
            print()
            print('  ★★ 新增「我们独有的 C++ 函数」%d 个（工厂没有 ⇒ 判失败）：' % len(newo))
            for n in newo[:a.top]:
                print('     %s' % n)
        if newv or newo:
            return 1
        print()
        print('  [PASS] 台账一致（无新增），签名不一致 %d 项 / 独有 %d 项' % (len(pend), len(pend_orph)))
        return 0

    if bad:
        print('  [FAIL] 存在 %d 个签名不一致' % len(bad))
        return 1
    print('  [PASS] 两侧 C++ 签名完全一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
