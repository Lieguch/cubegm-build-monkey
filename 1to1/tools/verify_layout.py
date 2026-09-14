#!/usr/bin/env python3
"""
verify_layout.py — P3 布局校验：重建 ELF 的数据符号地址 vs 工厂权威账本。

门禁口径（按绑定区分，这是唯一有意义的口径）：
  · 全局（g）符号 —— **硬门禁**：外部契约（驱动/其他模块/烧死的绝对地址）依赖它们，
    必须与工厂逐位一致。
  · 局部（l）符号 —— **信息项**：内部链接（static）对象，外部不可见；我们的编译单元
    自带私有副本（zlib/mp3/mxml 的常量表等），地址不同不影响行为，仅作统计。

★ 重名符号（P3 二期④，2026-09-13）
----------------------------------
工厂 4 个名字各存在**同名的两份**（分属不同编译单元）。我们按「实测 TU 归属」拆成
不同符号名（见 tools/xref_scan.py / tools/dup_assign.py，报告 report/xref_dup.txt），
本脚本据此把账本的每个 (名字,地址) 映射到我们 ELF 中对应的那个符号：

  账本条目                     我们的符号              归属（实测）
  handle        @0x3b21c8  →  handle                 os_windows_rk.c static（4 个函数）
  handle        @0x3cf988  →  handle_emurun          EmuRun.c static（17 个函数）
  diff_prev     @0x3bc414  →  diff_prev              ui_jkt.c static（15 个函数）
  diff_prev     @0x3e1a38  →  diff_prev_global       GLOBAL（4 个函数经 GOT）
  SoundBuffer   @0x3ceaf0  →  SoundBuffer            ui_jkt.c static（AudioProcess）
  SoundBuffer   @0x3e1944  →  SoundBuffer_global     GLOBAL（实测零引用 = DEAD）
  ArchivePath   @0x3ae610  →  ArchivePath            ui_jkt.c static（4 个函数）
  ArchivePath   @0x3e18d4  →  ArchivePath_global     GLOBAL（实测零引用 = DEAD）

输入： <rebuilt.elf> <factory_globals.tsv>
退出码：0 = 全局符号全部一致；2 = 有全局偏差

★ 附加门禁「命名自洽」（NAME_ENC）
--------------------------------
Ghidra 与我们的别名体系里，`UNK_<hex>` / `DAT_<hex>` 这类名字**把地址编进了名字**。
因此有一条零成本的强不变式：**凡形如 `UNK_xxxxxxxx` / `DAT_xxxxxxxx` 的符号，
其符号值必须等于 xxxxxxxx**。任何别名算错偏移都会在这里立刻暴露
（例：UNK_000d2f00 曾因缺 .text 镜像而被链接脚本显式置 0 → 指向地址 0 的运行期地雷）。
"""
import os
import re
import struct
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

NAME_ENC = re.compile(r'^(?:UNK|DAT)_([0-9a-fA-F]{6,8})$')

# 账本 (名字, 地址) → 我们 ELF 里的符号名
ALIAS = {
    ('handle', 0x3b21c8): 'handle',
    ('handle', 0x3cf988): 'handle_emurun',
    ('diff_prev', 0x3bc414): 'diff_prev',
    ('diff_prev', 0x3e1a38): 'diff_prev_global',
    ('SoundBuffer', 0x3ceaf0): 'SoundBuffer',
    ('SoundBuffer', 0x3e1944): 'SoundBuffer_global',
    ('ArchivePath', 0x3ae610): 'ArchivePath',
    ('ArchivePath', 0x3e18d4): 'ArchivePath_global',
}
# 已知不可镜像的 CRT 内部对象
ACCEPT = {
    '_IO_stdin_used': 'glibc CRT 内部对象（镜像按设计跳过头部 4B，由 crtbegin 提供）',
}


