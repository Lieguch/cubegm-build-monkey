/* ***** BEGIN LICENSE BLOCK ***** 
 * Version: RCSL 1.0/RPSL 1.0 
 *  
 * Portions Copyright (c) 1995-2002 RealNetworks, Inc. All Rights Reserved. 
 *      
 * The contents of this file, and the files included with this file, are 
 * subject to the current version of the RealNetworks Public Source License 
 * Version 1.0 (the "RPSL") available at 
 * http://www.helixcommunity.org/content/rpsl unless you have licensed 
 * the file under the RealNetworks Community Source License Version 1.0 
 * (the "RCSL") available at http://www.helixcommunity.org/content/rcsl, 
 * in which case the RCSL will apply. You may also obtain the license terms 
 * directly from RealNetworks.  You may not use this file except in 
 * compliance with the RPSL or, if you have a valid RCSL with RealNetworks 
 * applicable to this file, the RCSL.  Please see the applicable RPSL or 
 * RCSL for the rights, obligations and limitations governing use of the 
 * contents of the file.  
 *  
 * This file is part of the Helix DNA Technology. RealNetworks is the 
 * developer of the Original Code and owns the copyrights in the portions 
 * it created. 
 *  
 * This file, and the files included with this file, is distributed and made 
 * available on an 'AS IS' basis, WITHOUT WARRANTY OF ANY KIND, EITHER 
 * EXPRESS OR IMPLIED, AND REALNETWORKS HEREBY DISCLAIMS ALL SUCH WARRANTIES, 
 * INCLUDING WITHOUT LIMITATION, ANY WARRANTIES OF MERCHANTABILITY, FITNESS 
 * FOR A PARTICULAR PURPOSE, QUIET ENJOYMENT OR NON-INFRINGEMENT. 
 * 
 * Technology Compatibility Kit Test Suite(s) Location: 
 *    http://www.helixcommunity.org/content/tck 
 * 
 * Contributor(s): 
 *  
 * ***** END LICENSE BLOCK ***** */ 

/**************************************************************************************
 * Fixed-point MP3 decoder
 * Jon Recker (jrecker@real.com), Ken Cooke (kenc@real.com)
 * June 2003
 *
 * dct32.c - optimized implementations of 32-point DCT for matrixing stage of 
 *             polyphase filter
 **************************************************************************************/

#include "coder.h"
#include "assembly.h"

#define COS0_0  0x4013c251	/* Q31 */
#define COS0_1  0x40b345bd	/* Q31 */
#define COS0_2  0x41fa2d6d	/* Q31 */
#define COS0_3  0x43f93421	/* Q31 */
#define COS0_4  0x46cc1bc4	/* Q31 */
#define COS0_5  0x4a9d9cf0	/* Q31 */
#define COS0_6  0x4fae3711	/* Q31 */
#define COS0_7  0x56601ea7	/* Q31 */
#define COS0_8  0x5f4cf6eb	/* Q31 */
#define COS0_9  0x6b6fcf26	/* Q31 */
#define COS0_10 0x7c7d1db3	/* Q31 */
#define COS0_11 0x4ad81a97	/* Q30 */
#define COS0_12 0x5efc8d96	/* Q30 */
#define COS0_13 0x41d95790	/* Q29 */
#define COS0_14 0x6d0b20cf	/* Q29 */
#define COS0_15 0x518522fb	/* Q27 */

#define COS1_0  0x404f4672	/* Q31 */
#define COS1_1  0x42e13c10	/* Q31 */
#define COS1_2  0x48919f44	/* Q31 */
#define COS1_3  0x52cb0e63	/* Q31 */
#define COS1_4  0x64e2402e	/* Q31 */
#define COS1_5  0x43e224a9	/* Q30 */
#define COS1_6  0x6e3c92c1	/* Q30 */
#define COS1_7  0x519e4e04	/* Q28 */

#define COS2_0  0x4140fb46	/* Q31 */
#define COS2_1  0x4cf8de88	/* Q31 */
#define COS2_2  0x73326bbf	/* Q31 */
#define COS2_3  0x52036742	/* Q29 */

#define COS3_0  0x4545e9ef	/* Q31 */
#define COS3_1  0x539eba45	/* Q30 */

#define COS4_0  0x5a82799a	/* Q31 */

