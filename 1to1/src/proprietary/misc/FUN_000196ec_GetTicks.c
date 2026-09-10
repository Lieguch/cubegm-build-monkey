/* ============================================================
 * GetTicks   @ 0x000196ec   size=64B   callers=17
 * module: 01_main_emurun_joystick
 * ============================================================ */

int GetTicks(void)

{
  timeval local_18;
  
  gettimeofday(&local_18,(__timezone_ptr_t)0x0);
  return local_18.tv_sec * 1000 + local_18.tv_usec / 1000;
}
