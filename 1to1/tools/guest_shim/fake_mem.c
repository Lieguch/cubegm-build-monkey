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
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <ucontext.h>
#include <unistd.h>

/* ★ 弱引用 `dladdr`：只用于「真崩溃现场点名 pc 属于哪个库的哪个函数」。
 *   故意**不** `#include <dlfcn.h>`、也不 `-ldl` —— 用弱符号 + 自定义同布局结构体，
 *   保证链接期零依赖风险（zig 的 arm-linux-gnueabihf 目标不一定自带 libdl 导入库）。
 *   运行时若未解析则为 NULL，调用点已判空。 */
extern int dladdr(const void *addr, void *info) __attribute__((weak));

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

/* SFC（SPI Flash 控制器）寄存器页的物理偏移 —— 见 ② 段长注释 */
#define SFC_REG_OFF  0x10208000UL
#define SFC_REG_MIN  0x400u          /* SFC 寄存器区长度（sfc_init 映射 0x400）*/

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

/* ---- ②c 场景 E：`.zip` 打开瞬间**重新断言** key2 ---------------------------------
 * 动机（单变量定位"写入者"）：
 *   · 已知 `unzlocal_SearchCentralDir` 比对的是 `key2[0..7]`，而 `key2` 在 BSS（初值 0）；
 *   · 场景 B（constructor 里注入正确字节）会区分两种世界：
 *       行为仍不变 ⇒ 有代码在 constructor 之后把它覆写 = **存在写入者**；
 *       行为改变   ⇒ 无写入者，窗口直接打开。
 *   · 若存在写入者，本开关把写入时刻**推到 last moment**（打开 .zip 之前一瞬）：
 *       行为改变 ⇒ 写入发生在 constructor 与 zip-open 之间（写入者被夹到极窄窗口内）；
 *       行为仍不变 ⇒ 写入发生在 open 之后（下一次实验只需再往后推）。
 *   ★ 只在 `CGM_KEY2_HOOK=1` 时生效；两侧共用同一 shim ⇒ 差分依旧公平。 */
static int g_key2_hook, g_key2_hook_logged, g_key2_hits;

/* ★ 本段位于 `note` 的正式定义（更靠后）之前 ⇒ 必须先给前置声明，
 *   否则 zig/cc 报 "call to undeclared function 'note'"（实测就是这个错）。 */
static void note(const char *fmt, ...);

static void key2_assert(void)
{
    static const unsigned char sig[8] = { 'P', 'K', 0x05, 0x06, 'P', 'K', 0x07, 0x08 };
    volatile unsigned char *p = (volatile unsigned char *)(unsigned long)0x003E190Cu;
    int i;
    for (i = 0; i < 8; i++) {
        p[i] = sig[i];
    }
}

static int is_zip_path(const char *path)
{
    size_t n;
    if (path == NULL) {
        return 0;
    }
    n = strlen(path);
    return (n >= 4 && path[n - 4] == '.' && path[n - 3] == 'z'
            && path[n - 2] == 'i' && path[n - 1] == 'p');
}

/* ---- ②d I/O 轨迹（`CGM_IO_TRACE=1`）：**自证探针可达** -------------------------------
 * 为什么必须有（本轮实测教训）：
 *   场景 E 里 `key2 re-assert on open(...)` 一行都没打印，而我们**无法判断**
 *   "是钩子没生效" 还是 "zip 根本不经过这个拦截点"。按技能铁律 100/101：
 *   **任何"探针没输出"都必须能自证探针本身可达**，否则结论无效、白烧一轮 CI。
 * 做法：把 shim 看到的**每一个**文件打开（open/open64/openat/fopen64/fopen）连同结果
 *   打到 stderr（上限 48 条）。有这条轨迹，就能一眼看出 zip 走的是哪条路径。 */
static int g_io_trace, g_io_trace_n;

static void io_trace(const char *fn, const char *path, int rc)
{
    if (!g_io_trace || g_io_trace_n >= 48) {
        return;
    }
    g_io_trace_n++;
    note("[shim] io #%02d %-8s rc=%-4d %s%s\n", g_io_trace_n, fn, rc,
         (path != NULL) ? path : "(null)",
         (path != NULL && is_zip_path(path)) ? "   ◀ ZIP" : "");
}

static void key2_hook_try(const char *path)
{
    if (!g_key2_hook || !is_zip_path(path)) {
        return;
    }
    key2_assert();
    g_key2_hits++;
    if (g_key2_hook_logged < 6) {
        volatile unsigned char *p = (volatile unsigned char *)(unsigned long)0x003E190Cu;
        note("[shim] key2 re-assert on open(%s) -> 回读=%02x %02x %02x %02x %02x %02x %02x %02x\n",
             path, (unsigned)p[0], (unsigned)p[1], (unsigned)p[2], (unsigned)p[3],
             (unsigned)p[4], (unsigned)p[5], (unsigned)p[6], (unsigned)p[7]);
        g_key2_hook_logged++;
    }
}

