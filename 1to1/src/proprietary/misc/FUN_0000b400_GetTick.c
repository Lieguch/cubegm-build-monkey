/* ============================================================
 * GetTick   @ 0x0000b400   size=48B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

void GetTick(void)

{
  timeval local_10;
  
  gettimeofday(&local_10,(__timezone_ptr_t)0x0);
  return;
}
