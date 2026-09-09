/* ui_recent.c — 最近游戏列表 */

#include "ui_recent.h"
#include "ui.h"
#include "font.h"
#include "game_list.h"
#include "debug.h"
#include "rkgame.h"

#include <string.h>

static ui_recent_state_t s_recent;

int ui_recent_init(void) { memset(&s_recent, 0, sizeof(s_recent)); return 0; }
void ui_recent_open(void)  { s_recent.open = true; s_recent.cursor = 0; }
void ui_recent_close(void) { s_recent.open = false; }
bool ui_recent_is_open(void) { return s_recent.open; }

void ui_recent_tick(int keycode)
{
    if (!s_recent.open) return;
    #define KEY_UP 10
    #define KEY_DOWN 11
    #define KEY_OK 0
    #define KEY_CANCEL 1

    int count = game_list_is_loaded() ? game_list_count() : 0;
    if (keycode == KEY_UP && count > 0)
        s_recent.cursor = (s_recent.cursor - 1 + count) % count;
    else if (keycode == KEY_DOWN && count > 0)
        s_recent.cursor = (s_recent.cursor + 1) % count;
    else if (keycode == KEY_CANCEL)
        s_recent.open = false;
    else if (keycode == KEY_OK && count > 0 && s_recent.cursor < count)
        RKLOG_I("ui_recent: launch %d", s_recent.cursor);
}

void ui_recent_draw(void)
{
    if (!s_recent.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_GAME);

    if (font_is_ready()) {
        int y = 50;
        font_draw_text("Recent Games", 20, y, 0x00ff00);
        y += 30;
        if (game_list_is_loaded()) {
            int count = game_list_count();
            for (int i = s_recent.cursor; i < s_recent.cursor + 8 && i < count; i++) {
                game_entry_t *ge = game_list_get(i);
                if (!ge) continue;
                const char *prefix = (i == s_recent.cursor) ? " > " : "   ";
                char line[140];
                snprintf(line, sizeof(line), "%s%s", prefix, ge->name[0] ? ge->name : "(unnamed)");
                font_draw_text(line, 20, y + (i - s_recent.cursor) * 24,
                               (i == s_recent.cursor) ? 0x00ff00 : 0xffffff);
            }
        }
        font_draw_text("A=Launch  B=Back  U/D=Browse", 20, y + 8 * 24 + 10, 0x888888);
    }
}
