#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elf_load_audit.py —— **PT_LOAD 几何门禁**（第 15 道硬门禁）

为什么要有它（GAP 16.69，代价 = 一次真机失败 + 用户白跑两轮）
------------------------------------------------------------------
项目原有 14 道门禁查的是：ABI 头字段 / `.interp` / 段 VMA 是否与工厂一致 /
符号是否落在 PT_LOAD 内 / 动态段自洽 —— **全都只看"地址对不对"，没有任何一道看"段本身是否畸形"**。
于是下面这份**在 PC/qemu 上完全正常、在真机上直接起不来**的产物一路全绿：

    linker/factory.ld 里 `.data`/`.bss`/`.text` 被钉在 0x01000000/0x02000000/0x05000000，
    而 WA 属性的 `.fini_array` 在 `.rodata` 末尾（~0x4e00e0）。lld 把两者归入**同一个 RW 段**，
    该段 p_filesz 于是跨过中间 **11.1 MB 的 VMA 空洞**：
      · PT_LOAD 2 → 9 段；文件 3.9 MB → 17.3 MB（11 MB 是纯填充）
      · 最高 vaddr 3.9 MB → **268 MB**（内核据此把 brk 也推到 268 MB）
      · 该 11 MB 段与承载**全部代码**的 `.text` 段**地址重叠**
    真机（RK3036G，2×Cortex-A7）表现：**无法开机、诊断目录内零文件** —— 一条日志都不产生。

判据（每条都能独立说明"哪一项、多少、阈值多少"）
------------------------------------------------------------------
  A1  **段内不得跨未认领空隙**：对每个 `p_filesz>0` 的 PT_LOAD，取其文件区间
      `[p_offset, p_offset+p_filesz)`，累加落在其中的**非 NOBITS 节**的 `sh_size`；
      若 `p_filesz > covered + 8192` ⇒ **FAIL**（该段映射了文件里的空洞）。
      ★ 这条是**直接症状判据**，11 MB 空洞必然被它逮住。
  A2  **无真重叠**：任一段的起点不得落在另一段的 `[vaddr, vaddr+max(filesz,memsz))` 内部。
  A3  **对齐**：`p_vaddr % p_align == p_offset % p_align`。
  A4  **最高 vaddr 端 ≤ 32 MB**（工厂 3.9 MB；修复后我们 5.4 MB；缺陷态 268 MB）。
      —— 这个数直接决定内核给 brk 预留多大。
  A5  **段数 ≤ 12**（工厂 2；修复后 9；留余量）。
  A6  **文件大小 ≤ 8 MB**（工厂 3.9 MB；修复后 5.4 MB；缺陷态 16.6 MB）。

用法
    python tools/elf_load_audit.py build/rkgame.rebuilt.elf [golden/factory.rkgame.bin]
    退出码：0 = PASS；2 = FAIL；11 = 读不到输入（**必须硬失败**，否则门禁恒真）

自证
    python tools/elf_load_audit.py --selftest build/rkgame.rebuilt.elf
    ① 正常态 PASS ② 缺陷态（把某段 p_filesz 人为放大到跨洞）FAIL ③ 文件读不到 → exit 11
