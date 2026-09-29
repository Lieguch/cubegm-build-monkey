/* ============================================================
 * popwindows   @ 0x00027398   size=536B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ============================================================================
 * ★★★ 2026-09-29（§0.32）：**结构性修复 —— 把 Ghidra 拆散的"结构体"还原成数组**
 *
 * 病灶（实测，不是推测）：工厂的 `blockadaptive` 用 `&local_58` / `&local_40` 两个指针
 * 访问**各 6 个连续 int**：
 *     工厂 blockadaptive: `ldr _, [r0,#0] [#4] [#8] [#0xc] [#0x10]`（我方还含 `#0x14`）
 *     工厂 popwindows:    `&local_40 = sp+0x28`，`&local_58 = sp+0x40`（各跨 6 个 int）
 * 而 Ghidra 把这两个"结构体"拆成了 12 个独立局部变量。其中
 * `local_3c / local_38 / local_34 / local_30 / local_2c` 在 C 语言层面**只写不读**
 * （真实读取发生在 `blockadaptive` 里，但 C 的对象边界规则让编译器**无权**这么假定）
 * ⇒ `-Os` 判定为死存储并**整段删除** ⇒
 *     · 我方 popwindows 只有 **296 B**，工厂 **556 B**（比值 0.532）
 *     · 5 步插值的 `(iVar3*iVar6)/10`、`(iVar3*iVar7)/10` 计算**全部消失** ⇒ 行为不一致
 *
 * 为什么**不**用 `volatile` 打补丁：`volatile` 会把整块的访存顺序/次数都改掉，
 * 是"用另一个偏差盖住原偏差"。正确做法是**让源码如实表达语义** —— 它们本就是
 * 一个连续对象、会被被调函数按指针索引 ⇒ 声明成数组即可，对任何编译器都成立。
 *
 * 回退：`git checkout -- src/proprietary/mui/FUN_00027398_popwindows.c`
 *       （或 `build/_exp/popwindows.c.bak_preblk`）
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

void popwindows(gh_u4 *param_1)

{
  void *__dest;
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  void *__src;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  /* ★ 两块连续对象（各 6 个 int）；见文件头 §0.32 说明。
     `&local_58` = &blkB[0]、`&local_40` = &blkA[0] 是被调函数实际索引的基址。 */
  int blkB[6];
  int blkA[6];
  
  iVar4 = param_1[2];
  iVar2 = param_1[1];
  iVar7 = param_1[4] - iVar4;
  iVar6 = param_1[3] - iVar2;
  __dest = malloc(iVar6 * iVar7 * 2);
  local_40 = (int)DAT_003af29c;
  scrbuf = __dest;
  if (iVar7 < 1) {
    iVar9 = DAT_003af2a0 << 1;
  }
  else {
    iVar5 = 0;
    iVar9 = DAT_003af2a0 * 2;
    __src = (void *)(DAT_003af29c + (DAT_003af2a0 * iVar4 + iVar2) * 2);
    do {
      iVar5 = iVar5 + 1;
      memcpy(__dest,__src,iVar6 * 2);
      __src = (void *)((int)__src + iVar9);
      __dest = (void *)((int)__dest + iVar6 * 2);
    } while (iVar7 != iVar5);
  }
  local_44 = iVar6 * 2;
  local_58 = *param_1;
  iVar5 = 1;
  local_54 = 0;
  local_50 = 0;
  local_4c = iVar6;
  local_48 = iVar7;
  while( true ) {
    iVar3 = 5 - iVar5;
    iVar1 = iVar6 * iVar5;
    iVar8 = iVar7 * iVar5;
    iVar5 = iVar5 + 1;
    local_3c = (iVar3 * iVar6) / 10 + iVar2;
    local_38 = (iVar3 * iVar7) / 10 + iVar4;
    local_34 = iVar1 / 5 + local_3c;
    local_30 = iVar8 / 5 + local_38;
    local_2c = iVar9;
    blockadaptive((int *)&local_40,(int *)&local_58);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    usleep(18000);
    if (iVar5 == 6) break;
    iVar2 = param_1[1];
    iVar4 = param_1[2];
    iVar9 = DAT_003af2a0 << 1;
    iVar6 = param_1[3] - iVar2;
    iVar7 = param_1[4] - iVar4;
    local_40 = (int)DAT_003af29c;
  }
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
