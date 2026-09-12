/* ============================================================
 * mui_DisplayInputBuffer   @ 0x0001c330   size=220B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DisplayInputBuffer(void)

{
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  gh_u4 *puVar6;
  gh_u4 uVar7;
  int iVar8;
  int iVar9;
  int iVar10;
  
  iVar5 = DAT_003af6cc;
  iVar4 = DAT_003af6c8;
  OutRect._20_4_ = DAT_003af6d4;
  OutRect._12_4_ = DAT_003af6cc;
  OutRect._8_4_ = DAT_003af6c8;
  OutRect._16_4_ = DAT_003af6d0;
  if (0 < DAT_003af6d4 - DAT_003af6cc) {
    iVar9 = DAT_003af6d0 - DAT_003af6c8;
    iVar10 = (DAT_003af6d4 - DAT_003af6cc) + DAT_003af6cc;
    iVar1 = DAT_003af6c8 * 2;
    iVar8 = DAT_003af6cc;
    do {
      iVar2 = iVar8 * DAT_003af2a0 * 2;
      iVar3 = iVar8 * (gh_uint)*(gh_ushort *)(DAT_003af290 + 1) * 2;
      iVar8 = iVar8 + 1;
      memcpy((void *)(DAT_003af29c + iVar2 + iVar1),
             (void *)((int)DAT_003af290 + iVar3 + iVar1 + *DAT_003af290),iVar9 * 2);
    } while (iVar10 != iVar8);
  }
  puVar6 = m_search;
  uVar7 = mui_outputxy_t(DAT_003af29c,iVar4 + 2,iVar5,(gh_u1)DAT_003af6d8,DAT_003af6dc,
                         (gh_byte *)*m_search);
  puVar6[3] = uVar7;
  return;
}
