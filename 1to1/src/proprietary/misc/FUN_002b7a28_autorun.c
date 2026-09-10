/* ============================================================
 * autorun   @ 0x002b7a28   size=60B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void autorun(undefined4 param_1,char *param_2)

{
  RARCH_LOG("autorun %s %s\n",param_1,param_2);
  InitScr();
  if (*param_2 != '\0') {
    return;
  }
  run_game(param_1);
  return;
}
