/* ============================================================
 * InitRFJoystick   @ 0x0000d1c4   size=652B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void InitRFJoystick(void)

{
  int iVar1;
  pthread_t pStack_14;
  
  ReturnToMenu = 1;
  sunxi_gpio_set_cfgpin(0,1);
  sunxi_gpio_output(0,1);
  sunxi_gpio_set_cfgpin(1,1);
  sunxi_gpio_output(1,0);
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(2,1);
  osDelay(0x14);
  SPI_Write(0x53,0x5a);
  osDelay(0x14);
  SPI_Write(0x53,0xa5);
  osDelay(0x14);
  SPI_Write(0x25,0xa5);
  osDelay(0x32);
  iVar1 = SPI_Read(5);
  if (iVar1 != 0xa5) {
    RARCH_LOG("RF_IC Test Fail !\n");
    return;
  }
  RARCH_LOG("RF_IC Test Pass!\n");
  GetJoystickConfig(RF_JOYTable,0,0,1);
  GetJoystickConfig(0x3af06c,0,1,1);
  SPI_Write(0x3d,0x20);
  SPI_Write(0xfc,0);
  SPI_Write(0xe1,0);
  SPI_Write(0xe2,0);
  SPI_Write(0x20,0x8e);
  SPI_Write(0x27,0x70);
  SPI_Write_BUF(0x3f,5,&BB_cal_data);
  SPI_Write_BUF(0x3e,3,&RF_cal_data);
  SPI_Write(0x39,1);
  SPI_Write_BUF(0x3a,6,&RF_cal2_data);
  SPI_Write_BUF(0x3b,3,&Dem_cal2_data);
  SPI_Write(0x21,3);
  SPI_Write(0x22,3);
  SPI_Write(0x23,3);
  SPI_Write(0x24,2);
  SPI_Write(0x26,0x3f);
  SPI_Write(0x31,2);
  SPI_Write(0x32,2);
  SPI_Write(0x3c,0);
  SPI_Write_BUF(0x2a,5,&RX_ADDRESS0);
  SPI_Write_BUF(0x2b,5,&RX_ADDRESS1);
  RxMode();
  osDelay(0x28);
  SPI_Write(0x25,(undefined1)CHANNEL_TBL);
  RF_joy_key._0_4_ = 0;
  RF_joy_key._4_4_ = 0;
  pthread_create(&pStack_14,(pthread_attr_t *)0x0,RF_Joystick_timer_isr,(void *)0x0);
  return;
}
