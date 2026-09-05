/* ============================================================
 * rkgame-rebuild — 调试日志实现（信号安全）
 * ============================================================
 *
 * 架构：
 *   1. 在 entry.c _rkgame_start() 中，main() 之前调用 dbg_init()
 *   2. dbg_init() 打开日志文件 + 安装崩溃信号处理器 + 写入口标记
 *   3. 每个初始化阶段调用 dbg_probe(DBG_ST_XXX) 埋点
 *   4. 崩溃时 crash_handler() 将最后 N 条日志 + 寄存器 dump 写入 crash.log
 *   5. 正常退出时 dbg_close() 写入 session 结尾标记
 *
 * 信号安全约束：
 *   - crash_handler() 中只使用 write/open/close/fstat（POSIX async-signal-safe）
 *   - 不使用 malloc/free/snprintf/vsnprintf/printf（不在信号上下文中安全）
 *   - hex/itoa 编码全部内联实现
 *   - 日志使用 fd 而非 FILE*（避免 stdio 的锁）
 * ============================================================ */

#define _GNU_SOURCE
#include <unistd.h>
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <signal.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/ucontext.h>
#include <errno.h>
#include <stdint.h>
#include <stdarg.h>

#include "debug.h"

/* ---- 常量 ---- */

#define LOG_PATHS_DEFAULT \
    "/sdcard/cubegm/rkgame.log" \
    "/sdcard/rkgame.log" \
    "/tmp/rkgame.log" \
    "/dev/null"

#define CRASH_LOG_PATH  "/sdcard/cubegm/rkgame.crash.log"

/* 环形缓冲区：保存最后 N 条日志，崩溃时一次性写入 crash.log */
#define DBG_LOG_HISTORY  30
#define DBG_LOG_TEXT     200   /* 每条日志最大文本长度 */

/* ---- 阶段名 ---- */
static const char *const g_stage_names[] = {
    [DBG_ST_ENTRY]        = "ENTRY: _rkgame_start()",
    [DBG_ST_MAIN_BEGIN]   = "MAIN: begin",
    [DBG_ST_GET_PATH]     = "PATH: get_executable_path",
    [DBG_ST_CONFIG_LOAD]  = "CFG: config_load",
    [DBG_ST_DISP_INIT]    = "DISP: disp_init",
    [DBG_ST_AUDIO_INIT]   = "AUDIO: audio_init",
    [DBG_ST_SRAM_INIT]    = "SRAM: sram_init",
    [DBG_ST_JOY_INIT]     = "JOY: joy_init",
    [DBG_ST_CORE_DLOPEN]  = "CORE: dlopen",
    [DBG_ST_CORE_DLSYM]   = "CORE: dlsym batch",
    [DBG_ST_CORE_INIT]    = "CORE: retro_init",
    [DBG_ST_CORE_LOADGAME]= "CORE: retro_load_game",
    [DBG_ST_CORE_RUN]     = "CORE: run loop",
    [DBG_ST_CORE_UNLOAD]  = "CORE: unload",
    [DBG_ST_SHUTDOWN]     = "SHUTDOWN",
    [DBG_ST_END]          = "MAIN: exit 0",
};

/* ---- 全局状态 ---- */

static int g_log_fd = -1;
static int g_debug_level = DBG_LEVEL_DEBUG;

/* 日志历史条目 */
struct dbg_log_entry {
    uint32_t ts_ms;
    int      level;
    int      len;
    char     text[DBG_LOG_TEXT];
};
static struct dbg_log_entry g_log_history[DBG_LOG_HISTORY];
static int g_log_idx = 0;
static int g_log_count = 0;

/* ---- 内联编码 ---- */

static int hex32(char *buf, uint32_t v)
{
    static const char hex[] = "0123456789abcdef";
    int i;
    for (i = 7; i >= 0; i--) {
        buf[i] = hex[v & 0xf];
        v >>= 4;
    }
    return 8;
}

static int itoa32(char *buf, int32_t v)
{
    char tmp[12];
    int len = 0, neg = 0;
    int32_t x = v;

    if (x < 0) { neg = 1; x = -x; }
    if (x == 0) { tmp[len++] = '0'; }
    else {
        int i = 0;
        while (x > 0 && i < 10) {
            tmp[i++] = '0' + (x % 10);
            x /= 10;
        }
        len = i;
    }
    if (neg) tmp[len++] = '-';
    int i;
    for (i = 0; i < len; i++)
        buf[i] = tmp[len - 1 - i];
    return len;
}

static int strncpy_n(const char *src, char *dst, int n)
{
    int i = 0;
    while (i < n && src[i]) { dst[i] = src[i]; i++; }
    return i;
}

/* ---- 崩溃处理函数 ---- */

