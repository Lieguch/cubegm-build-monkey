#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
milestones.py —— 用「功能里程碑」度量进度（替代会随环境非单调变动的覆盖率）

为什么要它（本轮教训）
======================
覆盖率（tools/qemu_coverage.py）会随**环境**变动而非单调：场景 C 补了 libkms 桩让
`driver.so` 加载成功，程序随即撞上"假 /dev/dri 无法应答 DRM ioctl"而**更早终止**
⇒ 覆盖率 48 → 6。**但那不是实现退步**：同一场景下 工厂 7 / 控制组 7 / 重建 6
（三者同步下降 ⇒ 环境属性）。若把覆盖率当进度尺，就会出现"越修越远"的错觉。

正确的刻度是**里程碑**：程序在**同一环境**下是否推进到了更靠后的功能点，以及
**两侧是否同时推进**（等价性是否保持）。本工具从 rundir 的 stdout/stderr 里
逐条判定里程碑，输出「场景 × 里程碑 × 两侧」矩阵。

里程碑定义（判据全部是可观测字面量，不靠推断）
==============================================
M0 进程启动      stdout 含 `rkgame v`
M1 配置读取      stdout 含 `appname:`
M2 SPI/SFC 初始化 stdout 含 `ROM Size:` 或 stderr 含 `sfc cmd op=`
M3 driver.so 加载 stdout 含 `open driver.so sucess`（厂商原文拼写）/ 失败则 `open driver.so fail`
M4 DRM 显示      stdout 含 `open drm!`；失败会伴随 stderr `cannot find/open a drm device`
M5 main_Menu 入口 stdout 含 `root_path:`
M6 UI 资源包打开  出现 `find <item> in <path>.zip fail`（说明**包打开了**、只是条目不在）⇒ 打开成功；
                 仅出现 `open <path>.zip fail` ⇒ 打开失败
M7 菜单存活      到达 M5 后仍无 SIGSEGV（exit != 139）且 menu.log 行数 > 0
MX 终止          exit_code（139 = SIGSEGV）

用法
====
  python3 tools/milestones.py <scenario_dir> [<scenario_dir> ...]
    scenario_dir 形如 report/qemu 或 report/qemu_c（内含 rundir_{factory,rebuild,control}/）
"""
import os
import re
import sys

MILESTONES = [
    ("M0", "进程启动", "stdout", r"rkgame v"),
    ("M1", "配置读取", "stdout", r"appname:"),
    ("M2", "SPI/SFC 初始化", "stdout|stderr", r"ROM Size:|sfc cmd op="),
    ("M3", "driver.so 加载", "stdout", r"open driver\.so sucess"),
    ("M4", "DRM 显示", "stdout", r"open drm!"),
    ("M5", "main_Menu 入口", "stdout", r"root_path:"),
]

LABELS = ("factory", "rebuild", "control")


def read(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        return ""


def side_marks(scen_dir, label):
    """返回 (marks dict, extra dict)。marks[m] = True/False；extra 记录细节。"""
    rd = os.path.join(scen_dir, "rundir_%s" % label)
    out = read(os.path.join(rd, "stdout.txt"))
    err = read(os.path.join(rd, "stderr.txt"))
    marks = {}
    detail = {}
    for mid, name, where, pat in MILESTONES:
        hay = out if where == "stdout" else (err if where == "stderr" else out + err)
        marks[mid] = re.search(pat, hay) is not None
    # M6：zip 打开成功 vs 失败
    opened = re.search(r"find .+? in .+?\.zip fail", out) is not None
    openfail = re.search(r"open .+?\.zip fail", out) is not None
    marks["M6"] = opened
    detail["M6"] = "包已打开(条目缺失)" if opened else ("打开失败" if openfail else "未走到")
    # M7：到达菜单入口且没被 SIGSEGV 打死
    ex = None
    try:
        import json
        j = json.load(open(os.path.join(scen_dir, "behav_%s.json" % label), encoding="utf-8"))
        ex = j.get("exit_code")
    except Exception:
        pass
    marks["M7"] = bool(marks["M5"]) and ex not in (None, 139)
    detail["MX"] = ("exit=%s" % ex) if ex is not None else "exit=?"
    if re.search(r"cannot find/open a drm device", err):
        detail["M4"] = "drm 打开失败(ENOSYS)"
    if re.search(r"open driver\.so fail", out):
        detail["M3"] = "加载失败"
    return marks, detail


def main():
    dirs = sys.argv[1:]
    if not dirs:
        print(__doc__)
        return 1
    order = ["M0", "M1", "M2", "M3", "M4", "M5", "M6", "M7"]
    names = {m[0]: m[1] for m in MILESTONES}
    names.update({"M6": "UI 资源包打开", "M7": "菜单存活"})
    print("=" * 78)
    print("功能里程碑矩阵（✓=到达  ✗=未到达  ·=未走到该分支）")
    print("=" * 78)
    for d in dirs:
        print("\n### %s" % d)
        header = "  %-6s %-16s" % ("ID", "里程碑")
        rows = {}
        for lb in LABELS:
            if not os.path.isdir(os.path.join(d, "rundir_%s" % lb)):
                continue
            marks, detail = side_marks(d, lb)
            rows[lb] = (marks, detail)
            header += " %-14s" % lb
        print(header)
        for mid in order:
            if mid not in names:
                continue
            line = "  %-6s %-16s" % (mid, names[mid])
            for lb in rows:
                marks, detail = rows[lb]
                v = marks.get(mid)
                cell = "✓" if v else "✗"
                if mid in ("M3", "M4", "M6") and not v and mid in detail:
                    cell = "✗(%s)" % detail[mid]
                elif mid == "M6" and v and "M6" in detail:
                    cell = "✓(%s)" % detail["M6"]
                line += " %-14s" % cell
            print(line)
        line = "  %-6s %-16s" % ("MX", "终止")
        for lb in rows:
            line += " %-14s" % rows[lb][1].get("MX", "?")
        print(line)
        # 两侧一致性小结（同场景下 factory 与 rebuild 的里程碑差集）
        if "factory" in rows and "rebuild" in rows:
            a = {m for m, v in rows["factory"][0].items() if v}
            b = {m for m, v in rows["rebuild"][0].items() if v}
            diff = (a - b) | (b - a)
            print("  → 两侧里程碑差集：%s" % (", ".join(sorted(diff)) if diff else "空（完全同步）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
