/* ============================================================
 * gpsp_unzip   @ 0x002b4e20   size=228B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 gpsp_unzip(gh_u4 param_1,char *param_2)

{
  gh_u4 *iVar1;
  int iVar2;
  gh_u1 auStack_140 [296];
  gh_u4 local_18;
  
  memset(auStack_140,0,0x130);
  RARCH_LOG("gpsp_unzip:%s to %x\n",param_2,param_1);
  iVar1 = OpenZipU(param_2,0,2);
  if (iVar1 != 0) {
    RARCH_LOG("Open ZIP file ok\n");
    iVar2 = GetZipItemA(iVar1,0,auStack_140);
    if (iVar2 == 0) {
      iVar2 = UnzipItem(iVar1,0,(void *)param_1,0,3);
      CloseZipU(iVar1);
      if (iVar2 == 0) {
        RARCH_LOG("UnzipItem success!\n");
        return local_18;
      }
      RARCH_LOG("UnzipItem failed\n");
    }
    else {
      CloseZipU(iVar1);
    }
  }
  return 0;
}
