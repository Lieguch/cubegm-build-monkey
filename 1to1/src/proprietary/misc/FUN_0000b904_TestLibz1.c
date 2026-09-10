/* ============================================================
 * TestLibz1   @ 0x0000b904   size=248B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void TestLibz1(void)

{
  int iVar1;
  undefined4 local_1b0;
  undefined4 local_1ac;
  undefined1 auStack_1a8 [200];
  char local_e0 [4];
  char acStack_dc [200];
  
  local_1b0 = 200;
  iVar1 = compress(auStack_1a8,&local_1b0,"12345678901234567890123456789012345678901234567890",0x33)
  ;
  if (iVar1 == 0) {
    printf("orignal size: %d, compressed size :%d\n",0x33,local_1b0);
    local_1ac = 200;
    local_e0[0] = 'g';
    local_e0[1] = 'a';
    local_e0[2] = 'r';
    local_e0[3] = 'b';
    acStack_dc[0] = 'a';
    acStack_dc[1] = 'g';
    acStack_dc[2] = 'e';
    acStack_dc[3] = '\0';
    iVar1 = uncompress(local_e0,&local_1ac,auStack_1a8,local_1b0);
    if (iVar1 != 0) {
      printf("uncompress error: %d\n");
      return;
    }
    printf("orignal size: %d, uncompressed size :%d\n",0x33,local_1ac);
    iVar1 = strcmp(local_e0,"12345678901234567890123456789012345678901234567890");
    if (iVar1 != 0) {
      puts("BAD uncompress!!!");
      return;
    }
    printf("uncompress() succeed: %s\n",local_e0);
  }
  else {
    printf("compess error: %d\n");
  }
  return;
}
