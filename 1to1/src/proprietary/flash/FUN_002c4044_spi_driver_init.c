/* ============================================================
 * spi_driver_init   @ 0x002c4044   size=836B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 spi_driver_init(void)

{
  byte bVar1;
  byte bVar2;
  byte *pbVar3;
  byte *pbVar4;
  undefined4 uVar5;
  uint uVar6;
  byte *pbVar7;
  int iVar8;
  int iVar9;
  undefined1 uVar10;
  undefined4 local_120;
  undefined4 local_11c;
  undefined4 local_118;
  undefined4 local_114;
  byte local_110 [20];
  byte local_fc [4];
  byte local_f8 [160];
  byte local_58 [68];
  
  local_11c = 0;
  local_120 = 0x9f;
  sfc_request(&local_120,0,&local_118,3);
  uVar6 = local_118 & 0xff;
  spi_id._0_1_ = (byte)local_118;
  spi_id._1_1_ = local_118._1_1_;
  spi_id._2_1_ = local_118._2_1_;
  if (uVar6 == 0x85 || (uVar6 == 0xb || ((local_118 & 0xef) == 200 || uVar6 == 0x20))) {
    if (local_118._2_1_ == '\x18') {
      FlashSize = 0x1000000;
LAB_002c41fc:
      if (uVar6 == 0xb) goto LAB_002c4360;
      if (0x400000 < FlashSize) {
        uVar5 = 0;
        uVar10 = 0x4b;
        goto LAB_002c4220;
      }
LAB_002c42cc:
      local_11c = 0;
      local_120 = 0x484b;
      sfc_request(&local_120,0,&local_118,8);
      pbVar4 = (byte *)&UniqueID;
      pbVar3 = (byte *)&local_118;
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3;
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    else {
      if (local_118._2_1_ == '\x17') {
        FlashSize = 0x800000;
        goto LAB_002c41fc;
      }
      if (local_118._2_1_ == '\x16') {
        FlashSize = 0x400000;
        goto LAB_002c41fc;
      }
      if (local_118._2_1_ == '\x15') {
        FlashSize = 0x200000;
        if (uVar6 == 0xb) goto LAB_002c4360;
        goto LAB_002c42cc;
      }
      if (local_118._2_1_ == '\x14') {
        FlashSize = 0x100000;
      }
      else {
        if (local_118._2_1_ != '\x13') goto LAB_002c41fc;
        FlashSize = 0x80000;
      }
      if (uVar6 != 0xb) goto LAB_002c42cc;
LAB_002c4360:
      uVar5 = 0x194;
      uVar10 = 0x5a;
LAB_002c4220:
      local_11c = 0;
      local_120 = (uint)CONCAT11(0x48,uVar10);
      sfc_request(&local_120,uVar5,&local_118,0x10);
      pbVar4 = (byte *)&UniqueID;
      pbVar3 = (byte *)&local_118;
      do {
        pbVar7 = pbVar3 + 1;
        *pbVar4 = *pbVar3 ^ pbVar3[8];
        pbVar4 = pbVar4 + 1;
        pbVar3 = pbVar7;
      } while (pbVar7 != local_110);
    }
    if ((byte)spi_id == 0xb) {
      sflash_read_security_data(&local_118,0x100);
      goto LAB_002c40e0;
    }
  }
  sflash_read_security_data(&local_118,0x2000);
LAB_002c40e0:
  printf("ROM Size:%08X CRC32:%04X ",FlashSize,local_118);
  printf("Update time:");
  DateToTmuDate(local_114);
  if ((byte)spi_id == 0xb) {
    uVar5 = 0;
  }
  else {
    uVar5 = 0x1000;
  }
  sflash_read_security_data(&local_118,uVar5);
  iVar9 = 0;
  pbVar3 = &DAT_002dee30;
  iVar8 = 0;
  pbVar4 = (byte *)&local_118;
  do {
    bVar1 = *pbVar3;
    pbVar3 = pbVar3 + 1;
    if (iVar8 < 8) {
      bVar2 = *(byte *)((int)&UniqueID + iVar8);
    }
    else {
      bVar2 = pbVar4[-8];
    }
    iVar8 = iVar8 + 1;
    if (*pbVar4 != (byte)((bVar1 ^ bVar2) + pbVar4[0xc0])) {
      iVar9 = iVar9 + 1;
    }
    pbVar4 = pbVar4 + 1;
  } while (iVar8 != 0x18);
  if (iVar9 == 0) {
    pbVar7 = local_fc + 3;
    pbVar4 = local_fc + 1;
    pbVar3 = GamePath + 0x1b;
    do {
      pbVar7 = pbVar7 + 1;
      pbVar4 = pbVar4 + -1;
      pbVar3 = pbVar3 + 1;
      *pbVar3 = *pbVar7 ^ *pbVar4;
    } while (local_f8 + 0x1b != pbVar7);
    uVar5 = 1;
  }
  else {
    uVar5 = 0;
  }
  return uVar5;
}
