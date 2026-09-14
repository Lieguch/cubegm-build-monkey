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
  .init : { *(.init) }
  .plt : { *(.plt) *(.plt.*) }

  /* ---- ③ 运行时区（我们自己 + libc；地址自由，只要不与①②重叠）---- */
  .rodata 0x00410000 : { *(.rodata) *(.rodata.*) *(.ARM.extab*) *(.gcc_except_table*) }
  .init_array ALIGN(4) : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(.init_array)) KEEP(*(.init_array.*)) }
  .fini_array ALIGN(4) : { KEEP(*(.fini_array)) KEEP(*(.fini_array.*)) }
  .data 0x01000000 : { *(.data) *(.data.*) *(.data.rel.ro) *(.data.rel.ro.*) *(.got) *(.got.*) }
  .bss 0x02000000 : { *(.bss) *(.bss.*) *(COMMON) }
  .text 0x05000000 : { *(.text) *(.text.*) *(.fini) }
  .ARM.exidx : { *(.ARM.exidx) *(.ARM.exidx.*) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) *(.debug*) *(.ARM.attributes) }
}

/* ---- ③ 链接期占位（未供应符号显式置 0，便于链出并校验段地址）----
 * compress/uncompress：工厂从 libz.so.1 动态导入（NEEDED libz.so.1），试链环境无 libz
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
 *   故所有"兜底"一律用 PROVIDE_HIDDEN，绝不用裸赋值。 */
PROVIDE_HIDDEN(compress = 0);
PROVIDE_HIDDEN(uncompress = 0);
PROVIDE_HIDDEN(_init = 0);

/* CRT 符号：指向真实段首（构造子由 crtbegin 填入，语义正确） */
PROVIDE(__do_global_dtors_aux_fini_array_entry = ADDR(.fini_array));
PROVIDE(__frame_dummy_init_array_entry = ADDR(.init_array));
