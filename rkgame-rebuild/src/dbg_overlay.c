/* ============================================================
 * rkgame-rebuild — 屏幕调试叠加层（单文件自包含实现）
 * ============================================================
 *
 * 设计约束：只修改一个文件（本文件），不修改其他源文件。
 *
 * 核心需求：
 *   1. 从进程启动（constructor）就开始写日志，不依赖 disp_init
 *   2. disp_init 成功后才渲染屏幕 overlay
 *   3. disp_init 失败时，日志文件仍有完整 Debug 记录
 *
 * 实现方式：
 *   1. __attribute__((constructor)) 自动初始化，无需修改 main.c
 *      - 立即打开日志文件，写入启动标记
 *      - 启动后台线程
 *   2. 后台线程每 50ms：
 *      - 如果 disp_is_ready() == false：写入日志（启动诊断）
 *      - 如果 disp_is_ready() == true：检查按键 + 渲染 overlay
 *   3. __attribute__((destructor))  自动清理
 *   4. 直接调用 disp_draw_text / disp_draw_rect / disp_present
 *     （这些函数在 disp.c 中是非 static 的，可直接调用）
 *   5. 直接读取 /proc/self/status 和 /proc/meminfo
 *
 * 触发方式：
 *   长按 SELECT + START 2 秒 → 切换屏幕底部调试面板
 *
 * 颜色格式：
 *   XRGB8888，与 disp.c 保持一致（AARRGGBB，R/B 通道互换）
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <pthread.h>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <stdarg.h>

#include "rkgame.h"      /* disp_draw_text, disp_draw_rect, disp_present, joy_all_keys_state */

/* ============================================================
 * 常量
 * ============================================================ */

/* 切换组合键：SELECT + START
 * evdev.c 中 KEY_START = (1 << 12), KEY_SELECT = (1 << 13) */
#define OVERLAY_TOGGLE_COMBO  ((1u << 12) | (1u << 13))
#define OVERLAY_TOGGLE_HOLD_MS  2000

/* 后台线程检查间隔 */
#define OVERLAY_POLL_MS  50

/* 日志文件路径（与 debug.c 保持一致） */
#define DBG_LOG_PATH_1  "/sdcard/cubegm/rkgame.log"
#define DBG_LOG_PATH_2  "/sdcard/rkgame.log"
#define DBG_LOG_PATH_3  "/tmp/rkgame.log"

/* 颜色（XRGB8888，与 disp.c 保持一致） */
#define CLR_BLACK     0x00000000u
#define CLR_WHITE     0xFF000000u
#define CLR_GRAY      0xFF808080u
#define CLR_DARKGRAY  0xFF404040u
#define CLR_RED       0xFF0000FFu  /* R=B 通道, B=R 通道 */
#define CLR_GREEN     0xFF00FF00u
#define CLR_BLUE      0xFFFF0000u
#define CLR_YELLOW    0xFF00FFFFu
#define CLR_CYAN      0xFFFF00FFu
#define CLR_MAGENTA   0xFF8000FFu
#define CLR_PANEL_BG  0xE0000000u  /* 87% 不透明黑 */
#define CLR_PANEL_HDR 0xFF101010u  /* 标题栏深色 */

/* 面板尺寸 */
#define PANEL_HEIGHT  220
#define LINE_HEIGHT   22
#define PANEL_PADDING 10

/* 最大日志行数显示 */
#define MAX_LOG_LINES  5

/* ============================================================
 * 全局状态
 * ============================================================ */

static bool     g_enabled          = false;
static uint32_t g_hold_start_ms    = 0;
static uint32_t g_init_ms          = 0;
static pthread_t g_thread_id       = 0;
static volatile int g_running       = 1;

/* 渲染锁：防止后台线程与主线程同时写 framebuffer */
static pthread_mutex_t g_render_mutex = PTHREAD_MUTEX_INITIALIZER;

/* FPS 计数器 */
static int      g_frame_count      = 0;
static uint32_t g_fps_window_ms    = 0;
static int      g_fps              = 0;

/* 日志文件 fd（constructor 中打开，destructor 中关闭） */
static int      g_log_fd           = -1;

/* 日志写入锁：防止后台线程与 constructor 同时写 */
static pthread_mutex_t g_log_mutex = PTHREAD_MUTEX_INITIALIZER;

/* ============================================================
 * 工具函数
 * ============================================================ */

static uint32_t now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}

/* 从 /proc/self/status 或 /proc/meminfo 读取 "Key: N kB" 格式 */
static void read_proc_kb(const char *path, const char *key, uint64_t *out_kb)
{
    *out_kb = 0;
    FILE *f = fopen(path, "r");
    if (!f) return;
    char line[256];
    size_t klen = strlen(key);
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, key, klen) == 0) {
            unsigned long long v = 0;
            if (sscanf(line + klen, " %llu", &v) == 1)
                *out_kb = (uint64_t)v;
            break;
        }
    }
    fclose(f);
}

