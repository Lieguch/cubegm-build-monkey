#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「第 7 轮真机投放」目录 _sdcard_drop7/。

为什么要有第 7 轮（**欠账说明，不许含糊**）：
  drop6 是 2026-09-23 13:27 做的，之后**从未上机**。而 09-23 到现在，产物已经变了很多次：
    · PT_LOAD 几何畸形修复（drop6 已含）
    · MMIO 访存宽度窄化修复：`sfc_init` 的 `ldrh` → `ldr`（drop6 的 t3 就是这个的验证件）
    · mini-XML 3.x → **2.9**（工厂夹逼取证；DIVERGE 75→57）
    · GNU libiconv 1.17 → **1.16**，并把该 TU 编成 **-O0**（工厂形态取证；DIVERGE 57→46）
    · libcharset 配置宏 `HAVE_LANGINFO_CODESET`（工厂导入表取证：走 nl_langinfo 而非 getenv）
  ⇒ drop6 里的候选**全是旧产物**。本轮把当前产物重新投放。

本轮唯一要回答的问题（判决先写死，避免事后凑结论）：
  **t3（当前交付版）在真机上还崩不崩？**
    · 若"存活至超时"              ⇒ **根因修复成立**，进入五项验收（19088 游戏 / 中文 UI / 全菜单 / 存档 / BGM）
    · 若崩在**新的** PC（≠ sfc_init 邻域）⇒ 宽度修复生效，进入下一个故障点（探针会给出 PC/LR/SP/栈回溯）
    · 若仍崩在 sfc_init+0x6c       ⇒ 修复没生效 ⇒ 先核对设备上文件的 sha256 与本清单是否一致

探针 v5（src/probe/probe5.c）里**候选表是硬编的**，本包按它的表项填文件，不改探针：
    rkgame.bak  阳性对照（原厂，必须已在卡上，必须存活）
    rkgame.t1   = build/_prewidth.rebuilt.elf  【修复前对照】预期 SIGBUS
    rkgame.t3   = build/rkgame.rebuilt.elf     ★ 本轮候选

用法: PY=<python> python3 tools/stage_sd_round7.py [输出目录]
"""
import hashlib
import io
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop7')

ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe5'),          'cubegm/rkgame'),
    (os.path.join(ROOT, 'build', '_prewidth.rebuilt.elf'),  'cubegm/rkgame.t1'),
    (os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'),     'cubegm/rkgame.t3'),
]

CFG_INI = """# cgm_diag config.  The real setting is the first non-comment line below.
level = 3
#   0 = crash report only
#   1 = lifecycle / signals / file open-close / dlopen / threads
#   2 = 1 + read/write/lseek offsets + every ioctl + mmap  (built-in default)
#   3 = 2 + content hex + malloc-free detail (slowest)
"""

PUT_ONLY = """把本目录整体拷到 SD 卡的 cubegm/_diag/。
探针 v5 会把结论写进 PROBE5.txt；_diag/ 必须存在且可写。
cfg.ini 里第一行真设置是 level = 3。
"""

README_TMPL = """ 真机测试 第 7 轮 —— 交付版产物验证（取代 drop6）
=================================================================
生成时间: {gen}

【为什么又投一轮（先说清欠账）】

  drop6 是 09-23 13:27 做的，之后**从未上机**；而 09-23 之后产物又改了几次
  （mini-XML 3.x→2.9、libiconv 1.17→1.16 且改 -O0、libcharset 配置宏对齐）。
  ⇒ drop6 里的候选**全是旧产物**。本包换成当前产物，其余结构不变。

