/* ============================================================
 * mui_outputxy_t   @ 0x0001bbf8   size=888B   callers=11
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int mui_outputxy_t(gh_u1 *param_1,int param_2,int param_3,int param_4,gh_uint param_5,gh_byte *param_6)

{
  gh_byte *pbVar1;
  gh_u4 uVar2;
  gh_u4 uVar3;
  gh_u4 uVar4;
  gh_u4 uVar5;
  int iVar6;
  gh_ushort *puVar7;
  gh_byte *pbVar8;
  int iVar9;
  int iVar10;
  gh_uint uVar11;
  gh_uint uVar12;
  gh_ushort *puVar13;
  int iVar14;
  gh_uint in_fpscr;
  gh_u4 uVar15;
  float fVarScaleIn;  /* 原寄存器复用：此处专供 stbtt_ScaleForPixelHeight(float) */
  float fVar16;
  float fVar17;
  gh_u4 local_50;
  gh_u1 auStack_4c [4];
  int local_48;
  int local_44;
  int local_40;
  int local_3c [2];
  
  fVarScaleIn = VectorUnsignedToFloat(param_4 + 4U & 0xff,(gh_byte)(in_fpscr >> 0x16) & 3);
  fontscale = (float)stbtt_ScaleForPixelHeight(fVarScaleIn,font);
  stbtt_GetFontVMetrics(font,&fontascent,0);
  uVar11 = (gh_uint)*param_6;
  fVar16 = (float)VectorSignedToFloat(fontascent,(gh_byte)(in_fpscr >> 0x16) & 3);
  fontbaseline = (int)(fVar16 * fontscale);
  if (uVar11 != 0) {
    do {
      if ((uVar11 & 0xf0) == 0xe0) {
        pbVar8 = param_6 + 1;
        pbVar1 = param_6 + 2;
        param_6 = param_6 + 3;
        uVar11 = (uVar11 & 0x1f) << 0xc | *pbVar1 & 0x3f | (*pbVar8 & 0x3f) << 6;
      }
      else {
        param_6 = param_6 + 1;
      }
      fVar16 = (float)VectorSignedToFloat(param_2,(gh_byte)(in_fpscr >> 0x16) & 3);
      stbtt_GetCodepointHMetrics(font,uVar11,&local_50,auStack_4c);
      stbtt_GetCodepointBitmapBoxSubpixel
                (fontscale,fontscale,fVar16 - fVar16,0,font,uVar11,&local_48,&local_44,&local_40,
                 local_3c);
      iVar10 = local_3c[0];
      iVar6 = local_40;
      iVar14 = fontbaseline;
      iVar9 = fontbaseline + local_3c[0];
      memset(fontbitmap,0,iVar9 * local_40);
      stbtt_MakeCodepointBitmapSubpixel
                (fontscale,fontscale,fVar16 - fVar16,0,font,
                 fontbitmap + iVar6 * (iVar14 + local_44) + local_48,iVar6 - local_48,
                 iVar10 - local_44,iVar6,uVar11);
      uVar5 = OutRect._20_4_;
      uVar4 = OutRect._16_4_;
      uVar3 = OutRect._12_4_;
      uVar2 = OutRect._8_4_;
      uVar15 = OutRect._0_4_;
      iVar9 = param_3 + iVar9;
      if (param_2 < iVar6 + param_2) {
        puVar13 = (gh_ushort *)(param_1 + (OutRect._0_4_ * param_3 + param_2) * 2);
        iVar14 = param_2;
        do {
          if (param_3 < iVar9) {
            pbVar8 = fontbitmap + (iVar14 - param_2);
            puVar7 = puVar13;
            iVar10 = param_3;
            do {
              if (((((int)uVar2 <= iVar14) && ((int)uVar3 <= iVar10)) && (iVar14 < (int)uVar4)) &&
                 (iVar10 < (int)uVar5)) {
                uVar11 = (gh_uint)(*pbVar8 >> 3);
                if (uVar11 == 0x1f) {
                  *puVar7 = (gh_ushort)param_5;
                }
                else if (uVar11 != 0) {
                  uVar12 = CONCAT22(*puVar7,*puVar7) & 0x7e0f81f;
                  uVar11 = uVar12 + ((int)(uVar11 * (((param_5 | param_5 << 0x10) & 0x7e0f81f) -
                                                    uVar12)) >> 5) & 0x7e0f81f;
                  *puVar7 = (gh_ushort)uVar11 | (gh_ushort)(uVar11 >> 0x10);
                }
              }
              iVar10 = iVar10 + 1;
              puVar7 = puVar7 + uVar15;
              pbVar8 = pbVar8 + iVar6;
            } while (iVar9 != iVar10);
          }
          iVar14 = iVar14 + 1;
          puVar13 = puVar13 + 1;
        } while (iVar6 + param_2 != iVar14);
      }
      fVar17 = (float)VectorSignedToFloat(local_50,(gh_byte)(in_fpscr >> 0x16) & 3);
      param_2 = (int)(fVar17 * fontscale + 1.0 + fVar16);
    } while ((param_2 <= (int)uVar4) && (uVar11 = (gh_uint)*param_6, uVar11 != 0));
  }
  return param_2;
}
