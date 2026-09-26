/* 自动生成 —— 请勿手改；见 tools/gen_data_module.py
 * 每个段只放一份工厂原始镜像，全部符号（含 Ghidra DAT_x）以 .set 别名指向段内偏移。
 * 依据：段 VMA 必须与工厂一致（代码里烧死绝对地址）；DAT_x 不是工厂符号。 */

	.section .fimg_text,"a",%progbits
	.globl __f_text_base
	.type __f_text_base, %object
__f_text_base:
	.incbin "factory_text.bin"
	.size __f_text_base, 0x2d2188

	.section .fimg_rodata,"a",%progbits
	.globl __f_rodata_base
	.type __f_rodata_base, %object
__f_rodata_base:
	.incbin "factory_rodata.bin"
	.size __f_rodata_base, 0xd1358

	.section .fimg_data_rel_ro_local,"aw",%progbits
	.globl __f_data_rel_ro_local_base
	.type __f_data_rel_ro_local_base, %object
__f_data_rel_ro_local_base:
	.incbin "factory_data_rel_ro_local.bin"
	.size __f_data_rel_ro_local_base, 0x914

	.section .fimg_data,"aw",%progbits
	.globl __f_data_base
	.type __f_data_base, %object
__f_data_base:
	.incbin "factory_data.bin"
	.size __f_data_base, 0x2cfc

	.section .fimg_bss,"aw",%nobits
	.globl __f_bss_base
	.type __f_bss_base, %object
__f_bss_base:
	.space 0x2f95b
	.size __f_bss_base, 0x2f95b

	/* ---- 镜像尾部 slack（65536 字节零填充，页对齐）---- */
	.section .fimg_bss_pad,"aw",%progbits
	.globl __f_bss_pad_base
	.type __f_bss_pad_base, %object
__f_bss_pad_base:
	.zero 0x10000
	.size __f_bss_pad_base, 0x10000

/* ---- 符号别名 ---- */
/* .text：2 个符号 */
	.globl UNK_000d2f00
	.set UNK_000d2f00, __f_text_base + 0xc93f0
	.size UNK_000d2f00, 0x0
	.globl UNK_00118000
	.set UNK_00118000, __f_text_base + 0x10e4f0
	.size UNK_00118000, 0x0

