/* ============================================================
 * ui_pause.h — 暂停菜单（对齐原厂 PauseMenu）
 * ============================================================
 *
 * 原厂 PauseMenu @ 0x2ee00：
 *   游戏中按 Start 打开暂停菜单：
 *     - 继续游戏
 *     - 存状态 (Save State)
 *     - 读状态 (Load State)
 *     - 退出游戏
 * ============================================================ */

#ifndef UI_PAUSE_H
#define UI_PAUSE_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;
} ui_pause_state_t;

int  ui_pause_init(void);
void ui_pause_open(void);
void ui_pause_close(void);
void ui_pause_tick(int keycode);
void ui_pause_draw(void);
bool ui_pause_is_open(void);

#endif /* UI_PAUSE_H */
