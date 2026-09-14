#!/usr/bin/env python3
"""
gen_data_module.py — P3 数据段供应：生成「工厂镜像 + 符号别名」汇编与链接脚本。

原理（为什么必须这样做）：
  1) 反编译代码里**烧死了绝对地址**（如 `DrawSelectBar((int *)0x3afc44)`），所以段必须
     落在工厂相同 VMA：.rodata/.data/.bss 的地址由链接脚本固定。
  2) Ghidra 的 `DAT_xxxxxxxx` **不是工厂符号**——工厂真符号是大对象（`m_ui` size 1508 等），
     Ghidra 给其内部每个访问点另起了名字。若把它们各自独立定义，链接后各占空间 ⇒
     破坏原厂布局。
     ⇒ 做法：**每个段只放一份工厂原始镜像**，所有符号（含 `DAT_x`）一律用
        `.set NAME, <段基址符号> + <偏移>` 定义为**别名**，不额外分配空间。

输入：
  --elf       工厂 ELF
  --layout    ledger/factory_layout.tsv
  --globals   ledger/factory_globals.tsv（940 个权威数据对象）
  --missing   report/_link_missing.txt（MISSING 名单）
输出（默认）：
  src/data/factory_image.S           段镜像 + 全部符号别名
  src/data/factory_rodata.bin        工厂 .rodata 原始字节
  src/data/factory_data.bin          工厂 .data  原始字节
  linker/factory.ld                  复刻工厂 VMA 的链接脚本
"""
import argparse
import os
import re
import sys

# 只镜像这三段。.init_array/.fini_array 交给链接器（crtbegin 会填正确构造子），
# 否则会把工厂的构造函数地址搬过来 → 指向错的代码；但符号仍要 PROVIDE 到段首。
# SKIP_HEAD[section] = 跳过头部字节数（交由 CRT 提供，避免与 crt1.o 重复定义）
SKIP_HEAD = {'.rodata': 4}
# ★ 镜像段使用自定义名 .fimg_*：与编译产物的常规段（.rodata/.data/.bss）分离，
#   这样链接脚本能把「工厂地址区」和「我们自己+libc 的段」放到不同地址，互不重叠。
FIMG = {'.text': '.fimg_text',
        '.rodata': '.fimg_rodata',
        '.data.rel.ro_local': '.fimg_data_rel_ro_local',
        '.data.rel.ro.local': '.fimg_data_rel_ro_local',
        '.data': '.fimg_data',
        '.bss': '.fimg_bss'}
SEC_DEF = [('.text', 'a', 'progbits', None),
           ('.rodata', 'a', 'progbits', None),
           ('.data.rel.ro.local', 'aw', 'progbits', None),
           ('.data', 'aw', 'progbits', None),
           ('.bss', 'aw', 'nobits', None)]

# ★★ 工厂 .text 的**声明 size 越界**：0x9b10 + 0x2D21B8 = 0x2DBCC8，已经压到
#    .fini(0x2dbc98) 与 .rodata(0x2dbca0) 上。镜像必须在上一个真实节之前收尾，
#    否则会把 .fini/.rodata 的头 0x30 字节一起吞进 .fimg_text。
#    依据：工厂节表实测（.fini file off 0x2d3c98 / .rodata file off 0x2d3ca0）。
MIRROR_END = {'.text': 0x2dbc98}

# ★★ 镜像尾部 slack（页对齐的一整块零页）
#   血泪（P5 第一轮真实差分）：工厂进程里 `.bss` 之后**紧邻堆**（brk 就落在 .bss 末尾的下一页，
#   实测工厂 brk=0x003e2000、.bss 结束于 0x003e1ad3），所以「对 .bss 里的小缓冲区传一个大
#   bufsiz」是安全的 —— 例：get_executable_path() 里 readlink("/proc/self/exe", work_path, 4096)，
#   工厂 readlink 返回 21；而我们的重建产物把运行时区放到了 0x400000/0x5000000，brk 变成
#   0x0503e000 ⇒ work_path+4096 的尾部落进**未映射空洞** ⇒ qemu（会校验整段 bufsiz）
#   返回 -1 EFAULT ⇒ work_path 保持空 ⇒ directory/appname 空、路径全错、后续行为整体发散。
#   ⇒ 在 .fimg_bss 之后补一页对齐的零填充段，恢复「bss 之后有已映射内存」这一进程镜像性质。
#   （核引擎只在真正写入的字节上校验，qemu 更严格；补 slack 对两者都安全。）
BSS_PAD = 0x10000          # 64 KiB


