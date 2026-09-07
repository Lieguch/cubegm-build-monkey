/* ============================================================
 * ui_shoucang.c — 收藏列表（对齐原厂 mui_shoucang）
 * ============================================================ */

#include "ui_shoucang.h"
#include "ui.h"
#include "debug.h"

#include <string.h>

static ui_shoucang_state_t s_fav;

int ui_shoucang_init(void) { memset(&s_fav, 0, sizeof(s_fav)); return 0; }
void ui_shoucang_open(void)  { s_fav.open = true; s_fav.cursor = 0; }
void ui_shoucang_close(void) { s_fav.open = false; }
bool ui_shoucang_is_open(void) { return s_fav.open; }
void ui_shoucang_tick(int keycode) { (void)keycode; }

void ui_shoucang_draw(void)
{
    if (!s_fav.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_GAME);
}
