
golden/factory.rkgame.bin:     file format elf32-littlearm


Disassembly of section .text:

002b6c14 <FBA_Load>:
  2b6c14:	e59fc2c4 	ldr	ip, [pc, #708]	@ 2b6ee0 <FBA_Load+0x2cc>
  2b6c18:	e92d4ff0 	push	{r4, r5, r6, r7, r8, r9, sl, fp, lr}
  2b6c1c:	e08fc00c 	add	ip, pc, ip
  2b6c20:	e28cc004 	add	ip, ip, #4
  2b6c24:	e1a0a000 	mov	sl, r0
  2b6c28:	e24ddf4f 	sub	sp, sp, #316	@ 0x13c
  2b6c2c:	e59f62b0 	ldr	r6, [pc, #688]	@ 2b6ee4 <FBA_Load+0x2d0>
  2b6c30:	e8bc000f 	ldm	ip!, {r0, r1, r2, r3}
  2b6c34:	e28d5010 	add	r5, sp, #16
  2b6c38:	e59f82a8 	ldr	r8, [pc, #680]	@ 2b6ee8 <FBA_Load+0x2d4>
  2b6c3c:	e08f6006 	add	r6, pc, r6
  2b6c40:	e1a0e005 	mov	lr, r5
  2b6c44:	e3a04d05 	mov	r4, #320	@ 0x140
  2b6c48:	e3a070f0 	mov	r7, #240	@ 0xf0
  2b6c4c:	e8ae000f 	stmia	lr!, {r0, r1, r2, r3}
  2b6c50:	e8bc000f 	ldm	ip!, {r0, r1, r2, r3}
  2b6c54:	e8ae000f 	stmia	lr!, {r0, r1, r2, r3}
  2b6c58:	e89c0003 	ldm	ip, {r0, r1}
  2b6c5c:	e3a0c000 	mov	ip, #0
  2b6c60:	e59f3284 	ldr	r3, [pc, #644]	@ 2b6eec <FBA_Load+0x2d8>
  2b6c64:	e88e0003 	stm	lr, {r0, r1}
  2b6c68:	e1a0100a 	mov	r1, sl
  2b6c6c:	e7962008 	ldr	r2, [r6, r8]
  2b6c70:	e5824000 	str	r4, [r2]
  2b6c74:	e7962003 	ldr	r2, [r6, r3]
  2b6c78:	e59f3270 	ldr	r3, [pc, #624]	@ 2b6ef0 <FBA_Load+0x2dc>
  2b6c7c:	e5827000 	str	r7, [r2]
  2b6c80:	e7962003 	ldr	r2, [r6, r3]
  2b6c84:	e59f3268 	ldr	r3, [pc, #616]	@ 2b6ef4 <FBA_Load+0x2e0>
  2b6c88:	e5824000 	str	r4, [r2]
  2b6c8c:	e7962003 	ldr	r2, [r6, r3]
  2b6c90:	e59f3260 	ldr	r3, [pc, #608]	@ 2b6ef8 <FBA_Load+0x2e4>
  2b6c94:	e5827000 	str	r7, [r2]
  2b6c98:	e59f225c 	ldr	r2, [pc, #604]	@ 2b6efc <FBA_Load+0x2e8>
  2b6c9c:	e7960003 	ldr	r0, [r6, r3]
  2b6ca0:	e59f3258 	ldr	r3, [pc, #600]	@ 2b6f00 <FBA_Load+0x2ec>
  2b6ca4:	e5804000 	str	r4, [r0]
  2b6ca8:	e7962002 	ldr	r2, [r6, r2]
  2b6cac:	e582c000 	str	ip, [r2]
  2b6cb0:	e7963003 	ldr	r3, [r6, r3]
  2b6cb4:	e1a00003 	mov	r0, r3
  2b6cb8:	e58d300c 	str	r3, [sp, #12]
  2b6cbc:	ebf54a7d 	bl	96b8 <strcpy@plt>
  2b6cc0:	e59d3010 	ldr	r3, [sp, #16]
  2b6cc4:	e5d32000 	ldrb	r2, [r3]
  2b6cc8:	e3520000 	cmp	r2, #0
  2b6ccc:	0a00003b 	beq	2b6dc0 <FBA_Load+0x1ac>
  2b6cd0:	e59f222c 	ldr	r2, [pc, #556]	@ 2b6f04 <FBA_Load+0x2f0>
  2b6cd4:	e28d4038 	add	r4, sp, #56	@ 0x38
  2b6cd8:	e59f9228 	ldr	r9, [pc, #552]	@ 2b6f08 <FBA_Load+0x2f4>
  2b6cdc:	e59f7228 	ldr	r7, [pc, #552]	@ 2b6f0c <FBA_Load+0x2f8>
  2b6ce0:	e7968002 	ldr	r8, [r6, r2]
  2b6ce4:	e08f9009 	add	r9, pc, r9
  2b6ce8:	e59f2220 	ldr	r2, [pc, #544]	@ 2b6f10 <FBA_Load+0x2fc>
  2b6cec:	e08f7007 	add	r7, pc, r7
  2b6cf0:	e08f2002 	add	r2, pc, r2
  2b6cf4:	e58d2008 	str	r2, [sp, #8]
  2b6cf8:	ea00001b 	b	2b6d6c <FBA_Load+0x158>
  2b6cfc:	ebf54ae8 	bl	98a4 <dlsym@plt>
  2b6d00:	e59f320c 	ldr	r3, [pc, #524]	@ 2b6f14 <FBA_Load+0x300>
  2b6d04:	e7963003 	ldr	r3, [r6, r3]
  2b6d08:	e1a02000 	mov	r2, r0
  2b6d0c:	e3520000 	cmp	r2, #0
  2b6d10:	e1a0000a 	mov	r0, sl
  2b6d14:	e5832000 	str	r2, [r3]
  2b6d18:	0a000007 	beq	2b6d3c <FBA_Load+0x128>
  2b6d1c:	e12fff32 	blx	r2
  2b6d20:	e3500000 	cmp	r0, #0
  2b6d24:	e59f01ec 	ldr	r0, [pc, #492]	@ 2b6f18 <FBA_Load+0x304>
  2b6d28:	e08f0000 	add	r0, pc, r0
  2b6d2c:	ba000002 	blt	2b6d3c <FBA_Load+0x128>
  2b6d30:	ebfffb45 	bl	2b5a4c <Load_Proc1>
  2b6d34:	e3500000 	cmp	r0, #0
  2b6d38:	1a000023 	bne	2b6dcc <FBA_Load+0x1b8>
  2b6d3c:	e59f01d8 	ldr	r0, [pc, #472]	@ 2b6f1c <FBA_Load+0x308>
  2b6d40:	e1a01004 	mov	r1, r4
  2b6d44:	e08f0000 	add	r0, pc, r0
  2b6d48:	ebf54c62 	bl	9ed8 <RARCH_LOG>
  2b6d4c:	e59f31cc 	ldr	r3, [pc, #460]	@ 2b6f20 <FBA_Load+0x30c>
  2b6d50:	e08f3003 	add	r3, pc, r3
  2b6d54:	e5930300 	ldr	r0, [r3, #768]	@ 0x300
  2b6d58:	ebf54ada 	bl	98c8 <dlclose@plt>
  2b6d5c:	e5b53004 	ldr	r3, [r5, #4]!
  2b6d60:	e5d32000 	ldrb	r2, [r3]
  2b6d64:	e3520000 	cmp	r2, #0
  2b6d68:	0a000014 	beq	2b6dc0 <FBA_Load+0x1ac>
  2b6d6c:	e1a02008 	mov	r2, r8
  2b6d70:	e1a01009 	mov	r1, r9
  2b6d74:	e1a00004 	mov	r0, r4
  2b6d78:	ebf54a3c 	bl	9670 <sprintf@plt>
  2b6d7c:	e3a01002 	mov	r1, #2
  2b6d80:	e1a00004 	mov	r0, r4
  2b6d84:	ebf54ac9 	bl	98b0 <dlopen@plt>
  2b6d88:	e59f1194 	ldr	r1, [pc, #404]	@ 2b6f24 <FBA_Load+0x310>
  2b6d8c:	e08f1001 	add	r1, pc, r1
  2b6d90:	e3500000 	cmp	r0, #0
  2b6d94:	e5870300 	str	r0, [r7, #768]	@ 0x300
  2b6d98:	1affffd7 	bne	2b6cfc <FBA_Load+0xe8>
  2b6d9c:	ebf54ac6 	bl	98bc <dlerror@plt>
  2b6da0:	e1a01004 	mov	r1, r4
  2b6da4:	e1a02000 	mov	r2, r0
  2b6da8:	e59d0008 	ldr	r0, [sp, #8]
  2b6dac:	ebf54c49 	bl	9ed8 <RARCH_LOG>
  2b6db0:	e5b53004 	ldr	r3, [r5, #4]!
  2b6db4:	e5d32000 	ldrb	r2, [r3]
  2b6db8:	e3520000 	cmp	r2, #0
  2b6dbc:	1affffea 	bne	2b6d6c <FBA_Load+0x158>
  2b6dc0:	e3a00000 	mov	r0, #0
  2b6dc4:	e28ddf4f 	add	sp, sp, #316	@ 0x13c
  2b6dc8:	e8bd8ff0 	pop	{r4, r5, r6, r7, r8, r9, sl, fp, pc}
  2b6dcc:	e59f3154 	ldr	r3, [pc, #340]	@ 2b6f28 <FBA_Load+0x314>
  2b6dd0:	e3a0b000 	mov	fp, #0
  2b6dd4:	e59f0150 	ldr	r0, [pc, #336]	@ 2b6f2c <FBA_Load+0x318>
  2b6dd8:	e7961003 	ldr	r1, [r6, r3]
  2b6ddc:	e08f0000 	add	r0, pc, r0
  2b6de0:	ebfffaf5 	bl	2b59bc <run_process>
  2b6de4:	e59f3144 	ldr	r3, [pc, #324]	@ 2b6f30 <FBA_Load+0x31c>
  2b6de8:	e59d000c 	ldr	r0, [sp, #12]
  2b6dec:	e59f2140 	ldr	r2, [pc, #320]	@ 2b6f34 <FBA_Load+0x320>
  2b6df0:	e7963003 	ldr	r3, [r6, r3]
  2b6df4:	eddf0b37 	vldr	d16, [pc, #220]	@ 2b6ed8 <FBA_Load+0x2c4>
  2b6df8:	e59f1138 	ldr	r1, [pc, #312]	@ 2b6f38 <FBA_Load+0x324>
  2b6dfc:	e8830801 	stm	r3, {r0, fp}
  2b6e00:	e583b008 	str	fp, [r3, #8]
  2b6e04:	e08f1001 	add	r1, pc, r1
  2b6e08:	e58d3004 	str	r3, [sp, #4]
  2b6e0c:	e7962002 	ldr	r2, [r6, r2]
  2b6e10:	e5970300 	ldr	r0, [r7, #768]	@ 0x300
  2b6e14:	edc20b00 	vstr	d16, [r2]
  2b6e18:	ebf54aa1 	bl	98a4 <dlsym@plt>
  2b6e1c:	e59d3004 	ldr	r3, [sp, #4]
  2b6e20:	e2502000 	subs	r2, r0, #0
  2b6e24:	e1a00003 	mov	r0, r3
  2b6e28:	0a000002 	beq	2b6e38 <FBA_Load+0x224>
  2b6e2c:	e12fff32 	blx	r2
  2b6e30:	e150000b 	cmp	r0, fp
  2b6e34:	1a000008 	bne	2b6e5c <FBA_Load+0x248>
  2b6e38:	e59f00fc 	ldr	r0, [pc, #252]	@ 2b6f3c <FBA_Load+0x328>
  2b6e3c:	e3a01000 	mov	r1, #0
  2b6e40:	e08f0000 	add	r0, pc, r0
  2b6e44:	ebfffadc 	bl	2b59bc <run_process>
  2b6e48:	e59f00f0 	ldr	r0, [pc, #240]	@ 2b6f40 <FBA_Load+0x32c>
  2b6e4c:	e3a01000 	mov	r1, #0
  2b6e50:	e08f0000 	add	r0, pc, r0
  2b6e54:	ebfffad8 	bl	2b59bc <run_process>
  2b6e58:	eaffffb7 	b	2b6d3c <FBA_Load+0x128>
  2b6e5c:	e59f00e0 	ldr	r0, [pc, #224]	@ 2b6f44 <FBA_Load+0x330>
  2b6e60:	e1a01004 	mov	r1, r4
  2b6e64:	e59d200c 	ldr	r2, [sp, #12]
  2b6e68:	e08f0000 	add	r0, pc, r0
  2b6e6c:	ebf54c19 	bl	9ed8 <RARCH_LOG>
  2b6e70:	ebfffb64 	bl	2b5c08 <Load_Proc2>
  2b6e74:	e59f20cc 	ldr	r2, [pc, #204]	@ 2b6f48 <FBA_Load+0x334>
  2b6e78:	e59f30cc 	ldr	r3, [pc, #204]	@ 2b6f4c <FBA_Load+0x338>
  2b6e7c:	e7962002 	ldr	r2, [r6, r2]
  2b6e80:	e582b000 	str	fp, [r2]
  2b6e84:	e7963003 	ldr	r3, [r6, r3]
  2b6e88:	e5933000 	ldr	r3, [r3]
  2b6e8c:	e153000b 	cmp	r3, fp
  2b6e90:	0a00000c 	beq	2b6ec8 <FBA_Load+0x2b4>
  2b6e94:	e59f30b4 	ldr	r3, [pc, #180]	@ 2b6f50 <FBA_Load+0x33c>
  2b6e98:	e7964003 	ldr	r4, [r6, r3]
  2b6e9c:	e5940000 	ldr	r0, [r4]
  2b6ea0:	e3500000 	cmp	r0, #0
  2b6ea4:	0a000001 	beq	2b6eb0 <FBA_Load+0x29c>
  2b6ea8:	ebf54a2c 	bl	9760 <free@plt>
  2b6eac:	e584b000 	str	fp, [r4]
  2b6eb0:	e3a00cff 	mov	r0, #65280	@ 0xff00
  2b6eb4:	ebf55ae4 	bl	da4c <video_driver_set_rotation>
  2b6eb8:	e59f0094 	ldr	r0, [pc, #148]	@ 2b6f54 <FBA_Load+0x340>
  2b6ebc:	e08f0000 	add	r0, pc, r0
  2b6ec0:	ebf54c04 	bl	9ed8 <RARCH_LOG>
  2b6ec4:	eaffffbd 	b	2b6dc0 <FBA_Load+0x1ac>
  2b6ec8:	e3a00cff 	mov	r0, #65280	@ 0xff00
  2b6ecc:	ebf55ade 	bl	da4c <video_driver_set_rotation>
  2b6ed0:	eafffff6 	b	2b6eb0 <FBA_Load+0x29c>
  2b6ed4:	e320f000 	nop	{0}
	...
  2b6ee0:	000f9504 	.word	0x000f9504
  2b6ee4:	000fb380 	.word	0x000fb380
  2b6ee8:	ffffff50 	.word	0xffffff50
  2b6eec:	ffffff54 	.word	0xffffff54
  2b6ef0:	ffffff58 	.word	0xffffff58
  2b6ef4:	ffffff5c 	.word	0xffffff5c
  2b6ef8:	ffffff60 	.word	0xffffff60
  2b6efc:	ffffff64 	.word	0xffffff64
  2b6f00:	ffffff68 	.word	0xffffff68
  2b6f04:	fffffd40 	.word	0xfffffd40
  2b6f08:	00026f3c 	.word	0x00026f3c
  2b6f0c:	00118994 	.word	0x00118994
  2b6f10:	00026da4 	.word	0x00026da4
  2b6f14:	ffffff74 	.word	0xffffff74
  2b6f18:	00024f84 	.word	0x00024f84
  2b6f1c:	00026f2c 	.word	0x00026f2c
  2b6f20:	00118930 	.word	0x00118930
  2b6f24:	00026ea0 	.word	0x00026ea0
  2b6f28:	ffffff78 	.word	0xffffff78
  2b6f2c:	00026e64 	.word	0x00026e64
  2b6f30:	ffffff6c 	.word	0xffffff6c
  2b6f34:	fffffea0 	.word	0xfffffea0
  2b6f38:	00026d78 	.word	0x00026d78
  2b6f3c:	00026cec 	.word	0x00026cec
  2b6f40:	00026cf0 	.word	0x00026cf0
  2b6f44:	00026df4 	.word	0x00026df4
  2b6f48:	fffffec8 	.word	0xfffffec8
  2b6f4c:	fffffd4c 	.word	0xfffffd4c
  2b6f50:	fffffed4 	.word	0xfffffed4
  2b6f54:	00026dc4 	.word	0x00026dc4
D0äÄãD