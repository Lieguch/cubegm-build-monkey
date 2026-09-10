/* ============================================================
 * spi_printf   @ 0x0000a6f0   size=116B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

void spi_printf(char *param_1,undefined4 param_2,undefined4 param_3,undefined4 param_4)

{
  int iVar1;
  undefined4 uStack_c;
  undefined4 uStack_8;
  undefined4 uStack_4;
  
  uStack_c = param_2;
  uStack_8 = param_3;
  uStack_4 = param_4;
  iVar1 = vsnprintf(bprintf_buf,0x200,param_1,&uStack_c);
  if (-1 < iVar1) {
    outputxy1(bprintf_buf);
    spi_printf_needflash = 1;
    printf("%s",bprintf_buf);
  }
  return;
}