/* .rodata：738 个符号 */
	.globl DAT_002dbcb4
	.set DAT_002dbcb4, __f_rodata_base + 0x10
	.size DAT_002dbcb4, 0x0
	.globl DAT_002dbd74
	.set DAT_002dbd74, __f_rodata_base + 0xd0
	.size DAT_002dbd74, 0x0
	.globl DAT_002dbe58
	.set DAT_002dbe58, __f_rodata_base + 0x1b4
	.size DAT_002dbe58, 0x0
	.globl DAT_002dbe5c
	.set DAT_002dbe5c, __f_rodata_base + 0x1b8
	.size DAT_002dbe5c, 0x0
	.globl DAT_002dbe60
	.set DAT_002dbe60, __f_rodata_base + 0x1bc
	.size DAT_002dbe60, 0x0
	.globl DAT_002dccf4
	.set DAT_002dccf4, __f_rodata_base + 0x1050
	.size DAT_002dccf4, 0x0
	.globl DAT_002dcd50
	.set DAT_002dcd50, __f_rodata_base + 0x10ac
	.size DAT_002dcd50, 0x0
	.globl DAT_002dcd5c
	.set DAT_002dcd5c, __f_rodata_base + 0x10b8
	.size DAT_002dcd5c, 0x0
	.globl DAT_002dcd70
	.set DAT_002dcd70, __f_rodata_base + 0x10cc
	.size DAT_002dcd70, 0x0
	.globl DAT_002dcea4
	.set DAT_002dcea4, __f_rodata_base + 0x1200
	.size DAT_002dcea4, 0x0
	.globl DAT_002dcf4c
	.set DAT_002dcf4c, __f_rodata_base + 0x12a8
	.size DAT_002dcf4c, 0x0
	.globl DAT_002dd508
	.set DAT_002dd508, __f_rodata_base + 0x1864
	.size DAT_002dd508, 0x0
	.globl DAT_002dd64c
	.set DAT_002dd64c, __f_rodata_base + 0x19a8
	.size DAT_002dd64c, 0x0
	.globl DAT_002dd860
	.set DAT_002dd860, __f_rodata_base + 0x1bbc
	.size DAT_002dd860, 0x0
	.globl DAT_002dd878
	.set DAT_002dd878, __f_rodata_base + 0x1bd4
	.size DAT_002dd878, 0x0
	.globl DAT_002dd88c
	.set DAT_002dd88c, __f_rodata_base + 0x1be8
	.size DAT_002dd88c, 0x0
	.globl DAT_002ddd74
	.set DAT_002ddd74, __f_rodata_base + 0x20d0
	.size DAT_002ddd74, 0x0
	.globl DAT_002dee30
	.set DAT_002dee30, __f_rodata_base + 0x318c
	.size DAT_002dee30, 0x0
	.globl _ZL6cplens
	.set _ZL6cplens, __f_rodata_base + 0x31a8
	.size _ZL6cplens, 0x7c
	.globl _ZL6cplext
	.set _ZL6cplext, __f_rodata_base + 0x3224
	.size _ZL6cplext, 0x7c
	.globl _ZL6cpdist
	.set _ZL6cpdist, __f_rodata_base + 0x32a0
	.size _ZL6cpdist, 0x78
	.globl _ZL6cpdext
	.set _ZL6cpdext, __f_rodata_base + 0x3318
	.size _ZL6cpdext, 0x78
	.globl _ZL8fixed_tl
	.set _ZL8fixed_tl, __f_rodata_base + 0x3390
	.size _ZL8fixed_tl, 0x1000
	.globl _ZL8fixed_td
	.set _ZL8fixed_td, __f_rodata_base + 0x4390
	.size _ZL8fixed_td, 0x100
	.globl _ZL12inflate_mask
	.set _ZL12inflate_mask, __f_rodata_base + 0x4490
	.size _ZL12inflate_mask, 0x44
	.globl _ZL6border
	.set _ZL6border, __f_rodata_base + 0x44d4
	.size _ZL6border, 0x4c
	.globl _ZL9crc_table
	.set _ZL9crc_table, __f_rodata_base + 0x4520
	.size _ZL9crc_table, 0x400
	.globl mui_Rect
	.set mui_Rect, __f_rodata_base + 0x4920
	.size mui_Rect, 0xb0
	.globl m_Typetab
	.set m_Typetab, __f_rodata_base + 0x49d0
	.size m_Typetab, 0xb4
	.globl GBAKeyMapping
	.set GBAKeyMapping, __f_rodata_base + 0x4a84
	.size GBAKeyMapping, 0x60
	.globl NESKeyMapping
	.set NESKeyMapping, __f_rodata_base + 0x4ae4
	.size NESKeyMapping, 0x60
	.globl SNESKeyMapping
	.set SNESKeyMapping, __f_rodata_base + 0x4b44
	.size SNESKeyMapping, 0x60
	.globl GENSKeyMapping
	.set GENSKeyMapping, __f_rodata_base + 0x4b44
	.size GENSKeyMapping, 0x60
	.globl DEFKeyMapping
	.set DEFKeyMapping, __f_rodata_base + 0x4b44
	.size DEFKeyMapping, 0x60
	.globl FBA_index
	.set FBA_index, __f_rodata_base + 0x4be4
	.size FBA_index, 0x18
	.globl SNES_index
	.set SNES_index, __f_rodata_base + 0x4bfc
	.size SNES_index, 0x18
	.globl MD_index
	.set MD_index, __f_rodata_base + 0x4c14
	.size MD_index, 0x18
	.globl STD_index
	.set STD_index, __f_rodata_base + 0x4c2c
	.size STD_index, 0x18
	.globl joy_key_mask
	.set joy_key_mask, __f_rodata_base + 0x4c44
	.size joy_key_mask, 0x40
	.globl asc2_1608
	.set asc2_1608, __f_rodata_base + 0x4c84
	.size asc2_1608, 0x5f0
	.globl UNK_002e0938
	.set UNK_002e0938, __f_rodata_base + 0x4c94
	.size UNK_002e0938, 0x0
	.globl DAT_002e0d18
	.set DAT_002e0d18, __f_rodata_base + 0x5074
	.size DAT_002e0d18, 0x0
	.globl xmp3_sfBandTable
	.set xmp3_sfBandTable, __f_rodata_base + 0x5274
	.size xmp3_sfBandTable, 0x29a
	.globl xmp3_slotTab
	.set xmp3_slotTab, __f_rodata_base + 0x5510
	.size xmp3_slotTab, 0x10e
	.globl xmp3_sideBytesTab
	.set xmp3_sideBytesTab, __f_rodata_base + 0x5620
	.size xmp3_sideBytesTab, 0xc
	.globl xmp3_bitsPerSlotTab
	.set xmp3_bitsPerSlotTab, __f_rodata_base + 0x562c
	.size xmp3_bitsPerSlotTab, 0x6
	.globl xmp3_samplesPerFrameTab
	.set xmp3_samplesPerFrameTab, __f_rodata_base + 0x5634
	.size xmp3_samplesPerFrameTab, 0x12
	.globl xmp3_bitrateTab
	.set xmp3_bitrateTab, __f_rodata_base + 0x5648
	.size xmp3_bitrateTab, 0x10e
	.globl xmp3_samplerateTab
	.set xmp3_samplerateTab, __f_rodata_base + 0x5758
	.size xmp3_samplerateTab, 0x24
	.globl SFLenTab
	.set SFLenTab, __f_rodata_base + 0x577c
	.size SFLenTab, 0x20
	.globl NRTab
	.set NRTab, __f_rodata_base + 0x579c
	.size NRTab, 0x48
	.globl xmp3_polyCoef
	.set xmp3_polyCoef, __f_rodata_base + 0x57e4
	.size xmp3_polyCoef, 0x420
	.globl xmp3_coef32
	.set xmp3_coef32, __f_rodata_base + 0x5c04
	.size xmp3_coef32, 0x7c
	.globl xmp3_csa
	.set xmp3_csa, __f_rodata_base + 0x5c80
	.size xmp3_csa, 0x40
	.globl xmp3_uniqueIDTab
	.set xmp3_uniqueIDTab, __f_rodata_base + 0x5cc0
	.size xmp3_uniqueIDTab, 0x8
	.globl xmp3_ISFIIP
	.set xmp3_ISFIIP, __f_rodata_base + 0x5cc8
	.size xmp3_ISFIIP, 0x10
	.globl xmp3_ISFMpeg2
	.set xmp3_ISFMpeg2, __f_rodata_base + 0x5cd8
	.size xmp3_ISFMpeg2, 0x100
	.globl xmp3_ISFMpeg1
	.set xmp3_ISFMpeg1, __f_rodata_base + 0x5dd8
	.size xmp3_ISFMpeg1, 0x38
	.globl xmp3_imdctWin
	.set xmp3_imdctWin, __f_rodata_base + 0x5e10
	.size xmp3_imdctWin, 0x240
	.globl c18
	.set c18, __f_rodata_base + 0x6050
	.size c18, 0x24
	.globl fastWin36
	.set fastWin36, __f_rodata_base + 0x6074
	.size fastWin36, 0x48
	.globl xmp3_quadTabMaxBits
	.set xmp3_quadTabMaxBits, __f_rodata_base + 0x60bc
	.size xmp3_quadTabMaxBits, 0x8
	.globl xmp3_quadTabOffset
	.set xmp3_quadTabOffset, __f_rodata_base + 0x60c4
	.size xmp3_quadTabOffset, 0x8
	.globl xmp3_quadTable
	.set xmp3_quadTable, __f_rodata_base + 0x60cc
	.size xmp3_quadTable, 0x50
	.globl xmp3_huffTabLookup
	.set xmp3_huffTabLookup, __f_rodata_base + 0x611c
	.size xmp3_huffTabLookup, 0x100
	.globl xmp3_huffTabOffset
	.set xmp3_huffTabOffset, __f_rodata_base + 0x621c
	.size xmp3_huffTabOffset, 0x80
	.globl xmp3_huffTable
	.set xmp3_huffTable, __f_rodata_base + 0x629c
	.size xmp3_huffTable, 0x2124
	.globl pow43_14
	.set pow43_14, __f_rodata_base + 0x83c0
	.size pow43_14, 0x100
	.globl pow14
	.set pow14, __f_rodata_base + 0x84c0
	.size pow14, 0x10
	.globl pow43
	.set pow43, __f_rodata_base + 0x84d0
	.size pow43, 0xc0
	.globl pow2frac
	.set pow2frac, __f_rodata_base + 0x8590
	.size pow2frac, 0x20
	.globl pow2exp
	.set pow2exp, __f_rodata_base + 0x85b0
	.size pow2exp, 0x20
	.globl preTab
	.set preTab, __f_rodata_base + 0x85d0
	.size preTab, 0x16
	.globl dcttab
	.set dcttab, __f_rodata_base + 0x85e8
	.size dcttab, 0xc0
	.globl direct_tab
	.set direct_tab, __f_rodata_base + 0x86a8
	.size direct_tab, 0x10
	.globl xdirect_tab
	.set xdirect_tab, __f_rodata_base + 0x86b8
	.size xdirect_tab, 0x10
	.globl xbase64_tab
	.set xbase64_tab, __f_rodata_base + 0x86c8
	.size xbase64_tab, 0x10
	.globl iso8859_2_2uni
	.set iso8859_2_2uni, __f_rodata_base + 0x86d8
	.size iso8859_2_2uni, 0xc0
	.globl iso8859_2_page00
	.set iso8859_2_page00, __f_rodata_base + 0x8798
	.size iso8859_2_page00, 0xe0
	.globl iso8859_2_page02
	.set iso8859_2_page02, __f_rodata_base + 0x8878
	.size iso8859_2_page02, 0x20
	.globl iso8859_3_2uni
	.set iso8859_3_2uni, __f_rodata_base + 0x8898
	.size iso8859_3_2uni, 0xc0
	.globl iso8859_3_page00
	.set iso8859_3_page00, __f_rodata_base + 0x8958
	.size iso8859_3_page00, 0x60
	.globl iso8859_3_page01
	.set iso8859_3_page01, __f_rodata_base + 0x89b8
	.size iso8859_3_page01, 0x78
	.globl iso8859_3_page02
	.set iso8859_3_page02, __f_rodata_base + 0x8a30
	.size iso8859_3_page02, 0x8
	.globl iso8859_4_2uni
	.set iso8859_4_2uni, __f_rodata_base + 0x8a38
	.size iso8859_4_2uni, 0xc0
	.globl iso8859_4_page00
	.set iso8859_4_page00, __f_rodata_base + 0x8af8
	.size iso8859_4_page00, 0xe0
	.globl iso8859_4_page02
	.set iso8859_4_page02, __f_rodata_base + 0x8bd8
	.size iso8859_4_page02, 0x20
	.globl iso8859_5_2uni
	.set iso8859_5_2uni, __f_rodata_base + 0x8bf8
	.size iso8859_5_2uni, 0xc0
	.globl iso8859_5_page00
	.set iso8859_5_page00, __f_rodata_base + 0x8cb8
	.size iso8859_5_page00, 0x10
	.globl iso8859_5_page04
	.set iso8859_5_page04, __f_rodata_base + 0x8cc8
	.size iso8859_5_page04, 0x60
	.globl iso8859_6_2uni
	.set iso8859_6_2uni, __f_rodata_base + 0x8d28
	.size iso8859_6_2uni, 0xc0
	.globl iso8859_6_page00
	.set iso8859_6_page00, __f_rodata_base + 0x8de8
	.size iso8859_6_page00, 0x10
	.globl iso8859_6_page06
	.set iso8859_6_page06, __f_rodata_base + 0x8df8
	.size iso8859_6_page06, 0x50
	.globl iso8859_7_2uni
	.set iso8859_7_2uni, __f_rodata_base + 0x8e48
	.size iso8859_7_2uni, 0xc0
	.globl iso8859_7_page00
	.set iso8859_7_page00, __f_rodata_base + 0x8f08
	.size iso8859_7_page00, 0x20
	.globl iso8859_7_page03
	.set iso8859_7_page03, __f_rodata_base + 0x8f28
	.size iso8859_7_page03, 0x58
	.globl iso8859_7_page20
	.set iso8859_7_page20, __f_rodata_base + 0x8f80
	.size iso8859_7_page20, 0x10
	.globl iso8859_8_2uni
	.set iso8859_8_2uni, __f_rodata_base + 0x8f90
	.size iso8859_8_2uni, 0xc0
	.globl iso8859_8_page00
	.set iso8859_8_page00, __f_rodata_base + 0x9050
	.size iso8859_8_page00, 0x58
	.globl iso8859_8_page05
	.set iso8859_8_page05, __f_rodata_base + 0x90a8
	.size iso8859_8_page05, 0x20
	.globl iso8859_8_page20
	.set iso8859_8_page20, __f_rodata_base + 0x90c8
	.size iso8859_8_page20, 0x10
	.globl iso8859_9_2uni
	.set iso8859_9_2uni, __f_rodata_base + 0x90d8
	.size iso8859_9_2uni, 0x60
	.globl iso8859_9_page00
	.set iso8859_9_page00, __f_rodata_base + 0x9138
	.size iso8859_9_page00, 0x30
	.globl iso8859_9_page01
	.set iso8859_9_page01, __f_rodata_base + 0x9168
	.size iso8859_9_page01, 0x48
	.globl iso8859_10_2uni
	.set iso8859_10_2uni, __f_rodata_base + 0x91b0
	.size iso8859_10_2uni, 0xc0
	.globl iso8859_10_page00
	.set iso8859_10_page00, __f_rodata_base + 0x9270
	.size iso8859_10_page00, 0xe0
	.globl iso8859_13_2uni
	.set iso8859_13_2uni, __f_rodata_base + 0x9350
	.size iso8859_13_2uni, 0xc0
	.globl iso8859_13_page00
	.set iso8859_13_page00, __f_rodata_base + 0x9410
	.size iso8859_13_page00, 0xe0
	.globl iso8859_13_page20
	.set iso8859_13_page20, __f_rodata_base + 0x94f0
	.size iso8859_13_page20, 0x8
	.globl iso8859_14_2uni
	.set iso8859_14_2uni, __f_rodata_base + 0x94f8
	.size iso8859_14_2uni, 0xc0
	.globl iso8859_14_page00
	.set iso8859_14_page00, __f_rodata_base + 0x95b8
	.size iso8859_14_page00, 0x60
	.globl iso8859_14_page01_0
	.set iso8859_14_page01_0, __f_rodata_base + 0x9618
	.size iso8859_14_page01_0, 0x20
	.globl iso8859_14_page01_1
	.set iso8859_14_page01_1, __f_rodata_base + 0x9638
	.size iso8859_14_page01_1, 0x10
	.globl iso8859_14_page1e_0
	.set iso8859_14_page1e_0, __f_rodata_base + 0x9648
	.size iso8859_14_page1e_0, 0x88
	.globl iso8859_14_page1e_1
	.set iso8859_14_page1e_1, __f_rodata_base + 0x96d0
	.size iso8859_14_page1e_1, 0x8
	.globl iso8859_15_2uni
	.set iso8859_15_2uni, __f_rodata_base + 0x96d8
	.size iso8859_15_2uni, 0x40
	.globl iso8859_15_page00
	.set iso8859_15_page00, __f_rodata_base + 0x9718
	.size iso8859_15_page00, 0x20
	.globl iso8859_15_page01
	.set iso8859_15_page01, __f_rodata_base + 0x9738
	.size iso8859_15_page01, 0x30
	.globl iso8859_16_2uni
	.set iso8859_16_2uni, __f_rodata_base + 0x9768
	.size iso8859_16_2uni, 0xc0
	.globl iso8859_16_page00
	.set iso8859_16_page00, __f_rodata_base + 0x9828
	.size iso8859_16_page00, 0xe0
	.globl iso8859_16_page02
	.set iso8859_16_page02, __f_rodata_base + 0x9908
	.size iso8859_16_page02, 0x8
	.globl iso8859_16_page20
	.set iso8859_16_page20, __f_rodata_base + 0x9910
	.size iso8859_16_page20, 0x8
	.globl koi8_r_2uni
	.set koi8_r_2uni, __f_rodata_base + 0x9918
	.size koi8_r_2uni, 0x100
	.globl koi8_r_page00
	.set koi8_r_page00, __f_rodata_base + 0x9a18
	.size koi8_r_page00, 0x58
	.globl koi8_r_page04
	.set koi8_r_page04, __f_rodata_base + 0x9a70
	.size koi8_r_page04, 0x58
	.globl koi8_r_page22
	.set koi8_r_page22, __f_rodata_base + 0x9ac8
	.size koi8_r_page22, 0x50
	.globl koi8_r_page23
	.set koi8_r_page23, __f_rodata_base + 0x9b18
	.size koi8_r_page23, 0x8
	.globl koi8_r_page25
	.set koi8_r_page25, __f_rodata_base + 0x9b20
	.size koi8_r_page25, 0xa8
	.globl koi8_u_2uni
	.set koi8_u_2uni, __f_rodata_base + 0x9bc8
	.size koi8_u_2uni, 0x100
	.globl koi8_u_page00
	.set koi8_u_page00, __f_rodata_base + 0x9cc8
	.size koi8_u_page00, 0x58
	.globl koi8_u_page04
	.set koi8_u_page04, __f_rodata_base + 0x9d20
	.size koi8_u_page04, 0x98
	.globl koi8_u_page22
	.set koi8_u_page22, __f_rodata_base + 0x9db8
	.size koi8_u_page22, 0x50
	.globl koi8_u_page23
	.set koi8_u_page23, __f_rodata_base + 0x9e08
	.size koi8_u_page23, 0x8
	.globl koi8_u_page25
	.set koi8_u_page25, __f_rodata_base + 0x9e10
	.size koi8_u_page25, 0xa8
	.globl koi8_ru_2uni
	.set koi8_ru_2uni, __f_rodata_base + 0x9eb8
	.size koi8_ru_2uni, 0x100
	.globl koi8_ru_page00
	.set koi8_ru_page00, __f_rodata_base + 0x9fb8
	.size koi8_ru_page00, 0x58
	.globl koi8_ru_page04
	.set koi8_ru_page04, __f_rodata_base + 0xa010
	.size koi8_ru_page04, 0x98
	.globl koi8_ru_page22
	.set koi8_ru_page22, __f_rodata_base + 0xa0a8
	.size koi8_ru_page22, 0x50
	.globl koi8_ru_page23
	.set koi8_ru_page23, __f_rodata_base + 0xa0f8
	.size koi8_ru_page23, 0x8
	.globl koi8_ru_page25
	.set koi8_ru_page25, __f_rodata_base + 0xa100
	.size koi8_ru_page25, 0xa8
	.globl cp1250_2uni
	.set cp1250_2uni, __f_rodata_base + 0xa1a8
	.size cp1250_2uni, 0x100
	.globl cp1250_page00
	.set cp1250_page00, __f_rodata_base + 0xa2a8
	.size cp1250_page00, 0xe0
	.globl cp1250_page02
	.set cp1250_page02, __f_rodata_base + 0xa388
	.size cp1250_page02, 0x20
	.globl cp1250_page20
	.set cp1250_page20, __f_rodata_base + 0xa3a8
	.size cp1250_page20, 0x30
	.globl cp1251_2uni
	.set cp1251_2uni, __f_rodata_base + 0xa3d8
	.size cp1251_2uni, 0x100
	.globl cp1251_page00
	.set cp1251_page00, __f_rodata_base + 0xa4d8
	.size cp1251_page00, 0x20
	.globl cp1251_page04
	.set cp1251_page04, __f_rodata_base + 0xa4f8
	.size cp1251_page04, 0x98
	.globl cp1251_page20
	.set cp1251_page20, __f_rodata_base + 0xa590
	.size cp1251_page20, 0x30
	.globl cp1252_2uni
	.set cp1252_2uni, __f_rodata_base + 0xa5c0
	.size cp1252_2uni, 0x40
	.globl cp1252_page01
	.set cp1252_page01, __f_rodata_base + 0xa600
	.size cp1252_page01, 0x48
	.globl cp1252_page02
	.set cp1252_page02, __f_rodata_base + 0xa648
	.size cp1252_page02, 0x20
	.globl cp1252_page20
	.set cp1252_page20, __f_rodata_base + 0xa668
	.size cp1252_page20, 0x30
	.globl cp1253_2uni
	.set cp1253_2uni, __f_rodata_base + 0xa698
	.size cp1253_2uni, 0x100
	.globl cp1253_page00
	.set cp1253_page00, __f_rodata_base + 0xa798
	.size cp1253_page00, 0x20
	.globl cp1253_page03
	.set cp1253_page03, __f_rodata_base + 0xa7b8
	.size cp1253_page03, 0x50
	.globl cp1253_page20
	.set cp1253_page20, __f_rodata_base + 0xa808
	.size cp1253_page20, 0x30
	.globl cp1254_2uni_1
	.set cp1254_2uni_1, __f_rodata_base + 0xa838
	.size cp1254_2uni_1, 0x40
	.globl cp1254_2uni_2
	.set cp1254_2uni_2, __f_rodata_base + 0xa878
	.size cp1254_2uni_2, 0x20
	.globl cp1254_2uni_3
	.set cp1254_2uni_3, __f_rodata_base + 0xa898
	.size cp1254_2uni_3, 0x20
	.globl cp1254_page00
	.set cp1254_page00, __f_rodata_base + 0xa8b8
	.size cp1254_page00, 0x30
	.globl cp1254_page01
	.set cp1254_page01, __f_rodata_base + 0xa8e8
	.size cp1254_page01, 0x80
	.globl cp1254_page02
	.set cp1254_page02, __f_rodata_base + 0xa968
	.size cp1254_page02, 0x20
	.globl cp1254_page20
	.set cp1254_page20, __f_rodata_base + 0xa988
	.size cp1254_page20, 0x30
	.globl cp1255_comp_table_data
	.set cp1255_comp_table_data, __f_rodata_base + 0xa9b8
	.size cp1255_comp_table_data, 0x90
	.globl cp1255_comp_table
	.set cp1255_comp_table, __f_rodata_base + 0xaa48
	.size cp1255_comp_table, 0x40
	.globl cp1255_decomp_table
	.set cp1255_decomp_table, __f_rodata_base + 0xaa88
	.size cp1255_decomp_table, 0x110
	.globl cp1255_comb_table
	.set cp1255_comb_table, __f_rodata_base + 0xab98
	.size cp1255_comb_table, 0x8
	.globl cp1255_2uni
	.set cp1255_2uni, __f_rodata_base + 0xaba0
	.size cp1255_2uni, 0x100
	.globl cp1255_page00
	.set cp1255_page00, __f_rodata_base + 0xaca0
	.size cp1255_page00, 0x58
	.globl cp1255_page02
	.set cp1255_page02, __f_rodata_base + 0xacf8
	.size cp1255_page02, 0x20
	.globl cp1255_page05
	.set cp1255_page05, __f_rodata_base + 0xad18
	.size cp1255_page05, 0x48
	.globl cp1255_page20
	.set cp1255_page20, __f_rodata_base + 0xad60
	.size cp1255_page20, 0x38
	.globl cp1256_2uni
	.set cp1256_2uni, __f_rodata_base + 0xad98
	.size cp1256_2uni, 0x100
	.globl cp1256_page00
	.set cp1256_page00, __f_rodata_base + 0xae98
	.size cp1256_page00, 0x60
	.globl cp1256_page01
	.set cp1256_page01, __f_rodata_base + 0xaef8
	.size cp1256_page01, 0x48
	.globl cp1256_page06
	.set cp1256_page06, __f_rodata_base + 0xaf40
	.size cp1256_page06, 0xd0
	.globl cp1256_page20
	.set cp1256_page20, __f_rodata_base + 0xb010
	.size cp1256_page20, 0x38
	.globl cp1257_2uni
	.set cp1257_2uni, __f_rodata_base + 0xb048
	.size cp1257_2uni, 0x100
	.globl cp1257_page00
	.set cp1257_page00, __f_rodata_base + 0xb148
	.size cp1257_page00, 0xe0
	.globl cp1257_page02
	.set cp1257_page02, __f_rodata_base + 0xb228
	.size cp1257_page02, 0x20
	.globl cp1257_page20
	.set cp1257_page20, __f_rodata_base + 0xb248
	.size cp1257_page20, 0x30
	.globl viet_comp_table_data
	.set viet_comp_table_data, __f_rodata_base + 0xb278
	.size viet_comp_table_data, 0x328
	.globl viet_comp_table
	.set viet_comp_table, __f_rodata_base + 0xb5a0
	.size viet_comp_table, 0x28
	.globl viet_decomp_table
	.set viet_decomp_table, __f_rodata_base + 0xb5c8
	.size viet_decomp_table, 0x324
	.globl cp1258_comb_table
	.set cp1258_comb_table, __f_rodata_base + 0xb8ec
	.size cp1258_comb_table, 0x5
	.globl cp1258_comp_bases
	.set cp1258_comp_bases, __f_rodata_base + 0xb8f4
	.size cp1258_comp_bases, 0x30
	.globl cp1258_2uni
	.set cp1258_2uni, __f_rodata_base + 0xb924
	.size cp1258_2uni, 0x100
	.globl cp1258_page00
	.set cp1258_page00, __f_rodata_base + 0xba24
	.size cp1258_page00, 0x58
	.globl cp1258_page01
	.set cp1258_page01, __f_rodata_base + 0xba7c
	.size cp1258_page01, 0x68
	.globl cp1258_page02
	.set cp1258_page02, __f_rodata_base + 0xbae4
	.size cp1258_page02, 0x20
	.globl cp1258_page03
	.set cp1258_page03, __f_rodata_base + 0xbb04
	.size cp1258_page03, 0x28
	.globl cp1258_page20
	.set cp1258_page20, __f_rodata_base + 0xbb2c
	.size cp1258_page20, 0x30
	.globl cp850_2uni
	.set cp850_2uni, __f_rodata_base + 0xbb5c
	.size cp850_2uni, 0x100
	.globl cp850_page00
	.set cp850_page00, __f_rodata_base + 0xbc5c
	.size cp850_page00, 0x60
	.globl cp850_page25
	.set cp850_page25, __f_rodata_base + 0xbcbc
	.size cp850_page25, 0xa8
	.globl cp862_2uni
	.set cp862_2uni, __f_rodata_base + 0xbd64
	.size cp862_2uni, 0x100
	.globl cp862_page00
	.set cp862_page00, __f_rodata_base + 0xbe64
	.size cp862_page00, 0x60
	.globl cp862_page03
	.set cp862_page03, __f_rodata_base + 0xbec4
	.size cp862_page03, 0x38
	.globl cp862_page22
	.set cp862_page22, __f_rodata_base + 0xbefc
	.size cp862_page22, 0x50
	.globl cp862_page25
	.set cp862_page25, __f_rodata_base + 0xbf4c
	.size cp862_page25, 0xa8
	.globl cp866_2uni
	.set cp866_2uni, __f_rodata_base + 0xbff4
	.size cp866_2uni, 0xa0
	.globl cp866_page00
	.set cp866_page00, __f_rodata_base + 0xc094
	.size cp866_page00, 0x18
	.globl cp866_page04
	.set cp866_page04, __f_rodata_base + 0xc0ac
	.size cp866_page04, 0x60
	.globl cp866_page22
	.set cp866_page22, __f_rodata_base + 0xc10c
	.size cp866_page22, 0x8
	.globl cp866_page25
	.set cp866_page25, __f_rodata_base + 0xc114
	.size cp866_page25, 0xa8
	.globl cp1131_2uni
	.set cp1131_2uni, __f_rodata_base + 0xc1bc
	.size cp1131_2uni, 0x100
	.globl cp1131_page00
	.set cp1131_page00, __f_rodata_base + 0xc2bc
	.size cp1131_page00, 0x18
	.globl cp1131_page04
	.set cp1131_page04, __f_rodata_base + 0xc2d4
	.size cp1131_page04, 0x98
	.globl cp1131_page25
	.set cp1131_page25, __f_rodata_base + 0xc36c
	.size cp1131_page25, 0x98
	.globl mac_roman_2uni
	.set mac_roman_2uni, __f_rodata_base + 0xc404
	.size mac_roman_2uni, 0x100
	.globl mac_roman_page00
	.set mac_roman_page00, __f_rodata_base + 0xc504
	.size mac_roman_page00, 0x60
	.globl mac_roman_page01
	.set mac_roman_page01, __f_rodata_base + 0xc564
	.size mac_roman_page01, 0x68
	.globl mac_roman_page02
	.set mac_roman_page02, __f_rodata_base + 0xc5cc
	.size mac_roman_page02, 0x20
	.globl mac_roman_page20
	.set mac_roman_page20, __f_rodata_base + 0xc5ec
	.size mac_roman_page20, 0x38
	.globl mac_roman_page21
	.set mac_roman_page21, __f_rodata_base + 0xc624
	.size mac_roman_page21, 0x8
	.globl mac_roman_page22
	.set mac_roman_page22, __f_rodata_base + 0xc62c
	.size mac_roman_page22, 0x68
	.globl mac_roman_pagefb
	.set mac_roman_pagefb, __f_rodata_base + 0xc694
	.size mac_roman_pagefb, 0x8
	.globl mac_centraleurope_2uni
	.set mac_centraleurope_2uni, __f_rodata_base + 0xc69c
	.size mac_centraleurope_2uni, 0x100
	.globl mac_centraleurope_page00
	.set mac_centraleurope_page00, __f_rodata_base + 0xc79c
	.size mac_centraleurope_page00, 0xe0
	.globl mac_centraleurope_page20
	.set mac_centraleurope_page20, __f_rodata_base + 0xc87c
	.size mac_centraleurope_page20, 0x30
	.globl mac_centraleurope_page22
	.set mac_centraleurope_page22, __f_rodata_base + 0xc8ac
	.size mac_centraleurope_page22, 0x20
	.globl mac_centraleurope_page22_1
	.set mac_centraleurope_page22_1, __f_rodata_base + 0xc8cc
	.size mac_centraleurope_page22_1, 0x8
	.globl mac_iceland_2uni
	.set mac_iceland_2uni, __f_rodata_base + 0xc8d4
	.size mac_iceland_2uni, 0x100
	.globl mac_iceland_page00
	.set mac_iceland_page00, __f_rodata_base + 0xc9d4
	.size mac_iceland_page00, 0x60
	.globl mac_iceland_page01
	.set mac_iceland_page01, __f_rodata_base + 0xca34
	.size mac_iceland_page01, 0x68
	.globl mac_iceland_page02
	.set mac_iceland_page02, __f_rodata_base + 0xca9c
	.size mac_iceland_page02, 0x20
	.globl mac_iceland_page20
	.set mac_iceland_page20, __f_rodata_base + 0xcabc
	.size mac_iceland_page20, 0x38
	.globl mac_iceland_page21
	.set mac_iceland_page21, __f_rodata_base + 0xcaf4
	.size mac_iceland_page21, 0x8
	.globl mac_iceland_page22
	.set mac_iceland_page22, __f_rodata_base + 0xcafc
	.size mac_iceland_page22, 0x68
	.globl mac_croatian_2uni
	.set mac_croatian_2uni, __f_rodata_base + 0xcb64
	.size mac_croatian_2uni, 0x100
	.globl mac_croatian_page00
	.set mac_croatian_page00, __f_rodata_base + 0xcc64
	.size mac_croatian_page00, 0xf8
	.globl mac_croatian_page02
	.set mac_croatian_page02, __f_rodata_base + 0xcd5c
	.size mac_croatian_page02, 0x20
	.globl mac_croatian_page20
	.set mac_croatian_page20, __f_rodata_base + 0xcd7c
	.size mac_croatian_page20, 0x38
	.globl mac_croatian_page21
	.set mac_croatian_page21, __f_rodata_base + 0xcdb4
	.size mac_croatian_page21, 0x8
	.globl mac_croatian_page22
	.set mac_croatian_page22, __f_rodata_base + 0xcdbc
	.size mac_croatian_page22, 0x68
	.globl mac_romania_2uni
	.set mac_romania_2uni, __f_rodata_base + 0xce24
	.size mac_romania_2uni, 0x100
	.globl mac_romania_page00
	.set mac_romania_page00, __f_rodata_base + 0xcf24
	.size mac_romania_page00, 0xf8
	.globl mac_romania_page02
	.set mac_romania_page02, __f_rodata_base + 0xd01c
	.size mac_romania_page02, 0x20
	.globl mac_romania_page20
	.set mac_romania_page20, __f_rodata_base + 0xd03c
	.size mac_romania_page20, 0x38
	.globl mac_romania_page21
	.set mac_romania_page21, __f_rodata_base + 0xd074
	.size mac_romania_page21, 0x8
	.globl mac_romania_page22
	.set mac_romania_page22, __f_rodata_base + 0xd07c
	.size mac_romania_page22, 0x68
	.globl mac_cyrillic_2uni
	.set mac_cyrillic_2uni, __f_rodata_base + 0xd0e4
	.size mac_cyrillic_2uni, 0x100
	.globl mac_cyrillic_page00
	.set mac_cyrillic_page00, __f_rodata_base + 0xd1e4
	.size mac_cyrillic_page00, 0x20
	.globl mac_cyrillic_page04
	.set mac_cyrillic_page04, __f_rodata_base + 0xd204
	.size mac_cyrillic_page04, 0x60
	.globl mac_cyrillic_page20
	.set mac_cyrillic_page20, __f_rodata_base + 0xd264
	.size mac_cyrillic_page20, 0x18
	.globl mac_cyrillic_page21
	.set mac_cyrillic_page21, __f_rodata_base + 0xd27c
	.size mac_cyrillic_page21, 0x18
	.globl mac_cyrillic_page22
	.set mac_cyrillic_page22, __f_rodata_base + 0xd294
	.size mac_cyrillic_page22, 0x68
	.globl mac_ukraine_2uni
	.set mac_ukraine_2uni, __f_rodata_base + 0xd2fc
	.size mac_ukraine_2uni, 0x100
	.globl mac_ukraine_page00
	.set mac_ukraine_page00, __f_rodata_base + 0xd3fc
	.size mac_ukraine_page00, 0x20
	.globl mac_ukraine_page04
	.set mac_ukraine_page04, __f_rodata_base + 0xd41c
	.size mac_ukraine_page04, 0x98
	.globl mac_ukraine_page20
	.set mac_ukraine_page20, __f_rodata_base + 0xd4b4
	.size mac_ukraine_page20, 0x18
	.globl mac_ukraine_page21
	.set mac_ukraine_page21, __f_rodata_base + 0xd4cc
	.size mac_ukraine_page21, 0x18
	.globl mac_ukraine_page22
	.set mac_ukraine_page22, __f_rodata_base + 0xd4e4
	.size mac_ukraine_page22, 0x68
	.globl mac_greek_2uni
	.set mac_greek_2uni, __f_rodata_base + 0xd54c
	.size mac_greek_2uni, 0x100
	.globl mac_greek_page00
	.set mac_greek_page00, __f_rodata_base + 0xd64c
	.size mac_greek_page00, 0x60
	.globl mac_greek_page03
	.set mac_greek_page03, __f_rodata_base + 0xd6ac
	.size mac_greek_page03, 0x50
	.globl mac_greek_page20
	.set mac_greek_page20, __f_rodata_base + 0xd6fc
	.size mac_greek_page20, 0x28
	.globl mac_greek_page22
	.set mac_greek_page22, __f_rodata_base + 0xd724
	.size mac_greek_page22, 0x20
	.globl mac_turkish_2uni
	.set mac_turkish_2uni, __f_rodata_base + 0xd744
	.size mac_turkish_2uni, 0x100
	.globl mac_turkish_page00
	.set mac_turkish_page00, __f_rodata_base + 0xd844
	.size mac_turkish_page00, 0x60
	.globl mac_turkish_page01
	.set mac_turkish_page01, __f_rodata_base + 0xd8a4
	.size mac_turkish_page01, 0x80
	.globl mac_turkish_page02
	.set mac_turkish_page02, __f_rodata_base + 0xd924
	.size mac_turkish_page02, 0x20
	.globl mac_turkish_page20
	.set mac_turkish_page20, __f_rodata_base + 0xd944
	.size mac_turkish_page20, 0x28
	.globl mac_turkish_page21
	.set mac_turkish_page21, __f_rodata_base + 0xd96c
	.size mac_turkish_page21, 0x8
	.globl mac_turkish_page22
	.set mac_turkish_page22, __f_rodata_base + 0xd974
	.size mac_turkish_page22, 0x68
	.globl mac_hebrew_2uni
	.set mac_hebrew_2uni, __f_rodata_base + 0xd9dc
	.size mac_hebrew_2uni, 0x100
	.globl mac_hebrew_page00
	.set mac_hebrew_page00, __f_rodata_base + 0xdadc
	.size mac_hebrew_page00, 0x60
	.globl mac_hebrew_page05
	.set mac_hebrew_page05, __f_rodata_base + 0xdb3c
	.size mac_hebrew_page05, 0x40
	.globl mac_hebrew_page20
	.set mac_hebrew_page20, __f_rodata_base + 0xdb7c
	.size mac_hebrew_page20, 0x18
	.globl mac_hebrew_pagefb
	.set mac_hebrew_pagefb, __f_rodata_base + 0xdb94
	.size mac_hebrew_pagefb, 0x38
	.globl mac_arabic_2uni
	.set mac_arabic_2uni, __f_rodata_base + 0xdbcc
	.size mac_arabic_2uni, 0x100
	.globl mac_arabic_page00
	.set mac_arabic_page00, __f_rodata_base + 0xdccc
	.size mac_arabic_page00, 0x60
	.globl mac_arabic_page06
	.set mac_arabic_page06, __f_rodata_base + 0xdd2c
	.size mac_arabic_page06, 0xd0
	.globl mac_thai_2uni
	.set mac_thai_2uni, __f_rodata_base + 0xddfc
	.size mac_thai_2uni, 0x100
	.globl mac_thai_page00
	.set mac_thai_page00, __f_rodata_base + 0xdefc
	.size mac_thai_page00, 0x20
	.globl mac_thai_page0e
	.set mac_thai_page0e, __f_rodata_base + 0xdf1c
	.size mac_thai_page0e, 0x60
	.globl mac_thai_page20
	.set mac_thai_page20, __f_rodata_base + 0xdf7c
	.size mac_thai_page20, 0x20
	.globl mac_thai_pagef8
	.set mac_thai_pagef8, __f_rodata_base + 0xdf9c
	.size mac_thai_pagef8, 0x20
	.globl hp_roman8_2uni
	.set hp_roman8_2uni, __f_rodata_base + 0xdfbc
	.size hp_roman8_2uni, 0xc0
	.globl hp_roman8_page00
	.set hp_roman8_page00, __f_rodata_base + 0xe07c
	.size hp_roman8_page00, 0x60
	.globl hp_roman8_page01
	.set hp_roman8_page01, __f_rodata_base + 0xe0dc
	.size hp_roman8_page01, 0x38
	.globl hp_roman8_page02
	.set hp_roman8_page02, __f_rodata_base + 0xe114
	.size hp_roman8_page02, 0x20
	.globl nextstep_2uni
	.set nextstep_2uni, __f_rodata_base + 0xe134
	.size nextstep_2uni, 0x100
	.globl nextstep_page00
	.set nextstep_page00, __f_rodata_base + 0xe234
	.size nextstep_page00, 0x60
	.globl nextstep_page01
	.set nextstep_page01, __f_rodata_base + 0xe294
	.size nextstep_page01, 0x68
	.globl nextstep_page02
	.set nextstep_page02, __f_rodata_base + 0xe2fc
	.size nextstep_page02, 0x20
	.globl nextstep_page20
	.set nextstep_page20, __f_rodata_base + 0xe31c
	.size nextstep_page20, 0x38
	.globl nextstep_pagefb
	.set nextstep_pagefb, __f_rodata_base + 0xe354
	.size nextstep_pagefb, 0x8
	.globl armscii_8_2uni
	.set armscii_8_2uni, __f_rodata_base + 0xe35c
	.size armscii_8_2uni, 0xc0
	.globl armscii_8_page00
	.set armscii_8_page00, __f_rodata_base + 0xe41c
	.size armscii_8_page00, 0x8
	.globl armscii_8_page00_1
	.set armscii_8_page00_1, __f_rodata_base + 0xe424
	.size armscii_8_page00_1, 0x20
	.globl armscii_8_page05
	.set armscii_8_page05, __f_rodata_base + 0xe444
	.size armscii_8_page05, 0x60
	.globl armscii_8_page20
	.set armscii_8_page20, __f_rodata_base + 0xe4a4
	.size armscii_8_page20, 0x18
	.globl georgian_academy_2uni
	.set georgian_academy_2uni, __f_rodata_base + 0xe4bc
	.size georgian_academy_2uni, 0x40
	.globl georgian_academy_page00
	.set georgian_academy_page00, __f_rodata_base + 0xe4fc
	.size georgian_academy_page00, 0x20
	.globl georgian_academy_page01
	.set georgian_academy_page01, __f_rodata_base + 0xe51c
	.size georgian_academy_page01, 0x48
	.globl georgian_academy_page02
	.set georgian_academy_page02, __f_rodata_base + 0xe564
	.size georgian_academy_page02, 0x20
	.globl georgian_academy_page20
	.set georgian_academy_page20, __f_rodata_base + 0xe584
	.size georgian_academy_page20, 0x30
	.globl georgian_ps_2uni_1
	.set georgian_ps_2uni_1, __f_rodata_base + 0xe5b4
	.size georgian_ps_2uni_1, 0x40
	.globl georgian_ps_2uni_2
	.set georgian_ps_2uni_2, __f_rodata_base + 0xe5f4
	.size georgian_ps_2uni_2, 0x4e
	.globl georgian_ps_page00
	.set georgian_ps_page00, __f_rodata_base + 0xe644
	.size georgian_ps_page00, 0x20
	.globl georgian_ps_page01
	.set georgian_ps_page01, __f_rodata_base + 0xe664
	.size georgian_ps_page01, 0x48
	.globl georgian_ps_page02
	.set georgian_ps_page02, __f_rodata_base + 0xe6ac
	.size georgian_ps_page02, 0x20
	.globl georgian_ps_page10
	.set georgian_ps_page10, __f_rodata_base + 0xe6cc
	.size georgian_ps_page10, 0x28
	.globl georgian_ps_page20
	.set georgian_ps_page20, __f_rodata_base + 0xe6f4
	.size georgian_ps_page20, 0x30
	.globl koi8_t_2uni
	.set koi8_t_2uni, __f_rodata_base + 0xe724
	.size koi8_t_2uni, 0x100
	.globl koi8_t_page00
	.set koi8_t_page00, __f_rodata_base + 0xe824
	.size koi8_t_page00, 0x20
	.globl koi8_t_page04
	.set koi8_t_page04, __f_rodata_base + 0xe844
	.size koi8_t_page04, 0xf0
	.globl koi8_t_page20
	.set koi8_t_page20, __f_rodata_base + 0xe934
	.size koi8_t_page20, 0x30
	.globl koi8_t_page21
	.set koi8_t_page21, __f_rodata_base + 0xe964
	.size koi8_t_page21, 0x18
	.globl pt154_2uni
	.set pt154_2uni, __f_rodata_base + 0xe97c
	.size pt154_2uni, 0x80
	.globl pt154_page00
	.set pt154_page00, __f_rodata_base + 0xe9fc
	.size pt154_page00, 0x20
	.globl pt154_page04
	.set pt154_page04, __f_rodata_base + 0xea1c
	.size pt154_page04, 0xf0
	.globl pt154_page20
	.set pt154_page20, __f_rodata_base + 0xeb0c
	.size pt154_page20, 0x18
	.globl rk1048_2uni
	.set rk1048_2uni, __f_rodata_base + 0xeb24
	.size rk1048_2uni, 0x100
	.globl rk1048_page00
	.set rk1048_page00, __f_rodata_base + 0xec24
	.size rk1048_page00, 0x20
	.globl rk1048_page04
	.set rk1048_page04, __f_rodata_base + 0xec44
	.size rk1048_page04, 0xf0
	.globl rk1048_page20
	.set rk1048_page20, __f_rodata_base + 0xed34
	.size rk1048_page20, 0x30
	.globl rk1048_page21
	.set rk1048_page21, __f_rodata_base + 0xed64
	.size rk1048_page21, 0x18
	.globl mulelao_2uni
	.set mulelao_2uni, __f_rodata_base + 0xed7c
	.size mulelao_2uni, 0xc0
	.globl mulelao_page0e
	.set mulelao_page0e, __f_rodata_base + 0xee3c
	.size mulelao_page0e, 0x60
	.globl cp1133_2uni_1
	.set cp1133_2uni_1, __f_rodata_base + 0xee9c
	.size cp1133_2uni_1, 0x80
	.globl cp1133_2uni_2
	.set cp1133_2uni_2, __f_rodata_base + 0xef1c
	.size cp1133_2uni_2, 0x20
	.globl cp1133_page00
	.set cp1133_page00, __f_rodata_base + 0xef3c
	.size cp1133_page00, 0x10
	.globl cp1133_page0e
	.set cp1133_page0e, __f_rodata_base + 0xef4c
	.size cp1133_page0e, 0x60
	.globl cp874_2uni
	.set cp874_2uni, __f_rodata_base + 0xefac
	.size cp874_2uni, 0x100
	.globl cp874_page0e
	.set cp874_page0e, __f_rodata_base + 0xf0ac
	.size cp874_page0e, 0x60
	.globl cp874_page20
	.set cp874_page20, __f_rodata_base + 0xf10c
	.size cp874_page20, 0x18
	.globl viscii_2uni_1
	.set viscii_2uni_1, __f_rodata_base + 0xf124
	.size viscii_2uni_1, 0x40
	.globl viscii_2uni_2
	.set viscii_2uni_2, __f_rodata_base + 0xf164
	.size viscii_2uni_2, 0x100
	.globl viscii_page00
	.set viscii_page00, __f_rodata_base + 0xf264
	.size viscii_page00, 0xf8
	.globl viscii_page1e
	.set viscii_page1e, __f_rodata_base + 0xf35c
	.size viscii_page1e, 0x60
	.globl tcvn_comb_table
	.set tcvn_comb_table, __f_rodata_base + 0xf3bc
	.size tcvn_comb_table, 0x5
	.globl tcvn_comp_bases
	.set tcvn_comp_bases, __f_rodata_base + 0xf3c4
	.size tcvn_comp_bases, 0x30
	.globl tcvn_2uni_1
	.set tcvn_2uni_1, __f_rodata_base + 0xf3f4
	.size tcvn_2uni_1, 0x30
	.globl tcvn_2uni_2
	.set tcvn_2uni_2, __f_rodata_base + 0xf424
	.size tcvn_2uni_2, 0x100
	.globl tcvn_page00
	.set tcvn_page00, __f_rodata_base + 0xf524
	.size tcvn_page00, 0x118
	.globl tcvn_page03
	.set tcvn_page03, __f_rodata_base + 0xf63c
	.size tcvn_page03, 0x28
	.globl tcvn_page1e
	.set tcvn_page1e, __f_rodata_base + 0xf664
	.size tcvn_page1e, 0x60
	.globl jisx0208_2uni_page21
	.set jisx0208_2uni_page21, __f_rodata_base + 0xf6c4
	.size jisx0208_2uni_page21, 0x564
	.globl jisx0208_2uni_page30
	.set jisx0208_2uni_page30, __f_rodata_base + 0xfc28
	.size jisx0208_2uni_page30, 0x31fc
	.globl jisx0208_2charset
	.set jisx0208_2charset, __f_rodata_base + 0x12e24
	.size jisx0208_2charset, 0x35be
	.globl jisx0208_uni2indx_page00
	.set jisx0208_uni2indx_page00, __f_rodata_base + 0x163e4
	.size jisx0208_uni2indx_page00, 0x40
	.globl jisx0208_uni2indx_page03
	.set jisx0208_uni2indx_page03, __f_rodata_base + 0x16424
	.size jisx0208_uni2indx_page03, 0x58
	.globl jisx0208_uni2indx_page20
	.set jisx0208_uni2indx_page20, __f_rodata_base + 0x1647c
	.size jisx0208_uni2indx_page20, 0xc8
	.globl jisx0208_uni2indx_page25
	.set jisx0208_uni2indx_page25, __f_rodata_base + 0x16544
	.size jisx0208_uni2indx_page25, 0x5c
	.globl jisx0208_uni2indx_page30
	.set jisx0208_uni2indx_page30, __f_rodata_base + 0x165a0
	.size jisx0208_uni2indx_page30, 0x40
	.globl jisx0208_uni2indx_page4e
	.set jisx0208_uni2indx_page4e, __f_rodata_base + 0x165e0
	.size jisx0208_uni2indx_page4e, 0x146c
	.globl jisx0208_uni2indx_pageff
	.set jisx0208_uni2indx_pageff, __f_rodata_base + 0x17a4c
	.size jisx0208_uni2indx_pageff, 0x3c
	.globl jisx0212_2uni_page22
	.set jisx0212_2uni_page22, __f_rodata_base + 0x17a88
	.size jisx0212_2uni_page22, 0xa2
	.globl jisx0212_2uni_page26
	.set jisx0212_2uni_page26, __f_rodata_base + 0x17b2c
	.size jisx0212_2uni_page26, 0x178
	.globl jisx0212_2uni_page29
	.set jisx0212_2uni_page29, __f_rodata_base + 0x17ca4
	.size jisx0212_2uni_page29, 0x226
	.globl jisx0212_2uni_page30
	.set jisx0212_2uni_page30, __f_rodata_base + 0x17ecc
	.size jisx0212_2uni_page30, 0x2d52
	.globl jisx0212_2charset
	.set jisx0212_2charset, __f_rodata_base + 0x1ac20
	.size jisx0212_2charset, 0x2f66
	.globl jisx0212_uni2indx_page00
	.set jisx0212_uni2indx_page00, __f_rodata_base + 0x1db88
	.size jisx0212_uni2indx_page00, 0x118
	.globl jisx0212_uni2indx_page21
	.set jisx0212_uni2indx_page21, __f_rodata_base + 0x1dca0
	.size jisx0212_uni2indx_page21, 0xc
	.globl jisx0212_uni2indx_page4e
	.set jisx0212_uni2indx_page4e, __f_rodata_base + 0x1dcac
	.size jisx0212_uni2indx_page4e, 0x146c
	.globl jisx0212_uni2indx_pageff
	.set jisx0212_uni2indx_pageff, __f_rodata_base + 0x1f118
	.size jisx0212_uni2indx_pageff, 0x18
	.globl gb2312_2uni_page21
	.set gb2312_2uni_page21, __f_rodata_base + 0x1f130
	.size gb2312_2uni_page21, 0x67e
	.globl gb2312_2uni_page30
	.set gb2312_2uni_page30, __f_rodata_base + 0x1f7b0
	.size gb2312_2uni_page30, 0x34e0
	.globl gb2312_2charset
	.set gb2312_2charset, __f_rodata_base + 0x22c90
	.size gb2312_2charset, 0x3a2a
	.globl gb2312_uni2indx_page00
	.set gb2312_uni2indx_page00, __f_rodata_base + 0x266bc
	.size gb2312_uni2indx_page00, 0x118
	.globl gb2312_uni2indx_page20
	.set gb2312_uni2indx_page20, __f_rodata_base + 0x267d4
	.size gb2312_uni2indx_page20, 0x194
	.globl gb2312_uni2indx_page30
	.set gb2312_uni2indx_page30, __f_rodata_base + 0x26968
	.size gb2312_uni2indx_page30, 0x8c
	.globl gb2312_uni2indx_page4e
	.set gb2312_uni2indx_page4e, __f_rodata_base + 0x269f4
	.size gb2312_uni2indx_page4e, 0x13bc
	.globl gb2312_uni2indx_page9e
	.set gb2312_uni2indx_page9e, __f_rodata_base + 0x27db0
	.size gb2312_uni2indx_page9e, 0x6c
	.globl gb2312_uni2indx_pageff
	.set gb2312_uni2indx_pageff, __f_rodata_base + 0x27e1c
	.size gb2312_uni2indx_pageff, 0x3c
	.globl isoir165ext_2uni_page2b
	.set isoir165ext_2uni_page2b, __f_rodata_base + 0x27e58
	.size isoir165ext_2uni_page2b, 0x3ac
	.globl isoir165ext_2uni_page7a
	.set isoir165ext_2uni_page7a, __f_rodata_base + 0x28204
	.size isoir165ext_2uni_page7a, 0x3ac
	.globl isoir165ext_2charset
	.set isoir165ext_2charset, __f_rodata_base + 0x285b0
	.size isoir165ext_2charset, 0x6d8
	.globl isoir165ext_uni2indx_page00
	.set isoir165ext_uni2indx_page00, __f_rodata_base + 0x28c88
	.size isoir165ext_uni2indx_page00, 0x80
	.globl isoir165ext_uni2indx_page03
	.set isoir165ext_uni2indx_page03, __f_rodata_base + 0x28d08
	.size isoir165ext_uni2indx_page03, 0x30
	.globl isoir165ext_uni2indx_page1e
	.set isoir165ext_uni2indx_page1e, __f_rodata_base + 0x28d38
	.size isoir165ext_uni2indx_page1e, 0x70
	.globl isoir165ext_uni2indx_page30
	.set isoir165ext_uni2indx_page30, __f_rodata_base + 0x28da8
	.size isoir165ext_uni2indx_page30, 0x10
	.globl isoir165ext_uni2indx_page32
	.set isoir165ext_uni2indx_page32, __f_rodata_base + 0x28db8
	.size isoir165ext_uni2indx_page32, 0x80
	.globl isoir165ext_uni2indx_page4e
	.set isoir165ext_uni2indx_page4e, __f_rodata_base + 0x28e38
	.size isoir165ext_uni2indx_page4e, 0xbc0
	.globl isoir165ext_uni2indx_page7e
	.set isoir165ext_uni2indx_page7e, __f_rodata_base + 0x299f8
	.size isoir165ext_uni2indx_page7e, 0x534
	.globl isoir165ext_uni2indx_page94
	.set isoir165ext_uni2indx_page94, __f_rodata_base + 0x29f2c
	.size isoir165ext_uni2indx_page94, 0x23c
	.globl isoir165ext_uni2indx_page9e
	.set isoir165ext_uni2indx_page9e, __f_rodata_base + 0x2a168
	.size isoir165ext_uni2indx_page9e, 0x64
	.globl isoir165ext_uni2indx_pageff
	.set isoir165ext_uni2indx_pageff, __f_rodata_base + 0x2a1cc
	.size isoir165ext_uni2indx_pageff, 0x14
	.globl gbkext1_2uni_page81
	.set gbkext1_2uni_page81, __f_rodata_base + 0x2a1e0
	.size gbkext1_2uni_page81, 0x2f80
	.globl gbkext2_2uni_pagea8
	.set gbkext2_2uni_pagea8, __f_rodata_base + 0x2d160
	.size gbkext2_2uni_pagea8, 0x40a0
	.globl gbkext_inv_2charset
	.set gbkext_inv_2charset, __f_rodata_base + 0x31200
	.size gbkext_inv_2charset, 0x6fd2
	.globl gbkext_inv_uni2indx_page02
	.set gbkext_inv_uni2indx_page02, __f_rodata_base + 0x381d4
	.size gbkext_inv_uni2indx_page02, 0x38
	.globl gbkext_inv_uni2indx_page20
	.set gbkext_inv_uni2indx_page20, __f_rodata_base + 0x3820c
	.size gbkext_inv_uni2indx_page20, 0xb0
	.globl gbkext_inv_uni2indx_page25
	.set gbkext_inv_uni2indx_page25, __f_rodata_base + 0x382bc
	.size gbkext_inv_uni2indx_page25, 0x44
	.globl gbkext_inv_uni2indx_page30
	.set gbkext_inv_uni2indx_page30, __f_rodata_base + 0x38300
	.size gbkext_inv_uni2indx_page30, 0x40
	.globl gbkext_inv_uni2indx_page32
	.set gbkext_inv_uni2indx_page32, __f_rodata_base + 0x38340
	.size gbkext_inv_uni2indx_page32, 0x78
	.globl gbkext_inv_uni2indx_page4e
	.set gbkext_inv_uni2indx_page4e, __f_rodata_base + 0x383b8
	.size gbkext_inv_uni2indx_page4e, 0x146c
	.globl gbkext_inv_uni2indx_pagef9
	.set gbkext_inv_uni2indx_pagef9, __f_rodata_base + 0x39824
	.size gbkext_inv_uni2indx_pagef9, 0x4c
	.globl gbkext_inv_uni2indx_pagefe
	.set gbkext_inv_uni2indx_pagefe, __f_rodata_base + 0x39870
	.size gbkext_inv_uni2indx_pagefe, 0x7c
	.globl cp936ext_2uni_pagea6
	.set cp936ext_2uni_pagea6, __f_rodata_base + 0x398ec
	.size cp936ext_2uni_pagea6, 0x2c
	.globl cp936ext_2uni_pagea8
	.set cp936ext_2uni_pagea8, __f_rodata_base + 0x39918
	.size cp936ext_2uni_pagea8, 0xc
	.globl cp936ext_page01
	.set cp936ext_page01, __f_rodata_base + 0x39924
	.size cp936ext_page01, 0x20
	.globl cp936ext_page02
	.set cp936ext_page02, __f_rodata_base + 0x39944
	.size cp936ext_page02, 0x30
	.globl cp936ext_pagefe
	.set cp936ext_pagefe, __f_rodata_base + 0x39974
	.size cp936ext_pagefe, 0x30
	.globl cns11643_1_2uni_page21
	.set cns11643_1_2uni_page21, __f_rodata_base + 0x399a4
	.size cns11643_1_2uni_page21, 0x3e8
	.globl cns11643_1_2uni_page42
	.set cns11643_1_2uni_page42, __f_rodata_base + 0x39d8c
	.size cns11643_1_2uni_page42, 0x44
	.globl cns11643_1_2uni_page44
	.set cns11643_1_2uni_page44, __f_rodata_base + 0x39dd0
	.size cns11643_1_2uni_page44, 0x2a32
	.globl cns11643_2_2uni_page21
	.set cns11643_2_2uni_page21, __f_rodata_base + 0x3c804
	.size cns11643_2_2uni_page21, 0x3bc4
	.globl cns11643_3_2uni_page21
	.set cns11643_3_2uni_page21, __f_rodata_base + 0x403c8
	.size cns11643_3_2uni_page21, 0x3008
	.globl cns11643_3_2uni_page64
	.set cns11643_3_2uni_page64, __f_rodata_base + 0x433d0
	.size cns11643_3_2uni_page64, 0x248
	.globl cns11643_3_2uni_upages
	.set cns11643_3_2uni_upages, __f_rodata_base + 0x43618
	.size cns11643_3_2uni_upages, 0x220
	.globl cns11643_4a_2uni_page21
	.set cns11643_4a_2uni_page21, __f_rodata_base + 0x43838
	.size cns11643_4a_2uni_page21, 0x16c4
	.globl cns11643_4a_2uni_upages
	.set cns11643_4a_2uni_upages, __f_rodata_base + 0x44efc
	.size cns11643_4a_2uni_upages, 0x350
	.globl cns11643_4b_2uni_page40
	.set cns11643_4b_2uni_page40, __f_rodata_base + 0x4524c
	.size cns11643_4b_2uni_page40, 0x2240
	.globl cns11643_4b_2uni_upages
	.set cns11643_4b_2uni_upages, __f_rodata_base + 0x4748c
	.size cns11643_4b_2uni_upages, 0x3e0
	.globl cns11643_5_2uni_page21
	.set cns11643_5_2uni_page21, __f_rodata_base + 0x4786c
	.size cns11643_5_2uni_page21, 0x4336
	.globl cns11643_5_2uni_upages
	.set cns11643_5_2uni_upages, __f_rodata_base + 0x4bba4
	.size cns11643_5_2uni_upages, 0x394
	.globl cns11643_6_2uni_page21
	.set cns11643_6_2uni_page21, __f_rodata_base + 0x4bf38
	.size cns11643_6_2uni_page21, 0x31e8
	.globl cns11643_6_2uni_upages
	.set cns11643_6_2uni_upages, __f_rodata_base + 0x4f120
	.size cns11643_6_2uni_upages, 0x330
	.globl cns11643_7_2uni_page21
	.set cns11643_7_2uni_page21, __f_rodata_base + 0x4f450
	.size cns11643_7_2uni_page21, 0x3316
	.globl cns11643_7_2uni_upages
	.set cns11643_7_2uni_upages, __f_rodata_base + 0x52768
	.size cns11643_7_2uni_upages, 0x318
	.globl cns11643_15_2uni_page21
	.set cns11643_15_2uni_page21, __f_rodata_base + 0x52a80
	.size cns11643_15_2uni_page21, 0x3802
	.globl cns11643_15_2uni_upages
	.set cns11643_15_2uni_upages, __f_rodata_base + 0x56284
	.size cns11643_15_2uni_upages, 0x3f4
	.globl cns11643_inv_2charset
	.set cns11643_inv_2charset, __f_rodata_base + 0x56678
	.size cns11643_inv_2charset, 0x289b6
	.globl cns11643_inv_uni2indx_page00
	.set cns11643_inv_uni2indx_page00, __f_rodata_base + 0x7f030
	.size cns11643_inv_uni2indx_page00, 0x40
	.globl cns11643_inv_uni2indx_page02
	.set cns11643_inv_uni2indx_page02, __f_rodata_base + 0x7f070
	.size cns11643_inv_uni2indx_page02, 0x74
	.globl cns11643_inv_uni2indx_page20
	.set cns11643_inv_uni2indx_page20, __f_rodata_base + 0x7f0e4
	.size cns11643_inv_uni2indx_page20, 0xb0
	.globl cns11643_inv_uni2indx_page24
	.set cns11643_inv_uni2indx_page24, __f_rodata_base + 0x7f194
	.size cns11643_inv_uni2indx_page24, 0x94
	.globl cns11643_inv_uni2indx_page30
	.set cns11643_inv_uni2indx_page30, __f_rodata_base + 0x7f228
	.size cns11643_inv_uni2indx_page30, 0x1bec
	.globl cns11643_inv_uni2indx_pagefa
	.set cns11643_inv_uni2indx_pagefa, __f_rodata_base + 0x80e14
	.size cns11643_inv_uni2indx_pagefa, 0xc
	.globl cns11643_inv_uni2indx_pagefe
	.set cns11643_inv_uni2indx_pagefe, __f_rodata_base + 0x80e20
	.size cns11643_inv_uni2indx_pagefe, 0x7c
	.globl cns11643_inv_uni2indx_page200
	.set cns11643_inv_uni2indx_page200, __f_rodata_base + 0x80e9c
	.size cns11643_inv_uni2indx_page200, 0x29b8
	.globl cns11643_inv_uni2indx_page2f8
	.set cns11643_inv_uni2indx_page2f8, __f_rodata_base + 0x83854
	.size cns11643_inv_uni2indx_page2f8, 0x88
	.globl big5_2uni_pagea1
	.set big5_2uni_pagea1, __f_rodata_base + 0x838dc
	.size big5_2uni_pagea1, 0x2fd2
	.globl big5_2uni_pagec9
	.set big5_2uni_pagec9, __f_rodata_base + 0x868b0
	.size big5_2uni_pagec9, 0x3bc8
	.globl big5_2charset
	.set big5_2charset, __f_rodata_base + 0x8a478
	.size big5_2charset, 0x6b0e
	.globl big5_uni2indx_page00
	.set big5_uni2indx_page00, __f_rodata_base + 0x90f88
	.size big5_uni2indx_page00, 0x40
	.globl big5_uni2indx_page02
	.set big5_uni2indx_page02, __f_rodata_base + 0x90fc8
	.size big5_uni2indx_page02, 0x98
	.globl big5_uni2indx_page20
	.set big5_uni2indx_page20, __f_rodata_base + 0x91060
	.size big5_uni2indx_page20, 0xb0
	.globl big5_uni2indx_page24
	.set big5_uni2indx_page24, __f_rodata_base + 0x91110
	.size big5_uni2indx_page24, 0x94
	.globl big5_uni2indx_page30
	.set big5_uni2indx_page30, __f_rodata_base + 0x911a4
	.size big5_uni2indx_page30, 0xf8
	.globl big5_uni2indx_page4e
	.set big5_uni2indx_page4e, __f_rodata_base + 0x9129c
	.size big5_uni2indx_page4e, 0x146c
	.globl big5_uni2indx_pagefa
	.set big5_uni2indx_pagefa, __f_rodata_base + 0x92708
	.size big5_uni2indx_pagefa, 0x4
	.globl big5_uni2indx_pagefe
	.set big5_uni2indx_pagefe, __f_rodata_base + 0x9270c
	.size big5_uni2indx_pagefe, 0x5c
	.globl ksc5601_2uni_page21
	.set ksc5601_2uni_page21, __f_rodata_base + 0x92768
	.size ksc5601_2uni_page21, 0x8b6
	.globl ksc5601_2uni_page30
	.set ksc5601_2uni_page30, __f_rodata_base + 0x93020
	.size ksc5601_2uni_page30, 0x125c
	.globl ksc5601_2uni_page4a
	.set ksc5601_2uni_page4a, __f_rodata_base + 0x9427c
	.size ksc5601_2uni_page4a, 0x2630
	.globl ksc5601_2charset
	.set ksc5601_2charset, __f_rodata_base + 0x968ac
	.size ksc5601_2charset, 0x4046
	.globl ksc5601_uni2indx_page00
	.set ksc5601_uni2indx_page00, __f_rodata_base + 0x9a8f4
	.size ksc5601_uni2indx_page00, 0x118
	.globl ksc5601_uni2indx_page20
	.set ksc5601_uni2indx_page20, __f_rodata_base + 0x9aa0c
	.size ksc5601_uni2indx_page20, 0x19c
	.globl ksc5601_uni2indx_page30
	.set ksc5601_uni2indx_page30, __f_rodata_base + 0x9aba8
	.size ksc5601_uni2indx_page30, 0xf8
	.globl ksc5601_uni2indx_page4e
	.set ksc5601_uni2indx_page4e, __f_rodata_base + 0x9aca0
	.size ksc5601_uni2indx_page4e, 0x1468
	.globl ksc5601_uni2indx_pageac
	.set ksc5601_uni2indx_pageac, __f_rodata_base + 0x9c108
	.size ksc5601_uni2indx_pageac, 0xae8
	.globl ksc5601_uni2indx_pagef9
	.set ksc5601_uni2indx_pagef9, __f_rodata_base + 0x9cbf0
	.size ksc5601_uni2indx_pagef9, 0x44
	.globl ksc5601_uni2indx_pageff
	.set ksc5601_uni2indx_pageff, __f_rodata_base + 0x9cc34
	.size ksc5601_uni2indx_pageff, 0x3c
	.globl jamo_initial
	.set jamo_initial, __f_rodata_base + 0x9cc70
	.size jamo_initial, 0x20
	.globl jamo_medial
	.set jamo_medial, __f_rodata_base + 0x9cc90
	.size jamo_medial, 0x20
	.globl jamo_final
	.set jamo_final, __f_rodata_base + 0x9ccb0
	.size jamo_final, 0x20
	.globl jamo_final_notinitial
	.set jamo_final_notinitial, __f_rodata_base + 0x9ccd0
	.size jamo_final_notinitial, 0x20
	.globl jamo_initial_index
	.set jamo_initial_index, __f_rodata_base + 0x9ccf0
	.size jamo_initial_index, 0x20
	.globl jamo_medial_index
	.set jamo_medial_index, __f_rodata_base + 0x9cd10
	.size jamo_medial_index, 0x20
	.globl jamo_final_index
	.set jamo_final_index, __f_rodata_base + 0x9cd30
	.size jamo_final_index, 0x20
	.globl johab_hangul_page31
	.set johab_hangul_page31, __f_rodata_base + 0x9cd50
	.size johab_hangul_page31, 0x66
	.globl jamo_initial_index_inverse
	.set jamo_initial_index_inverse, __f_rodata_base + 0x9cdb8
	.size jamo_initial_index_inverse, 0x13
	.globl jamo_medial_index_inverse
	.set jamo_medial_index_inverse, __f_rodata_base + 0x9cdcc
	.size jamo_medial_index_inverse, 0x15
	.globl jamo_final_index_inverse
	.set jamo_final_index_inverse, __f_rodata_base + 0x9cde4
	.size jamo_final_index_inverse, 0x1c
	.globl cp932ext_2uni_page87
	.set cp932ext_2uni_page87, __f_rodata_base + 0x9ce00
	.size cp932ext_2uni_page87, 0xb8
	.globl cp932ext_2uni_pageed
	.set cp932ext_2uni_pageed, __f_rodata_base + 0x9ceb8
	.size cp932ext_2uni_pageed, 0x2f0
	.globl cp932ext_2uni_pagefa
	.set cp932ext_2uni_pagefa, __f_rodata_base + 0x9d1a8
	.size cp932ext_2uni_pagefa, 0x308
	.globl cp932ext_2charset
	.set cp932ext_2charset, __f_rodata_base + 0x9d4b0
	.size cp932ext_2charset, 0x392
	.globl cp932ext_uni2indx_page21
	.set cp932ext_uni2indx_page21, __f_rodata_base + 0x9d844
	.size cp932ext_uni2indx_page21, 0x70
	.globl cp932ext_uni2indx_page24
	.set cp932ext_uni2indx_page24, __f_rodata_base + 0x9d8b4
	.size cp932ext_uni2indx_page24, 0x20
	.globl cp932ext_uni2indx_page30
	.set cp932ext_uni2indx_page30, __f_rodata_base + 0x9d8d4
	.size cp932ext_uni2indx_page30, 0x8
	.globl cp932ext_uni2indx_page32
	.set cp932ext_uni2indx_page32, __f_rodata_base + 0x9d8dc
	.size cp932ext_uni2indx_page32, 0x74
	.globl cp932ext_uni2indx_page4e
	.set cp932ext_uni2indx_page4e, __f_rodata_base + 0x9d950
	.size cp932ext_uni2indx_page4e, 0x1e4
	.globl cp932ext_uni2indx_page57
	.set cp932ext_uni2indx_page57, __f_rodata_base + 0x9db34
	.size cp932ext_uni2indx_page57, 0xb0
	.globl cp932ext_uni2indx_page5b
	.set cp932ext_uni2indx_page5b, __f_rodata_base + 0x9dbe4
	.size cp932ext_uni2indx_page5b, 0xb8
	.globl cp932ext_uni2indx_page5f
	.set cp932ext_uni2indx_page5f, __f_rodata_base + 0x9dc9c
	.size cp932ext_uni2indx_page5f, 0x728
	.globl cp932ext_uni2indx_page7d
	.set cp932ext_uni2indx_page7d, __f_rodata_base + 0x9e3c4
	.size cp932ext_uni2indx_page7d, 0xac
	.globl cp932ext_uni2indx_page83
	.set cp932ext_uni2indx_page83, __f_rodata_base + 0x9e470
	.size cp932ext_uni2indx_page83, 0xb0
	.globl cp932ext_uni2indx_page88
	.set cp932ext_uni2indx_page88, __f_rodata_base + 0x9e520
	.size cp932ext_uni2indx_page88, 0x1b4
	.globl cp932ext_uni2indx_page90
	.set cp932ext_uni2indx_page90, __f_rodata_base + 0x9e6d4
	.size cp932ext_uni2indx_page90, 0x3b8
	.globl cp932ext_uni2indx_pagef9
	.set cp932ext_uni2indx_pagef9, __f_rodata_base + 0x9ea8c
	.size cp932ext_uni2indx_pagef9, 0x4c
	.globl cp932ext_uni2indx_pageff
	.set cp932ext_uni2indx_pageff, __f_rodata_base + 0x9ead8
	.size cp932ext_uni2indx_pageff, 0x3c
	.globl cp50221_0208_ext_2uni
	.set cp50221_0208_ext_2uni, __f_rodata_base + 0x9eb14
	.size cp50221_0208_ext_2uni, 0xc0
	.globl cp50221_0208_ext_page21
	.set cp50221_0208_ext_page21, __f_rodata_base + 0x9ebd4
	.size cp50221_0208_ext_page21, 0x60
	.globl cp50221_0208_ext_page22
	.set cp50221_0208_ext_page22, __f_rodata_base + 0x9ec34
	.size cp50221_0208_ext_page22, 0x20
	.globl cp50221_0208_ext_page24
	.set cp50221_0208_ext_page24, __f_rodata_base + 0x9ec54
	.size cp50221_0208_ext_page24, 0x18
	.globl cp50221_0208_ext_page30
	.set cp50221_0208_ext_page30, __f_rodata_base + 0x9ec6c
	.size cp50221_0208_ext_page30, 0x8
	.globl cp50221_0208_ext_page32
	.set cp50221_0208_ext_page32, __f_rodata_base + 0x9ec74
	.size cp50221_0208_ext_page32, 0x10
	.globl cp50221_0208_ext_page32_1
	.set cp50221_0208_ext_page32_1, __f_rodata_base + 0x9ec84
	.size cp50221_0208_ext_page32_1, 0x10
	.globl cp50221_0208_ext_page33
	.set cp50221_0208_ext_page33, __f_rodata_base + 0x9ec94
	.size cp50221_0208_ext_page33, 0xd0
	.globl cp50221_0212_ext_2uni
	.set cp50221_0212_ext_2uni, __f_rodata_base + 0x9ed64
	.size cp50221_0212_ext_2uni, 0xe0
	.globl cp50221_0212_ext_page21
	.set cp50221_0212_ext_page21, __f_rodata_base + 0x9ee44
	.size cp50221_0212_ext_page21, 0x10
	.globl cp50221_0212_ext_page53
	.set cp50221_0212_ext_page53, __f_rodata_base + 0x9ee54
	.size cp50221_0212_ext_page53, 0x28
	.globl cp50221_0212_ext_page6d
	.set cp50221_0212_ext_page6d, __f_rodata_base + 0x9ee7c
	.size cp50221_0212_ext_page6d, 0x10
	.globl cp50221_0212_ext_page76
	.set cp50221_0212_ext_page76, __f_rodata_base + 0x9ee8c
	.size cp50221_0212_ext_page76, 0x20
	.globl cp50221_0212_ext_page7d
	.set cp50221_0212_ext_page7d, __f_rodata_base + 0x9eeac
	.size cp50221_0212_ext_page7d, 0x38
	.globl cp50221_0212_ext_page97
	.set cp50221_0212_ext_page97, __f_rodata_base + 0x9eee4
	.size cp50221_0212_ext_page97, 0x20
	.globl cp50221_0212_ext_pagefa
	.set cp50221_0212_ext_pagefa, __f_rodata_base + 0x9ef04
	.size cp50221_0212_ext_pagefa, 0x28
	.globl cp50221_0212_ext_pageff
	.set cp50221_0212_ext_pageff, __f_rodata_base + 0x9ef2c
	.size cp50221_0212_ext_pageff, 0x8
	.globl gb18030ext_2uni_pagea9
	.set gb18030ext_2uni_pagea9, __f_rodata_base + 0x9ef34
	.size gb18030ext_2uni_pagea9, 0x1a
	.globl gb18030ext_2uni_pagefe
	.set gb18030ext_2uni_pagefe, __f_rodata_base + 0x9ef50
	.size gb18030ext_2uni_pagefe, 0x180
	.globl gb18030ext_page2e
	.set gb18030ext_page2e, __f_rodata_base + 0x9f0d0
	.size gb18030ext_page2e, 0xa0
	.globl gb18030ext_page2f
	.set gb18030ext_page2f, __f_rodata_base + 0x9f170
	.size gb18030ext_page2f, 0x20
	.globl gb18030ext_page34
	.set gb18030ext_page34, __f_rodata_base + 0x9f190
	.size gb18030ext_page34, 0x70
	.globl gb18030ext_page36
	.set gb18030ext_page36, __f_rodata_base + 0x9f200
	.size gb18030ext_page36, 0x30
	.globl gb18030ext_page39
	.set gb18030ext_page39, __f_rodata_base + 0x9f230
	.size gb18030ext_page39, 0x30
	.globl gb18030ext_page43
	.set gb18030ext_page43, __f_rodata_base + 0x9f260
	.size gb18030ext_page43, 0x70
	.globl gb18030ext_page46
	.set gb18030ext_page46, __f_rodata_base + 0x9f2d0
	.size gb18030ext_page46, 0x40
	.globl gb18030ext_page47_1
	.set gb18030ext_page47_1, __f_rodata_base + 0x9f310
	.size gb18030ext_page47_1, 0x20
	.globl gb18030ext_page47_2
	.set gb18030ext_page47_2, __f_rodata_base + 0x9f330
	.size gb18030ext_page47_2, 0x30
	.globl gb18030ext_page49
	.set gb18030ext_page49, __f_rodata_base + 0x9f360
	.size gb18030ext_page49, 0xf0
	.globl gb18030ext_page4c
	.set gb18030ext_page4c, __f_rodata_base + 0x9f450
	.size gb18030ext_page4c, 0x70
	.globl gb18030ext_page4d
	.set gb18030ext_page4d, __f_rodata_base + 0x9f4c0
	.size gb18030ext_page4d, 0x20
	.globl gb18030ext_page9f
	.set gb18030ext_page9f, __f_rodata_base + 0x9f4e0
	.size gb18030ext_page9f, 0x20
	.globl gb18030ext_pagefe
	.set gb18030ext_pagefe, __f_rodata_base + 0x9f500
	.size gb18030ext_pagefe, 0x20
	.globl gb18030uni_charset2uni_ranges
	.set gb18030uni_charset2uni_ranges, __f_rodata_base + 0x9f520
	.size gb18030uni_charset2uni_ranges, 0x338
	.globl gb18030uni_uni2charset_ranges
	.set gb18030uni_uni2charset_ranges, __f_rodata_base + 0x9f858
	.size gb18030uni_uni2charset_ranges, 0x338
	.globl gb18030uni_ranges
	.set gb18030uni_ranges, __f_rodata_base + 0x9fb90
	.size gb18030uni_ranges, 0x19c
	.globl gb18030_pua2charset
	.set gb18030_pua2charset, __f_rodata_base + 0x9fd2c
	.size gb18030_pua2charset, 0xba
	.globl cp950_2uni_pagea1
	.set cp950_2uni_pagea1, __f_rodata_base + 0x9fde8
	.size cp950_2uni_pagea1, 0x274
	.globl cp950ext_2uni_pagef9
	.set cp950ext_2uni_pagef9, __f_rodata_base + 0xa005c
	.size cp950ext_2uni_pagef9, 0x52
	.globl cp950ext_2charset
	.set cp950ext_2charset, __f_rodata_base + 0xa00b0
	.size cp950ext_2charset, 0x52
	.globl cp950ext_uni2indx_page25
	.set cp950ext_uni2indx_page25, __f_rodata_base + 0xa0104
	.size cp950ext_uni2indx_page25, 0x28
	.globl cp950ext_uni2indx_page58
	.set cp950ext_uni2indx_page58, __f_rodata_base + 0xa012c
	.size cp950ext_uni2indx_page58, 0x30
	.globl cp950ext_uni2indx_page5a
	.set cp950ext_uni2indx_page5a, __f_rodata_base + 0xa015c
	.size cp950ext_uni2indx_page5a, 0x40
	.globl cp950ext_uni2indx_page60
	.set cp950ext_uni2indx_page60, __f_rodata_base + 0xa019c
	.size cp950ext_uni2indx_page60, 0x18
	.globl cp950ext_uni2indx_page78
	.set cp950ext_uni2indx_page78, __f_rodata_base + 0xa01b4
	.size cp950ext_uni2indx_page78, 0x24
	.globl cp950ext_uni2indx_page7c
	.set cp950ext_uni2indx_page7c, __f_rodata_base + 0xa01d8
	.size cp950ext_uni2indx_page7c, 0x2c
	.globl cp950ext_uni2indx_page88
	.set cp950ext_uni2indx_page88, __f_rodata_base + 0xa0204
	.size cp950ext_uni2indx_page88, 0x34
	.globl cp950ext_uni2indx_page92
	.set cp950ext_uni2indx_page92, __f_rodata_base + 0xa0238
	.size cp950ext_uni2indx_page92, 0x30
	.globl hkscs1999_2uni_page88
	.set hkscs1999_2uni_page88, __f_rodata_base + 0xa0268
	.size hkscs1999_2uni_page88, 0x4e6
	.globl hkscs1999_2uni_page8d
	.set hkscs1999_2uni_page8d, __f_rodata_base + 0xa0750
	.size hkscs1999_2uni_page8d, 0x1888
	.globl hkscs1999_2uni_pagec6
	.set hkscs1999_2uni_pagec6, __f_rodata_base + 0xa1fd8
	.size hkscs1999_2uni_pagec6, 0x3ae
	.globl hkscs1999_2uni_pagef9
	.set hkscs1999_2uni_pagef9, __f_rodata_base + 0xa2388
	.size hkscs1999_2uni_pagef9, 0x75c
	.globl hkscs1999_2uni_upages
	.set hkscs1999_2uni_upages, __f_rodata_base + 0xa2ae4
	.size hkscs1999_2uni_upages, 0xf34
	.globl hkscs1999_2charset
	.set hkscs1999_2charset, __f_rodata_base + 0xa3a18
	.size hkscs1999_2charset, 0x24b4
	.globl hkscs1999_uni2indx_page00
	.set hkscs1999_uni2indx_page00, __f_rodata_base + 0xa5ecc
	.size hkscs1999_uni2indx_page00, 0xb4
	.globl hkscs1999_uni2indx_page04
	.set hkscs1999_uni2indx_page04, __f_rodata_base + 0xa5f80
	.size hkscs1999_uni2indx_page04, 0x18
	.globl hkscs1999_uni2indx_page1e
	.set hkscs1999_uni2indx_page1e, __f_rodata_base + 0xa5f98
	.size hkscs1999_uni2indx_page1e, 0x34
	.globl hkscs1999_uni2indx_page21
	.set hkscs1999_uni2indx_page21, __f_rodata_base + 0xa5fcc
	.size hkscs1999_uni2indx_page21, 0x3c
	.globl hkscs1999_uni2indx_page23
	.set hkscs1999_uni2indx_page23, __f_rodata_base + 0xa6008
	.size hkscs1999_uni2indx_page23, 0xa0
	.globl hkscs1999_uni2indx_page27
	.set hkscs1999_uni2indx_page27, __f_rodata_base + 0xa60a8
	.size hkscs1999_uni2indx_page27, 0x10
	.globl hkscs1999_uni2indx_page2e
	.set hkscs1999_uni2indx_page2e, __f_rodata_base + 0xa60b8
	.size hkscs1999_uni2indx_page2e, 0x110
	.globl hkscs1999_uni2indx_page34
	.set hkscs1999_uni2indx_page34, __f_rodata_base + 0xa61c8
	.size hkscs1999_uni2indx_page34, 0x1af0
	.globl hkscs1999_uni2indx_pagef9
	.set hkscs1999_uni2indx_pagef9, __f_rodata_base + 0xa7cb8
	.size hkscs1999_uni2indx_pagef9, 0x4
	.globl hkscs1999_uni2indx_pageff
	.set hkscs1999_uni2indx_pageff, __f_rodata_base + 0xa7cbc
	.size hkscs1999_uni2indx_pageff, 0x3c
	.globl hkscs1999_uni2indx_page200
	.set hkscs1999_uni2indx_page200, __f_rodata_base + 0xa7cf8
	.size hkscs1999_uni2indx_page200, 0x247c
	.globl hkscs1999_uni2indx_page294
	.set hkscs1999_uni2indx_page294, __f_rodata_base + 0xaa174
	.size hkscs1999_uni2indx_page294, 0x80
	.globl hkscs1999_uni2indx_page297
	.set hkscs1999_uni2indx_page297, __f_rodata_base + 0xaa1f4
	.size hkscs1999_uni2indx_page297, 0x3ec
	.globl hkscs1999_uni2indx_page2f8
	.set hkscs1999_uni2indx_page2f8, __f_rodata_base + 0xaa5e0
	.size hkscs1999_uni2indx_page2f8, 0x78
	.globl hkscs2001_2uni_page8c
	.set hkscs2001_2uni_page8c, __f_rodata_base + 0xaa658
	.size hkscs2001_2uni_page8c, 0xf6
	.globl hkscs2001_2uni_upages
	.set hkscs2001_2uni_upages, __f_rodata_base + 0xaa750
	.size hkscs2001_2uni_upages, 0x154
	.globl hkscs2001_2charset
	.set hkscs2001_2charset, __f_rodata_base + 0xaa8a4
	.size hkscs2001_2charset, 0xe8
	.globl hkscs2001_uni2indx_page35
	.set hkscs2001_uni2indx_page35, __f_rodata_base + 0xaa98c
	.size hkscs2001_uni2indx_page35, 0x18
	.globl hkscs2001_uni2indx_page3c
	.set hkscs2001_uni2indx_page3c, __f_rodata_base + 0xaa9a4
	.size hkscs2001_uni2indx_page3c, 0xb8
	.globl hkscs2001_uni2indx_page40
	.set hkscs2001_uni2indx_page40, __f_rodata_base + 0xaaa5c
	.size hkscs2001_uni2indx_page40, 0x20
	.globl hkscs2001_uni2indx_page42
	.set hkscs2001_uni2indx_page42, __f_rodata_base + 0xaaa7c
	.size hkscs2001_uni2indx_page42, 0x2c
	.globl hkscs2001_uni2indx_page4b
	.set hkscs2001_uni2indx_page4b, __f_rodata_base + 0xaaaa8
	.size hkscs2001_uni2indx_page4b, 0x64
	.globl hkscs2001_uni2indx_page4e
	.set hkscs2001_uni2indx_page4e, __f_rodata_base + 0xaab0c
	.size hkscs2001_uni2indx_page4e, 0xec
	.globl hkscs2001_uni2indx_page53
	.set hkscs2001_uni2indx_page53, __f_rodata_base + 0xaabf8
	.size hkscs2001_uni2indx_page53, 0x50
	.globl hkscs2001_uni2indx_page57
	.set hkscs2001_uni2indx_page57, __f_rodata_base + 0xaac48
	.size hkscs2001_uni2indx_page57, 0x78
	.globl hkscs2001_uni2indx_page5a
	.set hkscs2001_uni2indx_page5a, __f_rodata_base + 0xaacc0
	.size hkscs2001_uni2indx_page5a, 0x174
	.globl hkscs2001_uni2indx_page61
	.set hkscs2001_uni2indx_page61, __f_rodata_base + 0xaae34
	.size hkscs2001_uni2indx_page61, 0xc
	.globl hkscs2001_uni2indx_page65
	.set hkscs2001_uni2indx_page65, __f_rodata_base + 0xaae40
	.size hkscs2001_uni2indx_page65, 0x24
	.globl hkscs2001_uni2indx_page67
	.set hkscs2001_uni2indx_page67, __f_rodata_base + 0xaae64
	.size hkscs2001_uni2indx_page67, 0x1c
	.globl hkscs2001_uni2indx_page69
	.set hkscs2001_uni2indx_page69, __f_rodata_base + 0xaae80
	.size hkscs2001_uni2indx_page69, 0x5c
	.globl hkscs2001_uni2indx_page6c
	.set hkscs2001_uni2indx_page6c, __f_rodata_base + 0xaaedc
	.size hkscs2001_uni2indx_page6c, 0x80
	.globl hkscs2001_uni2indx_page70
	.set hkscs2001_uni2indx_page70, __f_rodata_base + 0xaaf5c
	.size hkscs2001_uni2indx_page70, 0x130
	.globl hkscs2001_uni2indx_page76
	.set hkscs2001_uni2indx_page76, __f_rodata_base + 0xab08c
	.size hkscs2001_uni2indx_page76, 0xbc
	.globl hkscs2001_uni2indx_page7a
	.set hkscs2001_uni2indx_page7a, __f_rodata_base + 0xab148
	.size hkscs2001_uni2indx_page7a, 0x11c
	.globl hkscs2001_uni2indx_page82
	.set hkscs2001_uni2indx_page82, __f_rodata_base + 0xab264
	.size hkscs2001_uni2indx_page82, 0x40
	.globl hkscs2001_uni2indx_page85
	.set hkscs2001_uni2indx_page85, __f_rodata_base + 0xab2a4
	.size hkscs2001_uni2indx_page85, 0x44
	.globl hkscs2001_uni2indx_page88
	.set hkscs2001_uni2indx_page88, __f_rodata_base + 0xab2e8
	.size hkscs2001_uni2indx_page88, 0x28
	.globl hkscs2001_uni2indx_page8b
	.set hkscs2001_uni2indx_page8b, __f_rodata_base + 0xab310
	.size hkscs2001_uni2indx_page8b, 0x24
	.globl hkscs2001_uni2indx_page8e
	.set hkscs2001_uni2indx_page8e, __f_rodata_base + 0xab334
	.size hkscs2001_uni2indx_page8e, 0x74
	.globl hkscs2001_uni2indx_page91
	.set hkscs2001_uni2indx_page91, __f_rodata_base + 0xab3a8
	.size hkscs2001_uni2indx_page91, 0xc0
	.globl hkscs2001_uni2indx_page97
	.set hkscs2001_uni2indx_page97, __f_rodata_base + 0xab468
	.size hkscs2001_uni2indx_page97, 0xbc
	.globl hkscs2001_uni2indx_page9f
	.set hkscs2001_uni2indx_page9f, __f_rodata_base + 0xab524
	.size hkscs2001_uni2indx_page9f, 0x2c
	.globl hkscs2001_uni2indx_page214
	.set hkscs2001_uni2indx_page214, __f_rodata_base + 0xab550
	.size hkscs2001_uni2indx_page214, 0x10
	.globl hkscs2001_uni2indx_page219
	.set hkscs2001_uni2indx_page219, __f_rodata_base + 0xab560
	.size hkscs2001_uni2indx_page219, 0x24
	.globl hkscs2001_uni2indx_page21d
	.set hkscs2001_uni2indx_page21d, __f_rodata_base + 0xab584
	.size hkscs2001_uni2indx_page21d, 0x30
	.globl hkscs2001_uni2indx_page220
	.set hkscs2001_uni2indx_page220, __f_rodata_base + 0xab5b4
	.size hkscs2001_uni2indx_page220, 0x20
	.globl hkscs2001_uni2indx_page227
	.set hkscs2001_uni2indx_page227, __f_rodata_base + 0xab5d4
	.size hkscs2001_uni2indx_page227, 0x8
	.globl hkscs2001_uni2indx_page232
	.set hkscs2001_uni2indx_page232, __f_rodata_base + 0xab5dc
	.size hkscs2001_uni2indx_page232, 0x80
	.globl hkscs2001_uni2indx_page23c
	.set hkscs2001_uni2indx_page23c, __f_rodata_base + 0xab65c
	.size hkscs2001_uni2indx_page23c, 0x1c
	.globl hkscs2001_uni2indx_page241
	.set hkscs2001_uni2indx_page241, __f_rodata_base + 0xab678
	.size hkscs2001_uni2indx_page241, 0x14
	.globl hkscs2001_uni2indx_page245
	.set hkscs2001_uni2indx_page245, __f_rodata_base + 0xab68c
	.size hkscs2001_uni2indx_page245, 0x4
	.globl hkscs2001_uni2indx_page249
	.set hkscs2001_uni2indx_page249, __f_rodata_base + 0xab690
	.size hkscs2001_uni2indx_page249, 0x48
	.globl hkscs2001_uni2indx_page251
	.set hkscs2001_uni2indx_page251, __f_rodata_base + 0xab6d8
	.size hkscs2001_uni2indx_page251, 0x34
	.globl hkscs2001_uni2indx_page256
	.set hkscs2001_uni2indx_page256, __f_rodata_base + 0xab70c
	.size hkscs2001_uni2indx_page256, 0x28
	.globl hkscs2001_uni2indx_page25c
	.set hkscs2001_uni2indx_page25c, __f_rodata_base + 0xab734
	.size hkscs2001_uni2indx_page25c, 0x50
	.globl hkscs2001_uni2indx_page26b
	.set hkscs2001_uni2indx_page26b, __f_rodata_base + 0xab784
	.size hkscs2001_uni2indx_page26b, 0x8
	.globl hkscs2001_uni2indx_page26d
	.set hkscs2001_uni2indx_page26d, __f_rodata_base + 0xab78c
	.size hkscs2001_uni2indx_page26d, 0x20
	.globl hkscs2001_uni2indx_page26f
	.set hkscs2001_uni2indx_page26f, __f_rodata_base + 0xab7ac
	.size hkscs2001_uni2indx_page26f, 0x30
	.globl hkscs2001_uni2indx_page271
	.set hkscs2001_uni2indx_page271, __f_rodata_base + 0xab7dc
	.size hkscs2001_uni2indx_page271, 0x4
	.globl hkscs2001_uni2indx_page287
	.set hkscs2001_uni2indx_page287, __f_rodata_base + 0xab7e0
	.size hkscs2001_uni2indx_page287, 0x4
	.globl hkscs2001_uni2indx_page289
	.set hkscs2001_uni2indx_page289, __f_rodata_base + 0xab7e4
	.size hkscs2001_uni2indx_page289, 0x7c
	.globl hkscs2001_uni2indx_page28d
	.set hkscs2001_uni2indx_page28d, __f_rodata_base + 0xab860
	.size hkscs2001_uni2indx_page28d, 0x30
	.globl hkscs2001_uni2indx_page299
	.set hkscs2001_uni2indx_page299, __f_rodata_base + 0xab890
	.size hkscs2001_uni2indx_page299, 0x14
	.globl hkscs2001_uni2indx_page29c
	.set hkscs2001_uni2indx_page29c, __f_rodata_base + 0xab8a4
	.size hkscs2001_uni2indx_page29c, 0x20
	.globl hkscs2001_uni2indx_page2a1
	.set hkscs2001_uni2indx_page2a1, __f_rodata_base + 0xab8c4
	.size hkscs2001_uni2indx_page2a1, 0x70
	.globl hkscs2004_2uni_page87
	.set hkscs2004_2uni_page87, __f_rodata_base + 0xab934
	.size hkscs2004_2uni_page87, 0x74
	.globl hkscs2004_2uni_page8c
	.set hkscs2004_2uni_page8c, __f_rodata_base + 0xab9a8
	.size hkscs2004_2uni_page8c, 0x17a
	.globl hkscs2004_2uni_upages
	.set hkscs2004_2uni_upages, __f_rodata_base + 0xabb24
	.size hkscs2004_2uni_upages, 0x138
	.globl hkscs2004_2charset
	.set hkscs2004_2charset, __f_rodata_base + 0xabc5c
	.size hkscs2004_2charset, 0xf6
	.globl hkscs2004_uni2indx_page34
	.set hkscs2004_uni2indx_page34, __f_rodata_base + 0xabd54
	.size hkscs2004_uni2indx_page34, 0x14
	.globl hkscs2004_uni2indx_page36
	.set hkscs2004_uni2indx_page36, __f_rodata_base + 0xabd68
	.size hkscs2004_uni2indx_page36, 0xe0
	.globl hkscs2004_uni2indx_page3b
	.set hkscs2004_uni2indx_page3b, __f_rodata_base + 0xabe48
	.size hkscs2004_uni2indx_page3b, 0x28
	.globl hkscs2004_uni2indx_page3d
	.set hkscs2004_uni2indx_page3d, __f_rodata_base + 0xabe70
	.size hkscs2004_uni2indx_page3d, 0x40
	.globl hkscs2004_uni2indx_page3f
	.set hkscs2004_uni2indx_page3f, __f_rodata_base + 0xabeb0
	.size hkscs2004_uni2indx_page3f, 0xbc
	.globl hkscs2004_uni2indx_page43
	.set hkscs2004_uni2indx_page43, __f_rodata_base + 0xabf6c
	.size hkscs2004_uni2indx_page43, 0x114
	.globl hkscs2004_uni2indx_page4a
	.set hkscs2004_uni2indx_page4a, __f_rodata_base + 0xac080
	.size hkscs2004_uni2indx_page4a, 0x2c
	.globl hkscs2004_uni2indx_page4c
	.set hkscs2004_uni2indx_page4c, __f_rodata_base + 0xac0ac
	.size hkscs2004_uni2indx_page4c, 0x64
	.globl hkscs2004_uni2indx_page4f
	.set hkscs2004_uni2indx_page4f, __f_rodata_base + 0xac110
	.size hkscs2004_uni2indx_page4f, 0x30
	.globl hkscs2004_uni2indx_page56
	.set hkscs2004_uni2indx_page56, __f_rodata_base + 0xac140
	.size hkscs2004_uni2indx_page56, 0x40
	.globl hkscs2004_uni2indx_page59
	.set hkscs2004_uni2indx_page59, __f_rodata_base + 0xac180
	.size hkscs2004_uni2indx_page59, 0x120
	.globl hkscs2004_uni2indx_page5f
	.set hkscs2004_uni2indx_page5f, __f_rodata_base + 0xac2a0
	.size hkscs2004_uni2indx_page5f, 0x10
	.globl hkscs2004_uni2indx_page66
	.set hkscs2004_uni2indx_page66, __f_rodata_base + 0xac2b0
	.size hkscs2004_uni2indx_page66, 0x5c
	.globl hkscs2004_uni2indx_page6e
	.set hkscs2004_uni2indx_page6e, __f_rodata_base + 0xac30c
	.size hkscs2004_uni2indx_page6e, 0x18
	.globl hkscs2004_uni2indx_page71
	.set hkscs2004_uni2indx_page71, __f_rodata_base + 0xac324
	.size hkscs2004_uni2indx_page71, 0x4c
	.globl hkscs2004_uni2indx_page74
	.set hkscs2004_uni2indx_page74, __f_rodata_base + 0xac370
	.size hkscs2004_uni2indx_page74, 0x28
	.globl hkscs2004_uni2indx_page79
	.set hkscs2004_uni2indx_page79, __f_rodata_base + 0xac398
	.size hkscs2004_uni2indx_page79, 0x34
	.globl hkscs2004_uni2indx_page7d
	.set hkscs2004_uni2indx_page7d, __f_rodata_base + 0xac3cc
	.size hkscs2004_uni2indx_page7d, 0x28
	.globl hkscs2004_uni2indx_page81
	.set hkscs2004_uni2indx_page81, __f_rodata_base + 0xac3f4
	.size hkscs2004_uni2indx_page81, 0x1c
	.globl hkscs2004_uni2indx_page85
	.set hkscs2004_uni2indx_page85, __f_rodata_base + 0xac410
	.size hkscs2004_uni2indx_page85, 0x28
	.globl hkscs2004_uni2indx_page8a
	.set hkscs2004_uni2indx_page8a, __f_rodata_base + 0xac438
	.size hkscs2004_uni2indx_page8a, 0x40
	.globl hkscs2004_uni2indx_page97
	.set hkscs2004_uni2indx_page97, __f_rodata_base + 0xac478
	.size hkscs2004_uni2indx_page97, 0x58
	.globl hkscs2004_uni2indx_page9f
	.set hkscs2004_uni2indx_page9f, __f_rodata_base + 0xac4d0
	.size hkscs2004_uni2indx_page9f, 0x30
	.globl hkscs2004_uni2indx_page201
	.set hkscs2004_uni2indx_page201, __f_rodata_base + 0xac500
	.size hkscs2004_uni2indx_page201, 0x50
	.globl hkscs2004_uni2indx_page20a
	.set hkscs2004_uni2indx_page20a, __f_rodata_base + 0xac550
	.size hkscs2004_uni2indx_page20a, 0x68
	.globl hkscs2004_uni2indx_page21a
	.set hkscs2004_uni2indx_page21a, __f_rodata_base + 0xac5b8
	.size hkscs2004_uni2indx_page21a, 0x1c
	.globl hkscs2004_uni2indx_page21d
	.set hkscs2004_uni2indx_page21d, __f_rodata_base + 0xac5d4
	.size hkscs2004_uni2indx_page21d, 0x4c
	.globl hkscs2004_uni2indx_page221
	.set hkscs2004_uni2indx_page221, __f_rodata_base + 0xac620
	.size hkscs2004_uni2indx_page221, 0x34
	.globl hkscs2004_uni2indx_page227
	.set hkscs2004_uni2indx_page227, __f_rodata_base + 0xac654
	.size hkscs2004_uni2indx_page227, 0x28
	.globl hkscs2004_uni2indx_page232
	.set hkscs2004_uni2indx_page232, __f_rodata_base + 0xac67c
	.size hkscs2004_uni2indx_page232, 0x18
	.globl hkscs2004_uni2indx_page235
	.set hkscs2004_uni2indx_page235, __f_rodata_base + 0xac694
	.size hkscs2004_uni2indx_page235, 0x48
	.globl hkscs2004_uni2indx_page23b
	.set hkscs2004_uni2indx_page23b, __f_rodata_base + 0xac6dc
	.size hkscs2004_uni2indx_page23b, 0x8
	.globl hkscs2004_uni2indx_page23e
	.set hkscs2004_uni2indx_page23e, __f_rodata_base + 0xac6e4
	.size hkscs2004_uni2indx_page23e, 0xbc
	.globl hkscs2004_uni2indx_page242
	.set hkscs2004_uni2indx_page242, __f_rodata_base + 0xac7a0
	.size hkscs2004_uni2indx_page242, 0x30
	.globl hkscs2004_uni2indx_page24b
	.set hkscs2004_uni2indx_page24b, __f_rodata_base + 0xac7d0
	.size hkscs2004_uni2indx_page24b, 0x4
	.globl hkscs2004_uni2indx_page254
	.set hkscs2004_uni2indx_page254, __f_rodata_base + 0xac7d4
	.size hkscs2004_uni2indx_page254, 0x28
	.globl hkscs2004_uni2indx_page25a
	.set hkscs2004_uni2indx_page25a, __f_rodata_base + 0xac7fc
	.size hkscs2004_uni2indx_page25a, 0x18
	.globl hkscs2004_uni2indx_page26b
	.set hkscs2004_uni2indx_page26b, __f_rodata_base + 0xac814
	.size hkscs2004_uni2indx_page26b, 0x54
	.globl hkscs2004_uni2indx_page26e
	.set hkscs2004_uni2indx_page26e, __f_rodata_base + 0xac868
	.size hkscs2004_uni2indx_page26e, 0x24
	.globl hkscs2004_uni2indx_page270
	.set hkscs2004_uni2indx_page270, __f_rodata_base + 0xac88c
	.size hkscs2004_uni2indx_page270, 0x38
	.globl hkscs2004_uni2indx_page272
	.set hkscs2004_uni2indx_page272, __f_rodata_base + 0xac8c4
	.size hkscs2004_uni2indx_page272, 0x80
	.globl hkscs2004_uni2indx_page27b
	.set hkscs2004_uni2indx_page27b, __f_rodata_base + 0xac944
	.size hkscs2004_uni2indx_page27b, 0x74
	.globl hkscs2004_uni2indx_page286
	.set hkscs2004_uni2indx_page286, __f_rodata_base + 0xac9b8
	.size hkscs2004_uni2indx_page286, 0x30
	.globl hkscs2004_uni2indx_page289
	.set hkscs2004_uni2indx_page289, __f_rodata_base + 0xac9e8
	.size hkscs2004_uni2indx_page289, 0x1c
	.globl hkscs2004_uni2indx_page28b
	.set hkscs2004_uni2indx_page28b, __f_rodata_base + 0xaca04
	.size hkscs2004_uni2indx_page28b, 0x30
	.globl hkscs2004_uni2indx_page290
	.set hkscs2004_uni2indx_page290, __f_rodata_base + 0xaca34
	.size hkscs2004_uni2indx_page290, 0x20
	.globl hkscs2004_uni2indx_page298
	.set hkscs2004_uni2indx_page298, __f_rodata_base + 0xaca54
	.size hkscs2004_uni2indx_page298, 0x54
	.globl hkscs2004_uni2indx_page29e
	.set hkscs2004_uni2indx_page29e, __f_rodata_base + 0xacaa8
	.size hkscs2004_uni2indx_page29e, 0x30
	.globl hkscs2004_uni2indx_page2a1
	.set hkscs2004_uni2indx_page2a1, __f_rodata_base + 0xacad8
	.size hkscs2004_uni2indx_page2a1, 0x30
	.globl hkscs2004_uni2indx_page2a3
	.set hkscs2004_uni2indx_page2a3, __f_rodata_base + 0xacb08
	.size hkscs2004_uni2indx_page2a3, 0x18
	.globl hkscs2008_2uni_page87
	.set hkscs2008_2uni_page87, __f_rodata_base + 0xacb20
	.size hkscs2008_2uni_page87, 0xfc
	.globl hkscs2008_2uni_upages
	.set hkscs2008_2uni_upages, __f_rodata_base + 0xacc1c
	.size hkscs2008_2uni_upages, 0xc8
	.globl hkscs2008_2charset
	.set hkscs2008_2charset, __f_rodata_base + 0xacce4
	.size hkscs2008_2charset, 0x88
	.globl hkscs2008_uni2indx_page34
	.set hkscs2008_uni2indx_page34, __f_rodata_base + 0xacd6c
	.size hkscs2008_uni2indx_page34, 0x3c
	.globl hkscs2008_uni2indx_page38
	.set hkscs2008_uni2indx_page38, __f_rodata_base + 0xacda8
	.size hkscs2008_uni2indx_page38, 0x20
	.globl hkscs2008_uni2indx_page3a
	.set hkscs2008_uni2indx_page3a, __f_rodata_base + 0xacdc8
	.size hkscs2008_uni2indx_page3a, 0x40
	.globl hkscs2008_uni2indx_page3e
	.set hkscs2008_uni2indx_page3e, __f_rodata_base + 0xace08
	.size hkscs2008_uni2indx_page3e, 0x3c
	.globl hkscs2008_uni2indx_page40
	.set hkscs2008_uni2indx_page40, __f_rodata_base + 0xace44
	.size hkscs2008_uni2indx_page40, 0x64
	.globl hkscs2008_uni2indx_page43
	.set hkscs2008_uni2indx_page43, __f_rodata_base + 0xacea8
	.size hkscs2008_uni2indx_page43, 0x7c
	.globl hkscs2008_uni2indx_page46
	.set hkscs2008_uni2indx_page46, __f_rodata_base + 0xacf24
	.size hkscs2008_uni2indx_page46, 0x2c
	.globl hkscs2008_uni2indx_page49
	.set hkscs2008_uni2indx_page49, __f_rodata_base + 0xacf50
	.size hkscs2008_uni2indx_page49, 0x10
	.globl hkscs2008_uni2indx_page52
	.set hkscs2008_uni2indx_page52, __f_rodata_base + 0xacf60
	.size hkscs2008_uni2indx_page52, 0x14
	.globl hkscs2008_uni2indx_page54
	.set hkscs2008_uni2indx_page54, __f_rodata_base + 0xacf74
	.size hkscs2008_uni2indx_page54, 0x14
	.globl hkscs2008_uni2indx_page57
	.set hkscs2008_uni2indx_page57, __f_rodata_base + 0xacf88
	.size hkscs2008_uni2indx_page57, 0x68
	.globl hkscs2008_uni2indx_page62
	.set hkscs2008_uni2indx_page62, __f_rodata_base + 0xacff0
	.size hkscs2008_uni2indx_page62, 0x34
	.globl hkscs2008_uni2indx_page66
	.set hkscs2008_uni2indx_page66, __f_rodata_base + 0xad024
	.size hkscs2008_uni2indx_page66, 0x64
	.globl hkscs2008_uni2indx_page6a
	.set hkscs2008_uni2indx_page6a, __f_rodata_base + 0xad088
	.size hkscs2008_uni2indx_page6a, 0xc
	.globl hkscs2008_uni2indx_page70
	.set hkscs2008_uni2indx_page70, __f_rodata_base + 0xad094
	.size hkscs2008_uni2indx_page70, 0x1c
	.globl hkscs2008_uni2indx_page73
	.set hkscs2008_uni2indx_page73, __f_rodata_base + 0xad0b0
	.size hkscs2008_uni2indx_page73, 0x74
	.globl hkscs2008_uni2indx_page79
	.set hkscs2008_uni2indx_page79, __f_rodata_base + 0xad124
	.size hkscs2008_uni2indx_page79, 0xb4
	.globl hkscs2008_uni2indx_page84
	.set hkscs2008_uni2indx_page84, __f_rodata_base + 0xad1d8
	.size hkscs2008_uni2indx_page84, 0x88
	.globl hkscs2008_uni2indx_page88
	.set hkscs2008_uni2indx_page88, __f_rodata_base + 0xad260
	.size hkscs2008_uni2indx_page88, 0x28
	.globl hkscs2008_uni2indx_page8b
	.set hkscs2008_uni2indx_page8b, __f_rodata_base + 0xad288
	.size hkscs2008_uni2indx_page8b, 0x24
	.globl hkscs2008_uni2indx_page90
	.set hkscs2008_uni2indx_page90, __f_rodata_base + 0xad2ac
	.size hkscs2008_uni2indx_page90, 0x14
	.globl hkscs2008_uni2indx_page92
	.set hkscs2008_uni2indx_page92, __f_rodata_base + 0xad2c0
	.size hkscs2008_uni2indx_page92, 0x8
	.globl hkscs2008_uni2indx_page94
	.set hkscs2008_uni2indx_page94, __f_rodata_base + 0xad2c8
	.size hkscs2008_uni2indx_page94, 0xc
	.globl hkscs2008_uni2indx_page97
	.set hkscs2008_uni2indx_page97, __f_rodata_base + 0xad2d4
	.size hkscs2008_uni2indx_page97, 0x14
	.globl hkscs2008_uni2indx_page9f
	.set hkscs2008_uni2indx_page9f, __f_rodata_base + 0xad2e8
	.size hkscs2008_uni2indx_page9f, 0x34
	.globl hkscs2008_uni2indx_page20a
	.set hkscs2008_uni2indx_page20a, __f_rodata_base + 0xad31c
	.size hkscs2008_uni2indx_page20a, 0x24
	.globl hkscs2008_uni2indx_page21d
	.set hkscs2008_uni2indx_page21d, __f_rodata_base + 0xad340
	.size hkscs2008_uni2indx_page21d, 0x18
	.globl hkscs2008_uni2indx_page224
	.set hkscs2008_uni2indx_page224, __f_rodata_base + 0xad358
	.size hkscs2008_uni2indx_page224, 0x34
	.globl hkscs2008_uni2indx_page231
	.set hkscs2008_uni2indx_page231, __f_rodata_base + 0xad38c
	.size hkscs2008_uni2indx_page231, 0x58
	.globl hkscs2008_uni2indx_page235
	.set hkscs2008_uni2indx_page235, __f_rodata_base + 0xad3e4
	.size hkscs2008_uni2indx_page235, 0x68
	.globl hkscs2008_uni2indx_page241
	.set hkscs2008_uni2indx_page241, __f_rodata_base + 0xad44c
	.size hkscs2008_uni2indx_page241, 0x1c
	.globl hkscs2008_uni2indx_page258
	.set hkscs2008_uni2indx_page258, __f_rodata_base + 0xad468
	.size hkscs2008_uni2indx_page258, 0x38
	.globl hkscs2008_uni2indx_page25d
	.set hkscs2008_uni2indx_page25d, __f_rodata_base + 0xad4a0
	.size hkscs2008_uni2indx_page25d, 0x30
	.globl hkscs2008_uni2indx_page260
	.set hkscs2008_uni2indx_page260, __f_rodata_base + 0xad4d0
	.size hkscs2008_uni2indx_page260, 0xc
	.globl hkscs2008_uni2indx_page26e
	.set hkscs2008_uni2indx_page26e, __f_rodata_base + 0xad4dc
	.size hkscs2008_uni2indx_page26e, 0x24
	.globl hkscs2008_uni2indx_page27b
	.set hkscs2008_uni2indx_page27b, __f_rodata_base + 0xad500
	.size hkscs2008_uni2indx_page27b, 0x1c
	.globl hkscs2008_uni2indx_page289
	.set hkscs2008_uni2indx_page289, __f_rodata_base + 0xad51c
	.size hkscs2008_uni2indx_page289, 0x4
	.globl hkscs2008_uni2indx_page2ad
	.set hkscs2008_uni2indx_page2ad, __f_rodata_base + 0xad520
	.size hkscs2008_uni2indx_page2ad, 0x40
	.globl uhc_1_2uni_main_page81
	.set uhc_1_2uni_main_page81, __f_rodata_base + 0xad560
	.size uhc_1_2uni_main_page81, 0x80
	.globl uhc_1_2uni_page81
	.set uhc_1_2uni_page81, __f_rodata_base + 0xad5e0
	.size uhc_1_2uni_page81, 0x1640
	.globl uhc_1_2charset_main
	.set uhc_1_2charset_main, __f_rodata_base + 0xaec20
	.size uhc_1_2charset_main, 0x5a
	.globl uhc_1_2charset
	.set uhc_1_2charset, __f_rodata_base + 0xaec7c
	.size uhc_1_2charset, 0x1640
	.globl uhc_1_uni2indx_pageac
	.set uhc_1_uni2indx_pageac, __f_rodata_base + 0xb02bc
	.size uhc_1_uni2indx_pageac, 0x72c
	.globl uhc_2_2uni_main_pagea1
	.set uhc_2_2uni_main_pagea1, __f_rodata_base + 0xb09e8
	.size uhc_2_2uni_main_pagea1, 0x98
	.globl uhc_2_2uni_pagea1
	.set uhc_2_2uni_pagea1, __f_rodata_base + 0xb0a80
	.size uhc_2_2uni_pagea1, 0xc36
	.globl uhc_2_2charset_main
	.set uhc_2_2charset_main, __f_rodata_base + 0xb16b8
	.size uhc_2_2charset_main, 0x62
	.globl uhc_2_2charset
	.set uhc_2_2charset, __f_rodata_base + 0xb171c
	.size uhc_2_2charset, 0xc36
	.globl uhc_2_uni2indx_pagec8
	.set uhc_2_uni2indx_pagec8, __f_rodata_base + 0xb2354
	.size uhc_2_uni2indx_pagec8, 0x3ec
	.globl cjk_variants
	.set cjk_variants, __f_rodata_base + 0xb2740
	.size cjk_variants, 0x5e0c
	.globl cjk_variants_indx
	.set cjk_variants_indx, __f_rodata_base + 0xb854c
	.size cjk_variants_indx, 0xa400
	.globl translit_data
	.set translit_data, __f_rodata_base + 0xc294c
	.size translit_data, 0x8e70
	.globl translit_page00
	.set translit_page00, __f_rodata_base + 0xcb7bc
	.size translit_page00, 0x2b0
	.globl translit_page02
	.set translit_page02, __f_rodata_base + 0xcba6c
	.size translit_page02, 0x10
	.globl translit_page02_1
	.set translit_page02_1, __f_rodata_base + 0xcba7c
	.size translit_page02_1, 0x50
	.globl translit_page03
	.set translit_page03, __f_rodata_base + 0xcbacc
	.size translit_page03, 0x60
	.globl translit_page05
	.set translit_page05, __f_rodata_base + 0xcbb2c
	.size translit_page05, 0x10
	.globl translit_page06
	.set translit_page06, __f_rodata_base + 0xcbb3c
	.size translit_page06, 0x20
	.globl translit_page0e
	.set translit_page0e, __f_rodata_base + 0xcbb5c
	.size translit_page0e, 0x60
	.globl translit_page0f
	.set translit_page0f, __f_rodata_base + 0xcbbbc
	.size translit_page0f, 0x20
	.globl translit_page1e
	.set translit_page1e, __f_rodata_base + 0xcbbdc
	.size translit_page1e, 0x140
	.globl translit_page1e_2
	.set translit_page1e_2, __f_rodata_base + 0xcbd1c
	.size translit_page1e_2, 0x10
	.globl translit_page20
	.set translit_page20, __f_rodata_base + 0xcbd2c
	.size translit_page20, 0xb0
	.globl translit_page20_3
	.set translit_page20_3, __f_rodata_base + 0xcbddc
	.size translit_page20_3, 0x10
	.globl translit_page21
	.set translit_page21, __f_rodata_base + 0xcbdec
	.size translit_page21, 0x1b0
	.globl translit_page22
	.set translit_page22, __f_rodata_base + 0xcbf9c
	.size translit_page22, 0xc0
	.globl translit_page22_4
	.set translit_page22_4, __f_rodata_base + 0xcc05c
	.size translit_page22_4, 0x60
	.globl translit_page24
	.set translit_page24, __f_rodata_base + 0xcc0bc
	.size translit_page24, 0x1e0
	.globl translit_page25
	.set translit_page25, __f_rodata_base + 0xcc29c
	.size translit_page25, 0x80
	.globl translit_page2a
	.set translit_page2a, __f_rodata_base + 0xcc31c
	.size translit_page2a, 0x10
	.globl translit_page2f
	.set translit_page2f, __f_rodata_base + 0xcc32c
	.size translit_page2f, 0x1b0
	.globl translit_page30
	.set translit_page30, __f_rodata_base + 0xcc4dc
	.size translit_page30, 0x1f0
	.globl translit_page31
	.set translit_page31, __f_rodata_base + 0xcc6cc
	.size translit_page31, 0xc0
	.globl translit_page31_5
	.set translit_page31_5, __f_rodata_base + 0xcc78c
	.size translit_page31_5, 0x420
	.globl translit_pagef9
	.set translit_pagef9, __f_rodata_base + 0xccbac
	.size translit_pagef9, 0x2e0
	.globl translit_pagefb
	.set translit_pagefb, __f_rodata_base + 0xcce8c
	.size translit_pagefb, 0xa0
	.globl translit_pagefe
	.set translit_pagefe, __f_rodata_base + 0xccf2c
	.size translit_pagefe, 0x50
	.globl translit_pageff
	.set translit_pageff, __f_rodata_base + 0xccf7c
	.size translit_pageff, 0x1e0
	.globl translit_page1d4
	.set translit_page1d4, __f_rodata_base + 0xcd15c
	.size translit_page1d4, 0x800
	.globl translit_page2f8
	.set translit_page2f8, __f_rodata_base + 0xcd95c
	.size translit_page2f8, 0x440
	.globl all_encodings
	.set all_encodings, __f_rodata_base + 0xcdd9c
	.size all_encodings, 0x8d4
	.globl stringpool_contents
	.set stringpool_contents, __f_rodata_base + 0xce670
	.size stringpool_contents, 0xdfd
	.globl aliases
	.set aliases, __f_rodata_base + 0xcf470
	.size aliases, 0x1cd0
	.globl all_canonical
	.set all_canonical, __f_rodata_base + 0xd1158
	.size all_canonical, 0xe2
	.globl conversion_lists.7622
	.set conversion_lists.7622, __f_rodata_base + 0xd123c
	.size conversion_lists.7622, 0x10
	.globl asso_values.9691
	.set asso_values.9691, __f_rodata_base + 0xd124c
	.size asso_values.9691, 0x100

