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
 * 做法（三个措施，判据都刻意收窄）
 * ---------------------------------------------------------------
 * ⓪ `constructor`：**栈投毒**（把 SP 下方约 96 KiB 填成固定模式），让"未初始化读"在
 *    两侧得到**同一个确定值**。否则两份二进制因栈帧布局不同（实测帧 0x10C vs 0x20），
 *    未初始化读必然不同 ⇒ 假差异把门禁打红（详见第 ③ 节长注释）。
 *    ★ 实现用**递归帧**填（每层 4 KiB × 24 层），**不做**「SP 减去一个大偏移再写」——
 *      后者在 qemu-user 下会写到未映射区，实测把 guest 打成启动即 SIGSEGV（两侧 stdout 0 行）。
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
#include <stdio.h>
#include <stdlib.h>
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

/* ---- ③ 栈「投毒」：让**未初始化读**变得可复现 -------------------------
 *
 * 为什么需要（P5 实测，控制组给出决定性证据）：
 *   `spi_driver_init()` 在假硬件下会打印 `ROM Size:%08X CRC32:%04X Update time:…`
 *   其中 CRC32 直接取自 `[sp+8]`、时间取自 `[sp+12]` —— 而这两个槽**没有任何初始化**：
 *   它们本应由 `sfc_request()` 填入安全数据，假硬件下这次填不进去 ⇒ 打印的是
 *   **上一层栈帧残留的垃圾**。
 *   实测：原厂二进制跑两遍**完全一致**（20/20 行，自确定性成立），但重建产物打印出
 *   不同的值，并因此在 2 行之前就崩 —— 因为两份二进制是**不同编译器**编的，栈帧布局
 *   不同（实测 `spi_driver_init` 帧：原厂 0x10C / 重建 0x20）⇒ 残留垃圾必然不同。
 *   这类差异**不是代码保真度信号**，却会把门禁打成红色，掩盖真正的信号。
 *
 * 做法：在 guest 里加一个**早于 `main`** 的构造函数（ELF constructor，`__libc_start_main`
 *   初始化链会调用它），把当前栈指针往下约 96 KiB 的区域统一填成固定模式 `0xA5`。
 *   随后所有被复用的栈帧（包括 `spi_driver_init` 的 `[sp+8]/[sp+12]`）读到的都是
 *   **同一个确定值**，于是"未初始化读"在两侧等价 —— 差异只剩真正的实现差异。
 *   ★ 两侧加载**同一份** shim ⇒ 注入模式完全相同，比较依然公平。
 *
 * ★★ 实现方式很关键（这是一个**踩过的坑**）：
 *   不能写「取当前 SP，减掉一个大偏移，再向下 memcpy 一片」—— qemu-user 对 guest 栈的
 *   映射不像原生内核那样按需增长，那个地址可能**未映射**，一写就把 guest 打成启动即
 *   SIGSEGV（实测：两侧 stdout 0 行、只剩 qemu 的 `uncaught target signal 11` 一行，
 *   而这恰好会让"确定性前缀"退化成 1 行 ⇒ 门禁**假 PASS**）。
 *   正确做法：**递归**。每层分配 4 KiB 的 volatile 数组并填满，递归 DEPTH 层再逐层返回。
 *   这样每一页都是**正常栈增长**得到的（qemu 支持），返回后这些页就成为"被污染的废栈"，
 *   供后续更深的调用复用。
 */
#define POISON_BYTE   0xA5u
#define POISON_FRAME  4088u     /* 每层帧大小（略小于一页，避免叠加出界） */
/* ★ 深度：192 层 × 4088 B ≈ 768 KiB。
 *   为什么要这么深（实测推理）：`spi_driver_init` 打印的 `Update time` 取自 `sp+12`，
 *   而该槽在假硬件下**从未被写**（`sfc_request` 的两条读路径都因状态寄存器恒 0 而超时返回、
 *   不写缓冲区；`sflash_read_security_data` 只写 3 字节 = sp+8..sp+10）。
 *   ⇒ 只要调用链深到 96 KiB 以外，第一版 96 KiB 的投毒就够不到这一帧，值不随之变化。
 *   加深覆盖即可判定"到底是不是栈残留"。 */
#define POISON_DEPTH  192u

static void shim_poison_walk(unsigned int depth)
{
    volatile unsigned char buf[POISON_FRAME];
    unsigned int i;

    for (i = 0; i < POISON_FRAME; i++) {
        buf[i] = (unsigned char)POISON_BYTE;
    }
    if (depth > 0u) {
        shim_poison_walk(depth - 1u);
    }
    /* 让编译器无法把这一帧优化掉（volatile 已足够，这里再加一道读回） */
    if (buf[0] != (unsigned char)POISON_BYTE && buf[0] == 0xFFu) {
        return;
    }
}

__attribute__((constructor)) static void shim_poison_stack(void)
{
    shim_poison_walk(POISON_DEPTH);

    /* 证据行（默认静默；把 CGM_SHIM_VERBOSE=1 经 qemu -E 传进 guest 才输出）：
     * 让我们能从采集到的 stderr 里确认"投毒真的跑了、覆盖多少字节"。
     * ★ 用 write(2,…) 而不是 printf：constructor 早于 stdio 完全就绪，避免缓冲陷阱。 */
    if (getenv("CGM_SHIM_VERBOSE") != NULL) {
        char buf[128];
        int n = snprintf(buf, sizeof(buf),
                         "[shim] stack poison: frame=%u B x depth=%u = %u KiB, byte=0x%02X\n",
                         (unsigned)POISON_FRAME, (unsigned)POISON_DEPTH,
                         (unsigned)(POISON_FRAME * POISON_DEPTH / 1024u),
                         (unsigned)POISON_BYTE);
        if (n > 0) {
            (void)write(2, buf, (size_t)(n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1));
        }
    }
}

/* ---- ② 物理寄存器映射 → 匿名零页 ------------------------------------- */static void *sys_mmap2(void *addr, size_t len, int prot, int flags,
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
