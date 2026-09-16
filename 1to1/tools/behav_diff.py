#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""behav_diff.py — 行为差分门禁（P5 主门禁的比对端）

比对 behav_capture.sh 产出的两份行为指纹（原厂 vs 重建）。

判定维度：
  P0 前置：两侧 workdir 必须相同（否则比的是路径差异）；两侧二进制必须**不同**
  B0 非空洞：参考侧必须有可观测行为，否则 INCONCLUSIVE(3)
  B1 退出码一致            必须（若 --control 显示退出码本身不确定 ⇒ 降级为信息项）
  B2 语义事件序列一致      必须 —— ★ 但只判「参考实现自身可复现的**确定性前缀**」（见下）
  B3 新增文件路径一致      必须
  B4 变更文件路径一致      必须
  B5 menu.log 内容 sha 一致 两侧都有日志时必须（真机日志名 = menu.log）
  B6 帧缓冲采样哈希一致     若两侧均非 none 则必须
  B7 shm 心跳一致          若两侧均 >0 则必须
  B8 设备访问计数一致       若两侧均经过 SFC 设备仿真则必须（命令条数 + 寄存器访问次数）
     ★ 这一项能抓住「设备访存被编译器提升/合并/向量化」——该类差异在 stdout 事件里不可见
  B8 设备访问计数一致       若两侧均经过 SFC 设备仿真则必须（命令条数 + 寄存器访问次数）
     ★ 这一项能抓住「设备访存被编译器提升/合并/向量化」——该类差异在 stdout 事件里不可见

★ B0c 确定性控制（--control，强烈建议）：
  用**同一份参考二进制**跑第二遍，得到 control 指纹。取
      k = events(factory) 与 events(control) 的**最长公共前缀**
  含义：前 k 行是参考实现自身可复现的（可判定）部分；第 k+1 行起是参考实现**自己**都不稳定
  的部分（典型成因：假硬件下某次读失败 ⇒ 上层读到**未初始化的栈缓冲** ⇒ 打印垃圾值，
  而垃圾取决于两份二进制的栈布局 ⇒ 作为「实现差异」毫无意义）。
  ⇒ 于是 B2 只判 `rebuild[:k] == factory[:k]` 且 `len(rebuild) >= k`：
     **参考侧确定性到达过的地方，重建侧必须也到达且内容相同**；确定性前缀之后的长度差异不计为失败
     （但会在报告里单列，并标明"环境受限"）。
  没有 --control 时退化为旧的全量严格比较（并打印提示：建议加控制组）。
  对照组自身必须满足「同一二进制」（sha 相同），否则报 P0d FAIL。

退出码：0 = PASS；2 = FAIL；3 = INCONCLUSIVE（环境不足以驱动参考实现）

用法:
  behav_diff.py factory.json rebuild.json [--control control.json] [--detail]