static int open_impl(const char *path, int flags, va_list ap)
{
    mode_t mode = 0;
    const char *tgt;

    if (flags & (O_CREAT | O_TMPFILE)) {
        mode = (mode_t)va_arg(ap, int);
    }
    key2_hook_try(path);
    tgt = redirect_dev(path);
    {
        int rc = raw_openat(tgt != NULL ? tgt : path, flags, mode);
        io_trace("open", path, rc);
        return rc;
    }
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

/* ---- ②e `fopen`/`fopen64` 拦截（本轮补的关键缺口）--------------------------------
 * 实测事实：`rkgame` 的动态导入**同时含 `open` 与 `fopen`**，而 zip 读法（反编译里的
 * `lufseek`/`luftell`/`lufread`）走的是 **stdio 层（`FILE*`）**。
 * glibc 的 `fopen` **内部用隐藏符号调 `open64`，不走 PLT** ⇒ 我们原来的
 * `open`/`openat` 拦截点**根本不经过** ⇒ 场景 E 的 `.zip` 重断言钩子静默失效
 * （stderr 里 0 条 `re-assert`，而 stderr 本身是好的）。
 * ⇒ 必须直接拦截 `fopen`/`fopen64` 才能拿到"打开 .zip 的前一瞬间"。
 *
 * 链接策略（避免给 shim 增加硬依赖）：
 *   ① 弱声明 `dlsym`，可用则取 `RTLD_NEXT` 下的真 `fopen`（语义 100% 一致）；
 *   ② 取不到就退化为 `open(path, mode→flags) + fdopen(fd, mode)`（只覆盖常见的
 *      r/w/a 与 `+`、`b`、`x` 组合；本场景只读为主，风险可控）。
 */
__attribute__((weak)) extern void *dlsym(void *handle, const char *symbol);
#define SHIM_RTLD_NEXT ((void *)-1l)

static int mode_to_flags(const char *mode)
{
    int fl;
    char c0 = (mode != NULL) ? mode[0] : 'r';
    int plus = (mode != NULL && strchr(mode, '+') != NULL);
    if (c0 == 'w') {
        fl = plus ? (O_RDWR | O_CREAT | O_TRUNC) : (O_WRONLY | O_CREAT | O_TRUNC);
    } else if (c0 == 'a') {
        fl = plus ? (O_RDWR | O_CREAT | O_APPEND) : (O_WRONLY | O_CREAT | O_APPEND);
    } else {
        fl = plus ? O_RDWR : O_RDONLY;
    }
    if (mode != NULL && strchr(mode, 'x') != NULL) {
        fl |= O_EXCL;
    }
    return fl;
}

static FILE *(*g_real_fopen)(const char *, const char *);
static FILE *(*g_real_fopen64)(const char *, const char *);
static int g_fopen_chain = 1;      /* 1=dlsym(RTLD_NEXT) 真 fopen；2=强制 open+fdopen */
static int g_in_fopen;             /* 重入保护：绝不在链式调用里递归进自己 */

/* constructor 阶段**预解析**真 fopen：决不在 fopen 内部第一次调 dlsym
 * （dlsym 自身可能 malloc/触发符号解析，从 fopen 内部首次进入风险不可控）。 */
static void shim_resolve_fopen(void)
{
    if (dlsym != NULL) {
        if (g_real_fopen == NULL) {
            g_real_fopen = (FILE *(*)(const char *, const char *))dlsym(SHIM_RTLD_NEXT, "fopen");
        }
        if (g_real_fopen64 == NULL) {
            g_real_fopen64 = (FILE *(*)(const char *, const char *))dlsym(SHIM_RTLD_NEXT, "fopen64");
        }
    }
}

static FILE *shim_fopen_impl(const char *path, const char *mode, int is64)
{
    FILE *(*real_fn)(const char *, const char *);
    FILE *fp;
    int fd;

    if (g_in_fopen) {                       /* 递归 ⇒ 直接走最底层的 open+fdopen */
        fd = raw_openat(path, mode_to_flags(mode), 0644);
        return (fd < 0) ? NULL : fdopen(fd, mode);
    }
    g_in_fopen = 1;
    key2_hook_try(path);
    real_fn = is64 ? g_real_fopen64 : g_real_fopen;
    if (g_fopen_chain == 1 && real_fn != NULL) {
        fp = real_fn(path, mode);
        io_trace(is64 ? "fopen64" : "fopen", path, fp ? 0 : -1);
        (void)mode;
        g_in_fopen = 0;
        return fp;
    }
    fd = raw_openat(path, mode_to_flags(mode), 0644);
    if (fd < 0) {
        io_trace(is64 ? "fopen64*" : "fopen*", path, -1);
        g_in_fopen = 0;
        return NULL;
    }
    fp = fdopen(fd, mode);
    if (fp == NULL) {
        (void)syscall(SYS_close, fd);
    }
    io_trace(is64 ? "fopen64*" : "fopen*", path, fp ? 0 : -1);
    g_in_fopen = 0;
    return fp;
}

FILE *fopen(const char *path, const char *mode)
{
    return shim_fopen_impl(path, mode, 0);
}

FILE *fopen64(const char *path, const char *mode)
{
    return shim_fopen_impl(path, mode, 1);
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
    key2_hook_try(path);
    /* 只有 AT_FDCWD + 绝对路径才做重定向；相对目录一律原样转发 */
    tgt = (dirfd == AT_FDCWD) ? redirect_dev(path) : NULL;
    {
        int rc = (tgt != NULL) ? raw_openat(tgt, flags, mode)
                              : (int)syscall(SYS_openat, dirfd, path, flags, mode);
        io_trace("openat", path, rc);
        return rc;
    }
}

/* ---- ③ SFC（SPI Flash 控制器）设备仿真 -------------------------------
 *
 * 目标：让 `spi_driver_init()` 的 flash 校验和通过（它返回非 0 时，main() 才会继续走
 *       `UpdateROM → ShareMemCreat → XintiaoThread → main_Menu()` —— 菜单，重建量最大的一块）。
 *
 * 为什么必须做「**有状态设备**」而不是「一块静态内存页」：
 *   · 读循环是 `*param_3 = g_sfc_reg[0x42]`（**同一个地址**反复读）
 *     ⇒ 静态页每次返回同一个字 ⇒ 缓冲区内容必然 4 字节周期；
 *   · 校验和是 `buf[k] == (KY[k] ^ v_k) + buf[k+0xc0]`，其中 KY（工厂 .rodata @0x002dee30
 *     的 24 字节 = "aXDT8kluSPu6PvHIV2JhA1V4"）实测**不是** 4 字节周期
 *     （KY[8]=0x53 vs KY[12]=0x50）⇒ 静态页下**数学上不可能通过**。
 *     （已用「766 KiB 栈投毒」反证那两个值不是随机栈垃圾，而是被写过的确定性内存。）
 *   ⇒ 唯一出路是逐字返回不同数据 ⇒ 需要**每次寄存器访问都能插手**。
 *
 * 做法：把 SFC 寄存器页设成 PROT_NONE，用 SIGSEGV 处理器按设备语义应答：
 *   · 写 0x100（reg[0x40]，低16位=opcode、位16..29=字节数）⇒ 记录"这条命令"并复位 FIFO
 *   · 写 0x104（reg[0x41]）= 地址                        ⇒ 记录"读/写哪个地址"
 *   · 读 0x108（reg[0x42]）= 数据寄存器 ⇒ 每次返回 FIFO 的**下一个字**（逐字变化）
 *   · 读 0x020（reg[8]）= 状态：位16..20 = 当前可读字数（真实 FIFO 语义）
 *   · 读 0x010（reg[4]）= 忙标志：**恒 0**（"立刻空闲"，否则上层会空转 10000 次 usleep）
 *   · 其余寄存器读写走影子数组（等价于"写下去没反应"的假外设）
 *
 * "这片 flash 里存的内容"由 sfc_dev_prepare() 按 (opcode, addr) 决定：
 *   0x9f   @ —      → 芯片 ID {0x0b, 0x00, 0x18}（0x0b 让原厂走上它的 W25Q 分支）
 *   0x485a @0x194   → 16 字节：前 8 = KY[0..7]、后 8 = 0
 *                     ⇒ 代码算出 UniqueID[k] = buf[k] ^ buf[k+8] = KY[k]
 *   0x4848 @0x100   → 全 0 ⇒ 打印 `ROM Size:01000000 CRC32:0000 Update time:1980-0-0 0:0:0`
 *   0x4848 @0x000   → 256 字节，**按校验和方程反解**（见下）
 *   其它            → 全 0
 *
 * ★ 反解（不硬编码结果，全部由 KY 现算，避免抄错）：
 *     校验和：buf[k] == (KY[k] ^ v_k) + buf[k+0xc0]
 *             v_k = UniqueID[k] = KY[k]      (k < 8)
 *             v_k = buf[k-8]                 (k >= 8)
 *     令 buf[0xc0..0xd7] = 0（+0 项消失），于是
 *             k = 0..7  : buf[k] = KY[k] ^ KY[k]     = 0
 *             k = 8..15 : buf[k] = KY[k] ^ buf[k-8]  = KY[k]
 *             k = 16..23: buf[k] = KY[k] ^ KY[k-8]
 *
 * ★ 两侧加载**同一份** shim ⇒ 拿到同一片"假 flash" ⇒ 差分依然公平（设备是环境，不是实现）。
 * ★ 回退开关：`CGM_SFC_MODE=seed` 退回旧的"静态种子页"行为（便于不改代码排查）。
 */
#define SFC_OFF_BUSY   0x010u    /* reg[4]  忙标志（读恒 0）*/
#define SFC_OFF_STATUS 0x020u    /* reg[8]  状态：位 16..20 = 可读字数 */
#define SFC_OFF_STAT2  0x024u    /* reg[9]  状态2 */
#define SFC_OFF_CMD    0x100u    /* reg[0x40] 低16=opcode、位16..29=字节数 */
#define SFC_OFF_ADDR   0x104u    /* reg[0x41] 地址 */
#define SFC_OFF_DATA   0x108u    /* reg[0x42] 数据寄存器（FIFO）*/

/* 工厂 .rodata @0x002dee30 的 24 字节校验密钥表（逐字节取自工厂镜像）*/
static const unsigned char KY[24] = {
    0x61, 0x58, 0x44, 0x54, 0x38, 0x6b, 0x6c, 0x75,
    0x53, 0x50, 0x75, 0x36, 0x50, 0x76, 0x48, 0x49,
    0x56, 0x32, 0x4a, 0x68, 0x41, 0x31, 0x56, 0x34
};

static volatile unsigned char *g_sfc_base;      /* 设备页基址（0 = 未装配）*/
static unsigned int g_sfc_pagelen;              /* 受保护长度（按页取整）*/
static int g_sfc_mode_device = 1;               /* 1 = 设备仿真；0 = 旧静态种子 */

static unsigned char g_shadow[SFC_REG_MIN];     /* 其它寄存器影子 */
static unsigned char g_pay[256];                 /* 当前请求的"flash 内容" */
static unsigned int  g_pay_len;                  /* 有效字节数（0 = 无限 0）*/
static unsigned int  g_pay_pos;
static unsigned int  g_pay_zero = 1;
static unsigned int  g_prepared;
static unsigned int  g_opcode;
static unsigned int  g_addr;
static unsigned int  g_reqlen;
static unsigned long g_faults, g_cmds, g_unhandled;
static int           g_logged;
static int           g_mode_ready;
/* ★ 场景 B（key2 注入）是否启用 —— 崩溃现场探针要用它决定是否回读 key2。 */
static int           g_key2_seeded;

/* 前置声明（定义在后面的段落里）*/
static void note(const char *fmt, ...);
static void sfc_seed(void *p, size_t len);

static void sfc_dev_prepare(void)
{
    unsigned int i;

    if (g_prepared) {
        return;
    }
    g_prepared = 1;
    g_pay_pos  = 0;
    g_pay_zero = 1;                 /* 默认：无限 0（不耗尽，避免上层空转等待）*/
    g_pay_len  = 0;

    if (g_opcode == 0x009f) {                       /* JEDEC ID */
        g_pay_zero = 0;
        g_pay[0] = 0x0b;                            /* 让原厂走 "id == 0x0b" 分支 */
        g_pay[1] = 0x00;
        g_pay[2] = 0x18;                            /* => FlashSize = 0x1000000 */
        g_pay[3] = 0x00;
        g_pay_len = 4;
    } else if (g_opcode == 0x485a) {                /* 读 UniqueID（16 字节）*/
        g_pay_zero = 0;
        for (i = 0; i < 8; i++) {
            g_pay[i] = KY[i];                       /* => UniqueID[k] = KY[k] */
        }
        for (i = 8; i < 16; i++) {
            g_pay[i] = 0;
        }
        g_pay_len = 16;
    } else if (g_opcode == 0x4848 && g_addr == 0x0000) {
        g_pay_zero = 0;
        memset(g_pay, 0, sizeof(g_pay));
        for (i = 0; i < 8; i++) {
            g_pay[i] = (unsigned char)(KY[i] ^ KY[i]);          /* = 0 */
        }
        for (i = 8; i < 24; i++) {
            g_pay[i] = (unsigned char)(KY[i] ^ g_pay[i - 8]);   /* 反解出来的键 */
        }
        g_pay_len = 256;                            /* buf[0xc0..0xd7] 保持 0 */
    }
    /* 其它（含 0x4848 @0x100）：全 0 ⇒ 打印行与原窗口一致 */

    /* ★★ 实验开关 `CGM_SFC_PATTERN=<hex 字节>`：把**所有** SFC 读载荷统一填成该字节。
     *   要判定的问题：崩溃现场实测 key2 被写成 `00 00 00 00 00 7d 1e 47`（既不是我们注入的
     *   签名、也不是上面任何一种 KY 派生载荷）⇒ 必须先确定「key2 的内容来自哪里」。
     *   判据：若 key2 变成该字节的重复 ⇒ **链路 = SFC 读 → key2**（沙箱修法 = 仿真正确的
     *   security 载荷）；若 key2 不变 ⇒ 来源与 SFC 无关，改用「写陷阱」定位写入者。
     *   ★ 两侧共用同一份 shim、同一取值 ⇒ 差分公平。 */
    {
        const char *sp = getenv("CGM_SFC_PATTERN");
        /* ★ 只覆盖**数据读**：0x9f(芯片ID) 与 0x485a(UniqueID) 必须保持真实，
         *   否则 spi_driver_init 会走错分支（0xC7 不在 {0x85,0x0b,0xc8,0x20} 里）⇒ 根本走不到 zip。 */
        if (sp != NULL && sp[0] != '\0' && g_opcode != 0x009f && g_opcode != 0x485a) {
            unsigned int v = 0, k = 0;
            while (sp[k] != '\0' && k < 8) {
                char c = sp[k]; unsigned int d;
                if (c >= '0' && c <= '9') d = (unsigned int)(c - '0');
                else if (c >= 'a' && c <= 'f') d = (unsigned int)(c - 'a' + 10);
                else if (c >= 'A' && c <= 'F') d = (unsigned int)(c - 'A' + 10);
                else break;
                v = (v << 4) | d; k++;
            }
            if (k > 0) {
                for (i = 0; i < sizeof(g_pay); i++) g_pay[i] = (unsigned char)v;
                g_pay_zero = 0;
                g_pay_len = 256;
            }
        }
    }
    if (g_logged < 24) {
        note("[shim] sfc cmd op=0x%04x addr=0x%06x len=%u -> payload=%s(%u B)\n",
             g_opcode, g_addr, g_reqlen,
             g_pay_zero ? "zeros" : "flash", g_pay_len);
        g_logged++;
    }
}

static unsigned int sfc_fifo_avail(void)
{
    unsigned int rem;

    if (!g_prepared || g_pay_zero) {
        return 16;                  /* 无限 0：永远"有得读" */
    }
    rem = g_pay_len - g_pay_pos;
    return rem == 0 ? 0 : ((rem + 3) / 4 > 16 ? 16 : (rem + 3) / 4);
}

static unsigned long sfc_fifo_next(unsigned int size)
{
    unsigned long v = 0;
    unsigned int i;

    sfc_dev_prepare();
    for (i = 0; i < size; i++) {
        unsigned char b = 0;
        if (g_pay_pos < g_pay_len) {
            b = g_pay[g_pay_pos++];
        }
        v |= (unsigned long)b << (8 * i);
    }
    return v;
}

static unsigned long sfc_dev_read(unsigned int off, unsigned int size)
{
    unsigned int wi = off >> 2, shift = (off & 3u) * 8u;
    unsigned long w = 0, v = 0;
    unsigned int i;

    if (wi == (SFC_OFF_DATA >> 2)) {
        return sfc_fifo_next(size);     /* 数据寄存器：按本次访问宽度推进 FIFO */
    }
    /* ★ 必须按「寄存器字 + 字节偏移」应答：实测重建侧读状态用的是
     *   `ldrh r1,[r0,#34]`（reg[8] 的**上半字** = 可读字数）与 `ldrb r1,[r0,#34]`，
     *   而不是整字读 0x20。只认精确偏移会让这些访问拿到 0 ⇒ FIFO 永远"没数据" ⇒ 上层空转超时。*/
    switch (wi) {
        case SFC_OFF_BUSY >> 2:   w = 0; break;                                   /* 忙标志：恒 0 */
        case SFC_OFF_STATUS >> 2: w = (unsigned long)sfc_fifo_avail() << 16; break;
        case SFC_OFF_STAT2 >> 2:  w = 0; break;
        default:
            if (wi < sizeof(g_shadow) / 4u) {
                w = (unsigned long)g_shadow[wi * 4]
                  | ((unsigned long)g_shadow[wi * 4 + 1] << 8)
                  | ((unsigned long)g_shadow[wi * 4 + 2] << 16)
                  | ((unsigned long)g_shadow[wi * 4 + 3] << 24);
            }
            break;
    }
    w >>= shift;
    for (i = 0; i < size && i < 4u; i++) {
        v |= ((w >> (8 * i)) & 0xffu) << (8 * i);
    }
    return v;
}

static void sfc_dev_write(unsigned int off, unsigned long val, unsigned int size)
{
    unsigned int i;

    if (off == SFC_OFF_CMD) {                       /* 新命令：复位 FIFO */
        g_opcode   = (unsigned int)(val & 0xffffu);
        g_reqlen   = (unsigned int)((val >> 16) & 0x3fffu);
        g_prepared = 0;
        g_pay_pos  = 0;
        g_cmds++;
        return;
    }
    if (off == SFC_OFF_ADDR) {
        g_addr = (unsigned int)val;
        return;
    }
    if ((unsigned long)off + size <= (unsigned long)sizeof(g_shadow)) {
        for (i = 0; i < size; i++) {
            g_shadow[off + i] = (unsigned char)((val >> (8 * i)) & 0xffu);
        }
    }
}

/* --- 寄存器取/存：用**具名字段**（不按结构布局做指针算术，跨 ABI 更安全）--- */
static void regs_load(mcontext_t *m, unsigned long *R)
{
    R[0]  = m->arm_r0;   R[1]  = m->arm_r1;   R[2]  = m->arm_r2;   R[3]  = m->arm_r3;
    R[4]  = m->arm_r4;   R[5]  = m->arm_r5;   R[6]  = m->arm_r6;   R[7]  = m->arm_r7;
    R[8]  = m->arm_r8;   R[9]  = m->arm_r9;   R[10] = m->arm_r10;
    R[11] = m->arm_fp;   R[12] = m->arm_ip;   R[13] = m->arm_sp;
    R[14] = m->arm_lr;   R[15] = m->arm_pc;
}

static void regs_store(mcontext_t *m, const unsigned long *R)
{
    m->arm_r0 = R[0];   m->arm_r1 = R[1];   m->arm_r2 = R[2];   m->arm_r3 = R[3];
    m->arm_r4 = R[4];   m->arm_r5 = R[5];   m->arm_r6 = R[6];   m->arm_r7 = R[7];
    m->arm_r8 = R[8];   m->arm_r9 = R[9];   m->arm_r10 = R[10];
    m->arm_fp = R[11];  m->arm_ip = R[12];  m->arm_sp = R[13];
    m->arm_lr = R[14];  m->arm_pc = R[15];
}

static void sfc_fault(int sig, siginfo_t *si, void *vctx)
{
    ucontext_t *uc = (ucontext_t *)vctx;
    mcontext_t *m  = &uc->uc_mcontext;
    unsigned long addr = (unsigned long)si->si_addr;
    unsigned long R[16];
    unsigned int ins, off, L, I, P, U, W, Rn, Rd, size, wb, mask;
    unsigned long v;

    if (!(g_sfc_base && addr >= (unsigned long)g_sfc_base
          && addr < (unsigned long)g_sfc_base + g_sfc_pagelen)) {
        /* ★★ 这是**真正的崩溃**（不是设备缺页）—— 就在这里把现场打全，比叫 gdb 更可靠：
         *    gdb 停在"有人访问了坏地址"时只能给出 pc，而 pc 常落在 ld.so/PLT 解析器里
         *    （调用点信息已丢）；本处能同时给出 pc / lr（=调用者）/ sp / r0-r5，
         *    足以直接判定"哪条指令、用哪个基址寄存器、被谁调用"。
         *    实测价值：一次就把「崩在 main_Menu() 之前的 PLT 跳转」定位到具体寄存器。 */
        /* ★★ 场景 B 的**判决性探针**（CGM_KEY2_SEED）：场景 B 首跑实测 —— 注入成功
         *    （shim 自己的 evidence 行已打印）、`-E CGM_KEY2_SEED=1` 也确实传进 guest，
         *    但**行为与场景 A 逐字相同**（仍 `open .../ui_cn.zip fail`、覆盖率 48/49 不变）
         *    ⇒ 「中央目录搜索必须比对 key2」这个归因**可能是错的**。崩溃现场再读一次 key2：
         *      · 仍是注入值 ⇒ **key2 不是签名来源**（需重新定位 GOT 目标）；
         *      · 已变全 0   ⇒ 有代码在注入之后**覆写了它**（那就是真正的写入者）。 */
        /* CGM_KEY2_PROBE=1：不依赖注入，直接观察崩溃现场的 key2（判定"谁在写 key2"）。 */
        if (g_key2_seeded || getenv("CGM_KEY2_PROBE") != NULL) {
            volatile unsigned char *k2p = (volatile unsigned char *)(unsigned long)0x003E190Cu;
            note("[shim] key2 @0x3E190C 现值 = %02x %02x %02x %02x %02x %02x %02x %02x"
                 "（注入值应为 50 4b 05 06 50 4b 06 06）\n",
                 (unsigned)k2p[0], (unsigned)k2p[1], (unsigned)k2p[2], (unsigned)k2p[3],
                 (unsigned)k2p[4], (unsigned)k2p[5], (unsigned)k2p[6], (unsigned)k2p[7]);
        }
        note("[shim] ★ 真崩溃 @0x%08lx 不在设备页 (base=%p) pc=0x%08lx lr=0x%08lx sp=0x%08lx\n",
             addr, (void *)g_sfc_base,
             (unsigned long)m->arm_pc, (unsigned long)m->arm_lr,
             (unsigned long)m->arm_sp);
        note("        r0=0x%08lx r1=0x%08lx r2=0x%08lx r3=0x%08lx r4=0x%08lx r5=0x%08lx r6=0x%08lx r7=0x%08lx\n",
             (unsigned long)m->arm_r0, (unsigned long)m->arm_r1,
             (unsigned long)m->arm_r2, (unsigned long)m->arm_r3,
             (unsigned long)m->arm_r4, (unsigned long)m->arm_r5,
             (unsigned long)m->arm_r6, (unsigned long)m->arm_r7);
        /* ★★ pc 常落在共享库里（PLT 解析后调用点信息已丢），必须**点名是哪个库的哪个函数**：
         *    - pc 可能是 libc/ld.so，也可能是 shim 自己 ⇒ 不点名就只能靠猜（已浪费过时间）。
         *    - 用 `dladdr` 解析：它查 **guest 自己的 link_map**，对 guest 地址是正确的；
         *      容器里读 /proc/self/maps 会拿到**宿主**的映射，可能对不上，故不作首选。
         *    - `dladdr` 声明为 **weak**：zig 的 arm-linux-gnueabihf 目标不一定自带 libdl 的导入库，
         *      弱符号可保证**链接期零风险**（运行时若未解析则为 NULL，先判空再调用）。
         *    - `signal(sig, SIG_DFL)` 必须**先**设，否则下面读 pc 处指令若也缺页会递归进处理器。 */
        signal(sig, SIG_DFL);
        {
            void *weak_dladdr = (void *)dladdr;          /* 弱引用：可能为 NULL */
            unsigned long q[2];
            int k;
            q[0] = (unsigned long)m->arm_pc;             /* 出错点 */
            q[1] = (unsigned long)m->arm_lr;             /* 调用者返回点 */
            if (weak_dladdr) {
                /* ① pc / lr 归属：`lr` 常能直接点名**调用者函数**（pc 可能只到库内某函数） */
                for (k = 0; k < 2; k++) {
                    struct { const char *fname; void *fbase; const char *sname; void *saddr; } di;
                    di.fname = 0; di.fbase = 0; di.sname = 0; di.saddr = 0;
                    if (dladdr((void *)q[k], &di) && di.fname) {
                        note("[shim]   %-11s 0x%08lx -> %s + 0x%lx   符号=%s\n",
                             k ? "lr(调用者)" : "pc(出错点)", q[k], di.fname,
                             q[k] - (unsigned long)di.fbase,
                             di.sname ? di.sname : "(无)");
                    } else {
                        note("[shim]   %-11s 0x%08lx -> dladdr 未解析\n",
                             k ? "lr(调用者)" : "pc(出错点)", q[k]);
                    }
                }
                /* ② 栈回溯：sp 起 11 个字里凡能被 dladdr 解析的都列出来
                 *    —— 这就是一条"穷人版 backtrace"，不需要 gdb，且在真崩溃时依然拿得到。 */
                {
                    unsigned long *sp = (unsigned long *)(unsigned long)m->arm_sp;
                    note("[shim]   栈回溯（sp+0..sp+40；仅列可解析项）:\n");
                    for (k = 0; k < 11; k++) {
                        struct { const char *fname; void *fbase; const char *sname; void *saddr; } di;
                        unsigned long v = sp[k];
                        if (v < 0x10000) continue;
                        di.fname = 0; di.fbase = 0; di.sname = 0; di.saddr = 0;
                        if (dladdr((void *)v, &di) && di.fname) {
                            note("[shim]     [sp+%2d] = 0x%08lx -> %s + 0x%lx  %s\n",
                                 k * 4, v, di.fname, v - (unsigned long)di.fbase,
                                 di.sname ? di.sname : "");
                        }
                    }
                }
            } else {
                note("[shim]   dladdr 不可用（pc=0x%08lx lr=0x%08lx）\n", q[0], q[1]);
            }
        }
        note("[shim]   故障指令 @pc = 0x%08x   [pc-4]=0x%08x  [pc+4]=0x%08x\n",
             *(volatile unsigned int *)(unsigned long)m->arm_pc,
             *(volatile unsigned int *)(unsigned long)(m->arm_pc - 4),
             *(volatile unsigned int *)(unsigned long)(m->arm_pc + 4));
        return;                     /* 返回后同一指令再次缺址 ⇒ 真正崩掉（保持原语义）*/
    }

    g_faults++;
    ins = *(volatile unsigned int *)m->arm_pc;
    off = (unsigned int)(addr - (unsigned long)g_sfc_base);
    regs_load(m, R);

    /* --- 块传送 LDM/STM（bits 27..25 == 100）：设备侧用不到，读到就给 0 --- */
    if ((ins & 0x0E000000u) == 0x08000000u) {
        unsigned int rl = ins & 0xffffu, i;
        if (ins & (1u << 20)) {
            for (i = 0; i < 16; i++) {
                if ((rl >> i) & 1u) {
                    R[i] = 0;
                }
            }
        }
        g_unhandled++;
        regs_store(m, R);
        m->arm_pc += 4;
        return;
    }

    /* --- 半字 / 有符号字节传送（bit4=1 且 bits27..25==000）--- */
    if ((ins & 0x0E000000u) == 0 && (ins & 0x90u) == 0x90u) {
        L = (ins >> 20) & 1u; Rn = (ins >> 16) & 0xFu; Rd = (ins >> 12) & 0xFu;
        P = (ins >> 24) & 1u; U = (ins >> 23) & 1u; W = (ins >> 21) & 1u;
        size = ((ins >> 5) & 1u) ? 2u : 1u;          /* H=1 → 半字；H=0（S=1）→ 有符号字节 */
        wb = (P == 0) || W;
        if (L) {
            v = sfc_dev_read(off, size);
            if ((ins >> 6) & 1u) {                   /* S=1：LDRSB / LDRSH → 符号扩展 */
                if (size == 2u) {
                    v = (unsigned long)(long)(short)(v & 0xffffu);
                } else {
                    v = (unsigned long)(long)(signed char)(v & 0xffu);
                }
            }
            R[Rd] = v;
        } else {
            v = R[Rd] & (size == 2 ? 0xffffu : 0xffu);
            sfc_dev_write(off, v, size);
        }
        if (wb && Rn != 15) {
            unsigned long doff = (ins & (1u << 22))
                               ? R[ins & 0xFu]                                  /* 寄存器偏移 */
                               : (unsigned long)(((ins >> 4) & 0xF0u) | (ins & 0xFu)); /* imm4H:imm4L */
            R[Rn] = U ? R[Rn] + doff : R[Rn] - doff;
        }
        regs_store(m, R);
        m->arm_pc += 4;
        return;
    }

    /* --- 单寄存器传送（bits 27..26 == 01）--- */
    if ((ins & 0x0C000000u) != 0x04000000u) {
        g_unhandled++;
        note("[shim] SFC: 未识别指令 @0x%08x = 0x%08x（off=0x%x）—— 跳过\n",
             (unsigned int)m->arm_pc, ins, off);
        m->arm_pc += 4;
        return;
    }

    I = (ins >> 25) & 1u; P = (ins >> 24) & 1u; U = (ins >> 23) & 1u;
    size = (ins & (1u << 22)) ? 1u : 4u;             /* B=1 → 字节 */
    W = (ins >> 21) & 1u; L = (ins >> 20) & 1u;
    Rn = (ins >> 16) & 0xFu; Rd = (ins >> 12) & 0xFu;
    wb = (P == 0) || W;

    if (L) {
        v = sfc_dev_read(off, size);
        mask = (size == 4) ? 0xffffffffu : 0xffu;
        R[Rd] = v & mask;
    } else {
        v = R[Rd] & ((size == 4) ? 0xffffffffu : 0xffu);
        sfc_dev_write(off, v, size);
    }

    if (wb && Rn != 15) {                            /* 写回（P=0 或 W=1）*/
        unsigned long doff;
        if (I) {
            doff = (unsigned long)(ins & 0xFFFu);
        } else {
            unsigned int rm = ins & 0xFu, sh = (ins >> 7) & 0x1Fu, ty = (ins >> 5) & 3u;
            doff = R[rm];
            if (sh) {
                if (ty == 0)      doff = (doff << (32 - sh)) >> (32 - sh);
                else if (ty == 1) doff = (doff >> sh) | (doff << (32 - sh));
                else if (ty == 2) doff = (unsigned long)((long)doff >> sh);
                else              doff = (doff >> sh) | ((doff & 1u) ? (0xFFFFFFFFu << (32 - sh)) : 0);
            }
        }
        R[Rn] = U ? R[Rn] + doff : R[Rn] - doff;
    }

    if (L && Rd == 15) {                             /* 读入 pc = 分支：不再 +4 */
        regs_store(m, R);
        return;
    }
    regs_store(m, R);
    m->arm_pc += 4;
}

static void sfc_disarm(void)
{
    g_sfc_base = 0;
    g_sfc_pagelen = 0;
}

/* 装配设备：把刚映射到的页设成 PROT_NONE，并装 SIGSEGV/SIGBUS 处理器 */
/* ★★ 崩溃报告器**提前装配**（本轮补的仪器缺口）----------------------------------
 * 实测事故（2026-09-17 场景 E）：重建产物在解析 `setting.xml`（mini-XML）时 SIGSEGV，
 *   stderr 里**只有 qemu 的 `uncaught target signal 11` 一行，没有任何现场** ——
 *   因为处理器原本只在 `sfc_arm_device()`（= `spi_driver_init` 里 mmap SFC 页时）才装，
 *   而这次崩溃发生在**那之前** ⇒ pc/lr/栈全丢，只能靠猜（浪费了一轮 CI 与大量时间）。
 * 修法：在 constructor（早于 main）就把 SIGSEGV/SIGBUS 处理器装上；
 *   此时 `g_sfc_base == NULL`，任何缺页都会走"真崩溃"分支 ⇒ **任何位置的崩溃都能自报现场**。
 *   `sfc_arm_device()` 之后仍会再装一次（幂等），行为不变。 */
static void shim_arm_crash_reporter(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = sfc_fault;
    sa.sa_flags = SA_SIGINFO | SA_RESTART;
    sigemptyset(&sa.sa_mask);
    (void)sigaction(SIGSEGV, &sa, NULL);
    (void)sigaction(SIGBUS, &sa, NULL);
}

static void sfc_arm_device(void *p, size_t len)
{
    unsigned long page = 0x1000;

    shim_arm_crash_reporter();          /* 幂等：constructor 已装过，这里确保仍生效 */

    g_sfc_base = (volatile unsigned char *)p;
    g_sfc_pagelen = (unsigned int)(((len + page - 1) / page) * page);
    memset(g_shadow, 0, sizeof(g_shadow));
    g_prepared = 0;
    g_opcode = 0;
    g_addr = 0;
    if (syscall(__NR_mprotect, p, (size_t)g_sfc_pagelen, PROT_NONE) != 0) {
        note("[shim] SFC: mprotect(PROT_NONE) 失败 errno=%d — 退回静态种子页\n", errno);
        g_sfc_base = 0;
        g_sfc_pagelen = 0;
        sfc_seed(p, len);
        return;
    }
    note("[shim] SFC 设备仿真已装配 base=%p len=0x%x（每次寄存器访问由 SIGSEGV 处理器应答）\n",
         (void *)p, g_sfc_pagelen);
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
    /* ---- ②b 场景 B：key2 注入（让「资源包可打开」这条真机路径进得来）---------------
     * 背景（P5 实测 + 静态取证）：
     *   · 工厂与重建**全文件都搜不到 `PK\x05\x06`/`PK\x03\x04`/`PK\x01\x02` 字节串**
     *     ⇒ ZIP 签名不在 .rodata，只能在运行期内存里；
     *   · `unzlocal_SearchCentralDir`（工厂 0x10eb0）逐字节比对的正是**全局 `key2`**
     *     （@0x3E190C，`.bss` 28 B，symtab 有符号；Ghidra 全 812 个函数里只有 3 个 zip 函数读它）；
     *   · 而 **整个 rkgame + driver.so 都没有任何 key2 的写入者**（driver.so 里连
     *     0x3E190C 常量与 PK 字节都没有 ⇒ 不是"外部模块填的"）。
     *   ⇒ 默认环境下 key2 全 0 ⇒ 搜索找的是「4 个 0x00」而**不是** EoCD 签名 ⇒
     *     工厂与重建都打不开 ui_cn.zip ⇒ 双双停在 `mui_setting` 的 NULL+4 崩溃。
     *     于是**整个菜单层（mui 42 函数 / 70396 B = 重构量的 57%）永远跑不到**。
     *
     * 本开关做的事：把厂商签名表按最自然的排布写进 key2，让"资源包可打开"这条路径
     * 在两**侧都以完全相同的方式**变得可观测（差分依旧公平：两侧加载同一份 shim、
     * 同一份注入值）。
     *   · CGM_KEY2_SEED=1  → key2[0..3]="PK\5\6" [4..7]="PK\6\6"
     *                        [8..11]="PK\3\4" [12..15]="PK\1\2"
     *   · 未设 / =0        → 不注入（= 场景 A，与工厂默认态一致）
     * ★ 地址 0x003E190C 是**常量**：guest 非 PIE（gdb 已断言"地址即链接地址"），
     *   且两侧布局账本（ledger/factory_globals.tsv）已核对该全局同址。
     * ★ 只在显式开启时写内存；若假设不成立会立刻在 constructor 里 SIGSEGV（可见、可退）。 */
    /* ★ 先把崩溃报告器装上（早于 main）：任何位置的崩溃都必须能自报 pc/lr/栈。
     *   这条是**仪器纪律**，不是可选项 —— 缺了它，本轮多花了一整轮 CI 才定位到崩点。 */
    shim_arm_crash_reporter();
    {
        const char *fc = getenv("CGM_FOPEN_CHAIN");
        if (fc != NULL && fc[0] == '2') {
            g_fopen_chain = 2;
        }
    }
    shim_resolve_fopen();
    g_io_trace = (getenv("CGM_IO_TRACE") != NULL
                  && getenv("CGM_IO_TRACE")[0] != '\0'
                  && getenv("CGM_IO_TRACE")[0] != '0');
    g_key2_hook = (getenv("CGM_KEY2_HOOK") != NULL
                   && getenv("CGM_KEY2_HOOK")[0] != '\0'
                   && getenv("CGM_KEY2_HOOK")[0] != '0');
    {
        const char *k2 = getenv("CGM_KEY2_SEED");
        if (k2 != NULL && k2[0] != '\0' && k2[0] != '0') {
            /* ★★ 2026-09-17 修正（关键）：`unzlocal_SearchCentralDir` 只在 `key2[0..3]` 与
             *   `key2[4..7]` 两个 4 字节组上比对（反编译第 66..69 行），对应上游 Wischik 的
             *   两个字面量 `PK\x05\x06`（EoCD）与 **`PK\x07\x08`**（spanned）。
             *   本开关上一版写的是 `PK\x06\x06` ⇒ 注入的字节本身就不可能是签名 ⇒
             *   场景 B「注入后行为毫无变化」**是错的注入值造成的假阴性**，不能作为归因依据。 */
            static const unsigned char sig[16] = {
                'P', 'K', 0x05, 0x06, 'P', 'K', 0x07, 0x08,
                'P', 'K', 0x03, 0x04, 'P', 'K', 0x01, 0x02
            };
            volatile unsigned char *p = (volatile unsigned char *)(unsigned long)0x003E190Cu;
            int i;
            for (i = 0; i < 16; i++) {
                p[i] = sig[i];
            }
            g_key2_seeded = 1;
            /* ★ 回读校验：证明"写到了我们以为的地址上"（而不是写到某块无关的可写内存）。
             *   若这里读回的不是 PK 值，说明 0x3E190C 在运行期并非 key2 所在 ⇒ 注入无效。 */
            note("[shim] key2 seeded @0x3E190C = PK\\x05\\x06 PK\\x07\\x08 PK\\x03\\x04 PK\\x01\\x02"
                 "  回读=%02x %02x %02x %02x %02x %02x %02x %02x（场景 B：让 ui_cn.zip 可打开）\n",
                 (unsigned)p[0], (unsigned)p[1], (unsigned)p[2], (unsigned)p[3],
                 (unsigned)p[4], (unsigned)p[5], (unsigned)p[6], (unsigned)p[7]);
        }
    }

    shim_poison_walk(POISON_DEPTH);

    /* 证据行（默认静默；把 CGM_SHIM_VERBOSE=1 经 qemu -E 传进 guest 才输出）：
     * 让我们能从采集到的 stderr 里确认"投毒真的跑了、覆盖多少字节"。
     * ★ 用 write(2,…) 而不是 printf：constructor 早于 stdio 完全就绪，避免缓冲陷阱。 */
    if (getenv("CGM_SHIM_VERBOSE") != NULL) {
        char buf[128];
        int n = snprintf(buf, sizeof(buf),
                         "[shim] active: poison=%u KiB(byte=0x%02X) sfc_seed@0x%08lX=%s\n",
                         (unsigned)(POISON_FRAME * POISON_DEPTH / 1024u),
                         (unsigned)POISON_BYTE, SFC_REG_OFF,
                         "on");
        if (n > 0) {
            (void)write(2, buf, (size_t)(n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1));
        }
    }
}

/* ---- ② 物理寄存器映射 → 匿名零页 ------------------------------------- */

/* ★★ SFC（SPI Flash 控制器）寄存器页：把「传输永不完成」改成「传输完成、数据为 0」。
 *
 * 为什么必须做（P5 实测根因，有源码级证据）：
 *   `src/proprietary/flash/FUN_002c43f8_sfc_init.c` 对 SFC 寄存器做
 *       mmap(NULL, 0x400, RW, MAP_SHARED, fd, 0x10208000);
 *   而 `sfc_request()`（0x2c39f0）的两条读路径都以**状态寄存器**为闸门：
 *       · 字循环：`uVar1 = (reg[8] & 0x1fffff) >> 16; if (uVar1 == 0) { usleep(1); …超时 }`
 *       · 尾字节：`if ((reg[8] & 0x1f0000) == 0) { …超时 }`
 *   匿名零页里 `reg[8] == 0` ⇒ **永远超时** ⇒ 数据路径整段不执行、缓冲区**不被写入**
 *   ⇒ 上层 `spi_driver_init()` 打印的 `CRC32:[sp+8]` / `Update time:[sp+12]` 读的是链上更早
 *   代码留下的确定值；它对本二进制确定（控制组两遍一致），但两份二进制**必然不同**
 *   ⇒ 变成一条「看起来像实现差异」的假分歧（实测：`CRC32:0000` vs `0003`）。
 *   ★ 佐证：栈投毒加深到 766 KiB 后这两个值**完全不变** ⇒ 不是随机栈残留，是被写过的内存。
 *
 * 做法：只在**这一个**物理偏移上把匿名页预置成完成态：
 *       reg[4] (0x10)   = 0           不忙
 *       reg[8] (0x20)   = 0x00010000  已收到 1 个 word（bits16..20 ≠ 0 ⇒ 传输完成）
 *       reg[9] (0x24)   = 0           不忙（末尾等待循环立即通过）
 *       reg[0x42] (0x108) = 0         数据寄存器 = 0（假硬件没有真实闪存数据）
 *   ⇒ 传输立即「完成」、写进缓冲区的字节全是 0 ⇒ 两侧读到同样的 0。
 *   副作用（好）：不再有 10001 次 usleep 超时 ⇒ guest 明显更快。
 *
 * ★ 只认这一个偏移；其余物理映射仍是纯零页（保持「设备不存在」语义，避免误伤别的外设）。
 */

static void sfc_seed(void *p, size_t len)
{
    volatile unsigned int *r = (volatile unsigned int *)p;

    if (len < SFC_REG_MIN) {
        return;
    }
    r[4] = 0u;                    /* 忙标志：不忙 */
    r[8] = 0x00010000u;           /* 状态：传输完成（1 word） */
    r[9] = 0u;                    /* 状态：不忙 */
    r[0x42] = 0u;                 /* 数据寄存器：0 */
}

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
            if (uoff == SFC_REG_OFF) {
                if (!g_mode_ready) {           /* CGM_SFC_MODE=seed 可回退旧行为 */
                    const char *md = getenv("CGM_SFC_MODE");
                    g_sfc_mode_device = !(md && md[0] == 's' && md[1] == 'e');
                    g_mode_ready = 1;
                }
                if (g_sfc_mode_device) {
                    sfc_arm_device(p, len);    /* 变成"有状态设备"（见 ③ 段长注释）*/
                } else {
                    sfc_seed(p, len);          /* 旧行为：静态种子页 */
                }
            }
            return p;
        }
        /* 匿名映射也失败 ⇒ 退回原语义，让上层自己去报错 */
    }
    return sys_mmap2(addr, len, prot, flags, fd, uoff);
}

