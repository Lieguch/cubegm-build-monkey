/* ============================================================
 * ui_type.c — 游戏分类界面实现（对齐原厂 mui_type @ 0x1a3c8）
 * ============================================================
 *
 * 分类定义（对齐原厂 SD 卡 <NNN> 目录）：
 *   000 — 街机 (Arcade/FBA)
 *   001 — FC/NES
 *   002 — SFC/SMC
 *   003 — MD/GG
 *   004 — GBA
 *   005 — NES
 *   006 — GB/GBC
 *   007 — PS1
 *   008 — Atari 2600
 * ============================================================ */

#include "ui_type.h"
#include "rkgame.h"
#include "ui.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static ui_type_state_t s_type;

/* 分类定义（对齐原厂目录） */
static const char *g_type_names[] = {
    "000 - Arcade/FBA",
    "001 - FC/NES",
    "002 - SFC/SMC",
    "003 - MD/GG",
    "004 - GBA",
    "005 - NES",
    "006 - GB/GBC",
    "007 - PS1",
    "008 - Atari 2600"
};

#define TYPE_COUNT (sizeof(g_type_names) / sizeof(g_type_names[0]))

int ui_type_init(void)
{
    memset(&s_type, 0, sizeof(s_type));
    s_type.type_count = TYPE_COUNT;
    s_type.cursor = 0;
    for (int i = 0; i < TYPE_COUNT && i < 10; i++) {
        snprintf(s_type.type_names[i], 64, "%s", g_type_names[i]);
    }
    RKLOG_I("ui_type_init: %d categories loaded", TYPE_COUNT);
    return 0;
}

void ui_type_open(void)  { s_type.open = true; s_type.cursor = 0; }
void ui_type_close(void) { s_type.open = false; }
bool ui_type_is_open(void) { return s_type.open; }
int  ui_type_selected(void) { return s_type.cursor; }

void ui_type_tick(int keycode)
{
    if (!s_type.open) return;

    /* 简化按键映射（与 main.c 一致） */
    #define KEY_UP       10
    #define KEY_DOWN     11
    #define KEY_LEFT     12
    #define KEY_RIGHT    13
    #define KEY_OK       0
    #define KEY_CANCEL   1

    if (keycode == KEY_UP || keycode == KEY_LEFT) {
        s_type.cursor = (s_type.cursor - 1 + s_type.type_count) % s_type.type_count;
        RKLOG_I("ui_type: cursor -> %d", s_type.cursor);
    } else if (keycode == KEY_DOWN || keycode == KEY_RIGHT) {
        s_type.cursor = (s_type.cursor + 1) % s_type.type_count;
        RKLOG_I("ui_type: cursor -> %d", s_type.cursor);
    } else if (keycode == KEY_CANCEL) {
        s_type.open = false;
        RKLOG_I("ui_type: closed");
    }
    /* KEY_OK: 选中分类，返回索引给调用方 */
}

void ui_type_draw(void)
{
    if (!s_type.open) return;

    /* 绘制 type.raw 背景（若已加载） */
    if (ui_is_ready()) {
        ui_draw_page(UI_PAGE_TYPE);
    }

    /* 叠加分类列表文字 */
    if (font_is_ready()) {
        const char *path = work_path;
        int y = 60;

        /* 标题 */
        font_draw_text("Game Categories", 20, y, 0x00ff00);
        y += 30;

        /* 当前分类目录 */
        char dir[20];
        snprintf(dir, sizeof(dir), "%s%03d", path, s_type.cursor);
        font_draw_text(dir, 20, y, 0xffffff);
        y += 30;

        /* 分类列表 */
        for (int i = 0; i < s_type.type_count; i++) {
            const char *prefix = (i == s_type.cursor) ? " > " : "   ";
            char line[80];
            snprintf(line, sizeof(line), "%s%s", prefix, s_type.type_names[i]);
            font_draw_text(line, 20, y + i * 28,
                           (i == s_type.cursor) ? 0x00ff00 : 0xffffff);
        }

        /* 提示 */
        font_draw_text("A=Select  B=Back  Up/Down=Browse",
                       20, y + s_type.type_count * 28 + 10, 0x888888);
    }
}
