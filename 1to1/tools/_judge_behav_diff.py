# -*- coding: utf-8 -*-
"""R305 判据行四方对照：CNB 云开发复现 vs 前三轮 CI 基线

判据口径（对齐 workflow step 12 主门禁 = report/qemu 段）：
  · 只取「行为差分门禁」中 **report/qemu**（主门禁）那一段；
    排除同一日志里的 report/qemu_frames 段（那是帧探针 job，口径不同）。
    ★ 定位方式：用「参考端 report/qemu/behav_factory.json」这一行作段首，
      直到「behav_diff 退出码」行止 —— 不用命令回显做标记（易被后段覆盖）。
  · 判据行 = 段内 [PASS]/[FAIL]/[SKIP] 行 + `behav_diff 退出码 = N`
  · 时间戳（GitHub log 前缀 ISO8601Z）剥离、空白归一；**哈希保留原文**
    （要能直接看出 dfdaf563 / ffc51130 是否一致）
  · 另给「结构同形」判定（掩掉 hex/数字后比较），用于区分「结构变了」与「仅数值变了」

输出：四方逐行对照表 + 精确/同形双口径结论
"""
import os
import re
import sys

# ★ 归档进 tools/ 后，仓库根 = 本脚本目录的上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "report", "_r305_cnb")
BASES = [
    ("e5aef10e 轮", os.path.join(ROOT, "_qemu_behav_log_prev.txt")),
    ("288fa2d0 轮", os.path.join(ROOT, "_qemu_behav_log.txt")),
    ("ad13c99b 轮", os.path.join(ROOT, "_qemu_behav_log2.txt")),
    ("R305 CI(c4cacee)", os.path.join(OUT, "ci_run41553016828_joblog.txt")),
]
CUR = os.path.join(OUT, "behav_diff.txt")

TS = re.compile(r"^\d{4}-\d{2}-\d{2}T[\d:.]+Z\s*")
HEX = re.compile(r"\b[0-9a-f]{6,}\b")
NUM = re.compile(r"\d+")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def gate_rows(text):
    """抽出 report/qemu 主门禁段的判据行 + 三侧摘要行"""
    lines = [TS.sub("", l).strip() for l in text.splitlines()]
    start = None
    for i, l in enumerate(lines):
        if re.search(r"参考端\s+report/qemu/behav_factory\.json", l) and "qemu_frames" not in l:
            start = i
            break
    if start is None:
        return [], []
    seg = []
    for j in range(start, len(lines)):
        seg.append(lines[j])
        if "退出码" in lines[j]:
            break
    rows = [x for x in seg if re.search(r"\[(PASS|FAIL|SKIP)\]", x) or "退出码" in x]
    summary = [x for x in seg if re.search(r"(参考端|重建端|控制端)", x)]
    return [norm(x) for x in rows], [norm(x) for x in summary]


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def shape(s):
    """结构同形：hex 与数字统一掩码"""
    s = HEX.sub("<HEX>", s)
    s = NUM.sub("<N>", s)
    return s


def sig(rows, use_shape=False):
    return [shape(x) if use_shape else x for x in rows]


def main():
    data = {}
    for name, path in BASES:
        if os.path.exists(path):
            rows, summ = gate_rows(read(path))
            data[name] = (rows, summ)
        else:
            data[name] = (None, None)
    if not os.path.exists(CUR):
        print("!! 缺本轮 behav_diff.txt：%s" % CUR)
        sys.exit(2)
    rows, summ = gate_rows(read(CUR))
    data["R305 CNB 复现"] = (rows, summ)

    names = list(data.keys())
    print("=" * 108)
    print("R305 判据行四方对照（主门禁 report/qemu 段；哈希保留原文）")
    print("=" * 108)

    # 逐行对照：按「形状」聚类键
    keys = []
    for n in names:
        for r in data[n][0] or []:
            k = shape(r)
            if k not in keys:
                keys.append(k)
    for k in keys:
        print("\n◆ %s" % k)
        for n in names:
            rs = data[n][0]
            v = None
            if rs:
                for r in rs:
                    if shape(r) == k:
                        v = r
                        break
            print("   %-16s %s" % (n, v if v else "（无此行）"))

    print("\n" + "=" * 108)
    print("三侧摘要行（exit / stdout / 日志行数）")
    print("=" * 108)
    for n in names:
        print("\n[%s]" % n)
        for s in data[n][1] or []:
            print("   %s" % s)

    print("\n" + "=" * 108)
    print("判定")
    print("=" * 108)
    # 三方基线彼此精确一致？
    base_names = names[:-1]
    base_rows = [data[n][0] for n in base_names]
    have = [b for b in base_rows if b]
    base_exact_same = bool(have) and all(b == have[0] for b in have)
    base_shape_same = bool(have) and all(sig(b, True) == sig(have[0], True) for b in have)
    print("  %d 方 CI 基线：精确一致=%s  结构同形=%s" % (len(have), base_exact_same, base_shape_same))

    cur = data["R305 CNB 复现"][0]
    if not cur:
        print("  本轮判据行：空 ⇒ 复现仍不可判（INCONCLUSIVE）")
        return
    ref = have[0] if have else []
    # 「behav_diff 退出码 = N」由 **CI step 的 echo** 产生，不在 behav_diff.txt 载体里
    # ⇒ 载体差异，单独剔除后再比结构。
    ref_nc = [x for x in ref if "退出码" not in x]
    cur_nc = [x for x in cur if "退出码" not in x]
    if cur == ref:
        print("  本轮 vs CI 基线：**逐字一致** ⇒ 判据零变化")
    elif sig(cur_nc, True) == sig(ref_nc, True):
        print("  本轮 vs CI 基线：**判据结构同形**（剔除 CI step 额外 echo 的『退出码』载体行后）")
        print("  ⇒ 结构未变；以下为**仅数值/载体**层面的差异，逐条列出：")
    else:
        print("  本轮 vs CI 基线：**结构不同** ⇒ 需逐条分析")
    only_cur = [x for x in cur_nc if x not in ref_nc]
    only_ref = [x for x in ref_nc if x not in cur_nc]
    print("\n  本轮有而基线无（%d）:" % len(only_cur))
    for x in only_cur:
        print("    + %s" % x)
    print("  基线有而本轮无（%d）:" % len(only_ref))
    for x in only_ref:
        print("    - %s" % x)
    # 同形但数值不同的行（形如 B2 228/228 → 227/227）
    diff_rows = []
    for k in keys:
        if "退出码" in k:
            continue
        vals = {}
        for n in names:
            rs = data[n][0] or []
            for r in rs:
                if shape(r) == k:
                    vals[n] = r
                    break
        uniq = set(vals.values())
        if len(uniq) > 1:
            diff_rows.append((k, vals))
    if diff_rows:
        print("\n  同形但**数值不同**的判据行（%d）:" % len(diff_rows))
        for k, vals in diff_rows:
            print("    ◆ %s" % k)
            for n in names:
                print("        %-16s %s" % (n, vals.get(n, "（无此行）")))


if __name__ == "__main__":
    main()