/* ---- ④ 崩溃定位探针：munmap 处的状态快照 ---------------------------- */
/* 来历（P5 最后一处未解分歧）：行为差分只剩「重建侧少打印两行
 *   `find *_driver_deinit process fail`」。已有事实：
 *     · 重建侧 stdout 有 ROM 行、exit=139，工厂侧多两行后才崩；
 *     · `-strace` 显示重建侧在 `close(sfc fd)` 之后、`sfc_uninit()` 的
 *       `munmap(…, 0x400)` **之前**就崩了；
 *     · `-d in_asm` 尾部停在 `spi_driver_init` 的 `pop {…, pc}`（说明它**已返回**）；
 *     · si_addr=0xf2280500 落在"已翻译代码"里 ⇒ 老块不会再被 in_asm 记录。
 *   于是只剩两个候选：
 *     ① 返回地址被破坏 ⇒ `pop {…,pc}` 跳到坏地址（那样就永远回不到 main，也就不会有 munmap）；
 *     ② 回到 main 后 `dlsym(handle, "sound_driver_deinit")` 的 `handle` 是垃圾
 *        （工厂里 `handle` 位于 `.bss`，值为 0）。
 *   本探针把这两条路都变成**可观测事件**：
 *     · 若重建侧**看不到** sfc_uninit 的 munmap 行 ⇒ ① 成立；
 *     · 若看得到、且 `handle` 不是 0 ⇒ ② 成立。
 *
 *   ★ 便利条件：guest 是**非 PIE**，`.bss` 就加载在链接地址上 ⇒ shim 可直接读
 *     `*(void **)0x003b21c8` 拿到那个 `handle`（两侧都有这个符号，地址相同）。
 *   两侧加载同一份 shim ⇒ 差分依然公平。 */

