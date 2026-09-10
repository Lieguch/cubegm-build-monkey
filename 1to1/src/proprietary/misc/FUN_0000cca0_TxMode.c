/* ============================================================
 * TxMode   @ 0x0000cca0   size=88B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void TxMode(void)

{
  SPI_Write(0xfc,0);
  SPI_Write(0xe1,0);
  SPI_Write(0xe2,0);
  SPI_Write(0x27,0x70);
  SPI_Write(0x20,0x8e);
  osDelay(10);
  SPI_Write(0xfd,0);
  return;
}
