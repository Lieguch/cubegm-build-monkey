#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「探针 v4」投放目录 _sdcard_drop6/。

本轮的**唯一**核心问题
---------------------------------------------------------------
    上一轮设备实测拿到的 SIGBUS 是在 `sfc_init+0x6c`，离线读到那正是
        `e1d012bc` = `ldrh r1,[r0,#0x2c]`   ← 16 位窄化读 /dev/mem 的 SFC 寄存器
    而**修复版**（本仓库当前产物）在同一点是
        `e5804000` = `str r4,[r0]`（先写）+ `e590102c` = `ldr r1,[r0,#0x2c]`（32 位读）
    ⇒ 本轮只回答一件事：**修复版还崩不崩？**

投的是什么（7 个候选，成败都可解释）
---------------------------------------------------------------
    cubegm/rkgame      = 探针 v4（静态、无 interp、~11 KB）
    cubegm/rkgame.t4   = 最小动态 ELF（基线，应 exit 0）
    cubegm/rkgame.t1   = A 线【修复前】★ 应与上一轮同点 SIGBUS（= 阳性对照的"已知缺陷态"）
    cubegm/rkgame.t3   = A 线【修复后】★★ 本轮关键：若不再 SIGBUS ⇒ 修复被真机证实
    cubegm/rkgame.t2   = A 线 diag【修复前】
    cubegm/rkgame.t6   = A 线 diag【修复后】
    cubegm/rkgame.t5   = B 线 v15（对照：已验证能跑）
    cubegm/rkgame.bak  = 阳性对照（原厂，用户此前已备份；**必须存在**）

为什么这么设计
---------------------------------------------------------------
    · 阳性对照（原厂）使"候选失败"成为可解释的差异，而非"探针坏了"。
    · **同一镜像的修复前/修复后成对** ⇒ 结果差异只能归因于那 28 字节的机器码改动
      （离线已逐字节确认：两版只差 `sfc_request`，676→704 B）。
    · t4/t5 锁定"加载层与工具链没问题"这个不变式。
    · diag 版带**仪器自证行**（VARCHK）：trace.log 里的 %d/%s/%p 是否可信，
      本轮由设备自己回答，不再靠推测。

用法
    PY=<python> python3 tools/stage_sd_probe4.py [输出目录]
"""
import hashlib
import io
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop6')

# 源文件 → 目标相对路径
ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe4'),          'cubegm/rkgame'),
    (os.path.join(ROOT, 'build', 'rkgame.t4'),              'cubegm/rkgame.t4'),
    # 修复前：与上一轮设备实测 SIGBUS 的字节完全相同
    (os.path.join(ROOT, 'build', '_prewidth.rebuilt.elf'),  'cubegm/rkgame.t1'),
    (os.path.join(ROOT, 'build', '_prewidth.diag'),         'cubegm/rkgame.t2'),
    # ★ 修复后：含 MMIO 32 位读 + 恢复工厂的「先写后读」顺序
    (os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'),     'cubegm/rkgame.t3'),
    (os.path.join(ROOT, 'build', 'rkgame.diag'),            'cubegm/rkgame.t6'),
    # 对照：已实测能跑的 B 线
    (os.path.join(ROOT, 'build', 'rkgame.brebuild'),        'cubegm/rkgame.t5'),
]

# ★ 配置文件里的**注释不能出现真键名**：旧解析器是"全文找第一个 level"，
#   注释里的 `level=2` 会把真值劫持掉（本轮实测 level 一直=2 就是这个原因）。
#   这里双保险：解析器已改成跳过注释行，同时配置文件也不在注释里写键名。
CFG_INI = """\
# cgm_diag config.  The real setting is the first non-comment line below.
level = 3
#   0 = crash report only
#   1 = lifecycle / signals / file open-close / dlopen / threads
#   2 = 1 + read/write/lseek offsets + every ioctl + mmap  (built-in default)
#   3 = 2 + content hex + malloc-free detail (slowest)
"""

PUT_TEXT = ("把本目录整体拷到 SD 卡的 cubegm/_diag/。\n"
            "探针 v4 会把结论写进 PROBE4.txt；_diag/ 必须存在且可写。\n"
            "cfg.ini 里第一行真设置是 level = 3。\n")

GEN = [
    ('cubegm/_diag/cfg.ini', CFG_INI),
    ('cubegm/_diag/_PUT-ONLY-THIS-FOLDER.txt', PUT_TEXT),
]

README = """ 真机测试说明 —— 探针 v4（验证 MMIO 宽度修复）
============================================================

【上一轮已经确定的（你的 PROBE3.txt 功劳）】

  1 原厂对照        → 存活至超时          ✅ 阳性对照通过
  2 t4 最小动态 ELF → 正常退出 exit=0      ✅ 动态链接链路完全正常
  3 A 线 rebuilt    → ★ SIGBUS(7)         PC=sfc_init+0x6c
  4 A 线 diag       → ★ SIGSEGV(11)
  7 B 线 v15        → 存活至超时          ✅ 我们自己的代码在真机上真的跑起来了
                          (它的 stdout 是 "=== rkgame rebuild starting ===" ×2
                           + "failed to apply hwparams: -22")

