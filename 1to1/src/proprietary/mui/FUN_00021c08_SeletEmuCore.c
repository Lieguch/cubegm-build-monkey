/* ============================================================
 * SeletEmuCore   @ 0x00021c08   size=1712B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int SeletEmuCore(gh_byte *param_1)

{
  int iVar1;
  void *__ptr;
  void *__ptr_00;
  char *pcVar2;
  FILE *__stream;
  int iVar3;
  int iVar4;
  gh_uint uVar5;
  gh_ushort uVar6;
  int iVar7;
  int iVar8;
  gh_ushort *puVar9;
  gh_ushort *puVar10;
  gh_bool bVar11;
  /* ★ R180 根修（GAP 18.03，与 R173 FBA_Load / R179 八条 / R180 DisplayThumbnail 同构）：
   * -0x158..-0x12c 是 mui_blockcopy 的**连续 12 个 int 参数槽**：
   *   · -0x158..-0x140 = local_158[6]     （param_2 组，Ghidra 已正确识别为数组）
   *   · -0x140..-0x12c = local_140/local_13c/local_138/local_134/local_130/local_12c
   *                                                （param_1 组，被 Ghidra 拆成 6 个标量）
   * 即 param_1 = param_2 + 6 个 int。C 层 `&local_140` 只让**首元素**地址逃逸，
   * 而 mui_blockcopy 按 `int*` 读 param_1[1..5]（= local_13c..12c）或
   * param_2[1..5]（后 3 个调用点参数交换时）⇒ 跨对象访问（UB）⇒
   * `-Os` 把 local_13c/138/134/130/12c 五个槽判定为死存储并**整段删除**。
   * 实测铁证（云机 arm-linux-gnueabihf-gcc 14.2，tools/verify_blk12.py）：
   *   -O0：调用#1 前写 17 个槽（含 540/420/1080 三个常量）
   *   -Os：调用#1 前只写  9 个槽；#3/#4/#5 各只写 2 个槽
   *        ⇒ 0x21c/0x1a4/0x438 在 -Os 里**完全消失**（只余循环边界 cmp）
   *        ⇒ mui_blockcopy 的 dst/src stride 与偏移读到栈垃圾 ⇒ 选核界面 blit 错位。
   * 集合级 Δ 门禁同样放行本条：这些槽写的是**常量**（0/0x21c/0x1a4/0x438），
   * 不引用任何 DAT_* 符号 ⇒ 永远不进 Δ（GAP 18.01 的又一变体）。
   * 数组化后地址逃逸覆盖整段，-Os 不再消除任何一个槽。
   * 回退：还原为上面 7 行声明 + 原调用形式即可。 */
  int blk[12];
  char acStack_128 [260];
  
  iVar1 = FilePreEmu(param_1);
  iVar3 = DAT_003af2a0;
  iVar8 = (int)DAT_003af29c;
  __ptr = malloc(0x6ebe0);
  blk[5] = iVar3 << 1;                /* local_158[5] = param_2[5] 源 stride */
  iVar7 = 0;
  blk[2] = 0x96;                      /* local_158[2] = param_2[2] 源上 */
  blk[7] = 0;                         /* local_13c    = param_1[1] 目标左 */
  blk[9] = 0x21c;                     /* local_134    = param_1[3] */
  blk[8] = 0;                         /* local_138    = param_1[2] 目标上 */
  blk[11] = 0x438;                    /* local_12c    = param_1[5] 目标 stride */
  blk[4] = 0x23a;                     /* local_158[4] = param_2[4] 源行数 */
  blk[1] = 0x172;                     /* local_158[1] = param_2[1] 源左 */
  blk[10] = 0x1a4;                    /* local_130    = param_1[4] */
  blk[3] = 0x38e;                     /* local_158[3] = param_2[3] 源高 */
  blk[0] = iVar8;                     /* local_158[0] = param_2[0] 源基址 */
  blk[6] = (int)__ptr;                /* local_140    = param_1[0] 目标基址 */
  mui_blockcopy(&blk[6],&blk[0]);
  iVar4 = DAT_003af2a0;
  puVar9 = (gh_ushort *)(iVar8 + (iVar3 * 0x96 + 0x172) * 2 + -2);
  do {
    iVar8 = 0;
    puVar10 = puVar9;
    do {
      while( true ) {
        uVar6 = puVar10[1];
        uVar5 = uVar6 & 0x1f;
        if ((3 < iVar7) && (2 < iVar7 - 0x19cU)) break;
        if (0x216 < iVar8) goto LAB_00021d44;
LAB_00021e84:
        uVar6 = 0x630c;
LAB_00021d10:
        iVar8 = iVar8 + 1;
        puVar10 = puVar10 + 1;
        *puVar10 = uVar6;
        if (iVar8 == 0x21c) goto LAB_00021d94;
      }
      if (iVar8 < 4) {
        if (iVar7 < 0x19f) goto LAB_00021e84;
LAB_00021d08:
        uVar6 = (gh_ushort)uVar5 | uVar6 & 0xf800 | uVar6 & 0x7e0;
        goto LAB_00021d10;
      }
LAB_00021d44:
      if (iVar7 < 0x19f && iVar8 - 0x214U < 3) goto LAB_00021e84;
      iVar3 = iVar7;
      if (3 < iVar7) {
        iVar3 = iVar8;
      }
      if (iVar3 < 4) goto LAB_00021d08;
      iVar8 = iVar8 + 1;
      puVar10 = puVar10 + 1;
      *puVar10 = (gh_ushort)(uVar5 >> 3) | (uVar6 >> 0xe) << 0xb |
                 (gh_ushort)(((uVar6 & 0x7ff) >> 8) << 5);
    } while (iVar8 != 0x21c);
LAB_00021d94:
    iVar7 = iVar7 + 1;
    puVar9 = puVar9 + iVar4;
  } while (iVar7 != 0x1a4);
  OutRect._8_4_ = 0x172;
  OutRect._12_4_ = 0x96;
  OutRect._16_4_ = 0x38e;
  OutRect._20_4_ = 0x23a;
  if (iVar1 == 0) {
    mui_outputxy_t(DAT_003af29c,0x1b2,0xa2,0x22,0xfc1f,"The specified file is missing");
    mui_outputxy_t(DAT_003af29c,OutRect._8_4_ + 0x20,OutRect._12_4_ + 0xa8,0x18,0xffff,param_1);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    while (((iVar8 = mui_ReadJoystick(), iVar8 != 0x2000 && (iVar8 != 0x4000)) && (iVar8 != 8))) {
      mui_WaitNMI();
    }
    return 0;
  }
  mui_outputxy_t(DAT_003af29c,0x1b2,0xa2,0x22,0xfc1f,"Select a emulator core library");
  __ptr_00 = malloc(0x6ebe0);
  blk[6] = (int)__ptr_00;
  mui_blockcopy(&blk[6],&blk[0]);
  pcVar2 = stpcpy(acStack_128,work_path);
  builtin_strncpy(pcVar2,"cores/config.xml",0x11);
  __stream = fopen(acStack_128,"r");
  if (__stream == (FILE *)0x0) {
    RARCH_LOG("open config.xml fail!\n");
    tree = 0;
    iVar8 = 0;
  }
  else {
    tree = mxmlLoadFile(0,__stream,0);
    fclose(__stream);
    if (tree == 0) {
      iVar8 = 0;
    }
    else {
      iVar8 = 0;
      iVar3 = tree;
LAB_00021f90:
      iVar3 = mxmlFindElement(iVar3,tree,DAT_002dd508,0,0,1);
      if (iVar3 != 0) {
        iVar4 = mxmlFindElement(iVar3,tree,"supported_extensions",0,0,1);
        do {
          iVar1 = strcmp(*(char **)(*(int *)(iVar4 + 0x10) + 0x1c),(char *)&FilenameExt);
          if (iVar1 == 0) {
            iVar4 = mxmlFindElement(iVar3,tree,"emucore",0,0,1);
            if (iVar4 != 0) {
              iVar1 = iVar8 * 0x200;
              iVar8 = iVar8 + 1;
              pcVar2 = (char *)mxmlElementGetAttr(iVar4,DAT_002dcd70);
              strcpy(core_info_list + iVar1,pcVar2);
              pcVar2 = (char *)mxmlElementGetAttr(iVar4,DAT_002dbd74);
              strcpy(core_info_list + iVar1 + 0x100,pcVar2);
            }
            break;
          }
          iVar4 = mxmlFindElement(iVar4,tree,"supported_extensions",0,0,0);
        } while (iVar4 != 0);
        goto LAB_00021f90;
      }
      if (tree != 0) {
        mxmlDelete(tree);
        tree = 0;
      }
    }
  }
  EmuCore_list(0,0,iVar8);
  iVar3 = 0;
  ForceFlashCount = 0;
  iVar4 = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  uVar5 = mui_ReadJoystick();
  bVar11 = false;
  if (uVar5 == 0x40) goto LAB_00022190;
