/* ============================================================
 * cgm_diag.c —— 设备端诊断仪核心实现
 *
 * 铁律：本文件**只允许**通过 syscall() 与外界交互。
 *       绝不调用 open/printf/malloc/... —— 那些可能被 --wrap 重定向 ⇒ 无限递归。
 * ============================================================ */
#include "cgm_diag.h"

#include <stdarg.h>
#include <stdint.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <unistd.h>

#ifndef SYS_mkdirat
#define SYS_mkdirat __NR_mkdirat
#endif

/* ---------------- 极简 syscall 封装 ---------------- */
static long sc3(long n, long a, long b, long c) { return syscall(n, a, b, c); }
static long sc4(long n, long a, long b, long c, long d) { return syscall(n, a, b, c, d); }

static int  sys_open(const char *p, int fl, int mode) {
    return (int)sc4(SYS_openat, -100 /*AT_FDCWD*/, (long)p, fl, mode);
}
static int  sys_close(int fd) { return (int)sc3(SYS_close, fd, 0, 0); }
static int  sys_mkdir1(const char *p) { return (int)sc3(SYS_mkdirat, -100, (long)p, 0755); }

static void wraw(int fd, const void *p, unsigned n) {
    if (fd < 0) return;
    const char *c = (const char *)p;
    while (n) {
        long r = sc3(SYS_write, fd, (long)c, (long)n);
        if (r <= 0) return;
        c += r; n -= (unsigned)r;
    }
}
static void wstr(int fd, const char *s) { unsigned n = 0; while (s[n]) n++; wraw(fd, s, n); }

/* ---------------- 全局状态 ---------------- */
static int      g_booted;
static int      g_lvl = CGM_LVL_IO;
static int      g_logfd  = -1;
static int      g_snapfd = -1;
static int      g_framefd = -1;
static unsigned g_logbytes;
static unsigned g_rot;

static cgm_frame_t g_ring[CGM_RING_FRAMES];
static volatile unsigned g_rpos;      /* 单调递增；下标 = g_rpos & (N-1) */
static volatile unsigned g_depth;
static volatile unsigned g_ms;
static unsigned g_ms_tick;
static unsigned g_last_snap;
static unsigned g_last_sum;
static unsigned g_nframe;
static unsigned g_nopen;
static unsigned g_ndlopen;
static unsigned g_nioc;

/* 计数统计（summarize 用） */
#define CGM_CTR_N 48
static char     g_ctr_name[CGM_CTR_N][20];
static unsigned g_ctr_val[CGM_CTR_N];
static int      g_ctr_used;

static void ctr(const char *nm) {
    for (int i = 0; i < g_ctr_used; i++)
        if (g_ctr_name[i][0] == nm[0] && g_ctr_name[i][1] == nm[1] && g_ctr_name[i][2] == nm[2]) {
            unsigned j = 3; int same = 1;
            for (; nm[j] || g_ctr_name[i][j]; j++)
                if (nm[j] != g_ctr_name[i][j]) { same = 0; break; }
            if (same) { g_ctr_val[i]++; return; }
        }
    if (g_ctr_used < CGM_CTR_N) {
        int i = g_ctr_used++;
        unsigned j = 0;
        for (; nm[j] && j < 19; j++) g_ctr_name[i][j] = nm[j];
        g_ctr_name[i][j] = 0; g_ctr_val[i] = 1;
    }
}

/* ---------------- 极简格式化（不用 libc） ---------------- */
static char *p_uint(char *o, unsigned long v, int base, int zero, int width) {
    char t[24]; int n = 0;
    if (!v) t[n++] = '0';
    while (v) { unsigned d = (unsigned)(v % base); t[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10); v /= base; }
    while (n < width) t[n++] = '0';
    if (!zero && width > n) { /* 空格填充在下面统一处理 */ }
    for (int i = n - 1; i >= 0; i--) *o++ = t[i];
    return o;
}
static char *p_int(char *o, long v, int base, int zero, int width) {
    if (v < 0) { *o++ = '-'; return p_uint(o, (unsigned long)(-v), base, zero, width); }
    return p_uint(o, (unsigned long)v, base, zero, width);
}

