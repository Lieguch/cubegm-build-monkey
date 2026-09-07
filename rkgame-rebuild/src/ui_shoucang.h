/* ============================================================
 * ui_shoucang.h — 收藏游戏列表（对齐原厂 mui_shoucang）
 * ============================================================
 *
 * 原厂 mui_shoucang @ 0x19f4c：
 *   显示收藏列表（来自 config.xml 中标记 favorite="1" 的游戏）
 *   A 键：运行游戏；Fav 键：切换收藏
 * ============================================================ */

#ifndef UI_SHOUCANG_H
#define UI_SHOUCANG_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;
} ui_shoucang_state_t;

int  ui_shoucang_init(void);
void ui_shoucang_open(void);
void ui_shoucang_close(void);
void ui_shoucang_tick(int keycode);
void ui_shoucang_draw(void);
bool ui_shoucang_is_open(void);

#endif /* UI_SHOUCANG_H */
