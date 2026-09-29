/* ============================================================
 * popoffwindows   @ 0x000275c4   size=484B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ============================================================================
 * ★★★ 2026-09-29（§0.32）：与 `popwindows` **同一根因**的结构性修复。
 * 工厂 `blockadaptive` 用 `&local_40` / `&local_58` 按指针索引**各 6 个连续 int**；
 * Ghidra 把它们拆成 12 个独立局部变量，其中 `local_38/3c/30/34` 只写不读
 * ⇒ `-Os` 删掉死存储 ⇒ 我方 300 B vs 工厂 504 B（0.595）、5 步插值计算整体消失。
 * 修法 = 还原成数组（让"取首地址传外部函数"在编译器眼里可触及全部元素）。
 * 回退：`git checkout -- src/proprietary/mui/FUN_000275c4_popoffwindows.c`
 * ========================================================================== */
#define local_58 blkB[0]
#define local_54 blkB[1]
#define local_50 blkB[2]
#define local_4c blkB[3]
#define local_48 blkB[4]
#define local_44 blkB[5]
#define local_40 blkA[0]
#define local_3c blkA[1]
#define local_38 blkA[2]
#define local_34 blkA[3]
#define local_30 blkA[4]
#define local_2c blkA[5]

void popoffwindows(gh_u4 *param_1)

{
  void *pvVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  /* ★ 两块连续对象（各 6 个 int）；见文件头 §0.32 说明。 */
  int blkB[6];
  int blkA[6];
  
  iVar5 = param_1[2];
  iVar2 = param_1[1];
  local_58 = *param_1;
  iVar4 = param_1[3] - iVar2;
  local_54 = 0;
  local_50 = 0;
  iVar7 = 5;
  iVar3 = param_1[4] - iVar5;
  local_44 = iVar4 * 2;
  local_4c = iVar4;
  local_48 = iVar3;
  while( true ) {
    pvVar1 = scrbuf;
    if (0 < iVar3) {
      iVar6 = 0;
      do {
        iVar5 = iVar6 + iVar5;
        iVar3 = iVar4 * iVar6;
        iVar6 = iVar6 + 1;
        memcpy((void *)(DAT_003af29c + (DAT_003af2a0 * iVar5 + iVar2) * 2),
               (void *)((int)pvVar1 + iVar3 * 2),iVar4 << 1);
        iVar5 = param_1[2];
        iVar2 = param_1[1];
        iVar3 = param_1[4] - iVar5;
        iVar4 = param_1[3] - iVar2;
      } while (iVar6 < iVar3);
    }
    iVar9 = 5 - iVar7;
    iVar8 = iVar7 * iVar4;
    iVar6 = iVar7 * iVar3;
    iVar7 = iVar7 + -1;
    local_2c = DAT_003af2a0 << 1;
    local_38 = (iVar9 * iVar3) / 10 + iVar5;
    local_40 = (int)DAT_003af29c;
    local_3c = (iVar9 * iVar4) / 10 + iVar2;
    local_30 = iVar6 / 5 + local_38;
    local_34 = iVar8 / 5 + local_3c;
    blockadaptive((int *)&local_40,(int *)&local_58);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    usleep(18000);
    if (iVar7 == -1) break;
    iVar2 = param_1[1];
    iVar5 = param_1[2];
    iVar3 = param_1[4] - iVar5;
    iVar4 = param_1[3] - iVar2;
  }
  free(scrbuf);
  return;
}

#undef local_58
#undef local_54
#undef local_50
#undef local_4c
#undef local_48
#undef local_44
#undef local_40
#undef local_3c
#undef local_38
#undef local_34
#undef local_30
#undef local_2c