static void crash_handler(int sig, siginfo_t *info, void *ucontext)
{
    int fd = open(CRASH_LOG_PATH, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0)
        return;

    char buf[512];
    int n;

    /* 1) 信号信息 */
    n = 0;
    n += itoa32(buf + n, sig);
    buf[n++] = ' ';
    const char *sig_name = NULL;
    switch (sig) {
        case SIGSEGV: sig_name = "SIGSEGV";   break;
        case SIGBUS:  sig_name = "SIGBUS";    break;
        case SIGABRT: sig_name = "SIGABRT";   break;
        case SIGILL:  sig_name = "SIGILL";    break;
        case SIGFPE:  sig_name = "SIGFPE";    break;
        case SIGTRAP: sig_name = "SIGTRAP";   break;
        default:      sig_name = "UNKNOWN";   break;
    }
    n += strncpy_n(sig_name, buf + n, sizeof(buf) - n - 1);
    buf[n++] = '\n';
    write(fd, buf, n);

    /* 2) 故障地址 */
    if (info && info->si_addr) {
        n = 0;
        n += strncpy_n("fault_addr=", buf + n, sizeof(buf) - n - 1);
        n += hex32(buf + n, (uint32_t)(uintptr_t)info->si_addr);
        buf[n++] = '\n';
        write(fd, buf, n);
    }

    /* 3) 寄存器 dump（ARM32） */
    if (ucontext) {
        ucontext_t *uc = (ucontext_t *)ucontext;
        /* ARM32 mcontext_t 以 arm_r0..arm_r15, arm_cpsr 开头 */
        uint32_t regs[17];
        memcpy(regs, &uc->uc_mcontext, sizeof(regs));

        const char *names[] = {
            "r0", "r1", "r2", "r3",
            "r4", "r5", "r6", "r7",
            "r8", "r9", "sl", "fp",
            "ip", "sp", "lr", "pc",
            "cpsr"
        };
        int i;
        for (i = 0; i < 17; i++) {
            n = 0;
            n += strncpy_n(names[i], buf + n, sizeof(buf) - n - 1);
            buf[n++] = '=';
            n += hex32(buf + n, regs[i]);
            buf[n++] = ' ';
            write(fd, buf, n);
        }
        buf[0] = '\n';
        write(fd, buf, 1);
    }

    /* 4) 最后 N 条日志 */
    int k;
    for (k = 0; k < g_log_count && k < DBG_LOG_HISTORY; k++) {
        int idx = (g_log_idx - g_log_count + k + DBG_LOG_HISTORY) % DBG_LOG_HISTORY;
        const struct dbg_log_entry *e = &g_log_history[idx];
        if (e->len > 0 && e->len <= DBG_LOG_TEXT)
            write(fd, e->text, e->len);
    }

    close(fd);
    raise(SIGKILL);
}

/* ---- 日志写入 ---- */

/*
 * 关键：launcher 可能已经把自己的 stderr（fd 2）重定向到 rkgame.log。
 * 如果 dbg_init() 再独立 open 一个 fd 写同一个文件，两个 O_APPEND fd 会
 * 以不同进程内状态交错，真机日志里会出现半行/乱码。这里统一把 fd 2
 * dup2 到 g_log_fd，让 write(2,...)/fprintf(stderr,...)/dbg_log() 共享
 * 同一个文件描述符。
 */
static void dbg_redirect_stderr(void)
{
    if (g_log_fd < 0)
        return;

    int saved = dup(2);
    if (saved < 0)
        return;

    if (dup2(g_log_fd, 2) < 0) {
        close(saved);
        return;
    }
    close(saved);
}

static void dbg_write_to_fd(const char *data, int len)
{
    if (g_log_fd < 0)
        return;
    while (len > 0) {
        int n = write(g_log_fd, data, len);
        if (n <= 0) {
            if (n < 0 && (errno == EINTR || errno == EAGAIN))
                continue;
            break;
        }
        data += n;
        len -= n;
    }
}

