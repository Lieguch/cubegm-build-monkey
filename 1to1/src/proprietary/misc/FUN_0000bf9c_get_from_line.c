/* ============================================================
 * get_from_line   @ 0x0000bf9c   size=244B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

char * get_from_line(char *param_1,int param_2)

{
  size_t sVar1;
  char *pcVar2;
  int iVar3;
  char *pcVar4;
  undefined1 auStack_1c [4];
  
  sVar1 = strlen(param_1);
  if ((0 < (int)sVar1) && (pcVar2 = strchr(param_1,0x3d), pcVar2 != (char *)0x0)) {
    *pcVar2 = '\0';
    pcVar4 = pcVar2 + 1;
    iVar3 = strcmp(param_1,"I: Bus");
    if (iVar3 == 0) {
      __isoc99_sscanf(pcVar4,"%d Vendor=%x Product=%x Version=%x",auStack_1c,param_2,param_2 + 4,
                      param_2 + 8);
      pcVar4 = (char *)0x0;
    }
    else {
      iVar3 = strcmp(param_1,"N: Name");
      if (iVar3 == 0) {
        pcVar2 = stpcpy((char *)(param_2 + 0xc),pcVar2 + 2);
        pcVar2[(param_2 - (param_2 + 0xc)) + 10] = '\0';
        pcVar4 = (char *)0x0;
      }
      else {
        iVar3 = strcmp(param_1,"H: Handlers");
        if (iVar3 != 0) {
          return (char *)0x0;
        }
      }
    }
    return pcVar4;
  }
  return (char *)0x0;
}
