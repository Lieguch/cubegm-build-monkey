#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stage_sd_diag.py —— 生成「插卡即用」的 SD 投放目录（两步测试版）

产出
    _sdcard_drop/
      READ-ME-FIRST.txt              ← 给用户的全部步骤（自包含，两步测试）
      DEPLOY-MANIFEST.txt            ← sha256 / 体积 / 构建口径
      cubegm/
        rkgame                       ← 【第 1 步】诊断版（修复了 PT_LOAD 几何）
        rkgame.probe                 ← 【第 2 步备用】最小探针（3.5 KB，静态无 interp）
        _diag/
          cfg.ini
          _PUT-ONLY-THIS-FOLDER.txt

用法
    python tools/stage_sd_diag.py [--diag build/rkgame.diag] [--probe build/rkgame.probe]
                                  [--out _sdcard_drop] [--level 3]

★ 红线：本脚本**只生成我们自己的文件**，不触碰、不打包任何原厂文件。
   原厂 rkgame 的备份由用户在 SD 卡上手动完成（手册里有明确步骤）。
"""
import argparse
import hashlib
import io
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

README = """\
================================================================================
 CubeGM rkgame —— 设备诊断（**两步测试**版）
================================================================================

给你一句结论先：上一轮"无法开机 + 零日志"这件事，我在本地查到了**明确的结构性缺陷**
（见文末"背景"）。这一版的 rkgame 已经修掉它，体积也从 16.6 MB 降到 **5.4 MB**。
但它**还没在真机上验证过**，所以这一包设计成"两步"，用**最少的上机次数**把结论做实。

全部操作都在**电脑**上完成，设备只负责开机。

--------------------------------------------------------------------------------
【第 0 步】包里有什么
--------------------------------------------------------------------------------
  cubegm/rkgame          ← 【第 1 步用】诊断版（修复后）。覆盖到设备上的同名文件
  cubegm/rkgame.probe    ← 【第 2 步备用】最小探针，3.5 KB。**先不要动它**
  cubegm/_diag/cfg.ini   ← 日志级别（已设 level=3，最全）

--------------------------------------------------------------------------------
【第 1 步】备份原厂 rkgame ★★ 不可跳过 ★★
--------------------------------------------------------------------------------
  在 SD 卡的 cubegm/ 里：
    ① 复制一份 `rkgame`
    ② 把复制品改名为 `rkgame.factory.orig`
    ③ 再把 `rkgame.factory.orig` 复制到电脑上另一个文件夹（双保险）

  验证：cubegm/ 里应同时有
        rkgame                (原厂，待会儿要被覆盖)
        rkgame.factory.orig   (原厂备份，**别动它**)

  ⚠ 若这步没做而设备起不来，就要重新找原厂固件 —— 务必先做。

--------------------------------------------------------------------------------
【第 2 步】（第 1 步测试）部署诊断版并开机
--------------------------------------------------------------------------------
  ① 把本包 `cubegm/rkgame` 覆盖到 SD 卡的 `cubegm/rkgame`
  ② 把本包 `cubegm/rkgame.probe` 拷到 SD 卡的 `cubegm/rkgame.probe`（**保持这个文件名**）
  ③ 把本包 `cubegm/_diag/` 整个文件夹拷到 SD 卡的 `cubegm/_diag/`
     （若 SD 上已有 _diag，先删掉再拷，避免混入上一轮残留）
  ④ 插卡开机，**等满 90 秒**（黑屏也等满；崩溃现场在崩的那一刻就已经写进 SD）
  ⑤ 关机拔卡，看 `cubegm/_diag/` 里有没有东西

  ---- 结果 A：有日志（trace.log 里有 `## BOOT`）----
       ⇒ 结构性缺陷就是根因，且已修复。把整个 `_diag/` 取回来发我，**到此结束**。
         （要做第 3 步测试也可以，但没必要。）

  ---- 结果 B：**仍然一条日志都没有** ----
       ⇒ 继续做【第 3 步】。这一步能把"内核不肯 exec 我们的产物"和
         "跑了但写不出文件"这两件事**彻底分开**。

