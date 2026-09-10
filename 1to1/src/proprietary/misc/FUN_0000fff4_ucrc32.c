/* ============================================================
 * ucrc32   @ 0x0000fff4   size=340B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_uint ucrc32(gh_uint param_1,gh_byte *param_2,gh_uint param_3)

{
  gh_byte *pbVar1;
  gh_byte *pbVar2;
  gh_uint uVar3;
  gh_uint uVar4;
  
  if (param_2 != (gh_byte *)0x0) {
    param_1 = ~param_1;
    if (7 < param_3) {
      uVar3 = param_3 - 8;
      pbVar1 = param_2 + 8;
      do {
        pbVar2 = pbVar1 + 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-8] ^ param_1) & 0xff) * 4) ^ param_1 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-7] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-6] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-5] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-4] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-3] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        uVar4 = *(gh_uint *)(crc_table + ((pbVar1[-2] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        param_1 = *(gh_uint *)(crc_table + ((pbVar1[-1] ^ uVar4) & 0xff) * 4) ^ uVar4 >> 8;
        pbVar1 = pbVar2;
      } while (param_2 + (uVar3 & 0xfffffff8) + 0x10 != pbVar2);
      param_3 = param_3 & 7;
      param_2 = param_2 + (uVar3 & 0xfffffff8) + 8;
    }
    if (param_3 != 0) {
      pbVar1 = param_2;
      do {
        pbVar2 = pbVar1 + 1;
        param_1 = *(gh_uint *)(crc_table + ((*pbVar1 ^ param_1) & 0xff) * 4) ^ param_1 >> 8;
        pbVar1 = pbVar2;
      } while (pbVar2 != param_2 + param_3);
    }
    return ~param_1;
  }
  return 0;
}
