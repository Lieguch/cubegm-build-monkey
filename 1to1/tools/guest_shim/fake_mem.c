/* fake_mem.c — 假硬件 shim（LD_PRELOAD，armhf；**两侧 guest 用同一份**）
 *
 * 目的
 * ---------------------------------------------------------------
 * 让被测程序在 qemu 里能走得更深。实测的浅窗口成因（工厂源码 0xba1c sunxi_gpio_init）：
 *
 *     __fd = open("/dev/mem", O_RDWR);
 *     if (__fd < 0) return (void*)1;        // ← qemu/runner 上没有 /dev/mem ⇒ 就此返回（实测）
 *     CRU   = mmap(NULL, 0x400 , RW, SHARED, __fd, 0x20000000);
 *     GRF   = mmap(NULL, 0x2000, RW, SHARED, __fd, 0x20008000);
 *     GPIO0 = mmap(NULL, 0x4000, RW, SHARED, __fd, 0x2007c000);
 *     GPIO1 = mmap(NULL, 0x4000, RW, SHARED, __fd, 0x20080000);
 *     GPIO2 = mmap(NULL, 0x4000, RW, SHARED, __fd, 0x20084000);
 *     … 读/写 CRU+0xf0、GRF+0xa8、GRF+200（A20 风格寄存器）
 *
 * `InitJoystick()` 拿到非 0 后打印 `Failed to initialize GPIO`，随后**无条件**调
 * `InitRFJoystick()`，其中 `*(u32*)(GPIO2 + 4) |= 8` 而 `GPIO2 == NULL` ⇒ SIGSEGV。
 * 于是两侧的可观测窗口都只有 13 行 stdout，"等价"很浅。
 *
 * 做法（两个符号，判据都刻意收窄）
 * ---------------------------------------------------------------
 * ① `open/open64/openat`：只把**设备节点**重定向到 `/dev/zero`
 *    （白名单前缀：/dev/mem、/dev/fb、/dev/dri、/dev/input、/dev/sunxi、/dev/disp、
 *      /dev/cedar、/dev/spi、/dev/i2c）。其余路径（setting.xml / menu.log / *.so …）原样转发。
 *    为什么是 /dev/zero：O_RDONLY/O_RDWR 都能打开、读回 0、且可 mmap ⇒
 *    「文件存在但设备是空的」——正是我们想要的"假硬件"语义。
 * ② `mmap`：物理寄存器映射（MAP_SHARED + 可写 + 偏移 ≥ 4 MiB）改送**匿名零页**。
 *    寄存器读回 0、写入落在自己的页里 ⇒ 两侧完全一致，差分有效性不受影响。
 *
 * 判据（避免误伤正常文件映射）：
 *     fd >= 0  &&  (flags & MAP_SHARED)  &&  (prot & PROT_WRITE)  &&  off >= 0x00400000
 *
 * ★ 关键：只拦 mmap 是不够的 —— `open("/dev/mem")` 先失败，mmap 根本走不到（实测踩到）。
 * ★ 全部用**系统调用**实现（不经 dlsym/RTLD_NEXT）：少一层依赖，且与 glibc 版本无关。
 *   ARM EABI 的 `mmap2` 以**页**为单位传偏移（__NR_mmap2 = 192）。
 * ★ 不拦截 `ioctl`：让 ioctl 照常失败（ENOTTY），由被测程序自己的错误分支处理 ——
 *   两侧一致；而"伪造 ioctl 成功"会把未初始化的结构体交给程序，反而引入不确定性。
 *
 * 注意
 * ---------------------------------------------------------------
 * 本 shim **不进交付产物**：只在 qemu 行为采集时经 `LD_PRELOAD` 注入（由包装脚本用
 * qemu 的 `-E` 传给 **guest**；绝不能 export 到宿主 —— qemu 自己是 x86_64 宿主程序，
 * 宿主 ld.so 见到 armhf 的 .so 会直接崩，实测两侧 exit=129、零输出）。
 * 且**工厂侧与重建侧加载同一份**，保证差分是"同一环境下比实现"。
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef __NR_mmap2
#define __NR_mmap2 192
#endif
#ifndef SYS_openat
#define SYS_openat __NR_openat
#endif
#ifndef AT_FDCWD
#define AT_FDCWD (-100)
#endif

#define PHYS_OFF_MIN 0x00400000UL     /* 低于此偏移视为普通文件映射，原样转发 */

/* ---- ① 设备节点重定向 ------------------------------------------------ */
static const char *const DEV_PREFIX[] = {
    "/dev/mem", "/dev/fb", "/dev/dri", "/dev/input",
    "/dev/sunxi", "/dev/disp", "/dev/cedar", "/dev/spi", "/dev/i2c",
    NULL
};

static const char *redirect_dev(const char *path)
{
    int i;
    if (path == NULL) {
        return NULL;
    }
    if (strncmp(path, "/dev/", 5) != 0) {
        return NULL;
    }
    for (i = 0; DEV_PREFIX[i] != NULL; i++) {
        if (strncmp(path, DEV_PREFIX[i], strlen(DEV_PREFIX[i])) == 0) {
            return "/dev/zero";
        }
    }
    return NULL;
}

static int raw_openat(const char *path, int flags, mode_t mode)
{
    return (int)syscall(SYS_openat, AT_FDCWD, path, flags, mode);
}

static int open_impl(const char *path, int flags, va_list ap)
{
    mode_t mode = 0;
    const char *tgt;

    if (flags & (O_CREAT | O_TMPFILE)) {
        mode = (mode_t)va_arg(ap, int);
    }
    tgt = redirect_dev(path);
    return raw_openat(tgt != NULL ? tgt : path, flags, mode);
}

int open(const char *path, int flags, ...)
{
    va_list ap;
    int rc;
    va_start(ap, flags);
    rc = open_impl(path, flags, ap);
    va_end(ap);
    return rc;
}

int open64(const char *path, int flags, ...)
{
    va_list ap;
    int rc;
    va_start(ap, flags);
    rc = open_impl(path, flags, ap);
    va_end(ap);
    return rc;
}

int openat(int dirfd, const char *path, int flags, ...)
{
    mode_t mode = 0;
    const char *tgt;

    if (flags & (O_CREAT | O_TMPFILE)) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }
    /* 只有 AT_FDCWD + 绝对路径才做重定向；相对目录一律原样转发 */
    tgt = (dirfd == AT_FDCWD) ? redirect_dev(path) : NULL;
    if (tgt != NULL) {
        return raw_openat(tgt, flags, mode);
    }
    return (int)syscall(SYS_openat, dirfd, path, flags, mode);
}

/* ---- ② 物理寄存器映射 → 匿名零页 ------------------------------------- */
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
