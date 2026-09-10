/* ui_shoucang.c — 收藏列表 */

#include "ui_shoucang.h"
#include "ui.h"
#include "font.h"
#include "game_list.h"
#include "debug.h"
#include "rkgame.h"

#include <string.h>

static ui_shoucang_state_t s_fav;

int ui_shoucang_init(void) { memset(&s_fav, 0, sizeof(s_fav)); return 0; }
void ui_shoucang_open(void)  { s_fav.open = true; s_fav.cursor = 0; }
void ui_shoucang_close(void) { s_fav.open = false; }
bool ui_shoucang_is_open(void) { return s_fav.open; }

void ui_shoucang_tick(int keycode)
{
    if (!s_fav.open) return;
    /* P1-1: 统一原厂事件码 bitmask */
    #define FK_UP      0x10
    #define FK_DOWN    0x40
    #define FK_A       0x2000   /* 启动 */
    #define FK_B       0x4000   /* 返回 */

    int count = game_list_is_loaded() ? game_list_count() : 0;
    if ((keycode & FK_UP) && count > 0)
        s_fav.cursor = (s_fav.cursor - 1 + count) % count;
    else if ((keycode & FK_DOWN) && count > 0)
        s_fav.cursor = (s_fav.cursor + 1) % count;
    else if (keycode & FK_B)
        s_fav.open = false;
    else if ((keycode & FK_A) && count > 0 && s_fav.cursor < count)
        RKLOG_I("ui_shoucang: launch %d", s_fav.cursor);
}

void ui_shoucang_draw(void)
{
    if (!s_fav.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_GAME);

    if (font_is_ready()) {
        int y = 50;
        font_draw_text("Favorites", 20, y, 0x00ff00);
        y += 30;
        if (game_list_is_loaded()) {
            int count = game_list_count();
            int fav_count = 0;
            for (int i = s_fav.cursor; i < s_fav.cursor + 8 && i < count; i++) {
                game_entry_t *ge = game_list_get(i);
                if (!ge || !ge->favorite) continue;
                const char *prefix = (i == s_fav.cursor) ? " > " : "   ";
                char line[140];
                snprintf(line, sizeof(line), "%s%s", prefix, ge->name[0] ? ge->name : "(unnamed)");
                font_draw_text(line, 20, y + fav_count * 24,
                               (i == s_fav.cursor) ? 0x00ff00 : 0xffffff);
                fav_count++;
            }
            if (fav_count == 0)
                font_draw_text("(no favorites)", 20, y, 0x888888);
        }
        font_draw_text("A=Launch  B=Back  X=Fav  U/D=Browse", 20, y + 8 * 24 + 10, 0x888888);
    }
}