/* ★★★ 2026-10-04（第 134 轮）T09 根修 #4：删掉重复的 `static const dcttab[48]` 定义，
 * 改为引用 `src/data/factory_image.S` 里**已存在**的镜像别名。
 *
 * 根因（取证闭合，与第 131 轮 `default_core_list` **完全同型**）：
 *   ① 工厂 `dcttab` @ 0x002e428c，size 0xc0=192，`.rodata`，**LOCAL**
 *      —— 见 ledger/factory_globals.tsv:56。
 *   ② 镜像别名**早就生成好了**（factory_image.S:277-279）：
 *        .globl dcttab
 *        .set  dcttab, __f_rodata_base + 0x85e8      ⇒ 0x2e428c（与工厂逐位一致）
 *   ③ 但本文件原来又写了一份 `static const int dcttab[48] = {...}`，
 *      编进**自有 .rodata** @ 0x4d837c，**LOCAL 符号在汇编层遮蔽了上面的 .globl 别名**
 *      ⇒ 产物里同名两份：0x2e428c(GLOBAL, 镜像) + 0x4d837c(LOCAL, C 定义)。
 *   ④ 实测两份内容与工厂**逐字节相同**（192/192，前 16 字节
 *      `51c21340fb22855172464f40bd45b340` 三方一致）⇒ 纯重复副本，
 *      唯一问题是**代码读的是错地址那份**。
 *   ⑤ 后果（diff_exec 第 133 轮权威报告）：
 *      `xmp3_FDCT32 [strs] data-reads 仅F=[] 仅O=['dcttab+100:4:R@0x4d83e0' ...]`。
 *
 * 为何不改判据而是改绑定：工厂 GLOBAL/LOCAL 数据必须落在工厂地址（本项目纪律，
 *   GAP 17.14 + tools/dup_sym_gate.py 检查 3）。放宽判据会掩盖同族的真缺陷。
 * 为何不用 `&dcttab[0]` 之类的绕路：那样仍是 LOCAL 副本，地址不变。
 * 校验：`xmp3_FDCT32` 只把它当只读查表用（`const int *cptr = dcttab;`），
 *   内容由镜像提供逐字节相同 ⇒ 行为等价，且从此与工厂读同一地址。
 * 回退：git checkout src/upstream/mp3/real/dct32.c（或删掉本 extern 换回原定义块）。
 */
extern const int dcttab[];	/* 48 项 × 4B = 192 B；定义见 src/data/factory_image.S */

#define D32FP(i, s0, s1, s2) { \
    a0 = buf[i];			a3 = buf[31-i]; \
	a1 = buf[15-i];			a2 = buf[16+i]; \
    b0 = a0 + a3;			b3 = MULSHIFT32(*cptr++, a0 - a3) << (s0);	\
	b1 = a1 + a2;			b2 = MULSHIFT32(*cptr++, a1 - a2) << (s1);	\
	buf[i] = b0 + b1;		buf[15-i] = MULSHIFT32(*cptr,   b0 - b1) << (s2); \
	buf[16+i] = b2 + b3;    buf[31-i] = MULSHIFT32(*cptr++, b3 - b2) << (s2); \
}

/**************************************************************************************
 * Function:    FDCT32
 *
 * Description: Ken's highly-optimized 32-point DCT (radix-4 + radix-8) 
 *
 * Inputs:      input buffer, length = 32 samples
 *              require at least 6 guard bits in input vector x to avoid possibility
 *                of overflow in internal calculations (see bbtest_imdct test app)
 *              buffer offset and oddblock flag for polyphase filter input buffer
 *              number of guard bits in input
 *
 * Outputs:     output buffer, data copied and interleaved for polyphase filter
 *              no guarantees about number of guard bits in output
 *
 * Return:      none
 *
 * Notes:       number of muls = 4*8 + 12*4 = 80
 *              final stage of DCT is hardcoded to shuffle data into the proper order
 *                for the polyphase filterbank
 *              fully unrolled stage 1, for max precision (scale the 1/cos() factors
 *                differently, depending on magnitude)
 *              guard bit analysis verified by exhaustive testing of all 2^32 
 *                combinations of max pos/max neg values in x[]
 *
 * TODO:        code organization and optimization for ARM
 *              possibly interleave stereo (cut # of coef loads in half - may not have
 *                enough registers)
 **************************************************************************************/