LAB_00022128:
  if (uVar5 < 0x40 || bVar11) {
    if (uVar5 == 8) {
LAB_00022214:
      blk[6] = (int)__ptr;
      mui_blockcopy(&blk[0],&blk[6]);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      free(__ptr);
      free(__ptr_00);
      return (iVar4 + iVar3) * 0x200 + 0x3c9bec;
    }
    if (uVar5 == 0x10) {
      if (iVar3 != 0) {
        iVar3 = iVar3 + -1;
        goto LAB_00022148;
      }
      if (iVar4 != 0) {
        iVar4 = iVar4 + -1;
        goto LAB_00022148;
      }
      iVar3 = 0;
    }
  }
  else {
    if (uVar5 == 0x2000) goto LAB_00022214;
    if (uVar5 == 0x4000) {
      blk[6] = (int)__ptr;
      mui_blockcopy(&blk[0],&blk[6]);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      free(__ptr);
      free(__ptr_00);
      return 0;
    }
  }
LAB_00022180:
  while( true ) {
    mui_WaitNMI();
    uVar5 = mui_ReadJoystick();
    bVar11 = uVar5 == 0x40;
    if (!bVar11) break;
LAB_00022190:
    if (iVar3 < 6) goto code_r0x000221a0;
    if (iVar4 + iVar3 < iVar8 + -1) {
      iVar4 = iVar4 + 1;
      goto LAB_00022148;
    }
  }
  goto LAB_00022128;
code_r0x000221a0:
  if (iVar4 + iVar3 < iVar8 + -1) {
    iVar3 = iVar3 + 1;
LAB_00022148:
    blk[6] = (int)__ptr_00;
    mui_blockcopy(&blk[0],&blk[6]);
    EmuCore_list(iVar4,iVar3,iVar8);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  }
  goto LAB_00022180;
}
