/* ============================================================
 * GetJoystickConfig   @ 0x00029d48   size=688B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 GetJoystickConfig(int param_1,undefined4 param_2,undefined4 param_3,undefined4 param_4)

{
  bool bVar1;
  undefined4 uVar2;
  undefined1 *__ptr;
  undefined1 *puVar3;
  undefined1 *puVar4;
  int iVar6;
  undefined4 local_4a4;
  char acStack_4a0 [128];
  undefined1 local_420 [1024];
  undefined1 *puVar5;
  
  uVar2 = GetWorkPath();
  sprintf(acStack_4a0,"%s/joystick.zip",uVar2);
  res_hz = OpenZipU(acStack_4a0,0,2);
  if (res_hz != 0) {
    sprintf(acStack_4a0,"%04x_%04x_%04x",param_2,param_3,param_4);
    zr = FindZipItemA(res_hz,acStack_4a0,1,&local_4a4,ze);
    if (zr != 0) {
      sprintf(acStack_4a0,"%04x_%04x",param_2,param_3);
      zr = FindZipItemA(res_hz,acStack_4a0,1,&local_4a4,ze);
      if (zr != 0) {
        return 0;
      }
    }
    iVar6 = 0;
    __ptr = malloc(ze._296_4_ + 1);
    UnzipItem(res_hz,local_4a4,__ptr,0,3);
    __ptr[ze._296_4_] = 0;
    if (__ptr != (undefined1 *)0x0) {
      puVar3 = local_420;
      puVar5 = __ptr;
LAB_00029e40:
      puVar4 = puVar5 + 1;
      switch(*puVar5) {
      case 0:
        *puVar3 = 0;
        if (puVar3 <= local_420) {
          free(__ptr);
          return 0;
        }
        uVar2 = buttontoi(local_420);
        *(undefined4 *)(param_1 + iVar6 * 4) = uVar2;
        free(__ptr);
        return 0;
      case 1:
        break;
      case 2:
        break;
      case 3:
        break;
      case 4:
        break;
      case 5:
        break;
      case 6:
        break;
      case 7:
        break;
      case 8:
        break;
      case 9:
        break;
      case 10:
        goto LAB_00029f40;
      case 0xb:
        break;
      case 0xc:
        break;
      case 0xd:
        goto switchD_00029e48_caseD_d;
      case 0xe:
        break;
      case 0xf:
        break;
      case 0x10:
        break;
      case 0x11:
        break;
      case 0x12:
        break;
      case 0x13:
        break;
      case 0x14:
        break;
      case 0x15:
        break;
      case 0x16:
        break;
      case 0x17:
        break;
      case 0x18:
        break;
      case 0x19:
        break;
      case 0x1a:
        break;
      case 0x1b:
        break;
      case 0x1c:
        break;
      case 0x1d:
        break;
      case 0x1e:
        break;
      case 0x1f:
        break;
      case 0x20:
        goto LAB_00029f40;
      case 0x21:
        break;
      case 0x22:
        break;
      case 0x23:
        break;
      case 0x24:
        break;
      case 0x25:
        break;
      case 0x26:
        break;
      case 0x27:
        break;
      case 0x28:
        break;
      case 0x29:
        break;
      case 0x2a:
        break;
      case 0x2b:
        break;
      case 0x2c:
        goto LAB_00029f40;
      case 0x2d:
        break;
      case 0x2e:
        break;
      case 0x2f:
        break;
      case 0x30:
        break;
      case 0x31:
        break;
      case 0x32:
        break;
      case 0x33:
        break;
      case 0x34:
        break;
      case 0x35:
        break;
      case 0x36:
        break;
      case 0x37:
        break;
      case 0x38:
        break;
      case 0x39:
        break;
      case 0x3a:
        break;
      case 0x3b:
LAB_00029f40:
        *puVar3 = 0;
        bVar1 = local_420 < puVar3;
        puVar3 = local_420;
        puVar5 = puVar4;
        if (bVar1) {
          uVar2 = buttontoi(local_420);
          *(undefined4 *)(param_1 + iVar6 * 4) = uVar2;
          iVar6 = iVar6 + 1;
        }
        goto LAB_00029e40;
      }
      *puVar3 = *puVar5;
      puVar3 = puVar3 + 1;
      puVar5 = puVar4;
      goto LAB_00029e40;
    }
  }
  return 0;
switchD_00029e48_caseD_d:
  puVar5 = puVar4;
  goto LAB_00029e40;
}