【本轮我离线查出来的关键事实 —— 这就是为什么必须重测】

  你上次投的 t1/t2 **不是修复版**：设备上 rkgame.t1 = 5,663,896 B，而当前
  修复版 build/rkgame.rebuilt.elf = 5,663,928 B（相差 32 B）。

  更关键的是：崩溃 PC `sfc_init+0x6c` 我离线读到了那条指令 ——
     修复前： e1d012bc  =  ldrh r1, [r0, #0x2c]    ← ★16 位读
     修复后： e5804000  =  str  r4, [r0]           ← 32 位写（先写）
              e590102c  =  ldr  r1, [r0, #0x2c]    ← ★32 位读
  而崩溃报告里 r0 = mmap 基址、si_addr = mmap 基址 + 0x2C
  ⇒ 完全吻合：**在 mmap 出来的 SFC 寄存器区上做 16 位访问，触发了总线错误**。
  这也解释了为什么原厂不崩 —— 原厂在同一位置做的就是 32 位读。

  ⇒ 所以本轮要看的就一句：**t3（修复后）还崩不崩？**

【你要做的 4 步】

  1) 确认 SD 卡上 cubegm/rkgame.bak 存在（= 原厂备份，3,921,108 字节）
     ★ 它是"阳性对照"。若不存在，请先把原厂 rkgame 复制成 rkgame.bak 再继续。

  2) 把本包 cubegm/ 里的 7 个文件拷到 SD 卡 cubegm/（覆盖同名文件），
     并把 cubegm/_diag/ 整个目录也拷过去（合并覆盖，cfg.ini 一定要覆盖）：

        rkgame       (~11 KB)    ← 探针 v4，必须覆盖
        rkgame.t1    (5,663,896) ← A线【修复前】预期 SIGBUS
        rkgame.t3    (5,663,928) ← A线【修复后】★ 本轮关键
        rkgame.t2    (5,709,244) ← A线 diag【修复前】
        rkgame.t6    (5,709,292) ← A线 diag【修复后】
        rkgame.t4    (2,628)     ← 最小动态样件（基线）
        rkgame.t5    (1,031,860) ← B线 v15（对照）

  3) 插卡开机，**等满 150 秒**（7 个候选 × 最多 8 秒 + 开销）。

  4) 关机拔卡，把 cubegm/_diag/ 里这些发我：
        PROBE4.txt          ← 主日志（关键都在里面）
        p4_0_out.txt … p4_6_out.txt
        ldd_*                （若有）
     以及 cubegm/T4-OK.txt（若有）。

【回退到原厂（随时可做）】

  把 cubegm/rkgame.bak 复制一份改名成 cubegm/rkgame 即可。

【我拿到后怎么判（判据先写死，避免事后凑结论）】

  · 阳性对照（原厂）必须仍然"存活至超时"。否则整轮作废，先修探针。
  · t4 必须仍然 exit=0；t5 必须仍然"存活至超时"。否则工具链/加载层层面出了问题。
  · **t3 的 PC**：
      - 不再是 0x501bXX（sfc_init/邻近）⇒ 宽度修复生效，进入下一个故障点
      - 仍是 sfc_init+0x6c ⇒ 修复没生效（那就要核对设备上的文件 sha256）
    ★ 探针 v4 新增：崩溃时会打印 **PC 处 48 字节指令 + SP 起 512 字节栈 +
      栈上所有落在可执行区的候选返回地址** ⇒ 即使崩在别处也能直接回溯。
  · t6/t2 的 trace.log 里找 `VARCHK` 行：
      期望值和实测值一致 ⇒ trace.log 的 %d/%s/%p 可信，后续读数用它；
      不一致           ⇒ 变参不可信，那一轮只用 p4_*_out.txt（stdout/stderr）。

============================================================
"""


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    rows = []
    for src, rel in ITEMS:
        if not os.path.exists(src):
            print('  !! 缺少源文件 %s' % src)
            return 1
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        rows.append((rel, os.path.getsize(dst), sha256(dst)))

    for rel, content in GEN:
        dst = os.path.join(OUT, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        io.open(dst, 'w', encoding='utf-8', newline='\n').write(content)
        rows.append((rel, os.path.getsize(dst), sha256(dst)))

    manifest = ['# DEPLOY-MANIFEST — 探针 v4 投放包', '',
                '生成时间: %s' % time.strftime('%Y-%m-%d %H:%M:%S'), '',
                '| 目标路径 | 字节 | sha256 |', '|---|---|---|']
    for rel, sz, h in rows:
        manifest.append('| `%s` | %d | `%s` |' % (rel, sz, h))
    manifest += [
        '',
        '## 阳性对照（不在本包内，必须在设备上已存在）',
        '- `cubegm/rkgame.bak` —— 原厂 rkgame，3,921,108 B',
        '- 探针会先 execve 它。**它必须成功**，否则其余结论一概不可信。',
        '',
        '## 本轮 A/B 的自变量（离线逐字节确认）',
        '- 修复前 t1 = `build/_prewidth.rebuilt.elf`：`sfc_init+0x6c` = `ldrh r1,[r0,#0x2c]`',
        '- 修复后 t3 = `build/rkgame.rebuilt.elf`：`sfc_init+0x6c` = `str r4,[r0]`；`+0x70` = `ldr r1,[r0,#0x2c]`',
        '- 两版 ELF 的符号级差分：**只有 `sfc_request` 变了**（676 → 704 B），其余 2726 个符号仅整体平移。',
    ]
    io.open(os.path.join(OUT, 'DEPLOY-MANIFEST.txt'), 'w',
            encoding='utf-8', newline='\n').write('\n'.join(manifest) + '\n')

    io.open(os.path.join(OUT, 'READ-ME-FIRST.txt'), 'w',
            encoding='utf-8', newline='\n').write(README)

    print('  ✓ 投放目录: %s' % OUT)
    for rel, sz, h in rows:
        print('      %-38s %10d B  %s' % (rel, sz, h[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
