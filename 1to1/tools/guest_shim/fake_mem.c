/* fake_mem.c — 假硬件 shim（LD_PRELOAD，armhf；**两侧 guest 用同一份**）
 *
 * 目的
 * ---------------------------------------------------------------
 * 让被测程序在 qemu 里能走得更深。现状：`InitJoystick()` 里 `sunxi_gpio_init()` 因为
 * `open("/dev/mem")` / `mmap(phys)` 在 qemu 下必然失败而返回非 0 ⇒ 打印
 * `Failed to initialize GPIO`，随后**无条件**执行 `InitRFJoystick()`，其中
 * `*(u32*)(GPIO2 + 4) |= 8` 而 `GPIO2 == NULL` ⇒ SIGSEGV。
 * 于是两侧的可观测窗口都只有 13 行 stdout，行为差分的"等价"很浅。
 *
 * 做法（只拦一个符号：`mmap`）
 * ---------------------------------------------------------------
 * `sunxi_gpio_init()` 的调用形态实测为：
 *     mmap(NULL, 0x400, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x20000000)
 *     mmap(NULL, 0x2000/0x4000, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0x20008000/0x2007c000/…)
 * 即「物理内存寄存器映射」= `MAP_SHARED` + 可写 + **偏移是大物理地址**。
 * 这类映射在 qemu 里没有真实设备支撑，改送一块**真实的可写零页**（匿名映射）即可：
 * 寄存器读回 0、写入被丢弃 —— 对两侧完全一致，因此差分有效性不受影响。
 *
 * 判据（刻意收窄，避免误伤正常的文件映射）：
 *     fd >= 0  &&  (flags & MAP_SHARED)  &&  (prot & PROT_WRITE)  &&  off >= 0x00400000
 * ★ 用纯粹的系统调用实现（不经 dlsym/RTLD_NEXT）：少一层依赖，且对 glibc 版本无关。
 *   ARM EABI 的 `mmap2` 以**页**为单位传偏移（__NR_mmap2 = 192）。
 *
 * 注意
 * ---------------------------------------------------------------
 * 本 shim **不进交付产物**：只在 qemu 行为采集时通过 `LD_PRELOAD` 注入，且
 * **工厂侧与重建侧加载同一份**，保证差分是"同一环境下比实现"而不是"比环境"。
 */
#define _GNU_SOURCE
#include <stddef.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef __NR_mmap2
#define __NR_mmap2 192
#endif

#define PHYS_OFF_MIN 0x00400000UL     /* 低于此偏移视为普通文件映射，原样转发 */

static void *sys_mmap2(void *addr, size_t len, int prot, int flags,
                       int fd, unsigned long off)
{
    /* ARM 的 mmap2：off 以页为单位 */
    return (void *)syscall(__NR_mmap2, addr, len, prot, flags, fd, off >> 12);
}

void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t off)
{
    unsigned long uoff = (unsigned long)off;

    if (fd >= 0 && (flags & MAP_SHARED) && (prot & PROT_WRITE)
        && uoff >= PHYS_OFF_MIN) {
        /* 物理寄存器映射 ⇒ 给一块真实可写的匿名零页（"映射成功，但设备不存在"） */
        void *p = sys_mmap2(NULL, len, PROT_READ | PROT_WRITE,
                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
        if (p != MAP_FAILED) {
            return p;
        }
        /* 匿名映射也失败 ⇒ 退回原语义，让上层自己去报错 */
    }
    return sys_mmap2(addr, len, prot, flags, fd, uoff);
}
