/* 自动生成 —— 复刻工厂 rkgame 的内存映射（tools/gen_data_module.py）
 * 依据：反编译代码含烧死的绝对地址，段 VMA 必须与工厂逐位一致。 */
ENTRY(_start)

SECTIONS
{
  /* ---- ① 工厂地址区（必须逐位一致：代码里烧死绝对地址）---- */
  . = 0x00008000;
  .fimg_text 0x00009b10 : { *(.fimg_text) }
  .fimg_rodata 0x002dbca4 : { *(.fimg_rodata) }
  .fimg_data_rel_ro_local 0x003ae5c4 : { *(.fimg_data_rel_ro_local) }
  .fimg_data 0x003af000 : { *(.fimg_data) }
  .fimg_bss 0x003b2178 : { *(.fimg_bss) }
  .fimg_bss_pad 0x003e2000 : { *(.fimg_bss_pad) }

  /* ---- ② ELF 元数据（地址无关；排在 ① 之后，避免挤进工厂地址区）---- */
  . = 0x00400000;
  .interp : { *(.interp) }
  .note.ABI-tag : { *(.note.ABI-tag) }
  .hash : { *(.hash) }
  .gnu.hash : { *(.gnu.hash) }
  .dynsym : { *(.dynsym) }
  .dynstr : { *(.dynstr) }
  .gnu.version : { *(.gnu.version) }
  .gnu.version_r : { *(.gnu.version_r) }
  .rel.dyn : { *(.rel.dyn) }
  .rel.plt : { *(.rel.plt) }
  .plt : { *(.plt) *(.plt.*) }

  /* ---- ③ 运行时区（我们自己 + libc；地址自由，只要不与①②重叠）----
   * ★★★ 2026-09-22（GAP 16.69）：**这里曾把 `.data`/`.bss`/`.text` 钉在
   *   0x01000000 / 0x02000000 / 0x05000000**，结果 lld 把「WA 属性的 `.fini_array`（在
   *   `.rodata` 末尾 ~0x4e00e0）」和「钉在 0x01000000 的 `.data`」归入**同一个 RW 段**，
   *   该段的 p_filesz 于是跨过两者之间的 **11.1 MB VMA 空洞** ⇒ 产出一份畸形 ELF：
   *     · PT_LOAD 段数 2 → **9**；文件 3.9 MB → **17.3 MB**（11 MB 是填充）
   *     · 最高 vaddr 4 MB → **268 MB**（内核据此把 brk 也推到 268 MB）
   *     · 该 11 MB 段与承载**全部代码**的 `.text` 段**在地址上重叠**
   *   ⇒ 在 qemu/PC 上被容忍（所以 CI 一路全绿），**在真机上直接 exec 失败、一条日志都不产生**
   *     （2026-09-21 真机实测：换成本产物后无法开机，`_diag/` 内零文件；换回原厂即正常）。
   *   修法 = **不再钉死这几个地址**，让自有节紧接 `.rodata` 连续排布（与工厂的 2 段形态一致）。
   *   ★ 自有节的地址本来就无契约（工厂的 .data/.bss 在 0x3AF000/0x3B2178，由 `.fimg_*` 复刻），
   *     钉死它们纯属历史遗留 ⇒ 移动不影响任何「烧死的绝对地址」。 */
  .rodata 0x00410000 : { *(.rodata) *(.rodata.*) *(.ARM.extab*) *(.gcc_except_table*) }
  .init_array ALIGN(4) : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(.init_array)) KEEP(*(.init_array.*)) }
  .fini_array ALIGN(4) : { KEEP(*(.fini_array)) KEEP(*(.fini_array.*)) }
  /* ---- ③a RELRO 族（必须与 `.data` 分开，否则运行期会把我们的全局变量改成只读）----
   * ★★★ 2026-09-22（GAP 16.71）：**ld.lld 的 `PT_GNU_RELRO` = 「本 RW 段内第一个 relro 节
   *   的起点 → 最后一个 relro 节的终点」**。此前 `.data` 的输出段里混进了
   *   `*(.data.rel.ro) *(.got)`，而 lld 又把 `.dynamic` 自动排到 `.data` **之后** ⇒
   *   RELRO 起点 = `.fini_array`（0x4e00e0）、终点 = `.dynamic` 末尾（0x4e2b9c）
   *   ⇒ **`.data`（0x4e1000）整段落在 RELRO 里**，内核把该页取整区间
   *   （0x4e0000-0x4e3000）设成只读 ⇒ **进程写自己的全局变量即 SIGSEGV**。
   *   真机实证（探针 v3，t2=diag）：`SIGSEGV  si_addr=0x4e1010`（正是 diag 的 `g_lvl`），
   *   PC 在 `cgm_diag_boot` —— 连 `-finstrument-functions` 的插桩都还没跑起来就崩。
   *   对照：原厂 `PT_GNU_RELRO` = 0x3ae5c4 + 2620，**终点 0x3aefe0 恰好停在 `.data`
   *   （0x3af000，页对齐）之前** ⇒ 原厂 `.data` 完全可写。
   *   修法 = ① 把 `.data.rel.ro`/`.got`/`.dynamic` 放进**独立的、排在 `.data` 之前**的输出段；
   *          ② `.data` **页对齐**，保证 RELRO 的页取整区间不侵入 `.data`。
   *   门禁 = `tools/relro_audit.py`（已钉进 link_full.sh）。 */
  .data.rel.ro ALIGN(4) : { *(.data.rel.ro) *(.data.rel.ro.*) }
  .got ALIGN(4) : { *(.got) *(.got.*) }
  .dynamic ALIGN(4) : { *(.dynamic) }
  .data ALIGN(0x1000) : { *(.data) *(.data.*) }
  .bss  ALIGN(0x1000) : { *(.bss) *(.bss.*) *(COMMON) }
  .text ALIGN(0x1000) : { *(.init) *(.text) *(.text.*) *(.fini) }
  .ARM.exidx : { *(.ARM.exidx) *(.ARM.exidx.*) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) *(.debug*) *(.ARM.attributes) }
}

