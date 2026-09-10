/* ============================================================
 * xintiao   @ 0x0000a85c   size=44B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void xintiao(void)

{
  int *piVar1;
  undefined4 *puVar2;
  
  puVar2 = shm;
  piVar1 = shm + 1;
  *shm = 1;
  puVar2[1] = *piVar1 + 1;
  return;
}
