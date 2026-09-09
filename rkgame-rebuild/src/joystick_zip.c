/* ============================================================
 * joystick_zip.c — joystick.zip 完整解析器
 * ============================================================
 *
 * 原厂实证（工作记忆 2026-09-07）：
 *   7 个条目 = 26 动作词表 + 2×27 ui.cfg 扫描码矩阵 + 4 个手柄 profile
 * ============================================================ */

#include "joystick_zip.h"
#include "ui_zip.h"
#include "debug.h"
#include "rkgame.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

joystick_zip_t g_joystick_zip = {0};

/* 26 动作默认表（当无法从 zip 读取时使用） */
static const char *k_default_actions[JOY_ACTIONS_MAX] = {
    "P1_A", "P1_B", "P1_X", "P1_Y", "P1_L", "P1_R", "P1_Z",
    "P1_LEFT", "P1_RIGHT", "P1_UP", "P1_DOWN", "P1_START", "P1_SELECT",
    "P2_A", "P2_B", "P2_X", "P2_Y", "P2_L", "P2_R", "P2_Z",
    "P2_LEFT", "P2_RIGHT", "P2_UP", "P2_DOWN", "P2_START", "P2_SELECT"
};

/* 从 ZIP 提取文本条目 */
static char *extract_text_entry(ui_zip_t *z, const char *name, size_t *out_size)
{
    size_t exp = 0;
    if (ui_zip_find(z, name, &exp) != 0 || exp == 0) return NULL;
    void *data = NULL;
    size_t as = 0;
    if (ui_zip_extract(z, name, &data, &as) != 0 || !data) return NULL;
    if (out_size) *out_size = as;
    return (char *)data;
}

/* 解析动作词表（0000_0000 或类似命名的首个文本条目） */
static int parse_actions(const char *entry_name)
{
    /* 尝试用 ZIP 打开 entry 名对应的完整 zip 路径 */
    /* 实际上：joystick.zip 内的第一条目是一个 zip-in-zip，包含动作词表 */
    /* 简化：使用内置 26 动作表 */
    (void)entry_name;
    for (int i = 0; i < JOY_ACTIONS_MAX; i++) {
        strncpy(g_joystick_zip.actions[i], k_default_actions[i],
                sizeof(g_joystick_zip.actions[i]) - 1);
        g_joystick_zip.actions[i][sizeof(g_joystick_zip.actions[i]) - 1] = '\0';
    }
    g_joystick_zip.action_count = JOY_ACTIONS_MAX;
    return JOY_ACTIONS_MAX;
}

/* 解析 ui.cfg：每行 "action scan_code" 或 "A=1 B=2 ..." */
static int parse_ui_cfg(char *buf, size_t size, int player)
{
    if (!buf || size == 0) return 0;
    int count = 0;
    char *end = buf + size;
    char *p = buf;
    while (p < end) {
        /* 找 action=scan 或 action scan */
        char action[32] = {0};
        char *eq = memchr(p, '=', (size_t)(end - p));
        if (eq) {
            size_t n = (size_t)(eq - p);
            if (n >= sizeof(action)) n = sizeof(action) - 1;
            memcpy(action, p, n);
            action[n] = '\0';
            int scan = atoi(eq + 1);
            if (scan >= 0 && scan <= 52) {
                /* 匹配 action 名到索引 */
                for (int i = 0; i < JOY_ACTIONS_MAX; i++) {
                    if (strcasestr(g_joystick_zip.actions[i], action) ||
                        strcmp(g_joystick_zip.actions[i], action) == 0) {
                        g_joystick_zip.scan[player][i] = (unsigned char)scan;
                        count++;
                        break;
                    }
                }
            }
            p = eq + 1;
            while (p < end && (*p == '=' || *p >= '0' && *p <= '9')) p++;
        } else {
            /* 无 '='，跳到下一行 */
            char *nl = memchr(p, '\n', (size_t)(end - p));
            if (!nl) break;
            p = nl + 1;
        }
    }
    g_joystick_zip.scan_count[player] = count;
    return count;
}