/* 变参格式化（两段式）：
 *   · vfmt_ap(dst, cap, fmt, va_list) —— 真正干活；**转发必须走这个**
 *   · vfmt(dst, cap, fmt, ...)        —— 薄包装，供直接传实参的调用点用
 * ★★★ AArch32 上 `va_list` 是 struct，**不能当普通实参传**（见文件头 GAP 16.75）。 */
static int vfmt_ap(char *dst, int cap, const char *f, va_list ap) {
    const char *fmt = f;
    char *o = dst; char *end = dst + cap - 1;
#define PUT(ch) do { if (o < end) *o++ = (char)(ch); } while (0)
    while (*fmt) {
        if (*fmt != '%') { if (*fmt == '\n' || *fmt == '\r') { fmt++; continue; } PUT(*fmt++); continue; }
        fmt++;
        int zero = 0, width = 0;
        if (*fmt == '0') { zero = 1; fmt++; }
        while (*fmt >= '0' && *fmt <= '9') { width = width * 10 + (*fmt - '0'); fmt++; }
        int lng = 0;
        if (*fmt == 'l') { lng = 1; fmt++; }
        switch (*fmt) {
        case 's': { const char *s = va_arg(ap, const char *);
                    if (!s) s = "(null)";
                    for (int i = 0; s[i] && i < 220; i++) PUT(s[i]); break; }
        case 'c': PUT((char)va_arg(ap, int)); break;
        case 'x': o = lng ? p_uint(o, va_arg(ap, unsigned long), 16, zero, width)
                          : p_uint(o, va_arg(ap, unsigned),      16, zero, width); break;
        case 'u': o = lng ? p_uint(o, va_arg(ap, unsigned long), 10, zero, width)
                          : p_uint(o, va_arg(ap, unsigned),      10, zero, width); break;
        case 'd': o = lng ? p_int(o, va_arg(ap, long), 10, zero, width)
                          : p_int(o, va_arg(ap, int),  10, zero, width); break;
        case 'p': PUT('0'); PUT('x'); o = p_uint(o, (unsigned long)va_arg(ap, void *), 16, 1, 8); break;
        case '%': PUT('%'); break;
        default:  PUT('%'); PUT(*fmt); break;
        }
        fmt++;
    }
#undef PUT
    *o = 0;
    return (int)(o - dst);
}

/* 薄包装：直接传实参的调用点用这个（内部转成 va_list 再交给 vfmt_ap） */
static int vfmt(char *dst, int cap, const char *f, ...) {
    va_list ap; va_start(ap, f);
    int n = vfmt_ap(dst, cap, f, ap);
    va_end(ap);
    return n;
}

/* ---------------- 单调毫秒（粗采样，避免每次 syscall） ---------------- */
static unsigned now_ms(void) {
    if ((g_ms_tick++ & 0x7F) == 0) {
        struct { long s; long ns; } ts;
        if (sc3(SYS_clock_gettime, 1 /*CLOCK_MONOTONIC*/, (long)&ts, 0) == 0)
            g_ms = (unsigned)(ts.s * 1000u + (unsigned)(ts.ns / 1000000));
    }
    return g_ms;
}

static void cgm_lvl_load(void);
static void cgm_dump_env(void);
static void cgm_dump_maps(const char *dst);
static void cgm_install_signals(void);
static void cgm_write_banner(const char *how);
static void cgm_varchk(void);
static void cgm_watch_start(void);
static void cgm_tick(void);

