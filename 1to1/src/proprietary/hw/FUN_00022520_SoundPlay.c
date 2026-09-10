/* ============================================================
 * SoundPlay   @ 0x00022520   size=380B   callers=16
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SoundPlay(int param_1,int *param_2)

{
  int *piVar1;
  void *pvVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  
  if (param_2[1] != 1) {
    iVar3 = param_2[1];
    iVar4 = param_2[2];
    iVar6 = param_2[3];
    param_1 = param_1 * 0x24;
    *(int *)(SoundPlayer + param_1) = *param_2;
    *(int *)(SoundPlayer + param_1 + 4) = iVar3;
    *(int *)(SoundPlayer + param_1 + 8) = iVar4;
    *(int *)(SoundPlayer + param_1 + 0xc) = iVar6;
    iVar3 = param_2[5];
    iVar4 = param_2[6];
    iVar6 = param_2[7];
    *(int *)(SoundPlayer + param_1 + 0x10) = param_2[4];
    *(int *)(SoundPlayer + param_1 + 0x14) = iVar3;
    *(int *)(SoundPlayer + param_1 + 0x18) = iVar4;
    *(int *)(SoundPlayer + param_1 + 0x1c) = iVar6;
    *(int *)(SoundPlayer + param_1 + 0x20) = param_2[8];
    return;
  }
  piVar1 = malloc(0x28);
  iVar3 = param_1 * 0x24;
  iVar4 = *param_2;
  iVar6 = param_2[1];
  iVar5 = param_2[2];
  iVar7 = param_2[3];
  *(undefined1 *)(piVar1 + 4) = 0;
  *(int *)(SoundPlayer + iVar3) = iVar4;
  *(int *)(SoundPlayer + iVar3 + 4) = iVar6;
  *(int *)(SoundPlayer + iVar3 + 8) = iVar5;
  *(int *)(SoundPlayer + iVar3 + 0xc) = iVar7;
  iVar4 = param_2[5];
  iVar6 = param_2[6];
  iVar5 = param_2[7];
  *(int *)(SoundPlayer + iVar3 + 0x10) = param_2[4];
  *(int *)(SoundPlayer + iVar3 + 0x14) = iVar4;
  *(int *)(SoundPlayer + iVar3 + 0x18) = iVar6;
  *(int *)(SoundPlayer + iVar3 + 0x1c) = iVar5;
  *(int *)(SoundPlayer + iVar3 + 0x20) = param_2[8];
  iVar4 = param_2[2];
  iVar3 = param_2[3];
  iVar6 = param_2[4];
  piVar1[1] = *param_2;
  iVar3 = (iVar6 * (iVar3 * (iVar4 + 1) + iVar4 + 1)) / 0x3c;
  piVar1[2] = iVar3;
  pvVar2 = malloc(iVar3 + 0x900);
  piVar1[3] = (int)pvVar2;
  iVar3 = MP3InitDecoder();
  *piVar1 = iVar3;
  if (iVar3 == 0) {
    RARCH_LOG("** Cannot initialize MP3 decoder.\r\n");
  }
  iVar3 = param_2[7];
  iVar4 = param_2[6];
  piVar1[9] = piVar1[3];
  iVar3 = iVar3 - iVar4;
  piVar1[5] = 0;
  piVar1[6] = iVar3;
  while( true ) {
    iVar4 = MP3FindSyncWord(piVar1[1],iVar3);
    iVar3 = 0;
    if (-1 < iVar4) break;
    piVar1[6] = 0;
  }
  iVar6 = piVar1[6];
  param_1 = param_1 * 0x24;
  iVar3 = piVar1[1];
  piVar1[1] = iVar3 + iVar4;
  piVar1[7] = iVar3 + iVar4;
  piVar1[6] = iVar6 - iVar4;
  *(int **)(SoundPlayer + param_1) = piVar1;
  *(undefined4 *)(SoundPlayer + param_1 + 0x18) = 0;
  *(undefined4 *)(SoundPlayer + param_1 + 0x1c) = 0;
  piVar1[8] = iVar6 - iVar4;
  return;
}
