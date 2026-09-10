/* ============================================================
 * ClearBuffer   @ 0x002bdefc   size=32B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void ClearBuffer(undefined1 *param_1,int param_2)

{
  undefined1 *puVar1;
  undefined1 *puVar2;
  
  if (param_2 < 1) {
    return;
  }
  puVar2 = param_1;
  do {
    puVar1 = puVar2 + 1;
    *puVar2 = 0;
    puVar2 = puVar1;
  } while (puVar1 != param_1 + param_2);
  return;
}