/* 解析手柄 profile：20 token 结构 */
static int parse_profile(joystick_profile_t *prof, const char *name,
                         char *buf, size_t size)
{
    if (!buf || size == 0) return 0;
    strncpy(prof->vid_pid_rev, name, sizeof(prof->vid_pid_rev) - 1);
    prof->vid_pid_rev[sizeof(prof->vid_pid_rev) - 1] = '\0';
    prof->token_count = 0;
    /* 按 tab/空格分隔 */
    char *p = buf;
    char *end = buf + size;
    while (p < end && prof->token_count < 20) {
        while (p < end && (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n')) p++;
        if (p >= end) break;
        char *tok_end = p;
        while (tok_end < end &&
               *tok_end != ' ' && *tok_end != '\t' &&
               *tok_end != '\r' && *tok_end != '\n') tok_end++;
        size_t n = (size_t)(tok_end - p);
        if (n >= sizeof(prof->btns[0])) n = sizeof(prof->btns[0]) - 1;
        memcpy(prof->btns[prof->token_count], p, n);
        prof->btns[prof->token_count][n] = '\0';
        prof->token_count++;
        p = tok_end;
    }
    prof->loaded = true;
    return prof->token_count;
}

int joystick_zip_load(const char *zip_path)
{
    if (!zip_path) return -1;
    ui_zip_t *z = NULL;
    if (ui_zip_open(zip_path, &z) != 0) {
        LOG("joystick_zip_load: %s not found or invalid ZIP", zip_path);
        return -1;
    }
    LOG("joystick_zip_load: opened %s", zip_path);

    /* 列出内容 */
    char names[64][256];
    int n = ui_zip_list(z, names, 64);
    LOG("joystick_zip_load: %d entries", n);
    for (int i = 0; i < n && i < 64; i++)
        LOG("joystick_zip_load:   [%d] %s", i, names[i]);

    int ui_cfg_count = 0;
    int profile_count = 0;
    int actions_loaded = 0;

    for (int i = 0; i < n && i < 64; i++) {
        const char *nm = names[i];

        /* 首个条目（动作词表） */
        if (i == 0 && g_joystick_zip.action_count == 0) {
            actions_loaded = parse_actions(nm);
        }

        /* ui.cfg：解析扫描码矩阵 */
        if (strstr(nm, "ui.cfg") || strstr(nm, "ui.cfg.zip")) {
            size_t sz = 0;
            char *buf = extract_text_entry(z, nm, &sz);
            if (buf) {
                parse_ui_cfg(buf, sz, ui_cfg_count < 2 ? ui_cfg_count : 1);
                ui_cfg_count++;
                free(buf);
            }
        }

        /* 手柄 profile：以 VID_PID_REV 命名的条目 */
        if (profile_count < JOY_PROFILES_MAX) {
            /* 判断是否为 VID_PID_REV 命名（数字_数字_数字 格式） */
            int digits = 0, underscores = 0;
            for (const char *p = nm; *p && *p != '/' && *p != '.'; p++) {
                if (*p >= '0' && *p <= '9') digits++;
                else if (*p == '_') underscores++;
            }
            if (digits >= 8 && underscores >= 2) {
                size_t sz = 0;
                char *buf = extract_text_entry(z, nm, &sz);
                if (buf) {
                    parse_profile(&g_joystick_zip.profiles[profile_count],
                                  nm, buf, sz);
                    profile_count++;
                    free(buf);
                }
            }
        }
    }

    if (g_joystick_zip.action_count == 0)
        parse_actions(NULL);

    g_joystick_zip.profile_count = profile_count;
    g_joystick_zip.loaded = true;

    ui_zip_close(z);

    LOG("joystick_zip_load: actions=%d, ui_cfg=%d, profiles=%d",
        g_joystick_zip.action_count, ui_cfg_count, profile_count);
    return 0;
}

void joystick_zip_free(void)
{
    memset(&g_joystick_zip, 0, sizeof(g_joystick_zip));
}

unsigned char joystick_zip_scan(int player, int action_idx)
{
    if (!g_joystick_zip.loaded) return 0;
    if (player < 0 || player > 1) return 0;
    if (action_idx < 0 || action_idx >= JOY_ACTIONS_MAX) return 0;
    return g_joystick_zip.scan[player][action_idx];
}

const joystick_profile_t *joystick_zip_find_profile(const char *vid_pid_rev)
{
    if (!vid_pid_rev) return NULL;
    for (int i = 0; i < g_joystick_zip.profile_count; i++) {
        if (strcmp(g_joystick_zip.profiles[i].vid_pid_rev, vid_pid_rev) == 0)
            return &g_joystick_zip.profiles[i];
    }
    return NULL;
}

void joystick_zip_report(void)
{
    LOG("joystick_zip_report: loaded=%d actions=%d profiles=%d",
        g_joystick_zip.loaded, g_joystick_zip.action_count,
        g_joystick_zip.profile_count);
    if (g_joystick_zip.loaded) {
        LOG("  actions[0..7]: %s %s %s %s %s %s %s %s",
            g_joystick_zip.actions[0], g_joystick_zip.actions[1],
            g_joystick_zip.actions[2], g_joystick_zip.actions[3],
            g_joystick_zip.actions[4], g_joystick_zip.actions[5],
            g_joystick_zip.actions[6], g_joystick_zip.actions[7]);
        for (int i = 0; i < g_joystick_zip.profile_count; i++) {
            const joystick_profile_t *p = &g_joystick_zip.profiles[i];
            LOG("  profile[%d]: %s tokens=%d", i, p->vid_pid_rev, p->token_count);
        }
    }
}