/* ---------------- 初始化（幂等；可从 --wrap(__libc_start_main) / 构造器两处调用） ---------------- */
void cgm_diag_boot(const char *how)
{
    if (g_booted) return;
    g_booted = 1;
    cgm_lvl_load();

    sys_mkdir1("/sdcard");
    sys_mkdir1("/sdcard/cubegm");
    sys_mkdir1(CGM_DIAG_ROOT);

    g_logfd   = sys_open(CGM_DIAG_ROOT "/trace.log",       0x0001 | 0x0040 | 0x0400, 0644);
    g_snapfd  = sys_open(CGM_DIAG_ROOT "/frames.snap.bin", 0x0001 | 0x0040 | 0x0200, 0644);
    g_framefd = sys_open(CGM_DIAG_ROOT "/frames.bin",      0x0001 | 0x0040 | 0x0200, 0644);

    cgm_write_banner(how);
    cgm_varchk();                        /* ★ 仪器自证：变参可信度（判据写在函数注释里） */
    if (g_lvl >= CGM_LVL_CORE) {
        cgm_dump_env();
        cgm_dump_maps(CGM_DIAG_ROOT "/maps.start.txt");
    }
    cgm_install_signals();
    cgm_watch_start();
}

/* 供 --wrap 用：把可变参数拼成一行日志 */
/* ★ 加 format 属性：否则 -Wformat 对自定义格式化函数**一律不检查**
 *   （这就是我此前"编译无警告"却带着参数错位的原因）。 */
__attribute__((format(printf, 2, 3)))
void cgm_putline(const char *tag, const char *fmt, ...);   /* 见下 */
void cgm_putline(const char *tag, const char *fmt, ...)
{
    if (g_lvl <= CGM_LVL_OFF || g_logfd < 0) return;
    char buf[400];
    int n = 0;
    buf[n++] = ' '; buf[n++] = ' ';
    unsigned m = now_ms();
    char t[16]; int k = 0;
    if (!m) t[k++] = '0';
    while (m) { t[k++] = (char)('0' + m % 10); m /= 10; }
    while (k) buf[n++] = t[--k];
    buf[n++] = ' ';
    for (int i = 0; tag[i] && n < 20; i++) buf[n++] = tag[i];
    buf[n++] = ' ';
    va_list ap; va_start(ap, fmt);
    n += vfmt_ap(buf + n, (int)sizeof(buf) - n - 4, fmt, ap);   /* ★ 用 vfmt_ap 转发 va_list */
    va_end(ap);
    buf[n++] = '\n';
    if (g_logbytes > CGM_LOG_MAX_BYTES) {          /* 轮转一次 */
        sys_close(g_logfd);
        sys_open(CGM_DIAG_ROOT "/trace.1.log", 0x0001 | 0x0040 | 0x0200, 0644);
        g_logfd = sys_open(CGM_DIAG_ROOT "/trace.log", 0x0001 | 0x0040 | 0x0400 | 0x0200, 0644);
        g_logbytes = 0; g_rot++;
        wstr(g_logfd, "  ## rotated\n");
    }
    wraw(g_logfd, buf, (unsigned)n);
    g_logbytes += (unsigned)n;
}

/* ---------------- 级别 / 配置 ----------------
 * ★★★ 2026-09-23（设备实测 trace.log）：**cfg.ini 解析必须跳过注释行**。
 *   实测 trace.log 里 `level=2`，而 cfg.ini 里明确写着 `level = 3` ——
 *   因为上一版解析器在**全文**里找第一个 "level"，而**注释行里就有一个**
 *   （`# 本文件读不到就用默认 level=2`）⇒ 永远读到 2，`level = 3` 形同不存在。
 *   这是"键扫描不认行结构"的经典坑：**注释里出现同一个键名 ⇒ 值被注释劫持**。
 *   连带：缓冲区 256 → 1024（cfg.ini 会被注释撑长，256 B 可能读不全真值行）。
 *   判据（本轮设备自证）：trace.log 横幅必须出现 `level=3`。 */
