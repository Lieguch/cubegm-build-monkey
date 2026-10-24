/* ============================================================
 * PlaySound   @ 0x0000dbdc   size=32B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

#ifdef CGM_DIAG_TRACE_INPUT
extern void cgm_probe_io(int tag, unsigned a, unsigned b);
#endif

/* ★★★★★ 2026-10-23（R264，**本轮的关键修复**）
 *
 * 工厂机器码（0xdbdc，全函数）：
 *      dbdc: ldr r3,[pc,#24]  ; GOT 取 sound_driver_playframe 槽
 *      dbe4..dbec: r3 = [r3]  ; 若为 0
 *      dbf0: cmp r3,#0
 *      dbf4: bxeq lr          ; 空指针直接返回
 *      dbf8: bx r3            ; **尾调用**：r0/r1 原样转给 driver.so
 *
 * 三个调用点都**带两个实参**（机器码为证，例如 AudioProcess 0x26ab8）：
 *      movw r1,#735 (0x2df) ; add r0,pc,lit ; add r0,r0,#0x940 ; bl PlaySound
 *      TestRun  0xb644: mov r0,r8 ; movw r1,#0x2df ; bl PlaySound
 *      PlayFrame        : PlaySound(param_1, param_2)
 *
 * 我们此前把它重建成 `void PlaySound(void)` + `(*sound_driver_playframe)()`
 * ⇒ 编译器发的是**无实参调用**，r0/r1 是残留值 ⇒ driver.so 收到**垃圾缓冲区与长度**。
 * 实测后果（真机第 5 轮）：**全程没有任何声音**；且按键后驱动按垃圾指针处理音频，
 * 紧接着整机冻住（画面停在选项下移一格的那一刻）。
 * ★ 这类"K&R 声明掩盖形参个数"的坑与 sunxi_gpio_output 同一族，已由
 *   tools/check_argcount.py 覆盖（基线外的新增会被编译前门禁拦下）。
 */
void PlaySound(void *param_1, gh_u4 param_2)

{
  if (sound_driver_playframe == (gh_code *)0x0) {
    return;
  }
#ifdef CGM_DIAG_TRACE_INPUT
  { static int sc; if (sc++ < 16) cgm_probe_io('S', (unsigned)param_2, (unsigned)(gh_u4)(gh_uint)param_1); }
#endif
  ((void (*)(void *, gh_u4))sound_driver_playframe)(param_1, param_2);
#ifdef CGM_DIAG_TRACE_INPUT
  { static int sc2; if (sc2++ < 16) cgm_probe_io('s', 0, 0); }
#endif
  return;
}
