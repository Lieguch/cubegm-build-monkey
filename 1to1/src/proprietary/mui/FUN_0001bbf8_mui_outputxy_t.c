/* ============================================================
 * mui_outputxy_t   @ 0x0001bbf8   size=888B   callers=11
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int mui_outputxy_t(int param_1,int param_2,int param_3,int param_4,uint param_5,byte *param_6)

{
  byte *pbVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  undefined4 uVar4;
  undefined4 uVar5;
  int iVar6;
  ushort *puVar7;
  byte *pbVar8;
  int iVar9;
  int iVar10;
  uint uVar11;
  uint uVar12;
  ushort *puVar13;
  int iVar14;
  uint in_fpscr;
  undefined4 uVar15;
  float fVar16;
  float fVar17;
  undefined4 local_50;
  undefined1 auStack_4c [4];
  int local_48;
  int local_44;
  int local_40;
  int local_3c [2];
  
  uVar15 = VectorUnsignedToFloat(param_4 + 4U & 0xff,(byte)(in_fpscr >> 0x16) & 3);
  fontscale = (float)stbtt_ScaleForPixelHeight(uVar15,font);
  stbtt_GetFontVMetrics(font,&fontascent,0);
  uVar11 = (uint)*param_6;
  fVar16 = (float)VectorSignedToFloat(fontascent,(byte)(in_fpscr >> 0x16) & 3);
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
      fVar16 = (float)VectorSignedToFloat(param_2,(byte)(in_fpscr >> 0x16) & 3);
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
        puVar13 = (ushort *)(param_1 + (OutRect._0_4_ * param_3 + param_2) * 2);
        iVar14 = param_2;
        do {
          if (param_3 < iVar9) {
            pbVar8 = fontbitmap + (iVar14 - param_2);
            puVar7 = puVar13;
            iVar10 = param_3;
            do {
              if (((((int)uVar2 <= iVar14) && ((int)uVar3 <= iVar10)) && (iVar14 < (int)uVar4)) &&
                 (iVar10 < (int)uVar5)) {
                uVar11 = (uint)(*pbVar8 >> 3);
                if (uVar11 == 0x1f) {
                  *puVar7 = (ushort)param_5;
                }
                else if (uVar11 != 0) {
                  uVar12 = CONCAT22(*puVar7,*puVar7) & 0x7e0f81f;
                  uVar11 = uVar12 + ((int)(uVar11 * (((param_5 | param_5 << 0x10) & 0x7e0f81f) -
                                                    uVar12)) >> 5) & 0x7e0f81f;
                  *puVar7 = (ushort)uVar11 | (ushort)(uVar11 >> 0x10);
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
      fVar17 = (float)VectorSignedToFloat(local_50,(byte)(in_fpscr >> 0x16) & 3);
      param_2 = (int)(fVar17 * fontscale + 1.0 + fVar16);
    } while ((param_2 <= (int)uVar4) && (uVar11 = (uint)*param_6, uVar11 != 0));
  }
  return param_2;
}
