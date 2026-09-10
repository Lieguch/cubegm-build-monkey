/* ============================================================
 * UpdateROM   @ 0x0000ac44   size=912B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void UpdateROM(char *param_1)

{
  FILE *__stream;
  int *__ptr;
  int iVar1;
  int iVar2;
  void *__s;
  undefined4 uVar3;
  size_t unaff_r7;
  bool bVar4;
  char local_15c;
  char local_15b;
  char local_15a;
  undefined1 auStack_158 [4];
  undefined1 auStack_154 [268];
  int local_48;
  int local_30;
  int local_2c;
  
  __stream = fopen(param_1,"r+b");
  if (__stream == (FILE *)0x0) {
    printf("Load %s fail!\n",param_1);
    return;
  }
  fread(&local_15c,1,3,__stream);
  fclose(__stream);
  if (((local_15c != 'W') || (local_15b != 'Q')) || (local_15a != 'W')) {
    printf("%s format error!\n",param_1);
    return;
  }
  scr_h_size = 0x1e0;
  scr_v_size = 0x110;
  scr_data = malloc(0x3fc00);
  if (scr_data != (void *)0x0) {
    memset(scr_data,0,scr_v_size * scr_h_size * 2);
  }
  output_x = 0x14;
  output_y = 0x12;
  __ptr = malloc(0x10000);
  if ((char)spi_id == '\v') {
    uVar3 = 0x100;
  }
  else {
    uVar3 = 0x2000;
  }
  sflash_read_security_data(__ptr,uVar3);
  memset(auStack_158,0,0x130);
  iVar1 = OpenZipU(param_1,0,2);
  if (iVar1 == 0) {
    printf("%s openzip error!\n",param_1);
    __s = (void *)0x0;
  }
  else {
    iVar2 = GetZipItemA(iVar1,0,auStack_158);
    if (iVar2 == 0) {
      printf("%s,size:%08X,crc:%08X ",auStack_154,local_30,local_2c);
      printf("time:");
      DateToTmuDate(local_48);
      if (local_2c == *__ptr) {
        CloseZipU(iVar1);
        __s = (void *)0x0;
        goto LAB_0000af00;
      }
      if (local_30 < 0x4001) {
        unaff_r7 = 0x4000;
      }
      else {
        unaff_r7 = 0x4000;
        do {
          unaff_r7 = unaff_r7 * 2;
        } while ((int)unaff_r7 < local_30);
      }
      __s = malloc(unaff_r7);
      if (__s == (void *)0x0) {
        puts("Alloc memory fail!");
        return;
      }
      memset(__s,0xff,unaff_r7);
      UnzipItem(iVar1,0,__s,0,3);
      spi_printf("%08X UPDATE TO %08X\n",*__ptr,local_2c);
    }
    else {
      __s = (void *)0x0;
    }
    CloseZipU(iVar1);
    iVar1 = UpdateROMProc(__s,unaff_r7);
    if (iVar1 != 0) {
      if ((char)spi_id == '\v') {
        sflash_read_security_data(__ptr + 0x40,0);
        sflash_erase_security_data(0);
      }
      else {
        sflash_erase_security_data(0x2000);
      }
      memset(__ptr,0xff,0x100);
      bVar4 = (char)spi_id == '\v';
      *__ptr = local_2c;
      __ptr[1] = local_48;
      if (bVar4) {
        sflash_write_security_data(__ptr + 0x40,0);
        sflash_write_security_data(__ptr,0x100);
      }
      else {
        sflash_write_security_data(__ptr,0x2000);
      }
      spi_printf("REBOOT...           ");
      putchar(10);
      dispFlip(scr_data,scr_h_size,scr_v_size,scr_h_size << 1);
      free(__ptr);
      sync();
                    /* WARNING: Subroutine does not return */
      reboot(0x1234567);
    }
  }
LAB_0000af00:
  scr_h_size = 0x500;
  scr_v_size = 0x2d0;
  if (scr_data != (void *)0x0) {
    free(scr_data);
  }
  if (__ptr != (int *)0x0) {
    free(__ptr);
  }
  if (__s != (void *)0x0) {
    free(__s);
  }
  return;
}
