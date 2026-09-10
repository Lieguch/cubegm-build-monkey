/* ============================================================
 * getticks   @ 0x0000ccf8   size=44B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

int getticks(void)

{
  timeval local_10;
  
  gettimeofday(&local_10,(__timezone_ptr_t)0x0);
  return local_10.tv_sec * 1000000 + local_10.tv_usec;
}
