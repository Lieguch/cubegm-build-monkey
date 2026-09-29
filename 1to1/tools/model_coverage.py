#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""model_coverage.py —— 用**工厂实际导入的动态符号**对账 `libc_model` 的覆盖。

## 为什么必须有它（2026-09-28 实证）

尺子对"外部调用"是按**名字**查模型的（`ALIASES` 先归一，再进 `Model.call`）。
若某符号在模型里**没有任何条目**：
  · **两侧都未建模** ⇒ 两侧走同一段兜底 ⇒ 不影响判决（无害）。
  · **只有一侧未建模** ⇒ 两侧走**不同**的代码路径 ⇒ **假发散**。

已抓到的两例（都属"一侧建模、一侧不建模"）：
  · `_IO_putc`：工厂导入它（真头 + 优化档下 stdio.h 走 extern-inline），
    而模型**只建了 `_IO_getc`** ⇒ 工厂侧这条调用未被建模。
  · `bcmp`：clang 把 `strcmp(x,"字面量")==0` 优化成 `bcmp(x,"字面量",len+1)`（GCC 6.2 不会）
    ⇒ 我方调 `bcmp`、工厂调 `strcmp`。

## 判据（机械、可复算，且**带棘轮**）

1. 取 `golden/factory.rkgame.bin` 与我方产物的 `.dynsym` 未定义符号并集；
2. 逐个查 `libc_model.ALIASES` / 模型源码里实际实现的名字；
3. **未建模且只出现在一侧**的符号 ⇒ 必须登记在
   `tools/model_asymmetry_ledger.txt`（每行 `符号<TAB>原因`）。
   出现**不在台账里**的 ⇒ **FAIL（exit 1）**。

★ 纪律（新增 51）：**"未建模"必须能列名并留档**；单侧未建模是**仪器缺陷**，
不是被测代码的缺陷 —— 与 void/mangled 错配、访存宽度取错下标同族。

用法:
    python tools/model_coverage.py [--ours <elf>] [--list]
"""
import argparse
import os
import re
import sys

from elftools.elf.elffile import ELFFile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import libc_model  # noqa: E402

FACTORY = "golden/factory.rkgame.bin"
LEDGER = "tools/model_asymmetry_ledger.txt"
SELF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libc_model.py")


def imports(path):
    e = ELFFile(open(path, "rb"))
    d = e.get_section_by_name(".dynsym")
    return ({s.name for s in d.iter_symbols() if s.name and s["st_shndx"] == "SHN_UNDEF"}
            if d is not None else set())


def modelled_names():
    """从模型源码**机械推导**已实现名（防手写清单腐烂）。"""
    txt = open(SELF, encoding="utf-8").read()
    names = set(re.findall(r"if name == '([^']+)'", txt))
    for t in re.findall(r"if name in \(([^)]*)\):", txt):
        names |= set(re.findall(r"'([^']+)'", t))
    return names | set(libc_model.ALIASES)


def load_ledger():
    out = {}
    if not os.path.isfile(LEDGER):
        return out
    for ln in open(LEDGER, encoding="utf-8"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        parts = ln.split("\t", 1)
        out[parts[0]] = parts[1] if len(parts) > 1 else ""
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ours", default="build/rkgame.rebuilt.elf")
    ap.add_argument("--list", action="store_true",
                    help="打印全部未建模符号（含双侧），不判成败")
    a = ap.parse_args()

    fi = imports(FACTORY)
    oi = imports(a.ours)
    known = modelled_names()
    ledger = load_ledger()

    only_f = sorted(n for n in (fi - oi) if n not in known)
    only_o = sorted(n for n in (oi - fi) if n not in known)
    asym = [(n, "工厂") for n in only_f] + [(n, "我方") for n in only_o]

    print("工厂导入 %d ｜ 我方导入 %d ｜ 模型已建模（含别名）%d 个名字"
          % (len(fi), len(oi), len(known)))
    print("★ 单侧未建模（潜在假发散）: %d 个" % len(asym))
    for n, side in asym:
        mark = "已登记" if n in ledger else "★★ 未登记"
        print("   %-28s %-5s %s" % (n, side, mark))
    if a.list:
        both = sorted(n for n in (fi & oi) if n not in known)
        print("   两侧均未建模（无害）: %d 个: %s" % (len(both), both))
        return 0

    new = [n for n, _ in asym if n not in ledger]
    if new:
        print("\n★★ 出现**不在台账**里的单侧未建模符号：%s" % new)
        print("   要么补进 libc_model.ALIASES（若确为同函数别名），要么登记进 %s 并写原因。"
              % LEDGER)
        return 1
    print("\n结论：单侧未建模符号全部在台账内 ⇒ OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
