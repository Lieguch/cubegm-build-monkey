/* ============================================================
 * ScaleDisplayThread   @ 0x0000d518   size=236B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 ScaleDisplayThread(void)

{
  while ((DisplayThreadflag & 1) != 0) {
    if ((DisplayThreadflag & 2) != 0) {
      if (video_driver_frame != (code *)0x0) {
        (*video_driver_frame)(Frame_data,Frame_width,Frame_height,Frame_pitch);
      }
      pthread_mutex_lock((pthread_mutex_t *)mutex);
      DisplayThreadflag = DisplayThreadflag & 0xfffd;
      pthread_cond_signal((pthread_cond_t *)cond);
      pthread_mutex_unlock((pthread_mutex_t *)mutex);
    }
    pthread_mutex_lock((pthread_mutex_t *)mutex);
    if ((DisplayThreadflag & 2) == 0) {
      pthread_cond_wait((pthread_cond_t *)cond,(pthread_mutex_t *)mutex);
    }
    pthread_mutex_unlock((pthread_mutex_t *)mutex);
  }
  return 0;
}
