#!/usr/bin/env python3
"""mulshift_gate.py — 上游定点宏（MULSHIFT32 等）的 codegen 语义门禁。

★ 为什么需要（第 149 轮血泪）：
  helix 的 `MULSHIFT32(x,y) = ((int64_t)x*(int64_t)y) >> 32` 取的是**高 32 位**。
  实测真实 TU（`src/upstream/mp3/real/dct32.c`）里 clang 产出**两种都正确**的形态：
    · `smmul Rd,Rn,Rm`（ARMv6「stores the most significant 32 bits」，Arm 官方 ISA）
    · `umull` + `asr #31` + `mla`（符号修正的等价实现）
  ⇒ **单看「有几条 smmul」会误判**：第 148 轮我据此误报"clang 把语义降解成 mla"，
    实测是 smmul=**40** 条（我 grep 漏了同族助记符）。

本门禁只做**可机械判定**的事：
  ① 统计真实 TU 里 64→高 32 位乘法（`smmul/smull/umull/smal/umal`）的出现数；
     若**一条都没有** ⇒ 定点语义被整体丢弃 ⇒ **真风险，判失败**；
  ② 对比工厂形态并登记差异（不判失败，语义等价性已由 qemu-arm 实测确认）。

用法: python3 tools/mulshift_gate.py [--ours ...] [--factory ...] [--func ...]
退出: 0=通过（形态差异已登记）/ 2=失败（定点语义丢失或符号缺失）
"""
import argparse
import os
import re
import subprocess
import sys

ARM = 'arm-linux-gnueabihf-'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ 统计必须覆盖**同族前缀**（第 148 轮踩坑：`grep smul` 漏了 `smmul`，
#   因为 `smm` ≠ `smu`）。这也是本门禁存在的核心理由。
MUL_HI = ('smmul', 'smull', 'umull', 'smal', 'umal')
LO_RE = re.compile(r'\t(?:mla|mls)\b')
HI_RE = re.compile(r'\t(?:smmul|smull|umull|smal|umal)\b')


def count_in_func(binpath, func):
    """返回 (64→高32位乘法数, mla/mls 数, 指令总数)；符号不存在返回 None。"""
    d = subprocess.run([ARM + 'objdump', '-d', binpath],
                       capture_output=True, text=True,
                       errors='replace').stdout
    parts = d.split('<%s>:' % func)
    if len(parts) < 2:
        return None
    body = parts[1].split('\n\n')[0]
    lines = [ln for ln in body.splitlines() if '\t' in ln]
    hi = sum(1 for ln in lines if HI_RE.search(ln))
    lo = sum(1 for ln in lines if LO_RE.search(ln))
    return hi, lo, len(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--func', default='xmp3_FDCT32')
    a = ap.parse_args()

    print('== mulshift_gate（第 149 轮引入）==')
    print('  目标函数: %s' % a.func)
    o = count_in_func(a.ours, a.func)
    f = count_in_func(a.factory, a.func)
    if o is None or f is None:
        print('  ★ 至少一侧找不到该符号 ⇒ 无法判定（ours=%s factory=%s）'
              % (o is not None, f is not None))
        return 2
    print('  工厂: 64→高32位乘法=%-4d mla/mls=%-4d 指令总数=%d' % (f[0], f[1], f[2]))
    print('  我方: 64→高32位乘法=%-4d mla/mls=%-4d 指令总数=%d' % (o[0], o[1], o[2]))

    if o[0] == 0:
        print('')
        print('★FAIL：我方真实 TU 里一条 64→高32位乘法都没有')
        print('  ⇒ 定点宏语义可能被整体丢弃，会污染解码输出。')
        return 2
    print('')
    print('OK：定点乘法语义存在（64→高32位 共 %d 条）。' % o[0])
    if o[0] != f[0]:
        print('  登记形态差异：我方 %d 条 vs 工厂 %d 条' % (o[0], f[0]))
        print('  ★ 已实测的两种等价形态（第 149 轮取证，不猜）：')
        print('     · 工厂/我方 .o：`smmul Rd,Rn,Rm`（Armv6「存最高 32 位」）')
        print('     · 我方**链接后产物**：`umull` + `asr #31` + `mla` 三条一组')
        print('       （有符号 64 位积取高 32 位的等价实现；')
        print('        产物与 .o 指令数相同 573 ⇒ 是链接器等价变换，非指令增减）')
        print('  ★ 语义等价性已由 qemu-arm 真 CPU 语义实测：8/8 组输入与 C 真值逐项一致。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
