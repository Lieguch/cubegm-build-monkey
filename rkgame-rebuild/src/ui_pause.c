/* ============================================================
 * ui_pause.c — 暂停菜单（对齐原厂 PauseMenu @ 0x2ee00）
 * ============================================================ */

#include "ui_pause.h"
#include "rkgame.h"
#include "debug.h"

#include <string.h>

static ui_pause_state_t s_pause;

int ui_pause_init(void) { memset(&s_pause, 0, sizeof(s_pause)); return 0; }
void ui_pause_open(void)  { s_pause.open = true; s_pause.cursor = 0; }
void ui_pause_close(void) { s_pause.open = false; }
bool ui_pause_is_open(void) { return s_pause.open; }
void ui_pause_tick(int keycode) { (void)keycode; }
void ui_pause_draw(void) { (void)s_pause; }