--------------------------------------------------------------------------------
【第 3 步】（第 2 步测试，只在结果 B 时做）最小探针
--------------------------------------------------------------------------------
  ① 把 SD 卡上的 `cubegm/rkgame` 改名成 `cubegm/rkgame.diag.bak`（留着，别删）
  ② 把 `cubegm/rkgame.probe` **改名成** `cubegm/rkgame`（它就成为被执行的程序）
  ③ 插卡开机，**等满 60 秒**，关机拔卡

  这个探针只有 3.5 KB、静态链接、**没有 .interp 也没有 NEEDED**（不依赖任何动态库），
  一进去就用原始系统调用往 7 个路径写文件、并尝试把屏幕涂白。看结果：

  ---- 结果 B1：`cubegm/_diag/PROBE.txt` 出现（或 PROBE.renamed.txt）----
       ⇒ 内核**能** exec 我们的产物，SD 也**可写**。
         那么诊断版失败在**它自己的加载**（动态库 / glibc 版本 / 5.4 MB 体积）上。
         请把 PROBE.txt 发我（里面记录了 7 个路径各自打开的结果）。

  ---- 结果 B2：7 个路径都没有、屏幕也没变 ----
       ⇒ 内核**根本没能 exec 我们工具链产出的 ELF**（与内容无关）。
         这条信息同样关键：说明必须先解决"工具链产物能否被这台设备加载"，
         而不是继续改代码。请把 `cubegm/` 的**文件名列表**截图给我（不是内容）。

  ---- 结果 B3：屏幕变成了白/花屏，但没有文件 ----
       ⇒ 代码跑了，是**文件系统写不进去**。那我们把日志改成走 framebuffer / 其它通道。

  做完任一步想回退：把 `rkgame` 删掉，把 `rkgame.factory.orig` 改名回 `rkgame`。

--------------------------------------------------------------------------------
【第 4 步】取回什么发我
--------------------------------------------------------------------------------
  第 2 步（结果 A）：整个 `cubegm/_diag/` 文件夹（或压 zip）。
  第 3 步（结果 B）：`_diag/PROBE.txt` + `_diag/cfg.ini`（看它尾巴有没有被追加一行）
                    + `cubegm/` 的文件名列表截图。

--------------------------------------------------------------------------------
【第 5 步】日志级别（可选）
--------------------------------------------------------------------------------
  用记事本打开 `cubegm/_diag/cfg.ini`：
        level = 3   # 最全（含每次 ioctl、malloc 明细、内容 hex）★ 已默认
        level = 2   # 文件 + ioctl + mmap + dlopen + 线程 + 时间
        level = 1   # 只留生命周期 / 文件 open-close / dlopen / 崩溃
        level = 0   # 只留崩溃报告

--------------------------------------------------------------------------------
【附一】日志里那些字段怎么读
--------------------------------------------------------------------------------
  E addr depth     函数进入（addr 是本产物地址，离线符号化用）
  X addr           函数退出
  IO  open "path" fl=0x2 ret=4        文件打开（ret<0 即失败）
  IO  ioctl fd=7 req=0x0000c008 ret=0 ★ DRM/KMS/ALSA/evdev 全走这里
  DL  dlopen "driver.so" ret=0x…      driver.so 是否加载成功
  DL  dlsym "…" -> 0x… / MISSING      driver.so 的哪些符号被解析、哪些缺失
  TH  pthread_create fn=…             线程
  TM  nanosleep 0.100000000           真睡（区别于忙等）
  SG  signal sig=11 handler=…         谁装了信号处理
  ##  SUMMARY …                       每 15 秒一次的计数汇总
  ##  EXIT / ABORT
  另见 crash.txt / frames.bin / frames.snap.bin / heartbeat.txt / BEGIN.txt / env.txt

  毫秒是 **CLOCK_MONOTONIC**（开机起算），不是墙上时间。

--------------------------------------------------------------------------------
【附二】背景：上一轮"零日志"是怎么来的（已修）
--------------------------------------------------------------------------------
  本地查证结果：产物的**程序头表是畸形的**。
  链接脚本把 `.data`/`.bss`/`.text` 钉死在 0x01000000 / 0x02000000 / 0x05000000，
  而带写属性的 `.fini_array` 在 `.rodata` 末尾（~0x4e00e0）。链接器把两者放进同一个
  RW 段，于是这个段的长度跨过了中间 **11.1 MB 的地址空洞**：

      · PT_LOAD 段数 2 → 9；文件 3.9 MB → **16.6 MB**（11 MB 是纯填充）
      · 最高虚拟地址 3.9 MB → **268 MB**（内核据此把 brk 也推到这里）
      · 这个 11 MB 段与承载**全部代码**的 `.text` 段**地址重叠**

  在 PC/qemu 上被容忍（所以 CI 一路全绿），在 2×Cortex-A7 的小内存盒子上
  很可能直接 exec 失败 —— **一条日志都不会产生**，与实测现象一致。
  修法 = 不再钉死那几个地址，让自有节连续排布（与工厂的 2 段形态一致）。
  同时补了一道**专门查这个的门禁**（PT_LOAD 几何：重叠 / 跨洞 / 最高地址 / 体积），
  原有的 14 道门禁只看"地址对不对"，没有一道看"段本身是否畸形"。

