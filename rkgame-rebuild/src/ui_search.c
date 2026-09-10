/* ============================================================
 * ui_search.c — 搜索界面实现（对齐原厂 mui_search @ 0x1a5b0）
 * ============================================================ */

#include "ui_search.h"
#include "rkgame.h"
#include "ui.h"
#include "game_list.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <ctype.h>

static ui_search_state_t s_search;

int ui_search_init(void) { memset(&s_search, 0, sizeof(s_search)); return 0; }
void ui_search_open(void)  { s_search.open = true; s_search.cursor = 0; s_search.query[0] = '\0'; }
void ui_search_close(void) { s_search.open = false; }
bool ui_search_is_open(void) { return s_search.open; }

void ui_search_tick(int keycode)
{
    if (!s_search.open) return;
    /* P1-1: 统一原厂事件码 bitmask */
    #define FK_A       0x2000   /* 搜索确认 */
    #define FK_B       0x4000   /* 返回 */
    #define FK_LEFT    0x80
    #define FK_RIGHT   0x20

    if (keycode & FK_B) {
        s_search.open = false;
    } else if ((keycode & FK_LEFT) && s_search.cursor > 0) {
        s_search.cursor--;
        s_search.query[s_search.cursor] = '\0';
    } else if (keycode & FK_RIGHT) {
        /* 简化：用游戏列表中的字母填充搜索框 */
        int count = game_list_is_loaded() ? game_list_count() : 0;
        if (count > 0 && s_search.cursor < 31) {
            game_entry_t *ge = game_list_get(0);
            if (ge && ge->name[0]) {
                s_search.query[s_search.cursor++] = ge->name[0];
                s_search.query[s_search.cursor] = '\0';
            }
        }
    } else if ((keycode & FK_A) && s_search.query[0]) {
        /* 搜索完成，进入搜索文件列表 */
        RKLOG_I("ui_search: query='%s'", s_search.query);
    }
}

void ui_search_draw(void)
{
    if (!s_search.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_SEARCH);

    if (font_is_ready()) {
        int y = 60;
        font_draw_text("Search", 20, y, 0x00ff00);
        y += 30;

        /* 搜索框 */
        char box[60];
        snprintf(box, sizeof(box), "|%s        |", s_search.query);
        font_draw_text(box, 20, y, 0xffffff);
        y += 30;

        /* 搜索结果 */
        if (s_search.query[0] && game_list_is_loaded()) {
            int count = game_list_count();
            int results = 0;
            for (int i = 0; i < count && results < 8; i++) {
                game_entry_t *ge = game_list_get(i);
                if (ge && strstr(ge->name, s_search.query)) {
                    font_draw_text(ge->name, 20, y + results * 24, 0xffffff);
                    results++;
                }
            }
            if (results == 0)
                font_draw_text("(no results)", 20, y, 0x888888);
            y += results * 24 + 10;
        }

        font_draw_text("A=Search  B=Back  L=Delete", 20, y, 0x888888);
    }
}
