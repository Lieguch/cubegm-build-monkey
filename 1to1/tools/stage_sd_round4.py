#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「第 4 轮真机测试」投放目录 _sdcard_drop4/。

本轮与上一轮的**本质区别**：不只是诊断，而是**带两个已修的根因**上机。

投放内容
    cubegm/rkgame      = 探针 v3（9.4 KB，静态、无 interp）—— 负责"测别人"并抓崩溃现场
    cubegm/rkgame.t1   = ★ 修复后的交付版（5.4 MB）—— 期望：能起、能进菜单
    cubegm/rkgame.t2   = ★ 修复后的诊断版（5.7 MB）—— 期望：**这次会真的写出 _diag/ 日志**
    cubegm/rkgame.t4   = 最小动态 ELF 对照（2.6 KB，只依赖 libc）
    cubegm/rkgame.t5   = B 线 v15（1.0 MB，对照）
    cubegm/rkgame.bak  = 阳性对照（原厂，**必须已存在于 SD 卡**）

用法
    PY=<python> python3 tools/stage_sd_round4.py [输出目录]
"""
import hashlib
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop4')

ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe3'),        'cubegm/rkgame'),
    (os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'),   'cubegm/rkgame.t1'),
    (os.path.join(ROOT, 'build', 'rkgame.diag'),          'cubegm/rkgame.t2'),
    (os.path.join(ROOT, 'build', 'rkgame.t4'),            'cubegm/rkgame.t4'),
    (os.path.join(ROOT, 'build', 'rkgame.brebuild'),      'cubegm/rkgame.t5'),
]

README = """ 真机测试 v4 —— 两个根因已修，这次是"能不能用"的正面测试
============================================================

【上一轮（探针 v3）已经拿到的硬事实】
    1 原厂对照        → 存活至超时            ✅ 阳性对照通过
    3 t4 最小动态 ELF → 正常退出 exit=0        ✅ 动态链接链路本身正常
    4 A 线 rebuilt    → SIGBUS(7)  PC=sfc_init+0x6c
    5 A 线 diag       → SIGSEGV(11) PC=cgm_diag_boot+0x184  出错地址 0x4e1010
    原厂自己打印:      snd_pcm_start failed: -32        （无害，它继续活着）
    我们自己打印:      failed to apply hwparams: -22     （致命差异）
    ⇒ **exec 是成功的**；程序自己在初始化阶段崩。

【本轮已修的两个根因（都是机器码级证据）】

  ★ 根因 A：传给音频驱动的**采样率变成了 5,128,288**
     工厂 InitSound 的机器码是 `movw r1, #44100`；而 44100 == 0xAC44，**恰好等于**工厂里
     `UpdateROM` 的函数地址 ⇒ Ghidra 把"立即数 44100"反编译成了符号 `UpdateROM`，
     我们的重建原样抄下。工厂布局下两者数值相同、"碰巧无害"；我们的产物把 UpdateROM
     链接到别处 ⇒ 采样率变成天文数字 ⇒ `snd_pcm_hw_params()` 返回 -22(EINVAL)
     ⇒ driver.so 的音频初始化失败（原厂同一处只是无害的 -32）。
     修法：`(*sound_driver_init)(USE_HDMI_OUT,44100,2)` —— 现在机器码与工厂逐条一致
     （`movw r1, #0xac44`）。
     新增门禁 `tools/lint_const_args.py`：把 213 个重建函数里"工厂是立即数、源码却写成
     符号"的用法全部对拍出来（已双向自证）。

  ★ 根因 B：`PT_GNU_RELRO` **把我们的全局变量所在页圈成了只读**
     ld.lld 的 RELRO 区间 = 「本 RW 段第一个 relro 节 → 最后一个 relro 节」。
     此前 `.data` 的输出段里混进了 `*(.data.rel.ro)/*(.got)`，而 lld 又把 `.dynamic`
     自动排到 `.data` 之后 ⇒ RELRO 一路覆盖到 `.dynamic` 末尾 ⇒ **`.data` 整段在 RELRO 里**，
     内核按页取整后把 0x4e0000-0x4e3000 设成只读 ⇒ 进程**第一次写自己的全局变量就 SIGSEGV**。
     这正好解释 t2 的 `si_addr=0x4e1010`（= diag 的 `g_lvl`）、PC 在 `cgm_diag_boot`
     —— 连 `-finstrument-functions` 的插桩都没跑起来。
     对照原厂：`PT_GNU_RELRO = 0x3ae5c4 + 2620`，终点 0x3aefe0 **恰好停在页对齐的
     `.data`(0x3af000) 之前** ⇒ 原厂 `.data` 完全可写。
     修法：`.data.rel.ro`/`.got`/`.dynamic` 独立成段并排在 `.data` **之前**，`.data` 页对齐。
     现在：我们 RELRO 页区间 0x4e0000-0x4e2000，`.data` 在 0x4e2000（页对齐，可写）。
     新增门禁 `tools/relro_audit.py`（页面级判据，已双向自证）。

  两条门禁都已钉进 `tools/link_full.sh`（本地与 CI 都绕不过，失败即 exit 13/14）。

