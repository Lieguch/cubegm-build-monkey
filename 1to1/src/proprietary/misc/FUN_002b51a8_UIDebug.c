/* ============================================================
 * UIDebug   @ 0x002b51a8   size=468B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void UIDebug(int param_1,int param_2,undefined4 param_3,uint param_4)

{
  int iVar1;
  uint uVar2;
  undefined4 uVar3;
  size_t sVar4;
  undefined2 *puVar5;
  int iVar6;
  int *piVar7;
  uint uVar9;
  int iVar10;
  int iVar11;
  byte *pbVar12;
  int iVar13;
  uint in_fpscr;
  float fVar14;
  float fVar15;
  double dVar16;
  timeval *local_58;
  timeval local_50 [4];
  int *piVar8;
  
  param_4 = param_4 >> 1;
  iVar6 = 0;
  piVar7 = (int *)fpsbuf;
  do {
    piVar8 = piVar7 + 1;
    iVar6 = iVar6 + *piVar7;
    piVar7 = piVar8;
  } while (piVar8 != (int *)ticks_buf);
  local_58 = local_50;
  fVar14 = (float)VectorSignedToFloat(iVar6,(byte)(in_fpscr >> 0x16) & 3);
  fVar15 = 60.0;
  if (pal_ntsc != 0) {
    fVar15 = 50.0;
  }
  gettimeofday(local_58,(__timezone_ptr_t)0x0);
  uVar3 = DispFrameCount;
  iVar6 = local_50[0].tv_sec * 1000000 + local_50[0].tv_usec;
  if (1000000 < iVar6 - prev_time) {
    DispFrameCount = 0;
    fps0 = (float)VectorSignedToFloat(uVar3,(byte)(in_fpscr >> 0x16) & 3);
    prev_time = iVar6;
  }
  dVar16 = (double)(fVar15 * fVar14 * 0.0625);
  sprintf((char *)local_58,"%.02f %.02f",SUB84(dVar16,0),(int)((ulonglong)dVar16 >> 0x20),
          (double)fps0);
  sVar4 = strlen((char *)local_58);
  uVar9 = local_50[0].tv_sec & 0xff;
  if (uVar9 != 0) {
    iVar11 = param_4 + param_2 + -2 + sVar4 * -8;
    iVar6 = iVar11 * 2;
    iVar11 = iVar11 * -2;
    do {
      iVar1 = (uVar9 - 0x20) * 0x10;
      pbVar12 = &asc2_1608 + iVar1;
      iVar10 = iVar6;
      iVar13 = iVar11;
      do {
        uVar9 = 7;
        puVar5 = (undefined2 *)(param_1 + iVar10);
        do {
          uVar2 = uVar9 & 0xff;
          uVar9 = uVar9 - 1;
          if (((int)(uint)*pbVar12 >> uVar2 & 1U) == 0) {
            *puVar5 = 0;
          }
          else {
            *(undefined2 *)((int)puVar5 + iVar10 + iVar13) = 0xffe0;
          }
          puVar5 = puVar5 + 1;
        } while (uVar9 != 0xffffffff);
        pbVar12 = pbVar12 + 1;
        iVar13 = iVar13 + param_4 * -2;
        iVar10 = iVar10 + param_4 * 2;
      } while (&UNK_002e0938 + iVar1 != pbVar12);
      iVar11 = iVar11 + -0x10;
      iVar6 = iVar6 + 0x10;
      local_58 = (timeval *)((int)&local_58->tv_sec + 1);
      uVar9 = (uint)(byte)local_58->tv_sec;
    } while (uVar9 != 0);
  }
  return;
}
