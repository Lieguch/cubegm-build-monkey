#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stage_sd_diag.py —— 生成「插卡即用」的 SD 投放目录

产出
    _sdcard_drop/
      READ-ME-FIRST.txt               ← 给用户的全部步骤（自包含，拷到哪都看得懂）
      DEPLOY-MANIFEST.txt             ← sha256 / 体积 / 构建口径（留痕，便于回溯）
      cubegm/
        rkgame                        ← **诊断版**（覆盖设备上的同名文件）
        _diag/
          cfg.ini                     ← 日志级别（1/2/3）
          _PUT-ONLY-THIS-FOLDER.txt

用法
    python tools/stage_sd_diag.py [--diag build/rkgame.diag] [--out _sdcard_drop] [--level 2]

★ 红线遵守：本脚本**只生成我们自己的文件**，不触碰、不打包任何原厂文件。
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
 CubeGM rkgame —— 设备诊断版 部署说明（**设备没有命令行，全部在电脑上完成**）
================================================================================

你手上这份是从 SD 卡里取的；下面每一步都在**电脑**上操作，设备只负责开机跑。

--------------------------------------------------------------------------------
【第 0 步】确认你要的文件都在
--------------------------------------------------------------------------------
  cubegm/rkgame           ← 我们的「诊断版 rkgame」（要覆盖到设备上）
  cubegm/_diag/cfg.ini    ← 日志级别（默认 level=2，最全用 3）

--------------------------------------------------------------------------------
【第 1 步】把 SD 卡插到电脑
--------------------------------------------------------------------------------
  打开 SD 卡根目录，确认有 `cubegm/` 这个文件夹（设备上它挂载成 /sdcard/cubegm）。
  ★ 若看不到 cubegm/，说明插的是另一张卡，停下来说一声。

--------------------------------------------------------------------------------
【第 2 步】先备份原厂 rkgame ★★ 不可跳过 ★★
--------------------------------------------------------------------------------
  在 SD 卡的 cubegm/ 里：
    ① 复制一份 `rkgame`
    ② 把复制品改名为 `rkgame.factory.orig`
    ③ 再把 `rkgame.factory.orig` 复制到电脑上另一个文件夹（双保险）

  验证：cubegm/ 里现在应同时有
        rkgame                (原厂，待会儿要被覆盖)
        rkgame.factory.orig   (原厂的备份，**别动它**)

  ⚠ 若这一步没做而设备起不来，就要重新找原厂固件 —— 所以务必先做。

--------------------------------------------------------------------------------
【第 3 步】覆盖 rkgame + 放入诊断目录
--------------------------------------------------------------------------------
  ① 把本包 `cubegm/rkgame` 覆盖到 SD 卡的 `cubegm/rkgame`
     （覆盖前它会和 rkgame.factory.orig 是同名不同内容 —— 正常）
  ② 把本包 `cubegm/_diag/` **整个文件夹**拷到 SD 卡的 `cubegm/_diag/`
     （如果 SD 上已存在 _diag，先删掉它再拷，避免混入上一轮日志）

  最终 SD 上应该是：
        cubegm/rkgame                    ← 我们的诊断版
        cubegm/rkgame.factory.orig       ← 原厂备份（不动）
        cubegm/_diag/cfg.ini             ← 本次日志级别
        cubegm/ 其余文件原样不动
        （000 ~ 008 / root.dat 等**全部不要动**）

--------------------------------------------------------------------------------
【第 4 步】安全弹出 SD 卡 → 插进设备 → 开机
--------------------------------------------------------------------------------
  · 插卡，开机。
  · **等 90 秒**（诊断版每 5 秒写一次快照，给它时间）。
  · 然后关机、拔卡。
    - 如果开机后屏幕一直黑/一直停在某处，**也要等满 90 秒再断电** ——
      诊断版在崩的那一刻就会把崩溃现场写进 SD，黑屏不代表没日志。

--------------------------------------------------------------------------------
【第 5 步】把日志取回来
--------------------------------------------------------------------------------
  把 SD 卡插回电脑，**整个 `cubegm/_diag/` 文件夹**复制出来（或压成 zip）发我。

  应该看到这些文件（有几个算几个，缺失本身也是信息）：
    BEGIN.txt          本次运行横幅（含时钟、级别、阳性对照说明）
    env.txt            环境快照（environ / cmdline / maps / auxv / meminfo …）
    maps.start.txt     启动时的内存映射（离线把地址变符号名，必需）
    trace.log          ★ 主事件流（生命周期 / 文件 / ioctl / dlopen / 线程 / 信号）
    frames.bin         函数级轨迹（崩溃或退出时全量 dump）
    frames.snap.bin    ★ 每 5 秒一次快照（**卡死/断电也能拿到最近历史**）
    crash.txt          崩溃报告（信号 / 全部寄存器 / 回溯 / 栈扫描 / maps）
    heartbeat.txt      心跳（区分「卡死」与「崩溃」；含调用计数）
    summary.txt        （周期汇总写在 trace.log 里，形如 `## SUMMARY …`）
    cfg.ini            本次生效的配置

  ★★ 判断日志是否"有效"的三条 ★★
   1) BEGIN.txt 里应有 `### CGM-DIAG BEGIN` —— 有它说明诊断版真的跑起来了。
   2) trace.log 里应有 `## BOOT enter argc=` —— 有它说明进到了 main 之前的钩子。
   3) 若 trace.log **是空文件**：说明诊断版**根本没被执行**（不是"没触发"）
      ⇒ 那问题在启动层（替换没生效 / 文件系统只读 / icube 没 exec 它），
        请把 `cubegm/` 的目录清单（不是内容）截图发我。

