/* ============================================================
 * ReadUSBJoy   @ 0x0000c150   size=1092B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_uint ReadUSBJoy(int param_1)

{
  int iVar1;
  ssize_t sVar2;
  gh_uint uVar3;
  gh_uint uVar4;
  /* ★★ 2026-09-27 根修（UB）：Ghidra 把**一块 8 字节缓冲**（Linux `struct js_event`：
   *   time(4) / value(2) / type(1) / number(1)）拆成了 4 个独立声明，
   *   `read(iVar1, auStack_40, 8)` 只写了被看见的那一部分 ⇒ 其余三个字段在编译器看来
   *   **从未被写** ⇒ 读未初始化 = UB ⇒ 优化器删码。
   *   实测：-O0=14744B（完整） / -Os=**520B**（工厂 1196B，0.435x）。
   *   修法：恢复成一块真缓冲 + 三个按偏移的视图（偏移由 `struct js_event` 布局取证）。 */
  gh_u1 ev_buf[8];
#define ev_value  (*(short *)(void *)(ev_buf + 4))
#define ev_type   (*(unsigned char *)(void *)(ev_buf + 6))
#define ev_number (*(unsigned char *)(void *)(ev_buf + 7))
  char acStack_38 [36];
  
  iVar1 = access((&JOYSTICK_DEVNAME)[param_1],4);
  if (iVar1 < 0) {
    if (*(int *)(&joystick_fd + param_1 * 4) < 0) {
      return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
    }
    close(*(int *)(&joystick_fd + param_1 * 4));
    *(gh_u4 *)(&joystick_fd + param_1 * 4) = 0xffffffff;
    if (USBJoy_debug != 0) {
      spi_printf("%s %04x %04x %x js%d Closed\n",0x3e16a4,(InputDeviceInfo_blob)._0_4_,
                 (InputDeviceInfo_blob)._4_4_,(InputDeviceInfo_blob)._8_4_,param_1);
      return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
    }
    return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
  }
  iVar1 = *(int *)(&joystick_fd + param_1 * 4);
  if (iVar1 < 0) {
    iVar1 = open((&JOYSTICK_DEVNAME)[param_1],0x800);
    *(int *)(&joystick_fd + param_1 * 4) = iVar1;
    if (iVar1 < 0) {
      return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
    }
    sprintf(acStack_38,"js%d",param_1);
    iVar1 = GetInputInfo(acStack_38,InputDeviceInfo);
    if (iVar1 != 0) {
      RARCH_LOG("%s %04x %04x %x js%d Opened!\n",0x3e16a4,(InputDeviceInfo_blob)._0_4_,
                (InputDeviceInfo_blob)._4_4_,(InputDeviceInfo_blob)._8_4_,param_1);
      GetJoystickConfig(USB_Table + param_1 * 0x60,(InputDeviceInfo_blob)._0_4_,(InputDeviceInfo_blob)._4_4_,
                        (InputDeviceInfo_blob)._8_4_);
    }
    if (USBJoy_debug != 0) {
      spi_printf("USB Joystick %d Opened\n",param_1 + 1);
    }
    iVar1 = *(int *)(&joystick_fd + param_1 * 4);
    *(gh_u4 *)(&joy_key_tmp + param_1 * 4) = 0;
    if (iVar1 < 0) {
      return 0;
    }
  }
  sVar2 = read(iVar1,ev_buf,8);
  if (sVar2 != 8) {
    return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
  }
  if (USBJoy_debug != 0) {
    spi_printf("JS%d value %6hd, type: %2u, axis/button: %u\n",param_1 + 1,(int)ev_value,ev_type,
               ev_number);
  }
  if (ev_type == '\x02') {
    uVar3 = (gh_uint)ev_number;
    iVar1 = param_1 * 0x60;
    if ((uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x44)) ||
       (uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x4c))) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4) & 0xffffffaf;
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (ev_value < -0x58ef) {
        *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x10;
        return uVar3 | 0x10;
      }
      if (ev_value < 0x58f0) {
        return uVar3;
      }
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x40;
      return uVar3 | 0x40;
    }
    if ((uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x40)) ||
       (uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x48))) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4) & 0xffffff5f;
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (ev_value < -0x58ef) {
        *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x80;
        return uVar3 | 0x80;
      }
      if (ev_value < 0x58f0) {
        return uVar3;
      }
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x20;
      return uVar3 | 0x20;
    }
    if ((uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x50)) ||
       (uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x58))) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4) & 0xffffafff;
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (ev_value < -0x58ef) {
        *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x1000;
        return uVar3 | 0x1000;
      }
      if (ev_value < 0x58f0) {
        return uVar3;
      }
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x4000;
      return uVar3 | 0x4000;
    }
    if ((uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x54)) ||
       (uVar3 == *(gh_uint *)(USB_Table + iVar1 + 0x5c))) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4) & 0xffff5fff;
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (ev_value < -0x58ef) {
        *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x8000;
        return uVar3 | 0x8000;
      }
      if (ev_value < 0x58f0) {
        return uVar3;
      }
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x2000;
      return uVar3 | 0x2000;
    }
  }
  else if (ev_type == '\x01') {
    if (ev_value == 1) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4);
      uVar4 = *(gh_uint *)(USB_Table + (param_1 * 0x18 + (gh_uint)ev_number) * 4);
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar4 | uVar3;
      return uVar4 | uVar3;
    }
    if (ev_value == 0) {
      uVar3 = *(gh_uint *)(&joy_key_tmp + param_1 * 4);
      uVar4 = *(gh_uint *)(USB_Table + (param_1 * 0x18 + (gh_uint)ev_number) * 4);
      *(gh_uint *)(&joy_key_tmp + param_1 * 4) = uVar3 & ~uVar4;
      return uVar3 & ~uVar4;
    }
  }
  return *(gh_uint *)(&joy_key_tmp + param_1 * 4);
}
