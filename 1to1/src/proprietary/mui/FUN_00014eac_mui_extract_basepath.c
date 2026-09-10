/* ============================================================
 * mui_extract_basepath   @ 0x00014eac   size=88B   callers=3
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_extract_basepath(char *param_1,char *param_2,int param_3)

{
  char *pcVar1;
  
  strncpy(param_1,param_2,param_3 - 1);
  pcVar1 = strrchr(param_1,0x2f);
  if ((pcVar1 == (char *)0x0) && (pcVar1 = strrchr(param_1,0x5c), pcVar1 == (char *)0x0)) {
    *param_1 = '\0';
    return;
  }
  if (*pcVar1 == '/' || *pcVar1 == '\\') {
    *pcVar1 = '\0';
  }
  return;
}
