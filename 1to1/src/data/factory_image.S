/* 自动生成 —— 请勿手改；见 tools/gen_data_module.py
 * 每个段只放一份工厂原始镜像，全部符号（含 Ghidra DAT_x）以 .set 别名指向段内偏移。
 * 依据：段 VMA 必须与工厂一致（代码里烧死绝对地址）；DAT_x 不是工厂符号。 */

	.section .rodata,"a",%progbits
	.globl __f_rodata_base
	.type __f_rodata_base, %object
__f_rodata_base:
	.incbin "factory_rodata.bin"
	.size __f_rodata_base, 0xd1358

	.section .data.rel.ro.local,"aw",%progbits
	.globl __f_data_rel_ro_local_base
	.type __f_data_rel_ro_local_base, %object
__f_data_rel_ro_local_base:
	.incbin "factory_data_rel_ro_local.bin"
	.size __f_data_rel_ro_local_base, 0x914

	.section .data,"aw",%progbits
	.globl __f_data_base
	.type __f_data_base, %object
__f_data_base:
	.incbin "factory_data.bin"
	.size __f_data_base, 0x2cfc

	.section .bss,"aw",%nobits
	.globl __f_bss_base
	.type __f_bss_base, %object
__f_bss_base:
	.space 0x2f95b
	.size __f_bss_base, 0x2f95b