def bss_pad_vma(secs):
    """零填充段的 VMA：.fimg_bss 结束地址向上页对齐。"""
    b = secs['.bss']
    end = b['addr'] + b['size']
    return (end + 0xFFF) & ~0xFFF

# ★ 重名符号拆分（P3 二期④）。同名两份：一份是某 TU 的 static，一份是全局。
#   归属由 tools/xref_scan.py 的指令级交叉引用 + tools/dup_assign.py 的 TU 投票实测确定
#   （报告 report/xref_dup.txt / report/dup_assign.tsv）。此处补「非主名」那一份的别名。
#
#   | 名字          | 主名(globals.h)          | 拆分别名            | 依据 |
#   | handle        | 0x3b21c8 os_windows_rk.c | 0x3cf988 EmuRun.c   | 4 vs 17 个引用函数 |
#   | diff_prev     | 0x3bc414 ui_jkt.c        | 0x3e1a38 GLOBAL     | 15 static vs 4 经 GOT |
#   | SoundBuffer   | 0x3ceaf0 ui_jkt.c        | 0x3e1944 GLOBAL     | 全局份零引用（DEAD）|
#   | ArchivePath   | 0x3ae610 ui_jkt.c        | 0x3e18d4 GLOBAL     | 全局份零引用（DEAD）|
SPLIT_ALIASES = {
    'handle_emurun':      (0x3cf988, '.bss'),
    'diff_prev_global':   (0x3e1a38, '.bss'),
    'SoundBuffer_global': (0x3e1944, '.bss'),
    'ArchivePath_global': (0x3e18d4, '.bss'),
}
# 由链接器生成（不占独立空间）
LINKER_DEFINED = {'__frame_dummy_init_array_entry': '.init_array',
                  '__do_global_dtors_aux_fini_array_entry': '.fini_array'}
RE_DAT = re.compile(r'^DAT_([0-9a-fA-F]{6,8})$')
# ★ UNK_<hex>：Ghidra 对「落在未命名区域」的地址起的合成名（工厂 .text 段内
#   的只读数据表就是这种情况：实测 0xD2F00/0x118000 都是 .word 表，不是代码）。
RE_UNK = re.compile(r'^UNK_([0-9a-fA-F]{6,8})$')


