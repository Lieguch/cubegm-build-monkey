/* ============================================================
 * run_process   @ 0x002b59bc   size=124B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 run_process(undefined4 param_1,int param_2)

{
  pf = (code *)dlsym(handle,param_1);
  if (pf == (code *)0x0) {
    RARCH_LOG("find %s process fail \n",param_1);
    return 0;
  }
  if (param_2 != 0) {
    (*pf)(param_2);
    return 1;
  }
  (*pf)();
  return 1;
}