/* ---- 符号别名 ---- */
/* .rodata：737 个符号 */
	.globl DAT_002dbcb4
	.set DAT_002dbcb4, __f_rodata_base + 0x10
	.globl DAT_002dbd74
	.set DAT_002dbd74, __f_rodata_base + 0xd0
	.globl DAT_002dbe58
	.set DAT_002dbe58, __f_rodata_base + 0x1b4
	.globl DAT_002dbe5c
	.set DAT_002dbe5c, __f_rodata_base + 0x1b8
	.globl DAT_002dbe60
	.set DAT_002dbe60, __f_rodata_base + 0x1bc
	.globl DAT_002dccf4
	.set DAT_002dccf4, __f_rodata_base + 0x1050
	.globl DAT_002dcd50
	.set DAT_002dcd50, __f_rodata_base + 0x10ac
	.globl DAT_002dcd5c
	.set DAT_002dcd5c, __f_rodata_base + 0x10b8
	.globl DAT_002dcd70
	.set DAT_002dcd70, __f_rodata_base + 0x10cc
	.globl DAT_002dcea4
	.set DAT_002dcea4, __f_rodata_base + 0x1200
	.globl DAT_002dcf4c
	.set DAT_002dcf4c, __f_rodata_base + 0x12a8
	.globl DAT_002dd508
	.set DAT_002dd508, __f_rodata_base + 0x1864
	.globl DAT_002dd64c
	.set DAT_002dd64c, __f_rodata_base + 0x19a8
	.globl DAT_002dd860
	.set DAT_002dd860, __f_rodata_base + 0x1bbc
	.globl DAT_002dd878
	.set DAT_002dd878, __f_rodata_base + 0x1bd4
	.globl DAT_002dd88c
	.set DAT_002dd88c, __f_rodata_base + 0x1be8
	.globl DAT_002ddd74
	.set DAT_002ddd74, __f_rodata_base + 0x20d0
	.globl DAT_002dee30
	.set DAT_002dee30, __f_rodata_base + 0x318c
	.globl _ZL6cplens
	.set _ZL6cplens, __f_rodata_base + 0x31a8
	.globl _ZL6cplext
	.set _ZL6cplext, __f_rodata_base + 0x3224
	.globl _ZL6cpdist
	.set _ZL6cpdist, __f_rodata_base + 0x32a0
	.globl _ZL6cpdext
	.set _ZL6cpdext, __f_rodata_base + 0x3318
	.globl _ZL8fixed_tl
	.set _ZL8fixed_tl, __f_rodata_base + 0x3390
	.globl _ZL8fixed_td
	.set _ZL8fixed_td, __f_rodata_base + 0x4390
	.globl _ZL12inflate_mask
	.set _ZL12inflate_mask, __f_rodata_base + 0x4490
	.globl _ZL6border
	.set _ZL6border, __f_rodata_base + 0x44d4
	.globl _ZL9crc_table
	.set _ZL9crc_table, __f_rodata_base + 0x4520
	.globl mui_Rect
	.set mui_Rect, __f_rodata_base + 0x4920
	.globl m_Typetab
	.set m_Typetab, __f_rodata_base + 0x49d0
	.globl GBAKeyMapping
	.set GBAKeyMapping, __f_rodata_base + 0x4a84
	.globl NESKeyMapping
	.set NESKeyMapping, __f_rodata_base + 0x4ae4
	.globl SNESKeyMapping
	.set SNESKeyMapping, __f_rodata_base + 0x4b44
	.globl GENSKeyMapping
	.set GENSKeyMapping, __f_rodata_base + 0x4b44
	.globl DEFKeyMapping
	.set DEFKeyMapping, __f_rodata_base + 0x4b44
	.globl FBA_index
	.set FBA_index, __f_rodata_base + 0x4be4
	.globl SNES_index
	.set SNES_index, __f_rodata_base + 0x4bfc
	.globl MD_index
	.set MD_index, __f_rodata_base + 0x4c14
	.globl STD_index
	.set STD_index, __f_rodata_base + 0x4c2c
	.globl joy_key_mask
	.set joy_key_mask, __f_rodata_base + 0x4c44
	.globl asc2_1608
	.set asc2_1608, __f_rodata_base + 0x4c84
	.globl DAT_002e0d18
	.set DAT_002e0d18, __f_rodata_base + 0x5074
	.globl xmp3_sfBandTable
	.set xmp3_sfBandTable, __f_rodata_base + 0x5274
	.globl xmp3_slotTab
	.set xmp3_slotTab, __f_rodata_base + 0x5510
	.globl xmp3_sideBytesTab
	.set xmp3_sideBytesTab, __f_rodata_base + 0x5620
	.globl xmp3_bitsPerSlotTab
	.set xmp3_bitsPerSlotTab, __f_rodata_base + 0x562c
	.globl xmp3_samplesPerFrameTab
	.set xmp3_samplesPerFrameTab, __f_rodata_base + 0x5634
	.globl xmp3_bitrateTab
	.set xmp3_bitrateTab, __f_rodata_base + 0x5648
	.globl xmp3_samplerateTab
	.set xmp3_samplerateTab, __f_rodata_base + 0x5758
	.globl SFLenTab
	.set SFLenTab, __f_rodata_base + 0x577c
	.globl NRTab
	.set NRTab, __f_rodata_base + 0x579c
	.globl xmp3_polyCoef
	.set xmp3_polyCoef, __f_rodata_base + 0x57e4
	.globl xmp3_coef32
	.set xmp3_coef32, __f_rodata_base + 0x5c04
	.globl xmp3_csa
	.set xmp3_csa, __f_rodata_base + 0x5c80
	.globl xmp3_uniqueIDTab
	.set xmp3_uniqueIDTab, __f_rodata_base + 0x5cc0
	.globl xmp3_ISFIIP
	.set xmp3_ISFIIP, __f_rodata_base + 0x5cc8
	.globl xmp3_ISFMpeg2
	.set xmp3_ISFMpeg2, __f_rodata_base + 0x5cd8
	.globl xmp3_ISFMpeg1
	.set xmp3_ISFMpeg1, __f_rodata_base + 0x5dd8
	.globl xmp3_imdctWin
	.set xmp3_imdctWin, __f_rodata_base + 0x5e10
	.globl c18
	.set c18, __f_rodata_base + 0x6050
	.globl fastWin36
	.set fastWin36, __f_rodata_base + 0x6074
	.globl xmp3_quadTabMaxBits
	.set xmp3_quadTabMaxBits, __f_rodata_base + 0x60bc
	.globl xmp3_quadTabOffset
	.set xmp3_quadTabOffset, __f_rodata_base + 0x60c4
	.globl xmp3_quadTable
	.set xmp3_quadTable, __f_rodata_base + 0x60cc
	.globl xmp3_huffTabLookup
	.set xmp3_huffTabLookup, __f_rodata_base + 0x611c
	.globl xmp3_huffTabOffset
	.set xmp3_huffTabOffset, __f_rodata_base + 0x621c
	.globl xmp3_huffTable
	.set xmp3_huffTable, __f_rodata_base + 0x629c
	.globl pow43_14
	.set pow43_14, __f_rodata_base + 0x83c0
	.globl pow14
	.set pow14, __f_rodata_base + 0x84c0
	.globl pow43
	.set pow43, __f_rodata_base + 0x84d0
	.globl pow2frac
	.set pow2frac, __f_rodata_base + 0x8590
	.globl pow2exp
	.set pow2exp, __f_rodata_base + 0x85b0
	.globl preTab
	.set preTab, __f_rodata_base + 0x85d0
	.globl dcttab
	.set dcttab, __f_rodata_base + 0x85e8
	.globl direct_tab
	.set direct_tab, __f_rodata_base + 0x86a8
	.globl xdirect_tab
	.set xdirect_tab, __f_rodata_base + 0x86b8
	.globl xbase64_tab
	.set xbase64_tab, __f_rodata_base + 0x86c8
	.globl iso8859_2_2uni
	.set iso8859_2_2uni, __f_rodata_base + 0x86d8
	.globl iso8859_2_page00
	.set iso8859_2_page00, __f_rodata_base + 0x8798
	.globl iso8859_2_page02
	.set iso8859_2_page02, __f_rodata_base + 0x8878
	.globl iso8859_3_2uni
	.set iso8859_3_2uni, __f_rodata_base + 0x8898
	.globl iso8859_3_page00
	.set iso8859_3_page00, __f_rodata_base + 0x8958
	.globl iso8859_3_page01
	.set iso8859_3_page01, __f_rodata_base + 0x89b8
	.globl iso8859_3_page02
	.set iso8859_3_page02, __f_rodata_base + 0x8a30
	.globl iso8859_4_2uni
	.set iso8859_4_2uni, __f_rodata_base + 0x8a38
	.globl iso8859_4_page00
	.set iso8859_4_page00, __f_rodata_base + 0x8af8
	.globl iso8859_4_page02
	.set iso8859_4_page02, __f_rodata_base + 0x8bd8
	.globl iso8859_5_2uni
	.set iso8859_5_2uni, __f_rodata_base + 0x8bf8
	.globl iso8859_5_page00
	.set iso8859_5_page00, __f_rodata_base + 0x8cb8
	.globl iso8859_5_page04
	.set iso8859_5_page04, __f_rodata_base + 0x8cc8
	.globl iso8859_6_2uni
	.set iso8859_6_2uni, __f_rodata_base + 0x8d28
	.globl iso8859_6_page00
	.set iso8859_6_page00, __f_rodata_base + 0x8de8
	.globl iso8859_6_page06
	.set iso8859_6_page06, __f_rodata_base + 0x8df8
	.globl iso8859_7_2uni
	.set iso8859_7_2uni, __f_rodata_base + 0x8e48
	.globl iso8859_7_page00
	.set iso8859_7_page00, __f_rodata_base + 0x8f08
	.globl iso8859_7_page03
	.set iso8859_7_page03, __f_rodata_base + 0x8f28
	.globl iso8859_7_page20
	.set iso8859_7_page20, __f_rodata_base + 0x8f80
	.globl iso8859_8_2uni
	.set iso8859_8_2uni, __f_rodata_base + 0x8f90
	.globl iso8859_8_page00
	.set iso8859_8_page00, __f_rodata_base + 0x9050
	.globl iso8859_8_page05
	.set iso8859_8_page05, __f_rodata_base + 0x90a8
	.globl iso8859_8_page20
	.set iso8859_8_page20, __f_rodata_base + 0x90c8
	.globl iso8859_9_2uni
	.set iso8859_9_2uni, __f_rodata_base + 0x90d8
	.globl iso8859_9_page00
	.set iso8859_9_page00, __f_rodata_base + 0x9138
	.globl iso8859_9_page01
	.set iso8859_9_page01, __f_rodata_base + 0x9168
	.globl iso8859_10_2uni
	.set iso8859_10_2uni, __f_rodata_base + 0x91b0
	.globl iso8859_10_page00
	.set iso8859_10_page00, __f_rodata_base + 0x9270
	.globl iso8859_13_2uni
	.set iso8859_13_2uni, __f_rodata_base + 0x9350
	.globl iso8859_13_page00
	.set iso8859_13_page00, __f_rodata_base + 0x9410
	.globl iso8859_13_page20
	.set iso8859_13_page20, __f_rodata_base + 0x94f0
	.globl iso8859_14_2uni
	.set iso8859_14_2uni, __f_rodata_base + 0x94f8
	.globl iso8859_14_page00
	.set iso8859_14_page00, __f_rodata_base + 0x95b8
	.globl iso8859_14_page01_0
	.set iso8859_14_page01_0, __f_rodata_base + 0x9618
	.globl iso8859_14_page01_1
	.set iso8859_14_page01_1, __f_rodata_base + 0x9638
	.globl iso8859_14_page1e_0
	.set iso8859_14_page1e_0, __f_rodata_base + 0x9648
	.globl iso8859_14_page1e_1
	.set iso8859_14_page1e_1, __f_rodata_base + 0x96d0
	.globl iso8859_15_2uni
	.set iso8859_15_2uni, __f_rodata_base + 0x96d8
	.globl iso8859_15_page00
	.set iso8859_15_page00, __f_rodata_base + 0x9718
	.globl iso8859_15_page01
	.set iso8859_15_page01, __f_rodata_base + 0x9738
	.globl iso8859_16_2uni
	.set iso8859_16_2uni, __f_rodata_base + 0x9768
	.globl iso8859_16_page00
	.set iso8859_16_page00, __f_rodata_base + 0x9828
	.globl iso8859_16_page02
	.set iso8859_16_page02, __f_rodata_base + 0x9908
	.globl iso8859_16_page20
	.set iso8859_16_page20, __f_rodata_base + 0x9910
	.globl koi8_r_2uni
	.set koi8_r_2uni, __f_rodata_base + 0x9918
	.globl koi8_r_page00
	.set koi8_r_page00, __f_rodata_base + 0x9a18
	.globl koi8_r_page04
	.set koi8_r_page04, __f_rodata_base + 0x9a70
	.globl koi8_r_page22
	.set koi8_r_page22, __f_rodata_base + 0x9ac8
	.globl koi8_r_page23
	.set koi8_r_page23, __f_rodata_base + 0x9b18
	.globl koi8_r_page25
	.set koi8_r_page25, __f_rodata_base + 0x9b20
	.globl koi8_u_2uni
	.set koi8_u_2uni, __f_rodata_base + 0x9bc8
	.globl koi8_u_page00
	.set koi8_u_page00, __f_rodata_base + 0x9cc8
	.globl koi8_u_page04
	.set koi8_u_page04, __f_rodata_base + 0x9d20
	.globl koi8_u_page22
	.set koi8_u_page22, __f_rodata_base + 0x9db8
	.globl koi8_u_page23
	.set koi8_u_page23, __f_rodata_base + 0x9e08
	.globl koi8_u_page25
	.set koi8_u_page25, __f_rodata_base + 0x9e10
	.globl koi8_ru_2uni
	.set koi8_ru_2uni, __f_rodata_base + 0x9eb8
	.globl koi8_ru_page00
	.set koi8_ru_page00, __f_rodata_base + 0x9fb8
	.globl koi8_ru_page04
	.set koi8_ru_page04, __f_rodata_base + 0xa010
	.globl koi8_ru_page22
	.set koi8_ru_page22, __f_rodata_base + 0xa0a8
	.globl koi8_ru_page23
	.set koi8_ru_page23, __f_rodata_base + 0xa0f8
	.globl koi8_ru_page25
	.set koi8_ru_page25, __f_rodata_base + 0xa100
	.globl cp1250_2uni
	.set cp1250_2uni, __f_rodata_base + 0xa1a8
	.globl cp1250_page00
	.set cp1250_page00, __f_rodata_base + 0xa2a8
	.globl cp1250_page02
	.set cp1250_page02, __f_rodata_base + 0xa388
	.globl cp1250_page20
	.set cp1250_page20, __f_rodata_base + 0xa3a8
	.globl cp1251_2uni
	.set cp1251_2uni, __f_rodata_base + 0xa3d8
	.globl cp1251_page00
	.set cp1251_page00, __f_rodata_base + 0xa4d8
	.globl cp1251_page04
	.set cp1251_page04, __f_rodata_base + 0xa4f8
	.globl cp1251_page20
	.set cp1251_page20, __f_rodata_base + 0xa590
	.globl cp1252_2uni
	.set cp1252_2uni, __f_rodata_base + 0xa5c0
	.globl cp1252_page01
	.set cp1252_page01, __f_rodata_base + 0xa600
	.globl cp1252_page02
	.set cp1252_page02, __f_rodata_base + 0xa648
	.globl cp1252_page20
	.set cp1252_page20, __f_rodata_base + 0xa668
	.globl cp1253_2uni
	.set cp1253_2uni, __f_rodata_base + 0xa698
	.globl cp1253_page00
	.set cp1253_page00, __f_rodata_base + 0xa798
	.globl cp1253_page03
	.set cp1253_page03, __f_rodata_base + 0xa7b8
	.globl cp1253_page20
	.set cp1253_page20, __f_rodata_base + 0xa808
	.globl cp1254_2uni_1
	.set cp1254_2uni_1, __f_rodata_base + 0xa838
	.globl cp1254_2uni_2
	.set cp1254_2uni_2, __f_rodata_base + 0xa878
	.globl cp1254_2uni_3
	.set cp1254_2uni_3, __f_rodata_base + 0xa898
	.globl cp1254_page00
	.set cp1254_page00, __f_rodata_base + 0xa8b8
	.globl cp1254_page01
	.set cp1254_page01, __f_rodata_base + 0xa8e8
	.globl cp1254_page02
	.set cp1254_page02, __f_rodata_base + 0xa968
	.globl cp1254_page20
	.set cp1254_page20, __f_rodata_base + 0xa988
	.globl cp1255_comp_table_data
	.set cp1255_comp_table_data, __f_rodata_base + 0xa9b8
	.globl cp1255_comp_table
	.set cp1255_comp_table, __f_rodata_base + 0xaa48
	.globl cp1255_decomp_table
	.set cp1255_decomp_table, __f_rodata_base + 0xaa88
	.globl cp1255_comb_table
	.set cp1255_comb_table, __f_rodata_base + 0xab98
	.globl cp1255_2uni
	.set cp1255_2uni, __f_rodata_base + 0xaba0
	.globl cp1255_page00
	.set cp1255_page00, __f_rodata_base + 0xaca0
	.globl cp1255_page02
	.set cp1255_page02, __f_rodata_base + 0xacf8
	.globl cp1255_page05
	.set cp1255_page05, __f_rodata_base + 0xad18
	.globl cp1255_page20
	.set cp1255_page20, __f_rodata_base + 0xad60
	.globl cp1256_2uni
	.set cp1256_2uni, __f_rodata_base + 0xad98
	.globl cp1256_page00
	.set cp1256_page00, __f_rodata_base + 0xae98
	.globl cp1256_page01
	.set cp1256_page01, __f_rodata_base + 0xaef8
	.globl cp1256_page06
	.set cp1256_page06, __f_rodata_base + 0xaf40
	.globl cp1256_page20
	.set cp1256_page20, __f_rodata_base + 0xb010
	.globl cp1257_2uni
	.set cp1257_2uni, __f_rodata_base + 0xb048
	.globl cp1257_page00
	.set cp1257_page00, __f_rodata_base + 0xb148
	.globl cp1257_page02
	.set cp1257_page02, __f_rodata_base + 0xb228
	.globl cp1257_page20
	.set cp1257_page20, __f_rodata_base + 0xb248
	.globl viet_comp_table_data
	.set viet_comp_table_data, __f_rodata_base + 0xb278
	.globl viet_comp_table
	.set viet_comp_table, __f_rodata_base + 0xb5a0
	.globl viet_decomp_table
	.set viet_decomp_table, __f_rodata_base + 0xb5c8
	.globl cp1258_comb_table
	.set cp1258_comb_table, __f_rodata_base + 0xb8ec
	.globl cp1258_comp_bases
	.set cp1258_comp_bases, __f_rodata_base + 0xb8f4
	.globl cp1258_2uni
	.set cp1258_2uni, __f_rodata_base + 0xb924
	.globl cp1258_page00
	.set cp1258_page00, __f_rodata_base + 0xba24
	.globl cp1258_page01
	.set cp1258_page01, __f_rodata_base + 0xba7c
	.globl cp1258_page02
	.set cp1258_page02, __f_rodata_base + 0xbae4
	.globl cp1258_page03
	.set cp1258_page03, __f_rodata_base + 0xbb04
	.globl cp1258_page20
	.set cp1258_page20, __f_rodata_base + 0xbb2c
	.globl cp850_2uni
	.set cp850_2uni, __f_rodata_base + 0xbb5c
	.globl cp850_page00
	.set cp850_page00, __f_rodata_base + 0xbc5c
	.globl cp850_page25
	.set cp850_page25, __f_rodata_base + 0xbcbc
	.globl cp862_2uni
	.set cp862_2uni, __f_rodata_base + 0xbd64
	.globl cp862_page00
	.set cp862_page00, __f_rodata_base + 0xbe64
	.globl cp862_page03
	.set cp862_page03, __f_rodata_base + 0xbec4
	.globl cp862_page22
	.set cp862_page22, __f_rodata_base + 0xbefc
	.globl cp862_page25
	.set cp862_page25, __f_rodata_base + 0xbf4c
	.globl cp866_2uni
	.set cp866_2uni, __f_rodata_base + 0xbff4
	.globl cp866_page00
	.set cp866_page00, __f_rodata_base + 0xc094
	.globl cp866_page04
	.set cp866_page04, __f_rodata_base + 0xc0ac
	.globl cp866_page22
	.set cp866_page22, __f_rodata_base + 0xc10c
	.globl cp866_page25
	.set cp866_page25, __f_rodata_base + 0xc114
	.globl cp1131_2uni
	.set cp1131_2uni, __f_rodata_base + 0xc1bc
	.globl cp1131_page00
	.set cp1131_page00, __f_rodata_base + 0xc2bc
	.globl cp1131_page04
	.set cp1131_page04, __f_rodata_base + 0xc2d4
	.globl cp1131_page25
	.set cp1131_page25, __f_rodata_base + 0xc36c
	.globl mac_roman_2uni
	.set mac_roman_2uni, __f_rodata_base + 0xc404
	.globl mac_roman_page00
	.set mac_roman_page00, __f_rodata_base + 0xc504
	.globl mac_roman_page01
	.set mac_roman_page01, __f_rodata_base + 0xc564
	.globl mac_roman_page02
	.set mac_roman_page02, __f_rodata_base + 0xc5cc
	.globl mac_roman_page20
	.set mac_roman_page20, __f_rodata_base + 0xc5ec
	.globl mac_roman_page21
	.set mac_roman_page21, __f_rodata_base + 0xc624
	.globl mac_roman_page22
	.set mac_roman_page22, __f_rodata_base + 0xc62c
	.globl mac_roman_pagefb
	.set mac_roman_pagefb, __f_rodata_base + 0xc694
	.globl mac_centraleurope_2uni
	.set mac_centraleurope_2uni, __f_rodata_base + 0xc69c
	.globl mac_centraleurope_page00
	.set mac_centraleurope_page00, __f_rodata_base + 0xc79c
	.globl mac_centraleurope_page20
	.set mac_centraleurope_page20, __f_rodata_base + 0xc87c
	.globl mac_centraleurope_page22
	.set mac_centraleurope_page22, __f_rodata_base + 0xc8ac
	.globl mac_centraleurope_page22_1
	.set mac_centraleurope_page22_1, __f_rodata_base + 0xc8cc
	.globl mac_iceland_2uni
	.set mac_iceland_2uni, __f_rodata_base + 0xc8d4
	.globl mac_iceland_page00
	.set mac_iceland_page00, __f_rodata_base + 0xc9d4
	.globl mac_iceland_page01
	.set mac_iceland_page01, __f_rodata_base + 0xca34
	.globl mac_iceland_page02
	.set mac_iceland_page02, __f_rodata_base + 0xca9c
	.globl mac_iceland_page20
	.set mac_iceland_page20, __f_rodata_base + 0xcabc
	.globl mac_iceland_page21
	.set mac_iceland_page21, __f_rodata_base + 0xcaf4
	.globl mac_iceland_page22
	.set mac_iceland_page22, __f_rodata_base + 0xcafc
	.globl mac_croatian_2uni
	.set mac_croatian_2uni, __f_rodata_base + 0xcb64
	.globl mac_croatian_page00
	.set mac_croatian_page00, __f_rodata_base + 0xcc64
	.globl mac_croatian_page02
	.set mac_croatian_page02, __f_rodata_base + 0xcd5c
	.globl mac_croatian_page20
	.set mac_croatian_page20, __f_rodata_base + 0xcd7c
	.globl mac_croatian_page21
	.set mac_croatian_page21, __f_rodata_base + 0xcdb4
	.globl mac_croatian_page22
	.set mac_croatian_page22, __f_rodata_base + 0xcdbc
	.globl mac_romania_2uni
	.set mac_romania_2uni, __f_rodata_base + 0xce24
	.globl mac_romania_page00
	.set mac_romania_page00, __f_rodata_base + 0xcf24
	.globl mac_romania_page02
	.set mac_romania_page02, __f_rodata_base + 0xd01c
	.globl mac_romania_page20
	.set mac_romania_page20, __f_rodata_base + 0xd03c
	.globl mac_romania_page21
	.set mac_romania_page21, __f_rodata_base + 0xd074
	.globl mac_romania_page22
	.set mac_romania_page22, __f_rodata_base + 0xd07c
	.globl mac_cyrillic_2uni
	.set mac_cyrillic_2uni, __f_rodata_base + 0xd0e4
	.globl mac_cyrillic_page00
	.set mac_cyrillic_page00, __f_rodata_base + 0xd1e4
	.globl mac_cyrillic_page04
	.set mac_cyrillic_page04, __f_rodata_base + 0xd204
	.globl mac_cyrillic_page20
	.set mac_cyrillic_page20, __f_rodata_base + 0xd264
	.globl mac_cyrillic_page21
	.set mac_cyrillic_page21, __f_rodata_base + 0xd27c
	.globl mac_cyrillic_page22
	.set mac_cyrillic_page22, __f_rodata_base + 0xd294
	.globl mac_ukraine_2uni
	.set mac_ukraine_2uni, __f_rodata_base + 0xd2fc
	.globl mac_ukraine_page00
	.set mac_ukraine_page00, __f_rodata_base + 0xd3fc
	.globl mac_ukraine_page04
	.set mac_ukraine_page04, __f_rodata_base + 0xd41c
	.globl mac_ukraine_page20
	.set mac_ukraine_page20, __f_rodata_base + 0xd4b4
	.globl mac_ukraine_page21
	.set mac_ukraine_page21, __f_rodata_base + 0xd4cc
	.globl mac_ukraine_page22
	.set mac_ukraine_page22, __f_rodata_base + 0xd4e4
	.globl mac_greek_2uni
	.set mac_greek_2uni, __f_rodata_base + 0xd54c
	.globl mac_greek_page00
	.set mac_greek_page00, __f_rodata_base + 0xd64c
	.globl mac_greek_page03
	.set mac_greek_page03, __f_rodata_base + 0xd6ac
	.globl mac_greek_page20
	.set mac_greek_page20, __f_rodata_base + 0xd6fc
	.globl mac_greek_page22
	.set mac_greek_page22, __f_rodata_base + 0xd724
	.globl mac_turkish_2uni
	.set mac_turkish_2uni, __f_rodata_base + 0xd744
	.globl mac_turkish_page00
	.set mac_turkish_page00, __f_rodata_base + 0xd844
	.globl mac_turkish_page01
	.set mac_turkish_page01, __f_rodata_base + 0xd8a4
	.globl mac_turkish_page02
	.set mac_turkish_page02, __f_rodata_base + 0xd924
	.globl mac_turkish_page20
	.set mac_turkish_page20, __f_rodata_base + 0xd944
	.globl mac_turkish_page21
	.set mac_turkish_page21, __f_rodata_base + 0xd96c
	.globl mac_turkish_page22
	.set mac_turkish_page22, __f_rodata_base + 0xd974
	.globl mac_hebrew_2uni
	.set mac_hebrew_2uni, __f_rodata_base + 0xd9dc
	.globl mac_hebrew_page00
	.set mac_hebrew_page00, __f_rodata_base + 0xdadc
	.globl mac_hebrew_page05
	.set mac_hebrew_page05, __f_rodata_base + 0xdb3c
	.globl mac_hebrew_page20
	.set mac_hebrew_page20, __f_rodata_base + 0xdb7c
	.globl mac_hebrew_pagefb
	.set mac_hebrew_pagefb, __f_rodata_base + 0xdb94
	.globl mac_arabic_2uni
	.set mac_arabic_2uni, __f_rodata_base + 0xdbcc
	.globl mac_arabic_page00
	.set mac_arabic_page00, __f_rodata_base + 0xdccc
	.globl mac_arabic_page06
	.set mac_arabic_page06, __f_rodata_base + 0xdd2c
	.globl mac_thai_2uni
	.set mac_thai_2uni, __f_rodata_base + 0xddfc
	.globl mac_thai_page00
	.set mac_thai_page00, __f_rodata_base + 0xdefc
	.globl mac_thai_page0e
	.set mac_thai_page0e, __f_rodata_base + 0xdf1c
	.globl mac_thai_page20
	.set mac_thai_page20, __f_rodata_base + 0xdf7c
	.globl mac_thai_pagef8
	.set mac_thai_pagef8, __f_rodata_base + 0xdf9c
	.globl hp_roman8_2uni
	.set hp_roman8_2uni, __f_rodata_base + 0xdfbc
	.globl hp_roman8_page00
	.set hp_roman8_page00, __f_rodata_base + 0xe07c
	.globl hp_roman8_page01
	.set hp_roman8_page01, __f_rodata_base + 0xe0dc
	.globl hp_roman8_page02
	.set hp_roman8_page02, __f_rodata_base + 0xe114
	.globl nextstep_2uni
	.set nextstep_2uni, __f_rodata_base + 0xe134
	.globl nextstep_page00
	.set nextstep_page00, __f_rodata_base + 0xe234
	.globl nextstep_page01
	.set nextstep_page01, __f_rodata_base + 0xe294
	.globl nextstep_page02
	.set nextstep_page02, __f_rodata_base + 0xe2fc
	.globl nextstep_page20
	.set nextstep_page20, __f_rodata_base + 0xe31c
	.globl nextstep_pagefb
	.set nextstep_pagefb, __f_rodata_base + 0xe354
	.globl armscii_8_2uni
	.set armscii_8_2uni, __f_rodata_base + 0xe35c
	.globl armscii_8_page00
	.set armscii_8_page00, __f_rodata_base + 0xe41c
	.globl armscii_8_page00_1
	.set armscii_8_page00_1, __f_rodata_base + 0xe424
	.globl armscii_8_page05
	.set armscii_8_page05, __f_rodata_base + 0xe444
	.globl armscii_8_page20
	.set armscii_8_page20, __f_rodata_base + 0xe4a4
	.globl georgian_academy_2uni
	.set georgian_academy_2uni, __f_rodata_base + 0xe4bc
	.globl georgian_academy_page00
	.set georgian_academy_page00, __f_rodata_base + 0xe4fc
	.globl georgian_academy_page01
	.set georgian_academy_page01, __f_rodata_base + 0xe51c
	.globl georgian_academy_page02
	.set georgian_academy_page02, __f_rodata_base + 0xe564
	.globl georgian_academy_page20
	.set georgian_academy_page20, __f_rodata_base + 0xe584
	.globl georgian_ps_2uni_1
	.set georgian_ps_2uni_1, __f_rodata_base + 0xe5b4
	.globl georgian_ps_2uni_2
	.set georgian_ps_2uni_2, __f_rodata_base + 0xe5f4
	.globl georgian_ps_page00
	.set georgian_ps_page00, __f_rodata_base + 0xe644
	.globl georgian_ps_page01
	.set georgian_ps_page01, __f_rodata_base + 0xe664
	.globl georgian_ps_page02
	.set georgian_ps_page02, __f_rodata_base + 0xe6ac
	.globl georgian_ps_page10
	.set georgian_ps_page10, __f_rodata_base + 0xe6cc
	.globl georgian_ps_page20
	.set georgian_ps_page20, __f_rodata_base + 0xe6f4
	.globl koi8_t_2uni
	.set koi8_t_2uni, __f_rodata_base + 0xe724
	.globl koi8_t_page00
	.set koi8_t_page00, __f_rodata_base + 0xe824
	.globl koi8_t_page04
	.set koi8_t_page04, __f_rodata_base + 0xe844
	.globl koi8_t_page20
	.set koi8_t_page20, __f_rodata_base + 0xe934
	.globl koi8_t_page21
	.set koi8_t_page21, __f_rodata_base + 0xe964
	.globl pt154_2uni
	.set pt154_2uni, __f_rodata_base + 0xe97c
	.globl pt154_page00
	.set pt154_page00, __f_rodata_base + 0xe9fc
	.globl pt154_page04
	.set pt154_page04, __f_rodata_base + 0xea1c
	.globl pt154_page20
	.set pt154_page20, __f_rodata_base + 0xeb0c
	.globl rk1048_2uni
	.set rk1048_2uni, __f_rodata_base + 0xeb24
	.globl rk1048_page00
	.set rk1048_page00, __f_rodata_base + 0xec24
	.globl rk1048_page04
	.set rk1048_page04, __f_rodata_base + 0xec44
	.globl rk1048_page20
	.set rk1048_page20, __f_rodata_base + 0xed34
	.globl rk1048_page21
	.set rk1048_page21, __f_rodata_base + 0xed64
	.globl mulelao_2uni
	.set mulelao_2uni, __f_rodata_base + 0xed7c
	.globl mulelao_page0e
	.set mulelao_page0e, __f_rodata_base + 0xee3c
	.globl cp1133_2uni_1
	.set cp1133_2uni_1, __f_rodata_base + 0xee9c
	.globl cp1133_2uni_2
	.set cp1133_2uni_2, __f_rodata_base + 0xef1c
	.globl cp1133_page00
	.set cp1133_page00, __f_rodata_base + 0xef3c
	.globl cp1133_page0e
	.set cp1133_page0e, __f_rodata_base + 0xef4c
	.globl cp874_2uni
	.set cp874_2uni, __f_rodata_base + 0xefac
	.globl cp874_page0e
	.set cp874_page0e, __f_rodata_base + 0xf0ac
	.globl cp874_page20
	.set cp874_page20, __f_rodata_base + 0xf10c
	.globl viscii_2uni_1
	.set viscii_2uni_1, __f_rodata_base + 0xf124
	.globl viscii_2uni_2
	.set viscii_2uni_2, __f_rodata_base + 0xf164
	.globl viscii_page00
	.set viscii_page00, __f_rodata_base + 0xf264
	.globl viscii_page1e
	.set viscii_page1e, __f_rodata_base + 0xf35c
	.globl tcvn_comb_table
	.set tcvn_comb_table, __f_rodata_base + 0xf3bc
	.globl tcvn_comp_bases
	.set tcvn_comp_bases, __f_rodata_base + 0xf3c4
	.globl tcvn_2uni_1
	.set tcvn_2uni_1, __f_rodata_base + 0xf3f4
	.globl tcvn_2uni_2
	.set tcvn_2uni_2, __f_rodata_base + 0xf424
	.globl tcvn_page00
	.set tcvn_page00, __f_rodata_base + 0xf524
	.globl tcvn_page03
	.set tcvn_page03, __f_rodata_base + 0xf63c
	.globl tcvn_page1e
	.set tcvn_page1e, __f_rodata_base + 0xf664
	.globl jisx0208_2uni_page21
	.set jisx0208_2uni_page21, __f_rodata_base + 0xf6c4
	.globl jisx0208_2uni_page30
	.set jisx0208_2uni_page30, __f_rodata_base + 0xfc28
	.globl jisx0208_2charset
	.set jisx0208_2charset, __f_rodata_base + 0x12e24
	.globl jisx0208_uni2indx_page00
	.set jisx0208_uni2indx_page00, __f_rodata_base + 0x163e4
	.globl jisx0208_uni2indx_page03
	.set jisx0208_uni2indx_page03, __f_rodata_base + 0x16424
	.globl jisx0208_uni2indx_page20
	.set jisx0208_uni2indx_page20, __f_rodata_base + 0x1647c
	.globl jisx0208_uni2indx_page25
	.set jisx0208_uni2indx_page25, __f_rodata_base + 0x16544
	.globl jisx0208_uni2indx_page30
	.set jisx0208_uni2indx_page30, __f_rodata_base + 0x165a0
	.globl jisx0208_uni2indx_page4e
	.set jisx0208_uni2indx_page4e, __f_rodata_base + 0x165e0
	.globl jisx0208_uni2indx_pageff
	.set jisx0208_uni2indx_pageff, __f_rodata_base + 0x17a4c
	.globl jisx0212_2uni_page22
	.set jisx0212_2uni_page22, __f_rodata_base + 0x17a88
	.globl jisx0212_2uni_page26
	.set jisx0212_2uni_page26, __f_rodata_base + 0x17b2c
	.globl jisx0212_2uni_page29
	.set jisx0212_2uni_page29, __f_rodata_base + 0x17ca4
	.globl jisx0212_2uni_page30
	.set jisx0212_2uni_page30, __f_rodata_base + 0x17ecc
	.globl jisx0212_2charset
	.set jisx0212_2charset, __f_rodata_base + 0x1ac20
	.globl jisx0212_uni2indx_page00
	.set jisx0212_uni2indx_page00, __f_rodata_base + 0x1db88
	.globl jisx0212_uni2indx_page21
	.set jisx0212_uni2indx_page21, __f_rodata_base + 0x1dca0
	.globl jisx0212_uni2indx_page4e
	.set jisx0212_uni2indx_page4e, __f_rodata_base + 0x1dcac
	.globl jisx0212_uni2indx_pageff
	.set jisx0212_uni2indx_pageff, __f_rodata_base + 0x1f118
	.globl gb2312_2uni_page21
	.set gb2312_2uni_page21, __f_rodata_base + 0x1f130
	.globl gb2312_2uni_page30
	.set gb2312_2uni_page30, __f_rodata_base + 0x1f7b0
	.globl gb2312_2charset
	.set gb2312_2charset, __f_rodata_base + 0x22c90
	.globl gb2312_uni2indx_page00
	.set gb2312_uni2indx_page00, __f_rodata_base + 0x266bc
	.globl gb2312_uni2indx_page20
	.set gb2312_uni2indx_page20, __f_rodata_base + 0x267d4
	.globl gb2312_uni2indx_page30
	.set gb2312_uni2indx_page30, __f_rodata_base + 0x26968
	.globl gb2312_uni2indx_page4e
	.set gb2312_uni2indx_page4e, __f_rodata_base + 0x269f4
	.globl gb2312_uni2indx_page9e
	.set gb2312_uni2indx_page9e, __f_rodata_base + 0x27db0
	.globl gb2312_uni2indx_pageff
	.set gb2312_uni2indx_pageff, __f_rodata_base + 0x27e1c
	.globl isoir165ext_2uni_page2b
	.set isoir165ext_2uni_page2b, __f_rodata_base + 0x27e58
	.globl isoir165ext_2uni_page7a
	.set isoir165ext_2uni_page7a, __f_rodata_base + 0x28204
	.globl isoir165ext_2charset
	.set isoir165ext_2charset, __f_rodata_base + 0x285b0
	.globl isoir165ext_uni2indx_page00
	.set isoir165ext_uni2indx_page00, __f_rodata_base + 0x28c88
	.globl isoir165ext_uni2indx_page03
	.set isoir165ext_uni2indx_page03, __f_rodata_base + 0x28d08
	.globl isoir165ext_uni2indx_page1e
	.set isoir165ext_uni2indx_page1e, __f_rodata_base + 0x28d38
	.globl isoir165ext_uni2indx_page30
	.set isoir165ext_uni2indx_page30, __f_rodata_base + 0x28da8
	.globl isoir165ext_uni2indx_page32
	.set isoir165ext_uni2indx_page32, __f_rodata_base + 0x28db8
	.globl isoir165ext_uni2indx_page4e
	.set isoir165ext_uni2indx_page4e, __f_rodata_base + 0x28e38
	.globl isoir165ext_uni2indx_page7e
	.set isoir165ext_uni2indx_page7e, __f_rodata_base + 0x299f8
	.globl isoir165ext_uni2indx_page94
	.set isoir165ext_uni2indx_page94, __f_rodata_base + 0x29f2c
	.globl isoir165ext_uni2indx_page9e
	.set isoir165ext_uni2indx_page9e, __f_rodata_base + 0x2a168
	.globl isoir165ext_uni2indx_pageff
	.set isoir165ext_uni2indx_pageff, __f_rodata_base + 0x2a1cc
	.globl gbkext1_2uni_page81
	.set gbkext1_2uni_page81, __f_rodata_base + 0x2a1e0
	.globl gbkext2_2uni_pagea8
	.set gbkext2_2uni_pagea8, __f_rodata_base + 0x2d160
	.globl gbkext_inv_2charset
	.set gbkext_inv_2charset, __f_rodata_base + 0x31200
	.globl gbkext_inv_uni2indx_page02
	.set gbkext_inv_uni2indx_page02, __f_rodata_base + 0x381d4
	.globl gbkext_inv_uni2indx_page20
	.set gbkext_inv_uni2indx_page20, __f_rodata_base + 0x3820c
	.globl gbkext_inv_uni2indx_page25
	.set gbkext_inv_uni2indx_page25, __f_rodata_base + 0x382bc
	.globl gbkext_inv_uni2indx_page30
	.set gbkext_inv_uni2indx_page30, __f_rodata_base + 0x38300
	.globl gbkext_inv_uni2indx_page32
	.set gbkext_inv_uni2indx_page32, __f_rodata_base + 0x38340
	.globl gbkext_inv_uni2indx_page4e
	.set gbkext_inv_uni2indx_page4e, __f_rodata_base + 0x383b8
	.globl gbkext_inv_uni2indx_pagef9
	.set gbkext_inv_uni2indx_pagef9, __f_rodata_base + 0x39824
	.globl gbkext_inv_uni2indx_pagefe
	.set gbkext_inv_uni2indx_pagefe, __f_rodata_base + 0x39870
	.globl cp936ext_2uni_pagea6
	.set cp936ext_2uni_pagea6, __f_rodata_base + 0x398ec
	.globl cp936ext_2uni_pagea8
	.set cp936ext_2uni_pagea8, __f_rodata_base + 0x39918
	.globl cp936ext_page01
	.set cp936ext_page01, __f_rodata_base + 0x39924
	.globl cp936ext_page02
	.set cp936ext_page02, __f_rodata_base + 0x39944
	.globl cp936ext_pagefe
	.set cp936ext_pagefe, __f_rodata_base + 0x39974
	.globl cns11643_1_2uni_page21
	.set cns11643_1_2uni_page21, __f_rodata_base + 0x399a4
	.globl cns11643_1_2uni_page42
	.set cns11643_1_2uni_page42, __f_rodata_base + 0x39d8c
	.globl cns11643_1_2uni_page44
	.set cns11643_1_2uni_page44, __f_rodata_base + 0x39dd0
	.globl cns11643_2_2uni_page21
	.set cns11643_2_2uni_page21, __f_rodata_base + 0x3c804
	.globl cns11643_3_2uni_page21
	.set cns11643_3_2uni_page21, __f_rodata_base + 0x403c8
	.globl cns11643_3_2uni_page64
	.set cns11643_3_2uni_page64, __f_rodata_base + 0x433d0
	.globl cns11643_3_2uni_upages
	.set cns11643_3_2uni_upages, __f_rodata_base + 0x43618
	.globl cns11643_4a_2uni_page21
	.set cns11643_4a_2uni_page21, __f_rodata_base + 0x43838
	.globl cns11643_4a_2uni_upages
	.set cns11643_4a_2uni_upages, __f_rodata_base + 0x44efc
	.globl cns11643_4b_2uni_page40
	.set cns11643_4b_2uni_page40, __f_rodata_base + 0x4524c
	.globl cns11643_4b_2uni_upages
	.set cns11643_4b_2uni_upages, __f_rodata_base + 0x4748c
	.globl cns11643_5_2uni_page21
	.set cns11643_5_2uni_page21, __f_rodata_base + 0x4786c
	.globl cns11643_5_2uni_upages
	.set cns11643_5_2uni_upages, __f_rodata_base + 0x4bba4
	.globl cns11643_6_2uni_page21
	.set cns11643_6_2uni_page21, __f_rodata_base + 0x4bf38
	.globl cns11643_6_2uni_upages
	.set cns11643_6_2uni_upages, __f_rodata_base + 0x4f120
	.globl cns11643_7_2uni_page21
	.set cns11643_7_2uni_page21, __f_rodata_base + 0x4f450
	.globl cns11643_7_2uni_upages
	.set cns11643_7_2uni_upages, __f_rodata_base + 0x52768
	.globl cns11643_15_2uni_page21
	.set cns11643_15_2uni_page21, __f_rodata_base + 0x52a80
	.globl cns11643_15_2uni_upages
	.set cns11643_15_2uni_upages, __f_rodata_base + 0x56284
	.globl cns11643_inv_2charset
	.set cns11643_inv_2charset, __f_rodata_base + 0x56678
	.globl cns11643_inv_uni2indx_page00
	.set cns11643_inv_uni2indx_page00, __f_rodata_base + 0x7f030
	.globl cns11643_inv_uni2indx_page02
	.set cns11643_inv_uni2indx_page02, __f_rodata_base + 0x7f070
	.globl cns11643_inv_uni2indx_page20
	.set cns11643_inv_uni2indx_page20, __f_rodata_base + 0x7f0e4
	.globl cns11643_inv_uni2indx_page24
	.set cns11643_inv_uni2indx_page24, __f_rodata_base + 0x7f194
	.globl cns11643_inv_uni2indx_page30
	.set cns11643_inv_uni2indx_page30, __f_rodata_base + 0x7f228
	.globl cns11643_inv_uni2indx_pagefa
	.set cns11643_inv_uni2indx_pagefa, __f_rodata_base + 0x80e14
	.globl cns11643_inv_uni2indx_pagefe
	.set cns11643_inv_uni2indx_pagefe, __f_rodata_base + 0x80e20
	.globl cns11643_inv_uni2indx_page200
	.set cns11643_inv_uni2indx_page200, __f_rodata_base + 0x80e9c
	.globl cns11643_inv_uni2indx_page2f8
	.set cns11643_inv_uni2indx_page2f8, __f_rodata_base + 0x83854
	.globl big5_2uni_pagea1
	.set big5_2uni_pagea1, __f_rodata_base + 0x838dc
	.globl big5_2uni_pagec9
	.set big5_2uni_pagec9, __f_rodata_base + 0x868b0
	.globl big5_2charset
	.set big5_2charset, __f_rodata_base + 0x8a478
	.globl big5_uni2indx_page00
	.set big5_uni2indx_page00, __f_rodata_base + 0x90f88
	.globl big5_uni2indx_page02
	.set big5_uni2indx_page02, __f_rodata_base + 0x90fc8
	.globl big5_uni2indx_page20
	.set big5_uni2indx_page20, __f_rodata_base + 0x91060
	.globl big5_uni2indx_page24
	.set big5_uni2indx_page24, __f_rodata_base + 0x91110
	.globl big5_uni2indx_page30
	.set big5_uni2indx_page30, __f_rodata_base + 0x911a4
	.globl big5_uni2indx_page4e
	.set big5_uni2indx_page4e, __f_rodata_base + 0x9129c
	.globl big5_uni2indx_pagefa
	.set big5_uni2indx_pagefa, __f_rodata_base + 0x92708
	.globl big5_uni2indx_pagefe
	.set big5_uni2indx_pagefe, __f_rodata_base + 0x9270c
	.globl ksc5601_2uni_page21
	.set ksc5601_2uni_page21, __f_rodata_base + 0x92768
	.globl ksc5601_2uni_page30
	.set ksc5601_2uni_page30, __f_rodata_base + 0x93020
	.globl ksc5601_2uni_page4a
	.set ksc5601_2uni_page4a, __f_rodata_base + 0x9427c
	.globl ksc5601_2charset
	.set ksc5601_2charset, __f_rodata_base + 0x968ac
	.globl ksc5601_uni2indx_page00
	.set ksc5601_uni2indx_page00, __f_rodata_base + 0x9a8f4
	.globl ksc5601_uni2indx_page20
	.set ksc5601_uni2indx_page20, __f_rodata_base + 0x9aa0c
	.globl ksc5601_uni2indx_page30
	.set ksc5601_uni2indx_page30, __f_rodata_base + 0x9aba8
	.globl ksc5601_uni2indx_page4e
	.set ksc5601_uni2indx_page4e, __f_rodata_base + 0x9aca0
	.globl ksc5601_uni2indx_pageac
	.set ksc5601_uni2indx_pageac, __f_rodata_base + 0x9c108
	.globl ksc5601_uni2indx_pagef9
	.set ksc5601_uni2indx_pagef9, __f_rodata_base + 0x9cbf0
	.globl ksc5601_uni2indx_pageff
	.set ksc5601_uni2indx_pageff, __f_rodata_base + 0x9cc34
	.globl jamo_initial
	.set jamo_initial, __f_rodata_base + 0x9cc70
	.globl jamo_medial
	.set jamo_medial, __f_rodata_base + 0x9cc90
	.globl jamo_final
	.set jamo_final, __f_rodata_base + 0x9ccb0
	.globl jamo_final_notinitial
	.set jamo_final_notinitial, __f_rodata_base + 0x9ccd0
	.globl jamo_initial_index
	.set jamo_initial_index, __f_rodata_base + 0x9ccf0
	.globl jamo_medial_index
	.set jamo_medial_index, __f_rodata_base + 0x9cd10
	.globl jamo_final_index
	.set jamo_final_index, __f_rodata_base + 0x9cd30
	.globl johab_hangul_page31
	.set johab_hangul_page31, __f_rodata_base + 0x9cd50
	.globl jamo_initial_index_inverse
	.set jamo_initial_index_inverse, __f_rodata_base + 0x9cdb8
	.globl jamo_medial_index_inverse
	.set jamo_medial_index_inverse, __f_rodata_base + 0x9cdcc
	.globl jamo_final_index_inverse
	.set jamo_final_index_inverse, __f_rodata_base + 0x9cde4
	.globl cp932ext_2uni_page87
	.set cp932ext_2uni_page87, __f_rodata_base + 0x9ce00
	.globl cp932ext_2uni_pageed
	.set cp932ext_2uni_pageed, __f_rodata_base + 0x9ceb8
	.globl cp932ext_2uni_pagefa
	.set cp932ext_2uni_pagefa, __f_rodata_base + 0x9d1a8
	.globl cp932ext_2charset
	.set cp932ext_2charset, __f_rodata_base + 0x9d4b0
	.globl cp932ext_uni2indx_page21
	.set cp932ext_uni2indx_page21, __f_rodata_base + 0x9d844
	.globl cp932ext_uni2indx_page24
	.set cp932ext_uni2indx_page24, __f_rodata_base + 0x9d8b4
	.globl cp932ext_uni2indx_page30
	.set cp932ext_uni2indx_page30, __f_rodata_base + 0x9d8d4
	.globl cp932ext_uni2indx_page32
	.set cp932ext_uni2indx_page32, __f_rodata_base + 0x9d8dc
	.globl cp932ext_uni2indx_page4e
	.set cp932ext_uni2indx_page4e, __f_rodata_base + 0x9d950
	.globl cp932ext_uni2indx_page57
	.set cp932ext_uni2indx_page57, __f_rodata_base + 0x9db34
	.globl cp932ext_uni2indx_page5b
	.set cp932ext_uni2indx_page5b, __f_rodata_base + 0x9dbe4
	.globl cp932ext_uni2indx_page5f
	.set cp932ext_uni2indx_page5f, __f_rodata_base + 0x9dc9c
	.globl cp932ext_uni2indx_page7d
	.set cp932ext_uni2indx_page7d, __f_rodata_base + 0x9e3c4
	.globl cp932ext_uni2indx_page83
	.set cp932ext_uni2indx_page83, __f_rodata_base + 0x9e470
	.globl cp932ext_uni2indx_page88
	.set cp932ext_uni2indx_page88, __f_rodata_base + 0x9e520
	.globl cp932ext_uni2indx_page90
	.set cp932ext_uni2indx_page90, __f_rodata_base + 0x9e6d4
	.globl cp932ext_uni2indx_pagef9
	.set cp932ext_uni2indx_pagef9, __f_rodata_base + 0x9ea8c
	.globl cp932ext_uni2indx_pageff
	.set cp932ext_uni2indx_pageff, __f_rodata_base + 0x9ead8
	.globl cp50221_0208_ext_2uni
	.set cp50221_0208_ext_2uni, __f_rodata_base + 0x9eb14
	.globl cp50221_0208_ext_page21
	.set cp50221_0208_ext_page21, __f_rodata_base + 0x9ebd4
	.globl cp50221_0208_ext_page22
	.set cp50221_0208_ext_page22, __f_rodata_base + 0x9ec34
	.globl cp50221_0208_ext_page24
	.set cp50221_0208_ext_page24, __f_rodata_base + 0x9ec54
	.globl cp50221_0208_ext_page30
	.set cp50221_0208_ext_page30, __f_rodata_base + 0x9ec6c
	.globl cp50221_0208_ext_page32
	.set cp50221_0208_ext_page32, __f_rodata_base + 0x9ec74
	.globl cp50221_0208_ext_page32_1
	.set cp50221_0208_ext_page32_1, __f_rodata_base + 0x9ec84
	.globl cp50221_0208_ext_page33
	.set cp50221_0208_ext_page33, __f_rodata_base + 0x9ec94
	.globl cp50221_0212_ext_2uni
	.set cp50221_0212_ext_2uni, __f_rodata_base + 0x9ed64
	.globl cp50221_0212_ext_page21
	.set cp50221_0212_ext_page21, __f_rodata_base + 0x9ee44
	.globl cp50221_0212_ext_page53
	.set cp50221_0212_ext_page53, __f_rodata_base + 0x9ee54
	.globl cp50221_0212_ext_page6d
	.set cp50221_0212_ext_page6d, __f_rodata_base + 0x9ee7c
	.globl cp50221_0212_ext_page76
	.set cp50221_0212_ext_page76, __f_rodata_base + 0x9ee8c
	.globl cp50221_0212_ext_page7d
	.set cp50221_0212_ext_page7d, __f_rodata_base + 0x9eeac
	.globl cp50221_0212_ext_page97
	.set cp50221_0212_ext_page97, __f_rodata_base + 0x9eee4
	.globl cp50221_0212_ext_pagefa
	.set cp50221_0212_ext_pagefa, __f_rodata_base + 0x9ef04
	.globl cp50221_0212_ext_pageff
	.set cp50221_0212_ext_pageff, __f_rodata_base + 0x9ef2c
	.globl gb18030ext_2uni_pagea9
	.set gb18030ext_2uni_pagea9, __f_rodata_base + 0x9ef34
	.globl gb18030ext_2uni_pagefe
	.set gb18030ext_2uni_pagefe, __f_rodata_base + 0x9ef50
	.globl gb18030ext_page2e
	.set gb18030ext_page2e, __f_rodata_base + 0x9f0d0
	.globl gb18030ext_page2f
	.set gb18030ext_page2f, __f_rodata_base + 0x9f170
	.globl gb18030ext_page34
	.set gb18030ext_page34, __f_rodata_base + 0x9f190
	.globl gb18030ext_page36
	.set gb18030ext_page36, __f_rodata_base + 0x9f200
	.globl gb18030ext_page39
	.set gb18030ext_page39, __f_rodata_base + 0x9f230
	.globl gb18030ext_page43
	.set gb18030ext_page43, __f_rodata_base + 0x9f260
	.globl gb18030ext_page46
	.set gb18030ext_page46, __f_rodata_base + 0x9f2d0
	.globl gb18030ext_page47_1
	.set gb18030ext_page47_1, __f_rodata_base + 0x9f310
	.globl gb18030ext_page47_2
	.set gb18030ext_page47_2, __f_rodata_base + 0x9f330
	.globl gb18030ext_page49
	.set gb18030ext_page49, __f_rodata_base + 0x9f360
	.globl gb18030ext_page4c
	.set gb18030ext_page4c, __f_rodata_base + 0x9f450
	.globl gb18030ext_page4d
	.set gb18030ext_page4d, __f_rodata_base + 0x9f4c0
	.globl gb18030ext_page9f
	.set gb18030ext_page9f, __f_rodata_base + 0x9f4e0
	.globl gb18030ext_pagefe
	.set gb18030ext_pagefe, __f_rodata_base + 0x9f500
	.globl gb18030uni_charset2uni_ranges
	.set gb18030uni_charset2uni_ranges, __f_rodata_base + 0x9f520
	.globl gb18030uni_uni2charset_ranges
	.set gb18030uni_uni2charset_ranges, __f_rodata_base + 0x9f858
	.globl gb18030uni_ranges
	.set gb18030uni_ranges, __f_rodata_base + 0x9fb90
	.globl gb18030_pua2charset
	.set gb18030_pua2charset, __f_rodata_base + 0x9fd2c
	.globl cp950_2uni_pagea1
	.set cp950_2uni_pagea1, __f_rodata_base + 0x9fde8
	.globl cp950ext_2uni_pagef9
	.set cp950ext_2uni_pagef9, __f_rodata_base + 0xa005c
	.globl cp950ext_2charset
	.set cp950ext_2charset, __f_rodata_base + 0xa00b0
	.globl cp950ext_uni2indx_page25
	.set cp950ext_uni2indx_page25, __f_rodata_base + 0xa0104
	.globl cp950ext_uni2indx_page58
	.set cp950ext_uni2indx_page58, __f_rodata_base + 0xa012c
	.globl cp950ext_uni2indx_page5a
	.set cp950ext_uni2indx_page5a, __f_rodata_base + 0xa015c
	.globl cp950ext_uni2indx_page60
	.set cp950ext_uni2indx_page60, __f_rodata_base + 0xa019c
	.globl cp950ext_uni2indx_page78
	.set cp950ext_uni2indx_page78, __f_rodata_base + 0xa01b4
	.globl cp950ext_uni2indx_page7c
	.set cp950ext_uni2indx_page7c, __f_rodata_base + 0xa01d8
	.globl cp950ext_uni2indx_page88
	.set cp950ext_uni2indx_page88, __f_rodata_base + 0xa0204
	.globl cp950ext_uni2indx_page92
	.set cp950ext_uni2indx_page92, __f_rodata_base + 0xa0238
	.globl hkscs1999_2uni_page88
	.set hkscs1999_2uni_page88, __f_rodata_base + 0xa0268
	.globl hkscs1999_2uni_page8d
	.set hkscs1999_2uni_page8d, __f_rodata_base + 0xa0750
	.globl hkscs1999_2uni_pagec6
	.set hkscs1999_2uni_pagec6, __f_rodata_base + 0xa1fd8
	.globl hkscs1999_2uni_pagef9
	.set hkscs1999_2uni_pagef9, __f_rodata_base + 0xa2388
	.globl hkscs1999_2uni_upages
	.set hkscs1999_2uni_upages, __f_rodata_base + 0xa2ae4
	.globl hkscs1999_2charset
	.set hkscs1999_2charset, __f_rodata_base + 0xa3a18
	.globl hkscs1999_uni2indx_page00
	.set hkscs1999_uni2indx_page00, __f_rodata_base + 0xa5ecc
	.globl hkscs1999_uni2indx_page04
	.set hkscs1999_uni2indx_page04, __f_rodata_base + 0xa5f80
	.globl hkscs1999_uni2indx_page1e
	.set hkscs1999_uni2indx_page1e, __f_rodata_base + 0xa5f98
	.globl hkscs1999_uni2indx_page21
	.set hkscs1999_uni2indx_page21, __f_rodata_base + 0xa5fcc
	.globl hkscs1999_uni2indx_page23
	.set hkscs1999_uni2indx_page23, __f_rodata_base + 0xa6008
	.globl hkscs1999_uni2indx_page27
	.set hkscs1999_uni2indx_page27, __f_rodata_base + 0xa60a8
	.globl hkscs1999_uni2indx_page2e
	.set hkscs1999_uni2indx_page2e, __f_rodata_base + 0xa60b8
	.globl hkscs1999_uni2indx_page34
	.set hkscs1999_uni2indx_page34, __f_rodata_base + 0xa61c8
	.globl hkscs1999_uni2indx_pagef9
	.set hkscs1999_uni2indx_pagef9, __f_rodata_base + 0xa7cb8
	.globl hkscs1999_uni2indx_pageff
	.set hkscs1999_uni2indx_pageff, __f_rodata_base + 0xa7cbc
	.globl hkscs1999_uni2indx_page200
	.set hkscs1999_uni2indx_page200, __f_rodata_base + 0xa7cf8
	.globl hkscs1999_uni2indx_page294
	.set hkscs1999_uni2indx_page294, __f_rodata_base + 0xaa174
	.globl hkscs1999_uni2indx_page297
	.set hkscs1999_uni2indx_page297, __f_rodata_base + 0xaa1f4
	.globl hkscs1999_uni2indx_page2f8
	.set hkscs1999_uni2indx_page2f8, __f_rodata_base + 0xaa5e0
	.globl hkscs2001_2uni_page8c
	.set hkscs2001_2uni_page8c, __f_rodata_base + 0xaa658
	.globl hkscs2001_2uni_upages
	.set hkscs2001_2uni_upages, __f_rodata_base + 0xaa750
	.globl hkscs2001_2charset
	.set hkscs2001_2charset, __f_rodata_base + 0xaa8a4
	.globl hkscs2001_uni2indx_page35
	.set hkscs2001_uni2indx_page35, __f_rodata_base + 0xaa98c
	.globl hkscs2001_uni2indx_page3c
	.set hkscs2001_uni2indx_page3c, __f_rodata_base + 0xaa9a4
	.globl hkscs2001_uni2indx_page40
	.set hkscs2001_uni2indx_page40, __f_rodata_base + 0xaaa5c
	.globl hkscs2001_uni2indx_page42
	.set hkscs2001_uni2indx_page42, __f_rodata_base + 0xaaa7c
	.globl hkscs2001_uni2indx_page4b
	.set hkscs2001_uni2indx_page4b, __f_rodata_base + 0xaaaa8
	.globl hkscs2001_uni2indx_page4e
	.set hkscs2001_uni2indx_page4e, __f_rodata_base + 0xaab0c
	.globl hkscs2001_uni2indx_page53
	.set hkscs2001_uni2indx_page53, __f_rodata_base + 0xaabf8
	.globl hkscs2001_uni2indx_page57
	.set hkscs2001_uni2indx_page57, __f_rodata_base + 0xaac48
	.globl hkscs2001_uni2indx_page5a
	.set hkscs2001_uni2indx_page5a, __f_rodata_base + 0xaacc0
	.globl hkscs2001_uni2indx_page61
	.set hkscs2001_uni2indx_page61, __f_rodata_base + 0xaae34
	.globl hkscs2001_uni2indx_page65
	.set hkscs2001_uni2indx_page65, __f_rodata_base + 0xaae40
	.globl hkscs2001_uni2indx_page67
	.set hkscs2001_uni2indx_page67, __f_rodata_base + 0xaae64
	.globl hkscs2001_uni2indx_page69
	.set hkscs2001_uni2indx_page69, __f_rodata_base + 0xaae80
	.globl hkscs2001_uni2indx_page6c
	.set hkscs2001_uni2indx_page6c, __f_rodata_base + 0xaaedc
	.globl hkscs2001_uni2indx_page70
	.set hkscs2001_uni2indx_page70, __f_rodata_base + 0xaaf5c
	.globl hkscs2001_uni2indx_page76
	.set hkscs2001_uni2indx_page76, __f_rodata_base + 0xab08c
	.globl hkscs2001_uni2indx_page7a
	.set hkscs2001_uni2indx_page7a, __f_rodata_base + 0xab148
	.globl hkscs2001_uni2indx_page82
	.set hkscs2001_uni2indx_page82, __f_rodata_base + 0xab264
	.globl hkscs2001_uni2indx_page85
	.set hkscs2001_uni2indx_page85, __f_rodata_base + 0xab2a4
	.globl hkscs2001_uni2indx_page88
	.set hkscs2001_uni2indx_page88, __f_rodata_base + 0xab2e8
	.globl hkscs2001_uni2indx_page8b
	.set hkscs2001_uni2indx_page8b, __f_rodata_base + 0xab310
	.globl hkscs2001_uni2indx_page8e
	.set hkscs2001_uni2indx_page8e, __f_rodata_base + 0xab334
	.globl hkscs2001_uni2indx_page91
	.set hkscs2001_uni2indx_page91, __f_rodata_base + 0xab3a8
	.globl hkscs2001_uni2indx_page97
	.set hkscs2001_uni2indx_page97, __f_rodata_base + 0xab468
	.globl hkscs2001_uni2indx_page9f
	.set hkscs2001_uni2indx_page9f, __f_rodata_base + 0xab524
	.globl hkscs2001_uni2indx_page214
	.set hkscs2001_uni2indx_page214, __f_rodata_base + 0xab550
	.globl hkscs2001_uni2indx_page219
	.set hkscs2001_uni2indx_page219, __f_rodata_base + 0xab560
	.globl hkscs2001_uni2indx_page21d
	.set hkscs2001_uni2indx_page21d, __f_rodata_base + 0xab584
	.globl hkscs2001_uni2indx_page220
	.set hkscs2001_uni2indx_page220, __f_rodata_base + 0xab5b4
	.globl hkscs2001_uni2indx_page227
	.set hkscs2001_uni2indx_page227, __f_rodata_base + 0xab5d4
	.globl hkscs2001_uni2indx_page232
	.set hkscs2001_uni2indx_page232, __f_rodata_base + 0xab5dc
	.globl hkscs2001_uni2indx_page23c
	.set hkscs2001_uni2indx_page23c, __f_rodata_base + 0xab65c
	.globl hkscs2001_uni2indx_page241
	.set hkscs2001_uni2indx_page241, __f_rodata_base + 0xab678
	.globl hkscs2001_uni2indx_page245
	.set hkscs2001_uni2indx_page245, __f_rodata_base + 0xab68c
	.globl hkscs2001_uni2indx_page249
	.set hkscs2001_uni2indx_page249, __f_rodata_base + 0xab690
	.globl hkscs2001_uni2indx_page251
	.set hkscs2001_uni2indx_page251, __f_rodata_base + 0xab6d8
	.globl hkscs2001_uni2indx_page256
	.set hkscs2001_uni2indx_page256, __f_rodata_base + 0xab70c
	.globl hkscs2001_uni2indx_page25c
	.set hkscs2001_uni2indx_page25c, __f_rodata_base + 0xab734
	.globl hkscs2001_uni2indx_page26b
	.set hkscs2001_uni2indx_page26b, __f_rodata_base + 0xab784
	.globl hkscs2001_uni2indx_page26d
	.set hkscs2001_uni2indx_page26d, __f_rodata_base + 0xab78c
	.globl hkscs2001_uni2indx_page26f
	.set hkscs2001_uni2indx_page26f, __f_rodata_base + 0xab7ac
	.globl hkscs2001_uni2indx_page271
	.set hkscs2001_uni2indx_page271, __f_rodata_base + 0xab7dc
	.globl hkscs2001_uni2indx_page287
	.set hkscs2001_uni2indx_page287, __f_rodata_base + 0xab7e0
	.globl hkscs2001_uni2indx_page289
	.set hkscs2001_uni2indx_page289, __f_rodata_base + 0xab7e4
	.globl hkscs2001_uni2indx_page28d
	.set hkscs2001_uni2indx_page28d, __f_rodata_base + 0xab860
	.globl hkscs2001_uni2indx_page299
	.set hkscs2001_uni2indx_page299, __f_rodata_base + 0xab890
	.globl hkscs2001_uni2indx_page29c
	.set hkscs2001_uni2indx_page29c, __f_rodata_base + 0xab8a4
	.globl hkscs2001_uni2indx_page2a1
	.set hkscs2001_uni2indx_page2a1, __f_rodata_base + 0xab8c4
	.globl hkscs2004_2uni_page87
	.set hkscs2004_2uni_page87, __f_rodata_base + 0xab934
	.globl hkscs2004_2uni_page8c
	.set hkscs2004_2uni_page8c, __f_rodata_base + 0xab9a8
	.globl hkscs2004_2uni_upages
	.set hkscs2004_2uni_upages, __f_rodata_base + 0xabb24
	.globl hkscs2004_2charset
	.set hkscs2004_2charset, __f_rodata_base + 0xabc5c
	.globl hkscs2004_uni2indx_page34
	.set hkscs2004_uni2indx_page34, __f_rodata_base + 0xabd54
	.globl hkscs2004_uni2indx_page36
	.set hkscs2004_uni2indx_page36, __f_rodata_base + 0xabd68
	.globl hkscs2004_uni2indx_page3b
	.set hkscs2004_uni2indx_page3b, __f_rodata_base + 0xabe48
	.globl hkscs2004_uni2indx_page3d
	.set hkscs2004_uni2indx_page3d, __f_rodata_base + 0xabe70
	.globl hkscs2004_uni2indx_page3f
	.set hkscs2004_uni2indx_page3f, __f_rodata_base + 0xabeb0
	.globl hkscs2004_uni2indx_page43
	.set hkscs2004_uni2indx_page43, __f_rodata_base + 0xabf6c
	.globl hkscs2004_uni2indx_page4a
	.set hkscs2004_uni2indx_page4a, __f_rodata_base + 0xac080
	.globl hkscs2004_uni2indx_page4c
	.set hkscs2004_uni2indx_page4c, __f_rodata_base + 0xac0ac
	.globl hkscs2004_uni2indx_page4f
	.set hkscs2004_uni2indx_page4f, __f_rodata_base + 0xac110
	.globl hkscs2004_uni2indx_page56
	.set hkscs2004_uni2indx_page56, __f_rodata_base + 0xac140
	.globl hkscs2004_uni2indx_page59
	.set hkscs2004_uni2indx_page59, __f_rodata_base + 0xac180
	.globl hkscs2004_uni2indx_page5f
	.set hkscs2004_uni2indx_page5f, __f_rodata_base + 0xac2a0
	.globl hkscs2004_uni2indx_page66
	.set hkscs2004_uni2indx_page66, __f_rodata_base + 0xac2b0
	.globl hkscs2004_uni2indx_page6e
	.set hkscs2004_uni2indx_page6e, __f_rodata_base + 0xac30c
	.globl hkscs2004_uni2indx_page71
	.set hkscs2004_uni2indx_page71, __f_rodata_base + 0xac324
	.globl hkscs2004_uni2indx_page74
	.set hkscs2004_uni2indx_page74, __f_rodata_base + 0xac370
	.globl hkscs2004_uni2indx_page79
	.set hkscs2004_uni2indx_page79, __f_rodata_base + 0xac398
	.globl hkscs2004_uni2indx_page7d
	.set hkscs2004_uni2indx_page7d, __f_rodata_base + 0xac3cc
	.globl hkscs2004_uni2indx_page81
	.set hkscs2004_uni2indx_page81, __f_rodata_base + 0xac3f4
	.globl hkscs2004_uni2indx_page85
	.set hkscs2004_uni2indx_page85, __f_rodata_base + 0xac410
	.globl hkscs2004_uni2indx_page8a
	.set hkscs2004_uni2indx_page8a, __f_rodata_base + 0xac438
	.globl hkscs2004_uni2indx_page97
	.set hkscs2004_uni2indx_page97, __f_rodata_base + 0xac478
	.globl hkscs2004_uni2indx_page9f
	.set hkscs2004_uni2indx_page9f, __f_rodata_base + 0xac4d0
	.globl hkscs2004_uni2indx_page201
	.set hkscs2004_uni2indx_page201, __f_rodata_base + 0xac500
	.globl hkscs2004_uni2indx_page20a
	.set hkscs2004_uni2indx_page20a, __f_rodata_base + 0xac550
	.globl hkscs2004_uni2indx_page21a
	.set hkscs2004_uni2indx_page21a, __f_rodata_base + 0xac5b8
	.globl hkscs2004_uni2indx_page21d
	.set hkscs2004_uni2indx_page21d, __f_rodata_base + 0xac5d4
	.globl hkscs2004_uni2indx_page221
	.set hkscs2004_uni2indx_page221, __f_rodata_base + 0xac620
	.globl hkscs2004_uni2indx_page227
	.set hkscs2004_uni2indx_page227, __f_rodata_base + 0xac654
	.globl hkscs2004_uni2indx_page232
	.set hkscs2004_uni2indx_page232, __f_rodata_base + 0xac67c
	.globl hkscs2004_uni2indx_page235
	.set hkscs2004_uni2indx_page235, __f_rodata_base + 0xac694
	.globl hkscs2004_uni2indx_page23b
	.set hkscs2004_uni2indx_page23b, __f_rodata_base + 0xac6dc
	.globl hkscs2004_uni2indx_page23e
	.set hkscs2004_uni2indx_page23e, __f_rodata_base + 0xac6e4
	.globl hkscs2004_uni2indx_page242
	.set hkscs2004_uni2indx_page242, __f_rodata_base + 0xac7a0
	.globl hkscs2004_uni2indx_page24b
	.set hkscs2004_uni2indx_page24b, __f_rodata_base + 0xac7d0
	.globl hkscs2004_uni2indx_page254
	.set hkscs2004_uni2indx_page254, __f_rodata_base + 0xac7d4
	.globl hkscs2004_uni2indx_page25a
	.set hkscs2004_uni2indx_page25a, __f_rodata_base + 0xac7fc
	.globl hkscs2004_uni2indx_page26b
	.set hkscs2004_uni2indx_page26b, __f_rodata_base + 0xac814
	.globl hkscs2004_uni2indx_page26e
	.set hkscs2004_uni2indx_page26e, __f_rodata_base + 0xac868
	.globl hkscs2004_uni2indx_page270
	.set hkscs2004_uni2indx_page270, __f_rodata_base + 0xac88c
	.globl hkscs2004_uni2indx_page272
	.set hkscs2004_uni2indx_page272, __f_rodata_base + 0xac8c4
	.globl hkscs2004_uni2indx_page27b
	.set hkscs2004_uni2indx_page27b, __f_rodata_base + 0xac944
	.globl hkscs2004_uni2indx_page286
	.set hkscs2004_uni2indx_page286, __f_rodata_base + 0xac9b8
	.globl hkscs2004_uni2indx_page289
	.set hkscs2004_uni2indx_page289, __f_rodata_base + 0xac9e8
	.globl hkscs2004_uni2indx_page28b
	.set hkscs2004_uni2indx_page28b, __f_rodata_base + 0xaca04
	.globl hkscs2004_uni2indx_page290
	.set hkscs2004_uni2indx_page290, __f_rodata_base + 0xaca34
	.globl hkscs2004_uni2indx_page298
	.set hkscs2004_uni2indx_page298, __f_rodata_base + 0xaca54
	.globl hkscs2004_uni2indx_page29e
	.set hkscs2004_uni2indx_page29e, __f_rodata_base + 0xacaa8
	.globl hkscs2004_uni2indx_page2a1
	.set hkscs2004_uni2indx_page2a1, __f_rodata_base + 0xacad8
	.globl hkscs2004_uni2indx_page2a3
	.set hkscs2004_uni2indx_page2a3, __f_rodata_base + 0xacb08
	.globl hkscs2008_2uni_page87
	.set hkscs2008_2uni_page87, __f_rodata_base + 0xacb20
	.globl hkscs2008_2uni_upages
	.set hkscs2008_2uni_upages, __f_rodata_base + 0xacc1c
	.globl hkscs2008_2charset
	.set hkscs2008_2charset, __f_rodata_base + 0xacce4
	.globl hkscs2008_uni2indx_page34
	.set hkscs2008_uni2indx_page34, __f_rodata_base + 0xacd6c
	.globl hkscs2008_uni2indx_page38
	.set hkscs2008_uni2indx_page38, __f_rodata_base + 0xacda8
	.globl hkscs2008_uni2indx_page3a
	.set hkscs2008_uni2indx_page3a, __f_rodata_base + 0xacdc8
	.globl hkscs2008_uni2indx_page3e
	.set hkscs2008_uni2indx_page3e, __f_rodata_base + 0xace08
	.globl hkscs2008_uni2indx_page40
	.set hkscs2008_uni2indx_page40, __f_rodata_base + 0xace44
	.globl hkscs2008_uni2indx_page43
	.set hkscs2008_uni2indx_page43, __f_rodata_base + 0xacea8
	.globl hkscs2008_uni2indx_page46
	.set hkscs2008_uni2indx_page46, __f_rodata_base + 0xacf24
	.globl hkscs2008_uni2indx_page49
	.set hkscs2008_uni2indx_page49, __f_rodata_base + 0xacf50
	.globl hkscs2008_uni2indx_page52
	.set hkscs2008_uni2indx_page52, __f_rodata_base + 0xacf60
	.globl hkscs2008_uni2indx_page54
	.set hkscs2008_uni2indx_page54, __f_rodata_base + 0xacf74
	.globl hkscs2008_uni2indx_page57
	.set hkscs2008_uni2indx_page57, __f_rodata_base + 0xacf88
	.globl hkscs2008_uni2indx_page62
	.set hkscs2008_uni2indx_page62, __f_rodata_base + 0xacff0
	.globl hkscs2008_uni2indx_page66
	.set hkscs2008_uni2indx_page66, __f_rodata_base + 0xad024
	.globl hkscs2008_uni2indx_page6a
	.set hkscs2008_uni2indx_page6a, __f_rodata_base + 0xad088
	.globl hkscs2008_uni2indx_page70
	.set hkscs2008_uni2indx_page70, __f_rodata_base + 0xad094
	.globl hkscs2008_uni2indx_page73
	.set hkscs2008_uni2indx_page73, __f_rodata_base + 0xad0b0
	.globl hkscs2008_uni2indx_page79
	.set hkscs2008_uni2indx_page79, __f_rodata_base + 0xad124
	.globl hkscs2008_uni2indx_page84
	.set hkscs2008_uni2indx_page84, __f_rodata_base + 0xad1d8
	.globl hkscs2008_uni2indx_page88
	.set hkscs2008_uni2indx_page88, __f_rodata_base + 0xad260
	.globl hkscs2008_uni2indx_page8b
	.set hkscs2008_uni2indx_page8b, __f_rodata_base + 0xad288
	.globl hkscs2008_uni2indx_page90
	.set hkscs2008_uni2indx_page90, __f_rodata_base + 0xad2ac
	.globl hkscs2008_uni2indx_page92
	.set hkscs2008_uni2indx_page92, __f_rodata_base + 0xad2c0
	.globl hkscs2008_uni2indx_page94
	.set hkscs2008_uni2indx_page94, __f_rodata_base + 0xad2c8
	.globl hkscs2008_uni2indx_page97
	.set hkscs2008_uni2indx_page97, __f_rodata_base + 0xad2d4
	.globl hkscs2008_uni2indx_page9f
	.set hkscs2008_uni2indx_page9f, __f_rodata_base + 0xad2e8
	.globl hkscs2008_uni2indx_page20a
	.set hkscs2008_uni2indx_page20a, __f_rodata_base + 0xad31c
	.globl hkscs2008_uni2indx_page21d
	.set hkscs2008_uni2indx_page21d, __f_rodata_base + 0xad340
	.globl hkscs2008_uni2indx_page224
	.set hkscs2008_uni2indx_page224, __f_rodata_base + 0xad358
	.globl hkscs2008_uni2indx_page231
	.set hkscs2008_uni2indx_page231, __f_rodata_base + 0xad38c
	.globl hkscs2008_uni2indx_page235
	.set hkscs2008_uni2indx_page235, __f_rodata_base + 0xad3e4
	.globl hkscs2008_uni2indx_page241
	.set hkscs2008_uni2indx_page241, __f_rodata_base + 0xad44c
	.globl hkscs2008_uni2indx_page258
	.set hkscs2008_uni2indx_page258, __f_rodata_base + 0xad468
	.globl hkscs2008_uni2indx_page25d
	.set hkscs2008_uni2indx_page25d, __f_rodata_base + 0xad4a0
	.globl hkscs2008_uni2indx_page260
	.set hkscs2008_uni2indx_page260, __f_rodata_base + 0xad4d0
	.globl hkscs2008_uni2indx_page26e
	.set hkscs2008_uni2indx_page26e, __f_rodata_base + 0xad4dc
	.globl hkscs2008_uni2indx_page27b
	.set hkscs2008_uni2indx_page27b, __f_rodata_base + 0xad500
	.globl hkscs2008_uni2indx_page289
	.set hkscs2008_uni2indx_page289, __f_rodata_base + 0xad51c
	.globl hkscs2008_uni2indx_page2ad
	.set hkscs2008_uni2indx_page2ad, __f_rodata_base + 0xad520
	.globl uhc_1_2uni_main_page81
	.set uhc_1_2uni_main_page81, __f_rodata_base + 0xad560
	.globl uhc_1_2uni_page81
	.set uhc_1_2uni_page81, __f_rodata_base + 0xad5e0
	.globl uhc_1_2charset_main
	.set uhc_1_2charset_main, __f_rodata_base + 0xaec20
	.globl uhc_1_2charset
	.set uhc_1_2charset, __f_rodata_base + 0xaec7c
	.globl uhc_1_uni2indx_pageac
	.set uhc_1_uni2indx_pageac, __f_rodata_base + 0xb02bc
	.globl uhc_2_2uni_main_pagea1
	.set uhc_2_2uni_main_pagea1, __f_rodata_base + 0xb09e8
	.globl uhc_2_2uni_pagea1
	.set uhc_2_2uni_pagea1, __f_rodata_base + 0xb0a80
	.globl uhc_2_2charset_main
	.set uhc_2_2charset_main, __f_rodata_base + 0xb16b8
	.globl uhc_2_2charset
	.set uhc_2_2charset, __f_rodata_base + 0xb171c
	.globl uhc_2_uni2indx_pagec8
	.set uhc_2_uni2indx_pagec8, __f_rodata_base + 0xb2354
	.globl cjk_variants
	.set cjk_variants, __f_rodata_base + 0xb2740
	.globl cjk_variants_indx
	.set cjk_variants_indx, __f_rodata_base + 0xb854c
	.globl translit_data
	.set translit_data, __f_rodata_base + 0xc294c
	.globl translit_page00
	.set translit_page00, __f_rodata_base + 0xcb7bc
	.globl translit_page02
	.set translit_page02, __f_rodata_base + 0xcba6c
	.globl translit_page02_1
	.set translit_page02_1, __f_rodata_base + 0xcba7c
	.globl translit_page03
	.set translit_page03, __f_rodata_base + 0xcbacc
	.globl translit_page05
	.set translit_page05, __f_rodata_base + 0xcbb2c
	.globl translit_page06
	.set translit_page06, __f_rodata_base + 0xcbb3c
	.globl translit_page0e
	.set translit_page0e, __f_rodata_base + 0xcbb5c
	.globl translit_page0f
	.set translit_page0f, __f_rodata_base + 0xcbbbc
	.globl translit_page1e
	.set translit_page1e, __f_rodata_base + 0xcbbdc
	.globl translit_page1e_2
	.set translit_page1e_2, __f_rodata_base + 0xcbd1c
	.globl translit_page20
	.set translit_page20, __f_rodata_base + 0xcbd2c
	.globl translit_page20_3
	.set translit_page20_3, __f_rodata_base + 0xcbddc
	.globl translit_page21
	.set translit_page21, __f_rodata_base + 0xcbdec
	.globl translit_page22
	.set translit_page22, __f_rodata_base + 0xcbf9c
	.globl translit_page22_4
	.set translit_page22_4, __f_rodata_base + 0xcc05c
	.globl translit_page24
	.set translit_page24, __f_rodata_base + 0xcc0bc
	.globl translit_page25
	.set translit_page25, __f_rodata_base + 0xcc29c
	.globl translit_page2a
	.set translit_page2a, __f_rodata_base + 0xcc31c
	.globl translit_page2f
	.set translit_page2f, __f_rodata_base + 0xcc32c
	.globl translit_page30
	.set translit_page30, __f_rodata_base + 0xcc4dc
	.globl translit_page31
	.set translit_page31, __f_rodata_base + 0xcc6cc
	.globl translit_page31_5
	.set translit_page31_5, __f_rodata_base + 0xcc78c
	.globl translit_pagef9
	.set translit_pagef9, __f_rodata_base + 0xccbac
	.globl translit_pagefb
	.set translit_pagefb, __f_rodata_base + 0xcce8c
	.globl translit_pagefe
	.set translit_pagefe, __f_rodata_base + 0xccf2c
	.globl translit_pageff
	.set translit_pageff, __f_rodata_base + 0xccf7c
	.globl translit_page1d4
	.set translit_page1d4, __f_rodata_base + 0xcd15c
	.globl translit_page2f8
	.set translit_page2f8, __f_rodata_base + 0xcd95c
	.globl all_encodings
	.set all_encodings, __f_rodata_base + 0xcdd9c
	.globl stringpool_contents
	.set stringpool_contents, __f_rodata_base + 0xce670
	.globl aliases
	.set aliases, __f_rodata_base + 0xcf470
	.globl all_canonical
	.set all_canonical, __f_rodata_base + 0xd1158
	.globl conversion_lists.7622
	.set conversion_lists.7622, __f_rodata_base + 0xd123c
	.globl asso_values.9691
	.set asso_values.9691, __f_rodata_base + 0xd124c

