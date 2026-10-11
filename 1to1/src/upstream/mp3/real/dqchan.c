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
 * August 2003
 *
 * dqchan.c - dequantization of transform coefficients
 **************************************************************************************/

#include "coder.h"
#include "assembly.h"

typedef int ARRAY3[3];	/* for short-block reordering */

/* optional pre-emphasis for high-frequency scale factor bands */
/* ★★★ 2026-10-04（第 134 轮）T09 系统性根修 自动迁移（tools/migrate_dup_image_tables.py）：
 *   原为 `static char preTab[22] = {...}` ⇒ 编进自有 .rodata/.data，
 *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:275 已有的镜像别名
 *   `.set preTab, __f_rodata_base + 0x85d0`（= 工厂地址 共 22 字节）。
 *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。
 *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。
 *   回退：git checkout /workspace/1to1/src/upstream/mp3/real/dqchan.c
 */
extern const char preTab[];


/* pow(2,-i/4) for i=0..3, Q31 format */
/* ★★★ 2026-10-04（第 134 轮）T09 系统性根修 自动迁移（tools/migrate_dup_image_tables.py）：
 *   原为 `static int pow14[4] = {...}` ⇒ 编进自有 .rodata/.data，
 *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:263 已有的镜像别名
 *   `.set pow14, __f_rodata_base + 0x84c0`（= 工厂地址 共 16 字节）。
 *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。
 *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。
 *   回退：git checkout /workspace/1to1/src/upstream/mp3/real/dqchan.c
 */
extern const int pow14[];


/* pow(2,-i/4) * pow(j,4/3) for i=0..3 j=0..15, Q25 format */
static const int pow43_14[4][16] = {
{	0x00000000, 0x10000000, 0x285145f3, 0x453a5cdb, /* Q28 */
	0x0cb2ff53, 0x111989d6, 0x15ce31c8, 0x1ac7f203, 
	0x20000000, 0x257106b9, 0x2b16b4a3, 0x30ed74b4, 
	0x36f23fa5, 0x3d227bd3, 0x437be656, 0x49fc823c, },

{	0x00000000, 0x0d744fcd, 0x21e71f26, 0x3a36abd9, 
	0x0aadc084, 0x0e610e6e, 0x12560c1d, 0x168523cf, 
	0x1ae89f99, 0x1f7c03a4, 0x243bae49, 0x29249c67, 
	0x2e34420f, 0x33686f85, 0x38bf3dff, 0x3e370182, },

{	0x00000000, 0x0b504f33, 0x1c823e07, 0x30f39a55, 
	0x08facd62, 0x0c176319, 0x0f6b3522, 0x12efe2ad, 
	0x16a09e66, 0x1a79a317, 0x1e77e301, 0x2298d5b4, 
	0x26da56fc, 0x2b3a902a, 0x2fb7e7e7, 0x3450f650, },

{	0x00000000, 0x09837f05, 0x17f910d7, 0x2929c7a9, 
	0x078d0dfa, 0x0a2ae661, 0x0cf73154, 0x0fec91cb, 
	0x1306fe0a, 0x16434a6c, 0x199ee595, 0x1d17ae3d, 
	0x20abd76a, 0x2459d551, 0x28204fbb, 0x2bfe1808, },
};

/* pow(j,4/3) for j=16..63, Q23 format */
/* ★★★ 2026-10-04（第 134 轮）T09 系统性根修 自动迁移（tools/migrate_dup_image_tables.py）：
 *   原为 `static int pow43[] = {...}` ⇒ 编进自有 .rodata/.data，
 *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:266 已有的镜像别名
 *   `.set pow43, __f_rodata_base + 0x84d0`（= 工厂地址 共 192 字节）。
 *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。
 *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。
 *   回退：git checkout /workspace/1to1/src/upstream/mp3/real/dqchan.c
 */
extern const int pow43[];


/* sqrt(0.5) in Q31 format */
#define SQRTHALF 0x5a82799a

/*
 * Minimax polynomial approximation to pow(x, 4/3), over the range
 *  poly43lo: x = [0.5, 0.7071]
 *  poly43hi: x = [0.7071, 1.0]
 *
 * Relative error < 1E-7
 * Coefs are scaled by 4, 2, 1, 0.5, 0.25
 */
static const int poly43lo[5] = { 0x29a0bda9, 0xb02e4828, 0x5957aa1b, 0x236c498d, 0xff581859 };
static const int poly43hi[5] = { 0x10852163, 0xd333f6a4, 0x46e9408b, 0x27c2cef0, 0xfef577b4 };

/* pow(2, i*4/3) as exp and frac */
/* ★★★ 2026-10-04（第 134 轮）T09 系统性根修 自动迁移（tools/migrate_dup_image_tables.py）：
 *   原为 `static int pow2exp[8] = {...}` ⇒ 编进自有 .rodata/.data，
 *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:272 已有的镜像别名
 *   `.set pow2exp, __f_rodata_base + 0x85b0`（= 工厂地址 共 32 字节）。
 *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。
 *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。
 *   回退：git checkout /workspace/1to1/src/upstream/mp3/real/dqchan.c
 */
