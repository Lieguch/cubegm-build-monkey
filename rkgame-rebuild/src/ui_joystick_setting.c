/* ui_joystick_setting.c — 手柄映射 */

#include "ui_joystick_setting.h"
#include "font.h"
#include "debug.h"
#include "rkgame.h"

#include <string.h>

static ui_joystick_setting_state_t s_js;

int ui_joystick_setting_init(void) { memset(&s_js, 0, sizeof(s_js)); return 0; }
void ui_joystick_setting_open(void)  { s_js.open = true; s_js.cursor = 0; s_js.profile_index = 0; }
void ui_joystick_setting_close(void) { s_js.open = false; }
bool ui_joystick_setting_is_open(void) { return s_js.open; }

void ui_joystick_setting_tick(int keycode)
{
    if (!s_js.open) return;
    /* P1-1: 统一原厂事件码 bitmask */
    #define FK_UP     0x10
    #define FK_DOWN   0x40
    #define FK_A      0x2000
    #define FK_B      0x4000
    #define FK_LEFT   0x80
    #define FK_RIGHT  0x20

    int profiles = 4;
    if (keycode & FK_UP) s_js.cursor = (s_js.cursor - 1 + profiles) % profiles;
    else if (keycode & FK_DOWN) s_js.cursor = (s_js.cursor + 1) % profiles;
    else if (keycode & FK_LEFT) s_js.profile_index = (s_js.profile_index - 1 + 3) % 3;
    else if (keycode & FK_RIGHT) s_js.profile_index = (s_js.profile_index + 1) % 3;
    else if (keycode & FK_B) s_js.open = false;
    else if (keycode & FK_A) {
        RKLOG_I("ui_joystick: profile=%d btn=%d", s_js.profile_index, s_js.cursor);
        s_js.open = false;
    }
}

void ui_joystick_setting_draw(void)
{
    if (!s_js.open) return;
    if (font_is_ready()) {
        int y = 60;
        font_draw_text("Joystick Mapping", 20, y, 0x00ff00); y += 30;
        const char *btns[] = {"A", "B", "X", "Y", "L", "R", "START", "SELECT", "UP", "DOWN", "LEFT", "RIGHT"};
        for (int i = 0; i < 12; i++) {
            const char *prefix = (i == s_js.cursor) ? " > " : "   ";
            char line[60];
            snprintf(line, sizeof(line), "%s%s -> Button %d", prefix, btns[i], s_js.cursor);
            font_draw_text(line, 20, y + i * 24,
                           (i == s_js.cursor) ? 0x00ff00 : 0xffffff);
        }
        font_draw_text("A=Save  B=Back  U/D=Btn  L/R=Profile", 20, y + 12 * 24 + 10, 0x888888);
    }
}
