/* ============================================================
 * DrawFrame   @ 0x002b53a8   size=520B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DrawFrame(gh_u2 *param_1,int param_2,int param_3,int param_4)

{
  /* ★★ 2026-10-19（R211）：**删掉** Ghidra 渲染出来的顶部 `puVar1 = rotation_buff;`，
   *   改为在真正用到它的三个分支里直接取（下面 `puVar2 = rotation_buff;`）。
   *   为什么（CI 实测证据，不是风格偏好）：
   *     diff_exec 报 `DrawFrame [strs/core/misc] data-reads 仅F=[] 仅O=['0x003cfa94:4:R ×1']`
   *     —— `0x003cfa94` = `rotation_buff`（ledger/factory_globals.tsv:830）。
   *     沙箱跑的是 `soft_rotation == 0` 这条快速路径（.bss 全零 ⇒ 直接 goto LAB_002b5440），
   *     这条路上 `puVar1` 是**死值** ⇒ 工厂 GCC 不产生这次载入，而我们 clang 产生了
   *     ⇒ 我们比工厂**多一次 4B 读**。
   *   ⇒ 把死载入从"函数顶部"挪到"真正使用的分支里"，语义逐位不变（工厂就是这样）。
   *   ★ 推断尚未实测：本次改动的收敛结果以 CI 报告为准（见 PROGRESS R211 待办 2）。 */
  gh_u2 *puVar2;
  gh_u2 *puVar3;
  gh_u2 *puVar4;
  int iVar5;
  int iVar6;
  gh_u2 *puVar7;
  int iVar8;
  gh_u2 *puVar9;
  
  if (param_1 == (gh_u2 *)0x0) {
    return;
  }
  if (FrameSkip != 0) {
    return;
  }
  DispFrameCount = DispFrameCount + 1;
  iVar5 = param_3;
  iVar6 = param_2;
  puVar2 = param_1;
  this_frame._0_4_ = (gh_u4)param_1;
  this_frame._4_4_ = param_2;
  this_frame._8_4_ = param_3;
  this_frame._12_4_ = param_4;
  if (soft_rotation == 0) goto LAB_002b5440;
  iVar6 = param_3;
  if (rotation == 1) {
    if (param_2 != 0) {
      param_4 = param_3 * 2;
      puVar7 = param_1 + param_2 + -1;
      puVar4 = rotation_buff;
      do {
        if (param_3 != 0) {
          puVar9 = puVar4 + param_3;
          puVar2 = puVar7;
          puVar3 = puVar4;
          do {
            puVar4 = puVar3 + 1;
            *puVar3 = *puVar2;
            puVar2 = puVar2 + param_2;
            puVar3 = puVar4;
          } while (puVar4 != puVar9);
        }
        puVar7 = puVar7 + -1;
        iVar5 = param_2;
        puVar2 = rotation_buff;      /* ★ R211：原 `puVar1`（= rotation_buff）见顶部注释 */
      } while (puVar7 != param_1 + -1);
      goto LAB_002b5440;
    }
  }
  else {
    if (rotation != 3) {
      iVar6 = param_2;
      if (rotation == 2) {
        param_3 = param_3 * param_2;
        if (param_3 != 0) {
          param_1 = param_1 + param_3 + -0x80000000;
          puVar4 = rotation_buff + param_3 + -0x80000000;
          puVar2 = rotation_buff;
          do {
            param_1 = param_1 + -1;
            puVar7 = puVar2 + 1;
            *puVar2 = *param_1;
            puVar2 = puVar7;
          } while (puVar7 != puVar4);
        }
        param_4 = param_2 << 1;
        puVar2 = rotation_buff;      /* ★ R211：原 `puVar1`（= rotation_buff）见顶部注释 */
      }
      goto LAB_002b5440;
    }
    if (param_2 != 0) {
      param_4 = param_3 * 2;
      iVar8 = param_2 * (param_3 + 0x7fffffff);
      puVar7 = param_1 + iVar8;
      puVar4 = rotation_buff;
      do {
        if (param_3 != 0) {
          puVar9 = puVar4 + param_3;
          puVar2 = puVar7;
          puVar3 = puVar4;
          do {
            puVar4 = puVar3 + 1;
            *puVar3 = *puVar2;
            puVar2 = puVar2 + -param_2;
            puVar3 = puVar4;
          } while (puVar4 != puVar9);
        }
        puVar7 = puVar7 + 1;
        iVar5 = param_2;
        puVar2 = rotation_buff;      /* ★ R211：原 `puVar1`（= rotation_buff）见顶部注释 */
      } while (param_1 + param_2 + iVar8 != puVar7);
      goto LAB_002b5440;
    }
  }
  param_4 = param_3 << 1;
  iVar5 = param_2;
  puVar2 = rotation_buff;      /* ★ R211：原 `puVar1`（= rotation_buff）见顶部注释 */
LAB_002b5440:
  if (displayfps != 0) {
    UIDebug((void *)puVar2,iVar6,iVar5,param_4);
  }
  dispFlip(puVar2,iVar6,iVar5,param_4);
  return;
}
