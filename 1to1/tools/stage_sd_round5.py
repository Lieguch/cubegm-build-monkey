#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成「第 5 轮真机测试」投放目录 _sdcard_drop5/。

本轮新增（全部有真机/机器码证据）：
  ★ 根因 C：MMIO 访存宽度被编译器窄化
      · `sfc_init`   ：工厂 `ldr`（32 位）→ 我们 `ldrh`（16 位）   ⇒ 真机 SIGBUS(7) @ mmap基址+0x2C
      · `sfc_request`：同一个惯用法（9 个调用者，含 spi_read/spi_write/UpdateROM）
      · 修法：设备寄存器指针一律 `volatile`（宽度与顺序都被固化）
      · 新门禁 `tools/mmio_width_audit.py`（对照工厂访存宽度直方图，三态自证）
  ★ 诊断仪自身致命缺陷修复：AArch32 上 `va_list` 是 struct，**不能当普通实参转发**
      ⇒ 旧诊断版所有实参错位（乱码 + `null`）、并在 `vfmt` 里 SIGSEGV
      ⇒ 这次诊断版应当**真的能写出 _diag/ 全套日志**（含 BEGIN/crash/frames）

投放内容
    cubegm/rkgame      = 探针 v3（负责测候选、抓崩溃现场）
    cubegm/rkgame.t1   = ★ 三处修复后的交付版（期望：能起、能进菜单）
    cubegm/rkgame.t2   = ★ 修复后的诊断版（期望：写出 _diag/ 全套日志）
    cubegm/rkgame.t4   = 最小动态 ELF（对照）
    cubegm/rkgame.t5   = B 线 v15（对照）
    cubegm/rkgame.bak  = 阳性对照（原厂，必须已在卡上）

用法: PY=<python> python3 tools/stage_sd_round5.py [输出目录]
"""
import hashlib
import io
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '_sdcard_drop5')

ITEMS = [
    (os.path.join(ROOT, 'build', 'rkgame.probe3'),        'cubegm/rkgame'),
    (os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'),   'cubegm/rkgame.t1'),
    (os.path.join(ROOT, 'build', 'rkgame.diag'),          'cubegm/rkgame.t2'),
    (os.path.join(ROOT, 'build', 'rkgame.t4'),            'cubegm/rkgame.t4'),
    (os.path.join(ROOT, 'build', 'rkgame.brebuild'),      'cubegm/rkgame.t5'),
]

README = """ 真机测试 v5 —— 第三个根因已定位并修（MMIO 访存宽度）
============================================================

【上一轮（v4）拿到的硬事实 —— 你的日志非常有价值】
  · t1（交付版）原厂化的音频行出现了：`snd_pcm_start failed: -32`
      ← ★ 与**原厂逐字相同**（此前是致命的 `failed to apply hwparams: -22`）
      ⇒ 采样率 44100 那一处修复在真机上被证实有效；ld.so 侧也不再报
        `libasound.so.2: undefined symbol`（那是采样率天文数字导致 ALSA 去加载 rate 插件引起的）
  · t1 之后崩在：`SIGBUS(7)`，`si_addr = <mmap 基址>+0x2C`，`PC = sfc_init+0x6c`
      `r7 = 0x10208000`（mmap 偏移）、`r0 = mmap 基址` ⇒ **读 SFC 寄存器那一刻总线错误**
  · t2（诊断版）这次真的跑起来了（RELRO 修复生效，maps 里 `.data` 已可写），
      但死在**诊断仪自己**的 `vfmt+0x1c4`（见下面根因 D）

