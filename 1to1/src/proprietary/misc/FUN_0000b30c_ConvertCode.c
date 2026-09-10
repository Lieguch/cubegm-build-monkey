/* ============================================================
 * ConvertCode   @ 0x0000b30c   size=232B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

int ConvertCode(undefined4 param_1,undefined4 param_2,undefined4 param_3,undefined4 param_4,
               void *param_5,size_t param_6)

{
  int iVar1;
  int iVar2;
  int *piVar3;
  undefined4 local_18;
  undefined4 local_14 [2];
  
  local_18 = param_4;
  local_14[0] = param_3;
  iVar1 = libiconv_open(param_2,param_1);
  if (iVar1 == -1) {
    iVar2 = -1;
  }
  else {
    memset(param_5,0,param_6);
    iVar2 = libiconv(iVar1,local_14,&local_18,&param_5,&param_6);
    if (iVar2 == -1) {
      piVar3 = __errno_location();
      iVar1 = *piVar3;
      if (iVar1 == 0x16) {
        puts("EINVAL");
        return -1;
      }
      if (iVar1 == 0x54) {
        puts("EILSEQ");
        return -1;
      }
      if (iVar1 == 7) {
        puts("E2BiG");
        return -1;
      }
    }
    else {
      libiconv_close(iVar1);
    }
  }
  return iVar2;
}
