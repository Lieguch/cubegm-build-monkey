/* abi_probe.c — B6 ABI 边界最小裁决探针（**一次性诊断**，不进交付产物）
 *
 * 目的（R219 P1 / R220-R221 待办）
 * ---------------------------------------------------------------
 * B6 `frame_hash` 恒为全零基线 `b5449dc5`。已证伪的两条解释：
 *   ① 「driver 走 hcge 命令队列」—— R162 实测本机 driver.so 零 hcge_* 符号，走标准 DRM/KMS；
 *   ② 「shim 拦不到 MAP_DUMB offset」—— R189 已加 `drm_stub_fb_lookup_by_addr` 多实体反查，
 *      但 R221 云上实测 `fb_lookup HIT` **仍零行** ⇒ 不是"没命中"，是**根本没走 glibc mmap**。
 *
 * 根因（R137 已定案、R221 复证）：driver.so 的 `mmap` 是**自封定义**
 * （`.symtab` DEFINED `mmap@@GLIBC_2.4`，非 UNDEF）⇒ 直接发 `SVC` 绕过 glibc 包装
 * ⇒ LD_PRELOAD 的 shim 物理上拦不到它的私有画布 ⇒ 像素从不落进桩实体。
 *
 * ⇒ 观测点必须上移到 **ABI 边界**：driver.so 导出、rkgame 经 `dlsym` 取得的
 *   `video_driver_disp_frame(data, w, h, pitch)`。这是 rkgame 侧唯一能看见"真实帧内容"的位置
 *   （`dispFlip` → `(*video_driver_frame)(param_1, param_2, param_3, param_4)`，
 *     见 src/proprietary/hw/FUN_0000d8e4_dispFlip.c:43）。
 *
 * 判据（二选一，直接决定 B6 补强是否值得做）
 * ---------------------------------------------------------------
 *   A. 入参 hash 非全零 且 nz>0  ⇒ rkgame 确实在出非零画面
 *      ⇒ ABI 边界哈希可作 B6 的**真判据**，接进 behav_diff.py。
 *   B. 入参 hash == 全零 且 nz==0 ⇒ qemu 沙箱里菜单本就黑屏
 *      ⇒ B6 诚实红是**环境天花板**（不是观测点缺陷），停手观测点、归档结论。
 *
 * 递归安全 + RTLD_NEXT 语义（本文件 wrap 了 dlsym，这是唯一的实现风险）
 * ---------------------------------------------------------------
 *   取真 `dlsym` **必须**用 `dlvsym`（符号名不同 ⇒ 不会回到我们的实现 ⇒ 无递归）。
 *   两者都取不到 ⇒ 本 dlsym 返回 0（**fail-open 会掩盖问题**，所以选择"大声失败"：
 *   rkgame 会在 InitDisplay 打印 "can't find ... proc" 而不是静默跑错）。
 *
 *   ★★ R221 实测踩到的坑（exit=139，必须记住）：
 *   本 so 与 guest_shim.so **叠加**注入时，guest_shim 内部的
 *   `dlsym(RTLD_NEXT, "strcmp")` 会落到**本实现**。
 *   而 `RTLD_NEXT` 的语义是「从**调用者的** link_map 之后继续找」——
 *   一旦把调用转发进另一个 DSO，**调用者上下文已经变了** ⇒ RTLD_NEXT 解析错位
 *   ⇒ 返回 0 ⇒ guest_shim 拿到 NULL 的 real_strcmp ⇒ SIGSEGV（实测 exit=139、stdout 0 行）。
 *   ⇒ 修法：**handle == RTLD_NEXT 时改用 RTLD_DEFAULT**（全局查找）。
 *     对 guest_shim 的实际用途（strcmp/fopen/fseek/fread 的真实现）语义等价
 *     —— 这些符号我们**没有**包装，所以 RTLD_DEFAULT 拿到的必然是 libc 的真函数。
 *   ⇒ 另加 `CGM_ABI_PROBE=1` 显式开关（默认不 hook），避免影响其它场景。
 *
 * 编译（钉设备 glibc 2.29，与 build_guest_shim.sh 同口径）
 * ---------------------------------------------------------------
 *   zig cc -target arm-linux-gnueabihf.2.29 -mfloat-abi=hard -mfpu=neon \
 *       -shared -fPIC -O2 -w abi_probe.c -o abi_probe.so
 *
 * 用法：与 guest_shim.so 叠加注入，**本探针在前**（先解析 dlsym）：
 *   LD_PRELOAD=/path/abi_probe.so:/path/guest_shim.so
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <unistd.h>

typedef void *(*dlsym_t)(void *, const char *);
/* disp_frame 的 4 参签名来自 dispFlip 反汇编：data / width / height / pitch(字节) */
typedef int (*disp_frame_t)(void *, unsigned, unsigned, unsigned);

