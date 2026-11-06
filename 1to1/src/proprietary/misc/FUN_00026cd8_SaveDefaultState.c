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
   *   判据是 core 自报 size>0（无游戏白名单）；size==0 静默跳过。
   *   ★ R325（用户要求 2026-11-06）：SRAM 目录 = ROM 所在目录（不再 saves/%03d/）。
   *     fileName = core 加载时 strcpy 的 ROM **全路径**（如 /mnt/sdcard/roms/xxx.bin）；
   *     取其中目录段（最后一个 '/' 之前）+ RomName（basename、已去扩展名）拼 base。 */
  {
    char cgmBase [4100];
    int cgmB, cgmW;
    const char *slash = strrchr((const char *)fileName, '/');
    size_t dirlen = (slash != NULL) ? (size_t)(slash - (const char *)fileName) + 1u : 0u;
    memcpy(cgmBase, fileName, dirlen);
    strcpy(cgmBase + dirlen, RomName);
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