static void cgm_lvl_load(void)
{
    int fd = sys_open(CGM_DIAG_ROOT "/cfg.ini", 0x0000 /*O_RDONLY*/, 0);
    if (fd < 0) return;
    char b[1024];
    long n = sc3(SYS_read, fd, (long)b, (long)sizeof(b) - 1);
    sys_close(fd);
    if (n <= 0) return;
    b[n] = 0;
    {
        long i = 0;
        while (i < n) {
            long ls = i, le, k;
            while (i < n && b[i] != '\n') i++;
            le = i;
            if (i < n) i++;
            while (ls < le && (b[ls] == ' ' || b[ls] == '\t')) ls++;
            if (ls >= le || b[ls] == '#') continue;       /* ★ 跳过空行 / 注释行 */
            for (k = ls; k + 5 <= le; k++) {
                if ((b[k] == 'l' || b[k] == 'L') && b[k + 1] == 'e' && b[k + 2] == 'v'
                    && b[k + 3] == 'e' && b[k + 4] == 'l') {
                    long j = k + 5;
                    int v = 0, got = 0;
                    while (j < le && (b[j] == ' ' || b[j] == '=' || b[j] == 9 || b[j] == ':')) j++;
                    while (j < le && b[j] >= '0' && b[j] <= '9') {
                        v = v * 10 + (b[j] - '0'); j++; got = 1;
                    }
                    if (got && v >= 0 && v <= 3) g_lvl = v;
                    return;
                }
            }
        }
    }
}
int cgm_lvl(void) { return g_lvl; }
int cgm_want(int need) { return g_lvl >= need; }

/* ---------------- 启动横幅 ----------------
 * ★★★ 2026-09-23（设备实测 trace.log）：上一版三条横幅**被挤成同一行**，
 *   根因是 `vfmt_ap` 的既定行为 —— 它**丢弃格式串里的 \n**（为的是"每条日志恒单行"，
 *   cgm_putline 自己会补一个 \n）。但横幅是**直接调 vfmt**的，于是三行变一行。
 *   修法：横幅自己负责行分隔（每段之后显式 wstr("\n")），不改 vfmt_ap 的既定语义。
 *   同时中文字面量改 ASCII —— 实测编译后中文字节落盘会变成乱码
 *   （UTF-8 被按本地代码页解释后再编码），横幅是判据的一部分，**不能有歧义**。 */
static void cgm_write_banner(const char *how)
{
    char buf[420]; int n = 0;
    n += vfmt(buf + n, (int)sizeof(buf) - n,
              "### CGM-DIAG BEGIN  pid=%ld  jiffies=%u  level=%d  how=%s",
              (long)sc3(SYS_getpid, 0, 0, 0), g_ms, g_lvl, how);
    buf[n++] = '\n';
    n += vfmt(buf + n, (int)sizeof(buf) - n,
              "### build=%s %s  ring=%u frames  snap=%ums",
              __DATE__, __TIME__, (unsigned)CGM_RING_FRAMES, (unsigned)CGM_SNAP_MS);
    buf[n++] = '\n';
    n += vfmt(buf + n, (int)sizeof(buf) - n,
              "### positive-control (must appear in trace.log): BOOT / MAIN / EXIT or CRASH");
    buf[n++] = '\n';
    wraw(g_logfd, buf, (unsigned)n);
    g_logbytes += (unsigned)n;
}

/* ---------------- 仪器自证（变参可信度） ----------------
 * ★★★ 2026-09-23：设备实测 `BOOT enter argc=-1098883456 argv0="(null)"`，
 *   且同一份 trace.log 里**所有** %d/%s/%p 都像栈地址 ⇒ 两种可能：
 *     ① 参数本身错位（ABI 不符） ② cgm_putline 的变参读取错位。
 *   而**横幅**（走 vfmt 直传实参）打印的 pid/level/how **完全正确**
 *   ⇒ 至少 vfmt 没问题，嫌疑集中在"经 ... 转发"这条路上。
 *   判据（本轮设备自证）：下面这行**期望值与实测值并列**在一条日志里：
 *     expect int=12345 hex=abcdef str=HELLO ptr=12345678
 *     · 两者一致 ⇒ 变参可信，trace.log 里其它字段的异常就是**真值异常**（我们的代码真的传了垃圾）
 *     · 不一致   ⇒ 变参不可信，本文件所有的 %d/%s/%p **一律作废**，先修仪器再谈结论
 *   ★ 纪律：**先证明仪器可信，再读仪器给的数**。 */
static void cgm_varchk(void)
{
    cgm_putline("VARCHK",
                "expect int=12345 hex=abcdef str=HELLO ptr=12345678 -> got int=%d hex=%x str=%s ptr=%p",
                12345, 0xabcdef, "HELLO", (void *)0x12345678);
}

