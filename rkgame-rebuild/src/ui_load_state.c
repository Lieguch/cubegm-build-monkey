/* ============================================================
 * ui_load_state.c — 读状态（对齐原厂 mui_load_state @ 0x2f54c）
 * ============================================================ */

#include "ui_load_state.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

static ui_load_state_state_t s_ls;

int ui_load_state_init(void) { memset(&s_ls, 0, sizeof(s_ls)); s_ls.slot = 0; return 0; }
void ui_load_state_open(void)  { s_ls.open = true; s_ls.slot = 0; s_ls.loaded = false; }
void ui_load_state_close(void) { s_ls.open = false; }
bool ui_load_state_is_open(void) { return s_ls.open; }
void ui_load_state_tick(int keycode) { (void)keycode; }
void ui_load_state_draw(void) { (void)s_ls; }
