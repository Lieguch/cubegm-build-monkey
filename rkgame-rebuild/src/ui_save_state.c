/* ============================================================
 * ui_save_state.c — 存状态（对齐原厂 mui_save_state @ 0x2f320）
 * ============================================================ */

#include "ui_save_state.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
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
    /* 简化：左右切换槽位；OK 保存 */
    (void)keycode;
}

void ui_save_state_draw(void)
{
    if (!s_ss.open) return;
    /* 简化：绘制到菜单覆盖层 */
}