================================================================================
 有任何一步不确定，先停下问我，不要猜着做 —— 尤其是【第 1 步】的备份。
================================================================================
"""

CFG = """\
# cgm_diag 配置（放在 /sdcard/cubegm/_diag/cfg.ini）
# 本文件**读不到就用默认 level=2**；写错值也退回默认。
#   0 = 只留崩溃报告
#   1 = 生命周期 / 信号 / 文件 open-close / dlopen / 线程
#   2 = 1 + read/write/lseek 的偏移与长度 + ioctl 每次调用 + mmap   ← 默认
#   3 = 2 + 内容 hex + malloc/free 明细（最全，最慢）
level = {level}
"""


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--diag', default=os.path.join(ROOT, 'build', 'rkgame.diag'))
    ap.add_argument('--probe', default=os.path.join(ROOT, 'build', 'rkgame.probe'))
    ap.add_argument('--out', default=os.path.join(ROOT, '_sdcard_drop'))
    ap.add_argument('--level', type=int, default=3)
    a = ap.parse_args()

    for p, how in ((a.diag, 'sh tools/build_diag.sh'), (a.probe, 'sh tools/build_probe.sh')):
        if not os.path.exists(p):
            print('!! 找不到 %s\n   先跑： %s' % (p, how))
            return 2
    if a.level not in (0, 1, 2, 3):
        print('!! level 只能是 0..3')
        return 2

    out = a.out
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, 'cubegm', '_diag'))

    dst_bin = os.path.join(out, 'cubegm', 'rkgame')
    dst_prb = os.path.join(out, 'cubegm', 'rkgame.probe')
    shutil.copy2(a.diag, dst_bin)
    shutil.copy2(a.probe, dst_prb)
    with io.open(os.path.join(out, 'cubegm', '_diag', 'cfg.ini'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(CFG.format(level=a.level))
    with io.open(os.path.join(out, 'cubegm', '_diag', '_PUT-ONLY-THIS-FOLDER.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write('把本文件夹整个拷到 SD 卡的 /sdcard/cubegm/_diag/\n'
                '（不要把这个说明文件也放进设备，它无害但多余）\n')
    with io.open(os.path.join(out, 'READ-ME-FIRST.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write(README)

    man = ['CubeGM rkgame 诊断（两步测试版）—— 投放清单',
           '生成时间 : %s' % time.strftime('%Y-%m-%d %H:%M:%S'),
           '日志级别 : %d' % a.level,
           '',
           '%-32s %12s  %s' % ('文件', '字节', 'sha256')]
    for rel in ('cubegm/rkgame', 'cubegm/rkgame.probe', 'cubegm/_diag/cfg.ini', 'READ-ME-FIRST.txt'):
        p = os.path.join(out, rel.replace('/', os.sep))
        man.append('%-32s %12d  %s' % (rel, os.path.getsize(p), sha256(p)))
    man += ['',
            '★ rkgame      = 诊断版（PT_LOAD 几何已修；16.6 MB → 5.4 MB）',
            '★ rkgame.probe= 最小探针（3.5 KB，静态、无 interp、无 NEEDED）',
            '★ 本包**不含任何原厂文件**；原厂 rkgame 的备份请在 SD 卡上手动完成。']
    with io.open(os.path.join(out, 'DEPLOY-MANIFEST.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(man) + '\n')

    print('  ✓ 投放目录 → %s' % out)
    print('      cubegm/rkgame         %d B  (诊断版, level=%d)' % (os.path.getsize(dst_bin), a.level))
    print('      cubegm/rkgame.probe   %d B  (最小探针)' % os.path.getsize(dst_prb))
    print('      cubegm/_diag/cfg.ini  %d B' % os.path.getsize(os.path.join(out, 'cubegm', '_diag', 'cfg.ini')))
    print('      READ-ME-FIRST.txt     %d B' % os.path.getsize(os.path.join(out, 'READ-ME-FIRST.txt')))
    print()
    for ln in man[4:]:
        print('      %s' % ln)
    return 0


if __name__ == '__main__':
    sys.exit(main())
