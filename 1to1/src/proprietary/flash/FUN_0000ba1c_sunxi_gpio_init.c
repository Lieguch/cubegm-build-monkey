/* ============================================================
 * sunxi_gpio_init   @ 0x0000ba1c   size=428B   callers=1
 * module: 09_gpio
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void * sunxi_gpio_init(void)

{
  int __fd;
  void *pvVar1;
  
  __fd = open("/dev/mem",2);
  if (__fd < 0) {
    pvVar1 = (void *)0x1;
  }
  else {
    pvVar1 = mmap((void *)0x0,0x400,3,1,__fd,0x20000000);
    CRU = pvVar1;
    if (pvVar1 != (void *)0xffffffff) {
      GRF = mmap((void *)0x0,0x2000,3,1,__fd,0x20008000);
      if ((((GRF != (void *)0xffffffff) &&
           (GPIO0 = mmap((void *)0x0,0x4000,3,1,__fd,0x2007c000), GPIO0 != (void *)0xffffffff)) &&
          (GPIO1 = mmap((void *)0x0,0x4000,3,1,__fd,0x20080000), GPIO1 != (void *)0xffffffff)) &&
         (GPIO2 = mmap((void *)0x0,0x4000,3,1,__fd,0x20084000), GPIO2 != (void *)0xffffffff)) {
        close(__fd);
        printf("CRU_CLKGATE8_CON:%x\n",*(undefined4 *)((int)CRU + 0xf0));
        pvVar1 = CRU;
        *(uint *)((int)CRU + 0xf0) = *(uint *)((int)CRU + 0xf0) & 0xf1fff1ff | 0xe000000;
        printf("CRU_CLKGATE8_CON:%x\n",*(undefined4 *)((int)pvVar1 + 0xf0));
        printf("GRF_GPIO0A_IOMUX:%X\n",*(undefined4 *)((int)GRF + 0xa8));
        pvVar1 = GRF;
        *(uint *)((int)GRF + 200) = *(uint *)((int)GRF + 200) & 0xff3fff3f | 0xc00000;
        printf("GRF_GPIO2A_IOMUX:%X\n",*(undefined4 *)((int)pvVar1 + 200));
        return (void *)0x0;
      }
      pvVar1 = (void *)0x3;
    }
  }
  return pvVar1;
}
