/* ui_save_state.c — 存状态 */

#include "ui_save_state.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

static ui_save_state_state_t s_ss;

int ui_save_state_init(void) { memset(&s_ss, 0, sizeof(s_ss)); s_ss.slot = 0; return 0; }
void ui_save_state_open(void)  { s_ss.open = true; s_ss.slot = 0; s_ss.saved = false; }
void ui_save_state_close(void) { s_ss.open = false; }
bool ui_save_state_is_open(void) { return s_ss.open; }
int  ui_save_state_slot(void) { return s_ss.slot; }

void ui_save_state_tick(int keycode)
{
    if (!s_ss.open) return;
    #define KEY_OK 0
    #define KEY_CANCEL 1
    #define KEY_LEFT 12
    #define KEY_RIGHT 13

    if (keycode == KEY_LEFT && s_ss.slot > 0) s_ss.slot--;
    else if (keycode == KEY_RIGHT && s_ss.slot < 4) s_ss.slot++;
    else if (keycode == KEY_CANCEL) s_ss.open = false;
    else if (keycode == KEY_OK) {
        int rc = sstate_save(s_ss.slot);
        s_ss.saved = (rc == 0);
        RKLOG_I("ui_save_state: slot=%d rc=%d", s_ss.slot, rc);
        s_ss.open = false;
    }
}

void ui_save_state_draw(void)
{
    if (!s_ss.open) return;

    if (font_is_ready()) {
        int y = 100;
        font_draw_text("Save State", 200, y, 0x00ff00);
        y += 40;
        for (int i = 0; i < 5; i++) {
            const char *prefix = (i == s_ss.slot) ? " > " : "   ";
            char line[40];
            snprintf(line, sizeof(line), "%sSlot %d", prefix, i);
            font_draw_text(line, 200, y + i * 28,
                           (i == s_ss.slot) ? 0x00ff00 : 0xffffff);
        }
        font_draw_text("A=Save  B=Cancel  L/R=Select", 200, y + 5 * 28 + 10, 0x888888);
    }
}
