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
 * buffers.c - allocation and freeing of internal MP3 decoder buffers
 *
 * All memory allocation for the codec is done in this file, so if you don't want 
 *  to use other the default system malloc() and free() for heap management this is 
 *  the only file you'll need to change.
 **************************************************************************************/

#define USE_STATIC      1

#include "coder.h"

#if USE_STATIC
/* 1:1：这些状态的存储由工厂数据镜像提供（工厂 symtab 均为 g O .bss：
   mp3DecInfo@0x003dfffc / mi@0x003d99cc / hi@0x003dcdec / di@0x003e07ec /
   fh@0x003e1830 / sbi,sfi,si 同区），此处仅作声明，避免与之重复定义。 */
extern MP3DecInfo mp3DecInfo;
extern SubbandInfo sbi;
extern IMDCTInfo mi;
extern HuffmanInfo hi;
extern DequantInfo di;
extern ScaleFactorInfo sfi;
extern SideInfo si;
extern FrameHeader fh;
#else
#include "stdlib.h" 
#endif

/**************************************************************************************
 * Function:    ClearBuffer
 *
 * Description: fill buffer with 0's
 *
 * Inputs:      pointer to buffer
 *              number of bytes to fill with 0
 *
 * Outputs:     cleared buffer
 *
 * Return:      none
 *
 * Notes:       slow, platform-independent equivalent to memset(buf, 0, nBytes)
 *
 * ---- 2026-10-05（第 144 轮）工厂形态对齐：两处改动，均有铁证，勿删 ----
 *
 * 【证据 1：工厂侧】golden/factory.rkgame.bin
 *   ClearBuffer = 0x002bdefc / **32B / GLOBAL FUNC**（readelf -sW 实测），
 *   函数体是 8 条指令的**逐字节 strb 循环**（cmp r1,#0 / bxle lr / add r1,r0,r1
 *   / mov r3,#0 / strb r3,[r0],#1 / cmp r0,r1 / bne）。
 *   `xmp3_AllocateBuffers`（0x2bdf1c）的 **8 个 bl 全部指向 ClearBuffer**。
 *
 * 【证据 2：我方侧（改前）】
 *   1) clang 把上面这个 for 循环识别成 memset ⇒ 14 个调用点全部改指向
 *      **memset PLT 桩**（`bl 401620`，落在 .plt 0x401420+0x200），
 *      且函数体被替换成 `b <memset>` 尾调用（20B，零 strb）。
 *   2) `static` 使它无法成为 GLOBAL 符号，与工厂可被 `bl` 的形态不符。
 *
 * 【改法与为什么不用 flag】
 *   - `__attribute__((no_builtin("memset")))`：clang 官方属性，**仅作用于本函数体**。
 *     第 144 轮全量 A/B 已否决 flag 方案（`-fno-builtin-memset` → DIVERGE 17→19 净恶化，
 *     且对本函数零效应：它只拦"编译器自己合成 memset"，管不到"函数体内 idiom 识别"）。
 *   - **删除本 TU 的重复定义**，改为 include `proto.h` 复用**唯一实现**
 *     （`src/proprietary/misc/FUN_002bdefc_ClearBuffer.c`，工厂 0x2bdefc 的 1:1 复刻）。
 *     理由：工厂二进制里 `ClearBuffer` **只有一个** GLOBAL 符号（readelf 实测），
 *     而本项目原先有两处定义（此处 static 一份 + 复刻文件一份），
 *     靠 `static` 回避了冲突 —— 那正是"同一规则写两处"，会让两份实现的 codegen
 *     各走各的（此处被识别成 memset，复刻文件被内联掉）。
 *     统一到唯一实现后，工厂形态（32B 逐字节 strb 循环 + 可被 bl 的 GLOBAL 符号）
 *     由**一处**代码决定，`xmp3_AllocateBuffers` 的 8 个 bl 也会自然指向它。
 *   非 clang 编译器按 C11 忽略 unknown attribute，语义不变 ⇒ gcc 对照腿安全。
 **************************************************************************************/

/* ★ 唯一实现见 src/proprietary/misc/FUN_002bdefc_ClearBuffer.c（工厂 0x2bdefc）。
 *   这里只取声明（签名 gh_u1* / int 与本处 void* / int 在 ARM EABI 下同宽，兼容）。 */
extern void ClearBuffer(void *buf, int nBytes);

/**************************************************************************************
 * Function:    AllocateBuffers
 *
 * Description: allocate all the memory needed for the MP3 decoder
 *
 * Inputs:      none
 *
 * Outputs:     none
 *
 * Return:      pointer to MP3DecInfo structure (initialized with pointers to all 
 *                the internal buffers needed for decoding, all other members of 
 *                MP3DecInfo structure set to 0)
 *
 * Notes:       if one or more mallocs fail, function frees any buffers already
 *                allocated before returning
 **************************************************************************************/
