/* ============================================================
 * sfc_init   @ 0x002c43f8   size=152B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 sfc_init(void)

{
  int __fd;
  gh_u4 uVar2;
  /* ★★★ 2026-09-22（GAP 16.76）：**MMIO 必须用 volatile、且宽度必须是 32 位**。
   *
   * 真机证据（探针 v3，t1 交付版）：`SIGBUS(7)  si_addr=<mmap基址>+0x2C`、PC=`sfc_init+0x6c`，
   * 且 r7=0x10208000（mmap 偏移）、r0=mmap 基址 —— 即**读 SFC 寄存器那一刻总线错误**。
   *
   * 与工厂逐条对照，**唯一差异就是这个读的宽度**：
   *     工厂 0x2c4464:  ldr  r3, [r2, #44]      ← 32 位读
   *                     uxth r3, r3
   *     我们（旧）     : ldrh r1, [r0, #44]      ← ★ 16 位读
   * 原因：源码写的是 `puVar1[0xb] & 0xffff`（puVar1 是 `gh_u4*`），GCC 只用到低半字，
   * 就把 32 位加载**窄化**成 `ldrh` —— 对普通内存是合法优化，**对设备寄存器是改硬件行为**。
   * 顺带它还**调换了顺序**：工厂是「先写 [base]=0，再读 [base+0x2C]」，我们成了「先读后写」。
   *
   * ★ 纪律：**凡 mmap 出来的设备寄存器，指针一律 `volatile`**。
   *   · volatile 读/写**宽度与顺序都被固化**（编译器不得窄化、合并、重排）
   *   · 这正是本项目的核心目标：与工厂**逐条等价**，而不是"功能看起来一样"
   * 门禁：`tools/mmio_width_audit.py`（对照工厂/我们的访存宽度直方图，三态自证）。 */
  volatile gh_u4 *regs;

  __fd = open("/dev/mem",2);
  if (__fd < 0) {
    return 0xffffffff;
  }
  g_sfc_reg = mmap((void *)0x0,0x400,3,1,__fd,0x10208000);
  if (g_sfc_reg == (gh_u4 *)0xffffffff) {
    return 0xfffffffe;
  }
  close(__fd);
  regs = (volatile gh_u4 *)g_sfc_reg;
  uVar2 = 0;
  *regs = 0;                              /* SFC 控制寄存器：32 位写（工厂：str r0,[r2]） */
  if (3 < (regs[0xb] & 0xffffu)) {        /* 工厂：ldr + uxth —— **32 位读**再取低半字 */
    regs[0x22] = 1;                       /* 工厂：strhi r3,[r2,#136] —— 32 位写 */
  }
  return uVar2;
}
