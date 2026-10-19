/* ============================================================
 * strupr   @ 0x00016ebc   size=76B   callers=7
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_byte * strupr(gh_byte *param_1)

{
  gh_byte bVar1;
  gh_uint uVar2;
  int iVar3;
  __int32_t **pp_Var4;
  gh_byte *pbVar5;
  
  bVar1 = *param_1;
  pbVar5 = param_1;
  while (uVar2 = (gh_uint)bVar1, uVar2 != 0) {
    /* ★★ 2026-10-19（R211 回退）：**必须**写成被括号包住的 `(islower)(...)`。
     * glibc <ctype.h> 把 `islower` 定义成宏：
     *     #define islower(c) __isctype((c), _ISlower)
     *     #define __isctype(c, type) ((*__ctype_b_loc ())[(int)(c)] & (ushort)type)
     * 直接写 `islower(uVar2)` ⇒ 宏展开 ⇒ 我们侧变成调 `__ctype_b_loc`；
     * 而工厂二进制调的是 **libc 的 islower 函数本身**（CI 实测
     * `strupr [core] calls_ext F=['islower','islower','islower'] O=['__ctype_b_loc']`）
     * ⇒ 整组假发散。**括号包住函数名会抑制宏展开**，才能产出与工厂同形的调用。
     * （R209 曾把它"改顺手"成 `islower(uVar2)` —— 那是真实回退，棘轮当场抓到。） */
    iVar3 = (islower)(uVar2);
    if (iVar3 != 0) {
      pp_Var4 = (int **)__ctype_toupper_loc();
      *pbVar5 = (gh_byte)(*pp_Var4)[uVar2];
    }
    pbVar5 = pbVar5 + 1;
    bVar1 = *pbVar5;
  }
  return param_1;
}