/* .data.rel.ro.local：0 个符号 */

/* .data：163 个符号 */
	.globl DAT_003af008
	.set DAT_003af008, __f_data_base + 0x8
	.globl running
	.set running, __f_data_base + 0x18
	.globl Rowspacing
	.set Rowspacing, __f_data_base + 0x1c
	.globl joystick_fd
	.set joystick_fd, __f_data_base + 0x20
	.globl RF_JOYTable
	.set RF_JOYTable, __f_data_base + 0x30
	.globl CHANNEL_TBL
	.set CHANNEL_TBL, __f_data_base + 0xa8
	.globl RX_ADDRESS1
	.set RX_ADDRESS1, __f_data_base + 0xac
	.globl RX_ADDRESS0
	.set RX_ADDRESS0, __f_data_base + 0xb4
	.globl Dem_cal2_data
	.set Dem_cal2_data, __f_data_base + 0xbc
	.globl RF_cal2_data
	.set RF_cal2_data, __f_data_base + 0xc0
	.globl RF_cal_data
	.set RF_cal_data, __f_data_base + 0xc8
	.globl BB_cal_data
	.set BB_cal_data, __f_data_base + 0xcc
	.globl USB_Table
	.set USB_Table, __f_data_base + 0xd4
	.globl JOYSTICK_DEVNAME
	.set JOYSTICK_DEVNAME, __f_data_base + 0x254
	.globl m_ui
	.set m_ui, __f_data_base + 0x264
	.globl DAT_003af268
	.set DAT_003af268, __f_data_base + 0x268
	.globl DAT_003af26c
	.set DAT_003af26c, __f_data_base + 0x26c
	.globl DAT_003af270
	.set DAT_003af270, __f_data_base + 0x270
	.globl DAT_003af274
	.set DAT_003af274, __f_data_base + 0x274
	.globl DAT_003af278
	.set DAT_003af278, __f_data_base + 0x278
	.globl DAT_003af27c
	.set DAT_003af27c, __f_data_base + 0x27c
	.globl DAT_003af280
	.set DAT_003af280, __f_data_base + 0x280
	.globl DAT_003af284
	.set DAT_003af284, __f_data_base + 0x284
	.globl DAT_003af288
	.set DAT_003af288, __f_data_base + 0x288
	.globl DAT_003af28c
	.set DAT_003af28c, __f_data_base + 0x28c
	.globl DAT_003af290
	.set DAT_003af290, __f_data_base + 0x290
	.globl DAT_003af294
	.set DAT_003af294, __f_data_base + 0x294
	.globl DAT_003af298
	.set DAT_003af298, __f_data_base + 0x298
	.globl DAT_003af29c
	.set DAT_003af29c, __f_data_base + 0x29c
	.globl DAT_003af2a0
	.set DAT_003af2a0, __f_data_base + 0x2a0
	.globl DAT_003af2a4
	.set DAT_003af2a4, __f_data_base + 0x2a4
	.globl DAT_003af2a8
	.set DAT_003af2a8, __f_data_base + 0x2a8
	.globl DAT_003af2ac
	.set DAT_003af2ac, __f_data_base + 0x2ac
	.globl DAT_003af2b0
	.set DAT_003af2b0, __f_data_base + 0x2b0
	.globl DAT_003af2b4
	.set DAT_003af2b4, __f_data_base + 0x2b4
	.globl DAT_003af2b8
	.set DAT_003af2b8, __f_data_base + 0x2b8
	.globl DAT_003af2bc
	.set DAT_003af2bc, __f_data_base + 0x2bc
	.globl DAT_003af2c0
	.set DAT_003af2c0, __f_data_base + 0x2c0
	.globl DAT_003af30c
	.set DAT_003af30c, __f_data_base + 0x30c
	.globl DAT_003af310
	.set DAT_003af310, __f_data_base + 0x310
	.globl DAT_003af314
	.set DAT_003af314, __f_data_base + 0x314
	.globl DAT_003af318
	.set DAT_003af318, __f_data_base + 0x318
	.globl DAT_003af31c
	.set DAT_003af31c, __f_data_base + 0x31c
	.globl DAT_003af320
	.set DAT_003af320, __f_data_base + 0x320
	.globl DAT_003af324
	.set DAT_003af324, __f_data_base + 0x324
	.globl DAT_003af328
	.set DAT_003af328, __f_data_base + 0x328
	.globl DAT_003af37c
	.set DAT_003af37c, __f_data_base + 0x37c
	.globl DAT_003af380
	.set DAT_003af380, __f_data_base + 0x380
	.globl DAT_003af384
	.set DAT_003af384, __f_data_base + 0x384
	.globl DAT_003af388
	.set DAT_003af388, __f_data_base + 0x388
	.globl DAT_003af38c
	.set DAT_003af38c, __f_data_base + 0x38c
	.globl DAT_003af390
	.set DAT_003af390, __f_data_base + 0x390
	.globl DAT_003af394
	.set DAT_003af394, __f_data_base + 0x394
	.globl DAT_003af398
	.set DAT_003af398, __f_data_base + 0x398
	.globl DAT_003af39c
	.set DAT_003af39c, __f_data_base + 0x39c
	.globl DAT_003af3a0
	.set DAT_003af3a0, __f_data_base + 0x3a0
	.globl DAT_003af3a4
	.set DAT_003af3a4, __f_data_base + 0x3a4
	.globl DAT_003af3a8
	.set DAT_003af3a8, __f_data_base + 0x3a8
	.globl DAT_003af3ac
	.set DAT_003af3ac, __f_data_base + 0x3ac
	.globl DAT_003af698
	.set DAT_003af698, __f_data_base + 0x698
	.globl DAT_003af69c
	.set DAT_003af69c, __f_data_base + 0x69c
	.globl DAT_003af6a0
	.set DAT_003af6a0, __f_data_base + 0x6a0
	.globl DAT_003af6a4
	.set DAT_003af6a4, __f_data_base + 0x6a4
	.globl DAT_003af6a8
	.set DAT_003af6a8, __f_data_base + 0x6a8
	.globl DAT_003af6ac
	.set DAT_003af6ac, __f_data_base + 0x6ac
	.globl DAT_003af6b0
	.set DAT_003af6b0, __f_data_base + 0x6b0
	.globl DAT_003af6b8
	.set DAT_003af6b8, __f_data_base + 0x6b8
	.globl DAT_003af6bc
	.set DAT_003af6bc, __f_data_base + 0x6bc
	.globl DAT_003af6c0
	.set DAT_003af6c0, __f_data_base + 0x6c0
	.globl DAT_003af6c4
	.set DAT_003af6c4, __f_data_base + 0x6c4
	.globl DAT_003af6c8
	.set DAT_003af6c8, __f_data_base + 0x6c8
	.globl DAT_003af6cc
	.set DAT_003af6cc, __f_data_base + 0x6cc
	.globl DAT_003af6d0
	.set DAT_003af6d0, __f_data_base + 0x6d0
	.globl DAT_003af6d4
	.set DAT_003af6d4, __f_data_base + 0x6d4
	.globl DAT_003af6d8
	.set DAT_003af6d8, __f_data_base + 0x6d8
	.globl DAT_003af6dc
	.set DAT_003af6dc, __f_data_base + 0x6dc
	.globl DAT_003af6e0
	.set DAT_003af6e0, __f_data_base + 0x6e0
	.globl DAT_003af6e4
	.set DAT_003af6e4, __f_data_base + 0x6e4
	.globl DAT_003af6e8
	.set DAT_003af6e8, __f_data_base + 0x6e8
	.globl DAT_003af6f0
	.set DAT_003af6f0, __f_data_base + 0x6f0
	.globl DAT_003af6f4
	.set DAT_003af6f4, __f_data_base + 0x6f4
	.globl DAT_003af6f8
	.set DAT_003af6f8, __f_data_base + 0x6f8
	.globl DAT_003af6fc
	.set DAT_003af6fc, __f_data_base + 0x6fc
	.globl DAT_003af700
	.set DAT_003af700, __f_data_base + 0x700
	.globl DAT_003af704
	.set DAT_003af704, __f_data_base + 0x704
	.globl DAT_003af708
	.set DAT_003af708, __f_data_base + 0x708
	.globl DAT_003af70f
	.set DAT_003af70f, __f_data_base + 0x70f
	.globl DAT_003af718
	.set DAT_003af718, __f_data_base + 0x718
	.globl DAT_003af71c
	.set DAT_003af71c, __f_data_base + 0x71c
	.globl DAT_003af720
	.set DAT_003af720, __f_data_base + 0x720
	.globl DAT_003af724
	.set DAT_003af724, __f_data_base + 0x724
	.globl DAT_003af728
	.set DAT_003af728, __f_data_base + 0x728
	.globl DAT_003af72c
	.set DAT_003af72c, __f_data_base + 0x72c
	.globl DAT_003af730
	.set DAT_003af730, __f_data_base + 0x730
	.globl DAT_003af734
	.set DAT_003af734, __f_data_base + 0x734
	.globl DAT_003af738
	.set DAT_003af738, __f_data_base + 0x738
	.globl DAT_003af73c
	.set DAT_003af73c, __f_data_base + 0x73c
	.globl DAT_003af740
	.set DAT_003af740, __f_data_base + 0x740
	.globl DAT_003af744
	.set DAT_003af744, __f_data_base + 0x744
	.globl DAT_003af748
	.set DAT_003af748, __f_data_base + 0x748
	.globl DAT_003af74c
	.set DAT_003af74c, __f_data_base + 0x74c
	.globl DAT_003af788
	.set DAT_003af788, __f_data_base + 0x788
	.globl DAT_003af78c
	.set DAT_003af78c, __f_data_base + 0x78c
	.globl DAT_003af790
	.set DAT_003af790, __f_data_base + 0x790
	.globl DAT_003af794
	.set DAT_003af794, __f_data_base + 0x794
	.globl DAT_003af798
	.set DAT_003af798, __f_data_base + 0x798
	.globl DAT_003af79c
	.set DAT_003af79c, __f_data_base + 0x79c
	.globl DAT_003af7a0
	.set DAT_003af7a0, __f_data_base + 0x7a0
	.globl DAT_003af7a4
	.set DAT_003af7a4, __f_data_base + 0x7a4
	.globl DAT_003af7a8
	.set DAT_003af7a8, __f_data_base + 0x7a8
	.globl DAT_003af7ac
	.set DAT_003af7ac, __f_data_base + 0x7ac
	.globl DAT_003af7b0
	.set DAT_003af7b0, __f_data_base + 0x7b0
	.globl DAT_003af7b4
	.set DAT_003af7b4, __f_data_base + 0x7b4
	.globl DAT_003af7b8
	.set DAT_003af7b8, __f_data_base + 0x7b8
	.globl DAT_003af7bc
	.set DAT_003af7bc, __f_data_base + 0x7bc
	.globl DAT_003af7c0
	.set DAT_003af7c0, __f_data_base + 0x7c0
	.globl DAT_003af7c4
	.set DAT_003af7c4, __f_data_base + 0x7c4
	.globl DAT_003af7c8
	.set DAT_003af7c8, __f_data_base + 0x7c8
	.globl DAT_003af7cc
	.set DAT_003af7cc, __f_data_base + 0x7cc
	.globl DAT_003af7d0
	.set DAT_003af7d0, __f_data_base + 0x7d0
	.globl DAT_003af7d4
	.set DAT_003af7d4, __f_data_base + 0x7d4
	.globl DAT_003af7d8
	.set DAT_003af7d8, __f_data_base + 0x7d8
	.globl DAT_003af7e0
	.set DAT_003af7e0, __f_data_base + 0x7e0
	.globl DAT_003af7e4
	.set DAT_003af7e4, __f_data_base + 0x7e4
	.globl DAT_003af7e8
	.set DAT_003af7e8, __f_data_base + 0x7e8
	.globl DAT_003af7ec
	.set DAT_003af7ec, __f_data_base + 0x7ec
	.globl DAT_003af7f0
	.set DAT_003af7f0, __f_data_base + 0x7f0
	.globl DAT_003af7f4
	.set DAT_003af7f4, __f_data_base + 0x7f4
	.globl DAT_003af7f8
	.set DAT_003af7f8, __f_data_base + 0x7f8
	.globl DAT_003af7fc
	.set DAT_003af7fc, __f_data_base + 0x7fc
	.globl DAT_003af800
	.set DAT_003af800, __f_data_base + 0x800
	.globl DAT_003af804
	.set DAT_003af804, __f_data_base + 0x804
	.globl DAT_003af808
	.set DAT_003af808, __f_data_base + 0x808
	.globl DAT_003af820
	.set DAT_003af820, __f_data_base + 0x820
	.globl DAT_003af824
	.set DAT_003af824, __f_data_base + 0x824
	.globl DAT_003af828
	.set DAT_003af828, __f_data_base + 0x828
	.globl DAT_003af82c
	.set DAT_003af82c, __f_data_base + 0x82c
	.globl DAT_003af830
	.set DAT_003af830, __f_data_base + 0x830
	.globl DAT_003af834
	.set DAT_003af834, __f_data_base + 0x834
	.globl DAT_003af838
	.set DAT_003af838, __f_data_base + 0x838
	.globl DAT_003af83c
	.set DAT_003af83c, __f_data_base + 0x83c
	.globl DAT_003af840
	.set DAT_003af840, __f_data_base + 0x840
	.globl DAT_003af844
	.set DAT_003af844, __f_data_base + 0x844
	.globl m_movetab
	.set m_movetab, __f_data_base + 0x848
	.globl m_joysticktab
	.set m_joysticktab, __f_data_base + 0xbe0
	.globl m_statetab
	.set m_statetab, __f_data_base + 0xf7c
	.globl KEY_Table
	.set KEY_Table, __f_data_base + 0x100c
	.globl P1_Table
	.set P1_Table, __f_data_base + 0x104c
	.globl turbo_delay
	.set turbo_delay, __f_data_base + 0x1128
	.globl DAT_003b012c
	.set DAT_003b012c, __f_data_base + 0x112c
	.globl user_joy_key_mask
	.set user_joy_key_mask, __f_data_base + 0x1154
	.globl default_core_list
	.set default_core_list, __f_data_base + 0x1254
	.globl DAT_003b0274
	.set DAT_003b0274, __f_data_base + 0x1274
	.globl DAT_003b0278
	.set DAT_003b0278, __f_data_base + 0x1278
	.globl DAT_003b0298
	.set DAT_003b0298, __f_data_base + 0x1298
	.globl DAT_003b02b8
	.set DAT_003b02b8, __f_data_base + 0x12b8
	.globl DAT_003b02bc
	.set DAT_003b02bc, __f_data_base + 0x12bc
	.globl fps0
	.set fps0, __f_data_base + 0x2ce4
	.globl sound_len
	.set sound_len, __f_data_base + 0x2ce8
	.globl GameMenuHotKey
	.set GameMenuHotKey, __f_data_base + 0x2cec
	.globl SaveDefaultStateKey
	.set SaveDefaultStateKey, __f_data_base + 0x2cf0
	.globl _mxml_key
	.set _mxml_key, __f_data_base + 0x2cf4
	.globl _libiconv_version
	.set _libiconv_version, __f_data_base + 0x2cf8

