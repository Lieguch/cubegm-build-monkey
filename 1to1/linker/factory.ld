/* 自动生成 —— 复刻工厂 rkgame 的内存映射（tools/gen_data_module.py）
 * 依据：反编译代码含烧死的绝对地址，段 VMA 必须与工厂逐位一致。 */
ENTRY(_start)

SECTIONS
{
  /* ---- ① 工厂地址区（必须逐位一致：代码里烧死绝对地址）---- */
  . = 0x00008000;
  .fimg_rodata 0x002dbca4 : { *(.fimg_rodata) }
  .fimg_data_rel_ro_local 0x003ae5c4 : { *(.fimg_data_rel_ro_local) }
  .fimg_data 0x003af000 : { *(.fimg_data) }
  .fimg_bss 0x003b2178 : { *(.fimg_bss) }

  /* ---- ② 代码与运行时区（我们自己 + libc；地址自由，只要不与①重叠）---- */
  .text 0x00009b10 : { *(.text) *(.text.*) *(.init) *(.fini) *(.plt) *(.plt.*) }
  .ARM.exidx : { *(.ARM.exidx) *(.ARM.exidx.*) }
  .rodata 0x00400000 : { *(.rodata) *(.rodata.*) *(.ARM.extab*) *(.gcc_except_table*) }
  .init_array ALIGN(4) : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(.init_array)) KEEP(*(.init_array.*)) }
  .fini_array ALIGN(4) : { KEEP(*(.fini_array)) KEEP(*(.fini_array.*)) }
  .data 0x01000000 : { *(.data) *(.data.*) *(.data.rel.ro) *(.data.rel.ro.*) *(.got) *(.got.*) }
  .bss 0x02000000 : { *(.bss) *(.bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) *(.debug*) *(.ARM.attributes) }
}

/* ---- ③ 链接期占位（未供应符号显式置 0，便于链出并校验段地址）----
 * compress/uncompress：工厂从 libz.so.1 动态导入（NEEDED libz.so.1），试链环境无 libz
 * UNK_*：位于工厂 .text 段内的只读常量，等 P3 三期 .text 精确镜像
 * _init：真机构建由 CRT（crti.o）提供，此处占位仅供试链 */
compress = 0;
uncompress = 0;
_init = 0;
UNK_000d2f00 = 0;
UNK_00118000 = 0;
UNK_002e0938 = 0;

/* CRT 符号：指向真实段首（构造子由 crtbegin 填入，语义正确） */
PROVIDE(__do_global_dtors_aux_fini_array_entry = ADDR(.fini_array));
PROVIDE(__frame_dummy_init_array_entry = ADDR(.init_array));
