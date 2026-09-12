/* ============================================================
 * spi_printf   @ 0x0000a6f0   size=116B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* 证据：a6f0 push{r0,r1,r2,r3} + a704 add r3,sp,#28 / str r3,[sp,#4]（= 指向已存 r1）
   → 即 AAPCS32 变参序言，原函数为变参 spi_printf(char*, ...)，此处按原形还原 */
void spi_printf(char *param_1, ...)

{
  int iVar1;
  va_list ap;
  
  va_start(ap, param_1);
  iVar1 = vsnprintf(bprintf_buf,0x200,param_1,ap);
  va_end(ap);
  if (-1 < iVar1) {
    outputxy1(bprintf_buf);
    spi_printf_needflash = 1;
    printf("%s",bprintf_buf);
  }
  return;
}
