/* ============================================================
 * SetBacklight   @ 0x0000c8cc   size=28B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void SetBacklight(int param_1)

{
  if (param_1 == 0) {
    sunxi_gpio_output(0xcb);
    return;
  }
  sunxi_gpio_output(0xcb,1);
  return;
}