【根因 C：MMIO 访存宽度被编译器窄化（本轮修复）】
  与工厂逐条对照，`sfc_init` 里**唯一差异就是这个读的宽度**：
      工厂 0x2c4464:  ldr  r3, [r2, #44]     ← 32 位读（随后 uxth 取低半字）
      我们（旧）     : ldrh r1, [r0, #44]     ← ★ 16 位读
  原因：源码 `g_sfc_reg[0xb] & 0xffff`（指针是 `gh_u4*`），GCC 只用到低半字就把加载窄化了
        —— 对普通内存合法，**对设备寄存器等于改硬件行为**；而且它还把顺序从
        「先写 [base]=0 再读 [base+0x2C]」改成了「先读后写」。
  同一惯用法在 `sfc_request`（9 个调用者：spi_read/spi_write/UpdateROM/…）里也有一份
        ⇒ 那里是**下一处必然崩溃**，本轮一并修了。
  修法：设备寄存器指针一律 `volatile`（宽度、顺序都被固化）。
  修后机器码（与工厂等价）：
      str r4,[r0]        ← 先写
      ldr r1,[r0,#44]    ← 32 位读（不再是 ldrh）
      tst r1, #~3 / strne r1,[r0,#136]
  新门禁 `tools/mmio_width_audit.py`：对照工厂/我们的访存宽度直方图，三态自证
      （正常 PASS / 喂修复前快照必 FAIL / 缺文件 exit 11），已钉进 link_full.sh（exit 15）。

【根因 D：诊断仪自己崩了（本轮修复）】
  `trace.log` 里所有带实参的调用都**整体错位一格**且是垃圾值：
      IO fopen "…乱码…" mode="(null)" ret=0xbe8047c8
  根因：`cgm_putline()` 把 `va_list` **当成普通实参**传给了变参格式化函数。
       在 **AArch32 上 `va_list` 是 struct（x86-64 是数组）** ⇒ 传进去后格式化函数
       把"那个 va_list 对象"当成第一个变参 ⇒ 全部错位；最后那个"指针"不可读 ⇒
       `SIGSEGV`（PC=`vfmt+0x1c4`、si_addr=`0x32323534`=ASCII 数字当指针）。
  ★ 这个缺陷在 PC 上**不会复现** ⇒ 只能靠设备端日志抓出来。
  修法：拆成 `vfmt_ap(dst,cap,fmt,va_list)` + 薄包装 `vfmt(...)`，转发一律走 `vfmt_ap`；
       并给 `cgm_putline` 加 `__attribute__((format(printf,2,3)))`（这样 `-Wformat` 才真的检查，
       现在 0 警告）。

【你要做的 4 步】
  1) 确认 SD 卡 cubegm/rkgame.bak 在（原厂备份，3,921,108 B）。它是阳性对照。
  2) 把本包 cubegm/ 的 5 个文件拷到 SD 卡 cubegm/（覆盖同名），_diag/ 整个拷过去（合并）。
        ★ 建议先把 _diag/ 里旧文件清掉或改名，便于分辨本次新增的日志。
  3) 插卡开机，**等满 150 秒**（探针给每个候选 8 秒；诊断版会自己写日志）。
        ★ 屏幕若出现菜单/图标而不再是黑屏，就是 t1 或 t2 真起来了。
  4) 关机拔卡，把 cubegm/_diag/ 整个文件夹发我。这次应能看到：
        BEGIN.txt / trace.log / crash.txt / frames.bin / env.txt / maps.start.txt
        （若出现 BEGIN.txt 与可读的 trace.log，说明诊断仪真的活了）
      另外 cubegm/rkgame.log 也请一并发我（那是应用自己的日志文件，RARCH_LOG 写在那里）。

【回退原厂】把 cubegm/rkgame.bak 复制改名成 cubegm/rkgame。

【我拿到后的判读】
  · t1 进菜单            ⇒ 三处根因全中，进入逐项走查（菜单/游戏/存档/音频）
  · t1 仍崩、但有 crash.txt/frames.bin ⇒ 直接给函数名与地址，我按符号表定位
  · 诊断版仍写不出东西   ⇒ 收敛到"更早"的位置（init_array 之前），换手段继续
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
    man = ['# DEPLOY-MANIFEST —— 真机测试 v5', '',
           '| 目标路径 | 字节 | sha256（前 32） |', '|---|---|---|']
    for rel, sz, h in rows:
        man.append('| `%s` | %d | `%s` |' % (rel, sz, h[:32]))
    io.open(os.path.join(OUT, 'DEPLOY-MANIFEST.txt'), 'w',
            encoding='utf-8', newline='\n').write('\n'.join(man) + '\n')
    os.makedirs(os.path.join(OUT, 'cubegm', '_diag'), exist_ok=True)
    io.open(os.path.join(OUT, 'cubegm', '_diag', '_PUT-ONLY-THIS-FOLDER.txt'), 'w',
            encoding='utf-8', newline='\n').write(
        '把本目录整体拷到 SD 卡的 cubegm/_diag/（合并）。\n'
        '★ 建议先把旧的 _diag/ 内容清空，便于分辨本轮新增日志。\n')
    print('  ✓ 投放目录: %s' % OUT)
    for rel, sz, h in rows:
        print('    %-22s %10d B  sha256=%s' % (rel, sz, h[:16]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
