/* ============================================================
 * SaveDefaultState   @ 0x00026cd8   size=108B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"
#ifdef CGM_ENABLE_SRAM
#include "cgm_upgrade.h"   /* 目的 2 升级：SRAM/记忆卡电池存档 */
#endif

void SaveDefaultState(void)

{
  gh_u4 uVar1;
  gh_u4 uVar2;
  char acStack_1008 [4096];
  
  uVar1 = (gh_u4)GetWorkPath();
  uVar2 = gameType();
  sprintf(acStack_1008,"%ssaves/%03d/%s.sav",uVar1,uVar2,RomName);
  RARCH_LOG("SaveDefaultState:%s\n",acStack_1008);
  retro_save_state(acStack_1008);
#ifdef CGM_ENABLE_SRAM
  /* ★ 目的 2：即时 state(.sav) 之外，把 core 的 SRAM/记忆卡也落到 .srm/.rtc。
   *   判据是 core 自报 size>0（无游戏白名单）；size==0 静默跳过。 */
  {
    char cgmBase [4100];
    int cgmB, cgmW;
    sprintf(cgmBase,"%ssaves/%03d/%s",uVar1,uVar2,RomName);
    cgm_sram_set_base(cgmBase);
    cgmB = cgm_sram_bind(handle_emurun);
    cgmW = cgm_sram_flush_base();
    RARCH_LOG("SRAM hook(bind=%d,written=%d,size0=%u,size1=%u):%s\n",
              cgmB, cgmW,
              (unsigned)cgm_sram_size(0), (unsigned)cgm_sram_size(1), cgmBase);
  }
#endif
  return;
}