/* .data.rel.ro.local：8 个符号 */
	.globl _ZL8z_errmsg
	.set _ZL8z_errmsg, __f_data_rel_ro_local_base + 0x0
	.size _ZL8z_errmsg, 0x28
	.globl mui_typename
	.set mui_typename, __f_data_rel_ro_local_base + 0x28
	.size mui_typename, 0x24
	.globl ArchivePath
	.set ArchivePath, __f_data_rel_ro_local_base + 0x4c
	.size ArchivePath, 0x40
	.globl number
	.set number, __f_data_rel_ro_local_base + 0x8c
	.size number, 0x28
	.globl KayName
	.set KayName, __f_data_rel_ro_local_base + 0xb4
	.size KayName, 0x30
	.globl p_name
	.set p_name, __f_data_rel_ro_local_base + 0xe4
	.size p_name, 0x10
	.globl entities.6989
	.set entities.6989, __f_data_rel_ro_local_base + 0xf4
	.size entities.6989, 0x808
	.globl types.7806
	.set types.7806, __f_data_rel_ro_local_base + 0x8fc
	.size types.7806, 0x18

/* .data：173 个符号 */
	.globl __dso_handle
	.set __dso_handle, __f_data_base + 0x4
	.size __dso_handle, 0x0
	.globl DAT_003af008
	.set DAT_003af008, __f_data_base + 0x8
	.size DAT_003af008, 0x0
	.globl running
	.set running, __f_data_base + 0x18
	.size running, 0x4
	.globl Rowspacing
	.set Rowspacing, __f_data_base + 0x1c
	.size Rowspacing, 0x4
	.globl joystick_fd
	.set joystick_fd, __f_data_base + 0x20
	.size joystick_fd, 0x10
	.globl RF_JOYTable
	.set RF_JOYTable, __f_data_base + 0x30
	.size RF_JOYTable, 0x78
	.globl CHANNEL_TBL
	.set CHANNEL_TBL, __f_data_base + 0xa8
	.size CHANNEL_TBL, 0x4
	.globl RX_ADDRESS1
	.set RX_ADDRESS1, __f_data_base + 0xac
	.size RX_ADDRESS1, 0x5
	.globl RX_ADDRESS0
	.set RX_ADDRESS0, __f_data_base + 0xb4
	.size RX_ADDRESS0, 0x5
	.globl Dem_cal2_data
	.set Dem_cal2_data, __f_data_base + 0xbc
	.size Dem_cal2_data, 0x3
	.globl RF_cal2_data
	.set RF_cal2_data, __f_data_base + 0xc0
	.size RF_cal2_data, 0x6
	.globl RF_cal_data
	.set RF_cal_data, __f_data_base + 0xc8
	.size RF_cal_data, 0x3
	.globl BB_cal_data
	.set BB_cal_data, __f_data_base + 0xcc
	.size BB_cal_data, 0x5
	.globl USB_Table
	.set USB_Table, __f_data_base + 0xd4
	.size USB_Table, 0x180
	.globl JOYSTICK_DEVNAME
	.set JOYSTICK_DEVNAME, __f_data_base + 0x254
	.size JOYSTICK_DEVNAME, 0x10
	.globl m_ui
	.set m_ui, __f_data_base + 0x264
	.size m_ui, 0x5e4
	.globl DAT_003af268
	.set DAT_003af268, __f_data_base + 0x268
	.size DAT_003af268, 0x0
	.globl DAT_003af26c
	.set DAT_003af26c, __f_data_base + 0x26c
	.size DAT_003af26c, 0x0
	.globl DAT_003af270
	.set DAT_003af270, __f_data_base + 0x270
	.size DAT_003af270, 0x0
	.globl DAT_003af274
	.set DAT_003af274, __f_data_base + 0x274
	.size DAT_003af274, 0x0
	.globl DAT_003af278
	.set DAT_003af278, __f_data_base + 0x278
	.size DAT_003af278, 0x0
	.globl DAT_003af27c
	.set DAT_003af27c, __f_data_base + 0x27c
	.size DAT_003af27c, 0x0
	.globl DAT_003af280
	.set DAT_003af280, __f_data_base + 0x280
	.size DAT_003af280, 0x0
	.globl DAT_003af284
	.set DAT_003af284, __f_data_base + 0x284
	.size DAT_003af284, 0x0
	.globl DAT_003af288
	.set DAT_003af288, __f_data_base + 0x288
	.size DAT_003af288, 0x0
	.globl DAT_003af28c
	.set DAT_003af28c, __f_data_base + 0x28c
	.size DAT_003af28c, 0x0
	.globl DAT_003af290
	.set DAT_003af290, __f_data_base + 0x290
	.size DAT_003af290, 0x0
	.globl DAT_003af294
	.set DAT_003af294, __f_data_base + 0x294
	.size DAT_003af294, 0x0
	.globl DAT_003af298
	.set DAT_003af298, __f_data_base + 0x298
	.size DAT_003af298, 0x0
	.globl DAT_003af29c
	.set DAT_003af29c, __f_data_base + 0x29c
	.size DAT_003af29c, 0x0
	.globl DAT_003af2a0
	.set DAT_003af2a0, __f_data_base + 0x2a0
	.size DAT_003af2a0, 0x0
	.globl DAT_003af2a4
	.set DAT_003af2a4, __f_data_base + 0x2a4
	.size DAT_003af2a4, 0x0
	.globl DAT_003af2a8
	.set DAT_003af2a8, __f_data_base + 0x2a8
	.size DAT_003af2a8, 0x0
	.globl DAT_003af2ac
	.set DAT_003af2ac, __f_data_base + 0x2ac
	.size DAT_003af2ac, 0x0
	.globl DAT_003af2b0
	.set DAT_003af2b0, __f_data_base + 0x2b0
	.size DAT_003af2b0, 0x0
	.globl DAT_003af2b4
	.set DAT_003af2b4, __f_data_base + 0x2b4
	.size DAT_003af2b4, 0x0
	.globl DAT_003af2b8
	.set DAT_003af2b8, __f_data_base + 0x2b8
	.size DAT_003af2b8, 0x0
	.globl DAT_003af2bc
	.set DAT_003af2bc, __f_data_base + 0x2bc
	.size DAT_003af2bc, 0x0
	.globl DAT_003af2c0
	.set DAT_003af2c0, __f_data_base + 0x2c0
	.size DAT_003af2c0, 0x0
	.globl DAT_003af30c
	.set DAT_003af30c, __f_data_base + 0x30c
	.size DAT_003af30c, 0x0
	.globl DAT_003af310
	.set DAT_003af310, __f_data_base + 0x310
	.size DAT_003af310, 0x0
	.globl DAT_003af314
	.set DAT_003af314, __f_data_base + 0x314
	.size DAT_003af314, 0x0
	.globl DAT_003af318
	.set DAT_003af318, __f_data_base + 0x318
	.size DAT_003af318, 0x0
	.globl DAT_003af31c
	.set DAT_003af31c, __f_data_base + 0x31c
	.size DAT_003af31c, 0x0
	.globl DAT_003af320
	.set DAT_003af320, __f_data_base + 0x320
	.size DAT_003af320, 0x0
	.globl DAT_003af324
	.set DAT_003af324, __f_data_base + 0x324
	.size DAT_003af324, 0x0
	.globl DAT_003af328
	.set DAT_003af328, __f_data_base + 0x328
	.size DAT_003af328, 0x0
	.globl DAT_003af37c
	.set DAT_003af37c, __f_data_base + 0x37c
	.size DAT_003af37c, 0x0
	.globl DAT_003af380
	.set DAT_003af380, __f_data_base + 0x380
	.size DAT_003af380, 0x0
	.globl DAT_003af384
	.set DAT_003af384, __f_data_base + 0x384
	.size DAT_003af384, 0x0
	.globl DAT_003af388
	.set DAT_003af388, __f_data_base + 0x388
	.size DAT_003af388, 0x0
	.globl DAT_003af38c
	.set DAT_003af38c, __f_data_base + 0x38c
	.size DAT_003af38c, 0x0
	.globl DAT_003af390
	.set DAT_003af390, __f_data_base + 0x390
	.size DAT_003af390, 0x0
	.globl DAT_003af394
	.set DAT_003af394, __f_data_base + 0x394
	.size DAT_003af394, 0x0
	.globl DAT_003af398
	.set DAT_003af398, __f_data_base + 0x398
	.size DAT_003af398, 0x0
	.globl DAT_003af39c
	.set DAT_003af39c, __f_data_base + 0x39c
	.size DAT_003af39c, 0x0
	.globl DAT_003af3a0
	.set DAT_003af3a0, __f_data_base + 0x3a0
	.size DAT_003af3a0, 0x0
	.globl DAT_003af3a4
	.set DAT_003af3a4, __f_data_base + 0x3a4
	.size DAT_003af3a4, 0x0
	.globl DAT_003af3a8
	.set DAT_003af3a8, __f_data_base + 0x3a8
	.size DAT_003af3a8, 0x0
	.globl DAT_003af3ac
	.set DAT_003af3ac, __f_data_base + 0x3ac
	.size DAT_003af3ac, 0x0
	.globl DAT_003af698
	.set DAT_003af698, __f_data_base + 0x698
	.size DAT_003af698, 0x0
	.globl DAT_003af69c
	.set DAT_003af69c, __f_data_base + 0x69c
	.size DAT_003af69c, 0x0
	.globl DAT_003af6a0
	.set DAT_003af6a0, __f_data_base + 0x6a0
	.size DAT_003af6a0, 0x0
	.globl DAT_003af6a4
	.set DAT_003af6a4, __f_data_base + 0x6a4
	.size DAT_003af6a4, 0x0
	.globl DAT_003af6a8
	.set DAT_003af6a8, __f_data_base + 0x6a8
	.size DAT_003af6a8, 0x0
	.globl DAT_003af6ac
	.set DAT_003af6ac, __f_data_base + 0x6ac
	.size DAT_003af6ac, 0x0
	.globl DAT_003af6b0
	.set DAT_003af6b0, __f_data_base + 0x6b0
	.size DAT_003af6b0, 0x0
	.globl DAT_003af6b8
	.set DAT_003af6b8, __f_data_base + 0x6b8
	.size DAT_003af6b8, 0x0
	.globl DAT_003af6bc
	.set DAT_003af6bc, __f_data_base + 0x6bc
	.size DAT_003af6bc, 0x0
	.globl DAT_003af6c0
	.set DAT_003af6c0, __f_data_base + 0x6c0
	.size DAT_003af6c0, 0x0
	.globl DAT_003af6c4
	.set DAT_003af6c4, __f_data_base + 0x6c4
	.size DAT_003af6c4, 0x0
	.globl DAT_003af6c8
	.set DAT_003af6c8, __f_data_base + 0x6c8
	.size DAT_003af6c8, 0x0
	.globl DAT_003af6cc
	.set DAT_003af6cc, __f_data_base + 0x6cc
	.size DAT_003af6cc, 0x0
	.globl DAT_003af6d0
	.set DAT_003af6d0, __f_data_base + 0x6d0
	.size DAT_003af6d0, 0x0
	.globl DAT_003af6d4
	.set DAT_003af6d4, __f_data_base + 0x6d4
	.size DAT_003af6d4, 0x0
	.globl DAT_003af6d8
	.set DAT_003af6d8, __f_data_base + 0x6d8
	.size DAT_003af6d8, 0x0
	.globl DAT_003af6dc
	.set DAT_003af6dc, __f_data_base + 0x6dc
	.size DAT_003af6dc, 0x0
	.globl DAT_003af6e0
	.set DAT_003af6e0, __f_data_base + 0x6e0
	.size DAT_003af6e0, 0x0
	.globl DAT_003af6e4
	.set DAT_003af6e4, __f_data_base + 0x6e4
	.size DAT_003af6e4, 0x0
	.globl DAT_003af6e8
	.set DAT_003af6e8, __f_data_base + 0x6e8
	.size DAT_003af6e8, 0x0
	.globl DAT_003af6f0
	.set DAT_003af6f0, __f_data_base + 0x6f0
	.size DAT_003af6f0, 0x0
	.globl DAT_003af6f4
	.set DAT_003af6f4, __f_data_base + 0x6f4
	.size DAT_003af6f4, 0x0
	.globl DAT_003af6f8
	.set DAT_003af6f8, __f_data_base + 0x6f8
	.size DAT_003af6f8, 0x0
	.globl DAT_003af6fc
	.set DAT_003af6fc, __f_data_base + 0x6fc
	.size DAT_003af6fc, 0x0
	.globl DAT_003af700
	.set DAT_003af700, __f_data_base + 0x700
	.size DAT_003af700, 0x0
	.globl DAT_003af704
	.set DAT_003af704, __f_data_base + 0x704
	.size DAT_003af704, 0x0
	.globl DAT_003af708
	.set DAT_003af708, __f_data_base + 0x708
	.size DAT_003af708, 0x0
	.globl DAT_003af70f
	.set DAT_003af70f, __f_data_base + 0x70f
	.size DAT_003af70f, 0x0
	.globl DAT_003af718
	.set DAT_003af718, __f_data_base + 0x718
	.size DAT_003af718, 0x0
	.globl DAT_003af71c
	.set DAT_003af71c, __f_data_base + 0x71c
	.size DAT_003af71c, 0x0
	.globl DAT_003af720
	.set DAT_003af720, __f_data_base + 0x720
	.size DAT_003af720, 0x0
	.globl DAT_003af724
	.set DAT_003af724, __f_data_base + 0x724
	.size DAT_003af724, 0x0
	.globl DAT_003af728
	.set DAT_003af728, __f_data_base + 0x728
	.size DAT_003af728, 0x0
	.globl DAT_003af72c
	.set DAT_003af72c, __f_data_base + 0x72c
	.size DAT_003af72c, 0x0
	.globl DAT_003af730
	.set DAT_003af730, __f_data_base + 0x730
	.size DAT_003af730, 0x0
	.globl DAT_003af734
	.set DAT_003af734, __f_data_base + 0x734
	.size DAT_003af734, 0x0
	.globl DAT_003af738
	.set DAT_003af738, __f_data_base + 0x738
	.size DAT_003af738, 0x0
	.globl DAT_003af73c
	.set DAT_003af73c, __f_data_base + 0x73c
	.size DAT_003af73c, 0x0
	.globl DAT_003af740
	.set DAT_003af740, __f_data_base + 0x740
	.size DAT_003af740, 0x0
	.globl DAT_003af744
	.set DAT_003af744, __f_data_base + 0x744
	.size DAT_003af744, 0x0
	.globl DAT_003af748
	.set DAT_003af748, __f_data_base + 0x748
	.size DAT_003af748, 0x0
	.globl DAT_003af74c
	.set DAT_003af74c, __f_data_base + 0x74c
	.size DAT_003af74c, 0x0
	.globl DAT_003af788
	.set DAT_003af788, __f_data_base + 0x788
	.size DAT_003af788, 0x0
	.globl DAT_003af78c
	.set DAT_003af78c, __f_data_base + 0x78c
	.size DAT_003af78c, 0x0
	.globl DAT_003af790
	.set DAT_003af790, __f_data_base + 0x790
	.size DAT_003af790, 0x0
	.globl DAT_003af794
	.set DAT_003af794, __f_data_base + 0x794
	.size DAT_003af794, 0x0
	.globl DAT_003af798
	.set DAT_003af798, __f_data_base + 0x798
	.size DAT_003af798, 0x0
	.globl DAT_003af79c
	.set DAT_003af79c, __f_data_base + 0x79c
	.size DAT_003af79c, 0x0
	.globl DAT_003af7a0
	.set DAT_003af7a0, __f_data_base + 0x7a0
	.size DAT_003af7a0, 0x0
	.globl DAT_003af7a4
	.set DAT_003af7a4, __f_data_base + 0x7a4
	.size DAT_003af7a4, 0x0
	.globl DAT_003af7a8
	.set DAT_003af7a8, __f_data_base + 0x7a8
	.size DAT_003af7a8, 0x0
	.globl DAT_003af7ac
	.set DAT_003af7ac, __f_data_base + 0x7ac
	.size DAT_003af7ac, 0x0
	.globl DAT_003af7b0
	.set DAT_003af7b0, __f_data_base + 0x7b0
	.size DAT_003af7b0, 0x0
	.globl DAT_003af7b4
	.set DAT_003af7b4, __f_data_base + 0x7b4
	.size DAT_003af7b4, 0x0
	.globl DAT_003af7b8
	.set DAT_003af7b8, __f_data_base + 0x7b8
	.size DAT_003af7b8, 0x0
	.globl DAT_003af7bc
	.set DAT_003af7bc, __f_data_base + 0x7bc
	.size DAT_003af7bc, 0x0
	.globl DAT_003af7c0
	.set DAT_003af7c0, __f_data_base + 0x7c0
	.size DAT_003af7c0, 0x0
	.globl DAT_003af7c4
	.set DAT_003af7c4, __f_data_base + 0x7c4
	.size DAT_003af7c4, 0x0
	.globl DAT_003af7c8
	.set DAT_003af7c8, __f_data_base + 0x7c8
	.size DAT_003af7c8, 0x0
	.globl DAT_003af7cc
	.set DAT_003af7cc, __f_data_base + 0x7cc
	.size DAT_003af7cc, 0x0
	.globl DAT_003af7d0
	.set DAT_003af7d0, __f_data_base + 0x7d0
	.size DAT_003af7d0, 0x0
	.globl DAT_003af7d4
	.set DAT_003af7d4, __f_data_base + 0x7d4
	.size DAT_003af7d4, 0x0
	.globl DAT_003af7d8
	.set DAT_003af7d8, __f_data_base + 0x7d8
	.size DAT_003af7d8, 0x0
	.globl DAT_003af7e0
	.set DAT_003af7e0, __f_data_base + 0x7e0
	.size DAT_003af7e0, 0x0
	.globl DAT_003af7e4
	.set DAT_003af7e4, __f_data_base + 0x7e4
	.size DAT_003af7e4, 0x0
	.globl DAT_003af7e8
	.set DAT_003af7e8, __f_data_base + 0x7e8
	.size DAT_003af7e8, 0x0
	.globl DAT_003af7ec
	.set DAT_003af7ec, __f_data_base + 0x7ec
	.size DAT_003af7ec, 0x0
	.globl DAT_003af7f0
	.set DAT_003af7f0, __f_data_base + 0x7f0
	.size DAT_003af7f0, 0x0
	.globl DAT_003af7f4
	.set DAT_003af7f4, __f_data_base + 0x7f4
	.size DAT_003af7f4, 0x0
	.globl DAT_003af7f8
	.set DAT_003af7f8, __f_data_base + 0x7f8
	.size DAT_003af7f8, 0x0
	.globl DAT_003af7fc
	.set DAT_003af7fc, __f_data_base + 0x7fc
	.size DAT_003af7fc, 0x0
	.globl DAT_003af800
	.set DAT_003af800, __f_data_base + 0x800
	.size DAT_003af800, 0x0
	.globl DAT_003af804
	.set DAT_003af804, __f_data_base + 0x804
	.size DAT_003af804, 0x0
	.globl DAT_003af808
	.set DAT_003af808, __f_data_base + 0x808
	.size DAT_003af808, 0x0
	.globl DAT_003af820
	.set DAT_003af820, __f_data_base + 0x820
	.size DAT_003af820, 0x0
	.globl DAT_003af824
	.set DAT_003af824, __f_data_base + 0x824
	.size DAT_003af824, 0x0
	.globl DAT_003af828
	.set DAT_003af828, __f_data_base + 0x828
	.size DAT_003af828, 0x0
	.globl DAT_003af82c
	.set DAT_003af82c, __f_data_base + 0x82c
	.size DAT_003af82c, 0x0
	.globl DAT_003af830
	.set DAT_003af830, __f_data_base + 0x830
	.size DAT_003af830, 0x0
	.globl DAT_003af834
	.set DAT_003af834, __f_data_base + 0x834
	.size DAT_003af834, 0x0
	.globl DAT_003af838
	.set DAT_003af838, __f_data_base + 0x838
	.size DAT_003af838, 0x0
	.globl DAT_003af83c
	.set DAT_003af83c, __f_data_base + 0x83c
	.size DAT_003af83c, 0x0
	.globl DAT_003af840
	.set DAT_003af840, __f_data_base + 0x840
	.size DAT_003af840, 0x0
	.globl DAT_003af844
	.set DAT_003af844, __f_data_base + 0x844
	.size DAT_003af844, 0x0
	.globl m_movetab
	.set m_movetab, __f_data_base + 0x848
	.size m_movetab, 0x398
	.globl m_joysticktab
	.set m_joysticktab, __f_data_base + 0xbe0
	.size m_joysticktab, 0x39c
	.globl m_statetab
	.set m_statetab, __f_data_base + 0xf7c
	.size m_statetab, 0x90
	.globl KEY_Table
	.set KEY_Table, __f_data_base + 0x100c
	.size KEY_Table, 0x40
	.globl P1_Table
	.set P1_Table, __f_data_base + 0x104c
	.size P1_Table, 0xdc
	.globl turbo_delay
	.set turbo_delay, __f_data_base + 0x1128
	.size turbo_delay, 0x4
	.globl DAT_003b012c
	.set DAT_003b012c, __f_data_base + 0x112c
	.size DAT_003b012c, 0x0
	.globl DAT_003b0130
	.set DAT_003b0130, __f_data_base + 0x1130
	.size DAT_003b0130, 0x0
	.globl DAT_003b0134
	.set DAT_003b0134, __f_data_base + 0x1134
	.size DAT_003b0134, 0x0
	.globl DAT_003b0138
	.set DAT_003b0138, __f_data_base + 0x1138
	.size DAT_003b0138, 0x0
	.globl DAT_003b013c
	.set DAT_003b013c, __f_data_base + 0x113c
	.size DAT_003b013c, 0x0
	.globl DAT_003b0140
	.set DAT_003b0140, __f_data_base + 0x1140
	.size DAT_003b0140, 0x0
	.globl DAT_003b0144
	.set DAT_003b0144, __f_data_base + 0x1144
	.size DAT_003b0144, 0x0
	.globl DAT_003b0148
	.set DAT_003b0148, __f_data_base + 0x1148
	.size DAT_003b0148, 0x0
	.globl DAT_003b014c
	.set DAT_003b014c, __f_data_base + 0x114c
	.size DAT_003b014c, 0x0
	.globl DAT_003b0150
	.set DAT_003b0150, __f_data_base + 0x1150
	.size DAT_003b0150, 0x0
	.globl user_joy_key_mask
	.set user_joy_key_mask, __f_data_base + 0x1154
	.size user_joy_key_mask, 0x100
	.globl default_core_list
	.set default_core_list, __f_data_base + 0x1254
	.size default_core_list, 0x1a90
	.globl DAT_003b0274
	.set DAT_003b0274, __f_data_base + 0x1274
	.size DAT_003b0274, 0x0
	.globl DAT_003b0278
	.set DAT_003b0278, __f_data_base + 0x1278
	.size DAT_003b0278, 0x0
	.globl DAT_003b0298
	.set DAT_003b0298, __f_data_base + 0x1298
	.size DAT_003b0298, 0x0
	.globl DAT_003b02b8
	.set DAT_003b02b8, __f_data_base + 0x12b8
	.size DAT_003b02b8, 0x0
	.globl DAT_003b02bc
	.set DAT_003b02bc, __f_data_base + 0x12bc
	.size DAT_003b02bc, 0x0
	.globl fps0
	.set fps0, __f_data_base + 0x2ce4
	.size fps0, 0x4
	.globl sound_len
	.set sound_len, __f_data_base + 0x2ce8
	.size sound_len, 0x4
	.globl GameMenuHotKey
	.set GameMenuHotKey, __f_data_base + 0x2cec
	.size GameMenuHotKey, 0x4
	.globl SaveDefaultStateKey
	.set SaveDefaultStateKey, __f_data_base + 0x2cf0
	.size SaveDefaultStateKey, 0x4
	.globl _mxml_key
	.set _mxml_key, __f_data_base + 0x2cf4
	.size _mxml_key, 0x4
	.globl _libiconv_version
	.set _libiconv_version, __f_data_base + 0x2cf8
	.size _libiconv_version, 0x4