【你要做的 4 步】

  1) 确认 SD 卡上 cubegm/rkgame.bak 存在（原厂备份，约 3,921,108 字节）。
     ★ 它是"阳性对照"。若不在，请先把原厂 rkgame 复制成 rkgame.bak。

  2) 把本包 cubegm/ 里的这 5 个文件拷到 SD 卡 cubegm/（覆盖同名文件）：
        rkgame         ← 探针 v3（必须覆盖原来的那个）
        rkgame.t1      ← ★ 修复后的交付版
        rkgame.t2      ← ★ 修复后的诊断版（这次应该真的能写日志）
        rkgame.t4      ← 最小动态样件
        rkgame.t5      ← B 线 v15（对照）
     并把 cubegm/_diag/ 整个目录拷过去（已存在则合并）。

  3) 插卡开机，**等满 150 秒**（探针会给每个候选最多 15 秒）。
     ★ 屏幕上如果出现原厂菜单，说明探针正在测"原厂能不能被拉起"（阳性对照），数秒后会关掉。
     ★ 如果屏幕出现**菜单/图标**而不再是黑屏，那就是 t1 或 t2 真的起来了 —— 多等一会儿。

  4) 关机拔卡，把 cubegm/_diag/ **整个文件夹**发给我，尤其：
        PROBE4.txt（或 PROBE3.txt）  ← 探针主日志
        BEGIN.txt / trace.log / crash.txt / frames.bin ← **如果出现了这些，说明诊断版跑起来了**
        p3_*_out.txt / ldd_*         ← 各候选自己的输出与 ld.so 日志

【回退到原厂（随时可做）】
  把 cubegm/rkgame.bak 复制一份改名成 cubegm/rkgame。

【我拿到后的判读】
  · t1 起来了 + 有菜单           ⇒ 两个根因确实是拦路虎，进入"逐项走查"（菜单/游戏/存档/音频）
  · t1 仍崩但有 _diag/ 日志      ⇒ 日志直接给函数名/地址，我按符号表定位到源码
  · 连 t2 也一条日志都没有       ⇒ 说明崩在 init_array 之前（甚至更早），按新地址继续收敛
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

    io.open(os.path.join(OUT, 'READ-ME-FIRST.txt'), 'w',
            encoding='utf-8', newline='\n').write(README)

    man = ['# DEPLOY-MANIFEST —— 真机测试 v4', '',
           '| 目标路径 | 字节 | sha256（前 32） |', '|---|---|---|']
    for rel, sz, h in rows:
        man.append('| `%s` | %d | `%s` |' % (rel, sz, h[:32]))
    io.open(os.path.join(OUT, 'DEPLOY-MANIFEST.txt'), 'w',
            encoding='utf-8', newline='\n').write('\n'.join(man) + '\n')

    os.makedirs(os.path.join(OUT, 'cubegm', '_diag'), exist_ok=True)
    io.open(os.path.join(OUT, 'cubegm', '_diag', '_PUT-ONLY-THIS-FOLDER.txt'), 'w',
            encoding='utf-8', newline='\n').write(
        '把本目录整体拷到 SD 卡的 cubegm/_diag/（合并，不要删除已有文件）。\n'
        '诊断版（rkgame.t2）会把日志写进这里；探针会把结论写进 PROBE3.txt。\n')

    print('  ✓ 投放目录: %s' % OUT)
    for rel, sz, h in rows:
        print('    %-22s %10d B  sha256=%s' % (rel, sz, h[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
