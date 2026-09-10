/* ============================================================
 * sunxi_gpio_cleanup   @ 0x0000bebc   size=204B   callers=0
 * module: 09_gpio
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void sunxi_gpio_cleanup(void)

{
  if (CRU != (void *)0x0) {
    munmap(CRU,0x400);
    CRU = (void *)0x0;
  }
  if (GRF != (void *)0x0) {
    munmap(GRF,0x2000);
    GRF = (void *)0x0;
  }
  if (GPIO0 != (void *)0x0) {
    munmap(GPIO0,0x4000);
    GPIO0 = (void *)0x0;
  }
  if (GPIO1 != (void *)0x0) {
    munmap(GPIO1,0x4000);
    GPIO1 = (void *)0x0;
  }
  if (GPIO2 == (void *)0x0) {
    return;
  }
  munmap(GPIO2,0x4000);
  GPIO2 = (void *)0x0;
  return;
}
