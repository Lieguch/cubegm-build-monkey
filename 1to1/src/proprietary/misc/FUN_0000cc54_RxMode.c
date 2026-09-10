/* ============================================================
 * RxMode   @ 0x0000cc54   size=76B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void RxMode(void)

{
  SPI_Write(0xfc,0);
  SPI_Write(0xe1,0);
  SPI_Write(0xe2,0);
  SPI_Write(0x20,0x8f);
  osDelay(10);
  SPI_Write(0xfd,0);
  return;
}
