/* ============================================================
 * TestLibz0   @ 0x0000b6b0   size=548B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 TestLibz0(void)

{
  FILE *__stream;
  void *__ptr;
  undefined4 uVar1;
  byte *pbVar2;
  size_t sVar3;
  uint uVar4;
  uint uVar5;
  byte *pbVar6;
  byte *unaff_r6;
  size_t unaff_r9;
  byte *pbVar7;
  size_t sVar8;
  size_t local_8c;
  size_t local_88;
  char acStack_84 [104];
  
  sprintf(acStack_84,"%s/images/02.raw",work_path);
  __stream = fopen(acStack_84,"rb");
  if (__stream == (FILE *)0x0) {
    printf("open %s fail\n",acStack_84);
  }
  else {
    fseek(__stream,0,2);
    unaff_r9 = ftell(__stream);
    printf("file size is %x\n",unaff_r9);
    unaff_r6 = malloc(unaff_r9);
    fseek(__stream,0,0);
    fread(unaff_r6,1,unaff_r9,__stream);
    fclose(__stream);
  }
  local_8c = unaff_r9;
  __ptr = malloc(unaff_r9);
  printf("compress %x %x %x %x\n",__ptr,unaff_r9,unaff_r6,unaff_r9);
  pbVar6 = (byte *)((int)__ptr + -1);
  uVar1 = compress(__ptr,&local_8c,unaff_r6,unaff_r9);
  printf("compress finished %x %d\n",local_8c,uVar1);
  do {
    pbVar6 = pbVar6 + 1;
    printf("%02x ",(uint)*pbVar6);
  } while (pbVar6 != (byte *)((int)__ptr + 0xf));
  putchar(10);
  local_88 = unaff_r9 << 1;
  pbVar6 = malloc(local_88);
  sVar3 = local_88;
  memset(pbVar6,0,local_88);
  sVar8 = local_8c;
  printf("uncompress %x %x %x %x\n",pbVar6,sVar3,__ptr,local_8c);
  uVar1 = uncompress(pbVar6,&local_88,__ptr,local_8c);
  printf("uncompress finished %x %d\n",local_88,uVar1);
  if (0 < (int)local_88) {
    uVar4 = (uint)*unaff_r6;
    uVar5 = (uint)*pbVar6;
    if (uVar5 == uVar4) {
      sVar3 = 0;
      pbVar2 = pbVar6;
      pbVar7 = unaff_r6;
      do {
        sVar3 = sVar3 + 1;
        if (sVar3 == local_88) goto LAB_0000b888;
        pbVar7 = pbVar7 + 1;
        uVar4 = (uint)*pbVar7;
        pbVar2 = pbVar2 + 1;
        uVar5 = (uint)*pbVar2;
      } while (uVar4 == uVar5);
    }
    else {
      sVar3 = 0;
    }
    printf("%08x: %02x %02x\n",sVar3,uVar4,uVar5,sVar8);
  }
LAB_0000b888:
  free(pbVar6);
  free(__ptr);
  free(unaff_r6);
  return 1;
}
