/* ============================================================
 * ui_joystick_setting.c — 手柄映射（对齐原厂 mui_joystick_setting）
 * ============================================================ */

#include "ui_joystick_setting.h"
#include "debug.h"

#include <string.h>

static ui_joystick_setting_state_t s_js;

int ui_joystick_setting_init(void) { memset(&s_js, 0, sizeof(s_js)); return 0; }
void ui_joystick_setting_open(void)  { s_js.open = true; s_js.cursor = 0; s_js.profile_index = 0; }
void ui_joystick_setting_close(void) { s_js.open = false; }
bool ui_joystick_setting_is_open(void) { return s_js.open; }
void ui_joystick_setting_tick(int keycode) { (void)keycode; }
void ui_joystick_setting_draw(void) { (void)s_js; }
