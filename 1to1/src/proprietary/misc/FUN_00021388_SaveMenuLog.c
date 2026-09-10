/* ============================================================
 * SaveMenuLog   @ 0x00021388   size=128B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SaveMenuLog(void)

{
  FILE *__s;
  int __fd;
  char acStack_108 [256];
  
  sprintf(acStack_108,"%s/menu.log",work_path);
  __s = fopen(acStack_108,"wb");
  if (__s != (FILE *)0x0) {
    fwrite(m_menulog,1,0x1bc,__s);
    fflush(__s);
    __fd = fileno(__s);
    fsync(__fd);
    fclose(__s);
  }
  return;
}
