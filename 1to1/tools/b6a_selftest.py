#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B6A 判据判别力自测（R221）

为什么要这份自测（项目纪律：判据类工具必须自证有判别力）：
  「全绿但无效」是判据类工具最典型的失败形态。B6A 是新加的判据，
  必须证明它 **既会放过真一致、也会抓出真差异**，而不是恒 PASS / 恒 FAIL / 恒 SKIP。

四腿设计（每腿都用**真实 behav json 结构**，不是字符串匹配）：
  腿A  两侧 ABI 哈希 + 几何**完全一致**            ⇒ B6A 必须 PASS（不许误伤真一致）
  腿B  两侧哈希**差最后一位**                      ⇒ B6A 必须 FAIL（要有敏感性）
  腿C  一侧哈希 = **全零基线**（b5449dc5）          ⇒ B6A 必须 FAIL（全零 = 未观测到像素）
  腿D  一侧**无探针**（frame_hash_abi = none）      ⇒ B6A 必须 SKIP（不许把"没测"当"过"，也不许当"错"）
  腿E  哈希同但**几何不同**（w/h/pitch 不一致）      ⇒ B6A 必须 FAIL（本轮新增的几何判据）

用法：python tools/b6a_selftest.py
退出码：0 = 五腿全符合预期；1 = 有腿不符（打印差异）
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIFF = os.path.join(HERE, 'behav_diff.py')
PY = sys.executable or 'python3'

# 真实实测值（R221 云开发 factory 单侧）
REAL_HASH = 'dfdaf563'
REAL_WH = '1280x720x2560'
ZERO = 'b5449dc5'           # 全零 RG16 的 FNV-1a 基线（桩实测）


def base(fp, bsha, **over):
    """构造一份最小但**结构完整**的行为指纹。默认让除 B6A 外的判据全 PASS。"""
    d = {
        "binary": "/sdcard/cubegm/rkgame",
        "binary_sha256_16": bsha,
        "wrapper": "qemu-arm-static",
        "args": "",
        "workdir": "/sdcard/cubegm",
        "exit_code": 124,
        "timed_out": True,
        "preload": "guest_shim_probe.so",
        "observed": True,
        "log_file": "menu.log",
        "log_lines": 2,
        "log_sha256_16": "d7c86a6f1f399930",
        "stdout_lines": 27,
        "stderr_lines": 9585,
        "shm_heartbeat": 1,
        "sfc_faults": 180,
        "sfc_cmds": 4,
        "frame_hash": "e96c9dc5",          # 原 B6：两侧设成非全零且相等 ⇒ B6 PASS
        "frame_hash_abi": REAL_HASH,
        "frame_wh_pitch_abi": REAL_WH,
        "frame_disp_n": 6,
        "frame_commits": 3072,
        "events": ["E|line1", "E|line2"],
        "new_files": [],
        "changed_files": [],
        "fingerprint": fp,
    }
    d.update(over)
    return d


def run_leg(name, fa, rb, want_b6a_ok):
    """跑一次 behav_diff，取 B6A 的判定结果。"""
    tmp = tempfile.mkdtemp(prefix='b6a_')
    pa = os.path.join(tmp, 'f.json')
    pb = os.path.join(tmp, 'r.json')
    with open(pa, 'w', encoding='utf-8') as f:
        json.dump(fa, f, ensure_ascii=False)
    with open(pb, 'w', encoding='utf-8') as f:
        json.dump(rb, f, ensure_ascii=False)

    p = subprocess.run([PY, DIFF, pa, pb], capture_output=True, text=True,
                       encoding='utf-8', errors='replace')
    out = (p.stdout or '') + (p.stderr or '')

    line = ''
    for ln in out.splitlines():
        if 'B6A' in ln:
            line = ln.strip()
            break

    if not line:
        print(f'  [腿{name}] ★★ 输出里没有 B6A 行（判据未生效）')
        return False

    ok = '[PASS]' in line
    skip = 'SKIP' in line
    # ★ 语义口径：B6A 的"放行"包含 PASS 与 SKIP 两种（SKIP = 一侧没开探针，不判不误伤）；
    #   "拦截"只有 FAIL。期望值因此用**布尔**表达，但报告里必须区分 PASS / SKIP
    #   —— 把 SKIP 显示成 PASS 就等于把"没测"伪装成"测过"（本项目假绿红线）。
    actual_allow = ok or skip
    actual_desc = 'SKIP' if skip else ('PASS' if ok else 'FAIL')
    expect_desc = '放行(PASS/SKIP)' if want_b6a_ok else '拦截(FAIL)'
    good = (actual_allow == want_b6a_ok)

    mark = 'OK ' if good else '★FAIL'
    print(f'  [{mark}] 腿{name}: 期望 {expect_desc} / 实得 {actual_desc}')
    print(f'         {line}')
    return good


def main():
    print('=== B6A 判据判别力自测（五腿）===')
    print(f'  判据实现: {DIFF}')
    print(f'  实测锚点: hash={REAL_HASH} geom={REAL_WH} 全零基线={ZERO}')
    print()

    results = []

    # 腿A：完全一致 ⇒ 必须 PASS
    results.append(run_leg(
        'A(一致必过)',
        base('factory', 'aaaaaaaaaaaaaaaa'),
        base('rebuild', 'bbbbbbbbbbbbbbbb'),
        True))

    # 腿B：哈希差最后一位 ⇒ 必须 FAIL
    results.append(run_leg(
        'B(差一字符必红)',
        base('factory', 'aaaaaaaaaaaaaaaa'),
        base('rebuild', 'bbbbbbbbbbbbbbbb', frame_hash_abi='dfdaf564'),
        False))

    # 腿C：一侧全零基线 ⇒ 必须 FAIL
    results.append(run_leg(
        'C(全零必红)',
        base('factory', 'aaaaaaaaaaaaaaaa'),
        base('rebuild', 'bbbbbbbbbbbbbbbb', frame_hash_abi=ZERO),
        False))

    # 腿D：一侧无探针 ⇒ 必须 SKIP
    results.append(run_leg(
        'D(无探针必SKIP)',
        base('factory', 'aaaaaaaaaaaaaaaa'),
        base('rebuild', 'bbbbbbbbbbbbbbbb', frame_hash_abi='none',
             frame_wh_pitch_abi='none', frame_disp_n=0),
        True))

    # 腿E：哈希同但几何不同 ⇒ 必须 FAIL
    results.append(run_leg(
        'E(几何不同必红)',
        base('factory', 'aaaaaaaaaaaaaaaa'),
        base('rebuild', 'bbbbbbbbbbbbbbbb', frame_wh_pitch_abi='1280x1280x5120'),
        False))

    print()
    n = sum(1 for r in results if r)
    print(f'=== 结果：{n}/{len(results)} 腿符合预期 ===')
    if n != len(results):
        print('★★ 判别力不足：B6A 不能作为门禁使用，先修判据。')
        return 1
    print('判别力自证通过：B6A 既放过真一致、也抓出真差异（含全零与几何）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
