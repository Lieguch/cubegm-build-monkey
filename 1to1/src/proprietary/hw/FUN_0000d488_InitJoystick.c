/* ============================================================
 * InitJoystick   @ 0x0000d488   size=104B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitJoystick(void)

{
  int iVar1;
  
  iVar1 = (int)sunxi_gpio_init();
  if (iVar1 != 0) {
    RARCH_LOG("Failed to initialize GPIO\n");
  }
  InitRFJoystick();
  joy_key_blob._0_4_ = 0;
  joy_key_blob._4_4_ = 0;
  IR_JoyKey._0_1_ = 0;
  IR_JoyKey._1_1_ = 0;
  joytemp0 = 0;
  joytemp1 = 0;
  return;
}
