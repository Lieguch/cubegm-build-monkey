/* ============================================================
 * SoundClose   @ 0x00022404   size=116B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SoundClose(int param_1)

{
  int *__ptr;
  
  if (*(int *)(SoundPlayer + param_1 * 0x24 + 4) == 1) {
    __ptr = *(int **)(SoundPlayer + param_1 * 0x24);
    if (*__ptr != 0) {
      /* ★ 2026-09-18（第 47 轮）显式化：原写法 `MP3FreeDecoder()` 依赖
       * 上一句 `if (*__ptr != 0)` 留在 **r0** 里的寄存器副产物（工厂同样如此：
       * `2244c: ldr r0,[r6]` → `cmp r0,#0` → `beq` → `bl MP3FreeDecoder`，与我们
       * `500bf70: ldr r0,[r4]` → `cmp` → `beq` → `bl` **逐指令同形**）。
       * 但"依赖副产物"在换编译器后就会变成传垃圾 ⇒ 按项目纪律**显式化**：
       * 原型（proto.h）已按上游 `void MP3FreeDecoder(HMP3Decoder)` 改为真原型，
       * 调用点同步把 handle 写出来；码不变（r0 里已是同一个值，编译器无需重载）。 */
      MP3FreeDecoder((void *)*__ptr);
    }
    if ((void *)__ptr[3] != (void *)0x0) {
      free((void *)__ptr[3]);
    }
    free(__ptr);
  }
  *(gh_u4 *)(SoundPlayer + param_1 * 0x24) = 0;
  return;
}