#define GUEST_ADDR_handle    0x003b21c8u   /* run_process/InitDisplay/InitSound/DeinitDisplay 引用的 handle */
#define GUEST_ADDR_g_sfc_reg 0x003cfab8u

static void note(const char *fmt, ...)
{
    char buf[256];
    va_list ap;
    int n;

    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0) {
        (void)write(2, buf, (size_t)(n < (int)sizeof(buf) ? n : (int)sizeof(buf) - 1));
    }
}

int munmap(void *addr, size_t len)
{
    long r;

    /* 设备页被解除映射后必须"撤防"，否则处理器会把普通缺址当成设备访问 */
    if (g_sfc_base && (unsigned long)addr >= (unsigned long)g_sfc_base
        && (unsigned long)addr < (unsigned long)g_sfc_base + g_sfc_pagelen) {
        note("[shim] SFC 设备撤防（munmap %p）：faults=%lu cmds=%lu unhandled=%lu\n",
             addr, g_faults, g_cmds, g_unhandled);
        sfc_disarm();
    }
    r = syscall(__NR_munmap, addr, len);

    /* 只报告 sfc_init 那一次映射（0x400），避免噪声 */
    if (len == 0x400) {
        note("[shim] munmap(addr,0x400)=%ld handle=%p g_sfc_reg=%p\n",
             r,
             *(void *volatile *)GUEST_ADDR_handle,
             *(void *volatile *)GUEST_ADDR_g_sfc_reg);
    }
    return (int)r;
}