static double read_uptime(void)
{
    FILE *f = fopen("/proc/uptime", "r");
    if (!f) return 0.0;
    double up = 0.0;
    if (fscanf(f, "%lf", &up) != 1)
        up = 0.0;
    fclose(f);
    return up;
}

/* ============================================================
 * 日志写入（从 constructor 就开始，不依赖 disp_init）
 * ============================================================ */

/* 打开日志文件（constructor 中调用） */
static int open_log_file(void)
{
    const char *paths[] = {
        DBG_LOG_PATH_1,
        DBG_LOG_PATH_2,
        DBG_LOG_PATH_3,
        NULL
    };

    for (int i = 0; paths[i]; i++) {
        int fd = open(paths[i], O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (fd >= 0) {
            return fd;
        }
    }
    return -1;
}

/* 写入日志（线程安全） */
static void log_write(const char *fmt, ...)
{
    if (g_log_fd < 0)
        return;

    pthread_mutex_lock(&g_log_mutex);

    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    int len = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    if (len > 0) {
        if ((size_t)len >= sizeof(buf))
            len = sizeof(buf) - 1;
        if (buf[len - 1] != '\n')
            buf[len++] = '\n';
        write(g_log_fd, buf, len);
    }

    pthread_mutex_unlock(&g_log_mutex);
}

/* 写入时间戳 + 日志 */
static void log_ts(const char *fmt, ...)
{
    uint32_t ms = now_ms();
    va_list ap;
    va_start(ap, fmt);
    int len = snprintf((char[]) {0}, 0, fmt, ap);  /* dummy */
    va_end(ap);

    char buf[512];
    int prefix_len = snprintf(buf, sizeof(buf), "%ums ", ms);
    va_start(ap, fmt);
    int msg_len = vsnprintf(buf + prefix_len, sizeof(buf) - prefix_len, fmt, ap);
    va_end(ap);

    if (msg_len > 0) {
        if ((size_t)(prefix_len + msg_len) >= sizeof(buf))
            msg_len = sizeof(buf) - prefix_len - 1;
        if (buf[prefix_len + msg_len - 1] != '\n')
            buf[prefix_len + msg_len++] = '\n';
        if (g_log_fd >= 0)
            write(g_log_fd, buf, prefix_len + msg_len);
    }
}

/* 从日志文件读取最近 N 条非空行 */
static int read_last_logs(char lines[][128], int max_count)
{
    if (max_count <= 0 || g_log_fd < 0) return 0;

    /* 使用已打开的 fd 读取 */
    FILE *f = fdopen(dup(g_log_fd), "r");
    if (!f) return 0;

    char buf[8192];
    size_t len = 0;
    char tmp[512];
    while (fgets(tmp, sizeof(tmp), f) && len < sizeof(buf) - 1) {
        size_t tlen = strlen(tmp);
        if (tlen == 0) continue;
        memcpy(buf + len, tmp, tlen);
        len += tlen;
    }
    buf[len] = '\0';
    fclose(f);

    if (len == 0) return 0;

    int count = 0;
    char *end = buf + len;
    char *start = buf;

    while (end > start && count < max_count) {
        char *line_end = end;
        if (line_end > start && *(line_end - 1) == '\n')
            line_end--;

        char *line_start = line_end;
        while (line_start > start && *(line_start - 1) != '\n')
            line_start--;

        size_t line_len = line_end - line_start;
        if (line_len > 127) line_len = 127;

        memcpy(lines[count], line_start, line_len);
        lines[count][line_len] = '\0';
        count++;

        end = line_start - 1;
    }

    /* 反转（从新到旧） */
    for (int i = 0; i < count / 2; i++) {
        char tmp[128];
        memcpy(tmp, lines[i], 128);
        memcpy(lines[i], lines[count - 1 - i], 128);
        memcpy(lines[count - 1 - i], tmp, 128);
    }

    return count;
}

/* ============================================================
 * FPS 计算
 * ============================================================ */

static void update_fps(void)
{
    uint32_t now = now_ms();
    if (g_fps_window_ms == 0) {
        g_fps_window_ms = now;
        return;
    }
    if (now >= g_fps_window_ms && (now - g_fps_window_ms) >= 1000) {
        uint32_t elapsed = now - g_fps_window_ms;
        g_fps = (elapsed > 0) ? (int)(g_frame_count * 1000 / elapsed) : 0;
        g_frame_count = 0;
        g_fps_window_ms = now;
    }
}

/* ============================================================
 * 切换检测
 * ============================================================ */

static void check_toggle(void)
{
    if (!disp_is_ready())
        return;

    uint32_t cur = joy_all_keys_state();
    uint32_t now = now_ms();

    if ((cur & OVERLAY_TOGGLE_COMBO) == OVERLAY_TOGGLE_COMBO) {
        if (g_hold_start_ms == 0) {
            g_hold_start_ms = now;
        } else if (now >= g_hold_start_ms &&
                   (now - g_hold_start_ms) >= OVERLAY_TOGGLE_HOLD_MS) {
            g_enabled = !g_enabled;
            log_ts("[DBG-OVERLAY] overlay %s (held %ums)",
                   g_enabled ? "ON" : "OFF", now - g_hold_start_ms);
            g_hold_start_ms = 0;
        }
    } else {
        g_hold_start_ms = 0;
    }
}

/* ============================================================
 * 渲染
 * ============================================================ */

static void render_panel(const char *lines[], int line_count)
{
    int w = disp_fb_width();
    int h = disp_fb_height();
    if (w <= 0 || h <= 0)
        return;

    int panel_h = PANEL_HEIGHT;
    int panel_y = h - panel_h;
    if (panel_y < 0)
        panel_y = 0;

    pthread_mutex_lock(&g_render_mutex);

    disp_draw_rect(0, panel_y, w, panel_h, CLR_PANEL_BG);

    disp_draw_rect(0, panel_y, w, 24, CLR_PANEL_HDR);
    disp_draw_text(PANEL_PADDING, panel_y + 3,
                   "=== rkgame DEBUG OVERLAY ===", CLR_YELLOW);
    disp_draw_text(w - 300, panel_y + 3,
                   "SELECT+START 2s = toggle", CLR_WHITE);

    int x = PANEL_PADDING;
    int y = panel_y + 30;

    for (int i = 0; i < line_count; i++) {
        if (lines[i] && y + LINE_HEIGHT - 4 <= h)
            disp_draw_text(x, y, lines[i], CLR_WHITE);
        y += LINE_HEIGHT;
    }

    int hint_y = h - 14;
    disp_draw_text(x, hint_y,
                   "DEBUG: overlay active. Hold SELECT+START 2s to hide.",
                   CLR_RED);

    disp_present();

    pthread_mutex_unlock(&g_render_mutex);
}

static void dbg_overlay_render(void)
{
    if (!g_enabled || !disp_is_ready())
        return;

    uint64_t rss_kb = 0, vsz_kb = 0;
    read_proc_kb("/proc/self/status", "VmRSS:", &rss_kb);
    read_proc_kb("/proc/self/status", "VmSize:", &vsz_kb);
    uint64_t memtot_kb = 0, memavl_kb = 0;
    read_proc_kb("/proc/meminfo", "MemTotal:", &memtot_kb);
    read_proc_kb("/proc/meminfo", "MemAvailable:", &memavl_kb);

    uint32_t keys = joy_all_keys_state();
    uint32_t uptime_ms = now_ms() - g_init_ms;
    int minutes = (int)(uptime_ms / 60000);
    int seconds = (int)((uptime_ms / 1000) % 60);

    char lines[MAX_LOG_LINES + 8][128];
    int n = 0;

    snprintf(lines[n++], sizeof(lines[0]),
             "PID=%d  up=%dm%02ds  drm=%s  game=%s",
             (int)getpid(), minutes, seconds,
             disp_is_ready() ? "OK" : "FAIL",
             disp_is_game_mode() ? "ON" : "MENU");

    snprintf(lines[n++], sizeof(lines[0]),
             "VmRSS=%.0fMB  VmSize=%.0fMB  MemTotal=%.0fMB  Avail=%.0fMB",
             rss_kb / 1024.0, vsz_kb / 1024.0,
             memtot_kb / 1024.0, memavl_kb / 1024.0);

    snprintf(lines[n++], sizeof(lines[0]),
             "FPS=%d  fb=%dx%d",
             g_fps, disp_fb_width(), disp_fb_height());

    snprintf(lines[n++], sizeof(lines[0]),
             "keys=0x%08x", keys);

    char key_str[128] = "";
    const char *names[16] = {
        "B","Y","SEL","ST","L1","R1","A","X",
        "UP","DN","LT","RT","L3","R3","",""
    };
    for (int i = 0; i < 16; i++) {
        if (keys & (1u << i)) {
            size_t len = strlen(key_str);
            if (len > 0 && len + 1 < sizeof(key_str) - 1) {
                key_str[len] = '+';
                key_str[len + 1] = '\0';
            }
            len = strlen(key_str);
            strncpy(key_str + len, names[i], sizeof(key_str) - len - 1);
            key_str[sizeof(key_str) - 1] = '\0';
        }
    }
    if (!key_str[0])
        snprintf(key_str, sizeof(key_str), "(no keys pressed)");
    snprintf(lines[n++], sizeof(lines[0]), "pressed: %s", key_str);

    snprintf(lines[n++], sizeof(lines[0]),
             "--- last %d logs (newest first) ---", MAX_LOG_LINES);

    char log_lines[MAX_LOG_LINES][128];
    int log_count = read_last_logs(log_lines, MAX_LOG_LINES);
    if (log_count == 0) {
        snprintf(lines[n++], sizeof(lines[0]), "(no logs captured yet)");
    } else {
        for (int i = 0; i < log_count && n < MAX_LOG_LINES + 6; i++) {
            const char *l = log_lines[i];
            char truncated[128];
            if ((int)strlen(l) > 100) {
                strncpy(truncated, l, 100);
                truncated[100] = '\0';
            } else {
                strncpy(truncated, l, sizeof(truncated) - 1);
                truncated[sizeof(truncated) - 1] = '\0';
            }
            snprintf(lines[n++], sizeof(lines[0]), "%s", truncated);
        }
    }

    render_panel(lines, n);
}

/* ============================================================
 * 后台线程
 * ============================================================ */

static void *overlay_thread(void *arg)
{
    (void)arg;

    /* 等待 disp_init 完成（最多等 30 秒） */
    uint32_t wait_start = now_ms();
    while (g_running && !disp_is_ready() &&
           (now_ms() - wait_start) < 30000) {
        usleep(OVERLAY_POLL_MS * 1000);
    }

    if (!disp_is_ready()) {
        log_ts("[DBG-OVERLAY] disp_init failed, running in log-only mode");
    } else {
        log_ts("[DBG-OVERLAY] disp_init OK, overlay enabled (SELECT+START 2s)");
    }

    while (g_running) {
        /* FPS 计数 */
        g_frame_count++;
        update_fps();

        /* 如果 disp 就绪，检查按键 + 渲染 */
        if (disp_is_ready()) {
            check_toggle();
            if (g_enabled) {
                dbg_overlay_render();
            }
        }

        usleep(OVERLAY_POLL_MS * 1000);
    }
    return NULL;
}

/* ============================================================
 * 自动初始化 / 清理
 * ============================================================ */

__attribute__((constructor))
static void dbg_overlay_auto_init(void)
{
    g_init_ms = now_ms();
    g_fps_window_ms = 0;
    g_fps = 0;
    g_frame_count = 0;
    g_enabled = false;
    g_hold_start_ms = 0;
    g_running = 1;

    /* 立即打开日志文件（不依赖 disp_init） */
    g_log_fd = open_log_file();

    /* 写入启动标记（这是最早的 Debug 记录） */
    if (g_log_fd >= 0) {
        char buf[256];
        int len = snprintf(buf, sizeof(buf),
            "=== rkgame debug overlay STARTED (PID=%d, %ums) ===\n",
            (int)getpid(), g_init_ms);
        if (len > 0)
            write(g_log_fd, buf, len);

        /* 记录初始状态 */
        uint64_t memtot = 0, memavl = 0;
        read_proc_kb("/proc/meminfo", "MemTotal:", &memtot);
        read_proc_kb("/proc/meminfo", "MemAvailable:", &memavl);
        double up = read_uptime();

        len = snprintf(buf, sizeof(buf),
            "[INIT] MemTotal=%.0fMB Avail=%.0fMB uptime=%.0fs disp=%s\n",
            memtot / 1024.0, memavl / 1024.0, up,
            disp_is_ready() ? "READY" : "NOT_READY");
        if (len > 0)
            write(g_log_fd, buf, len);
    } else {
        fprintf(stderr, "[DBG-OVERLAY] failed to open log file\n");
    }

    /* 启动后台线程 */
    if (pthread_create(&g_thread_id, NULL, overlay_thread, NULL) != 0) {
        log_write("[DBG-OVERLAY] failed to create thread");
        g_running = 0;
        return;
    }

    log_ts("[DBG-OVERLAY] thread started (hold SELECT+START 2s to toggle)");
}

__attribute__((destructor))
static void dbg_overlay_auto_shutdown(void)
{
    g_running = 0;
    if (g_thread_id) {
        pthread_join(g_thread_id, NULL);
        g_thread_id = 0;
    }
    if (g_log_fd >= 0) {
        write(g_log_fd, "=== rkgame debug overlay STOPPED ===\n", 37);
        close(g_log_fd);
        g_log_fd = -1;
    }
}