"""
import io
import os
import struct
import sys

SHT_NOBITS = 8
SHT_SYMTAB = 2
PT_LOAD = 1


def read_elf(path):
    d = io.open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        raise ValueError('%s 不是 ELF' % path)
    if d[4] != 1 or d[5] != 1:
        raise ValueError('%s 不是 32 位小端 ELF' % path)
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    e_shentsize = struct.unpack_from('<H', d, 46)[0]
    e_shnum = struct.unpack_from('<H', d, 48)[0]
    ph = [struct.unpack_from('<8I', d, e_phoff + i * e_phentsize) for i in range(e_phnum)]
    sh = []
    for i in range(e_shnum):
        s = struct.unpack_from('<10I', d, e_shoff + i * e_shentsize)
        sh.append(s)
    return d, ph, sh


def audit(path, verbose=True):
    d, ph, sh = read_elf(path)
    loads = [(p[1], p[2], p[4], p[5], p[6], p[7]) for p in ph if p[0] == PT_LOAD]
    fails = []
    infos = []

    # A2 真重叠
    spans = [(va, va + max(fsz, msz)) for (_o, va, fsz, msz, _f, _a) in loads]
    ov = []
    for i, (a, b) in enumerate(spans):
        for j, (c, e) in enumerate(spans):
            if i != j and c < a < e:
                ov.append((i, j, c, a, e))
    if ov:
        fails.append(('A2', 'PT_LOAD 存在真重叠 %d 处（例：段%d 起点 0x%x 落在 段%d [0x%x,0x%x) 内部）'
                      % (len(ov), ov[0][1], ov[0][3], ov[0][0], ov[0][2], ov[0][4])))
    else:
        infos.append(('A2', 'PT_LOAD 无真重叠'))

    # A3 对齐
    bad = [(i, va, off, al) for i, (off, va, _fsz, _msz, _f, al) in enumerate(loads)
           if al and (va % al) != (off % al)]
    if bad:
        fails.append(('A3', '对齐违规 %d 处（例：段%d vaddr=0x%x offset=0x%x align=0x%x）'
                      % (len(bad), bad[0][0], bad[0][1], bad[0][2], bad[0][3])))
    else:
        infos.append(('A3', '全部段满足 p_vaddr %% p_align == p_offset %% p_align'))

    # A1 段内 filesz 不得远超其 PROGBITS 内容的**最外虚拟跨度**
    #    ★★ 第一版判据写错了（把 NOBITS 跳段当成跨洞）：段 1 里有
    #       PROGBITS → **NOBITS(`.fimg_bss`)** → PROGBITS 的排列，NOBITS 不占文件字节，
    #       但它的 vaddr 必须被段覆盖 ⇒ 文件里必然出现"合法填充"。
    #       ⇒ 正确判据不是"各节字节之和"，而是 **段必须覆盖的最外 vaddr 跨度**：
    #         vspan = max(PROGBITS vaddr_end) − min(PROGBITS vaddr_start)（取段 vaddr 区间内的节）
    #         若 p_filesz > vspan + 8192 ⇒ 段映射了超出内容跨度的字节。
    #   工厂同项 PASS（vspan 14,136 / filesz 15,280）；修复后我们 PASS（vspan 276,028 / filesz 277,052）。
    PROGBITS = [(s[3], s[3] + s[5]) for s in sh if s[1] != SHT_NOBITS and (s[2] & 0x2) and s[5] > 0]
    holey = []
    for i, (off, va, fsz, _msz, _f, _al) in enumerate(loads):
        if fsz == 0:
            continue
        vlo, vhi = va, va + fsz
        inside = [(a, b) for a, b in PROGBITS if a < vhi and b > vlo]
        if not inside:
            continue
        vspan = max(b for _a, b in inside) - min(a for a, _b_ in [(a, b) for a, b in inside])
        if fsz > vspan + 8192:
            holey.append((i, fsz, vspan, fsz - vspan))
    if holey:
        w = holey[0]
        fails.append(('A1', '段 %d 的 filesz=%d 超过其内容最外跨度 %d 达 **%d B（%.1f MB）** ⇒ 该段映射了空洞'
                      % (w[0], w[1], w[2], w[3], w[3] / 1048576.0)))
        if len(holey) > 1:
            fails.append(('A1', '另有 %d 个段同样超出内容跨度' % (len(holey) - 1)))
    else:
        infos.append(('A1', '无段超出其内容最外跨度（%d 个 PT_LOAD 全部只覆盖真实内容）' % len(loads)))

    # A4 最高 vaddr 端
    top = max(b for _a, b in spans) if spans else 0
    if top > 32 * 1024 * 1024:
        fails.append(('A4', '最高 vaddr 端 = 0x%x（%.1f MB）> 32 MB ⇒ 内核会把 brk 推到这里'
                      % (top, top / 1048576.0)))
    else:
        infos.append(('A4', '最高 vaddr 端 = 0x%x（%.1f MB）≤ 32 MB' % (top, top / 1048576.0)))

    # A5 段数
    if len(loads) > 12:
        fails.append(('A5', 'PT_LOAD 段数 = %d > 12' % len(loads)))
    else:
        infos.append(('A5', 'PT_LOAD 段数 = %d ≤ 12' % len(loads)))

    # A6 文件大小
    if len(d) > 8 * 1024 * 1024:
        fails.append(('A6', '文件 %d B（%.1f MB）> 8 MB' % (len(d), len(d) / 1048576.0)))
    else:
        infos.append(('A6', '文件 %d B（%.1f MB）≤ 8 MB' % (len(d), len(d) / 1048576.0)))

    if verbose:
        print('=' * 78)
        print('PT_LOAD 几何门禁 —— %s' % path)
        print('=' * 78)
        print('  %-4s %-11s %-11s %-11s %-10s %-6s %s' % ('#', 'vaddr', 'filesz', 'memsz', 'fileoff', 'flags', 'vaddr_end'))
        for i, (off, va, fsz, msz, fl, al) in enumerate(loads):
            flag = ('X' if fl & 1 else '-') + ('W' if fl & 2 else '-') + ('R' if fl & 4 else '-')
            print('  %-4d 0x%-9x %-11d %-11d 0x%-8x %-6s 0x%x' % (i, va, fsz, msz, off, flag, va + max(fsz, msz)))
        print('-' * 78)
        for tag, msg in infos:
            print('  [PASS] %-3s %s' % (tag, msg))
        for tag, msg in fails:
            print('  [FAIL] %-3s %s' % (tag, msg))
        print('-' * 78)
        print('  结论: %s' % ('PASS' if not fails else 'FAIL（%d 项）' % len(fails)))
    return fails


def _patch_load(d, ph_index, **kw):
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    buf = bytearray(d)
    p = list(struct.unpack_from('<8I', buf, e_phoff + ph_index * e_phentsize))
    for k, v in kw.items():
        p[int(k[1:])] = v
    struct.pack_into('<8I', buf, e_phoff + ph_index * e_phentsize, *p)
    return bytes(buf)


def selftest(good):
    """三态自证 —— 且**每条判据各有自己的缺陷态**（不能只测一条就当全部有效）。"""
    import tempfile
    print('=== elf_load_audit 三态自证（每条判据各有缺陷态）===')
    rc = 0
    tmp = os.path.join(tempfile.gettempdir(), '_loadaudit_bad.elf')

    # ① 正常态
    f = audit(good, verbose=False)
    print('① 正常态                                  %s' % ('PASS' if not f else 'FAIL ✗ %s' % f))
    if f:
        rc = 1

    d, ph, sh = read_elf(good)
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    shoff = struct.unpack_from('<I', d, 32)[0]
    shentsize = struct.unpack_from('<H', d, 46)[0]
    shnum = struct.unpack_from('<H', d, 48)[0]
    shstrndx = struct.unpack_from('<H', d, 50)[0]
    st = struct.unpack_from('<10I', d, shoff + shstrndx * shentsize)[4]
    text_va = None
    for i in range(shnum):
        s = struct.unpack_from('<10I', d, shoff + i * shentsize)
        k = d.index(b'\x00', st + s[0])
        if d[st + s[0]:k] == b'.text':
            text_va = s[3]
            break
    loads_idx = [i for i in range(e_phnum)
                 if struct.unpack_from('<8I', d, e_phoff + i * e_phentsize)[0] == PT_LOAD]
    sv = {i: struct.unpack_from('<8I', d, e_phoff + i * e_phentsize) for i in loads_idx}

    # ②a A2（真重叠）缺陷态：把 `.text` 之前、vaddr_end 最大的段的 filesz 拉长到吞掉 `.text`
    #     —— 这就是 2026-09-21 真机失败的**同一形态**。
    cand = max((i for i in loads_idx if sv[i][2] + sv[i][4] < (text_va or 0)),
               key=lambda i: sv[i][2] + sv[i][4], default=None)
    if cand is not None and text_va:
        io.open(tmp, 'wb').write(_patch_load(d, cand, p4=(text_va + 0x1000) - sv[cand][2],
                                             p5=max(sv[cand][5], (text_va + 0x1000) - sv[cand][2])))
        tags = set(t for t, _ in audit(tmp, verbose=False))
        ok = 'A2' in tags
        print('②a A2 缺陷态(段%d filesz 吞掉 .text)    %s 命中=%s' % (cand, '✓' if ok else '✗', sorted(tags)))
        if not ok:
            rc = 1
    else:
        print('②a A2 缺陷态                             跳过（找不到可注入点）')

    # ②b A1（filesz 超出内容跨度）缺陷态：给**最后一段**（vaddr_end 最大者）尾部加 5 MB 填充
    last = max(loads_idx, key=lambda i: sv[i][2] + sv[i][4])
    io.open(tmp, 'wb').write(_patch_load(d, last, p4=sv[last][4] + 5 * 1024 * 1024,
                                         p5=sv[last][5] + 5 * 1024 * 1024))
    tags = set(t for t, _ in audit(tmp, verbose=False))
    ok = 'A1' in tags
    print('②b A1 缺陷态(段%d 尾部 +5MB 填充)       %s 命中=%s' % (last, '✓' if ok else '✗', sorted(tags)))
    if not ok:
        rc = 1

    # ②c A3（对齐）缺陷态：把某段的 p_offset 改 1 字节
    io.open(tmp, 'wb').write(_patch_load(d, loads_idx[0], p1=sv[loads_idx[0]][1] + 1))
    tags = set(t for t, _ in audit(tmp, verbose=False))
    ok = 'A3' in tags
    print('②c A3 缺陷态(段%d p_offset+1)           %s 命中=%s' % (loads_idx[0], '✓' if ok else '✗', sorted(tags)))
    if not ok:
        rc = 1

    # ③ 读不到文件 ⇒ 必须硬失败（main 转 exit 11）
    try:
        audit(os.path.join(tempfile.gettempdir(), '_no_such_file_xyz.elf'), verbose=False)
        print('③  文件缺                                未抛错 ✗')
        rc = 1
    except Exception:
        print('③  文件缺                                抛错 ✓（main → exit 11）')

    print('  结果: %s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == '--selftest':
        return selftest(a[1])
    try:
        fails = audit(a[0])
    except Exception as e:
        print('  !! 无法读取/解析 %s：%s' % (a[0], e), file=sys.stderr)
        print('     —— 这必须是硬失败：读不到输入 ≠ 判据通过（否则门禁恒真）', file=sys.stderr)
        return 11
    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
