/* ============================================================
 * SPI_Read   @ 0x0000caa4   size=104B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 SPI_Read(undefined4 param_1)

{
  undefined4 uVar1;
  
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(0);
  SPI_WW(param_1);
  sunxi_gpio_set_cfgpin(2,0);
  uVar1 = SPI_RR();
  sunxi_gpio_output(0,1);
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(2,1);
  return uVar1;
}
