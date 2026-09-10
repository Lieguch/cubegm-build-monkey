/* ============================================================
 * SeletEmuCore   @ 0x00021c08   size=1712B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int SeletEmuCore(undefined4 param_1)

{
  int iVar1;
  void *__ptr;
  void *__ptr_00;
  char *pcVar2;
  FILE *__stream;
  int iVar3;
  int iVar4;
  uint uVar5;
  ushort uVar6;
  int iVar7;
  int iVar8;
  ushort *puVar9;
  ushort *puVar10;
  bool bVar11;
  int local_158 [6];
  void *local_140;
  undefined4 local_13c;
  undefined4 local_138;
  undefined4 local_134;
  undefined4 local_130;
  undefined4 local_12c;
  char acStack_128 [260];
  
  iVar1 = FilePreEmu();
  iVar3 = DAT_003af2a0;
  iVar8 = DAT_003af29c;
  __ptr = malloc(0x6ebe0);
  local_158[5] = iVar3 << 1;
  iVar7 = 0;
  local_158[2] = 0x96;
  local_13c = 0;
  local_134 = 0x21c;
  local_138 = 0;
  local_12c = 0x438;
  local_158[4] = 0x23a;
  local_158[1] = 0x172;
  local_130 = 0x1a4;
  local_158[3] = 0x38e;
  local_158[0] = iVar8;
  local_140 = __ptr;
  mui_blockcopy(&local_140,local_158);
  iVar4 = DAT_003af2a0;
  puVar9 = (ushort *)(iVar8 + (iVar3 * 0x96 + 0x172) * 2 + -2);
  do {
    iVar8 = 0;
    puVar10 = puVar9;
    do {
      while( true ) {
        uVar6 = puVar10[1];
        uVar5 = uVar6 & 0x1f;
        if ((3 < iVar7) && (2 < iVar7 - 0x19cU)) break;
        if (0x216 < iVar8) goto LAB_00021d44;
LAB_00021e84:
        uVar6 = 0x630c;
LAB_00021d10:
        iVar8 = iVar8 + 1;
        puVar10 = puVar10 + 1;
        *puVar10 = uVar6;
        if (iVar8 == 0x21c) goto LAB_00021d94;
      }
      if (iVar8 < 4) {
        if (iVar7 < 0x19f) goto LAB_00021e84;
LAB_00021d08:
        uVar6 = (ushort)uVar5 | uVar6 & 0xf800 | uVar6 & 0x7e0;
        goto LAB_00021d10;
      }
LAB_00021d44:
      if (iVar7 < 0x19f && iVar8 - 0x214U < 3) goto LAB_00021e84;
      iVar3 = iVar7;
      if (3 < iVar7) {
        iVar3 = iVar8;
      }
      if (iVar3 < 4) goto LAB_00021d08;
      iVar8 = iVar8 + 1;
      puVar10 = puVar10 + 1;
      *puVar10 = (ushort)(uVar5 >> 3) | (uVar6 >> 0xe) << 0xb |
                 (ushort)(((uVar6 & 0x7ff) >> 8) << 5);
    } while (iVar8 != 0x21c);
LAB_00021d94:
    iVar7 = iVar7 + 1;
    puVar9 = puVar9 + iVar4;
  } while (iVar7 != 0x1a4);
  OutRect._8_4_ = 0x172;
  OutRect._12_4_ = 0x96;
  OutRect._16_4_ = 0x38e;
  OutRect._20_4_ = 0x23a;
  if (iVar1 == 0) {
    mui_outputxy_t(DAT_003af29c,0x1b2,0xa2,0x22,0xfc1f,"The specified file is missing");
    mui_outputxy_t(DAT_003af29c,OutRect._8_4_ + 0x20,OutRect._12_4_ + 0xa8,0x18,0xffff,param_1);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    while (((iVar8 = mui_ReadJoystick(), iVar8 != 0x2000 && (iVar8 != 0x4000)) && (iVar8 != 8))) {
      mui_WaitNMI();
    }
    return 0;
  }
  mui_outputxy_t(DAT_003af29c,0x1b2,0xa2,0x22,0xfc1f,"Select a emulator core library");
  __ptr_00 = malloc(0x6ebe0);
  local_140 = __ptr_00;
  mui_blockcopy(&local_140,local_158);
  pcVar2 = stpcpy(acStack_128,work_path);
  builtin_strncpy(pcVar2,"cores/config.xml",0x11);
  __stream = fopen(acStack_128,"r");
  if (__stream == (FILE *)0x0) {
    RARCH_LOG("open config.xml fail!\n");
    tree = 0;
    iVar8 = 0;
  }
  else {
    tree = mxmlLoadFile(0,__stream);
    fclose(__stream);
    if (tree == 0) {
      iVar8 = 0;
    }
    else {
      iVar8 = 0;
      iVar3 = tree;
LAB_00021f90:
      iVar3 = mxmlFindElement(iVar3,tree,&DAT_002dd508,0,0,1);
      if (iVar3 != 0) {
        iVar4 = mxmlFindElement(iVar3,tree,"supported_extensions",0,0,1);
        do {
          iVar1 = strcmp(*(char **)(*(int *)(iVar4 + 0x10) + 0x1c),(char *)&FilenameExt);
          if (iVar1 == 0) {
            iVar4 = mxmlFindElement(iVar3,tree,"emucore",0,0,1);
            if (iVar4 != 0) {
              iVar1 = iVar8 * 0x200;
              iVar8 = iVar8 + 1;
              pcVar2 = (char *)mxmlElementGetAttr(iVar4,&DAT_002dcd70);
              strcpy(core_info_list + iVar1,pcVar2);
              pcVar2 = (char *)mxmlElementGetAttr(iVar4,&DAT_002dbd74);
              strcpy(core_info_list + iVar1 + 0x100,pcVar2);
            }
            break;
          }
          iVar4 = mxmlFindElement(iVar4,tree,"supported_extensions",0,0,0);
        } while (iVar4 != 0);
        goto LAB_00021f90;
      }
      if (tree != 0) {
        mxmlDelete();
        tree = 0;
      }
    }
  }
  EmuCore_list(0,0,iVar8);
  iVar3 = 0;
  ForceFlashCount = 0;
  iVar4 = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  uVar5 = mui_ReadJoystick();
  bVar11 = false;
  if (uVar5 == 0x40) goto LAB_00022190;
LAB_00022128:
  if (uVar5 < 0x40 || bVar11) {
    if (uVar5 == 8) {
LAB_00022214:
      local_140 = __ptr;
      mui_blockcopy(local_158,&local_140);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      free(__ptr);
      free(__ptr_00);
      return (iVar4 + iVar3) * 0x200 + 0x3c9bec;
    }
    if (uVar5 == 0x10) {
      if (iVar3 != 0) {
        iVar3 = iVar3 + -1;
        goto LAB_00022148;
      }
      if (iVar4 != 0) {
        iVar4 = iVar4 + -1;
        goto LAB_00022148;
      }
      iVar3 = 0;
    }
  }
  else {
    if (uVar5 == 0x2000) goto LAB_00022214;
    if (uVar5 == 0x4000) {
      local_140 = __ptr;
      mui_blockcopy(local_158,&local_140);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      free(__ptr);
      free(__ptr_00);
      return 0;
    }
  }
LAB_00022180:
  while( true ) {
    mui_WaitNMI();
    uVar5 = mui_ReadJoystick();
    bVar11 = uVar5 == 0x40;
    if (!bVar11) break;
LAB_00022190:
    if (iVar3 < 6) goto code_r0x000221a0;
    if (iVar4 + iVar3 < iVar8 + -1) {
      iVar4 = iVar4 + 1;
      goto LAB_00022148;
    }
  }
  goto LAB_00022128;
code_r0x000221a0:
  if (iVar4 + iVar3 < iVar8 + -1) {
    iVar3 = iVar3 + 1;
LAB_00022148:
    local_140 = __ptr_00;
    mui_blockcopy(local_158,&local_140);
    EmuCore_list(iVar4,iVar3,iVar8);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  }
  goto LAB_00022180;
}
