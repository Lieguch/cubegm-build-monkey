/* ============================================================
 * sunxi_gpio_get_cfgpin   @ 0x0000bcdc   size=100B   callers=0
 * module: 09_gpio
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_uint sunxi_gpio_get_cfgpin(gh_uint param_1)

{
  if (param_1 == 0) {
    return (*(gh_uint *)(GPIO2 + 4) & 0xf) >> 3;
  }
  if (param_1 != 1) {
    if (param_1 != 2) {
      return param_1;
    }
    return (*(gh_uint *)(GPIO0 + 4) & 3) >> 1;
  }
  return *(gh_uint *)(GPIO0 + 4) & 1;
}
