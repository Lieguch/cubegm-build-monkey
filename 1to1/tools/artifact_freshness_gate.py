#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artifact_freshness_gate.py —— **产物新鲜度门禁**（R242 事故的直接产物）

## 为什么必须有它（真实事故，代价 = 十几轮错误结论）
2026-10-22（R242）实测：`build/obj/FUN_002b6c14_FBA_Load.o` 的 mtime 是 **09-30**，
而 `src/proprietary/core/FUN_002b6c14_FBA_Load.c`（含「sprintf 补第 4 参」修复）是 **10-13**。
`build/rkgame.rebuilt.elf` 是**用这批旧对象重新链接**出来的（10-18）。
后果：云上跑的重建产物 `sprintf(buf,"%s/cores/%s",work_path,*ppcVar4)` **只传 3 个参数**
（无 r3）⇒ glibc 打 `(null)` ⇒ `FBA_Load` 的 10 槽 core 遍历全废
⇒ 连续多轮围绕 `unsupport.` 的归因（R237–R241）**前提不成立**。

全仓普查：`src/proprietary` 214 个 `.c` 中 **23 个 `.o` 比源码旧**，含 T11/T12 的
`ReadJoystick` / `ReadUSBJoy` / `mui_menu` / `main_Menu` / `SeletEmuCore` 修复。

## 判据（fail-closed，三条全过才算 FRESH）
F1 `src/proprietary/**/*.c` 必须有对应 `build/obj/*.o`（缺 = FAIL）
F2 每个 `.o` 的 mtime **必须 ≥** 对应 `.c` 的 mtime（旧 = FAIL，打印差多少天）
F3 产物 ELF 的 mtime **必须 ≥** 全部 `.c` 与全部 `.o` 的最大 mtime（否则 = 链接用了旧对象）

## 为何用 mtime 而不是内容哈希
`.o` 不含源码副本，无法与 `.c` 做内容对拍；mtime 是**唯一廉价且可机械判定的证据**。
它的误报方向是「源码被 touch 但内容没变」⇒ 多编一次（便宜）；
漏报方向是「源码改了但 mtime 被人为回拨」⇒ 罕见且属人为规避，门禁不为其负责。

## 用法
  python tools/artifact_freshness_gate.py                     # 检查（rc=0 FRESH / 2 STALE / 11 前置缺失）
  python tools/artifact_freshness_gate.py --elf build/xxx.elf --obj build/obj --src src/proprietary
  python tools/artifact_freshness_gate.py --selftest          # 自证（构造 stale/fresh 两侧锚点）

## 自证设计（项目纪律：门禁必须先证明自己有判别力）
`--selftest` 在临时目录里造三组锚点，**双向**验证：
  · stale 锚：`.c` 比 `.o` 新 1 天  ⇒ 必须报 STALE
  · fresh 锚：`.o` 比 `.c` 新 1 天  ⇒ 必须报 FRESH
  · elf-stale 锚：ELF 比 `.o` 旧  ⇒ 必须报 STALE