extern const int pow2exp[];


/* ★★★ 2026-10-04（第 134 轮）T09 系统性根修 自动迁移（tools/migrate_dup_image_tables.py）：
 *   原为 `static int pow2frac[8] = {...}` ⇒ 编进自有 .rodata/.data，
 *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:269 已有的镜像别名
 *   `.set pow2frac, __f_rodata_base + 0x8590`（= 工厂地址 共 32 字节）。
 *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。
 *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。
 *   回退：git checkout /workspace/1to1/src/upstream/mp3/real/dqchan.c
 */
extern const int pow2frac[];


/**************************************************************************************
 * Function:    DequantBlock
 *
 * Description: Ken's highly-optimized, low memory dequantizer performing the operation
 *              y = pow(x, 4.0/3.0) * pow(2, 25 - scale/4.0)
 *
 * Inputs:      input buffer of decode Huffman codewords (signed-magnitude)
 *              output buffer of same length (in-place (outbuf = inbuf) is allowed)
 *              number of samples
 *              
 * Outputs:     dequantized samples in Q25 format
 *
 * Return:      bitwise-OR of the unsigned outputs (for guard bit calculations)
 **************************************************************************************/
static int DequantBlock(int *inbuf, int *outbuf, int num, int scale)
{
	int tab4[4];
	int scalef, scalei, shift;
	int sx, x, y;
	int mask = 0;
	const int *tab16, *coef;

	tab16 = pow43_14[scale & 0x3];
	scalef = pow14[scale & 0x3];
	scalei = MIN(scale >> 2, 31);	/* smallest input scale = -47, so smallest scalei = -12 */

	/* cache first 4 values */
	shift = MIN(scalei + 3, 31);
	shift = MAX(shift, 0);
	tab4[0] = 0;
	tab4[1] = tab16[1] >> shift;
	tab4[2] = tab16[2] >> shift;
	tab4[3] = tab16[3] >> shift;

	do {

		sx = *inbuf++;
		x = sx & 0x7fffffff;	/* sx = sign|mag */

		if (x < 4) {

			y = tab4[x];

		} else if (x < 16) {

			y = tab16[x];
			y = (scalei < 0) ? y << -scalei : y >> scalei;

		} else {

			if (x < 64) {

				y = pow43[x-16];

				/* fractional scale */
				y = MULSHIFT32(y, scalef);
				shift = scalei - 3;

			} else {

				/* normalize to [0x40000000, 0x7fffffff] */
				x <<= 17;
				shift = 0;
				if (x < 0x08000000)
					x <<= 4, shift += 4;
				if (x < 0x20000000)
					x <<= 2, shift += 2;
				if (x < 0x40000000)
					x <<= 1, shift += 1;

				coef = (x < SQRTHALF) ? poly43lo : poly43hi;

				/* polynomial */
				y = coef[0];
				y = MULSHIFT32(y, x) + coef[1];
				y = MULSHIFT32(y, x) + coef[2];
				y = MULSHIFT32(y, x) + coef[3];
				y = MULSHIFT32(y, x) + coef[4];
				y = MULSHIFT32(y, pow2frac[shift]) << 3;

				/* fractional scale */
				y = MULSHIFT32(y, scalef);
				shift = scalei - pow2exp[shift];
			}

			/* integer scale */
			if (shift < 0) {
				shift = -shift;
				if (y > (0x7fffffff >> shift))
					y = 0x7fffffff;		/* clip */
				else
					y <<= shift;
			} else {
				y >>= shift;
			}
		}

		/* sign and store */
		mask |= y;
		*outbuf++ = (sx < 0) ? -y : y;

	} while (--num);

	return mask;
}

/**************************************************************************************
 * Function:    DequantChannel
 *
 * Description: dequantize one granule, one channel worth of decoded Huffman codewords
 *
 * Inputs:      sample buffer (decoded Huffman codewords), length = MAX_NSAMP samples
 *              work buffer for reordering short-block, length = MAX_REORDER_SAMPS
 *                samples (3 * width of largest short-block critical band)
 *              non-zero bound for this channel/granule
 *              valid FrameHeader, SideInfoSub, ScaleFactorInfoSub, and CriticalBandInfo
 *                structures for this channel/granule
 *
 * Outputs:     MAX_NSAMP dequantized samples in sampleBuf
 *              updated non-zero bound (indicating which samples are != 0 after DQ)
 *              filled-in cbi structure indicating start and end critical bands
 *
 * Return:      minimum number of guard bits in dequantized sampleBuf
 *
 * Notes:       dequantized samples in Q(DQ_FRACBITS_OUT) format 
 **************************************************************************************/
