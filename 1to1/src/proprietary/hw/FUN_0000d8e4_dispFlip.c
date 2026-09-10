/* ============================================================
 * dispFlip   @ 0x0000d8e4   size=320B   callers=25
 * module: 01_main_emurun_joystick
 * ============================================================ */

void dispFlip(undefined4 param_1,undefined4 param_2,undefined4 param_3,undefined4 param_4)

{
  if (DisplayThread == 0) {
    if (video_driver_frame == (code *)0x0) {
      return;
    }
  }
  else {
    while ((DisplayThreadflag & 2) != 0) {
      usleep(500);
      pthread_mutex_lock((pthread_mutex_t *)mutex);
      if ((DisplayThreadflag & 2) != 0) {
        pthread_cond_wait((pthread_cond_t *)cond,(pthread_mutex_t *)mutex);
      }
      pthread_mutex_unlock((pthread_mutex_t *)mutex);
    }
    Frame_data = param_1;
    Frame_height = param_3;
    Frame_pitch = param_4;
    Frame_width = param_2;
    pthread_mutex_lock((pthread_mutex_t *)mutex);
    DisplayThreadflag = DisplayThreadflag | 2;
    pthread_cond_signal((pthread_cond_t *)cond);
    pthread_mutex_unlock((pthread_mutex_t *)mutex);
    param_1 = Frame_data;
    param_2 = Frame_width;
    param_3 = Frame_height;
    param_4 = Frame_pitch;
  }
                    /* WARNING: Could not recover jumptable at 0x0000d9c4. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*video_driver_frame)(param_1,param_2,param_3,param_4);
  return;
}
