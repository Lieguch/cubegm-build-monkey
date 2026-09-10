/* ============================================================
 * Mp3DecodeLoop   @ 0x000266e4   size=372B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 Mp3DecodeLoop(int param_1)

{
  void *__src;
  int iVar1;
  int iVar2;
  int iVar3;
  int *piVar4;
  gh_uint uVar5;
  
  iVar2 = param_1 * 0x24;
  piVar4 = *(int **)(SoundPlayer + iVar2);
  __src = *(void **)(SoundPlayer + iVar2 + 0x18);
  if ((int)__src < *(int *)(SoundPlayer + iVar2 + 0x1c)) {
    memcpy((void *)piVar4[3],__src,*(int *)(SoundPlayer + iVar2 + 0x1c) - (int)__src);
    piVar4[9] = piVar4[3] +
                (*(int *)(SoundPlayer + iVar2 + 0x1c) - *(int *)(SoundPlayer + iVar2 + 0x18));
  }
  else {
    piVar4[9] = piVar4[3];
  }
  iVar2 = piVar4[1];
  iVar1 = piVar4[6];
  while( true ) {
    while( true ) {
      iVar2 = MP3FindSyncWord(iVar2,iVar1);
      if (-1 < iVar2) break;
      if (*(int *)(SoundPlayer + param_1 * 0x24 + 0x14) == 0) {
        SoundClose(param_1,piVar4 + 1);
        return 1;
      }
      iVar2 = piVar4[7];
      iVar1 = piVar4[8];
      *(gh_u1 *)(piVar4 + 4) = 0;
      piVar4[5] = 0;
      piVar4[1] = iVar2;
      piVar4[6] = iVar1;
    }
    uVar5 = piVar4[9];
    piVar4[1] = piVar4[1] + iVar2;
    piVar4[6] = piVar4[6] - iVar2;
    if ((gh_uint)(piVar4[3] + piVar4[2]) <= uVar5) {
      *(int *)(SoundPlayer + param_1 * 0x24 + 0x18) = piVar4[3];
      *(gh_uint *)(SoundPlayer + param_1 * 0x24 + 0x1c) = uVar5;
      return 1;
    }
    iVar2 = MP3Decode(*piVar4,piVar4 + 1,piVar4 + 6,uVar5,0);
    if (iVar2 != 0) {
      return 1;
    }
    if ((char)piVar4[4] != '\0') break;
    iVar2 = piVar4[1];
    iVar1 = piVar4[6];
    if (*(int *)(*piVar4 + 0x7bc) == 2) {
      iVar3 = piVar4[9] + 0x900;
    }
    else {
      iVar3 = piVar4[9] + 0x480;
    }
    piVar4[9] = iVar3;
    piVar4[5] = piVar4[5] + 1;
  }
  return 1;
}