任一向不符 ⇒ 自证失败（说明门禁本身没有判别力，不许投入使用）。
"""
import argparse
import os
import sys
import tempfile
import time

DEFAULT_SRC = os.path.join('src', 'proprietary')
DEFAULT_OBJ = os.path.join('build', 'obj')
DEFAULT_ELF = os.path.join('build', 'rkgame.rebuilt.elf')

DAY = 86400.0


def scan_pairs(src_dir, obj_dir):
    """返回 [(c_path, o_path or None)]。只收 <name>.c → <name>.o（同名扁平布局）。"""
    pairs = []
    for root, _dirs, files in os.walk(src_dir):
        for f in files:
            if not f.endswith('.c'):
                continue
            c = os.path.join(root, f)
            o = os.path.join(obj_dir, f[:-2] + '.o')
            pairs.append((c, o if os.path.exists(o) else None))
    pairs.sort()
    return pairs


def check(src_dir, obj_dir, elf):
    """返回 (verdict, details)。verdict ∈ FRESH / STALE / NOT-APPLICABLE。"""
    details = []
    if not os.path.isdir(src_dir):
        return None, [('MISSING-SRC', src_dir)]
    # ★ 语义区分（防假红）：
    #   `build/obj` **整个不存在** = 干净树（尚未构建）⇒ NOT-APPLICABLE（rc=3），不是缺陷；
    #   目录存在但**个别** .o 缺失/过期 = 确切的"产物不可信" ⇒ STALE（rc=2）。
    if not os.path.isdir(obj_dir):
        return 'NOT-APPLICABLE', [('NO-OBJ-DIR', obj_dir + '（干净树，尚未构建）')]
    if elf and not os.path.exists(elf):
        return 'NOT-APPLICABLE', [('NO-ELF', elf + '（产物尚未生成）')]

    pairs = scan_pairs(src_dir, obj_dir)
    missing = [(c, None) for c, o in pairs if o is None]
    stale = []
    for c, o in pairs:
        if o is None:
            continue
        dc, do = os.path.getmtime(c), os.path.getmtime(o)
        if do < dc:
            stale.append((c, o, (dc - do) / DAY))
    stale.sort(key=lambda x: -x[2])

    max_src = max((os.path.getmtime(c) for c, _ in pairs), default=0)
    max_obj = max((os.path.getmtime(o) for _, o in pairs if o), default=0)

    details.append(('COUNT-C', str(len(pairs))))
    details.append(('MISSING-OBJ', str(len(missing))))
    details.append(('STALE-OBJ', str(len(stale))))

    elf_stale = False
    if elf:
        me = os.path.getmtime(elf)
        newest = max(max_src, max_obj)
        if me < newest:
            elf_stale = True
            details.append(('STALE-ELF', '%.1f 天' % ((newest - me) / DAY)))

    for c, o, d in stale[:10]:
        details.append(('  stale', '%s  源码新 %.1f 天' % (os.path.basename(c), d)))
    for c, _ in missing[:10]:
        details.append(('  missing', os.path.basename(c)))

    verdict = 'FRESH' if not (missing or stale or elf_stale) else 'STALE'
    return verdict, details


def run_selftest():
    """双向锚点自证：stale 必须报 STALE，fresh 必须报 FRESH。"""
    ok = True
    with tempfile.TemporaryDirectory() as td:
        def build_case(name, c_age, o_age, elf_age):
            base = os.path.join(td, name)
            s = os.path.join(base, 'src')
            ob = os.path.join(base, 'obj')
            os.makedirs(s)
            os.makedirs(ob)
            now = time.time()
            c = os.path.join(s, 'A.c')
            o = os.path.join(ob, 'A.o')
            e = os.path.join(base, 'a.elf')
            open(c, 'w').write('x')
            open(o, 'w').write('x')
            open(e, 'w').write('x')
            os.utime(c, (now - c_age * DAY, now - c_age * DAY))
            os.utime(o, (now - o_age * DAY, now - o_age * DAY))
            os.utime(e, (now - elf_age * DAY, now - elf_age * DAY))
            return s, ob, e

        s, ob, e = build_case('stale', c_age=0, o_age=1, elf_age=0)
        v, _ = check(s, ob, e)
        print('  [self-test] stale 锚（.c 比 .o 新 1 天）⇒ %s  期望 STALE' % v)
        ok = ok and (v == 'STALE')

        s, ob, e = build_case('fresh', c_age=1, o_age=0, elf_age=0)
        v, _ = check(s, ob, e)
        print('  [self-test] fresh 锚（.o 比 .c 新 1 天）⇒ %s  期望 FRESH' % v)
        ok = ok and (v == 'FRESH')

        s, ob, e = build_case('elfstale', c_age=2, o_age=1, elf_age=5)
        v, _ = check(s, ob, e)
        print('  [self-test] elf-stale 锚（ELF 比 .o 旧）⇒ %s  期望 STALE' % v)
        ok = ok and (v == 'STALE')

    print('  SELF-TEST %s' % ('PASS（门禁有判别力）' if ok else '★FAIL（门禁无判别力，禁止使用）'))
    return 0 if ok else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--obj', default=DEFAULT_OBJ)
    ap.add_argument('--elf', default=DEFAULT_ELF)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        return run_selftest()

    verdict, details = check(a.src, a.obj, a.elf)
    if verdict is None:
        print('★★ 前置缺失（配置错），无法判定（fail-closed）')
        for k, v in details:
            print('  %-14s %s' % (k, v))
        return 11
    if verdict == 'NOT-APPLICABLE':
        print('  NOT-APPLICABLE（不适用，不计为失败）')
        for k, v in details:
            print('  %-14s %s' % (k, v))
        return 3
    for k, v in details:
        print('  %-14s %s' % (k, v))
    print()
    if verdict == 'FRESH':
        print('VERDICT: FRESH —— 产物由当前源码生成（%d 个 .c 全有 .o 且不老于源码，ELF 最新）' % len(scan_pairs(a.src, a.obj)))
        return 0
    print('VERDICT: STALE —— **产物不可信**：存在缺失/过期 .o 或 ELF 落后于源码。')
    print('  修法：rm -rf build/obj build/upstream && 重新构建（不许"有 .o 就跳过"）。')
    return 2


if __name__ == '__main__':
    sys.exit(main())
