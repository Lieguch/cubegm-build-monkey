/* ============================================================
 * sfc_request   @ 0x002c39f0   size=860B   callers=9
 * module: 01_main_emurun_joystick
 * ============================================================ */

uint sfc_request(uint *param_1,uint param_2,uint *param_3,uint param_4)

{
  uint uVar1;
  uint uVar2;
  uint *puVar3;
  uint uVar4;
  uint *puVar5;
  uint *puVar6;
  int iVar7;
  uint *puVar8;
  int iVar9;
  uint uVar10;
  
  puVar3 = g_sfc_reg;
  if (((g_sfc_reg[8] & 6) != 6) || ((g_sfc_reg[9] & 1) != 0)) {
    g_sfc_reg[4] = 1;
    if (puVar3[4] == 1) {
      iVar7 = 10000;
      do {
        usleep(1);
        iVar7 = iVar7 + -1;
        puVar3 = g_sfc_reg;
      } while (g_sfc_reg[4] == 1 && iVar7 != 0);
    }
    puVar3[2] = 0xffffffff;
  }
  puVar3 = g_sfc_reg;
  uVar1 = *param_1;
  uVar4 = (uVar1 & 0xffff) >> 8;
  uVar10 = uVar4 & 0xc0;
  if (uVar10 == 0xc0) {
    if ((param_1[1] & 0x1f0000) == 0) {
      return 0xfffffffe;
    }
    g_sfc_reg[6] = ((param_1[1] & 0x1fffff) >> 0x10) - 1;
  }
  uVar2 = param_1[1] | 2;
  param_1[1] = uVar2;
  if (3 < (puVar3[0xb] & 0xffff)) {
    puVar3[0x23] = param_4;
    uVar2 = param_1[1];
  }
  *puVar3 = uVar2;
  puVar3[0x40] = uVar1 & 0xc000ffff | (param_4 & 0x3fff) << 0x10;
  if (uVar10 != 0) {
    puVar3[0x41] = param_2;
  }
  if (param_4 == 0) {
    uVar1 = 0;
  }
  else if ((uVar4 & 0x10) == 0) {
    uVar4 = param_4 >> 2;
    uVar1 = 0;
    if (uVar4 != 0) {
      puVar5 = puVar3 + 8;
      uVar1 = *puVar5;
      iVar7 = 0;
      do {
        uVar1 = (uVar1 & 0x1fffff) >> 0x10;
        if (uVar1 == 0) {
          usleep(1);
          iVar9 = iVar7 + 1;
          puVar3 = g_sfc_reg;
          if (10000 < iVar7) {
            uVar1 = 0xfffffffc;
            break;
          }
          puVar5 = g_sfc_reg + 8;
        }
        else {
          if (uVar4 <= uVar1) {
            uVar1 = uVar4;
          }
          puVar6 = param_3 + uVar1;
          do {
            puVar8 = param_3 + 1;
            *param_3 = puVar3[0x42];
            param_3 = puVar8;
          } while (puVar8 != puVar6);
          uVar4 = uVar4 - uVar1;
          uVar1 = 0;
          param_3 = puVar6;
          if (uVar4 == 0) break;
          iVar9 = 0;
        }
        uVar1 = *puVar5;
        iVar7 = iVar9;
      } while( true );
    }
    if ((param_4 & 3) != 0) {
      if ((puVar3[8] & 0x1f0000) == 0) {
        iVar7 = 0x2711;
        usleep(1);
        do {
          puVar3 = g_sfc_reg;
          if ((g_sfc_reg[8] & 0x1f0000) != 0) goto LAB_002c3d08;
          usleep(1);
          iVar7 = iVar7 + -1;
        } while (iVar7 != 0);
        uVar1 = 0xfffffffc;
        puVar3 = g_sfc_reg;
      }
      else {
LAB_002c3d08:
        uVar4 = puVar3[0x42];
        uVar10 = 0;
        puVar5 = param_3;
        do {
          puVar6 = (uint *)((int)puVar5 + 1);
          *(char *)puVar5 = (char)(uVar4 >> (uVar10 & 0xff));
          uVar10 = uVar10 + 8;
          puVar5 = puVar6;
        } while ((uint *)((int)param_3 + (param_4 & 3)) != puVar6);
      }
    }
  }
  else {
    uVar1 = param_4 + 3 >> 2;
    if (uVar1 != 0) {
      iVar7 = 0;
      do {
        uVar4 = puVar3[8];
        iVar9 = iVar7;
        while (uVar4 = (uVar4 & 0x1fff) >> 8, uVar4 != 0) {
          if (uVar1 <= uVar4) {
            uVar4 = uVar1;
          }
          if (uVar4 != 0) {
            puVar6 = param_3 + uVar4;
            puVar5 = param_3;
            do {
              param_3 = puVar5 + 1;
              puVar3[0x42] = *puVar5;
              puVar5 = param_3;
            } while (param_3 != puVar6);
            uVar1 = uVar1 - uVar4;
          }
          if (uVar1 == 0) goto LAB_002c3b94;
          iVar9 = 0;
          uVar4 = puVar3[8];
        }
        usleep(1);
        iVar7 = iVar9 + 1;
        puVar3 = g_sfc_reg;
        if (10000 < iVar9) {
          uVar1 = 0xfffffffd;
          break;
        }
      } while (uVar1 != 0);
    }
  }
LAB_002c3b94:
  iVar7 = 0x186a2;
  do {
    if ((puVar3[9] & 1) == 0) goto LAB_002c3bc8;
    usleep(1);
    iVar7 = iVar7 + -1;
    puVar3 = g_sfc_reg;
  } while (iVar7 != 0);
  uVar1 = 0xfffffffd;
LAB_002c3bc8:
  usleep(1);
  return uVar1;
}