void dbg_log(int level, const char *fmt, ...)
{
    if (level > g_debug_level)
        return;

    char buf[512];
    va_list ap;
    int tlen;

    struct timeval tv;
    gettimeofday(&tv, NULL);
    uint32_t ts_ms = (uint32_t)(tv.tv_sec * 1000 + tv.tv_usec / 1000);
    tlen = itoa32(buf, ts_ms);

    buf[tlen++] = ' ';
    char lvl_char = 'D';
    if (level == DBG_LEVEL_INFO)  lvl_char = 'I';
    if (level == DBG_LEVEL_DEBUG) lvl_char = 'D';
    if (level == DBG_LEVEL_TRACE) lvl_char = 'T';
    buf[tlen++] = lvl_char;
    buf[tlen++] = ':';
    buf[tlen++] = ' ';

    va_start(ap, fmt);
    int vlen = vsnprintf(buf + tlen, sizeof(buf) - tlen, fmt, ap);
    va_end(ap);
    if (vlen < 0) vlen = 0;
    tlen += vlen;
    if (tlen >= (int)sizeof(buf) - 1)
        tlen = sizeof(buf) - 1;
    buf[tlen++] = '\n';

    dbg_write_to_fd(buf, tlen);

    struct dbg_log_entry *e = &g_log_history[g_log_idx];
    e->ts_ms = ts_ms;
    e->level = level;
    int save_len = tlen < DBG_LOG_TEXT ? tlen : DBG_LOG_TEXT;
    memcpy(e->text, buf, save_len);
    e->len = save_len;
    g_log_idx = (g_log_idx + 1) % DBG_LOG_HISTORY;
    if (g_log_count < DBG_LOG_HISTORY)
        g_log_count++;
}

void dbg_probe(int stage_id)
{
    if (stage_id < 0 || stage_id >= DBG_ST_END)
        return;
    char buf[128];
    int len = 3;
    buf[0] = 'P';
    buf[1] = ':';
    buf[2] = ' ';
    len += strncpy_n(g_stage_names[stage_id], buf + len, sizeof(buf) - len - 1);
    buf[len++] = '\n';
    dbg_write_to_fd(buf, len);

    struct dbg_log_entry *e = &g_log_history[g_log_idx];
    e->ts_ms = 0;
    e->level = DBG_LEVEL_INFO;
    int save_len = len < DBG_LOG_TEXT ? len : DBG_LOG_TEXT;
    memcpy(e->text, buf, save_len);
    e->len = save_len;
    g_log_idx = (g_log_idx + 1) % DBG_LOG_HISTORY;
    if (g_log_count < DBG_LOG_HISTORY)
        g_log_count++;
}

void dbg_init(void)
{
    /* ---- 1) 立刻向 stderr 输出可见标记（诊断：确认 main() 是否被执行） ---- */
    const char *banner = "=== rkgame rebuild starting ===\n";
    (void)write(2, banner, 32);

    /* ---- 2) 尝试多个日志路径（SD 卡写失败时降级） ---- */
    const char *const candidates[] = {
        "/sdcard/cubegm/rkgame.log",
        "/sdcard/rkgame.log",
        "/tmp/rkgame.log",
        NULL
    };
    int i;
    const char *chosen = NULL;
    int open_errno = 0;

    for (i = 0; candidates[i]; i++) {
        int fd = open(candidates[i], O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (fd >= 0) {
            g_log_fd = fd;
            chosen = candidates[i];
            break;
        }
        open_errno = errno;
    }

    /* ---- 3) 报告日志文件状态 ---- */
    if (g_log_fd >= 0) {
        /*
         * 先输出本次会话的 banner，再统一 fd 2 与日志 fd。
         * 这样 CI 的 test-emu.log 会先看到启动横幅，随后所有日志统一进入日志文件。
         */
        write(2, banner, 32);
        dbg_redirect_stderr();

        /* banner 同时写入日志文件（之前只写 stderr，设备上不可见） */
        write(g_log_fd, banner, 32);
        const char *header = "--- rkgame session start ---\n";
        write(g_log_fd, header, 28);
        char stbuf[128];
        int n = 0;
        n += strncpy_n("[DBG] log path = ", stbuf + n, sizeof(stbuf) - n - 1);
        n += strncpy_n(chosen, stbuf + n, sizeof(stbuf) - n - 1);
        stbuf[n++] = '\n';
        write(2, stbuf, n);
    } else {
        char stbuf[160];
        int n = 0;
        n += strncpy_n("[DBG] FATAL: cannot open any log path (errno=", stbuf + n, sizeof(stbuf) - n - 1);
        n += itoa32(stbuf + n, open_errno);
        stbuf[n++] = ')';
        stbuf[n++] = '\n';
        write(2, stbuf, n);
    }

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = crash_handler;
    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);

    sigaction(SIGSEGV, &sa, NULL);
    sigaction(SIGBUS,  &sa, NULL);
    sigaction(SIGABRT, &sa, NULL);
    sigaction(SIGILL,  &sa, NULL);
    sigaction(SIGFPE,  &sa, NULL);
    sigaction(SIGTRAP, &sa, NULL);

    dbg_probe(DBG_ST_ENTRY);
}

void dbg_close(void)
{
    if (g_log_fd >= 0) {
        const char *footer = "--- rkgame session end ---\n";
        write(g_log_fd, footer, 28);
        close(g_log_fd);
        g_log_fd = -1;
    }
}
