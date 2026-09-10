/* ============================================================
 * PlayFrame   @ 0x002b4d64   size=172B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 PlayFrame(undefined4 param_1,undefined4 param_2)

{
  int iVar1;
  timeval local_20;
  timeval local_18;
  
  gettimeofday(&local_20,(__timezone_ptr_t)0x0);
  PlaySound(param_1,param_2);
  gettimeofday(&local_18,(__timezone_ptr_t)0x0);
  iVar1 = ((local_18.tv_sec - local_20.tv_sec) * 1000000 + local_18.tv_usec) - local_20.tv_usec;
  if (8000 < iVar1) {
    gettimeofday((timeval *)&inTimeVal,(__timezone_ptr_t)0x0);
    diff_prev = 0;
    RARCH_LOG("Emurun [%d.%06d] ++++ Sound play timer over %dus ++++\n",local_18.tv_sec,
              local_18.tv_usec,iVar1);
  }
  return 0;
}
