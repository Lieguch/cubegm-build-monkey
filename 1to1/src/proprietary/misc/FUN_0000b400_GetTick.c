/* ============================================================
 * GetTick   @ 0x0000b400   size=48B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* 证据：b414 ldm sp,{r0,r2}(tv_sec,tv_usec) + b41c movt r3,#15(0xF4240=1000000)
   + b420 mla r0,r3,r0,r2 + b424 asr r1,r0,#31 → 返回 64 位微秒 1000000*sec+usec */
gh_longlong GetTick(void)

{
  timeval local_10;
  
  gettimeofday(&local_10,(__timezone_ptr_t)0x0);
  return (gh_longlong)(int)(local_10.tv_sec * 1000000 + local_10.tv_usec);
}