/* .bss：193 个符号 */
	.globl completed.10349
	.set completed.10349, __f_bss_base + 0x0
	.size completed.10349, 0x1
	.globl log_file_initialized
	.set log_file_initialized, __f_bss_base + 0x4
	.size log_file_initialized, 0x1
	.globl log_file_fp
	.set log_file_fp, __f_bss_base + 0x8
	.size log_file_fp, 0x4
	.globl shm
	.set shm, __f_bss_base + 0xc
	.size shm, 0x4
	.globl spi_printf_needflash
	.set spi_printf_needflash, __f_bss_base + 0x10
	.size spi_printf_needflash, 0x4
	.globl scr_data
	.set scr_data, __f_bss_base + 0x14
	.size scr_data, 0x4
	.globl soft_rotation
	.set soft_rotation, __f_bss_base + 0x18
	.size soft_rotation, 0x4
	.globl displayfps
	.set displayfps, __f_bss_base + 0x1c
	.size displayfps, 0x4
	.globl DisplayThread
	.set DisplayThread, __f_bss_base + 0x20
	.size DisplayThread, 0x4
	.globl CRU
	.set CRU, __f_bss_base + 0x24
	.size CRU, 0x4
	.globl GRF
	.set GRF, __f_bss_base + 0x28
	.size GRF, 0x4
	.globl GPIO0
	.set GPIO0, __f_bss_base + 0x2c
	.size GPIO0, 0x4
	.globl GPIO1
	.set GPIO1, __f_bss_base + 0x30
	.size GPIO1, 0x4
	.globl GPIO2
	.set GPIO2, __f_bss_base + 0x34
	.size GPIO2, 0x4
	.globl joy_key_tmp
	.set joy_key_tmp, __f_bss_base + 0x38
	.size joy_key_tmp, 0x10
	.globl gpiosignal
	.set gpiosignal, __f_bss_base + 0x48
	.size gpiosignal, 0x4
	.globl gpiofp
	.set gpiofp, __f_bss_base + 0x4c
	.size gpiofp, 0x4
	.globl handle
	.set handle, __f_bss_base + 0x50
	.size handle, 0x4
	.globl DisplayThreadflag
	.set DisplayThreadflag, __f_bss_base + 0x54
	.size DisplayThreadflag, 0x4
	.globl mutex
	.set mutex, __f_bss_base + 0x58
	.size mutex, 0x18
	.globl cond
	.set cond, __f_bss_base + 0x70
	.size cond, 0x30
	.globl _ZL10zopenerror
	.set _ZL10zopenerror, __f_bss_base + 0xa0
	.size _ZL10zopenerror, 0x4
	.globl lasterrorU
	.set lasterrorU, __f_bss_base + 0xa4
	.size lasterrorU, 0x4
	.globl file_info_list
	.set file_info_list, __f_bss_base + 0xa8
	.size file_info_list, 0xa0a0
	.globl DAT_003b2320
	.set DAT_003b2320, __f_bss_base + 0x1a8
	.size DAT_003b2320, 0x0
	.globl DAT_003b2324
	.set DAT_003b2324, __f_bss_base + 0x1ac
	.size DAT_003b2324, 0x0
	.globl DAT_003b23a4
	.set DAT_003b23a4, __f_bss_base + 0x22c
	.size DAT_003b23a4, 0x0
	.globl DAT_003b2424
	.set DAT_003b2424, __f_bss_base + 0x2ac
	.size DAT_003b2424, 0x0
	.globl DAT_003b24a4
	.set DAT_003b24a4, __f_bss_base + 0x32c
	.size DAT_003b24a4, 0x0
	.globl FilenameExt
	.set FilenameExt, __f_bss_base + 0xa148
	.size FilenameExt, 0x4
	.globl tree
	.set tree, __f_bss_base + 0xa14c
	.size tree, 0x4
	.globl filelist_tree
	.set filelist_tree, __f_bss_base + 0xa150
	.size filelist_tree, 0x4
	.globl res_hz
	.set res_hz, __f_bss_base + 0xa154
	.size res_hz, 0x4
	.globl ze
	.set ze, __f_bss_base + 0xa158
	.size ze, 0x130
	.globl zr
	.set zr, __f_bss_base + 0xa288
	.size zr, 0x4
	.globl mui_fast_lsit
	.set mui_fast_lsit, __f_bss_base + 0xa28c
	.size mui_fast_lsit, 0x4
	.globl m_search
	.set m_search, __f_bss_base + 0xa290
	.size m_search, 0x4
	.globl DisplayThumbnailflag
	.set DisplayThumbnailflag, __f_bss_base + 0xa294
	.size DisplayThumbnailflag, 0x4
	.globl ForceFlashCount
	.set ForceFlashCount, __f_bss_base + 0xa298
	.size ForceFlashCount, 0x4
	.globl diff_prev
	.set diff_prev, __f_bss_base + 0xa29c
	.size diff_prev, 0x4
	.globl m_time0
	.set m_time0, __f_bss_base + 0xa2a0
	.size m_time0, 0x4
	.globl font
	.set font, __f_bss_base + 0xa2a4
	.size font, 0x7c
	.globl fontscale
	.set fontscale, __f_bss_base + 0xa320
	.size fontscale, 0x4
	.globl fontascent
	.set fontascent, __f_bss_base + 0xa324
	.size fontascent, 0x4
	.globl fontbaseline
	.set fontbaseline, __f_bss_base + 0xa328
	.size fontbaseline, 0x4
	.globl OutRect
	.set OutRect, __f_bss_base + 0xa32c
	.size OutRect, 0x18
	.globl fontbitmap
	.set fontbitmap, __f_bss_base + 0xa344
	.size fontbitmap, 0x1000
	.globl fontname
	.set fontname, __f_bss_base + 0xb344
	.size fontname, 0x20
	.globl fontbuffer
	.set fontbuffer, __f_bss_base + 0xb364
	.size fontbuffer, 0x4
	.globl configitems
	.set configitems, __f_bss_base + 0xb368
	.size configitems, 0xc350
	.globl m_menulog
	.set m_menulog, __f_bss_base + 0x176b8
	.size m_menulog, 0x1bc
	.globl path
	.set path, __f_bss_base + 0x17874
	.size path, 0x100
	.globl core_info_list
	.set core_info_list, __f_bss_base + 0x17974
	.size core_info_list, 0x5000
	.globl hz
	.set hz, __f_bss_base + 0x1c974
	.size hz, 0x4
	.globl SoundBuffer
	.set SoundBuffer, __f_bss_base + 0x1c978
	.size SoundBuffer, 0xb80
	.globl scrbuf
	.set scrbuf, __f_bss_base + 0x1d4f8
	.size scrbuf, 0x4
	.globl Soundplayflag
	.set Soundplayflag, __f_bss_base + 0x1d4fc
	.size Soundplayflag, 0x4
	.globl errorcount
	.set errorcount, __f_bss_base + 0x1d500
	.size errorcount, 0x4
	.globl bimapFilebuffer
	.set bimapFilebuffer, __f_bss_base + 0x1d504
	.size bimapFilebuffer, 0x4
	.globl USBJoy_debug
	.set USBJoy_debug, __f_bss_base + 0x1d508
	.size USBJoy_debug, 0x4
	.globl SPI_MODE
	.set SPI_MODE, __f_bss_base + 0x1d50c
	.size SPI_MODE, 0x4
	.globl system_directory
	.set system_directory, __f_bss_base + 0x1d510
	.size system_directory, 0x100
	.globl save_directory
	.set save_directory, __f_bss_base + 0x1d610
	.size save_directory, 0x100
	.globl environment_str
	.set environment_str, __f_bss_base + 0x1d710
	.size environment_str, 0x100
	.globl user_joy_key_trubo
	.set user_joy_key_trubo, __f_bss_base + 0x1d814
	.size user_joy_key_trubo, 0x100
	.globl rgb_565_buffer
	.set rgb_565_buffer, __f_bss_base + 0x1d914
	.size rgb_565_buffer, 0x4
	.globl use_rgb_8888
	.set use_rgb_8888, __f_bss_base + 0x1d918
	.size use_rgb_8888, 0x4
	.globl rotation_buff
	.set rotation_buff, __f_bss_base + 0x1d91c
	.size rotation_buff, 0x4
	.globl rotation
	.set rotation, __f_bss_base + 0x1d920
	.size rotation, 0x4
	.globl skipCounter
	.set skipCounter, __f_bss_base + 0x1d924
	.size skipCounter, 0x4
	.globl FrameCount0
	.set FrameCount0, __f_bss_base + 0x1d928
	.size FrameCount0, 0x4
	.globl frames_prev
	.set frames_prev, __f_bss_base + 0x1d92c
	.size frames_prev, 0x4
	.globl PlayFrameError
	.set PlayFrameError, __f_bss_base + 0x1d930
	.size PlayFrameError, 0x4
	.globl ticks_ptr
	.set ticks_ptr, __f_bss_base + 0x1d934
	.size ticks_ptr, 0x4
	.globl AutoRestoreKey
	.set AutoRestoreKey, __f_bss_base + 0x1d938
	.size AutoRestoreKey, 0x4
	.globl _mxml_key_once
	.set _mxml_key_once, __f_bss_base + 0x1d93c
	.size _mxml_key_once, 0x4
	.globl g_sfc_reg
	.set g_sfc_reg, __f_bss_base + 0x1d940
	.size g_sfc_reg, 0x4
	.globl FlashSize
	.set FlashSize, __f_bss_base + 0x1d944
	.size FlashSize, 0x4
	.globl UniqueID
	.set UniqueID, __f_bss_base + 0x1d948
	.size UniqueID, 0x8
	.globl corecfg
	.set corecfg, __f_bss_base + 0x1d950
	.size corecfg, 0x3e80
	.globl items
	.set items, __f_bss_base + 0x217d0
	.size items, 0x3e80
	.globl sbi
	.set sbi, __f_bss_base + 0x25650
	.size sbi, 0x2204
	.globl mi
	.set mi, __f_bss_base + 0x27854
	.size mi, 0x1b20
	.globl file_info_list_ext
	.set file_info_list_ext, __f_bss_base + 0x29374
	.size file_info_list_ext, 0x1900
	.globl hi
	.set hi, __f_bss_base + 0x2ac74
	.size hi, 0x1210
	.globl autorundriver
	.set autorundriver, __f_bss_base + 0x2be84
	.size autorundriver, 0x1000
	.globl autorunfile
	.set autorunfile, __f_bss_base + 0x2ce84
	.size autorunfile, 0x1000
	.globl mp3DecInfo
	.set mp3DecInfo, __f_bss_base + 0x2de84
	.size mp3DecInfo, 0x7f0
	.globl di
	.set di, __f_bss_base + 0x2e674
	.size di, 0x348
	.globl bprintf_buf
	.set bprintf_buf, __f_bss_base + 0x2e9bc
	.size bprintf_buf, 0x200
	.globl si
	.set si, __f_bss_base + 0x2ebbc
	.size si, 0x148
	.globl sfi
	.set sfi, __f_bss_base + 0x2ed04
	.size sfi, 0x11c
	.globl Nesname
	.set Nesname, __f_bss_base + 0x2ee20
	.size Nesname, 0x100
	.globl RomName
	.set RomName, __f_bss_base + 0x2ef20
	.size RomName, 0x100
	.globl fileName
	.set fileName, __f_bss_base + 0x2f020
	.size fileName, 0x100
	.globl resource_path
	.set resource_path, __f_bss_base + 0x2f120
	.size resource_path, 0x100
	.globl root_path
	.set root_path, __f_bss_base + 0x2f220
	.size root_path, 0x100
	.globl work_path
	.set work_path, __f_bss_base + 0x2f320
	.size work_path, 0x100
	.globl m_crctable
	.set m_crctable, __f_bss_base + 0x2f420
	.size m_crctable, 0x80
	.globl mainkey
	.set mainkey, __f_bss_base + 0x2f4a0
	.size mainkey, 0x80
	.globl InputDeviceInfo
	.set InputDeviceInfo, __f_bss_base + 0x2f520
	.size InputDeviceInfo, 0x70
	.globl keyMapping
	.set keyMapping, __f_bss_base + 0x2f590
	.size keyMapping, 0x60
	.globl SoundPlayer
	.set SoundPlayer, __f_bss_base + 0x2f5f0
	.size SoundPlayer, 0x48
	.globl fpsbuf
	.set fpsbuf, __f_bss_base + 0x2f638
	.size fpsbuf, 0x40
	.globl ticks_buf
	.set ticks_buf, __f_bss_base + 0x2f678
	.size ticks_buf, 0x40
	.globl fh
	.set fh, __f_bss_base + 0x2f6b8
	.size fh, 0x38
	.globl mui_Effect0
	.set mui_Effect0, __f_bss_base + 0x2f6f0
	.size mui_Effect0, 0x24
	.globl mui_Effect1
	.set mui_Effect1, __f_bss_base + 0x2f714
	.size mui_Effect1, 0x24
	.globl mui_MenuMusic
	.set mui_MenuMusic, __f_bss_base + 0x2f738
	.size mui_MenuMusic, 0x24
	.globl GamePath
	.set GamePath, __f_bss_base + 0x2f778
	.size GamePath, 0x1c
	.globl key2
	.set key2, __f_bss_base + 0x2f794
	.size key2, 0x1c
	.globl mdtemp1
	.set mdtemp1, __f_bss_base + 0x2f7b0
	.size mdtemp1, 0x1c
	.globl game
	.set game, __f_bss_base + 0x2f7dc
	.size game, 0x10
	.globl game_joy_key
	.set game_joy_key, __f_bss_base + 0x2f7ec
	.size game_joy_key, 0x10
	.globl joy_key
	.set joy_key, __f_bss_base + 0x2f7fc
	.size joy_key, 0x10
	.globl this_frame
	.set this_frame, __f_bss_base + 0x2f80c
	.size this_frame, 0x10
	.globl frame_time_last
	.set frame_time_last, __f_bss_base + 0x2f820
	.size frame_time_last, 0x8
	.globl progress_stepcount
	.set progress_stepcount, __f_bss_base + 0x2f828
	.size progress_stepcount, 0x8
	.globl RF_joy_key
	.set RF_joy_key, __f_bss_base + 0x2f830
	.size RF_joy_key, 0x8
	.globl inTimeVal
	.set inTimeVal, __f_bss_base + 0x2f838
	.size inTimeVal, 0x8
	.globl outTimeVal
	.set outTimeVal, __f_bss_base + 0x2f840
	.size outTimeVal, 0x8
	.globl ChangeSeting
	.set ChangeSeting, __f_bss_base + 0x2f848
	.size ChangeSeting, 0x4
	.globl DispFrameCount
	.set DispFrameCount, __f_bss_base + 0x2f84c
	.size DispFrameCount, 0x4
	.globl DisplayZoomFlag
	.set DisplayZoomFlag, __f_bss_base + 0x2f850
	.size DisplayZoomFlag, 0x4
	.globl Filetype
	.set Filetype, __f_bss_base + 0x2f854
	.size Filetype, 0x4
	.globl FrameCount
	.set FrameCount, __f_bss_base + 0x2f858
	.size FrameCount, 0x4
	.globl FrameSkip
	.set FrameSkip, __f_bss_base + 0x2f85c
	.size FrameSkip, 0x4
	.globl Frame_data
	.set Frame_data, __f_bss_base + 0x2f860
	.size Frame_data, 0x4
	.globl Frame_height
	.set Frame_height, __f_bss_base + 0x2f864
	.size Frame_height, 0x4
	.globl Frame_pitch
	.set Frame_pitch, __f_bss_base + 0x2f868
	.size Frame_pitch, 0x4
	.globl Frame_width
	.set Frame_width, __f_bss_base + 0x2f86c
	.size Frame_width, 0x4
	.globl Joy1_Delay
	.set Joy1_Delay, __f_bss_base + 0x2f870
	.size Joy1_Delay, 0x4
	.globl Joy1_Press
	.set Joy1_Press, __f_bss_base + 0x2f874
	.size Joy1_Press, 0x4
	.globl SoundBufferIndex0
	.set SoundBufferIndex0, __f_bss_base + 0x2f878
	.size SoundBufferIndex0, 0x4
	.globl SoundBufferIndex1
	.set SoundBufferIndex1, __f_bss_base + 0x2f87c
	.size SoundBufferIndex1, 0x4
	.globl SoundBufferLength
	.set SoundBufferLength, __f_bss_base + 0x2f880
	.size SoundBufferLength, 0x4
	.globl TimeCountReg
	.set TimeCountReg, __f_bss_base + 0x2f884
	.size TimeCountReg, 0x4
	.globl Time_0
	.set Time_0, __f_bss_base + 0x2f888
	.size Time_0, 0x4
	.globl Time_1
	.set Time_1, __f_bss_base + 0x2f88c
	.size Time_1, 0x4
	.globl USE_HDMI_OUT
	.set USE_HDMI_OUT, __f_bss_base + 0x2f890
	.size USE_HDMI_OUT, 0x4
	.globl ZIP_BUF
	.set ZIP_BUF, __f_bss_base + 0x2f894
	.size ZIP_BUF, 0x4
	.globl ZIP_BUF_SIZE
	.set ZIP_BUF_SIZE, __f_bss_base + 0x2f898
	.size ZIP_BUF_SIZE, 0x4
	.globl _SetDoubleBuffer
	.set _SetDoubleBuffer, __f_bss_base + 0x2f89c
	.size _SetDoubleBuffer, 0x4
	.globl _SetFrameSkip
	.set _SetFrameSkip, __f_bss_base + 0x2f8a0
	.size _SetFrameSkip, 0x4
	.globl _retro_get_region
	.set _retro_get_region, __f_bss_base + 0x2f8a4
	.size _retro_get_region, 0x4
	.globl _retro_is_support
	.set _retro_is_support, __f_bss_base + 0x2f8a8
	.size _retro_is_support, 0x4
	.globl _retro_run
	.set _retro_run, __f_bss_base + 0x2f8ac
	.size _retro_run, 0x4
	.globl _retro_serialize
	.set _retro_serialize, __f_bss_base + 0x2f8b0
	.size _retro_serialize, 0x4
	.globl _retro_serialize_size
	.set _retro_serialize_size, __f_bss_base + 0x2f8b4
	.size _retro_serialize_size, 0x4
	.globl _retro_set_device
	.set _retro_set_device, __f_bss_base + 0x2f8b8
	.size _retro_set_device, 0x4
	.globl _retro_unserialize
	.set _retro_unserialize, __f_bss_base + 0x2f8bc
	.size _retro_unserialize, 0x4
	.globl disp_times
	.set disp_times, __f_bss_base + 0x2f8c4
	.size disp_times, 0x4
	.globl fps
	.set fps, __f_bss_base + 0x2f8c8
	.size fps, 0x4
	.globl fps_ptr
	.set fps_ptr, __f_bss_base + 0x2f8cc
	.size fps_ptr, 0x4
	.globl initialTicks
	.set initialTicks, __f_bss_base + 0x2f8d0
	.size initialTicks, 0x4
	.globl joytemp0
	.set joytemp0, __f_bss_base + 0x2f8d4
	.size joytemp0, 0x4
	.globl joytemp1
	.set joytemp1, __f_bss_base + 0x2f8d8
	.size joytemp1, 0x4
	.globl m_ticks
	.set m_ticks, __f_bss_base + 0x2f8dc
	.size m_ticks, 0x4
	.globl maxSkips
	.set maxSkips, __f_bss_base + 0x2f8e0
	.size maxSkips, 0x4
	.globl n_input_height
	.set n_input_height, __f_bss_base + 0x2f8e4
	.size n_input_height, 0x4
	.globl n_input_visible_height
	.set n_input_visible_height, __f_bss_base + 0x2f8e8
	.size n_input_visible_height, 0x4
	.globl n_input_visible_width
	.set n_input_visible_width, __f_bss_base + 0x2f8ec
	.size n_input_visible_width, 0x4
	.globl n_input_width
	.set n_input_width, __f_bss_base + 0x2f8f0
	.size n_input_width, 0x4
	.globl output_x
	.set output_x, __f_bss_base + 0x2f8f4
	.size output_x, 0x4
	.globl output_y
	.set output_y, __f_bss_base + 0x2f8f8
	.size output_y, 0x4
	.globl overtime
	.set overtime, __f_bss_base + 0x2f8fc
	.size overtime, 0x4
	.globl overtime1
	.set overtime1, __f_bss_base + 0x2f900
	.size overtime1, 0x4
	.globl pal_ntsc
	.set pal_ntsc, __f_bss_base + 0x2f904
	.size pal_ntsc, 0x4
	.globl pause_ret
	.set pause_ret, __f_bss_base + 0x2f908
	.size pause_ret, 0x4
	.globl pf
	.set pf, __f_bss_base + 0x2f90c
	.size pf, 0x4
	.globl prev_time
	.set prev_time, __f_bss_base + 0x2f910
	.size prev_time, 0x4
	.globl romfile
	.set romfile, __f_bss_base + 0x2f914
	.size romfile, 0x4
	.globl scr_buf
	.set scr_buf, __f_bss_base + 0x2f918
	.size scr_buf, 0x4
	.globl scr_h_size
	.set scr_h_size, __f_bss_base + 0x2f91c
	.size scr_h_size, 0x4
	.globl scr_v_size
	.set scr_v_size, __f_bss_base + 0x2f920
	.size scr_v_size, 0x4
	.globl screen_w
	.set screen_w, __f_bss_base + 0x2f924
	.size screen_w, 0x4
	.globl screen_x
	.set screen_x, __f_bss_base + 0x2f928
	.size screen_x, 0x4
	.globl set_rotation
	.set set_rotation, __f_bss_base + 0x2f92c
	.size set_rotation, 0x4
	.globl shmid
	.set shmid, __f_bss_base + 0x2f930
	.size shmid, 0x4
	.globl sound_driver_init
	.set sound_driver_init, __f_bss_base + 0x2f934
	.size sound_driver_init, 0x4
	.globl sound_driver_playframe
	.set sound_driver_playframe, __f_bss_base + 0x2f938
	.size sound_driver_playframe, 0x4
	.globl sound_times
	.set sound_times, __f_bss_base + 0x2f93c
	.size sound_times, 0x4
	.globl video_driver_deinit
	.set video_driver_deinit, __f_bss_base + 0x2f940
	.size video_driver_deinit, 0x4
	.globl video_driver_frame
	.set video_driver_frame, __f_bss_base + 0x2f944
	.size video_driver_frame, 0x4
	.globl video_driver_get_size
	.set video_driver_get_size, __f_bss_base + 0x2f948
	.size video_driver_get_size, 0x4
	.globl video_driver_setting
	.set video_driver_setting, __f_bss_base + 0x2f94c
	.size video_driver_setting, 0x4
	.globl spi_id
	.set spi_id, __f_bss_base + 0x2f950
	.size spi_id, 0x3
	.globl IR_JoyKey
	.set IR_JoyKey, __f_bss_base + 0x2f954
	.size IR_JoyKey, 0x2
	.globl ChannelIndex
	.set ChannelIndex, __f_bss_base + 0x2f956
	.size ChannelIndex, 0x1
	.globl ProtectCode
	.set ProtectCode, __f_bss_base + 0x2f957
	.size ProtectCode, 0x1
	.globl ProtectVer
	.set ProtectVer, __f_bss_base + 0x2f958
	.size ProtectVer, 0x1
	.globl ReturnToMenu
	.set ReturnToMenu, __f_bss_base + 0x2f959
	.size ReturnToMenu, 0x1
	.globl joy_key_Temp
	.set joy_key_Temp, __f_bss_base + 0x2f95a
	.size joy_key_Temp, 0x1

/* ---- 重名符号拆分别名（P3 二期④）----
 * 依据：tools/xref_scan.py（A32 PIC 指令级交叉引用）+ tools/dup_assign.py（TU 归属）
 * 实测报告见 report/xref_dup.txt。同名两份分属不同编译单元，合并会造成静默语义错位。 */
	.globl ArchivePath_global
	.set ArchivePath_global, __f_bss_base + 0x2f75c
	.size ArchivePath_global, 0x1c
	.globl SoundBuffer_global
	.set SoundBuffer_global, __f_bss_base + 0x2f7cc
	.size SoundBuffer_global, 0x10
	.globl diff_prev_global
	.set diff_prev_global, __f_bss_base + 0x2f8c0
	.size diff_prev_global, 0x4
	.globl handle_emurun
	.set handle_emurun, __f_bss_base + 0x1d810
	.size handle_emurun, 0x4

