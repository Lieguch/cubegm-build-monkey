/* ============================================================
 * ReadJoystickProc   @ 0x0000c7d8   size=96B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

#ifdef CGM_DIAG_TRACE_INPUT
extern void cgm_probe_io(int tag, unsigned a, unsigned b);
#endif

void ReadJoystickProc(void)

{
  gh_uint uVar1;
  gh_uint uVar2;
  gh_uint uVar3;
  gh_uint uVar4;
  gh_u4 uVar5;
  
  uVar2 = RF_joy_key_blob._4_4_;
  uVar1 = (gh_uint)RF_joy_key;
  uVar3 = ReadUSBJoy(0);
  uVar4 = ReadUSBJoy(1);
  uVar5 = ReadUSBJoy(2);
  joy_key_blob._12_4_ = ReadUSBJoy(3);
  joy_key_blob._0_4_ = uVar1 | uVar3;
  joy_key_blob._4_4_ = uVar2 | uVar4;
#ifdef CGM_DIAG_TRACE_INPUT
  if (joy_key_blob._0_4_ != 0) cgm_probe_io('K', (unsigned)joy_key_blob._0_4_, (unsigned)joy_key_blob._4_4_);
#endif
  joy_key_blob._8_4_ = uVar5;
  return;
}
