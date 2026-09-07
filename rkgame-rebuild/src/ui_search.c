/* ============================================================
 * ui_search.c — 搜索界面实现（对齐原厂 mui_search）
 * ============================================================ */

#include "ui_search.h"
#include "rkgame.h"
#include "ui.h"
#include "game_list.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <ctype.h>

static ui_search_state_t s_search;

int ui_search_init(void)
{
    memset(&s_search, 0, sizeof(s_search));
    return 0;
}

void ui_search_open(void)  { s_search.open = true;  s_search.cursor = 0; s_search.query[0] = '\0'; }
void ui_search_close(void) { s_search.open = false; }
bool ui_search_is_open(void) { return s_search.open; }

void ui_search_tick(int keycode)
{
    (void)keycode;
    /* 简化：后续接线到 keymap.c 输入 */
}

void ui_search_draw(void)
{
    if (!s_search.open) return;
    if (ui_is_ready()) {
        ui_draw_page(UI_PAGE_SEARCH);
    }
}