static void emit(const char *s, unsigned n);   /* 前置声明：constructor 里要用 */
static unsigned slen(const char *s);

/* ★ 消息常量化：长度一律用 slen() 计算，**不再手写数字**。
 *   手写长度的真实事故（R221）：`emit("...[=1)\n", 34)` 实际 37 字节
 *   ⇒ 少了 `\n` ⇒ 与下一行 `[drmstub]` 粘连成一行 ⇒ behav_capture 产出的 JSON
 *     出现控制字符（`Invalid control character at line 77`）⇒ 采集直接失败。 */
#define MSG_ENABLED "[abiprobe] enabled (CGM_ABI_PROBE=1)\n"
#define MSG_FATAL   "[abiprobe] FATAL: cannot resolve real dlsym\n"
#define MSG_HOOKED  "[abiprobe] HOOKED video_driver_disp_frame -> wrapper\n"

static dlsym_t      g_real_dlsym;
static disp_frame_t g_real_disp;
static int          g_calls;
static int          g_printed;
static int          g_hooked_logged;
static int          g_probe_on;
static unsigned     g_last_hash;      /* 上次已判定的哈希（变化检测）*/

/* 显式开关：只有 CGM_ABI_PROBE=1 时才 hook（默认完全透明）。
 * ★ 为什么默认关闭：本 so 会覆盖全局 `dlsym`，只要加载就改变符号解析路径；
 *   放进"只做一次裁决"的场合，必须能一键关掉，避免将来误带进正式差分。 */
__attribute__((constructor))
static void abi_probe_init(void)
{
    extern char *getenv(const char *) __attribute__((weak));
    const char *v;
    if (getenv == 0) return;
    v = getenv("CGM_ABI_PROBE");
    if (v != 0 && v[0] == '1') {
        g_probe_on = 1;
        emit(MSG_ENABLED, slen(MSG_ENABLED));
    }
}

/* ---- 极简输出（零 stdio 依赖：只用 write(2)，与桩同风格）---- */
static unsigned slen(const char *s) { unsigned n = 0; while (s[n]) n++; return n; }
static char *put_s(char *q, const char *s) { while (*s) *q++ = *s++; return q; }
static char *put_u(char *q, unsigned v)
{
    char tmp[12]; int n = 0;
    if (!v) { *q++ = '0'; return q; }
    while (v) { tmp[n++] = (char)('0' + (v % 10u)); v /= 10u; }
    while (n) *q++ = tmp[--n];
    return q;
}
static char *put_x8(char *q, unsigned v)
{
    const char *hx = "0123456789abcdef"; int i;
    for (i = 7; i >= 0; i--) q[i] = hx[v & 0xfu], v >>= 4;
    return q + 8;
}
/* 自己的字符串比较（不依赖 libc 的 strcmp，避免被其他 shim 改写） */
static int seq(const char *a, const char *b)
{
    while (*a && *a == *b) { a++; b++; }
    return (int)(unsigned char)*a - (int)(unsigned char)*b;
}

static unsigned fnv1a(const unsigned char *p, unsigned n)
{
    unsigned h = 2166136261u, i;
    for (i = 0; i < n; i++) { h ^= p[i]; h *= 16777619u; }
    return h;
}

static void emit(const char *s, unsigned n) { (void)write(2, s, n); }
/* 探针主体：对一帧入参缓冲取哈希 + 统计前 4 KiB 非零字节数
 * ★ 打印策略：前 6 帧必打；之后**只在哈希变化时**打（上限 64 行）——
 *   既保证"画面静止时不刷屏"，又不会漏掉按键/动画引起的画面变化。
 *   （若只打前 6 帧，`behav_capture.sh` 取"最后一条"时会拿到初始黑屏帧，
 *     从而漏判"按键改变了画面"这个最关键的行为差异。） */