/* ---------------- 环境快照 ---------------- */
static void dump_proc(const char *src, int fd, const char *hdr)
{
    wraw(fd, hdr, 0); wstr(fd, hdr);
    int s = sys_open(src, 0x0000, 0);
    if (s < 0) { wstr(fd, "  (open fail)\n"); return; }
    char b[4096];
    long n;
    while ((n = sc3(SYS_read, s, (long)b, (long)sizeof(b))) > 0) wraw(fd, b, (unsigned)n);
    sys_close(s);
    wstr(fd, "\n");
}
static void cgm_dump_env(void)
{
    int fd = sys_open(CGM_DIAG_ROOT "/env.txt", 0x0001 | 0x0040 | 0x0200, 0644);
    if (fd < 0) return;
    char b[256]; int n = 0;
    n += vfmt(b + n, (int)sizeof(b) - n, "pid=%ld ppid=%ld uid=%ld gid=%ld\n",
              (long)sc3(SYS_getpid, 0, 0, 0), (long)sc3(SYS_getppid, 0, 0, 0),
              (long)sc3(SYS_getuid, 0, 0, 0), (long)sc3(SYS_getgid, 0, 0, 0));
    wraw(fd, b, (unsigned)n);
    dump_proc("/proc/self/cmdline", fd, "--- cmdline ---\n");
    dump_proc("/proc/self/maps",    fd, "--- maps ---\n");
    dump_proc("/proc/self/auxv",    fd, "--- auxv ---\n");
    dump_proc("/proc/self/status",  fd, "--- status ---\n");
    dump_proc("/proc/version",      fd, "--- version ---\n");
    dump_proc("/proc/meminfo",      fd, "--- meminfo ---\n");
    dump_proc("/proc/cpuinfo",      fd, "--- cpuinfo ---\n");
    dump_proc("/proc/mounts",       fd, "--- mounts ---\n");
    /* environ：直接从 libc 全局读，不经函数调用 */
    {
        extern char **environ;
        wstr(fd, "--- environ ---\n");
        if (environ) for (int i = 0; environ[i] && i < 400; i++) { wstr(fd, environ[i]); wstr(fd, "\n"); }
        wstr(fd, "\n");
    }
    sys_close(fd);
}
static void cgm_dump_maps(const char *dst)
{
    int fd = sys_open(dst, 0x0001 | 0x0040 | 0x0200, 0644);
    if (fd < 0) return;
    dump_proc("/proc/self/maps", fd, "");
    sys_close(fd);
}

/* ---------------- 心跳 / 看门狗 ---------------- */
static volatile unsigned g_alarms;
static void on_alarm(int sig)
{
    (void)sig;
    g_alarms++;
    int fd = sys_open(CGM_DIAG_ROOT "/heartbeat.txt", 0x0001 | 0x0040 | 0x0200, 0644);
    if (fd < 0) return;
    char b[256]; int n = 0;
    n += vfmt(b + n, (int)sizeof(b) - n, "alarm=%u ms=%u frames=%u depth=%u open=%u ret=%u ioc=%u rot=%u\n",
              g_alarms, now_ms(), g_nframe, g_depth, g_nopen, g_ndlopen, g_nioc, g_rot);
    wraw(fd, b, (unsigned)n);
    sys_close(fd);
}
static void cgm_watch_start(void)
{
    struct { long sec; long usec; long isec; long iusec; } it;
    it.sec = CGM_SNAP_MS / 1000; it.usec = 0; it.isec = CGM_SNAP_MS / 1000; it.iusec = 0;
    sc4(SYS_setitimer, 1 /*ITIMER_REAL*/, (long)&it, 0, 0);
}

