/* ui_pause.c — 暂停菜单 */

#include "ui_pause.h"
#include "rkgame.h"
#include "font.h"
#include "debug.h"

#include <string.h>

static ui_pause_state_t s_pause;

int ui_pause_init(void) { memset(&s_pause, 0, sizeof(s_pause)); return 0; }
void ui_pause_open(void)  { s_pause.open = true; s_pause.cursor = 0; }
void ui_pause_close(void) { s_pause.open = false; }
bool ui_pause_is_open(void) { return s_pause.open; }

void ui_pause_tick(int keycode)
{
    if (!s_pause.open) return;
    #define KEY_UP 10
    #define KEY_DOWN 11
    #define KEY_OK 0
    #define KEY_CANCEL 1

    int items = 4; /* Resume, Save, Load, Quit */
    if (keycode == KEY_UP) s_pause.cursor = (s_pause.cursor - 1 + items) % items;
    else if (keycode == KEY_DOWN) s_pause.cursor = (s_pause.cursor + 1) % items;
    else if (keycode == KEY_CANCEL) s_pause.open = false;
    else if (keycode == KEY_OK) {
        switch (s_pause.cursor) {
        case 0: s_pause.open = false; break; /* Resume */
        case 1: /* Save State — 触发 ui_save_state */ break;
        case 2: /* Load State — 触发 ui_load_state */ break;
        case 3: /* Quit to menu */ break;
        }
        RKLOG_I("ui_pause: action=%d", s_pause.cursor);
    }
}

void ui_pause_draw(void)
{
    if (!s_pause.open) return;
    if (font_is_ready()) {
        int y = 200;
        font_draw_text("Paused", 300, y, 0x00ff00); y += 40;
        const char *items[] = {"Resume", "Save State", "Load State", "Quit to Menu"};
        for (int i = 0; i < 4; i++) {
            const char *prefix = (i == s_pause.cursor) ? " > " : "   ";
            char line[60];
            snprintf(line, sizeof(line), "%s%s", prefix, items[i]);
            font_draw_text(line, 300, y + i * 30,
                           (i == s_pause.cursor) ? 0x00ff00 : 0xffffff);
        }
        font_draw_text("A=Select  B=Close  U/D=Browse", 300, y + 4 * 30 + 10, 0x888888);
    }
}
