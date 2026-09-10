/* ui_search_file_list.c — 搜索列表 */

#include "ui_search_file_list.h"
#include "ui.h"
#include "font.h"
#include "game_list.h"
#include "debug.h"
#include "rkgame.h"

#include <string.h>

static ui_search_file_list_state_t s_sfl;

int ui_search_file_list_init(void) { memset(&s_sfl, 0, sizeof(s_sfl)); return 0; }
void ui_search_file_list_open(const char *query)
{
    s_sfl.open = true;
    s_sfl.cursor = 0;
    if (query) snprintf(s_sfl.query, sizeof(s_sfl.query), "%s", query);
}
void ui_search_file_list_close(void) { s_sfl.open = false; }
bool ui_search_file_list_is_open(void) { return s_sfl.open; }

void ui_search_file_list_tick(int keycode)
{
    if (!s_sfl.open) return;
    /* P1-1: 统一原厂事件码 bitmask */
    #define FK_UP     0x10
    #define FK_DOWN   0x40
    #define FK_A      0x2000
    #define FK_B      0x4000

    if (keycode & FK_B) { s_sfl.open = false; return; }
    if (keycode & FK_UP) s_sfl.cursor = (s_sfl.cursor - 1 + 8) % 8;
    else if (keycode & FK_DOWN) s_sfl.cursor = (s_sfl.cursor + 1) % 8;
    else if (keycode & FK_A) {
        RKLOG_I("ui_search_file_list: selected %d for '%s'", s_sfl.cursor, s_sfl.query);
        s_sfl.open = false;
    }
}

void ui_search_file_list_draw(void)
{
    if (!s_sfl.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_SEARCH);

    if (font_is_ready()) {
        int y = 50;
        char title[80];
        snprintf(title, sizeof(title), "Results for: '%s'", s_sfl.query);
        font_draw_text(title, 20, y, 0x00ff00); y += 30;

        if (game_list_is_loaded() && s_sfl.query[0]) {
            int count = game_list_count();
            int results = 0;
            for (int i = 0; i < count && results < 8; i++) {
                game_entry_t *ge = game_list_get(i);
                if (ge && strstr(ge->name, s_sfl.query)) {
                    const char *prefix = (results == s_sfl.cursor) ? " > " : "   ";
                    char line[140];
                    snprintf(line, sizeof(line), "%s%s", prefix, ge->name);
                    font_draw_text(line, 20, y + results * 24,
                                   (results == s_sfl.cursor) ? 0x00ff00 : 0xffffff);
                    results++;
                }
            }
            if (results == 0) font_draw_text("(no results)", 20, y, 0x888888);
        }
        font_draw_text("A=Launch  B=Back  U/D=Browse", 20, y + 8 * 24 + 10, 0x888888);
    }
}