def load_layout(p):
    out = {}
    for i, line in enumerate(open(p, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 8 or f[0] != 'SH':
            continue
        out[f[1]] = dict(addr=int(f[2], 16), size=int(f[3], 16),
                         flags=int(f[5], 16), offset=int(f[6], 16))
    return out


def load_globals(p):
    rows = []
    for i, line in enumerate(open(p, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 7:
            continue
        rows.append(dict(name=f[0], addr=int(f[1], 16), size=int(f[2], 16),
                         section=f[3]))
    return rows


def load_missing(p):
    """MISSING 名单加载：兼容两种格式
      ① `MISSING<TAB>name`（link_audit 报告节选）
      ② 裸名字一行一个（report/_undef_all.txt）
    ★ 踩坑：只认格式①时，传裸名单会静默得到空列表 → 别名全部丢失（934→17）。"""
    out = []
    for line in open(p, encoding='utf-8', errors='replace'):
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('/*'):
            continue
        f = s.split('\t')
        if f[0] == 'MISSING' and len(f) >= 2:
            out.append(f[1])
        elif len(f) == 1:
            out.append(f[0])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True)
    ap.add_argument('--layout', required=True)
    ap.add_argument('--globals', required=True)
    ap.add_argument('--missing', required=True)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = a.outdir or root
    datadir = os.path.join(outdir, 'src', 'data')
    linkdir = os.path.join(outdir, 'linker')
    os.makedirs(datadir, exist_ok=True)
    os.makedirs(linkdir, exist_ok=True)

    lay = load_layout(a.layout)
    globs = load_globals(a.globals)
    missing = load_missing(a.missing)

    elf = open(a.elf, 'rb').read()

    # ---- 段范围 ----
    secs = {}
    for nm, fl, ty, _ in SEC_DEF:
        if nm not in lay:
            raise SystemExit('layout 缺段 %s' % nm)
        secs[nm] = lay[nm]

    # ★ 段声明 size 越界收口（.text 见 MIRROR_END 注释）
    for _nm, _end in MIRROR_END.items():
        _s = secs.get(_nm)
        if _s and _s['addr'] + _s['size'] > _end:
            _s['size'] = _end - _s['addr']

    def which_sec(addr, size=1):
        for nm, _, _, _ in SEC_DEF:
            s = secs[nm]
            if s['addr'] <= addr < s['addr'] + s['size']:
                return nm
        return None

    # ---- 提取镜像 ----
    for nm, _, ty, _ in SEC_DEF:
        s = secs[nm]
        if ty == 'nobits':
            continue
        skip = SKIP_HEAD.get(nm, 0)
        blob = elf[s['offset'] + skip:s['offset'] + s['size']]
        if len(blob) != s['size'] - skip:
            raise SystemExit('段 %s 数据不足' % nm)
        open(os.path.join(datadir, 'factory_%s.bin' % nm.strip('.').replace('.', '_')), 'wb').write(blob)
        print('  提取 %-9s %d 字节' % (nm, len(blob)))

    # ---- 收集符号（去重；同名以工厂账本为准）----
    syms = {}
    skipped_crt = []
    for g in globs:
        if g['name'] in LINKER_DEFINED:
            skipped_crt.append(g['name'])
            continue
        syms.setdefault(g['name'], (g['addr'], g['section']))
    unplaced = []
    for m in missing:
        if m in syms:
            continue
        md = RE_DAT.match(m) or RE_UNK.match(m)
        if not md:
            unplaced.append(m)
            continue
        addr = int(md.group(1), 16)
        s = which_sec(addr)
        if not s:
            unplaced.append(m)
            continue
        syms[m] = (addr, s)

    # ---- 生成汇编 ----
    lines = []
    A = lines.append
    A('/* 自动生成 —— 请勿手改；见 tools/gen_data_module.py')
    A(' * 每个段只放一份工厂原始镜像，全部符号（含 Ghidra DAT_x）以 .set 别名指向段内偏移。')
    A(' * 依据：段 VMA 必须与工厂一致（代码里烧死绝对地址）；DAT_x 不是工厂符号。 */')
    A('')
    for nm, fl, ty, _ in SEC_DEF:
        s = secs[nm]
        A('\t.section %s,"%s",%%%s' % (FIMG[nm], fl, ty))
        A('\t.globl __f%s_base' % nm.replace('.', '_'))
        A('\t.type __f%s_base, %%object' % nm.replace('.', '_'))
        A('__f%s_base:' % nm.replace('.', '_'))
        s['_skip'] = SKIP_HEAD.get(nm, 0)
        bl = nm.strip('.').replace('.', '_')
        if ty == 'nobits':
            A('\t.space 0x%x' % s['size'])
        else:
            if nm in SKIP_HEAD:
                # ★ bin 文件本身已跳过 SKIP_HEAD 字节（gen 时 blob=elf[off+skip:off+size]），
                #   此处不能再 skip —— 否则 GNU as 报错、clang 静默截断尾部 4 字节
                A('\t.incbin "factory_%s.bin"' % bl)
            else:
                A('\t.incbin "factory_%s.bin"' % bl)
        A('\t.size __f%s_base, 0x%x' % (nm.replace('.', '_'), s['size'] - s.get('_skip', 0)))
        A('')
        if nm == '.bss':
            # ★ 见文件头 BSS_PAD 注释：恢复「镜像 .bss 之后仍是已映射内存」这一性质。
            A('\t/* ---- 镜像尾部 slack（%d 字节零填充，页对齐）---- */' % BSS_PAD)
            A('\t.section .fimg_bss_pad,"aw",%progbits')
            A('\t.globl __f_bss_pad_base')
            A('\t.type __f_bss_pad_base, %object')
            A('__f_bss_pad_base:')
            A('\t.zero 0x%x' % BSS_PAD)
            A('\t.size __f_bss_pad_base, 0x%x' % BSS_PAD)
            A('')
    A('/* ---- 符号别名 ---- */')
    per_sec = {nm: [] for nm, _, _, _ in SEC_DEF}
    for name, (addr, sec) in sorted(syms.items(), key=lambda kv: (kv[1][1], kv[1][0])):
        per_sec[sec].append((addr, name))
    total = 0
    for nm, _, _, _ in SEC_DEF:
        A('/* %s：%d 个符号 */' % (nm, len(per_sec[nm])))
        skip = SKIP_HEAD.get(nm, 0)
        for addr, name in per_sec[nm]:
            off = addr - secs[nm]['addr'] - skip
            if off < 0:
                continue      # 位于被跳过的 CRT 头部内（_IO_stdin_used）
            A('\t.globl %s' % name)
            A('\t.set %s, __f%s_base + 0x%x' % (name, nm.replace('.', '_'), off))
            total += 1
        A('')
    A('/* ---- 重名符号拆分别名（P3 二期④）----')
    A(' * 依据：tools/xref_scan.py（A32 PIC 指令级交叉引用）+ tools/dup_assign.py（TU 归属）')
    A(' * 实测报告见 report/xref_dup.txt。同名两份分属不同编译单元，合并会造成静默语义错位。 */')
    for alt in sorted(SPLIT_ALIASES):
        addr, sec = SPLIT_ALIASES[alt]
        off = addr - secs[sec]['addr'] - SKIP_HEAD.get(sec, 0)
        A('\t.globl %s' % alt)
        A('\t.set %s, __f%s_base + 0x%x' % (alt, sec.replace('.', '_'), off))
        total += 1
    A('')
    open(os.path.join(datadir, 'factory_image.S'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

    # ---- 链接脚本 ----
    L = []
    B = L.append
    B('/* 自动生成 —— 复刻工厂 rkgame 的内存映射（tools/gen_data_module.py）')
    B(' * 依据：反编译代码含烧死的绝对地址，段 VMA 必须与工厂逐位一致。 */')
    B('ENTRY(_start)')
    B('')
    B('SECTIONS')
    B('{')
    B('  /* ---- ① 工厂地址区（必须逐位一致：代码里烧死绝对地址）---- */')
    B('  . = 0x00008000;')
    # 工厂镜像段：只匹配 .fimg_*（我们自己/libc 的常规段不会落进来）
    # ★ VMA 一律取「工厂节地址 + SKIP_HEAD」，不再手写常量 —— 节表变动也不会写错。
    # ★ .fimg_text 覆盖整段工厂 .text（含其中 ~2.7MB 的只读数据表，如 UNK_000d2f00/
    #   UNK_00118000）：实测这些地址无符号、无函数，是 Ghidra 的 UNK_<addr> 合成名，
    #   只有「镜像 + .set 别名」能同时保证地址与字节都逐位一致。
    fimg_order = [('.fimg_text', '.text'),
                  ('.fimg_rodata', '.rodata'),
                  ('.fimg_data_rel_ro_local', '.data.rel.ro.local'),
                  ('.fimg_data', '.data'),
                  ('.fimg_bss', '.bss')]
    for fname, sec in fimg_order:
        vma = secs[sec]['addr'] + SKIP_HEAD.get(sec, 0)
        B('  %s 0x%08x : { *(%s) }' % (fname, vma, fname))
    # ★ 尾部 slack：见 BSS_PAD 注释（恢复「.bss 之后仍是已映射内存」的进程镜像性质）
    B('  .fimg_bss_pad 0x%08x : { *(.fimg_bss_pad) }' % bss_pad_vma(secs))
    B('')
    B('  /* ---- ② ELF 元数据（地址无关；排在 ① 之后，避免挤进工厂地址区）---- */')
    B('  . = 0x00400000;')
    B('  .interp : { *(.interp) }')
    B('  .note.ABI-tag : { *(.note.ABI-tag) }')
    B('  .hash : { *(.hash) }')
    B('  .gnu.hash : { *(.gnu.hash) }')
    B('  .dynsym : { *(.dynsym) }')
    B('  .dynstr : { *(.dynstr) }')
    B('  .gnu.version : { *(.gnu.version) }')
    B('  .gnu.version_r : { *(.gnu.version_r) }')
    B('  .rel.dyn : { *(.rel.dyn) }')
    B('  .rel.plt : { *(.rel.plt) }')
    B('  .init : { *(.init) }')
    B('  .plt : { *(.plt) *(.plt.*) }')
    B('')
    B('  /* ---- ③ 运行时区（我们自己 + libc；地址自由，只要不与①②重叠）---- */')
    B('  .rodata 0x00410000 : { *(.rodata) *(.rodata.*) *(.ARM.extab*) *(.gcc_except_table*) }')
    B('  .init_array ALIGN(4) : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(.init_array)) KEEP(*(.init_array.*)) }')
    B('  .fini_array ALIGN(4) : { KEEP(*(.fini_array)) KEEP(*(.fini_array.*)) }')
    B('  .data 0x01000000 : { *(.data) *(.data.*) *(.data.rel.ro) *(.data.rel.ro.*) *(.got) *(.got.*) }')
    B('  .bss 0x02000000 : { *(.bss) *(.bss.*) *(COMMON) }')
    B('  .text 0x05000000 : { *(.text) *(.text.*) *(.fini) }')
    B('  .ARM.exidx : { *(.ARM.exidx) *(.ARM.exidx.*) }')
    B('  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) *(.debug*) *(.ARM.attributes) }')
    B('}')
    B('')
    B('/* ---- ③ 链接期占位 ----')
    B(' * ★★ compress / uncompress：**不再占位**（此前 PROVIDE_HIDDEN(...=0) 把它们绑成 ABS 0）。')
    B(' *   实测：这两个符号被 `retro_save_state` / `retro_load_state`（以及 TestLibz0）调用，')
    B(' *   绑成 0 ⇒ 调用即跳地址 0 ⇒ SIGSEGV（存档/读档功能必崩）。')
    B(' *   工厂的取值方式 = 从 `libz.so.1` **动态导入**（NEEDED libz.so.1）⇒ 现在改为')
    B(' *   在 link_full.sh 里真实链接一个 ARM 版 libz.so.1（`LIBZ=<path>`），产物同样只记')
    B(' *   NEEDED libz.so.1，运行期由设备自己的 libz 解析 —— 与工厂一致。')
    B(' *   若找不到 libz.so.1，link_full.sh 会**显式报错退出**（绝不再静默置 0）。')
    B(' * _init：★ 只能用 PROVIDE_HIDDEN（"别人定义了就不生效"），**绝不能用裸赋值**。')
    B(' *   实测真因：裸赋值 `_init = 0;` 会压掉 crti.o 的真 `_init`，链接器于是在 .dynamic 写下')
    B(' *   `DT_INIT = 0`；glibc 的 call_init 照调不误 → `blx` 到地址 0（非 PIE 下 vaddr 0')
    B(' *   正是我们自己的 ELF 头，已映射）→ 跑到 0x20 处遇未定义指令 = SIGILL(si_addr=0x20)。')
    B(' *   这就是重建产物在 qemu 下起不来的真因。改为 PROVIDE_HIDDEN 后，CI(GCC 链了 crti.o)')
    B(' *   会采用 crti 的真 `_init`，DT_INIT 指向真实 .init 代码。')
    B(' *   ⚠ 本地 zig 工具链不带 crti.o ⇒ 本地链接的 DT_INIT 仍会是 0；由 tools/dyn_audit.py')
    B(' *   在 CI(GCC) 侧做硬门禁 —— 本地只作迭代，判定以 CI 为准。')
    B(' * ★ UNK_000d2f00 / UNK_00118000 / UNK_002e0938 已由「工厂 .text / .rodata 镜像 +')
    B(' *   .set 别名」真实供应（不再是 0 占位）——此前它们指向地址 0，是运行期地雷。')
    B(' * ★★ 血泪：`_init = 0;` 这种**普通赋值会压掉 crti.o 的真定义**，而 glibc 的')
    B(' *   __libc_start_main 会走 DT_INIT/初始化链 → 直接 blx 到 0 → SIGILL（si_addr≈0x20）。')
    B(' *   故所有"兜底"一律用 PROVIDE_HIDDEN，绝不用裸赋值。 */')
    B('PROVIDE_HIDDEN(_init = 0);')
    B('')
    B('/* CRT 符号：指向真实段首（构造子由 crtbegin 填入，语义正确） */')
    for sym, sec in sorted(LINKER_DEFINED.items()):
        B('PROVIDE(%s = ADDR(%s));' % (sym, sec))
    open(os.path.join(linkdir, 'factory.ld'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print('数据镜像符号总数 : %d' % total)
    print('CRT 符号(链接器定义): %s' % ', '.join(sorted(skipped_crt)))
    print('未落段的 MISSING : %d  %s' % (len(unplaced), ', '.join(unplaced[:10])))
    print('产出: src/data/factory_image.S, src/data/factory_*.bin, linker/factory.ld')
    return 0


if __name__ == '__main__':
    sys.exit(main())