/* ---- ③ 链接期占位 ----
 * ★★ compress / uncompress：**不再占位**（此前 PROVIDE_HIDDEN(...=0) 把它们绑成 ABS 0）。
 *   实测：这两个符号被 `retro_save_state` / `retro_load_state`（以及 TestLibz0）调用，
 *   绑成 0 ⇒ 调用即跳地址 0 ⇒ SIGSEGV（存档/读档功能必崩）。
 *   工厂的取值方式 = 从 `libz.so.1` **动态导入**（NEEDED libz.so.1）⇒ 现在改为
 *   在 link_full.sh 里真实链接一个 ARM 版 libz.so.1（`LIBZ=<path>`），产物同样只记
 *   NEEDED libz.so.1，运行期由设备自己的 libz 解析 —— 与工厂一致。
 *   若找不到 libz.so.1，link_full.sh 会**显式报错退出**（绝不再静默置 0）。
 * _init：★ 只能用 PROVIDE_HIDDEN（"别人定义了就不生效"），**绝不能用裸赋值**。
 *   实测真因：裸赋值 `_init = 0;` 会压掉 crti.o 的真 `_init`，链接器于是在 .dynamic 写下
 *   `DT_INIT = 0`；glibc 的 call_init 照调不误 → `blx` 到地址 0（非 PIE 下 vaddr 0
 *   正是我们自己的 ELF 头，已映射）→ 跑到 0x20 处遇未定义指令 = SIGILL(si_addr=0x20)。
 *   这就是重建产物在 qemu 下起不来的真因。改为 PROVIDE_HIDDEN 后，CI(GCC 链了 crti.o)
 *   会采用 crti 的真 `_init`，DT_INIT 指向真实 .init 代码。
 *   ⚠ 本地 zig 工具链不带 crti.o ⇒ 本地链接的 DT_INIT 仍会是 0；由 tools/dyn_audit.py
 *   在 CI(GCC) 侧做硬门禁 —— 本地只作迭代，判定以 CI 为准。
 * ★ UNK_000d2f00 / UNK_00118000 / UNK_002e0938 已由「工厂 .text / .rodata 镜像 +
 *   .set 别名」真实供应（不再是 0 占位）——此前它们指向地址 0，是运行期地雷。
 * ★★ 血泪：`_init = 0;` 这种**普通赋值会压掉 crti.o 的真定义**，而 glibc 的
 *   __libc_start_main 会走 DT_INIT/初始化链 → 直接 blx 到 0 → SIGILL（si_addr≈0x20）。
 *   故所有"兜底"一律用 PROVIDE_HIDDEN，绝不用裸赋值。
 * ★★ 但 _init/_fini 连 PROVIDE 兜底也不能留：zig 无 crti.o 时会落到 0
 *   ⇒ DT_INIT=0 ⇒ glibc call_init 跳地址 0 ⇒ 任何输出之前就 SIGSEGV。
 *   正确做法：由 src/compat/crt_init.S 提供真实 .init/.fini 节。 */
/* _init/_fini 由 src/compat/crt_init.S 真实提供（见该文件说明）。
 * 此处**故意不再置 0**：漏链 crt_init.o 时要**链接报错**，而不是静默生成 DT_INIT=0。 */

/* CRT 符号：指向真实段首（构造子由 crtbegin 填入，语义正确） */
PROVIDE(__do_global_dtors_aux_fini_array_entry = ADDR(.fini_array));
PROVIDE(__frame_dummy_init_array_entry = ADDR(.init_array));