/* .bss：194 个符号 */
	.globl completed.10349
	.set completed.10349, __f_bss_base + 0x0
	.globl log_file_initialized
	.set log_file_initialized, __f_bss_base + 0x4
	.globl log_file_fp
	.set log_file_fp, __f_bss_base + 0x8
	.globl shm
	.set shm, __f_bss_base + 0xc
	.globl spi_printf_needflash
	.set spi_printf_needflash, __f_bss_base + 0x10
	.globl scr_data
	.set scr_data, __f_bss_base + 0x14
	.globl soft_rotation
	.set soft_rotation, __f_bss_base + 0x18
	.globl displayfps
	.set displayfps, __f_bss_base + 0x1c
	.globl DisplayThread
	.set DisplayThread, __f_bss_base + 0x20
	.globl CRU
	.set CRU, __f_bss_base + 0x24
	.globl GRF
	.set GRF, __f_bss_base + 0x28
	.globl GPIO0
	.set GPIO0, __f_bss_base + 0x2c
	.globl GPIO1
	.set GPIO1, __f_bss_base + 0x30
	.globl GPIO2
	.set GPIO2, __f_bss_base + 0x34
	.globl joy_key_tmp
	.set joy_key_tmp, __f_bss_base + 0x38
	.globl gpiosignal
	.set gpiosignal, __f_bss_base + 0x48
	.globl gpiofp
	.set gpiofp, __f_bss_base + 0x4c
	.globl handle
	.set handle, __f_bss_base + 0x50
	.globl DisplayThreadflag
	.set DisplayThreadflag, __f_bss_base + 0x54
	.globl mutex
	.set mutex, __f_bss_base + 0x58
	.globl cond
	.set cond, __f_bss_base + 0x70
	.globl _ZL10zopenerror
	.set _ZL10zopenerror, __f_bss_base + 0xa0
	.globl lasterrorU
	.set lasterrorU, __f_bss_base + 0xa4
	.globl file_info_list
	.set file_info_list, __f_bss_base + 0xa8
	.globl DAT_003b2320
	.set DAT_003b2320, __f_bss_base + 0x1a8
	.globl DAT_003b2324
	.set DAT_003b2324, __f_bss_base + 0x1ac
	.globl DAT_003b23a4
	.set DAT_003b23a4, __f_bss_base + 0x22c
	.globl DAT_003b2424
	.set DAT_003b2424, __f_bss_base + 0x2ac
	.globl DAT_003b24a4
	.set DAT_003b24a4, __f_bss_base + 0x32c
	.globl FilenameExt
	.set FilenameExt, __f_bss_base + 0xa148
	.globl tree
	.set tree, __f_bss_base + 0xa14c
	.globl filelist_tree
	.set filelist_tree, __f_bss_base + 0xa150
	.globl res_hz
	.set res_hz, __f_bss_base + 0xa154
	.globl ze
	.set ze, __f_bss_base + 0xa158
	.globl zr
	.set zr, __f_bss_base + 0xa288
	.globl mui_fast_lsit
	.set mui_fast_lsit, __f_bss_base + 0xa28c
	.globl m_search
	.set m_search, __f_bss_base + 0xa290
	.globl DisplayThumbnailflag
	.set DisplayThumbnailflag, __f_bss_base + 0xa294
	.globl ForceFlashCount
	.set ForceFlashCount, __f_bss_base + 0xa298
	.globl diff_prev
	.set diff_prev, __f_bss_base + 0xa29c
	.globl m_time0
	.set m_time0, __f_bss_base + 0xa2a0
	.globl font
	.set font, __f_bss_base + 0xa2a4
	.globl fontscale
	.set fontscale, __f_bss_base + 0xa320
	.globl fontascent
	.set fontascent, __f_bss_base + 0xa324
	.globl fontbaseline
	.set fontbaseline, __f_bss_base + 0xa328
	.globl OutRect
	.set OutRect, __f_bss_base + 0xa32c
	.globl fontbitmap
	.set fontbitmap, __f_bss_base + 0xa344
	.globl fontname
	.set fontname, __f_bss_base + 0xb344
	.globl fontbuffer
	.set fontbuffer, __f_bss_base + 0xb364
	.globl configitems
	.set configitems, __f_bss_base + 0xb368
	.globl m_menulog
	.set m_menulog, __f_bss_base + 0x176b8
	.globl path
	.set path, __f_bss_base + 0x17874
	.globl core_info_list
	.set core_info_list, __f_bss_base + 0x17974
	.globl hz
	.set hz, __f_bss_base + 0x1c974
	.globl SoundBuffer
	.set SoundBuffer, __f_bss_base + 0x1c978
	.globl scrbuf
	.set scrbuf, __f_bss_base + 0x1d4f8
	.globl Soundplayflag
	.set Soundplayflag, __f_bss_base + 0x1d4fc
	.globl errorcount
	.set errorcount, __f_bss_base + 0x1d500
	.globl bimapFilebuffer
	.set bimapFilebuffer, __f_bss_base + 0x1d504
	.globl USBJoy_debug
	.set USBJoy_debug, __f_bss_base + 0x1d508
	.globl SPI_MODE
	.set SPI_MODE, __f_bss_base + 0x1d50c
	.globl system_directory
	.set system_directory, __f_bss_base + 0x1d510
	.globl save_directory
	.set save_directory, __f_bss_base + 0x1d610
	.globl environment_str
	.set environment_str, __f_bss_base + 0x1d710
	.globl user_joy_key_trubo
	.set user_joy_key_trubo, __f_bss_base + 0x1d814
	.globl rgb_565_buffer
	.set rgb_565_buffer, __f_bss_base + 0x1d914
	.globl use_rgb_8888
	.set use_rgb_8888, __f_bss_base + 0x1d918
	.globl rotation_buff
	.set rotation_buff, __f_bss_base + 0x1d91c
	.globl rotation
	.set rotation, __f_bss_base + 0x1d920
	.globl skipCounter
	.set skipCounter, __f_bss_base + 0x1d924
	.globl FrameCount0
	.set FrameCount0, __f_bss_base + 0x1d928
	.globl frames_prev
	.set frames_prev, __f_bss_base + 0x1d92c
	.globl PlayFrameError
	.set PlayFrameError, __f_bss_base + 0x1d930
	.globl ticks_ptr
	.set ticks_ptr, __f_bss_base + 0x1d934
	.globl AutoRestoreKey
	.set AutoRestoreKey, __f_bss_base + 0x1d938
	.globl _mxml_key_once
	.set _mxml_key_once, __f_bss_base + 0x1d93c
	.globl g_sfc_reg
	.set g_sfc_reg, __f_bss_base + 0x1d940
	.globl FlashSize
	.set FlashSize, __f_bss_base + 0x1d944
	.globl UniqueID
	.set UniqueID, __f_bss_base + 0x1d948
	.globl corecfg
	.set corecfg, __f_bss_base + 0x1d950
	.globl items
	.set items, __f_bss_base + 0x217d0
	.globl sbi
	.set sbi, __f_bss_base + 0x25650
	.globl mi
	.set mi, __f_bss_base + 0x27854
	.globl file_info_list_ext
	.set file_info_list_ext, __f_bss_base + 0x29374
	.globl hi
	.set hi, __f_bss_base + 0x2ac74
	.globl autorundriver
	.set autorundriver, __f_bss_base + 0x2be84
	.globl autorunfile
	.set autorunfile, __f_bss_base + 0x2ce84
	.globl mp3DecInfo
	.set mp3DecInfo, __f_bss_base + 0x2de84
	.globl di
	.set di, __f_bss_base + 0x2e674
	.globl bprintf_buf
	.set bprintf_buf, __f_bss_base + 0x2e9bc
	.globl si
	.set si, __f_bss_base + 0x2ebbc
	.globl sfi
	.set sfi, __f_bss_base + 0x2ed04
	.globl Nesname
	.set Nesname, __f_bss_base + 0x2ee20
	.globl RomName
	.set RomName, __f_bss_base + 0x2ef20
	.globl fileName
	.set fileName, __f_bss_base + 0x2f020
	.globl resource_path
	.set resource_path, __f_bss_base + 0x2f120
	.globl root_path
	.set root_path, __f_bss_base + 0x2f220
	.globl work_path
	.set work_path, __f_bss_base + 0x2f320
	.globl m_crctable
	.set m_crctable, __f_bss_base + 0x2f420
	.globl mainkey
	.set mainkey, __f_bss_base + 0x2f4a0
	.globl InputDeviceInfo
	.set InputDeviceInfo, __f_bss_base + 0x2f520
	.globl keyMapping
	.set keyMapping, __f_bss_base + 0x2f590
	.globl SoundPlayer
	.set SoundPlayer, __f_bss_base + 0x2f5f0
	.globl fpsbuf
	.set fpsbuf, __f_bss_base + 0x2f638
	.globl ticks_buf
	.set ticks_buf, __f_bss_base + 0x2f678
	.globl fh
	.set fh, __f_bss_base + 0x2f6b8
	.globl mui_Effect0
	.set mui_Effect0, __f_bss_base + 0x2f6f0
	.globl mui_Effect1
	.set mui_Effect1, __f_bss_base + 0x2f714
	.globl mui_MenuMusic
	.set mui_MenuMusic, __f_bss_base + 0x2f738
	.globl ArchivePath
	.set ArchivePath, __f_bss_base + 0x2f75c
	.globl GamePath
	.set GamePath, __f_bss_base + 0x2f778
	.globl key2
	.set key2, __f_bss_base + 0x2f794
	.globl mdtemp1
	.set mdtemp1, __f_bss_base + 0x2f7b0
	.globl game
	.set game, __f_bss_base + 0x2f7dc
	.globl game_joy_key
	.set game_joy_key, __f_bss_base + 0x2f7ec
	.globl joy_key
	.set joy_key, __f_bss_base + 0x2f7fc
	.globl this_frame
	.set this_frame, __f_bss_base + 0x2f80c
	.globl frame_time_last
	.set frame_time_last, __f_bss_base + 0x2f820
	.globl progress_stepcount
	.set progress_stepcount, __f_bss_base + 0x2f828
	.globl RF_joy_key
	.set RF_joy_key, __f_bss_base + 0x2f830
	.globl inTimeVal
	.set inTimeVal, __f_bss_base + 0x2f838
	.globl outTimeVal
	.set outTimeVal, __f_bss_base + 0x2f840
	.globl ChangeSeting
	.set ChangeSeting, __f_bss_base + 0x2f848
	.globl DispFrameCount
	.set DispFrameCount, __f_bss_base + 0x2f84c
	.globl DisplayZoomFlag
	.set DisplayZoomFlag, __f_bss_base + 0x2f850
	.globl Filetype
	.set Filetype, __f_bss_base + 0x2f854
	.globl FrameCount
	.set FrameCount, __f_bss_base + 0x2f858
	.globl FrameSkip
	.set FrameSkip, __f_bss_base + 0x2f85c
	.globl Frame_data
	.set Frame_data, __f_bss_base + 0x2f860
	.globl Frame_height
	.set Frame_height, __f_bss_base + 0x2f864
	.globl Frame_pitch
	.set Frame_pitch, __f_bss_base + 0x2f868
	.globl Frame_width
	.set Frame_width, __f_bss_base + 0x2f86c
	.globl Joy1_Delay
	.set Joy1_Delay, __f_bss_base + 0x2f870
	.globl Joy1_Press
	.set Joy1_Press, __f_bss_base + 0x2f874
	.globl SoundBufferIndex0
	.set SoundBufferIndex0, __f_bss_base + 0x2f878
	.globl SoundBufferIndex1
	.set SoundBufferIndex1, __f_bss_base + 0x2f87c
	.globl SoundBufferLength
	.set SoundBufferLength, __f_bss_base + 0x2f880
	.globl TimeCountReg
	.set TimeCountReg, __f_bss_base + 0x2f884
	.globl Time_0
	.set Time_0, __f_bss_base + 0x2f888
	.globl Time_1
	.set Time_1, __f_bss_base + 0x2f88c
	.globl USE_HDMI_OUT
	.set USE_HDMI_OUT, __f_bss_base + 0x2f890
	.globl ZIP_BUF
	.set ZIP_BUF, __f_bss_base + 0x2f894
	.globl ZIP_BUF_SIZE
	.set ZIP_BUF_SIZE, __f_bss_base + 0x2f898
	.globl _SetDoubleBuffer
	.set _SetDoubleBuffer, __f_bss_base + 0x2f89c
	.globl _SetFrameSkip
	.set _SetFrameSkip, __f_bss_base + 0x2f8a0
	.globl _retro_get_region
	.set _retro_get_region, __f_bss_base + 0x2f8a4
	.globl _retro_is_support
	.set _retro_is_support, __f_bss_base + 0x2f8a8
	.globl _retro_run
	.set _retro_run, __f_bss_base + 0x2f8ac
	.globl _retro_serialize
	.set _retro_serialize, __f_bss_base + 0x2f8b0
	.globl _retro_serialize_size
	.set _retro_serialize_size, __f_bss_base + 0x2f8b4
	.globl _retro_set_device
	.set _retro_set_device, __f_bss_base + 0x2f8b8
	.globl _retro_unserialize
	.set _retro_unserialize, __f_bss_base + 0x2f8bc
	.globl disp_times
	.set disp_times, __f_bss_base + 0x2f8c4
	.globl fps
	.set fps, __f_bss_base + 0x2f8c8
	.globl fps_ptr
	.set fps_ptr, __f_bss_base + 0x2f8cc
	.globl initialTicks
	.set initialTicks, __f_bss_base + 0x2f8d0
	.globl joytemp0
	.set joytemp0, __f_bss_base + 0x2f8d4
	.globl joytemp1
	.set joytemp1, __f_bss_base + 0x2f8d8
	.globl m_ticks
	.set m_ticks, __f_bss_base + 0x2f8dc
	.globl maxSkips
	.set maxSkips, __f_bss_base + 0x2f8e0
	.globl n_input_height
	.set n_input_height, __f_bss_base + 0x2f8e4
	.globl n_input_visible_height
	.set n_input_visible_height, __f_bss_base + 0x2f8e8
	.globl n_input_visible_width
	.set n_input_visible_width, __f_bss_base + 0x2f8ec
	.globl n_input_width
	.set n_input_width, __f_bss_base + 0x2f8f0
	.globl output_x
	.set output_x, __f_bss_base + 0x2f8f4
	.globl output_y
	.set output_y, __f_bss_base + 0x2f8f8
	.globl overtime
	.set overtime, __f_bss_base + 0x2f8fc
	.globl overtime1
	.set overtime1, __f_bss_base + 0x2f900
	.globl pal_ntsc
	.set pal_ntsc, __f_bss_base + 0x2f904
	.globl pause_ret
	.set pause_ret, __f_bss_base + 0x2f908
	.globl pf
	.set pf, __f_bss_base + 0x2f90c
	.globl prev_time
	.set prev_time, __f_bss_base + 0x2f910
	.globl romfile
	.set romfile, __f_bss_base + 0x2f914
	.globl scr_buf
	.set scr_buf, __f_bss_base + 0x2f918
	.globl scr_h_size
	.set scr_h_size, __f_bss_base + 0x2f91c
	.globl scr_v_size
	.set scr_v_size, __f_bss_base + 0x2f920
	.globl screen_w
	.set screen_w, __f_bss_base + 0x2f924
	.globl screen_x
	.set screen_x, __f_bss_base + 0x2f928
	.globl set_rotation
	.set set_rotation, __f_bss_base + 0x2f92c
	.globl shmid
	.set shmid, __f_bss_base + 0x2f930
	.globl sound_driver_init
	.set sound_driver_init, __f_bss_base + 0x2f934
	.globl sound_driver_playframe
	.set sound_driver_playframe, __f_bss_base + 0x2f938
	.globl sound_times
	.set sound_times, __f_bss_base + 0x2f93c
	.globl video_driver_deinit
	.set video_driver_deinit, __f_bss_base + 0x2f940
	.globl video_driver_frame
	.set video_driver_frame, __f_bss_base + 0x2f944
	.globl video_driver_get_size
	.set video_driver_get_size, __f_bss_base + 0x2f948
	.globl video_driver_setting
	.set video_driver_setting, __f_bss_base + 0x2f94c
	.globl spi_id
	.set spi_id, __f_bss_base + 0x2f950
	.globl IR_JoyKey
	.set IR_JoyKey, __f_bss_base + 0x2f954
	.globl ChannelIndex
	.set ChannelIndex, __f_bss_base + 0x2f956
	.globl ProtectCode
	.set ProtectCode, __f_bss_base + 0x2f957
	.globl ProtectVer
	.set ProtectVer, __f_bss_base + 0x2f958
	.globl ReturnToMenu
	.set ReturnToMenu, __f_bss_base + 0x2f959
	.globl joy_key_Temp
	.set joy_key_Temp, __f_bss_base + 0x2f95a