【你要做的 4 步】

  1) 确认 SD 卡上 cubegm/rkgame.bak 存在（= 原厂备份，应为 3,921,108 字节）。
     ★ 它是"阳性对照"。若不存在，请先把原厂 rkgame 复制成 rkgame.bak 再继续。

  2) 把本包 cubegm/ 里这 4 个东西拷到 SD 卡：
        rkgame           (~12 KB)      ← 探针 v5，**必须覆盖**
        rkgame.t1        ({t1_size})   ← A线【修复前对照】预期 SIGBUS
        rkgame.t3        ({t3_size})   ← ★ 本轮候选（当前交付版）
        _diag/           整个目录（合并覆盖，cfg.ini 一定要覆盖）

  3) 插卡开机，**等满 90 秒**（3 个候选 + 开销）。

  4) 关机拔卡，把 cubegm/_diag/PROBE5.txt 发我（以及同目录下本轮新出现的
     p5_*.txt / ldd_* / T4-OK.txt，若有）。

【回退到原厂（随时可做）】

  把 cubegm/rkgame.bak 复制一份改名成 cubegm/rkgame 即可。

【本轮判断标准（★ 先写死，避免事后凑结论）】

  · 阳性对照 rkgame.bak 必须仍"存活至超时"。否则整轮作废，先修探针。
  · t1（修复前）预期仍是 SIGBUS —— 若 t1 **不再崩**，说明自变量没生效，先核 sha256。
  · **t3（本轮关键）三种可能，各有明确含义：**
      (a) 存活至超时        ⇒ ★ 启动链上的根因修复成立 ⇒ 进入五项验收
      (b) 崩在**别的** PC    ⇒ 宽度修复生效，进入下一个故障点
                              （探针 v5 会给出 PC/LR/SP + PC 处指令字节 + 栈回溯候选）
      (c) 仍崩在 sfc_init 附近 ⇒ 修复没生效 ⇒ 先比对本清单里 t3 的 sha256
                                与设备上的文件是否一致（不一致 = 拷错了）

【本包文件的 sha256（投放前请核对，尤其 t3）】

  cubegm/rkgame.t3  {t3_size} 字节
    {t3_sha}
  cubegm/rkgame.t1  {t1_size} 字节
    {t1_sha}

【诚实声明（没有验证的）】

  · 宽度修复与"上游版本对齐"已在本轮交付版里；但**本交付版尚未在真机上跑过**。
{ruler}
  · ★ 本轮修掉两个**真缺陷**（由新增的体量覆盖门禁抓到，行为尺看不见它们）：
      · `UpdateROM`（写固件）体量 112 B → 680 B（工厂 976 B）
      · `ReadUSBJoy`（USB 手柄）体量 520 B → 1072 B（工厂 1196 B）
    两者的成因相同：Ghidra 把一块缓冲拆成多个小对象 ⇒ 读未初始化/写越界 = **UB**
    ⇒ 优化器把整段实现删掉。现已修复，且产物里 `reboot`/`sync` 已与工厂一致地导入。
  · 沙箱侧已能复现真机的 MMIO 总线约束：修复前产物在严格模式下会报
    `MMIO-STRICT VIOLATION off=0x2c w=2 pc=0x00501b84`（= 真机 SIGBUS @ sfc_init+0x6c），
    当前产物 0 违反。
