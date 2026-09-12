/* ============================================================
 * JoystickTest   @ 0x0002a00c   size=4476B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void JoystickTest(int param_1)

{
  gh_byte bVar1;
  gh_bool bVar2;
  gh_u4 uVar3;
  int *__ptr;
  gh_byte *__ptr_00;
  long lVar4;
  gh_uint *puVar5;
  gh_uint *puVar6;
  gh_uint uVar8;
  int iVar9;
  gh_uint uVar10;
  gh_byte *pbVar11;
  gh_uint uVar13;
  gh_uint uVar14;
  gh_uint uVar15;
  gh_byte *pbVar16;
  gh_u4 local_4ac;
  char acStack_4a8 [128];
  gh_byte local_428 [1028];
  gh_uint *puVar7;
  gh_byte *pbVar12;
  
  RARCH_LOG("JoystickTest\n");
  if (DAT_003af29c == (void *)0x0) {
    mui_LoadSetting();
    DAT_003af2a0 = 0x500;
    DAT_003af2a4 = 0x2d0;
    DAT_003af29c = malloc(0x1c2000);
  }
  uVar3 = (gh_u4)GetWorkPath();
  sprintf(acStack_4a8,"%s/joystick.zip",uVar3);
  res_hz = OpenZipU(acStack_4a8,0,2);
  if (res_hz == 0) {
    RARCH_LOG("open %s fail\n",acStack_4a8);
    return;
  }
  zr = FindZipItemA(res_hz,"joystick.raw",1,&local_4ac,ze);
  if (zr != 0) {
    RARCH_LOG("find joystick.raw fail\n");
    return;
  }
  __ptr = malloc((ze_blob)._296_4_);
  UnzipItem(res_hz,local_4ac,__ptr,0,3);
  zr = FindZipItemA(res_hz,"ui.cfg",1,&local_4ac,ze);
  if (zr == 0) {
    __ptr_00 = malloc((ze_blob)._296_4_);
    UnzipItem(res_hz,local_4ac,__ptr_00,0,3);
    if (__ptr_00 != (gh_byte *)0x0) {
      iVar9 = 0;
      pbVar12 = __ptr_00;
      pbVar16 = local_428;
LAB_0002b20c:
      while( true ) {
        do {
          pbVar11 = pbVar12 + 1;
          bVar1 = *pbVar12;
          pbVar12 = pbVar11;
        } while (bVar1 == 0xd);
        if (bVar1 < 0xe) break;
        if ((bVar1 == 0x2c) || (bVar1 == 0x3b)) goto LAB_0002b268;
LAB_0002b258:
        *pbVar16 = bVar1;
        pbVar16 = pbVar16 + 1;
      }
      if (bVar1 != 0) {
        if (bVar1 != 10) goto LAB_0002b258;
LAB_0002b268:
        *pbVar16 = 0;
        lVar4 = strtol((char *)local_428,(char **)0x0,10);
        *(long *)(P1_Table + iVar9 * 4) = lVar4;
        iVar9 = iVar9 + 1;
        pbVar16 = local_428;
        goto LAB_0002b20c;
      }
      *pbVar16 = 0;
      lVar4 = strtol((char *)local_428,(char **)0x0,10);
      *(long *)(P1_Table + iVar9 * 4) = lVar4;
      free(__ptr_00);
    }
  }
  CloseZipU(res_hz);
  memcpy(DAT_003af29c,(void *)((int)__ptr + *__ptr),
         (gh_uint)*(gh_ushort *)((int)__ptr + 6) * (gh_uint)*(gh_ushort *)(__ptr + 1) * 2);
  OutRect._20_4_ = 0x2d0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  ForceFlashCount = 0;
  OutRect._16_4_ = 0x500;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  scr_data = (unsigned char *)UNK_00118000 + (int)DAT_003af29c;
  scr_h_size = 0x500;
  scr_v_size = 0x110;
  output_x = 0x14;
  output_y = 0x24;
  if ((P1_Table_blob)._216_4_ != 0) {
    USBJoy_debug = 1;
  }
  uVar8 = 0;
  uVar10 = 0;
  diff_prev = 0;
  m_time0 = GetTicks();
  do {
    ReadJoystickProc();
    if (joy_key_blob._0_4_ == 0x11) {
      USBJoy_debug = 0;
      free(__ptr);
      return;
    }
    uVar13 = joy_key_blob._0_4_;
    uVar14 = joy_key_blob._4_4_;
    if (param_1 != 0) {
      TurboKeyProcess();
      uVar14 = 0;
      uVar13 = 0;
      puVar5 = (gh_uint *)(KEY_Table + 0x3c);
      puVar6 = (gh_uint *)(user_joy_key_mask + 0x40);
      do {
        puVar7 = puVar6 + -1;
        if (((game_joy_key_blob)._0_4_ & *puVar7) != 0) {
          uVar13 = uVar13 | *puVar5;
        }
        if (((game_joy_key_blob)._4_4_ & puVar6[0xf]) != 0) {
          uVar14 = uVar14 | *puVar5;
        }
        puVar5 = puVar5 + -1;
        puVar6 = puVar7;
      } while (puVar7 != (gh_uint *)user_joy_key_mask);
      local_4ac = 0xffffffff;
      if ((int)(joy_key_blob._0_4_) < 0) {
        uVar13 = uVar13 | 0x80000000;
      }
      if ((int)(joy_key_blob._4_4_) < 0) {
        uVar14 = uVar14 | 0x80000000;
      }
    }
    uVar15 = uVar13 & 0xf0;
    if ((uVar10 & 0xf0) == uVar15) {
      bVar2 = false;
    }
    else {
      if ((uVar10 & 0xf0) != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr,
                        *(gh_u4 *)(P1_Table + ((uVar10 & 0xff) >> 4) * 4));
      }
      if (uVar15 != 0) {
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr,*(gh_u4 *)(P1_Table + (uVar15 >> 2))
                     );
      }
      bVar2 = true;
      uVar10 = uVar10 & 0xffffff0f | uVar15;
    }
    if ((uVar13 & 1) == 0) {
      if ((uVar10 & 1) == 0) goto LAB_0002a258;
      if ((P1_Table_blob)._64_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xfffffffe;
      bVar2 = true;
      if ((uVar13 & 8) != 0) goto LAB_0002a260;
LAB_0002a60c:
      if ((uVar10 & 8) == 0) goto LAB_0002a27c;
      if ((P1_Table_blob)._68_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xfffffff7;
      bVar2 = true;
      if (-1 < (int)uVar13) goto LAB_0002a284;
LAB_0002a630:
      if ((int)uVar10 < 0) goto LAB_0002a28c;
      if ((P1_Table_blob)._72_4_ != 0) {
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 | 0x80000000;
      bVar2 = true;
      if ((uVar13 & 0x1000) != 0) goto LAB_0002a294;
LAB_0002a654:
      if ((uVar10 & 0x1000) == 0) goto LAB_0002a2b0;
      if ((P1_Table_blob)._76_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xffffefff;
      bVar2 = true;
      if ((uVar13 & 0x8000) != 0) goto LAB_0002a2b8;
LAB_0002a678:
      if ((uVar10 & 0x8000) == 0) goto LAB_0002a2d4;
      if ((P1_Table_blob)._80_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xffff7fff;
      bVar2 = true;
      if ((uVar13 & 0x2000) != 0) goto LAB_0002a2dc;
LAB_0002a69c:
      if ((uVar10 & 0x2000) == 0) goto LAB_0002a2f8;
      if ((P1_Table_blob)._84_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xffffdfff;
      bVar2 = true;
      if ((uVar13 & 0x4000) != 0) goto LAB_0002a300;
LAB_0002a6c0:
      if ((uVar10 & 0x4000) == 0) goto LAB_0002a31c;
      if ((P1_Table_blob)._88_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xffffbfff;
      bVar2 = true;
      if ((uVar13 & 0x100) != 0) goto LAB_0002a324;
LAB_0002a6e4:
      if ((uVar10 & 0x100) == 0) goto LAB_0002a340;
      if ((P1_Table_blob)._92_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xfffffeff;
      bVar2 = true;
      if ((uVar13 & 0x200) != 0) goto LAB_0002a348;
LAB_0002a708:
      if ((uVar10 & 0x200) == 0) goto LAB_0002a364;
      if ((P1_Table_blob)._96_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xfffffdff;
      bVar2 = true;
      if ((uVar13 & 0x400) != 0) goto LAB_0002a36c;
LAB_0002a72c:
      if ((uVar10 & 0x400) == 0) goto LAB_0002a388;
      if ((P1_Table_blob)._100_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar10 = uVar10 & 0xfffffbff;
      bVar2 = true;
      if ((uVar13 & 0x800) != 0) goto LAB_0002a390;
LAB_0002a750:
      if ((uVar10 & 0x800) != 0) {
        if ((P1_Table_blob)._104_4_ != 0) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 & 0xfffff7ff;
        bVar2 = true;
      }
    }
    else {
      if ((uVar10 & 1) == 0) {
        if ((P1_Table_blob)._64_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 1;
        bVar2 = true;
      }
LAB_0002a258:
      if ((uVar13 & 8) == 0) goto LAB_0002a60c;
LAB_0002a260:
      if ((uVar10 & 8) == 0) {
        if ((P1_Table_blob)._68_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 8;
        bVar2 = true;
      }
LAB_0002a27c:
      if ((int)uVar13 < 0) goto LAB_0002a630;
LAB_0002a284:
      if ((int)uVar10 < 0) {
        if ((P1_Table_blob)._72_4_ != 0) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 & 0x7fffffff;
        bVar2 = true;
      }
LAB_0002a28c:
      if ((uVar13 & 0x1000) == 0) goto LAB_0002a654;
LAB_0002a294:
      if ((uVar10 & 0x1000) == 0) {
        if ((P1_Table_blob)._76_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x1000;
        bVar2 = true;
      }
LAB_0002a2b0:
      if ((uVar13 & 0x8000) == 0) goto LAB_0002a678;
LAB_0002a2b8:
      if ((uVar10 & 0x8000) == 0) {
        if ((P1_Table_blob)._80_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x8000;
        bVar2 = true;
      }
LAB_0002a2d4:
      if ((uVar13 & 0x2000) == 0) goto LAB_0002a69c;
LAB_0002a2dc:
      if ((uVar10 & 0x2000) == 0) {
        if ((P1_Table_blob)._84_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x2000;
        bVar2 = true;
      }
LAB_0002a2f8:
      if ((uVar13 & 0x4000) == 0) goto LAB_0002a6c0;
LAB_0002a300:
      if ((uVar10 & 0x4000) == 0) {
        if ((P1_Table_blob)._88_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x4000;
        bVar2 = true;
      }
LAB_0002a31c:
      if ((uVar13 & 0x100) == 0) goto LAB_0002a6e4;
LAB_0002a324:
      if ((uVar10 & 0x100) == 0) {
        if ((P1_Table_blob)._92_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x100;
        bVar2 = true;
      }
LAB_0002a340:
      if ((uVar13 & 0x200) == 0) goto LAB_0002a708;
LAB_0002a348:
      if ((uVar10 & 0x200) == 0) {
        if ((P1_Table_blob)._96_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x200;
        bVar2 = true;
      }
LAB_0002a364:
      if ((uVar13 & 0x400) == 0) goto LAB_0002a72c;
LAB_0002a36c:
      if ((uVar10 & 0x400) == 0) {
        if ((P1_Table_blob)._100_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x400;
        bVar2 = true;
      }
LAB_0002a388:
      if ((uVar13 & 0x800) == 0) goto LAB_0002a750;
LAB_0002a390:
      if ((uVar10 & 0x800) == 0) {
        if ((P1_Table_blob)._104_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar10 = uVar10 | 0x800;
        bVar2 = true;
      }
    }
    uVar13 = uVar14 & 0xf0;
    if ((uVar8 & 0xf0) != uVar13) {
      if ((uVar8 & 0xf0) != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr,
                        *(gh_u4 *)(P1_Table + (((uVar8 & 0xff) >> 4) + 0x1b) * 4));
      }
      if (uVar13 != 0) {
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr,
                      *(gh_u4 *)(P1_Table + (uVar13 >> 2) + 0x6c));
      }
      bVar2 = true;
      uVar8 = uVar8 & 0xffffff0f | uVar13;
    }
    if ((uVar14 & 1) == 0) {
      if ((uVar8 & 1) == 0) goto LAB_0002a3fc;
      if ((P1_Table_blob)._172_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xfffffffe;
      bVar2 = true;
      if ((uVar14 & 8) != 0) goto LAB_0002a404;
LAB_0002a814:
      if ((uVar8 & 8) == 0) goto LAB_0002a420;
      if ((P1_Table_blob)._176_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xfffffff7;
      bVar2 = true;
      if (-1 < (int)uVar14) goto LAB_0002a428;
LAB_0002a838:
      if ((int)uVar8 < 0) goto LAB_0002a430;
      if ((P1_Table_blob)._180_4_ != 0) {
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 | 0x80000000;
      bVar2 = true;
      if ((uVar14 & 0x1000) != 0) goto LAB_0002a438;
LAB_0002a85c:
      if ((uVar8 & 0x1000) == 0) goto LAB_0002a454;
      if ((P1_Table_blob)._184_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xffffefff;
      bVar2 = true;
      if ((uVar14 & 0x8000) == 0) goto LAB_0002a880;
LAB_0002a45c:
      if ((uVar8 & 0x8000) == 0) {
        if ((P1_Table_blob)._188_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x8000;
        bVar2 = true;
      }
LAB_0002a478:
      if ((uVar14 & 0x2000) == 0) goto LAB_0002a8a4;
LAB_0002a480:
      if ((uVar8 & 0x2000) == 0) {
        if ((P1_Table_blob)._192_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x2000;
        bVar2 = true;
      }
LAB_0002a49c:
      if ((uVar14 & 0x4000) == 0) goto LAB_0002a8c8;
LAB_0002a4a4:
      if ((uVar8 & 0x4000) == 0) {
        if ((P1_Table_blob)._196_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x4000;
        bVar2 = true;
      }
LAB_0002a4c0:
      if ((uVar14 & 0x100) == 0) goto LAB_0002a8ec;
LAB_0002a4c8:
      if ((uVar8 & 0x100) == 0) {
        if ((P1_Table_blob)._200_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x100;
        bVar2 = true;
      }
    }
    else {
      if ((uVar8 & 1) == 0) {
        if ((P1_Table_blob)._172_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 1;
        bVar2 = true;
      }
LAB_0002a3fc:
      if ((uVar14 & 8) == 0) goto LAB_0002a814;
LAB_0002a404:
      if ((uVar8 & 8) == 0) {
        if ((P1_Table_blob)._176_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 8;
        bVar2 = true;
      }
LAB_0002a420:
      if ((int)uVar14 < 0) goto LAB_0002a838;
LAB_0002a428:
      if ((int)uVar8 < 0) {
        if ((P1_Table_blob)._180_4_ != 0) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 & 0x7fffffff;
        bVar2 = true;
      }
LAB_0002a430:
      if ((uVar14 & 0x1000) == 0) goto LAB_0002a85c;
LAB_0002a438:
      if ((uVar8 & 0x1000) == 0) {
        if ((P1_Table_blob)._184_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x1000;
        bVar2 = true;
      }
LAB_0002a454:
      if ((uVar14 & 0x8000) != 0) goto LAB_0002a45c;
LAB_0002a880:
      if ((uVar8 & 0x8000) == 0) goto LAB_0002a478;
      if ((P1_Table_blob)._188_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xffff7fff;
      bVar2 = true;
      if ((uVar14 & 0x2000) != 0) goto LAB_0002a480;
LAB_0002a8a4:
      if ((uVar8 & 0x2000) == 0) goto LAB_0002a49c;
      if ((P1_Table_blob)._192_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xffffdfff;
      bVar2 = true;
      if ((uVar14 & 0x4000) != 0) goto LAB_0002a4a4;
LAB_0002a8c8:
      if ((uVar8 & 0x4000) == 0) goto LAB_0002a4c0;
      if ((P1_Table_blob)._196_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xffffbfff;
      bVar2 = true;
      if ((uVar14 & 0x100) != 0) goto LAB_0002a4c8;
LAB_0002a8ec:
      if ((uVar8 & 0x100) != 0) {
        if ((P1_Table_blob)._200_4_ != 0) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 & 0xfffffeff;
        bVar2 = true;
      }
    }
    if ((uVar14 & 0x200) == 0) {
      if ((uVar8 & 0x200) == 0) goto LAB_0002a508;
      if ((P1_Table_blob)._204_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar8 = uVar8 & 0xfffffdff;
      bVar2 = true;
      if ((uVar14 & 0x400) != 0) goto LAB_0002a510;
LAB_0002a7ac:
      if ((uVar8 & 0x400) == 0) goto LAB_0002a934;
      if ((P1_Table_blob)._208_4_ != 0) {
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
      }
      uVar15 = uVar8 & 0xfffffbff;
      uVar13 = uVar8;
joined_r0x0002a52c:
      uVar8 = uVar15;
      if ((uVar14 & 0x800) == 0) {
        if ((uVar13 & 0x800) == 0) goto LAB_0002a90c;
        goto joined_r0x0002a7e0;
      }
      if ((uVar13 & 0x800) == 0) goto LAB_0002a53c;
LAB_0002a90c:
      if (spi_printf_needflash != 0) goto LAB_0002a928;
LAB_0002a564:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    }
    else {
      if ((uVar8 & 0x200) == 0) {
        if ((P1_Table_blob)._204_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x200;
        bVar2 = true;
      }
LAB_0002a508:
      if ((uVar14 & 0x400) == 0) goto LAB_0002a7ac;
LAB_0002a510:
      if ((uVar8 & 0x400) == 0) {
        if ((P1_Table_blob)._208_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar15 = uVar8 | 0x400;
        uVar13 = uVar8;
        goto joined_r0x0002a52c;
      }
LAB_0002a934:
      if ((uVar14 & 0x800) != 0) {
        if ((uVar8 & 0x800) != 0) goto LAB_0002a944;
LAB_0002a53c:
        if ((P1_Table_blob)._212_4_ != 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 | 0x800;
LAB_0002a550:
        if (spi_printf_needflash == 0) goto LAB_0002a564;
LAB_0002a928:
        spi_printf_needflash = 0;
        goto LAB_0002a564;
      }
      if ((uVar8 & 0x800) != 0) {
joined_r0x0002a7e0:
        if ((P1_Table_blob)._212_4_ != 0) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,__ptr);
        }
        uVar8 = uVar8 & 0xfffff7ff;
        goto LAB_0002a550;
      }
LAB_0002a944:
      if (spi_printf_needflash != 0) goto LAB_0002a928;
      if (bVar2) goto LAB_0002a564;
    }
    mui_WaitNMI();
  } while( true );
}
