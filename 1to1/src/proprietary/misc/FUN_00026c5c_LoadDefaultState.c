/* ============================================================
 * LoadDefaultState   @ 0x00026c5c   size=112B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"
#ifdef CGM_ENABLE_SRAM
#include "cgm_upgrade.h"
#endif

void LoadDefaultState(void)

{
  gh_u4 uVar1;
  gh_u4 uVar2;
  int iVar3;
  char acStack_1010 [4100];
  
  uVar1 = (gh_u4)GetWorkPath();
  uVar2 = gameType();
  sprintf(acStack_1010,"%ssaves/%03d/%s.sav",uVar1,uVar2,RomName);
  iVar3 = access(acStack_1010,0);
  if (iVar3 == 0) {
    retro_load_state(acStack_1010);
  }
#ifdef CGM_ENABLE_SRAM
  /* ★ 目的 2：把 .srm/.rtc 读回 core 的 SRAM 视图。
   *   ★ 注意：md/SFC 的 SRAM 是**延迟建立**的，首帧此处 size 可能仍=0，
   *     load 会记 pending，由 Load_Proc2 主循环每帧 cgm_sram_poll_base() 在 size>0 后补读。 */
  {
    char cgmBase [4100];
    int cgmN;
    sprintf(cgmBase,"%ssaves/%03d/%s",uVar1,uVar2,RomName);
    cgm_sram_set_base(cgmBase);
    (void)cgm_sram_bind(handle_emurun);
    cgmN = cgm_sram_load_base();
    RARCH_LOG("SRAM load hook(channels=%d,size0=%u,size1=%u):%s\n",
              cgmN, (unsigned)cgm_sram_size(0), (unsigned)cgm_sram_size(1), cgmBase);
  }
#endif
  return;
}
