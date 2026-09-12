/* ============================================================
 * get_items_from_file   @ 0x0001f2fc   size=148B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int get_items_from_file(char *param_1,char *param_2)

{
  FILE *__stream;
  char *pcVar1;
  int iVar2;
  char acStack_418 [1028];
  
  __stream = fopen(param_1,"r");
  if (__stream == (FILE *)0x0) {
    iVar2 = -1;
  }
  else {
    iVar2 = 0;
    mainkey[0] = 0;
    while( true ) {
      pcVar1 = fgets(acStack_418,0x3ff,__stream);
      if (pcVar1 == (char *)0x0) break;
      get_item_from_line(acStack_418,param_2);
      iVar2 = iVar2 + 1;
      param_2 = param_2 + 0xfa;
    }
    close((int)__stream);
  }
  return iVar2;
}
