/* ============================================================
 * mui_ReadJoystick   @ 0x0002141c   size=16B   callers=13
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

uint mui_ReadJoystick(void)

{
  uint uVar1;
  
  uVar1 = ReadJoystick();
  return uVar1 & 0xefffffff;
}