void FDCT32(int *buf, int *dest, int offset, int oddBlock, int gb)
{
    int i, s, tmp, es;
    const int *cptr = dcttab;
    int a0, a1, a2, a3, a4, a5, a6, a7;
    int b0, b1, b2, b3, b4, b5, b6, b7;
	int *d;

	/* scaling - ensure at least 6 guard bits for DCT 
	 * (in practice this is already true 99% of time, so this code is
	 *  almost never triggered)
	 */
	es = 0;
	if (gb < 6) {
		es = 6 - gb;
		for (i = 0; i < 32; i++)
			buf[i] >>= es;
	}

	/* first pass */    
	D32FP(0, 1, 5, 1);
	D32FP(1, 1, 3, 1);
	D32FP(2, 1, 3, 1);
	D32FP(3, 1, 2, 1);
	D32FP(4, 1, 2, 1);
	D32FP(5, 1, 1, 2);
	D32FP(6, 1, 1, 2);
	D32FP(7, 1, 1, 4);

	/* second pass */
	for (i = 4; i > 0; i--) {
		a0 = buf[0]; 	    a7 = buf[7];		a3 = buf[3];	    a4 = buf[4];
		b0 = a0 + a7;	    b7 = MULSHIFT32(*cptr++, a0 - a7) << 1;
		b3 = a3 + a4;	    b4 = MULSHIFT32(*cptr++, a3 - a4) << 3;
		a0 = b0 + b3;	    a3 = MULSHIFT32(*cptr,   b0 - b3) << 1;
		a4 = b4 + b7;		a7 = MULSHIFT32(*cptr++, b7 - b4) << 1;

		a1 = buf[1];	    a6 = buf[6];	    a2 = buf[2];	    a5 = buf[5];
		b1 = a1 + a6;	    b6 = MULSHIFT32(*cptr++, a1 - a6) << 1;
		b2 = a2 + a5;	    b5 = MULSHIFT32(*cptr++, a2 - a5) << 1;
		a1 = b1 + b2;		a2 = MULSHIFT32(*cptr,   b1 - b2) << 2;
		a5 = b5 + b6;	    a6 = MULSHIFT32(*cptr++, b6 - b5) << 2;

		b0 = a0 + a1;	    b1 = MULSHIFT32(COS4_0, a0 - a1) << 1;
		b2 = a2 + a3;	    b3 = MULSHIFT32(COS4_0, a3 - a2) << 1;
		buf[0] = b0;	    buf[1] = b1;
		buf[2] = b2 + b3;	buf[3] = b3;

		b4 = a4 + a5;	    b5 = MULSHIFT32(COS4_0, a4 - a5) << 1;
		b6 = a6 + a7;	    b7 = MULSHIFT32(COS4_0, a7 - a6) << 1;
		b6 += b7;
		buf[4] = b4 + b6;	buf[5] = b5 + b7;
		buf[6] = b5 + b6;	buf[7] = b7;

		buf += 8;
	}
	buf -= 32;	/* reset */

	/* sample 0 - always delayed one block */
	d = dest + 64*16 + ((offset - oddBlock) & 7) + (oddBlock ? 0 : VBUF_LENGTH);
	s = buf[ 0];				d[0] = d[8] = s;
    
	/* samples 16 to 31 */
	d = dest + offset + (oddBlock ? VBUF_LENGTH  : 0);

	s = buf[ 1];				d[0] = d[8] = s;	d += 64;

	tmp = buf[25] + buf[29];
	s = buf[17] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[ 9] + buf[13];		d[0] = d[8] = s;	d += 64;
	s = buf[21] + tmp;			d[0] = d[8] = s;	d += 64;

	tmp = buf[29] + buf[27];
	s = buf[ 5];				d[0] = d[8] = s;	d += 64;
	s = buf[21] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[13] + buf[11];		d[0] = d[8] = s;	d += 64;
	s = buf[19] + tmp;			d[0] = d[8] = s;	d += 64;

	tmp = buf[27] + buf[31];
	s = buf[ 3];				d[0] = d[8] = s;	d += 64;
	s = buf[19] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[11] + buf[15];		d[0] = d[8] = s;	d += 64;
	s = buf[23] + tmp;			d[0] = d[8] = s;	d += 64;

	tmp = buf[31];
	s = buf[ 7];				d[0] = d[8] = s;	d += 64;
	s = buf[23] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[15];				d[0] = d[8] = s;	d += 64;
	s = tmp;					d[0] = d[8] = s;

	/* samples 16 to 1 (sample 16 used again) */
	d = dest + 16 + ((offset - oddBlock) & 7) + (oddBlock ? 0 : VBUF_LENGTH);

	s = buf[ 1];				d[0] = d[8] = s;	d += 64;

	tmp = buf[30] + buf[25];
	s = buf[17] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[14] + buf[ 9];		d[0] = d[8] = s;	d += 64;
	s = buf[22] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[ 6];				d[0] = d[8] = s;	d += 64;

	tmp = buf[26] + buf[30];
	s = buf[22] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[10] + buf[14];		d[0] = d[8] = s;	d += 64;
	s = buf[18] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[ 2];				d[0] = d[8] = s;	d += 64;

	tmp = buf[28] + buf[26];
	s = buf[18] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[12] + buf[10];		d[0] = d[8] = s;	d += 64;
	s = buf[20] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[ 4];				d[0] = d[8] = s;	d += 64;

	tmp = buf[24] + buf[28];
	s = buf[20] + tmp;			d[0] = d[8] = s;	d += 64;
	s = buf[ 8] + buf[12];		d[0] = d[8] = s;	d += 64;
	s = buf[16] + tmp;			d[0] = d[8] = s;

	/* this is so rarely invoked that it's not worth making two versions of the output
	 *   shuffle code (one for no shift, one for clip + variable shift) like in IMDCT
	 * here we just load, clip, shift, and store on the rare instances that es != 0
	 */
	if (es) {
		d = dest + 64*16 + ((offset - oddBlock) & 7) + (oddBlock ? 0 : VBUF_LENGTH);
		s = d[0];	CLIP_2N(s, 31 - es);	d[0] = d[8] = (s << es);
	
		d = dest + offset + (oddBlock ? VBUF_LENGTH  : 0);
		for (i = 16; i <= 31; i++) {
			s = d[0];	CLIP_2N(s, 31 - es);	d[0] = d[8] = (s << es);	d += 64;
		}

		d = dest + 16 + ((offset - oddBlock) & 7) + (oddBlock ? 0 : VBUF_LENGTH);
		for (i = 15; i >= 0; i--) {
			s = d[0];	CLIP_2N(s, 31 - es);	d[0] = d[8] = (s << es);	d += 64;
		}
	}
}
