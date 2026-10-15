/* ============================================================
 * DisplayPage_list   @ 0x0002187c   size=248B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DisplayPage_list(int param_1,gh_u4 param_2,int param_3)

{
  int iVar1;
  int iVar2;
  /* R179 根修：-0x48..-0x1c 是 mui_blockcopy(param_1=&local_30,param_2=&local_48) 的连续 12 个 int 参数槽。
   * Ghidra 拆成 12 独立标量 ⇒ &local_30/&local_48 跨对象块读 = UB ⇒ -Os 消除 af2a0 写入
   * （af2a0<<1 落在 param_2[5]=local_34 与 param_1[5]=local_1c，均被 mui_blockcopy 的 stride 读走）。
   * 数组化：blk[0..5]=param_2(local_48..34)、blk[6..11]=param_1(local_30..1c)，地址逃逸覆盖整段。 */
  int blk[12];
  
  blk[2] = DAT_003af724;                      /* local_40 */
  OutRect._16_4_ = DAT_003af720 + DAT_003af728;
  blk[3] = OutRect._16_4_ + 8;                /* local_3c */
  blk[0] = (int)DAT_003af294 + *DAT_003af294; /* local_48 */
  OutRect._8_4_ = DAT_003af720;
  blk[4] = DAT_003af724 + DAT_003af72c;       /* local_38 */
  OutRect._12_4_ = DAT_003af724;
  blk[6] = (int)DAT_003af29c;                 /* local_30 = param_1[0]（目标基址）*/
  blk[5] = DAT_003af2a0 << 1;                 /* local_34 = param_2[5]（源 stride）*/
  blk[1] = DAT_003af720 + -8;                 /* local_44 */
  blk[7] = blk[1];                            /* local_2c = param_1[1] */
  blk[8] = blk[2];                            /* local_28 = param_1[2] */
  blk[9] = blk[3];                            /* local_24 = param_1[3] */
  blk[10] = blk[4];                           /* local_20 = param_1[4] */
  blk[11] = blk[5];                           /* local_1c = param_1[5]（目标 stride）*/
  OutRect._20_4_ = blk[4];                    /* local_38 */
  mui_blockcopy(&blk[6],&blk[0]);
  if ((0 < DAT_003af394) && (param_1 != param_3)) {
    iVar1 = 0;
    do {
      iVar2 = iVar1 + 1;
      DisplayLine_list(param_1,iVar1,param_2);
      if (DAT_003af394 <= iVar2) {
        return;
      }
      iVar1 = iVar2;
    } while (param_3 != iVar2 + param_1);
  }
  return;
}