/* ---------------- 函数级轨迹 ---------------- */
void cgm_frame_enter(uint32_t addr, uint32_t caller)
{
    if (g_booted < 2) { if (!g_booted) return; g_booted = 2; }
    unsigned r = g_rpos++;
    cgm_frame_t *f = &g_ring[r & (CGM_RING_FRAMES - 1)];
    f->addr = addr;
    f->meta = ((uint32_t)g_depth & 0xFFFFu) << 8;
    f->ms = now_ms();
    g_depth++;
    g_nframe++;
    (void)caller;
    cgm_tick();
}
void cgm_frame_exit(uint32_t addr)
{
    if (g_booted < 2) return;
    if (g_depth) g_depth--;
    unsigned r = g_rpos++;
    cgm_frame_t *f = &g_ring[r & (CGM_RING_FRAMES - 1)];
    f->addr = addr;
    f->meta = 1u | (((uint32_t)g_depth & 0xFFFFu) << 8);
    f->ms = now_ms();
    g_nframe++;
}

/* 把环形缓冲按"最旧→最新"线性化写出去 */
static void dump_ring(int fd)
{
    unsigned total = g_rpos;
    unsigned cnt = total < CGM_RING_FRAMES ? total : CGM_RING_FRAMES;
    cgm_frame_t hdr;
    hdr.addr = 0x43474D44u;      /* 'CGMD' magic */
    hdr.meta = cnt;
    hdr.ms = total;
    wraw(fd, &hdr, sizeof(hdr));
    unsigned start = total - cnt;
    for (unsigned i = 0; i < cnt; i++) {
        cgm_frame_t *f = &g_ring[(start + i) & (CGM_RING_FRAMES - 1)];
        wraw(fd, f, sizeof(*f));
        if ((i & 0x3FF) == 0 && total) { /* 让出一点，避免长阻塞 */ }
    }
}
static void cgm_do_snap(void)
{
    if (g_snapfd < 0) return;
    sc3(SYS_lseek, g_snapfd, 0, 0 /*SEEK_SET*/);
    dump_ring(g_snapfd);
    wstr(g_logfd, "  ## snapshot\n");
}

/* 周期任务：由 instrument 每次调用顺带驱动，**不需要线程** */
static void cgm_tick(void)
{
    unsigned m = g_ms;
    if (m - g_last_snap >= CGM_SNAP_MS) { g_last_snap = m + 1; cgm_do_snap(); }
    if (m - g_last_sum >= CGM_SUMMARY_MS) {
        g_last_sum = m + 1;
        if (g_logfd >= 0 && g_lvl >= CGM_LVL_CORE) {
            char b[640]; int n = 0;
            n += vfmt(b + n, (int)sizeof(b) - n,
                      "  ## SUMMARY ms=%u frames=%u depth=%u open=%u dlopen=%u ioctl=%u alarms=%u rot=%u |",
                      m, g_nframe, g_depth, g_nopen, g_ndlopen, g_nioc, g_alarms, g_rot);
            for (int i = 0; i < g_ctr_used && n < 560; i++)
                n += vfmt(b + n, (int)sizeof(b) - n, " %s=%u", g_ctr_name[i], g_ctr_val[i]);
            b[n++] = '\n';
            wraw(g_logfd, b, (unsigned)n); g_logbytes += (unsigned)n;
        }
    }
}

