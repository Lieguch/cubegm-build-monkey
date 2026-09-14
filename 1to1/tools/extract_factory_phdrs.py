#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""extract_factory_phdrs.py — 从工厂二进制导出程序头台账（布局保真的**基准**）

为什么需要它（★ 真实差分抓到的假分歧）：
  工厂 rkgame 的首个 PT_LOAD 从 **0x8000** 开始（`p_align=0x1000`），
  因此 **地址 0..0x7fff 在工厂进程里是空洞**。
  我们的重建产物原先把首个 LOAD 放在 **0x0**（p_align=0x10000 时链接器会把首段起点
  一路向下取整到 0），于是：

      sunxi_gpio_set_cfgpin(0,1)  →  *(u32*)(GPIO2 + 4) |= 8
      （GPIO2 因 /dev/mem 打不开而保持 NULL）⇒ 写**地址 4**

  · 工厂：地址 4 未映射 ⇒ 立刻 SIGSEGV（stdout 停在 "Failed to initialize GPIO"）
  · 我们：地址 4 被 LOAD 覆盖且（CI 上 GNU ld 合并成 fl=0x7）**可写**
          ⇒ 写成功、静默污染镜像首字节 ⇒ 继续跑到 "RF_IC Test Fail !" 才崩

  ⇒ 行为差分因此报出一条**假分歧**，且这类"静默成功"会掩盖真实缺陷。
  正确做法：把工厂的程序头（地址/权限/对齐）当**基准**固化下来，由门禁强制对齐。

用法: python tools/extract_factory_phdrs.py [factory_elf] [out_tsv]
默认: D:/output/rkgame/rkgame → ledger/factory_phdrs.tsv
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_ELF = 'D:/output/rkgame/rkgame'

TAG = {1: 'LOAD', 2: 'DYNAMIC', 3: 'INTERP', 4: 'NOTE', 6: 'PHDR',
       0x6474e550: 'GNU_EH_FRAME', 0x6474e551: 'GNU_STACK',
       0x6474e552: 'GNU_RELRO', 0x70000001: 'ARM_EXIDX'}


def main():
    elf = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ELF
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'ledger', 'factory_phdrs.tsv')
    if not os.path.exists(elf):
        print('FATAL 找不到工厂 ELF: %s' % elf)
        return 1
    d = open(elf, 'rb').read()
    phoff = struct.unpack_from('<I', d, 28)[0]
    ents = struct.unpack_from('<H', d, 42)[0]
    num = struct.unpack_from('<H', d, 44)[0]

    rows = []
    for i in range(num):
        o = phoff + i * ents
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        rows.append((TAG.get(t, hex(t)), off, va, fsz, msz, fl, al))

    lines = ['# 工厂 rkgame 程序头台账（由 tools/extract_factory_phdrs.py 生成，勿手改）',
             '# 列：type\toffset\tvaddr\tfilesz\tmemsz\tflags\talign',
             '# flags: 4=R / 2=W / 1=X']
    for nm, off, va, fsz, msz, fl, al in rows:
        lines.append('%s\t0x%08x\t0x%08x\t%d\t%d\t0x%x\t0x%x' % (nm, off, va, fsz, msz, fl, al))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')

    loads = [r for r in rows if r[0] == 'LOAD']
    print('程序头 %d 条（LOAD %d 条）→ %s' % (len(rows), len(loads), out))
    for nm, off, va, fsz, msz, fl, al in loads:
        print('  LOAD va=0x%08x..0x%08x fl=0x%x(%s) align=0x%x'
              % (va, va + msz, fl, ''.join(c for c, b in zip('RWX', (4, 2, 1)) if fl & b), al))
    low = min(r[2] for r in loads)
    print('  ★ 工厂最低 LOAD 地址 = 0x%08x ⇒ 地址 [0, 0x%08x) 在工厂进程里是**空洞**' % (low, low))
    return 0


if __name__ == '__main__':
    sys.exit(main())
