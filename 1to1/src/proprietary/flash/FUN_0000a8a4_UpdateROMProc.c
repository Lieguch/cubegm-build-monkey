/* ============================================================
 * UpdateROMProc   @ 0x0000a8a4   size=792B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 UpdateROMProc(int param_1,int param_2)

{
  void *__ptr;
  int iVar1;
  undefined4 uVar2;
  int iVar3;
  char *pcVar4;
  char *pcVar5;
  void *pvVar6;
  void *pvVar7;
  int iVar8;
  int local_58;
  int local_48;
  int local_44;
  pthread_t apStack_2c [2];
  
  __ptr = malloc(0x10000);
  iVar1 = pthread_create(apStack_2c,(pthread_attr_t *)0x0,XintiaoThread,(void *)0x0);
  if (iVar1 != 0) {
    puts("can\'t create XintiaoThread process thread \r");
  }
  putchar(10);
  if (0 < param_2) {
    iVar1 = 0;
    local_58 = 0;
    local_44 = param_1;
    do {
      printf("\b\r");
      uVar2 = __aeabi_idiv(local_58,param_2);
      spi_printf("%08X %3d%%",iVar1,uVar2);
      local_48 = 3;
      while( true ) {
        spi_printf(&DAT_002dbe58);
        dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
        pvVar6 = __ptr;
        do {
          pvVar7 = (void *)((int)pvVar6 + 0x100);
          iVar3 = spi_read((iVar1 - (int)__ptr) + (int)pvVar6,pvVar6);
          if (iVar3 < 0) goto LAB_0000aa00;
          pvVar6 = pvVar7;
        } while (pvVar7 != (void *)((int)__ptr + 0x10000));
        iVar8 = param_2 - iVar1;
        pcVar5 = (char *)((int)__ptr + -1);
        pcVar4 = (char *)(local_44 + -1);
        iVar3 = 0;
        if (0xffff < iVar8) {
          iVar8 = 0x10000;
        }
        while( true ) {
          pcVar4 = pcVar4 + 1;
          pcVar5 = pcVar5 + 1;
          if (*pcVar4 != *pcVar5) break;
          iVar3 = iVar3 + 1;
          if (iVar8 <= iVar3) goto LAB_0000aa64;
        }
        if (iVar8 <= iVar3) break;
        spi_printf(&DAT_002dbe5c);
        dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
        iVar3 = erase_sector(iVar1);
        if (-1 < iVar3) {
          spi_printf(&DAT_002dbe60);
          dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
          iVar3 = local_44;
          do {
            iVar8 = iVar3 + 0x100;
            iVar3 = spi_write((iVar1 - local_44) + iVar3,iVar3);
            if (iVar3 < 0) break;
            iVar3 = iVar8;
          } while (iVar8 != local_44 + 0x10000);
        }
        local_48 = local_48 + -1;
        if (local_48 == 0) {
          spi_printf("Update fail.\n");
LAB_0000aa00:
          free(__ptr);
          return 0xffffffff;
        }
      }
LAB_0000aa64:
      spi_printf("           \n");
      iVar1 = iVar1 + 0x10000;
      local_44 = local_44 + 0x10000;
      local_58 = local_58 + 0x640000;
    } while (iVar1 != (param_2 - 1U & 0xffff0000) + 0x10000);
  }
  printf("\b\r");
  spi_printf("100% OK           \n");
  uVar2 = dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
  return uVar2;
}
