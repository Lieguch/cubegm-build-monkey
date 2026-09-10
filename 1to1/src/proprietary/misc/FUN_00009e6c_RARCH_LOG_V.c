/* ============================================================
 * RARCH_LOG_V   @ 0x00009e6c   size=96B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void RARCH_LOG_V(char *param_1,__gnuc_va_list param_2)

{
  int __fd;
  
  if (log_file_initialized == '\0') {
    vfprintf(stdout,param_1,param_2);
    return;
  }
  vfprintf(log_file_fp,param_1,param_2);
  fflush(log_file_fp);
  __fd = fileno(log_file_fp);
  fsync(__fd);
  return;
}
