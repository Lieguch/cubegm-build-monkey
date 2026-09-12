/* ============================================================
 * sunxi_gpio_output   @ 0x0000bd4c   size=232B   callers=9
 * module: 09_gpio
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 sunxi_gpio_output(int param_1,int param_2)

{
  if (param_1 != 0) {
    if (param_1 == 1) {
      if (param_2 == 0) {
        *(gh_u4 *)GPIO0 = *(gh_u4 *)GPIO0 & 0xfffffffe;
      }
      else {
        *(gh_u4 *)GPIO0 = *(gh_u4 *)GPIO0 | 1;
      }
    }
    else if (param_1 == 2) {
      if (param_2 == 0) {
        *(gh_u4 *)GPIO0 = *(gh_u4 *)GPIO0 & 0xfffffffd;
      }
      else {
        *(gh_u4 *)GPIO0 = *(gh_u4 *)GPIO0 | 2;
      }
    }
    return 0;
  }
  if (param_2 != 0) {
    *(gh_u4 *)GPIO2 = *(gh_u4 *)GPIO2 | 8;
    return 0;
  }
  *(gh_u4 *)GPIO2 = *(gh_u4 *)GPIO2 & 0xfffffff7;
  return 0;
}