int DequantChannel(int *sampleBuf, int *workBuf, int *nonZeroBound, FrameHeader *fh, SideInfoSub *sis, 
					ScaleFactorInfoSub *sfis, CriticalBandInfo *cbi)
{
	int i, j, w, cb;
	/* int cbStartL, cbEndL, cbStartS, cbEndS; */
	int cbEndL, cbStartS, cbEndS;
	int nSamps, nonZero, sfactMultiplier, gbMask;
	int globalGain, gainI;
	int cbMax[3];
	ARRAY3 *buf;    /* short block reorder */
	
	/* set default start/end points for short/long blocks - will update with non-zero cb info */
	if (sis->blockType == 2) {
		/* cbStartL = 0; */
		if (sis->mixedBlock) { 
			cbEndL = (fh->ver == MPEG1 ? 8 : 6); 
			cbStartS = 3; 
		} else {
			cbEndL = 0; 
			cbStartS = 0;
		}
		cbEndS = 13;
	} else {
		/* long block */
		/* cbStartL = 0; */
		cbEndL =   22;
		cbStartS = 13;
		cbEndS =   13;
	}
	cbMax[2] = cbMax[1] = cbMax[0] = 0;
	gbMask = 0;
	i = 0;

	/* sfactScale = 0 --> quantizer step size = 2
	 * sfactScale = 1 --> quantizer step size = sqrt(2)
	 *   so sfactMultiplier = 2 or 4 (jump through globalGain by powers of 2 or sqrt(2))
	 */
	sfactMultiplier = 2 * (sis->sfactScale + 1);

	/* offset globalGain by -2 if midSide enabled, for 1/sqrt(2) used in MidSideProc()
	 *  (DequantBlock() does 0.25 * gainI so knocking it down by two is the same as 
	 *   dividing every sample by sqrt(2) = multiplying by 2^-.5)
	 */
	globalGain = sis->globalGain;
	if (fh->modeExt >> 1)
		 globalGain -= 2;
	globalGain += IMDCT_SCALE;		/* scale everything by sqrt(2), for fast IMDCT36 */

	/* long blocks */
	for (cb = 0; cb < cbEndL; cb++) {

		nonZero = 0;
		nSamps = fh->sfBand->l[cb + 1] - fh->sfBand->l[cb];
		gainI = 210 - globalGain + sfactMultiplier * (sfis->l[cb] + (sis->preFlag ? (int)preTab[cb] : 0));

		nonZero |= DequantBlock(sampleBuf + i, sampleBuf + i, nSamps, gainI);
		i += nSamps;

		/* update highest non-zero critical band */
		if (nonZero) 
			cbMax[0] = cb;
		gbMask |= nonZero;

		if (i >= *nonZeroBound) 
			break;
	}

	/* set cbi (Type, EndS[], EndSMax will be overwritten if we proceed to do short blocks) */
	cbi->cbType = 0;			/* long only */
	cbi->cbEndL  = cbMax[0];
	cbi->cbEndS[0] = cbi->cbEndS[1] = cbi->cbEndS[2] = 0;
	cbi->cbEndSMax = 0;

	/* early exit if no short blocks */
	if (cbStartS >= 12) 
		return CLZ(gbMask) - 1;
	
	/* short blocks */
	cbMax[2] = cbMax[1] = cbMax[0] = cbStartS;
	for (cb = cbStartS; cb < cbEndS; cb++) {

		nSamps = fh->sfBand->s[cb + 1] - fh->sfBand->s[cb];
		for (w = 0; w < 3; w++) {
			nonZero =  0;
			gainI = 210 - globalGain + 8*sis->subBlockGain[w] + sfactMultiplier*(sfis->s[cb][w]);

			nonZero |= DequantBlock(sampleBuf + i + nSamps*w, workBuf + nSamps*w, nSamps, gainI);

			/* update highest non-zero critical band */
			if (nonZero)
				cbMax[w] = cb;
			gbMask |= nonZero;
		}

		/* reorder blocks */
		buf = (ARRAY3 *)(sampleBuf + i);
		i += 3*nSamps;
		for (j = 0; j < nSamps; j++) {
			buf[j][0] = workBuf[0*nSamps + j];
			buf[j][1] = workBuf[1*nSamps + j];
			buf[j][2] = workBuf[2*nSamps + j];
		}

		ASSERT(3*nSamps <= MAX_REORDER_SAMPS);

		if (i >= *nonZeroBound) 
			break;
	}

	/* i = last non-zero INPUT sample processed, which corresponds to highest possible non-zero 
	 *     OUTPUT sample (after reorder)
	 * however, the original nzb is no longer necessarily true
	 *   for each cb, buf[][] is updated with 3*nSamps samples (i increases 3*nSamps each time)
	 *   (buf[j + 1][0] = 3 (input) samples ahead of buf[j][0])
     * so update nonZeroBound to i
	 */
	*nonZeroBound = i;

	ASSERT(*nonZeroBound <= MAX_NSAMP);

	cbi->cbType = (sis->mixedBlock ? 2 : 1);	/* 2 = mixed short/long, 1 = short only */

	cbi->cbEndS[0] = cbMax[0];
	cbi->cbEndS[1] = cbMax[1];
	cbi->cbEndS[2] = cbMax[2];

	cbi->cbEndSMax = cbMax[0];
	cbi->cbEndSMax = MAX(cbi->cbEndSMax, cbMax[1]);
	cbi->cbEndSMax = MAX(cbi->cbEndSMax, cbMax[2]);

	return CLZ(gbMask) - 1;
}

