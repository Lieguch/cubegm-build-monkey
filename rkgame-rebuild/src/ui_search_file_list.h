/* ============================================================
 * ui_search_file_list.h — 搜索结果列表（对齐原厂 mui_search_file_list）
 * ============================================================
 *
 * 原厂 mui_search_file_list @ 0x1b170：
 *   根据搜索关键字遍历 ROM 目录，列出匹配文件
 *   A 键：运行对应 ROM
 * ============================================================ */

#ifndef UI_SEARCH_FILE_LIST_H
#define UI_SEARCH_FILE_LIST_H

#include <stdbool.h>

typedef struct {
    bool    open;
    char    query[64];
    int     cursor;
} ui_search_file_list_state_t;

int  ui_search_file_list_init(void);
void ui_search_file_list_open(const char *query);
void ui_search_file_list_close(void);
void ui_search_file_list_tick(int keycode);
void ui_search_file_list_draw(void);
bool ui_search_file_list_is_open(void);

#endif /* UI_SEARCH_FILE_LIST_H */
