#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""classify_strict2.py — 把 report/local_recon_build.txt 的假绿清单按错误特征归类并统计。
用法: python tools/classify_strict2.py [report_path]
只读，不编译。"""
import re, sys, collections, os

REP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "report", "local_recon_build.txt")
txt = open(REP, encoding="utf-8", errors="replace").read()

# 取「★ 假绿清单」节，到下一个分隔/「---」为止
m = re.search(r"★ 假绿清单[^\n]*\n(.*?)(?:\n---|\Z)", txt, re.S)
body = m.group(1) if m else ""
rows = [l for l in body.splitlines() if l.strip() and "|" in l]

BUCKETS = [
    ("int→pointer 实参",      r"incompatible integer to pointer conversion"),
    ("pointer→int 实参",      r"incompatible pointer to integer conversion"),
    ("指针类型不符",           r"incompatible pointer types"),
    ("函数指针类型不符",       r"incompatible function pointer types"),
    ("赋值 int↔pointer",      r"incompatible (integer to pointer|pointer to integer) conversion (assigning|initializing|returning)"),
    ("返回值/参数类型",        r"incompatible (integer to pointer|pointer to integer|pointer types)"),
    ("其他",                  r"."),
]

print(f"报告: {REP}")
print(f"假绿条目: {len(rows)}\n")

cnt = collections.Counter()
detail = collections.defaultdict(list)
for r in rows:
    f, err = (r.split("|", 1) + [""])[:2]
    for name, pat in BUCKETS:
        if re.search(pat, err):
            cnt[name] += 1
            detail[name].append((f, err[:160]))
            break

for name, n in cnt.most_common():
    print(f"[{n:3d}] {name}")
print()

# 按文件聚合（哪些文件假绿最多）
byfile = collections.Counter(r.split("|", 1)[0] for r in rows)
print("假绿最多的前 20 个文件：")
for f, n in byfile.most_common(20):
    print(f"  {n:2d}  {f}")
print()
print("明细（前 60 条）：")
for name, _ in cnt.most_common():
    for f, e in detail[name][:60]:
        print(f"  {os.path.basename(f)} :: {e}")
