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
M7 菜单存活      到达 M5（菜单入口）且**未被信号终止**：exit < 128
                （0=自行退出；124=GNU timeout 超时被杀 ⇒ **一直在跑**）；
                128+N = 被信号 N 杀死 ⇒ ✗（134=SIGABRT / 139=SIGSEGV / 137=SIGKILL 一律算"死"）
                ★ 口径修正（2026-09-19）：旧判据 `ex != 139` 只排除 SIGSEGV ⇒ 把 134(SIGABRT)
                  也判成"存活"⇒ 出过**假绿**。详见 side_marks() 内注释。
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
    # M7：**菜单存活** —— 语义 = 到达菜单入口(M5) 且 **未被信号终止**。
    # ★★ 口径修正（2026-09-19，实测驱动；旧判据产生过**假绿**）
    #   旧式：`ex not in (None, 139)` —— 只排除 SIGSEGV ⇒ **把 134(SIGABRT) 也判成"存活"**。
    #   实测后果：场景 `dv_x` 的 factory 侧其实死于 ALSA 断言（`pcm.c:3009 ... Assertion`，exit=134），
    #   却被判 `M7 ✓`；加了 ALSA 桩后它变成 139 ⇒ 判 ✗。表面看像"M7 在两侧之间来回交换"，
    #   实际是**判据太宽**、把"被 abort 打死"误当"活着"。
    #   新式：`ex < 128`（GNU timeout 语义 —— 命令自身退出 → 原样返回其退出码；
    #     超时被杀 → 124；被信号 N 杀死 → 128+N）⇒ 0 与 124 都算"活着"，134/139 等一律算"死"。
    #   ★ 误差方向：任何 `128+N` 都判 ✗（保守）；代价是"进程用 exit(200+) 自行退出"会被误判 ✗（罕见，可接受）。
    #   ★ `ex is None`（behav_*.json 缺失）判 ✗ —— "本该产出的产物缺席"必须显式失败，不得静默放行。
    ex = None
    try:
        import json
        j = json.load(open(os.path.join(scen_dir, "behav_%s.json" % label), encoding="utf-8"))
        ex = j.get("exit_code")
    except Exception:
        pass
    marks["M7"] = bool(marks["M5"]) and ex is not None and ex < 128
    if not marks["M5"]:
        detail["M7"] = "未到菜单入口"
    elif ex is None:
        detail["M7"] = "无终止码(仪器缺失)"
    elif marks["M7"]:
        detail["M7"] = "活着(exit=%d)" % ex
    else:
        detail["M7"] = "被信号终止(exit=%d)" % ex
    detail["MX"] = ("exit=%s" % ex) if ex is not None else "exit=?"
    if re.search(r"cannot find/open a drm device", err):
        detail["M4"] = "drm 打开失败(ENOSYS)"
    if re.search(r"open driver\.so fail", out):
        detail["M3"] = "加载失败"
    return marks, detail


def selftest():
    """★ 仪器自证（正负双向，锚点人工核对过）。

    为什么必须有它：M7 判据在 2026-09-19 出过**假绿** —— 旧式 `ex != 139` 把
    `exit=134`（SIGABRT，被 ALSA 断言打死）判成"菜单存活"。那次是**人工肉眼看出来**的。
    **仪器缺陷必须由锚点自证拦住，而不是靠人看。**
    """
    import json as _json
    import shutil
    import tempfile

    cases = [
        # (exit_code, 是否到达 M5, 期望 M7, 说明)
        (124,  True,  True,  "超时被杀 ⇒ 一直在跑 ⇒ 活着"),
        (0,    True,  True,  "自行正常退出 ⇒ 活着"),
        (1,    True,  True,  "自行以 1 退出 ⇒ 仍属未被信号终止"),
        (134,  True,  False, "SIGABRT(ALSA 断言) ⇒ ★ 旧判据正是在此假绿"),
        (139,  True,  False, "SIGSEGV ⇒ 死"),
        (137,  True,  False, "SIGKILL ⇒ 死"),
        (124,  False, False, "没到菜单入口 ⇒ 不算存活"),
        (None, True,  False, "behav json 缺失 ⇒ 仪器缺失必须显式失败"),
    ]
    print("=" * 78)
    print("milestones.py 仪器自证（M7 判据；锚点均由人工核对）")
    print("=" * 78)
    bad = 0
    for ex, m5, want, note in cases:
        d = tempfile.mkdtemp(prefix="cgm_ms_")
        lb = "factory"
        rd = os.path.join(d, "rundir_" + lb)
        os.makedirs(rd)
        with open(os.path.join(rd, "stdout.txt"), "w", encoding="utf-8") as f:
            f.write("root_path:/sdcard\n" if m5 else "nothing here\n")
        with open(os.path.join(d, "behav_%s.json" % lb), "w", encoding="utf-8") as f:
            _json.dump({"exit_code": ex}, f)
        marks, _detail = side_marks(d, lb)
        got = bool(marks.get("M7"))
        ok = (got == want)
        if not ok:
            bad += 1
        print("  %-6s exit=%-5s M5=%-5s → M7=%-5s (期望 %-5s)  %s"
              % ("✓" if ok else "★FAIL", ex, m5, got, want, note))
        shutil.rmtree(d, ignore_errors=True)
    print("-" * 78)
    print("  结论：%s" % ("★ 有锚点未通过 ⇒ 判据不可信，必须修" if bad else "全部锚点通过 ✓"))
    return 1 if bad else 0


def main():
    dirs = sys.argv[1:]
    if dirs and dirs[0] == "--selftest":
        return selftest()
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
                elif mid == "M7" and "M7" in detail:
                    # ★ M7 必须带出**判定依据**（exit 值）：否则 "M7 ✗" 无法区分
                    #   "被信号打死" 与 "压根没到菜单入口" —— 这是两个完全不同的结论。
                    cell = ("✓(%s)" if v else "✗(%s)") % detail["M7"]
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
