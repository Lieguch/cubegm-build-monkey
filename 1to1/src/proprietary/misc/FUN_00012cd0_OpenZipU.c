/* ============================================================
 * OpenZipU   @ 0x00012cd0   size=128B   callers=13
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 * OpenZipU(void *param_1,gh_uint param_2,gh_uint param_3)

{
  TUnzip *this;
  gh_u4 *puVar1;
  
  this = _Znwj(0x240);
  /* ★★ 必须用**字节**偏移，不能写 `this + 0x138` —— `this` 是 `TUnzip *`，
   *   而 `TUnzip` 是**576 字节**的类（= 上面 `_Znwj(0x240)` 申请的尺寸），
   *   于是 `this + 0x138` 会被按元素大小缩放成 `0x138 × 576 = 0x2BE00`（180 KB），
   *   `this + 4` 变成 `4 × 576 = 0x900`。
   *
   *   工厂机器码是**字节偏移**（0x12cfc / 0x12d04）：
   *      12cfc: str ip, [r0, #312]      ; = *(u32 *)((char*)this + 0x138) = -1
   *      12d04: stm r0, {r5, ip}        ; = *(u32 *)this = 0 ; *(u32 *)((char*)this + 4) = -1
   *   实测代价（P5 第六个真实分歧）：越界写 `[obj+0x2BE00]` 直接 SIGSEGV
   *      （shim 现场 pc = `OpenZipU+0x2c`、`故障指令 0xE7891000 = ldr/str [r9, r0]`、
   *        `r0 = 0x2be00`；调用者 `get_items_from_zipfile+0x28`）⇒ 卡在 `ui_cn.zip` 读取处，
   *      而工厂在同一位置是**优雅失败**（`OpenZipU` 返回 0 → 打印 `open ... fail!` 并继续）。 */
  *(gh_u4 *)((char *)this + 0x138) = 0xffffffff;
  *(gh_u4 *)this = 0;
  *(gh_u4 *)((char *)this + 4) = 0xffffffff;
  lasterrorU = _ZN6TUnzip4OpenEPvjj(this,param_1,param_2,param_3);
  if (lasterrorU == 0) {
    puVar1 = _Znwj(8);
    puVar1[1] = (gh_u4)this;
    *puVar1 = 1;
    return puVar1;
  }
  _ZdlPv(this);
  return (gh_u4 *)0x0;
}