static int probe_disp_frame(void *data, unsigned w, unsigned h, unsigned pitch)
{
    g_calls++;

    if (data != 0) {
        unsigned long bytes = (unsigned long)h * (unsigned long)pitch;
        unsigned lim, nz = 0, i, hh;
        int changed;
        char line[192], *q = line;

        if (bytes > (64UL << 20)) bytes = (64UL << 20);   /* cap 64 MiB，防越界读 */
        hh = fnv1a((const unsigned char *)data, (unsigned)bytes);
        changed = (hh != g_last_hash);
        if (changed) g_last_hash = hh;

        if (g_printed < 6 || (changed && g_printed < 64)) {
            lim = (unsigned)(bytes < 4096UL ? bytes : 4096UL);
            for (i = 0; i < lim; i++) if (((const unsigned char *)data)[i]) nz++;

            g_printed++;
            q = put_s(q, "[abiprobe] disp#");
            q = put_u(q, (unsigned)g_calls);
            q = put_s(q, " data=");
            q = put_x8(q, (unsigned)(unsigned long)data);
            q = put_s(q, " w=");    q = put_u(q, w);
            q = put_s(q, " h=");    q = put_u(q, h);
            q = put_s(q, " pitch=");q = put_u(q, pitch);
            q = put_s(q, " bytes=");q = put_u(q, (unsigned)bytes);
            q = put_s(q, " hash="); q = put_x8(q, hh);
            q = put_s(q, " nz4k="); q = put_u(q, nz);
            *q++ = '\n';
            emit(line, (unsigned)(q - line));
        }
    }

    if (g_real_disp != 0) return g_real_disp(data, w, h, pitch);
    return 0;
}

void *dlsym(void *handle, const char *symbol)
{
    void *r;

    if (g_real_dlsym == 0) {
        /* 真 dlsym 只能经 dlvsym 取（同名会递归）。RTLD_NEXT 在**本 so 的**上下文里
         * 指向「abi_probe 之后」的 so，而 glibc 的 dlsym 一定在 libc/libdl 里 ⇒ 语义成立。 */
        extern void *dlvsym(void *, const char *, const char *) __attribute__((weak));
        if (dlvsym != 0)
            g_real_dlsym = (dlsym_t)dlvsym(RTLD_NEXT, "dlsym", "GLIBC_2.4");
        if (g_real_dlsym == 0 && dlvsym != 0)
            g_real_dlsym = (dlsym_t)dlvsym(RTLD_DEFAULT, "dlsym", "GLIBC_2.4");
        if (g_real_dlsym == 0) {
            /* 大声失败：rkgame 会打印 "can't find ... proc"，不会静默跑错 */
            emit(MSG_FATAL, slen(MSG_FATAL));
            return (void *)0;
        }
    }

    /* ★★ 本探针**必须编进 guest_shim 同一个 DSO**（见 build_guest_shim.sh 的说明）。
     *   同一 DSO 时，`dlsym(RTLD_NEXT,..)` 的调用者 link_map 与真 dlsym 的返回地址同属一个 so
     *   ⇒ glibc 从本 so **之后**继续找（libc）⇒ 语义天然正确、不递归。
     *   ★ 反面：若做成独立 .so 叠加，转发后调用者上下文改变 ⇒ 先命中 guest_shim 自己的
     *     fopen/fseek ⇒ 无限递归 ⇒ SIGSEGV（R221 实测 exit=139 两次复现）。
     *   ⇒ 因此这里**不得**把 RTLD_NEXT 改写成 RTLD_DEFAULT（那在同一 so 场景会自命中）。 */
    r = g_real_dlsym(handle, symbol);

    /* 只在显式开关下 hook（默认不干扰）*/
    if (r != 0 && symbol != 0
        && g_probe_on && seq(symbol, "video_driver_disp_frame") == 0) {
        if (g_real_disp == 0) g_real_disp = (disp_frame_t)r;
        if (!g_hooked_logged) {
            g_hooked_logged = 1;
            emit(MSG_HOOKED, slen(MSG_HOOKED));
        }
        return (void *)probe_disp_frame;
    }
    return r;
}