/* ---------------- 崩溃捕获 ---------------- */
static const char *signame(int s)
{
    switch (s) {
    case 4:  return "SIGILL";   case 6:  return "SIGABRT"; case 7:  return "SIGBUS";
    case 8:  return "SIGFPE";   case 11: return "SIGSEGV"; case 5:  return "SIGTRAP";
    case 31: return "SIGSYS";   case 15: return "SIGTERM"; case 2:  return "SIGINT";
    default: return "SIG?";
    }
}
static void on_crash(int sig, siginfo_t *si, void *uc_)
{
    int fd = sys_open(CGM_DIAG_ROOT "/crash.txt", 0x0001 | 0x0040 | 0x0200 | 0x0100, 0644);
    char b[512]; int n;
    unsigned m = now_ms();
    if (fd >= 0) {
        n = vfmt(b, (int)sizeof(b),
                 "=== CGM-DIAG CRASH ===\nsignal=%d (%s)  si_code=%d  si_addr=%p  ms=%u\n"
                 "frames=%u depth=%u total=%u\n",
                 sig, signame(sig), si ? si->si_code : -1,
                 si ? si->si_addr : 0, m, g_nframe, g_depth, g_rpos);
        wraw(fd, b, (unsigned)n);
        /* 寄存器 */
        unsigned long pc = 0, lr = 0, sp = 0, fp = 0, cpsr = 0;
        unsigned long r[13];
        for (int i = 0; i < 13; i++) r[i] = 0;
        if (uc_) {
            ucontext_t *uc = (ucontext_t *)uc_;
            mcontext_t *mc = &uc->uc_mcontext;
            pc = (unsigned long)mc->arm_pc; lr = (unsigned long)mc->arm_lr;
            sp = (unsigned long)mc->arm_sp; fp = (unsigned long)mc->arm_fp;
            cpsr = (unsigned long)mc->arm_cpsr;
            for (int i = 0; i < 13; i++) r[i] = (unsigned long)mc->arm_r0 + 0; /* 占位，见下 */
            r[0] = (unsigned long)mc->arm_r0;  r[1] = (unsigned long)mc->arm_r1;
            r[2] = (unsigned long)mc->arm_r2;  r[3] = (unsigned long)mc->arm_r3;
            r[4] = (unsigned long)mc->arm_r4;  r[5] = (unsigned long)mc->arm_r5;
            r[6] = (unsigned long)mc->arm_r6;  r[7] = (unsigned long)mc->arm_r7;
            r[8] = (unsigned long)mc->arm_r8;  r[9] = (unsigned long)mc->arm_r9;
            r[10] = (unsigned long)mc->arm_r10; r[11] = fp; r[12] = (unsigned long)mc->arm_ip;
            n = vfmt(b, (int)sizeof(b),
                     "pc=%08lx lr=%08lx sp=%08lx fp=%08lx ip=%08lx cpsr=%08lx\n"
                     "r0=%08lx r1=%08lx r2=%08lx r3=%08lx\n"
                     "r4=%08lx r5=%08lx r6=%08lx r7=%08lx\n"
                     "r8=%08lx r9=%08lx r10=%08lx\n",
                     pc, lr, sp, fp, (unsigned long)mc->arm_ip, cpsr,
                     r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], r[9], r[10]);
            wraw(fd, b, (unsigned)n);
            /* fp 链（ARM EABI：fp → [prev_fp, lr]） */
            wstr(fd, "--- fp chain ---\n");
            unsigned long f = fp;
            for (int i = 0; i < 64 && f >= 0x1000; i++) {
                unsigned long prev = *(volatile unsigned long *)f;
                unsigned long ret  = *(volatile unsigned long *)(f + 4);
                n = vfmt(b, (int)sizeof(b), "  [%2d] fp=%08lx ret=%08lx\n", i, f, ret);
                wraw(fd, b, (unsigned)n);
                if (prev <= f) break;
                f = prev;
            }
            /* 栈扫描兜底（无 fp 时也能给出候选返回地址） */
            wstr(fd, "--- stack scan (sp..sp+8K, 4B 对齐, 去重) ---\n");
            unsigned long seen[96]; int nseen = 0;
            for (unsigned long a = sp; a < sp + 8192 && nseen < 96; a += 4) {
                unsigned long v = *(volatile unsigned long *)a;
                if (v < 0x00008000ul || v > 0x0ffffffful) continue;
                int dup = 0;
                for (int k = 0; k < nseen; k++) if (seen[k] == v) { dup = 1; break; }
                if (dup) continue;
                seen[nseen++] = v;
                n = vfmt(b, (int)sizeof(b), "  %08lx\n", v);
                wraw(fd, b, (unsigned)n);
            }
        }
        /* 环形缓冲**全量** dump 到独立文件 */
        if (g_framefd >= 0) { sc3(SYS_lseek, g_framefd, 0, 0); dump_ring(g_framefd); }
        /* maps（符号化必需） */
        wstr(fd, "--- /proc/self/maps ---\n");
        { int s = sys_open("/proc/self/maps", 0x0000, 0);
          if (s >= 0) { char t[4096]; long k; while ((k = sc3(SYS_read, s, (long)t, (long)sizeof(t))) > 0) wraw(fd, t, (unsigned)k); sys_close(s); } }
        /* 打开的文件（脚本可据此定位"卡在哪个文件"） */
        wstr(fd, "--- /proc/self/fd ---\n");
        { int s = sys_open("/proc/self/fd", 0x0000 | 0x10000 /*O_DIRECTORY*/, 0);
          if (s >= 0) { char t[1024]; long k; while ((k = sc3(SYS_read, s, (long)t, (long)sizeof(t))) > 0) wraw(fd, t, (unsigned)k); sys_close(s); } }
        wstr(fd, "=== END CRASH ===\n");
        sys_close(fd);
    }
    /* 走默认动作：保留原始退出码语义（SIGSEGV ⇒ 139） */
    sc4(SYS_rt_sigaction, sig, 0, 0, 8);
    sc3(SYS_tgkill, (long)sc3(SYS_getpid, 0, 0, 0), (long)sc3(SYS_gettid, 0, 0, 0), sig);
    sc3(SYS_exit_group, 139, 0, 0);
}

