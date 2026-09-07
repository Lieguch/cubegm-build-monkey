/* ============================================================
 * ui_recent.h — 最近游戏列表（对齐原厂 mui_recent）
 * ============================================================
 *
 * 原厂 mui_recent @ 0x1a9b8：
 *   显示最近玩过的游戏列表（来自 saves/ 目录最近修改的 .srm）
 *   A 键：跳转运行对应游戏
 * ============================================================ */

#ifndef UI_RECENT_H
#define UI_RECENT_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;
} ui_recent_state_t;

int  ui_recent_init(void);
void ui_recent_open(void);
void ui_recent_close(void);
void ui_recent_tick(int keycode);
void ui_recent_draw(void);
bool ui_recent_is_open(void);

#endif /* UI_RECENT_H */
