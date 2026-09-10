/* ============================================================
 * sunxi_gpio_input   @ 0x0000be4c   size=100B   callers=2
 * module: 09_gpio
 * ============================================================ */

uint sunxi_gpio_input(uint param_1)

{
  if (param_1 == 0) {
    return (*(uint *)(GPIO2 + 0x50) & 0xf) >> 3;
  }
  if (param_1 != 1) {
    if (param_1 != 2) {
      return param_1;
    }
    return (*(uint *)(GPIO0 + 0x50) & 3) >> 1;
  }
  return *(uint *)(GPIO0 + 0x50) & 1;
}