static void cgm_install_signals(void)
{
    /* struct sigaction 布局（glibc arm）：handler(4) mask(8) flags(4) restorer(4)
       —— 为避免头文件与设备 glibc 版本差异，这里用本地结构按 glibc 定义填。 */
    struct ksa {
        void (*handler)(int, siginfo_t *, void *);
        unsigned long sa_mask;
        int sa_flags;
        void (*sa_restorer)(void);
    } sa;
    sa.handler = on_crash; sa.sa_mask = 0; sa.sa_flags = 4 /*SA_SIGINFO*/; sa.sa_restorer = 0;
    int sigs[] = { 4, 6, 7, 8, 11, 5, 31, 15, 2 };
    for (unsigned i = 0; i < sizeof(sigs) / sizeof(sigs[0]); i++)
        sc4(SYS_rt_sigaction, sigs[i], (long)&sa, 0, 8);
    /* SIGALRM 心跳 */
    sa.handler = (void (*)(int, siginfo_t *, void *))on_alarm;
    sa.sa_flags = 4; sa.sa_mask = 0; sa.sa_restorer = 0;
    sc4(SYS_rt_sigaction, 14 /*SIGALRM*/, (long)&sa, 0, 8);
}

/* ---------------- 生命周期钩子 ---------------- */
void cgm_lifecycle(const char *ev, int code)
{
    if (g_booted < 2) { if (!g_booted) return; g_booted = 2; }
    char buf[300]; int n = 0;
    n += vfmt(buf + n, (int)sizeof(buf) - n, "  ## %s code=%d ms=%u frames=%u total=%u\n",
              ev, code, now_ms(), g_nframe, g_rpos);
    if (g_logfd >= 0) { wraw(g_logfd, buf, (unsigned)n); g_logbytes += (unsigned)n; }
    if (g_framefd >= 0 && (!ev[0] || ev[0] != 'X')) { sc3(SYS_lseek, g_framefd, 0, 0); dump_ring(g_framefd); }
}

/* cgm_tick 需要被外面调用（--wrap 的 io 事件里） */
void cgm_tick_public(void);
void cgm_tick_public(void) { cgm_tick(); }

/* 计数器入口（给 wrap 用） */
void cgm_bump(const char *nm);
void cgm_bump(const char *nm) { ctr(nm); }

/* ============================================================
 * -finstrument-functions 的两个回调
 *
 * ★ 本文件**必须**用 `-finstrument-functions-exclude-file-list` 排除掉
 *   （tools/build_diag.sh 已这么做），否则这两个函数自己会被插桩 ⇒ 无限递归。
 *   这里再显式加 no_instrument_function，双保险。
 * ============================================================ */
__attribute__((no_instrument_function))
void __cyg_profile_func_enter(void *this_fn, void *call_site)
{
    cgm_frame_enter((uint32_t)(uintptr_t)this_fn, (uint32_t)(uintptr_t)call_site);
}

__attribute__((no_instrument_function))
void __cyg_profile_func_exit(void *this_fn, void *call_site)
{
    (void)call_site;
    cgm_frame_exit((uint32_t)(uintptr_t)this_fn);
}
