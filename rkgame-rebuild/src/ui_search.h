/* ============================================================
 * ui_search.h — 游戏搜索界面（对齐原厂 mui_search）
 * ============================================================
 *
 * 原厂 mui_search @ 0x1a5b0：
 *   显示 search.raw，允许输入搜索关键字
 *   匹配 game_list 中的 name/name_zh，输出结果列表
 *   A 键：进入 mui_search_file_list 显示匹配列表
 * ============================================================ */

#ifndef UI_SEARCH_H
#define UI_SEARCH_H

#include <stdbool.h>

typedef struct {
    bool    open;
    char    query[64];
    int     cursor;           /* 输入光标位置 */
    bool    result_shown;
} ui_search_state_t;

int  ui_search_init(void);
void ui_search_open(void);
void ui_search_close(void);
void ui_search_tick(int keycode);
void ui_search_draw(void);
bool ui_search_is_open(void);

#endif /* UI_SEARCH_H */
