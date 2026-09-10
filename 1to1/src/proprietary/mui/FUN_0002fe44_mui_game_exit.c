/* ============================================================
 * mui_game_exit   @ 0x0002fe44   size=300B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 mui_game_exit(void)

{
  int iVar1;
  
  do {
    if (DAT_003af2b8 == (int *)0x0) {
      mui_LoadUIResource(&DAT_003af2b8,"game.raw");
    }
    memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
           (uint)*(ushort *)((int)DAT_003af2b8 + 6) * (uint)*(ushort *)(DAT_003af2b8 + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,2);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    iVar1 = mui_ReadJoystick();
    while (iVar1 != 0x40) {
      if (iVar1 == 0x2000) {
        pause_ret = 1;
        return 0;
      }
      if (iVar1 == 0x10) {
        SoundPlay(1,mui_Effect0);
        return 1;
      }
      mui_WaitNMI();
      iVar1 = mui_ReadJoystick();
    }
    SoundPlay(1,mui_Effect0);
    iVar1 = mui_save_state();
    if (iVar1 == 0) {
      return 0;
    }
  } while( true );
}
