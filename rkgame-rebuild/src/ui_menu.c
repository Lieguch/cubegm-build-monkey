/* ============================================================
 * ui_menu.c — 主菜单 UI 实现（对齐原厂 m_ui + mui_menu）
 * ============================================================
 *
 * 原厂 mui_menu @ 0x1b80c：
 *   1. 显示 menu.raw 背景
 *   2. 显示当前 type.raw 分类
 *   3. 显示 game.raw 缩略图 + 游戏名
 *   4. 按键：A=确认(→run_game), ←→=切分类, ↑↓=切游戏, MENU=设置, SEARCH=搜索
 * ============================================================ */

#include "ui_menu.h"
#include "ui.h"
#include "ui_zip.h"
#include "game_list.h"
#include "font.h"
#include "debug.h"
#include "rkgame.h"

#include <stdio.h>
#include <string.h>

static ui_menu_state_t s_menu = {
    .page = 0,
    .category_index = 0,
    .game_index = 0,
    .active = true,
};

int ui_menu_init(void)
{
    s_menu.category_index = 0;
    s_menu.game_index = 0;
    s_menu.active = true;
    s_menu.page = UI_PAGE_MENU;
    RKLOG_I("ui_menu_init: category=0 game=0");
    return 0;
}

const ui_menu_state_t *ui_menu_state(void) { return &s_menu; }

int ui_menu_selected_game(void) { return s_menu.game_index; }

void ui_menu_tick(int keycode)
{
    /* P1-1: 统一原厂事件码 bitmask（A=0x2000 B=0x4000 UP=0x10 DOWN=0x40
     * LEFT=0x80 RIGHT=0x20 START=0x008 SELECT=0x001） */
    #define FK_UP      0x10
    #define FK_DOWN    0x40
    #define FK_LEFT    0x80
    #define FK_RIGHT   0x20
    #define FK_A       0x2000
    #define FK_B       0x4000
    #define FK_START   0x008
    #define FK_SELECT  0x001

    if (!s_menu.active) return;
    if (keycode == 0) return;   /* 0 = 本帧无有效按键，须跳过避免误触发 */

    int count = game_list_is_loaded() ? game_list_count() : 0;

    if ((keycode & FK_UP) && count > 0) {
        s_menu.game_index = (s_menu.game_index - 1 + count) % count;
        RKLOG_I("ui_menu: game -> %d", s_menu.game_index);
    } else if ((keycode & FK_DOWN) && count > 0) {
        s_menu.game_index = (s_menu.game_index + 1) % count;
        RKLOG_I("ui_menu: game -> %d", s_menu.game_index);
    } else if (keycode & FK_LEFT) {
        s_menu.category_index = (s_menu.category_index - 1 + 9) % 9;
        s_menu.game_index = 0;
        RKLOG_I("ui_menu: category -> %d", s_menu.category_index);
    } else if (keycode & FK_RIGHT) {
        s_menu.category_index = (s_menu.category_index + 1) % 9;
        s_menu.game_index = 0;
        RKLOG_I("ui_menu: category -> %d", s_menu.category_index);
    } else if ((keycode & FK_A) && count > 0 && s_menu.game_index < count) {
        RKLOG_I("ui_menu: launch game %d", s_menu.game_index);
        /* 启动由 main.c 的 game_loop 处理 */
    }
}

void ui_menu_draw(void)
{
    if (!s_menu.active) return;
    if (!ui_is_ready()) return;

    ui_draw_page(UI_PAGE_MENU);

    if (font_is_ready()) {
        int y = 40;

        /* 分类指示 */
        char cat[40];
        snprintf(cat, sizeof(cat), "Category: %d", s_menu.category_index);
        font_draw_text(cat, 20, y, 0x00ff00);
        y += 28;

        /* 游戏列表 */
        if (game_list_is_loaded()) {
            int count = game_list_count();
            int page_size = 8;
            int scroll = (s_menu.game_index / page_size) * page_size;

            font_draw_text("Games:", 20, y, 0xffffff);
            y += 24;

            for (int i = scroll; i < scroll + page_size && i < count; i++) {
                game_entry_t *ge = game_list_get(i);
                if (!ge) continue;
                const char *name = ge->name[0] ? ge->name : "(unnamed)";
                const char *prefix = (i == s_menu.game_index) ? " > " : "   ";
                char line[160];
                snprintf(line, sizeof(line), "%s%s", prefix, name);
                font_draw_text(line, 20, y + (i - scroll) * 22,
                               (i == s_menu.game_index) ? 0x00ff00 : 0xffffff);
            }
            y += page_size * 22 + 10;
        }

        /* 提示 */
        font_draw_text("A=Launch  B=Back  L/R=Category  U/D=Browse",
                       20, y, 0x888888);
    }
}

int ui_menu_run(void)
{
    if (!ui_is_ready()) return 0;
    ui_draw_page(UI_PAGE_MENU);
    return 0;
}
