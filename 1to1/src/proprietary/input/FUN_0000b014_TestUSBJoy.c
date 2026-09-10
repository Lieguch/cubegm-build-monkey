/* ============================================================
 * TestUSBJoy   @ 0x0000b014   size=708B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void TestUSBJoy(void)

{
  undefined4 uVar1;
  int iVar2;
  ssize_t sVar3;
  int iVar4;
  int *piVar5;
  int iVar6;
  undefined1 auStack_150 [4];
  short local_14c;
  undefined1 local_14a;
  undefined1 local_149;
  int local_148 [5];
  undefined4 uStack_134;
  undefined4 uStack_130;
  undefined4 uStack_12c;
  char local_128 [260];
  
  local_148[4] = DAT_003af008;
  uStack_134 = DAT_003af00c;
  uStack_130 = DAT_003af010;
  uStack_12c = DAT_003af014;
  scr_h_size = 0x1e0;
  scr_v_size = 0x110;
  scr_data = malloc(0x3fc00);
  if (scr_data != (void *)0x0) {
    memset(scr_data,0,scr_v_size * scr_h_size * 2);
  }
  output_x = 0x14;
  local_148[0] = -1;
  local_148[1] = 0xffffffff;
  local_148[2] = 0xffffffff;
  output_y = Rowspacing + 0x12;
  local_148[3] = 0xffffffff;
LAB_0000b12c:
  iVar4 = 0;
  piVar5 = local_148;
  iVar6 = local_148[0];
  do {
    sprintf(local_128,"/dev/input/js%d",iVar4);
    iVar2 = access(local_128,4);
    if (iVar2 < 0) {
      if (-1 < iVar6) {
        close(iVar6);
        spi_printf("USB Joystick %d Closed\n",iVar4);
        *piVar5 = -1;
      }
    }
    else {
      if (iVar6 < 0) {
        iVar6 = open(local_128,0x800);
        *piVar5 = iVar6;
        spi_printf("USB Joystick %d Opened\n",iVar4);
        if (iVar6 < 0) goto joined_r0x0000b1b8;
      }
      sVar3 = read(iVar6,auStack_150,8);
      if (sVar3 == 8) {
        spi_printf("JS%d value %6hd, type: %2u, axis/button: %u\n",iVar4,(int)local_14c,local_14a,
                   local_149);
      }
    }
joined_r0x0000b1b8:
    if (iVar4 == 3) break;
    iVar4 = iVar4 + 1;
    piVar5 = piVar5 + 1;
    iVar6 = *piVar5;
  } while( true );
  iVar6 = 0;
  memset((void *)(scr_h_size * 0x24 + (int)scr_data),0,Rowspacing * scr_h_size * 2);
  builtin_strncpy(local_128,"USB Joystick Test: ",0x14);
  do {
    if (local_148[iVar6] != -1) {
      strcat(local_128,(char *)local_148[iVar6 + 4]);
    }
    iVar4 = output_y;
    uVar1 = output_x;
    iVar6 = iVar6 + 1;
  } while (iVar6 != 4);
  output_x = 0x14;
  output_y = 10;
  outputxy1(local_128);
  output_x = uVar1;
  output_y = iVar4;
  dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
  usleep(20000);
  goto LAB_0000b12c;
}
