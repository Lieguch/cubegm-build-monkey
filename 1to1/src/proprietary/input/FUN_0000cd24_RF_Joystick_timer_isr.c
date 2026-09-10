/* ============================================================
 * RF_Joystick_timer_isr   @ 0x0000cd24   size=1136B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void RF_Joystick_timer_isr(void)

{
  int iVar1;
  gh_uint uVar2;
  int iVar3;
  gh_uint uVar4;
  gh_byte local_2c;
  gh_byte local_2b;
  
  do {
    while( true ) {
      iVar1 = getticks();
      uVar2 = SPI_Read(7);
      if ((uVar2 & 0x40) == 0) break;
      SPI_Write(0xfc,0);
      SPI_Read_BUF(0x61,2,&local_2c);
      iVar3 = (int)(uVar2 << 0x1e) >> 0x1f;
      local_2b = ~local_2b;
      uVar2 = local_2b & 0x20;
      if ((local_2b & 0x20) != 0) {
        uVar2 = *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c);
      }
      if ((local_2b & 0x10) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 4);
      }
      if ((local_2b & 8) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 8);
      }
      if ((local_2b & 4) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0xc);
      }
      if ((local_2b & 2) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x10);
      }
      if ((local_2b & 1) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x14);
      }
      if ((local_2b & 0x80) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x18);
      }
      if ((local_2b & 0x40) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x1c);
      }
      if ((local_2c & 8) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x20);
      }
      if ((local_2c & 0x40) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x24);
      }
      if ((local_2c & 0x20) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x28);
      }
      if ((local_2c & 0x10) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x2c);
      }
      if ((local_2c & 2) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x30);
      }
      if ((local_2c & 4) != 0) {
        uVar2 = uVar2 | *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x34);
      }
      *(gh_uint *)((int)&RF_joy_key + iVar3 * -4) = uVar2;
      *(gh_u2 *)((int)&TimeCountReg + iVar3 * -2) = 0;
      if ((local_2c & 1) != 0) {
        *(gh_uint *)((int)&RF_joy_key + iVar3 * -4) =
             *(gh_uint *)(RF_JOYTable + iVar3 * -0x3c + 0x38) | uVar2;
      }
      SPI_Write(0xe2,0);
      SPI_Write(0x27,0x70);
      SPI_Write(0xfd,0);
      iVar3 = getticks();
      if (300 < (gh_uint)(iVar3 - iVar1)) goto LAB_0000cfd4;
LAB_0000cddc:
      uVar2 = (gh_uint)ChannelIndex;
      uVar4 = uVar2 + 1 & 7;
      ChannelIndex = (gh_byte)uVar4;
      if ((uVar2 + 1 & 1) == 0) {
        SPI_Write(0x25,*(gh_u1 *)((int)&CHANNEL_TBL + (uVar4 >> 1)));
      }
      TimeCountReg._0_2_ = (gh_ushort)TimeCountReg + 1;
      TimeCountReg._2_2_ = TimeCountReg._2_2_ + 1;
      if (0x100 < (gh_ushort)TimeCountReg) {
        RF_joy_key._0_4_ = 0;
      }
      if (0x100 < TimeCountReg._2_2_) {
        RF_joy_key._4_4_ = 0;
      }
      usleep(4000);
    }
    iVar3 = getticks();
    if ((gh_uint)(iVar3 - iVar1) < 0x12d) goto LAB_0000cddc;
LAB_0000cfd4:
    SPI_Write(0x53,0x5a);
    usleep(2000);
    SPI_Write(0x53,0xa5);
    usleep(2000);
    SPI_Write(0x3d,0x20);
    SPI_Write(0xfc,0);
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
    SPI_Write(0xe1,0);
    SPI_Write(0xe2,0);
    SPI_Write(0x20,0x8f);
    SPI_Write(0xfd,0);
    uVar2 = (gh_uint)ChannelIndex;
    uVar4 = uVar2 + 1 & 7;
    ChannelIndex = (gh_byte)uVar4;
    if ((uVar2 + 1 & 1) == 0) {
      SPI_Write(0x25,*(gh_u1 *)((int)&CHANNEL_TBL + (uVar4 >> 1)));
    }
    TimeCountReg._0_2_ = (gh_ushort)TimeCountReg + 1;
    TimeCountReg._2_2_ = TimeCountReg._2_2_ + 1;
    if (0x100 < (gh_ushort)TimeCountReg) {
      RF_joy_key._0_4_ = 0;
    }
    if (0x100 < TimeCountReg._2_2_) {
      RF_joy_key._4_4_ = 0;
    }
  } while( true );
}
