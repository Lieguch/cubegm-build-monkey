#!/usr/bin/env python3
"""生成「探针 v3」投放目录 _sdcard_drop3/。

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
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop3')

# 源文件 → 目标相对路径
ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe3'),        'cubegm/rkgame'),
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


README = """ 真机测试说明 —— 探针 v3（抓崩溃现场）
============================================================

【这次已经确定的（你上一次的 PROBE2.txt 功劳）】

  1 原厂对照        → 存活至超时        ✅ 阳性对照通过
  3 t4 最小动态 ELF → 正常退出 exit=0    ✅ 动态链接链路完全正常
  4 A 线 rebuilt    → 被信号杀 signal=7   ★ SIGBUS（总线错误）
  5 A 线 diag       → 被信号杀 signal=11  ★ SIGSEGV（段错误）

  ⇒ **exec 是成功的**（内核与 ld.so 都放行）。程序自己在初始化阶段崩。
  ⇒ 我此前怀疑的 5 个结构原因（PT_LOAD 段数 / GNU_STACK / DT_INIT / 页冲突 /
    文本重定位）**全部被排除**（本地逐项查过，一个都不成立）。

【所以这次只做一件事：抓崩溃现场】

  探针 v3 用 ptrace 当 tracer，对每个候选：
    · 在 exec 成功后**停在第一条用户指令** ⇒ dump 此时的**完整 /proc/PID/maps**
      （看有没有哪个段没映射上 —— 这是 v2 做不到的）
    · 崩溃时抓 **si_addr（崩溃地址）+ PC + LR + SP**（→ 可离线符号化到具体函数）
    · 把子进程的 **stdout/stderr 重定向到文件**（目标程序和 glibc 打印的错误都会落盘）
    · 给子进程传 LD_DEBUG=libs,init（ld.so 自己的步骤日志落到 _diag/ldd_<pid>）


【你要做的 4 步】

  1) 确认 SD 卡上 cubegm/rkgame.bak 存在（= 原厂备份，约 3,921,108 字节）
     ★ 它是"阳性对照"。若不存在，请先把原厂 rkgame 复制成 rkgame.bak 再继续。

  2) 把本包 cubegm/ 里的这 5 个文件拷到 SD 卡 cubegm/（覆盖同名文件）：
        rkgame         (9,440 B)   ← 探针 v3，必须覆盖原来的
        rkgame.t4      (2,628 B)   ← 最小动态样件（上次成功过）
        rkgame.t1      (5.4 MB)    ← A 线 rebuilt（上次 SIGBUS）
        rkgame.t2      (5.7 MB)    ← A 线 diag（上次 SIGSEGV）
        rkgame.t5      (1.0 MB)    ← B 线 v15（对照）
     并把 cubegm/_diag/ 整个目录也拷过去（若已存在则合并）。

  3) 插卡开机，**等满 120 秒**（这次每个候选最多 8 秒 × 6 个 + 开销）。
     ★ 屏幕可能短暂出现原厂菜单 —— 正常，6~8 秒后探针会关掉它继续测。

  4) 关机、拔卡，把 cubegm/_diag/ 里这些文件发给我（尽量都发）：
        PROBE3.txt          ← 主日志（关键的都在里面）
        p3_0_out.txt … p3_5_out.txt  ← 每个候选自己的 stdout/stderr
        ldd_*               ← ld.so 的步骤日志（若有）
     如果还有 cubegm/T4-OK.txt 也一起发。


【回退到原厂（随时可做）】

  把 cubegm/rkgame.bak 复制一份改名成 cubegm/rkgame 即可。


【我拿到后能做什么】

  · maps（exec 后）⇒ 直接看出 A 线产物哪个段**没映射成功**
  · crash addr + PC ⇒ 符号化到**具体函数**（我有全部符号表）⇒ 定位到源码行
  · p3_*_out.txt ⇒ 程序或 glibc 打印的错误（如 "undefined symbol: xxx"）
  · ldd_* ⇒ ld.so 走到哪一步（加载？重定位？init？）

  这四个数据源合起来，**足以定位到具体函数**，而不是继续猜结构。
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
