/* ============================================================
 * PlaySound   @ 0x0000dbdc   size=32B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void PlaySound(void)

{
  if (sound_driver_playframe == (gh_code *)0x0) {
    return;
  }
                    /* WARNING: Could not recover jumptable at 0x0000dbf8. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*sound_driver_playframe)();
  return;
}
