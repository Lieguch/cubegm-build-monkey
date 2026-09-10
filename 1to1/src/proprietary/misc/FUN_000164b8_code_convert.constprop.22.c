/* ============================================================
 * code_convert.constprop.22   @ 0x000164b8   size=144B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

int code_convert_constprop_22(undefined4 param_1,undefined4 param_2,void *param_3,size_t param_4)

{
  int iVar1;
  int iVar2;
  void *local_20;
  undefined4 local_1c;
  undefined4 local_18;
  size_t local_14;
  
  local_20 = param_3;
  local_1c = param_1;
  local_18 = param_2;
  local_14 = param_4;
  iVar1 = libiconv_open("GB2312","utf-8");
  if (iVar1 == 0) {
    iVar2 = -1;
  }
  else {
    memset(local_20,0,param_4);
    iVar2 = libiconv(iVar1,&local_1c,&local_18,&local_20,&local_14);
    if (iVar2 != -1) {
      libiconv_close(iVar1);
    }
  }
  return iVar2;
}