--------------------------------------------------------------------------------
【第 6 步】如果想调"更全"或"更省"
--------------------------------------------------------------------------------
  用电脑上的记事本打开 `cubegm/_diag/cfg.ini`，改成：
        level = 3      # 最全（含 ioctl 每次调用、malloc/free 明细、内容 hex）★ 最慢
        level = 2      # 默认：文件 + ioctl + mmap + dlopen + 线程 + 时间
        level = 1      # 只留：生命周期 / 文件 open-close / dlopen / 崩溃
        level = 0      # 只留崩溃报告
  ★ 覆盖最全 = 3。若设备本来就卡，先用 3 跑一次；跑不动再降到 2。

--------------------------------------------------------------------------------
【第 7 步】怎么回退
--------------------------------------------------------------------------------
  把 SD 卡的 `cubegm/rkgame` 删掉，把 `rkgame.factory.orig` 改名回 `rkgame` 即可。
  （这就是第 2 步备份的意义；`_diag/` 留着不影响运行。）

--------------------------------------------------------------------------------
【附】日志里那些字段怎么读
--------------------------------------------------------------------------------
  E addr depth     函数进入（addr 是本产物里的地址，离线符号化用）
  X addr           函数退出
  IO  open "path" fl=0x2 ret=4      文件打开（ret<0 就是失败）
  IO  ioctl fd=7 req=0x0000c008 ret=0   ★ DRM/KMS/ALSA/evdev 全走这里
  IO  mmap len=… ret=0x…            显存/帧缓冲映射
  DL  dlopen "driver.so" ret=0x…    driver.so 是否加载成功
  DL  dlsym "…" -> 0x… / MISSING    driver.so 的哪些符号被解析、哪些缺失
  TH  pthread_create fn=…           线程
  TM  nanosleep 0.100000000         真睡（区别于忙等）
  SG  signal sig=11 handler=…       谁装了信号处理
  ##  SUMMARY …                     每 15 秒一次的计数汇总
  ##  EXIT / ABORT                 正常/异常退出
  (crash.txt)                      崩溃现场

  时区说明：毫秒是 **CLOCK_MONOTONIC**（开机起算），不是墙上时间。
  BEGIN.txt 里有 pid 与 build 时间，可用来对齐多次运行。

================================================================================
 有任何一步不确定，先停下问我，不要猜着做 —— 尤其是第 2 步的备份。
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
    ap.add_argument('--out', default=os.path.join(ROOT, '_sdcard_drop'))
    ap.add_argument('--level', type=int, default=2)
    a = ap.parse_args()

    if not os.path.exists(a.diag):
        print('!! 找不到诊断产物 %s\n   先跑： CC="<zig> cc" sh tools/build_diag.sh' % a.diag)
        return 2
    if a.level not in (0, 1, 2, 3):
        print('!! level 只能是 0..3'); return 2

    out = a.out
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(os.path.join(out, 'cubegm', '_diag'))

    dst_bin = os.path.join(out, 'cubegm', 'rkgame')
    shutil.copy2(a.diag, dst_bin)
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

    man = []
    man.append('CubeGM rkgame 诊断版 —— 投放清单')
    man.append('生成时间 : %s' % time.strftime('%Y-%m-%d %H:%M:%S'))
    man.append('日志级别 : %d' % a.level)
    man.append('')
    man.append('%-34s %12s  %s' % ('文件', '字节', 'sha256'))
    for rel in ('cubegm/rkgame', 'cubegm/_diag/cfg.ini', 'READ-ME-FIRST.txt'):
        p = os.path.join(out, rel.replace('/', os.sep))
        man.append('%-34s %12d  %s' % (rel, os.path.getsize(p), sha256(p)))
    man.append('')
    man.append('★ 交付版（非诊断）产物在 build/rkgame.rebuilt.elf，本包不含它。')
    man.append('★ 本包**不含任何原厂文件**；原厂 rkgame 的备份请在 SD 卡上手动完成。')
    with io.open(os.path.join(out, 'DEPLOY-MANIFEST.txt'), 'w',
                 encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(man) + '\n')

    print('  ✓ 投放目录 → %s' % out)
    print('      cubegm/rkgame                %d B  (诊断版, level=%d)' % (os.path.getsize(dst_bin), a.level))
    print('      cubegm/_diag/cfg.ini         %d B' % os.path.getsize(os.path.join(out, 'cubegm', '_diag', 'cfg.ini')))
    print('      READ-ME-FIRST.txt            %d B' % os.path.getsize(os.path.join(out, 'READ-ME-FIRST.txt')))
    print('      DEPLOY-MANIFEST.txt')
    for ln in man[4:7]:
        print('      %s' % ln)
    return 0


if __name__ == '__main__':
    sys.exit(main())
