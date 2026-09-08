/* ui_load_state.c — 读状态 */

#include "ui_load_state.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

static ui_load_state_state_t s_ls;

int ui_load_state_init(void) { memset(&s_ls, 0, sizeof(s_ls)); s_ls.slot = 0; return 0; }
void ui_load_state_open(void)  { s_ls.open = true; s_ls.slot = 0; s_ls.loaded = false; }
void ui_load_state_close(void) { s_ls.open = false; }
bool ui_load_state_is_open(void) { return s_ls.open; }

void ui_load_state_tick(int keycode)
{
    if (!s_ls.open) return;
    #define KEY_OK 0
    #define KEY_CANCEL 1
    #define KEY_LEFT 12
    #define KEY_RIGHT 13

    if (keycode == KEY_LEFT && s_ls.slot > 0) s_ls.slot--;
    else if (keycode == KEY_RIGHT && s_ls.slot < 4) s_ls.slot++;
    else if (keycode == KEY_CANCEL) s_ls.open = false;
    else if (keycode == KEY_OK) {
        int rc = sstate_load(s_ls.slot);
        s_ls.loaded = (rc == 0);
        RKLOG_I("ui_load_state: slot=%d rc=%d", s_ls.slot, rc);
        s_ls.open = false;
    }
}

void ui_load_state_draw(void)
{
    if (!s_ls.open) return;
    if (font_is_ready()) {
        int y = 100;
        font_draw_text("Load State", 200, y, 0x00ff00);
        y += 40;
        for (int i = 0; i < 5; i++) {
            const char *prefix = (i == s_ls.slot) ? " > " : "   ";
            char line[40];
            snprintf(line, sizeof(line), "%sSlot %d", prefix, i);
            font_draw_text(line, 200, y + i * 28,
                           (i == s_ls.slot) ? 0x00ff00 : 0xffffff);
        }
        font_draw_text("A=Load  B=Cancel  L/R=Select", 200, y + 5 * 28 + 10, 0x888888);
    }
}
