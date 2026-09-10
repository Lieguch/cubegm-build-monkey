/* ============================================================
 * InitSound   @ 0x0000db08   size=160B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitSound(void)

{
  if (handle == 0) {
    return;
  }
  sound_driver_init = (gh_code *)dlsym(handle,"sound_driver_init");
  if (sound_driver_init != (gh_code *)0x0) {
    (*sound_driver_init)(USE_HDMI_OUT,UpdateROM,2);
    sound_driver_playframe = dlsym(handle,"sound_driver_playframe");
    if (sound_driver_playframe != 0) {
      return;
    }
    puts("can\'t find sound_driver_playframe proc");
    return;
  }
  puts("can\'t find sound_driver_init proc");
  return;
}
