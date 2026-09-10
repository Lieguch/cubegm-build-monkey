/* ============================================================
 * ReadUSBJoy   @ 0x0000c150   size=1092B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

uint ReadUSBJoy(int param_1)

{
  int iVar1;
  ssize_t sVar2;
  uint uVar3;
  uint uVar4;
  undefined1 auStack_40 [4];
  short local_3c;
  char local_3a;
  byte local_39;
  char acStack_38 [36];
  
  iVar1 = access((&JOYSTICK_DEVNAME)[param_1],4);
  if (iVar1 < 0) {
    if (*(int *)(&joystick_fd + param_1 * 4) < 0) {
      return *(uint *)(&joy_key_tmp + param_1 * 4);
    }
    close(*(int *)(&joystick_fd + param_1 * 4));
    *(undefined4 *)(&joystick_fd + param_1 * 4) = 0xffffffff;
    if (USBJoy_debug != 0) {
      spi_printf("%s %04x %04x %x js%d Closed\n",0x3e16a4,InputDeviceInfo._0_4_,
                 InputDeviceInfo._4_4_,InputDeviceInfo._8_4_,param_1);
      return *(uint *)(&joy_key_tmp + param_1 * 4);
    }
    return *(uint *)(&joy_key_tmp + param_1 * 4);
  }
  iVar1 = *(int *)(&joystick_fd + param_1 * 4);
  if (iVar1 < 0) {
    iVar1 = open((&JOYSTICK_DEVNAME)[param_1],0x800);
    *(int *)(&joystick_fd + param_1 * 4) = iVar1;
    if (iVar1 < 0) {
      return *(uint *)(&joy_key_tmp + param_1 * 4);
    }
    sprintf(acStack_38,"js%d",param_1);
    iVar1 = GetInputInfo(acStack_38,InputDeviceInfo);
    if (iVar1 != 0) {
      RARCH_LOG("%s %04x %04x %x js%d Opened!\n",0x3e16a4,InputDeviceInfo._0_4_,
                InputDeviceInfo._4_4_,InputDeviceInfo._8_4_,param_1);
      GetJoystickConfig(USB_Table + param_1 * 0x60,InputDeviceInfo._0_4_,InputDeviceInfo._4_4_,
                        InputDeviceInfo._8_4_);
    }
    if (USBJoy_debug != 0) {
      spi_printf("USB Joystick %d Opened\n",param_1 + 1);
    }
    iVar1 = *(int *)(&joystick_fd + param_1 * 4);
    *(undefined4 *)(&joy_key_tmp + param_1 * 4) = 0;
    if (iVar1 < 0) {
      return 0;
    }
  }
  sVar2 = read(iVar1,auStack_40,8);
  if (sVar2 != 8) {
    return *(uint *)(&joy_key_tmp + param_1 * 4);
  }
  if (USBJoy_debug != 0) {
    spi_printf("JS%d value %6hd, type: %2u, axis/button: %u\n",param_1 + 1,(int)local_3c,local_3a,
               local_39);
  }
  if (local_3a == '\x02') {
    uVar3 = (uint)local_39;
    iVar1 = param_1 * 0x60;
    if ((uVar3 == *(uint *)(USB_Table + iVar1 + 0x44)) ||
       (uVar3 == *(uint *)(USB_Table + iVar1 + 0x4c))) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4) & 0xffffffaf;
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (local_3c < -0x58ef) {
        *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x10;
        return uVar3 | 0x10;
      }
      if (local_3c < 0x58f0) {
        return uVar3;
      }
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x40;
      return uVar3 | 0x40;
    }
    if ((uVar3 == *(uint *)(USB_Table + iVar1 + 0x40)) ||
       (uVar3 == *(uint *)(USB_Table + iVar1 + 0x48))) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4) & 0xffffff5f;
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (local_3c < -0x58ef) {
        *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x80;
        return uVar3 | 0x80;
      }
      if (local_3c < 0x58f0) {
        return uVar3;
      }
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x20;
      return uVar3 | 0x20;
    }
    if ((uVar3 == *(uint *)(USB_Table + iVar1 + 0x50)) ||
       (uVar3 == *(uint *)(USB_Table + iVar1 + 0x58))) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4) & 0xffffafff;
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (local_3c < -0x58ef) {
        *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x1000;
        return uVar3 | 0x1000;
      }
      if (local_3c < 0x58f0) {
        return uVar3;
      }
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x4000;
      return uVar3 | 0x4000;
    }
    if ((uVar3 == *(uint *)(USB_Table + iVar1 + 0x54)) ||
       (uVar3 == *(uint *)(USB_Table + iVar1 + 0x5c))) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4) & 0xffff5fff;
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3;
      if (local_3c < -0x58ef) {
        *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x8000;
        return uVar3 | 0x8000;
      }
      if (local_3c < 0x58f0) {
        return uVar3;
      }
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 | 0x2000;
      return uVar3 | 0x2000;
    }
  }
  else if (local_3a == '\x01') {
    if (local_3c == 1) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4);
      uVar4 = *(uint *)(USB_Table + (param_1 * 0x18 + (uint)local_39) * 4);
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar4 | uVar3;
      return uVar4 | uVar3;
    }
    if (local_3c == 0) {
      uVar3 = *(uint *)(&joy_key_tmp + param_1 * 4);
      uVar4 = *(uint *)(USB_Table + (param_1 * 0x18 + (uint)local_39) * 4);
      *(uint *)(&joy_key_tmp + param_1 * 4) = uVar3 & ~uVar4;
      return uVar3 & ~uVar4;
    }
  }
  return *(uint *)(&joy_key_tmp + param_1 * 4);
}
