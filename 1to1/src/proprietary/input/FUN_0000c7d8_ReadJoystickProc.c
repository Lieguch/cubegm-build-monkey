/* ============================================================
 * ReadJoystickProc   @ 0x0000c7d8   size=96B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void ReadJoystickProc(void)

{
  uint uVar1;
  uint uVar2;
  uint uVar3;
  uint uVar4;
  undefined4 uVar5;
  
  uVar2 = RF_joy_key._4_4_;
  uVar1 = (uint)RF_joy_key;
  uVar3 = ReadUSBJoy(0);
  uVar4 = ReadUSBJoy(1);
  uVar5 = ReadUSBJoy(2);
  joy_key._12_4_ = ReadUSBJoy(3);
  joy_key._0_4_ = uVar1 | uVar3;
  joy_key._4_4_ = uVar2 | uVar4;
  joy_key._8_4_ = uVar5;
  return;
}