"""
import json
import os
import sys
import difflib


def load(p):
    return json.load(open(p, encoding='utf-8'))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    pa, pb = sys.argv[1], sys.argv[2]
    a, b = load(pa), load(pb)
    detail = '--detail' in sys.argv

    # ---- 可选：确定性控制组（同一份参考二进制再跑一遍）----
    c = None
    pc = None
    if '--control' in sys.argv:
        i = sys.argv.index('--control')
        if i + 1 < len(sys.argv):
            pc = sys.argv[i + 1]
            c = load(pc)

    fails = []
    checks = []
    hard = []          # 前置硬条件（不满足直接 FAIL，不再谈行为）

    def chk(name, ok, note=''):
        checks.append((name, ok, note))
        if not ok:
            fails.append(name)

    la = int(a.get('log_lines', 0) or 0)
    ev_a = len(a.get('events', []))
    so_a = int(a.get('stdout_lines', 0) or 0)

    print('=' * 68)
    print('行为差分门禁  %s  vs  %s' % (a.get('label'), b.get('label')))
    print('=' * 68)
    print('  参考端 %s' % pa)
    print('     binary=%s  sha=%s' % (a.get('binary'), a.get('binary_sha256_16')))
    print('     workdir=%s  exit=%s  stdout=%s 行  log=%s/%s 行'
          % (a.get('workdir'), a.get('exit_code'), a.get('stdout_lines'),
             a.get('log_file'), a.get('log_lines')))
    print('  重建端 %s' % pb)
    print('     binary=%s  sha=%s' % (b.get('binary'), b.get('binary_sha256_16')))
    print('     workdir=%s  exit=%s  stdout=%s 行  log=%s/%s 行'
          % (b.get('workdir'), b.get('exit_code'), b.get('stdout_lines'),
             b.get('log_file'), b.get('log_lines')))
    if c is not None:
        print('  控制端 %s（同一份参考二进制复跑）' % pc)
        print('     binary=%s  sha=%s  exit=%s  events=%d 行'
              % (c.get('binary'), c.get('binary_sha256_16'), c.get('exit_code'),
                 len(c.get('events', []))))
    else:
        print('  控制端 （未提供 --control ⇒ 无法区分「实现差异」与「参考实现自身不确定」）')
    print('-' * 68)

    # ---- P0 前置条件 ----
    wa, wb = a.get('workdir'), b.get('workdir')
    if wa != wb:
        hard.append('P0a workdir 不一致：%s vs %s（差分比的是路径差异，不是代码差异）' % (wa, wb))
    sa, sb = a.get('binary_sha256_16'), b.get('binary_sha256_16')
    if sa and sb and sa == sb:
        hard.append('P0b 两侧二进制 sha 相同（%s）—— 等于拿同一份二进制自比，差分无意义' % sa)
    if os.path.abspath(pa) == os.path.abspath(pb):
        hard.append('P0c 两侧指纹文件是同一个路径')
    if c is not None:
        sc = c.get('binary_sha256_16')
        if sa and sc and sa != sc:
            hard.append('P0d 控制组二进制 sha（%s）与参考侧（%s）不同 —— 控制组必须是**同一份**参考二进制'
                        % (sc, sa))
        if os.path.abspath(pc) == os.path.abspath(pa):
            hard.append('P0e 控制组指纹文件与参考侧是同一个路径（等于没跑）')
    for h in hard:
        print('  [FAIL] %s' % h)
    if hard:
        print('-' * 68)
        print('  门禁结果: FAIL（%d 项前置条件不满足）' % len(hard))
        return 2

    # ---- B0 非空洞前置检查（★ 拒绝「两边都什么都没发生」的假通过）----
    # ★ 不能用 log_lines 判断：运行目录里**预置**了 menu.log，log_lines 恒 ≥1。
    # ★★ 也不能只看 observed：`observed` 把 **stderr** 也算进去，而 qemu 自身的
    #    `uncaught target signal 11` 就是一行 stderr —— 于是"两侧都在启动瞬间崩掉、
    #    一行业务输出都没有"会被判成 observed=True（实测踩到，且叠加确定性前缀后
    #    变成了**假 PASS**）。⇒ 这里要求**真正的行为**：stdout 有行，或产生了新增/变更文件。
    def real_obs(d):
        return (int(d.get('stdout_lines', 0) or 0) > 0
                or len(d.get('new_files', [])) > 0
                or len(d.get('changed_files', [])) > 0)

    if not real_obs(a):
        print('  [INCONCLUSIVE] B0 参考侧（工厂）**没有真正的行为观测**：')
        print('      stdout_lines=%s  新增文件=%s  变更文件=%s   （stderr_lines=%s 不计）'
              % (a.get('stdout_lines'), len(a.get('new_files', [])),
                 len(a.get('changed_files', [])), a.get('stderr_lines')))
        print('      stderr: %s' % (a.get('stderr_sha256_16') or '(未记录)'))
        print('  重建侧: stdout_lines=%s  新增文件=%s  变更文件=%s'
              % (b.get('stdout_lines'), len(b.get('new_files', [])),
                 len(b.get('changed_files', []))))
        print('  ⇒ 环境不足以驱动参考实现，本差分**无意义**（不是 PASS，也不是 FAIL）')
        print('     排查方向：① 目标二进制是否可执行（chmod +x）；② 是否被 guest shim 打死在启动处；')
        print('               ③ stdout 是否被全缓冲吃掉；④ work 目录资源是否就位。')
        return 3
    if 'observed' not in a:                  # 兼容旧指纹：只做提示
        print('  [note] 参考指纹缺 observed 字段（旧版本），已改用 stdout/新增/变更文件判定')

    # ---- B0c 确定性控制：求参考实现自身的**可复现前缀** ----
    ea, eb = a.get('events', []), b.get('events', [])
    det_prefix = None          # None = 无控制组（退化为全量严格比较）
    volatile = False
    ec = None
    exit_volatile = False
    if c is not None:
        ec = c.get('events', [])
        k = 0
        while k < len(ea) and k < len(ec) and ea[k] == ec[k]:
            k += 1
        det_prefix = k
        volatile = (k < len(ea)) or (k < len(ec))
        exit_volatile = (a.get('exit_code') != c.get('exit_code'))
        print('--- 确定性控制（同一份参考二进制跑两遍）---')
        print('  参考侧 %d 行 / 控制侧 %d 行；**可复现前缀 = %d 行**'
              % (len(ea), len(ec), det_prefix))
        if volatile:
            print('  ⚠ 参考实现自身从第 %d 行起不确定 ⇒ 该行之后**不可判定**（不计为失败）：' % (det_prefix + 1))
            if det_prefix < len(ea):
                print('      参考侧 #%d : %s' % (det_prefix + 1, ea[det_prefix][:150]))
            if det_prefix < len(ec):
                print('      控制侧 #%d : %s' % (det_prefix + 1, ec[det_prefix][:150]))
            print('   成因（本项目实测）：假硬件下某次读失败 ⇒ 上层打印**未初始化的栈缓冲**；')
            print('   垃圾值取决于两份二进制各自的栈布局 ⇒ 作为"实现差异"没有意义。')
        else:
            print('  ✓ 参考实现两遍完全一致（整段都可判定）')
        if exit_volatile:
            print('  ⚠ 退出码本身不确定（%s vs %s）⇒ B1 降级为信息项'
                  % (a.get('exit_code'), c.get('exit_code')))
        print('-' * 68)

    # ---- B1..B7 ----
    # ★ 可复现前缀必须包含**真正的 stdout 事件**：否则前缀会退化成「只有 qemu 自己的
    #   `uncaught target signal 11` 一行」——此时"两侧一致"毫无意义（实测：guest 被 shim
    #   打死在启动处，两侧 stdout 均为 0 行，前缀=1，门禁**假 PASS**）。
    if det_prefix is not None and not any(x.startswith('O|') for x in ea[:det_prefix]):
        print('  [INCONCLUSIVE] 可复现前缀（%d 行）里**不含任何 stdout 事件**：' % det_prefix)
        for x in ea[:det_prefix]:
            print('      %s' % x[:150])
        print('  ⇒ 前缀已退化为「guest 启动即崩」的噪声行，本差分**无意义**（不是 PASS）')
        print('     排查方向：① guest shim 是否把程序打死在启动处；② 目标二进制是否可执行；')
        print('               ③ 参考二进制是否根本没有产出（环境不足）。')
        return 3
    if exit_volatile:
        checks.append(('B1 exit_code', True, 'INFO（参考侧自身不确定：%s/%s；本次 %s vs %s）'
                       % (a.get('exit_code'), c.get('exit_code'),
                          a.get('exit_code'), b.get('exit_code'))))
    else:
        chk('B1 exit_code', a.get('exit_code') == b.get('exit_code'),
            '%s vs %s' % (a.get('exit_code'), b.get('exit_code')))

    if det_prefix is None:
        same_ev = ea == eb
        chk('B2 events', same_ev, '%d vs %d 行' % (len(ea), len(eb)))
        b2_note = ''
    else:
        # ★ 只判「参考侧确定性到达过的地方」：重建侧必须也到达且逐行相同。
        #   重建侧比确定性前缀更短 ⇒ 它在**可判定区间内**就更早崩了 ⇒ 真实失败。
        head_a, head_b = ea[:det_prefix], eb[:det_prefix]
        same_ev = (head_a == head_b) and (len(eb) >= det_prefix)
        note = '可判定前缀 %d/%d 行一致；重建侧共 %d 行' % (
            sum(1 for x, y in zip(head_a, head_b) if x == y), det_prefix, len(eb))
        if len(eb) < det_prefix:
            note += '  ★ 重建侧未到达参考侧的确定性前缀（可判定区间内提前终止）'
        elif volatile:
            note += '  （其后 %d 行参考侧自身不确定，不计为失败）' % (len(ea) - det_prefix)
        chk('B2 events', same_ev, note)
        b2_note = note

    fa = sorted(x.split('|')[0] for x in a.get('new_files', []))
    fb = sorted(x.split('|')[0] for x in b.get('new_files', []))
    chk('B3 new_files', fa == fb, '%d vs %d 个' % (len(fa), len(fb)))

    ga = sorted(x.split('|')[0] for x in a.get('changed_files', []))
    gb = sorted(x.split('|')[0] for x in b.get('changed_files', []))
    chk('B4 changed_files', ga == gb, '%d vs %d 个' % (len(ga), len(gb)))

    ha, hb = a.get('log_sha256_16'), b.get('log_sha256_16')
    if ha and hb and ha != 'none' and hb != 'none':
        chk('B5 log_sha', ha == hb, '%s(%s) vs %s(%s)'
            % (ha, a.get('log_file'), hb, b.get('log_file')))
    else:
        checks.append(('B5 log_sha', True, 'SKIP (一侧无日志文件)'))

    fha, fhb = a.get('frame_hash', 'none'), b.get('frame_hash', 'none')
    if fha != 'none' and fhb != 'none':
        chk('B6 frame_hash', fha == fhb, '%s vs %s' % (fha, fhb))
    else:
        checks.append(('B6 frame_hash', True, 'SKIP (一侧不可读)'))

    sma, smb = int(a.get('shm_heartbeat', 0)), int(b.get('shm_heartbeat', 0))
    if sma > 0 and smb > 0:
        chk('B7 shm', sma == smb, '%d vs %d' % (sma, smb))
    else:
        checks.append(('B7 shm', True, 'SKIP (一侧无 shm)'))

    # ---- B8 设备访问计数：同一份假设备，两侧访问它的次数必须一致 ----
    # 来历（P5 第四个真实分歧）：重建侧把 `*dst++ = reg[0x108]` 的设备读
    #   提升出循环并向量化（一次读、4 字广播）⇒ 设备访问次数 180 → 57。
    #   这一差异**在 stdout 事件里不可见**（前 17 行逐字相等），
    #   只在后续校验和失败导致分支不同时才暴露 —— 若早有这样一条计数门禁，可立刻定位。
    #   ⇒ 既然两侧跑的是**同一份** shim（同一份假设备），访问次数就应当逐值相等；
    #     不等即说明"设备交互的轨迹形状"与工厂不同，属真实保真度缺口。
    cfa, cfb = int(a.get('sfc_cmds', 0) or 0), int(b.get('sfc_cmds', 0) or 0)
    ffa, ffb = int(a.get('sfc_faults', 0) or 0), int(b.get('sfc_faults', 0) or 0)
    if cfa > 0 and cfb > 0:
        chk('B8a sfc_cmds', cfa == cfb, '%d vs %d 条命令' % (cfa, cfb))
        chk('B8b sfc_faults', ffa == ffb, '%d vs %d 次寄存器访问' % (ffa, ffb))
        if ffa != ffb:
            print('        ★ 两侧访问次数不等 ⇒ 有设备访存被编译器**提升出循环 / 合并 / 向量化**，'
                  '或循环结构不同；')
            print('          常见形态：`*dst++ = reg[DATA]` 被优化成「读一次 + vdup/vst1 广播」；'
                  '修法：把该访存限定为 `volatile`（一次 C 访问 = 一次设备访问）。')
    else:
        checks.append(('B8 sfc_devaccess', True, 'SKIP (一侧未经过 SFC 设备仿真)'))

    for n, ok, note in checks:
        print('  [%s] %-18s %s' % ('PASS' if ok else 'FAIL', n, note))
    print('-' * 68)
    print('  门禁结果: %s (%d 项失败)' % ('PASS' if not fails else 'FAIL', len(fails)))

    if not same_ev and detail:
        print('\n--- 语义事件差异（factory → rebuild）---')
        lim = det_prefix if det_prefix is not None else len(ea)
        for ln in list(difflib.unified_diff(ea[:lim], eb[:lim], 'factory', 'rebuild',
                                           lineterm=''))[:120]:
            print('  ' + ln)
        if det_prefix is not None and len(ea) > det_prefix:
            print('\n--- 参考侧不确定的尾部（不计为失败，仅供人工核对）---')
            for i, x in enumerate(ea[det_prefix:det_prefix + 6], start=det_prefix + 1):
                print('  参考 #%d : %s' % (i, x[:150]))
            for i, x in enumerate(eb[det_prefix:det_prefix + 6], start=det_prefix + 1):
                print('  重建 #%d : %s' % (i, x[:150]))
    if c is None:
        print('\n提示: 未提供 --control。无法区分「实现差异」与「参考实现自身不确定」，'
              '建议在 harness 里跑一遍同一份参考二进制作为控制组。')
    if fa != fb and detail:
        print('\n--- 新增文件差异 ---')
        print('  仅原厂:', sorted(set(fa) - set(fb))[:10])
        print('  仅重建:', sorted(set(fb) - set(fa))[:10])
    if ga != gb and detail:
        print('\n--- 变更文件差异 ---')
        print('  仅原厂:', sorted(set(ga) - set(gb))[:10])
        print('  仅重建:', sorted(set(gb) - set(ga))[:10])

    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
