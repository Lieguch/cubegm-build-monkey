/* ============================================================
 * CloseZipU   @ 0x000130c4   size=132B   callers=11
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 CloseZipU(int *param_1)

{
  TUnzip *this;
  
  if (param_1 == (int *)0x0) {
    lasterrorU = 0x10000;
    return 0x10000;
  }
  if (*param_1 != 1) {
    lasterrorU = 0x80000;
    return 0x80000;
  }
  this = (TUnzip *)param_1[1];
  lasterrorU = TUnzip::Close(this);
  operator_delete(this);
  operator_delete(param_1);
  return lasterrorU;
}
