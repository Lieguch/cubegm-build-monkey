/* ============================================================
 * GetCoreIndex   @ 0x002b5624   size=136B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

int GetCoreIndex(char *param_1)

{
  int iVar1;
  char *__s1;
  int iVar2;
  
  iVar2 = 0;
  __s1 = &default_core_list;
  while( true ) {
    if (*__s1 == '\0') {
      return -1;
    }
    iVar1 = strcmp(__s1,param_1);
    if (iVar1 == 0) break;
    iVar2 = iVar2 + 1;
    __s1 = __s1 + 0x44;
    if (iVar2 == 100) {
      return -1;
    }
  }
  Filetype = *(uint *)(&DAT_003b0274 + iVar2 * 0x44) | Filetype;
  return iVar2;
}
