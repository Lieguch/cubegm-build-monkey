/* ============================================================
 * InitSound   @ 0x0000db08   size=160B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitSound(void)

{
  if (handle == 0) {
    return;
  }
  sound_driver_init = (gh_code *)dlsym(handle,"sound_driver_init");
  if (sound_driver_init != (gh_code *)0x0) {
    /* ★★★ 2026-09-22（GAP 16.72）：第 2 实参必须是**立即数 44100**（采样率），
     *   绝不能再写 `UpdateROM` —— 这是一次**Ghidra「常量 vs 符号」混淆**，且后果致命。
     *   工厂机器码（0x0db4c-0x0db60）：
     *       mov  r2, #2          ; arg3 = 2（≥1 ⇒ 立体声）
     *       movw r1, #44100      ; ★ arg2 = **44100(0xAC44)** —— 采样率
     *       ldr  r0, [=USE_HDMI_OUT]
     *       blx  r5              ; sound_driver_init(USE_HDMI_OUT, 44100, 2)
     *   而 44100 == **0xAC44**，**恰好等于**工厂里 `UpdateROM` 的函数地址 0x0000ac44
     *   ⇒ Ghidra 把「立即数 44100」反编译成了符号 `UpdateROM`，我们的重建原样抄了下来。
     *   在工厂布局里这个错误"碰巧无害"（两者数值相同），但在我们的产物里 `UpdateROM`
     *   被链接到 0x4e4060 附近 ⇒ 传给驱动的采样率变成 **≈5,128,288 Hz**。
     *   driver.so 的 `sound_driver_init` 用它算 buffer 大小：
     *       [fp,#-32] = arg2;  [fp,#-24] = (40*(arg2+1))/100 → 取 2 的幂
     *   ⇒ SoundDataBufferLen/period 被算成天文数字 ⇒ `snd_pcm_hw_params()` 返回 -22(EINVAL)
     *   ⇒ 真机日志 `failed to apply hwparams: -22`（原厂同一处是无关紧要的
     *   `snd_pcm_start failed: -32(EPIPE)`，它照常活下去）。
     *   ★ 纪律：**凡是「工厂是一条 movw/mov 立即数」的实参，重建里绝不能出现符号名**；
     *     判据 = 拿工厂反汇编的立即数与我们的实参值对拍（见 tools/lint_const_args.py）。 */
    (*sound_driver_init)(USE_HDMI_OUT,44100,2);
    sound_driver_playframe = dlsym(handle,"sound_driver_playframe");
    if (sound_driver_playframe != 0) {
      return;
    }
    puts("can\'t find sound_driver_playframe proc");
    return;
  }
  puts("can\'t find sound_driver_init proc");
  return;
}
