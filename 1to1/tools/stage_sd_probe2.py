#!/usr/bin/env python3
"""生成「探针 v2」投放目录 _sdcard_drop2/。

投的是什么
    cubegm/rkgame      = 探针 v2（静态、无 interp、8.2 KB）—— 它负责"测别人"
    cubegm/rkgame.t1   = A 当前 5.4 MB 重建产物（已知：零日志）
    cubegm/rkgame.t2   = B 诊断版 5.7 MB（已知：零日志）
    cubegm/rkgame.t4   = D 最小动态 ELF 2.6 KB（新对照，只依赖 libc）
    cubegm/rkgame.bak  = 阳性对照（原厂，用户此前已备份；**必须存在**）

为什么这样设计
    · 探针 v2 自己是**已被设备实测证明能跑**的技术路线（v1 同源），
      所以它给出的结论可信；它只负责 fork+execve 候选并记录 errno。
    · 阳性对照（原厂）使"候选失败"成为可解释的差异，而非"探针坏了"。
    · t1/t2 已知失败 ⇒ 它们是**已知缺陷态的复现**；t4 是新变量（动态但极小）。

用法
    PY=<python> python3 tools/stage_sd_probe2.py [输出目录]
"""
import hashlib
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop2')

# 源文件 → 目标相对路径
ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe2'),        'cubegm/rkgame'),
    (os.path.join(ROOT, 'build', 'rkgame.t4'),            'cubegm/rkgame.t4'),
    (os.path.join(ROOT, 'build', 'rkgame.brebuild'),      'cubegm/rkgame.t5'),
    (os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'),   'cubegm/rkgame.t1'),
    (os.path.join(ROOT, 'build', 'rkgame.diag'),          'cubegm/rkgame.t2'),
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


README = """============================================================
 真机测试说明 —— 探针 v2（一次就能定位"为什么起不来"）
============================================================

【本包要回答的问题】

  已知（你上次的实测，非常有用）：
    · 5.4 MB 版 → 无日志
    · 最小探针（静态）→ 成功写了 PROBE.txt

  结论已经收窄到一点：**静态能跑、动态起不来**。但还差最后一步 ——
  "动态起不来"到底是：
    (甲) 内核在加载 ELF 时就拒绝
    (乙) 内核放行了，但动态链接器(ld.so)加载/重定位失败
    (丙) exec 成功了，但程序在写第一行日志之前自己崩了
  这三者的**修法完全不同**，所以必须先分开。本包就是去分开它们。

  做法：本包里的 rkgame 是一个**探针**（不是重建产物）。它自己一定能跑
  （和你上次成功的那个同源），跑起来后它会依次 fork+execve 几个候选文件，
  把每个候选的**结局**记下来：
      · execve 返回了 errno 数字  → 属于 (甲)/(乙)
      · 子进程被信号杀掉(带信号号) → 属于 (丙)
      · 子进程正常退出 / 一直活着 → exec 成功


【你要做的 4 步】

  1) 确认 SD 卡上 cubegm/rkgame.bak 存在（= 原厂备份，约 3,921,108 字节）
     ★ 这是本测试的"阳性对照"。它不在包里。若不存在，请先把原厂 rkgame
       复制成 rkgame.bak 再继续。

  2) 把本包 cubegm/ 里的这 5 个文件拷到 SD 卡 cubegm/（会覆盖同名文件）：
        rkgame         (8,268 B)   ← 探针，必须覆盖原来的
        rkgame.t5      (1.0 MB)    ← ★ B 线 v15：**已在真机跑过**的那一版
        rkgame.t4      (2,628 B)   ← 最小动态样件（只依赖 libc）
        rkgame.t1      (5.4 MB)    ← A 线重建产物（已知：零日志）
        rkgame.t2      (5.7 MB)    ← A 线诊断版（已知：零日志）
     并把 cubegm/_diag/ 整个目录也拷过去（若已存在则合并）。

  3) 插卡开机，**等满 90 秒**。
     ★ 中途屏幕上**可能出现原厂菜单**——这是正常的，而且是好消息：
       它说明探针成功把原厂拉起来了（阳性对照通过）。
       约 6 秒后探针会把它关掉，然后继续测其它候选。
     屏幕全程黑屏也没关系，结论照样写在卡上。

  4) 关机、拔卡、把 cubegm/_diag/PROBE2.txt 发给我
     （如果还有 cubegm/T4-OK.txt 也一起发，那是好消息的信号）


【回退到原厂（随时可做）】

  把 cubegm/rkgame.bak 复制一份改名成 cubegm/rkgame 即可。
  注意：**.bak 是给探针当对照用的**，平时不要动它。


【我拿到 PROBE2.txt 后能确定什么】

  探针会带回：
    · 每个候选的 size / ELF magic（顺便检出"拷贝损坏"）
    · 每个候选的 execve errno 或 子进程结局（信号号 / 退出码）
    · 设备环境事实：/proc/sys/vm/mmap_min_addr、/proc/mounts、
      /proc/self/maps（能反推内核页大小）、/proc/version

  对应结论：
    · 原厂对照也失败        → 探针的 exec 机制有问题，我会先修探针
    · **t5(B线 v15) 成功**   → ★ **设备直接可用的版本可能就是它**（它已在真机跑过）
                              ⇒ 下一步就把它正式装成 rkgame，逐项走查（菜单/游戏/存档/音频）
    · t4(最小动态) 成功     → 动态链接没问题 ⇒ 问题在 A 线产物的结构/规模
    · t4 也失败 + errno=8   → 内核拒绝该 ELF ⇒ 修段布局/ELF 结构
    · t4 也失败 + errno=2   → 解释器或依赖库路径问题 ⇒ 查 loader
    · 候选被信号杀(如 11)   → exec 成功、程序初始化崩 ⇒ 查 CRT/重定位

  无论哪种结果，都是**可操作的**（不是又一轮猜）。

【已经知道的三方结构差异（供你理解为什么要测 t5）】

  A 线(零日志) 9 个 PT_LOAD、GNU_STACK memsz=16MB flags=RW-
  B 线 v15(跑过) 2 个 PT_LOAD、GNU_STACK memsz=0   flags=RWX、ET_DYN(PIE)
  原厂(正常)     2 个 PT_LOAD、GNU_STACK memsz=0   flags=RWX、ET_EXEC
  ⇒ A 线在"装载模型"上与另两者不同；B 线与原厂一致。
============================================================
"""


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    rows = []
    for src, rel in ITEMS:
        if not os.path.exists(src):
            print('  !! 缺少源文件 %s（先跑 build_probe2.sh / _mk_t4.py / link_full.sh）' % src)
            return 1
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        rows.append((rel, os.path.getsize(dst), sha256(dst)))

    # 说明书：只投 _diag/ 这一个目录的额外提示
    os.makedirs(os.path.join(OUT, 'cubegm', '_diag'), exist_ok=True)
    io.open(os.path.join(OUT, 'cubegm', '_diag', '_PUT-ONLY-THIS-FOLDER.txt'), 'w',
            encoding='utf-8', newline='\n').write(
        '把本目录整体拷到 SD 卡的 cubegm/_diag/。\n'
        '探针 v2 会把结论写进 PROBE2.txt；_diag/ 必须存在且可写。\n')

    manifest = ['# DEPLOY-MANIFEST — 探针 v2 投放包', '',
                '生成时间: %s' % __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
                '', '| 目标路径 | 字节 | sha256 |', '|---|---|---|']
    for rel, sz, h in rows:
        manifest.append('| `%s` | %d | `%s` |' % (rel, sz, h))
    manifest += ['', '## 阳性对照（不在本包内，必须在设备上已存在）',
                 '- `cubegm/rkgame.bak` —— 原厂 rkgame，3,921,108 B',
                 '- 探针会先 execve 它。**它必须成功**，否则其余结论一概不可信。',
                 '', '## 探针会读回的设备事实',
                 '- `/proc/sys/vm/mmap_min_addr`（若 > 产物最低 vaddr ⇒ 内核 EPERM 拒载）',
                 '- `/proc/mounts`（`/sdcard` 挂载参数：noexec / fmask）',
                 '- `/proc/self/maps`（反推内核**页大小**与加载方式）',
                 '- `/proc/version`']
    io.open(os.path.join(OUT, 'DEPLOY-MANIFEST.txt'), 'w',
            encoding='utf-8', newline='\n').write('\n'.join(manifest) + '\n')

    io.open(os.path.join(OUT, 'READ-ME-FIRST.txt'), 'w',
            encoding='utf-8', newline='\n').write(README)

    print('  ✓ 投放目录: %s' % OUT)
    for rel, sz, h in rows:
        print('      %-22s %10d B  %s' % (rel, sz, h[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
