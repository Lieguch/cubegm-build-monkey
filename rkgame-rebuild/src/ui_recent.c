/* ============================================================
 * ui_recent.c — 最近游戏列表（对齐原厂 mui_recent）
 * ============================================================ */

#include "ui_recent.h"
#include "ui.h"
#include "debug.h"

#include <string.h>

static ui_recent_state_t s_recent;

int ui_recent_init(void) { memset(&s_recent, 0, sizeof(s_recent)); return 0; }
void ui_recent_open(void)  { s_recent.open = true; s_recent.cursor = 0; }
void ui_recent_close(void) { s_recent.open = false; }
bool ui_recent_is_open(void) { return s_recent.open; }

void ui_recent_tick(int keycode) { (void)keycode; }

void ui_recent_draw(void)
{
    if (!s_recent.open) return;
    /* 简化：复用 game.raw 页面显示 */
    if (ui_is_ready()) ui_draw_page(UI_PAGE_GAME);
}
