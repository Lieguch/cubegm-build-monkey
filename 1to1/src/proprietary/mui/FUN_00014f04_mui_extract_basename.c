/* ============================================================
 * mui_extract_basename   @ 0x00014f04   size=128B   callers=8
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_extract_basename(char *param_1,char *param_2,int param_3)

{
  char *pcVar1;
  
  pcVar1 = strrchr(param_2,0x2f);
  if ((pcVar1 == (char *)0x0) && (pcVar1 = strrchr(param_2,0x5c), pcVar1 == (char *)0x0)) {
    pcVar1 = param_2;
  }
  if (*pcVar1 == '/' || *pcVar1 == '\\') {
    pcVar1 = pcVar1 + 1;
  }
  strncpy(param_1,pcVar1,param_3 - 1U);
  param_1[param_3 - 1U] = '\0';
  pcVar1 = strrchr(param_1,0x2e);
  if (pcVar1 != (char *)0x0) {
    *pcVar1 = '\0';
  }
  return;
}
