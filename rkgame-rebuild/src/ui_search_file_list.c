/* ============================================================
 * ui_search_file_list.c — 搜索列表（对齐原厂 mui_search_file_list）
 * ============================================================ */

#include "ui_search_file_list.h"
#include "ui.h"
#include "debug.h"

#include <string.h>

static ui_search_file_list_state_t s_sfl;

int ui_search_file_list_init(void) { memset(&s_sfl, 0, sizeof(s_sfl)); return 0; }
void ui_search_file_list_open(const char *query)
{
    s_sfl.open = true;
    s_sfl.cursor = 0;
    if (query) snprintf(s_sfl.query, sizeof(s_sfl.query), "%s", query);
}
void ui_search_file_list_close(void) { s_sfl.open = false; }
bool ui_search_file_list_is_open(void) { return s_sfl.open; }
void ui_search_file_list_tick(int keycode) { (void)keycode; }

void ui_search_file_list_draw(void)
{
    if (!s_sfl.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_SEARCH);
}
