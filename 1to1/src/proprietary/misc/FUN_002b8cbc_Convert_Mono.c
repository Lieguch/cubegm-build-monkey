/* ============================================================
 * Convert_Mono   @ 0x002b8cbc   size=44B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void Convert_Mono(undefined2 *param_1)

{
  undefined2 *puVar1;
  undefined2 *puVar2;
  
  puVar1 = param_1 + 0x480;
  puVar2 = param_1 + 0x8fe;
  do {
    *puVar2 = puVar1[-1];
    puVar1 = puVar1 + -1;
    puVar2[1] = *puVar1;
    puVar2 = puVar2 + -2;
  } while (puVar1 != param_1);
  return;
}
