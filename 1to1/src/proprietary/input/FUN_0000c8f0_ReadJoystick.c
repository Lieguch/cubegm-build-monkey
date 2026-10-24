/* ============================================================
 * ReadJoystick   @ 0x0000c8f0   size=204B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

#ifdef CGM_DIAG_TRACE_INPUT
extern void cgm_probe_tick(void);
#endif

gh_u4 ReadJoystick(void)

{
#ifdef CGM_DIAG_TRACE_INPUT
  cgm_probe_tick();   /* ★ R266：UI 主循环心跳（卡死判定的唯一基准） */
#endif
  gh_u4 uVar1;
  
  /* ★ R256：SRAM 每帧 poll 已挪到 Load_Proc2 游戏主循环。原挂在此 ReadJoystick()，
   *   但游戏主循环走 ReadJoystickProc() 不经过本函数 ⇒ poll 是死代码、断电保护从未生效。 */
  ReadJoystickProc();
#ifdef CGM_DIAG_JOY
  /* 诊断（交付不含）：打印防抖状态机输入，判定"放行值为何恒 0" */
  if (joy_key_blob._0_4_ != 0 || Joy1_Press != 0) {
    fprintf(stderr, "[diagjoy2] blob=0x%08x press=0x%08x delay=%d\n",
            (unsigned)joy_key_blob._0_4_, (unsigned)Joy1_Press, (int)Joy1_Delay);
  }
#endif
  if ((joy_key_blob._0_4_ != joytemp0) || (joy_key_blob._4_4_ != joytemp1)) {
    joytemp0 = joy_key_blob._0_4_;
    joytemp1 = joy_key_blob._4_4_;
  }
  if (joy_key_blob._0_4_ != 0) {
    if (joy_key_blob._0_4_ != Joy1_Press) {
      Joy1_Press = joy_key_blob._0_4_;
      Joy1_Delay = 0;
      return joy_key_blob._0_4_;
    }
    Joy1_Delay = Joy1_Delay + 1;
    if (Joy1_Delay < 0x27) {
      uVar1 = 0;
    }
    else {
      Joy1_Delay = 0x1e;
      uVar1 = joy_key_blob._0_4_;
    }
    return uVar1;
  }
  Joy1_Delay = 0;
  Joy1_Press = 0;
  return 0;
}