MP3DecInfo *AllocateBuffers(void)
{
#if USE_STATIC
	MP3DecInfo *mp3DecInfoPtr;
        mp3DecInfoPtr = (MP3DecInfo*)&mp3DecInfo;
        ClearBuffer((void*)&mp3DecInfo, sizeof(MP3DecInfo));

        mp3DecInfo.FrameHeaderPS =     (void*)&fh;
        mp3DecInfo.SideInfoPS =        (void*)&si;
        mp3DecInfo.ScaleFactorInfoPS = (void*)&sfi;
        mp3DecInfo.HuffmanInfoPS =     (void*)&hi;
        mp3DecInfo.DequantInfoPS =     (void*)&di;
        mp3DecInfo.IMDCTInfoPS =       (void*)&mi;
        mp3DecInfo.SubbandInfoPS =     (void*)&sbi;

        ClearBuffer((void*)&fh,  sizeof(FrameHeader));
        ClearBuffer((void*)&si,  sizeof(SideInfo));
        ClearBuffer((void*)&sfi, sizeof(ScaleFactorInfo));
        ClearBuffer((void*)&hi,  sizeof(HuffmanInfo));
        ClearBuffer((void*)&di,  sizeof(DequantInfo));
        ClearBuffer((void*)&mi,  sizeof(IMDCTInfo));
        ClearBuffer((void*)&sbi, sizeof(SubbandInfo));

        return mp3DecInfoPtr;
#else
	MP3DecInfo *mp3DecInfo;
	FrameHeader *fh;
	SideInfo *si;
	ScaleFactorInfo *sfi;
	HuffmanInfo *hi;
	DequantInfo *di;
	IMDCTInfo *mi;
	SubbandInfo *sbi;

	mp3DecInfo = (MP3DecInfo *)malloc(sizeof(MP3DecInfo));
	if (!mp3DecInfo)
		return 0;
	ClearBuffer(mp3DecInfo, sizeof(MP3DecInfo));
	
	fh =  (FrameHeader *)     malloc(sizeof(FrameHeader));
	si =  (SideInfo *)        malloc(sizeof(SideInfo));
	sfi = (ScaleFactorInfo *) malloc(sizeof(ScaleFactorInfo));
	hi =  (HuffmanInfo *)     malloc(sizeof(HuffmanInfo));
	di =  (DequantInfo *)     malloc(sizeof(DequantInfo));
	mi =  (IMDCTInfo *)       malloc(sizeof(IMDCTInfo));
	sbi = (SubbandInfo *)     malloc(sizeof(SubbandInfo));

	mp3DecInfo->FrameHeaderPS =     (void *)fh;
	mp3DecInfo->SideInfoPS =        (void *)si;
	mp3DecInfo->ScaleFactorInfoPS = (void *)sfi;
	mp3DecInfo->HuffmanInfoPS =     (void *)hi;
	mp3DecInfo->DequantInfoPS =     (void *)di;
	mp3DecInfo->IMDCTInfoPS =       (void *)mi;
	mp3DecInfo->SubbandInfoPS =     (void *)sbi;

	if (!fh || !si || !sfi || !hi || !di || !mi || !sbi) {
		FreeBuffers(mp3DecInfo);	/* safe to call - only frees memory that was successfully allocated */
		return 0;
	}
        
	/* important to do this - DSP primitives assume a bunch of state variables are 0 on first use */
	ClearBuffer(fh,  sizeof(FrameHeader));
	ClearBuffer(si,  sizeof(SideInfo));
	ClearBuffer(sfi, sizeof(ScaleFactorInfo));
	ClearBuffer(hi,  sizeof(HuffmanInfo));
	ClearBuffer(di,  sizeof(DequantInfo));
	ClearBuffer(mi,  sizeof(IMDCTInfo));
	ClearBuffer(sbi, sizeof(SubbandInfo));

	return mp3DecInfo;
#endif
}

#if !USE_STATIC
#define SAFE_FREE(x)	{if (x)	free(x);	(x) = 0;}	/* helper macro */
#endif

/**************************************************************************************
 * Function:    FreeBuffers
 *
 * Description: frees all the memory used by the MP3 decoder
 *
 * Inputs:      pointer to initialized MP3DecInfo structure
 *
 * Outputs:     none
 *
 * Return:      none
 *
 * Notes:       safe to call even if some buffers were not allocated (uses SAFE_FREE)
 **************************************************************************************/
void FreeBuffers(MP3DecInfo *mp3DecInfo)
{
#if !USE_STATIC
	if (!mp3DecInfo)
		return;

	SAFE_FREE(mp3DecInfo->FrameHeaderPS);
	SAFE_FREE(mp3DecInfo->SideInfoPS);
	SAFE_FREE(mp3DecInfo->ScaleFactorInfoPS);
	SAFE_FREE(mp3DecInfo->HuffmanInfoPS);
	SAFE_FREE(mp3DecInfo->DequantInfoPS);
	SAFE_FREE(mp3DecInfo->IMDCTInfoPS);
	SAFE_FREE(mp3DecInfo->SubbandInfoPS);

	SAFE_FREE(mp3DecInfo);
#endif
}
