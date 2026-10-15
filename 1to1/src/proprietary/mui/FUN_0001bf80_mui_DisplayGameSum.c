/* ============================================================
 * mui_DisplayGameSum   @ 0x0001bf80   size=232B   callers=5
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DisplayGameSum(void)

{
  gh_u4 uVar1;
  int iVar2;
  int iVar3;
  /* 根修（UB）：`sprintf((char*)&uStack_98, "%3d/%3d", ...)` 最多写 7 字节 + NUL，
     而 Ghidra 只声明 4 字节 gh_u4 ⇒ 越界 = UB。恢复成 16 字节缓冲（保对齐）。 */
  gh_u1 uStack_98[16];   /* 原 puStack_94(gh_undef*，-0x94) 与 uStack_98[4..7] 重叠，已合并进 uStack_98 */
  
  iVar3 = DAT_003af318;
  iVar2 = DAT_003af314;
  OutRect._16_4_ = DAT_003af31c;
  OutRect._8_4_ = DAT_003af314;
  OutRect._12_4_ = DAT_003af318;
  OutRect._20_4_ = DAT_003af320;
  mui_Undisplay(DAT_003af314,DAT_003af318,DAT_003af31c,DAT_003af320);
  uVar1 = DAT_003af394;
  if (DAT_003af288 == 0) {
    /* R179 根修（伪符号，非 UB）：工厂反汇编 = `ldr r3,[pc,#0x2c0e5c]; ldm r3,{r0,r1}; stm r8,{r0,r1}`
     *   r3 = pc(0x1bfe8)+0x2c0e5c = 0x2dce44，该处字节 = "  -/-  "（20 20 2d 2f 2d 20 20 00）= 8 字节块拷。
     *   Ghidra 把后 4 字节 "-  \0"(小端 0x0020202d) 误读成指针符号 DAT_0020202d（实际 0x20202d 处是别处数据
     *   0e d1 0d 20..），造成「第一字=0x2f2d2020 常量 + 第二字=死指针」的假拆分 ⇒ 死指针从未读 ⇒ -Os 消除引用。
     *   语义真相 = 向 uStack_98 拷入字符串 "  -/-  "（空列表占位符），被 mui_outputxy_t 消费。 */
    memcpy(uStack_98, "  -/-  ", 8);
  }
  else {
    iVar2 = __aeabi_idiv(DAT_003af288,DAT_003af394);
    iVar3 = __aeabi_idiv(DAT_003af278 + DAT_003af27c,uVar1);
    sprintf((char *)uStack_98,"%3d/%3d",iVar3 + 1,iVar2 + 1);
    iVar2 = OutRect._8_4_;
    iVar3 = OutRect._12_4_;
  }
  mui_outputxy_t(DAT_003af29c,iVar2 + 8,iVar3 + 6,(gh_u1)DAT_003af324,DAT_003af328,(gh_byte *)uStack_98);
  return;
}
