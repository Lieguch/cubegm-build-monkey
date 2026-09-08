/* ============================================================
 * joystick_zip.h — joystick.zip 完整解析器（P2-1）
 * ============================================================
 *
 * 原厂 joystick.zip 结构（26 动作词表 + ui.cfg 扫描码矩阵 + 手柄 profile）：
 *
 *   条目 1: 0000_0000.zip (107B)
 *           26 个动作词表：P1+P2 各 13 键（A/B/X/Y/L/R/Z/LEFT/RIGHT/UP/DOWN/START/SEL）
 *
 *   条目 2..3: ui.cfg (2 份，P1 和 P2)
 *           2×27 扫描码矩阵：每份含 26 个动作 → 扫描码（0-52）
 *
 *   条目 4..7: 4 个手柄 profile
 *           0810_0001_0100 / 0810_0001_0110 / 20bc_5500 / 2563_0555
 *           每个 20 tokens: VID/PID/REV + 17 按钮 + hat + axisX + axisY
 * ============================================================ */

#ifndef JOYSTICK_ZIP_H
#define JOYSTICK_ZIP_H

#include <stdbool.h>
#include <stddef.h>

#define JOY_ACTIONS_MAX  26
#define JOY_PROFILES_MAX 4

typedef struct {
    char vid_pid_rev[16];      /* "0810_0001_0100" */
    char btns[20][12];         /* 20 tokens: VID/PID/REV + 17 键 + hat + axisX/Y */
    int  token_count;
    bool loaded;
} joystick_profile_t;

typedef struct {
    /* 动作词表 */
    char actions[JOY_ACTIONS_MAX][32];
    int  action_count;

    /* 扫描码矩阵：[player 0/1][action_idx] = scan_code */
    unsigned char scan[2][JOY_ACTIONS_MAX];
    int           scan_count[2];

    /* 手柄 profile */
    joystick_profile_t profiles[JOY_PROFILES_MAX];
    int profile_count;

    bool loaded;
} joystick_zip_t;

extern joystick_zip_t g_joystick_zip;

int  joystick_zip_load(const char *zip_path);
void joystick_zip_free(void);

/* 按索引获取扫描码 */
unsigned char joystick_zip_scan(int player, int action_idx);

/* 按 VID/PID/REV 找 profile */
const joystick_profile_t *joystick_zip_find_profile(const char *vid_pid_rev);

/* 诊断 */
void joystick_zip_report(void);

#endif /* JOYSTICK_ZIP_H */
