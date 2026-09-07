/* ============================================================
 * rkgame-rebuild — 屏幕调试叠加层实现
 * ============================================================
 *
 * 设计要点：
 *   1. SELECT+START 长按 2s 切换开关（避免误触）
 *   2. 渲染到底部 1280×220 面板（半透明黑底）
 *   3. 显示：阶段 / FPS / 内存 / 按键状态 / 最近日志
 *   4. 零依赖（只读 /proc/self/status, /proc/meminfo, /proc/uptime）
 *   5. 与 disp.c 的 XRGB8888 颜色格式一致
 *
 * 颜色格式（与 disp.c 保持一致）：
 *   XRGB8888，其中 R/G/B 通道位置：
 *     R = (color >> 16) & 0xff
 *     G = (color >>  8) & 0xff
 *     B = (color & 0xff)
 *   注意：这与标准 RGB8888 相反（标准是 B<<16|G<<8|R），
 *   但 disp.c 已按此约定，overlay 必须一致。
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdlib.h>

#include "dbg_overlay.h"
#include "debug.h"
#include "rkgame.h"

/* ============================================================
 * 常量
 * ============================================================ */

/* 切换组合键：SELECT + START
 * evdev.c 中 KEY_START = (1 << 12), KEY_SELECT = (1 << 13) */
#define OVERLAY_TOGGLE_COMBO  ((1u << 12) | (1u << 13))
#define OVERLAY_TOGGLE_HOLD_MS  2000

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
#define PANEL_HEIGHT  240
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

/* FPS 计数器 */
static int      g_frame_count      = 0;
static uint32_t g_fps_window_ms    = 0;
static int      g_fps              = 0;

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
 * FPS 计算
 * ============================================================ */

void dbg_overlay_tick_frame(void)
{
    g_frame_count++;
    uint32_t now = now_ms();
    if (g_fps_window_ms == 0) {
        g_fps_window_ms = now;
    } else if (now >= g_fps_window_ms && (now - g_fps_window_ms) >= 1000) {
        uint32_t elapsed = now - g_fps_window_ms;
        g_fps = (elapsed > 0) ? (int)(g_frame_count * 1000 / elapsed) : 0;
        g_frame_count = 0;
        g_fps_window_ms = now;
    }
}

int dbg_overlay_fps(void) { return g_fps; }

/* ============================================================
 * 切换检测
 * ============================================================ */

static void dbg_overlay_check_toggle(void)
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
            LOG("dbg overlay %s (held %ums)",
                g_enabled ? "ON" : "OFF", now - g_hold_start_ms);
            DBG_I("dbg overlay %s", g_enabled ? "ON" : "OFF");
            g_hold_start_ms = 0;
        }
    } else {
        g_hold_start_ms = 0;
    }
}

void dbg_overlay_force_toggle(void)
{
    g_enabled = !g_enabled;
    LOG("dbg overlay %s (force)", g_enabled ? "ON" : "OFF");
}

/* ============================================================
 * 渲染
 * ============================================================ */

static void draw_panel(const char *lines[], int line_count)
{
    int w = disp_fb_width();
    int h = disp_fb_height();
    if (w <= 0 || h <= 0)
        return;

    int panel_h = PANEL_HEIGHT;
    int panel_y = h - panel_h;
    if (panel_y < 0)
        panel_y = 0;

    /* 面板背景（半透明黑） */
    disp_draw_rect(0, panel_y, w, panel_h, CLR_PANEL_BG);

    /* 顶部标题栏 */
    disp_draw_rect(0, panel_y, w, 24, CLR_PANEL_HDR);
    disp_draw_text(PANEL_PADDING, panel_y + 3,
                   "=== rkgame DEBUG OVERLAY ===", CLR_YELLOW);
    disp_draw_text(w - 300, panel_y + 3,
                   "SELECT+START 2s = toggle", CLR_WHITE);

    /* 内容行 */
    int x = PANEL_PADDING;
    int y = panel_y + 30;

    for (int i = 0; i < line_count && i < MAX_LOG_LINES + 6; i++) {
        if (lines[i] && y + LINE_HEIGHT - 4 <= h)
            disp_draw_text(x, y, lines[i], CLR_WHITE);
        y += LINE_HEIGHT;
    }

    /* 底部提示行（红色） */
    int hint_y = h - 14;
    disp_draw_text(x, hint_y,
                   "DEBUG: overlay active. Hold SELECT+START 2s to hide.",
                   CLR_RED);
}