=================================================================
"""


RULER_RE_N = re.compile(r'共有函数\s+(\d+)')
RULER_RE_S = re.compile(r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)\s*｜\s*TRUNC[^0-9]*(\d+)\s*｜\s*SKIP\s+(\d+)')


def ruler_stats(path):
    """→ (正文行, 明细行)。**解析不到就抛错**（fail-closed：不出带假数字的包）。"""
    if not os.path.isfile(path):
        raise SystemExit('★★ 行为尺报告不存在：%s（先跑 tools/diff_exec.py --batch）' % path)
    t = io.open(path, encoding='utf-8', errors='replace').read()
    m1 = RULER_RE_N.search(t)
    m2 = RULER_RE_S.search(t)
    if not (m1 and m2):
        raise SystemExit('★★ 行为尺报告解析失败（格式变了？）：%s' % path)
    tot = int(m1.group(1))
    pa, dv, tr, sk = (int(m2.group(1)), int(m2.group(2)), int(m2.group(3)), int(m2.group(4)))
    assert pa + dv + tr + sk == tot, '自洽校验失败：%d+%d+%d+%d != %d' % (pa, dv, tr, sk, tot)
    return ('  · 行为尺当前（读自 %s）：PASS %d ｜ DIVERGE %d ｜ TRUNC %d ｜ SKIP %d（共 %d，自洽 ✓）。'
            '\n    **DIVERGE 不为 0**，剩余明细见该报告。' % (os.path.basename(path), pa, dv, tr, sk, tot),
            'PASS %d / DIVERGE %d / TRUNC %d / SKIP %d（共 %d）' % (pa, dv, tr, sk, tot))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    missing = [s for s, _ in ITEMS if not os.path.isfile(s)]
    if missing:
        print('!! 缺文件，拒绝投放：')
        for m in missing:
            print('   ', m)
        return 2
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    # ★★ 2026-09-28 加：**fail-closed** —— 目录删不掉时必须中止。
    #   实测踩到：沙箱的 safe-delete 守卫让 `rmtree` 静默失败，脚本却继续往下写
    #   ⇒ 产出**缺 READ-ME-FIRST.txt 的半成品包**（正是"交半成品"这类事故）。
    if os.path.isdir(OUT):
        raise SystemExit('★★ 无法清空旧投放目录 %s（rmtree 被拦？）—— 中止，禁止产出半成品包' % OUT)
    os.makedirs(os.path.join(OUT, 'cubegm', '_diag'))
    rows = []
    for src, rel in ITEMS:
        dst = os.path.join(OUT, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        rows.append((rel, os.path.getsize(dst), sha256(dst)))
    with io.open(os.path.join(OUT, 'cubegm', '_diag', 'cfg.ini'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(CFG_INI)
    pf = 'cubegm/_diag/_PUT-ONLY-THIS-FOLDER.txt'
    with io.open(os.path.join(OUT, pf), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(PUT_ONLY)
    rows.append((pf, len(PUT_ONLY.encode()), sha256(os.path.join(OUT, pf))))
    # 探针会写出的产物（不随包投放，但要有位置）
    os.makedirs(os.path.join(OUT, 'cubegm', '_diag'), exist_ok=True)

    import datetime
    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = ['# DEPLOY-MANIFEST — 第 7 轮投放包', '',
             '生成时间: %s' % stamp, '',
             '| 目标路径 | 字节 | sha256 |', '|---|---|---|']
    for rel, size, h in rows:
        lines.append('| `%s` | %d | `%s` |' % (rel, size, h))
    lines += ['', '## 阳性对照（不在本包内，必须在设备上已存在）',
              '- `cubegm/rkgame.bak` —— 原厂 rkgame，**3,921,108 B**',
              '  探针会先 execve 它。**它必须成功**，否则其余结论一概不可信。', '',
              '## 与 drop6 的差别（自查用）',
              '- `cubegm/rkgame.t3` = 当前产物（含 mxml 2.9 / libiconv 1.16 @ -O0 / libcharset 配置对齐）',
              '- `cubegm/rkgame.t1` = 修复前对照（未变）',
              '- 探针 = probe5（drop6 用的是 probe4）']
    with io.open(os.path.join(OUT, 'DEPLOY-MANIFEST.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')

    t3 = [r for r in rows if r[0].endswith('rkgame.t3')][0]
    t1 = [r for r in rows if r[0].endswith('rkgame.t1')][0]
    ruler_line, _ = ruler_stats('report/_deliver_diff.txt')
    readme = README_TMPL.format(
        gen=stamp, t3_size=t3[1], t3_sha=t3[2], t1_size=t1[1], t1_sha=t1[2],
        ruler=ruler_line)
    with io.open(os.path.join(OUT, 'READ-ME-FIRST.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(readme)

    print('投放目录: %s' % OUT)
    for rel, size, h in rows:
        print('  %-34s %10d  %s' % (rel, size, h[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
