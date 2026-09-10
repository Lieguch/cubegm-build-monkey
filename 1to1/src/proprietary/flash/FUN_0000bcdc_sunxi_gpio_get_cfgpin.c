/* ============================================================
 * sunxi_gpio_get_cfgpin   @ 0x0000bcdc   size=100B   callers=0
 * module: 09_gpio
 * ============================================================ */

uint sunxi_gpio_get_cfgpin(uint param_1)

{
  if (param_1 == 0) {
    return (*(uint *)(GPIO2 + 4) & 0xf) >> 3;
  }
  if (param_1 != 1) {
    if (param_1 != 2) {
      return param_1;
    }
    return (*(uint *)(GPIO0 + 4) & 3) >> 1;
  }
  return *(uint *)(GPIO0 + 4) & 1;
}