static void dbg_overlay_render(void)
{
    if (!g_enabled || !disp_is_ready())
        return;

    /* ---- 收集信息 ---- */
    uint64_t rss_kb = 0, vsz_kb = 0;
    read_proc_kb("/proc/self/status", "VmRSS:", &rss_kb);
    read_proc_kb("/proc/self/status", "VmSize:", &vsz_kb);
    double uptime = read_uptime();
    uint64_t memtot_kb = 0, memavl_kb = 0;
    read_proc_kb("/proc/meminfo", "MemTotal:", &memtot_kb);
    read_proc_kb("/proc/meminfo", "MemAvailable:", &memavl_kb);

    uint32_t keys = joy_all_keys_state();
    int stage = dbg_current_stage();
    const char *stage_name = dbg_stage_name(stage);
    int dbg_level = dbg_get_level();

    uint32_t uptime_ms = now_ms() - g_init_ms;
    int minutes = (int)(uptime_ms / 60000);
    int seconds = (int)((uptime_ms / 1000) % 60);

    /* ---- 构建显示行 ---- */
    char lines[MAX_LOG_LINES + 8][128];
    int n = 0;

    /* 行 1：PID + 启动时长 */
    snprintf(lines[n++], sizeof(lines[0]),
             "PID=%d  up=%dm%02ds  stage=%d [%s]",
             (int)getpid(), minutes, seconds, stage, stage_name);

    /* 行 2：内存 */
    snprintf(lines[n++], sizeof(lines[0]),
             "VmRSS=%.0fMB  VmSize=%.0fMB  MemTotal=%.0fMB  Avail=%.0fMB",
             rss_kb / 1024.0, vsz_kb / 1024.0,
             memtot_kb / 1024.0, memavl_kb / 1024.0);

    /* 行 3：FPS + 显示状态 */
    snprintf(lines[n++], sizeof(lines[0]),
             "FPS=%d  DRM=%s  game=%s  fb=%dx%d  level=%d",
             g_fps,
             disp_is_ready() ? "OK" : "FAIL",
             disp_is_game_mode() ? "ON" : "MENU",
             disp_fb_width(), disp_fb_height(), dbg_level);

    /* 行 4：按键状态（hex） */
    snprintf(lines[n++], sizeof(lines[0]),
             "keys=0x%08x  (hex=16 actions)", keys);

    /* 行 5：按键状态（可读） */
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

    /* 行 6：分隔线 */
    snprintf(lines[n++], sizeof(lines[0]),
             "--- last %d logs (newest first) ---", MAX_LOG_LINES);

    /* 行 7-11：最近日志 */
    char log_lines[MAX_LOG_LINES][128];
    int log_count = dbg_get_last_logs(log_lines, MAX_LOG_LINES);
    if (log_count == 0) {
        snprintf(lines[n++], sizeof(lines[0]), "(no logs captured yet)");
    } else {
        /* 倒序显示：最新在最上面 */
        for (int i = log_count - 1; i >= 0 && n < MAX_LOG_LINES + 6; i--) {
            const char *l = log_lines[i];
            /* 截断到 100 字符 */
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

    /* ---- 渲染 ---- */
    draw_panel(lines, n);
}

/* ============================================================
 * 主入口
 * ============================================================ */

bool dbg_overlay_tick(void)
{
    dbg_overlay_check_toggle();
    if (g_enabled && disp_is_ready()) {
        dbg_overlay_render();
        return true;
    }
    return false;
}

void dbg_overlay_init(void)
{
    g_init_ms = now_ms();
    g_fps_window_ms = 0;
    g_fps = 0;
    g_frame_count = 0;
    g_enabled = false;
    g_hold_start_ms = 0;
    LOG("dbg_overlay: initialized (hold SELECT+START 2s to toggle)");
}

bool dbg_overlay_is_on(void) { return g_enabled; }
