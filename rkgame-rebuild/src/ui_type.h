/* ============================================================
 * ui_type.h — 游戏分类界面（对齐原厂 mui_type @ 0x1a3c8）
 * ============================================================
 *
 * 原厂 mui_type @ 0x1a3c8（4.7 KB）：
 *   显示 type.raw 背景，列出所有游戏分类（000-008）
 *   用户按左右键切换分类，按 A 进入该分类游戏列表
 * ============================================================ */

#ifndef UI_TYPE_H
#define UI_TYPE_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;           /* 当前分类索引 */
    int     type_count;       /* 分类数量 */
    char    type_names[10][64]; /* 分类名 */
} ui_type_state_t;

int  ui_type_init(void);
void ui_type_open(void);
void ui_type_close(void);
void ui_type_tick(int keycode);
void ui_type_draw(void);
bool ui_type_is_open(void);
int  ui_type_selected(void);

#endif /* UI_TYPE_H */
