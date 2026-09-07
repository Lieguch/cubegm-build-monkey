/* ============================================================
 * ui_save_state.h — 存状态界面（对齐原厂 mui_save_state）
 * ============================================================
 *
 * 原厂 mui_save_state @ 0x2f320：
 *   调用 retro_save_state(core, slot) 保存游戏快照到 saves/<game>.slot<N>
 *   支持多槽位（通常 0-4）
 * ============================================================ */

#ifndef UI_SAVE_STATE_H
#define UI_SAVE_STATE_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     slot;             /* 当前槽位 0-4 */
    bool    saved;            /* 保存是否成功 */
} ui_save_state_state_t;

int  ui_save_state_init(void);
void ui_save_state_open(void);
void ui_save_state_close(void);
void ui_save_state_tick(int keycode);
void ui_save_state_draw(void);
bool ui_save_state_is_open(void);
int  ui_save_state_slot(void);

#endif /* UI_SAVE_STATE_H */