def read_ledger(p):
    rows = []
    for i, line in enumerate(open(p, encoding='utf-8', errors='replace')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 5:
            continue
        try:
            rows.append((f[0], int(f[1], 16), f[4]))
        except ValueError:
            continue
    return rows


def read_elf_syms(path):
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    out = {}
    for i in range(n):
        o = e_shoff + i * es
        sh = struct.unpack_from('<10I', d, o)
        if sh[1] != 2:      # SHT_SYMTAB
            continue
        stroff = struct.unpack_from('<10I', d, e_shoff + sh[6] * es)[4]
        ent = sh[9] or 16
        for j in range(sh[5] // ent):
            so = sh[4] + j * ent
            nm, val, sz, info, other, shndx = struct.unpack_from('<IIIBBH', d, so)
            if nm == 0 or shndx in (0, 0xFFF2):
                continue
            e = d.index(b'\x00', stroff + nm)
            name = d[stroff + nm:e].decode('utf-8', 'replace')
            out.setdefault(name, val)
    return out


def load_segments(path):
    """PT_LOAD 的 [vaddr, vaddr+memsz) 区间 —— 运行期真正可访问的地址空间。"""
    d = open(path, 'rb').read()
    phoff = struct.unpack_from('<I', d, 28)[0]
    ents = struct.unpack_from('<H', d, 42)[0]
    num = struct.unpack_from('<H', d, 44)[0]
    segs = []
    for i in range(num):
        o = phoff + i * ents
        p_type, p_off, p_va, p_pa, p_fsz, p_msz, p_fl, p_al = struct.unpack_from('<8I', d, o)
        if p_type == 1 and p_msz:                       # PT_LOAD
            segs.append((p_va, p_va + p_msz))
    return segs


def read_factory_loads(tsv):
    """读 ledger/factory_phdrs.tsv → [(va, memsz, flags, align), ...]（仅 PT_LOAD）。
    返回 (loads, low_va, align)；文件不存在时返回 (None, None, None)。"""
    if not tsv or not os.path.exists(tsv):
        return None, None, None
    loads = []
    for line in open(tsv, encoding='utf-8', errors='replace'):
        if line.startswith('#') or not line.strip():
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 7 or f[0] != 'LOAD':
            continue
        loads.append((int(f[2], 16), int(f[4]), int(f[5], 16), int(f[6], 16)))
    if not loads:
        return None, None, None
    return loads, min(l[0] for l in loads), loads[0][3]


def read_phdrs(path):
    """完整程序头表：[(type, off, vaddr, filesz, memsz, flags, align), ...]"""
    d = open(path, 'rb').read()
    phoff = struct.unpack_from('<I', d, 28)[0]
    ents = struct.unpack_from('<H', d, 42)[0]
    num = struct.unpack_from('<H', d, 44)[0]
    out = []
    for i in range(num):
        o = phoff + i * ents
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        out.append((t, off, va, fsz, msz, fl, al))
    return out


def read_sections(path):
    """SHF_ALLOC 且 size>0 的节：[(name, addr, size, type, flags), ...]"""
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    si = struct.unpack_from('<H', d, 50)[0]
    stroff = struct.unpack_from('<I', d, e_shoff + si * es + 16)[0]
    out = []
    for i in range(n):
        o = e_shoff + i * es
        nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from('<10I', d, o)
        e = d.index(b'\x00', stroff + nm)
        name = d[stroff + nm:e].decode('utf-8', 'replace')
        if (fl & 0x2) and size:
            out.append((name, addr, size, typ, fl))
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    elf, ledger = sys.argv[1], sys.argv[2]
    want = read_ledger(ledger)
    got = read_elf_syms(elf)

    stat = collections.defaultdict(lambda: [0, 0, 0])
    bad_g, bad_l, miss = [], [], []
    split_hits = []
    for name, addr, bind in want:
        k = 'g' if bind == 'g' else 'l'
        sym = ALIAS.get((name, addr), name)
        if sym != name:
            split_hits.append((name, addr, sym))
        v = got.get(sym)
        if v is None:
            if name in ACCEPT:
                continue
            stat[k][2] += 1
            miss.append((sym, addr, bind))
        elif v == addr:
            stat[k][0] += 1
        else:
            stat[k][1] += 1
            (bad_g if k == 'g' else bad_l).append((sym, addr, v))

    L = []
    A = L.append
    A('=' * 70)
    A('P3 布局校验：%s' % os.path.basename(elf))
    A('=' * 70)
    A('账本符号数 : %d    （其中重名拆分条目 %d）' % (len(want), len(split_hits)))
    A('')
    A('%-10s %8s %8s %8s' % ('绑定', '一致', '偏差', '缺失'))
    for k, label in (('g', '全局 g'), ('l', '局部 l')):
        A('%-10s %8d %8d %8d' % (label, stat[k][0], stat[k][1], stat[k][2]))
    tot_g = sum(stat['g'])
    tot_l = sum(stat['l'])
    A('')
    A('★ 全局符号命中率 : %.1f%%  (%d/%d)   ← 硬门禁'
      % (100.0 * stat['g'][0] / max(1, tot_g), stat['g'][0], tot_g))
    A('  局部符号命中率 : %.1f%%  (%d/%d)   信息项（内部链接对象无外部契约）'
      % (100.0 * stat['l'][0] / max(1, tot_l), stat['l'][0], tot_l))
    A('')
    if split_hits:
        A('--- 重名拆分映射（账本 → 我们的符号）---')
        for n, a, s in sorted(split_hits, key=lambda x: x[1]):
            ok = '一致' if got.get(s) == a else ('缺失' if s not in got else '偏差')
            A('  %-14s @0x%08x  →  %-20s %s' % (n, a, s, ok))
        A('')

    real_bad = [x for x in bad_g if x[0] not in ACCEPT]

    # ---- 附加门禁：命名自洽（名字里编码的地址 == 符号值）----
    nenc, enc_bad = 0, []
    for nm, v in got.items():
        m = NAME_ENC.match(nm)
        if m:
            nenc += 1
            want = int(m.group(1), 16)
            if v != want:
                enc_bad.append((nm, want, v))
    A('--- 命名自洽门禁（UNK_/DAT_<hex> 的符号值必须 == 名字里的地址）---')
    A('  受检符号 %d 个；不符 %d 个' % (nenc, len(enc_bad)))
    for nm, want, v in enc_bad[:20]:
        A('  %-28s 名字 0x%08x 实际 0x%08x Δ%+d' % (nm, want, v, v - want))
    A('')

    # ---- 附加门禁：可映射性（符号值必须落在某个 PT_LOAD 内）----
    # ★ 边界口径：PT_LOAD 的 [vaddr, vaddr+memsz) 是**左闭右开**，但链接器定义的段尾标记
    #   （`__TMC_END__` / `_end` / `__bss_start` 等）按约定就落在「最后一字节之后」。
    #   故判定用 `lo <= v <= hi`（含终点），仍然能抓住真正的地雷 —— 落在**空洞**里的地址
    #   （例：曾把 UNK_* 置 0、或镜像尾部掉进无 LOAD 覆盖的缝隙）。实测该口径下
    #   本地 0 越界、CI（GCC/binutils ld）也只有 `__TMC_END__` 这一个边界标记，现已消除误报。
    segs = load_segments(elf)
    unmapped = []
    for nm, v in got.items():
        if not v:
            continue
        if not any(lo <= v <= hi for lo, hi in segs):
            unmapped.append((nm, v))
    A('--- 可映射性门禁（符号值必须落在 PT_LOAD 内，否则运行期访问即段错）---')
    A('  PT_LOAD 段数 %d；覆盖 %s' % (len(segs),
                                    ', '.join('0x%08x..0x%08x' % s for s in segs[:6])))
    A('  越界符号 %d 个' % len(unmapped))
    for nm, v in unmapped[:20]:
        A('  %-28s 0x%08x 不在任何 LOAD 段内' % (nm, v))
    A('')

    # ---- 程序头全量（本地 zig/lld 与 CI GCC/binutils 的段划分不同，必须能看到原件）----
    phdrs = read_phdrs(elf)
    rsegs = [(va, va + msz) for t, off, va, fsz, msz, fl, al in phdrs if t == 1 and msz]
    TAG = {1: 'LOAD', 2: 'DYNAMIC', 3: 'INTERP', 4: 'NOTE', 6: 'PHDR',
           0x6474e550: 'GNU_EH_FRAME', 0x6474e551: 'GNU_STACK',
           0x6474e552: 'GNU_RELRO', 0x70000001: 'ARM_EXIDX'}
    A('--- 程序头全量表（%d 条）---' % len(phdrs))
    for t, off, va, fsz, msz, fl, al in phdrs:
        A('  %-14s off=0x%08x va=0x%08x..0x%08x filesz=%-9d memsz=%-9d fl=0x%x al=0x%x'
          % (TAG.get(t, hex(t)), off, va, va + msz, fsz, msz, fl, al))
    A('')

    # ---- 附加门禁：节覆盖（SHF_ALLOC 节必须完整落在某个 PT_LOAD 内）----
    secs_alloc = read_sections(elf)
    bad_sec = []
    for name, addr, size, typ, fl in secs_alloc:
        if not any(lo <= addr and addr + size <= hi for lo, hi in rsegs):
            bad_sec.append((name, addr, size))
    A('--- 节覆盖门禁（SHF_ALLOC 节必须完整落在某个 PT_LOAD 内）---')
    A('  受检节 %d 个；未完全覆盖 %d 个' % (len(secs_alloc), len(bad_sec)))
    for name, addr, size in bad_sec[:20]:
        A('  %-24s 0x%08x..0x%08x (%d B) 未完全覆盖' % (name, addr, addr + size, size))
    A('')

    # ---- 附加门禁：镜像尾部 slack（★★ 真实差分抓到的地雷）----
    # 工厂进程的 `.bss` 之后**紧邻堆**（brk 落在 .bss 末页：实测工厂 brk=0x003e2000，
    # .bss 结束 0x003e1ad3），所以「往 .bss 里的小缓冲区传大 bufsiz」是安全的
    # （例：readlink("/proc/self/exe", work_path, 4096)）。我们的重建产物把运行时区放到
    # 0x400000/0x5000000，brk 变成 0x0503e000 ⇒ work_path+4096 的尾部落到**未映射空洞**，
    # qemu 校验整段 bufsiz ⇒ EFAULT ⇒ work_path 全空、路径全错、行为整体发散。
    # ⇒ 门禁：每个 .fimg_* 镜像之后必须仍有 ≥ SLACK 的已映射内存。
    # 口径：只查**镜像区的最后一段**（工厂的 .bss）。内部各段之间的间隙是工厂原版就有的
    # （例：工厂 .rodata 结束 0x3ad008 与 .data.rel.ro.local 0x3ae5c4 之间本就有一处空洞），
    # 逐段要求 slack 会把"忠实复刻工厂布局"误判成缺陷。
    # 真正必须成立的是：**镜像区末尾之后仍有 ≥SLACK 的已映射内存** —— 因为工厂进程里
    # 紧接着 .bss 的是堆（brk），任何"往 .bss 里的小缓冲区传大 bufsiz"的调用都依赖它。
    SLACK = 0x1000
    fimg_secs = [x for x in secs_alloc if x[0].startswith('.fimg_')]
    real = sorted([x for x in fimg_secs if x[0] != '.fimg_bss_pad'], key=lambda x: x[1])
    short = []
    if real:
        name, addr, size, typ, fl = real[-1]
        need = addr + size + SLACK
        if not any(lo <= addr and hi >= need for lo, hi in rsegs):
            best = max([hi for lo, hi in rsegs if lo <= addr] or [addr])
            short.append((name, addr + size, best, need - best))
    # ---- 附加门禁：段保真度（★★ 真实差分抓到的第二条假分歧）----
    # 工厂首个 PT_LOAD 从 0x8000 起（p_align=0x1000）⇒ 地址 [0,0x8000) 在工厂进程里是**空洞**。
    # 若我们的 ELF 把首段放在 0x0（p_align=0x10000 时链接器会向下取整到 0），且该段可写，
    # 那么「NULL 指针写」会**静默成功**而不是 SIGSEGV —— 实测 sunxi_gpio_set_cfgpin 里
    # `*(u32*)(GPIO2+4) |= 8`（GPIO2=NULL）就走这条岔路，导致行为差分报出一条假分歧。
    fleads, flow, falign = read_factory_loads(
        os.path.join(os.path.dirname(ledger), 'factory_phdrs.tsv'))
    seg_bad = []
    if fleads:
        for t, off, va, fsz, msz, fl, al in phdrs:
            if t != 1 or not msz:
                continue
            if flow is not None and va < flow:
                seg_bad.append(('低地址被映射', '0x%08x..0x%08x' % (va, va + msz),
                                '工厂最低 LOAD 是 0x%08x（[0,0x%08x) 应是空洞）' % (flow, flow)))
            if (fl & 2) and (fl & 1):
                seg_bad.append(('RWX 段', '0x%08x..0x%08x' % (va, va + msz),
                                '工厂没有任何 W∧X 的 LOAD'))
            if falign and al != falign:
                seg_bad.append(('LOAD 对齐不符', '0x%08x..0x%08x' % (va, va + msz),
                                '工厂 p_align=0x%x，本产物 0x%x' % (falign, al)))
        A('--- 段保真度门禁（地址空洞 / W^X / p_align，基准 = 工厂程序头台账）---')
        A('  基准：工厂最低 LOAD 0x%08x、p_align 0x%x；LOAD 条数 %d vs 工厂 %d'
          % (flow, falign, len([1 for x in phdrs if x[0] == 1 and x[4]]), len(fleads)))
        A('  违规 %d 项' % len(seg_bad))
        for kind, rng, why in seg_bad[:20]:
            A('  [%-14s] %-22s %s' % (kind, rng, why))
        A('')
    else:
        A('--- 段保真度门禁：跳过（未找到 factory_phdrs.tsv）---')
        A('')

    A('--- 镜像尾部 slack 门禁（镜像区最后一段结束后必须仍有 ≥0x%x 已映射内存）---' % SLACK)
    A('  镜像节 %d 个（未尾段 %s）；slack 不足 %d 个'
      % (len(fimg_secs), real[-1][0] if real else '(无)', len(short)))
    for name, end, cov_to, lack in short[:20]:      # ★ 变量名勿用 miss：上层已有同名列表
        A('  %-24s 结束 0x%08x 仅覆盖到 0x%08x（缺 %d B）' % (name, end, cov_to, lack))
    A('')

    if bad_g:
        A('--- 全局偏差明细（%d）---' % len(bad_g))
        for n, a, b in bad_g[:40]:
            tag = '   [可接受] %s' % ACCEPT[n] if n in ACCEPT else ''
            A('  %-28s 工厂 0x%08x 重建 0x%08x Δ%+d%s' % (n, a, b, b - a, tag))
        A('')
    if bad_l:
        A('--- 局部偏差样例（前 12 / 共 %d，信息项）---' % len(bad_l))
        for n, a, b in bad_l[:12]:
            A('  %-28s 工厂 0x%08x 重建 0x%08x' % (n, a, b))
        A('')
    if miss:
        A('--- 缺失（%d）---' % len(miss))
        for n, a, bind in miss[:12]:
            A('  %-28s 工厂 0x%08x (%s)' % (n, a, bind))
        A('')

    nfail = (len(real_bad) + len(enc_bad) + len(unmapped) + len(bad_sec)
             + len(short) + len(seg_bad))
    verdict = ('PASS' if nfail == 0
               else 'FAIL（全局地址不符 %d / 命名自洽失败 %d / 越 LOAD 段 %d / 节未覆盖 %d / 镜像 slack %d / 段保真 %d）'
                    % (len(real_bad), len(enc_bad), len(unmapped), len(bad_sec), len(short), len(seg_bad)))
    A('结论: %s' % verdict)
    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    rep = os.path.join(ROOT, 'report', 'verify_layout.txt')
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    open(rep, 'w', encoding='utf-8').write(txt)
    return 0 if nfail == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
