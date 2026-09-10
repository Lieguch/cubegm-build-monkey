/* ============================================================
 * mui_outputxy_length.isra.19   @ 0x0001b240   size=372B   callers=2
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int mui_outputxy_length_isra_19(int param_1,int param_2,gh_byte *param_3)

{
  gh_byte *pbVar1;
  gh_byte *pbVar2;
  gh_uint uVar3;
  gh_uint in_fpscr;
  gh_u4 uVar4;
  float fVar5;
  float fVar6;
  gh_u4 local_50;
  gh_u1 auStack_4c [4];
  gh_u1 auStack_48 [4];
  gh_u1 auStack_44 [4];
  gh_u1 auStack_40 [4];
  gh_u1 auStack_3c [8];
  
  uVar4 = VectorUnsignedToFloat(param_2 + 4U & 0xff,(gh_byte)(in_fpscr >> 0x16) & 3);
  fontscale = (float)stbtt_ScaleForPixelHeight(uVar4,font);
  stbtt_GetFontVMetrics(font,&fontascent,0);
  uVar3 = (gh_uint)*param_3;
  fVar5 = (float)VectorSignedToFloat(fontascent,(gh_byte)(in_fpscr >> 0x16) & 3);
  fontbaseline = (int)(fVar5 * fontscale);
  if (uVar3 != 0) {
    do {
      if ((uVar3 & 0xf0) == 0xe0) {
        pbVar1 = param_3 + 1;
        pbVar2 = param_3 + 2;
        param_3 = param_3 + 3;
        uVar3 = (uVar3 & 0x1f) << 0xc | *pbVar2 & 0x3f | (*pbVar1 & 0x3f) << 6;
      }
      else {
        param_3 = param_3 + 1;
      }
      fVar6 = (float)VectorSignedToFloat(param_1,(gh_byte)(in_fpscr >> 0x16) & 3);
      stbtt_GetCodepointHMetrics(font,uVar3,&local_50,auStack_4c);
      stbtt_GetCodepointBitmapBoxSubpixel
                (fontscale,fontscale,fVar6 - fVar6,0,font,uVar3,auStack_48,auStack_44,auStack_40,
                 auStack_3c);
      fVar5 = (float)VectorSignedToFloat(local_50,(gh_byte)(in_fpscr >> 0x16) & 3);
      param_1 = (int)(fVar5 * fontscale + 1.0 + fVar6);
    } while ((param_1 <= (int)OutRect._16_4_) && (uVar3 = (gh_uint)*param_3, uVar3 != 0));
  }
  return param_1;
}
