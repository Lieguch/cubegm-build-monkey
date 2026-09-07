/* ============================================================
 * ui_load_state.h — 读状态界面（对齐原厂 mui_load_state）
 * ============================================================
 *
 * 原厂 mui_load_state @ 0x2f54c：
 *   从 saves/<game>.slot<N> 读取快照到 retro_load_state
 * ============================================================ */

#ifndef UI_LOAD_STATE_H
#define UI_LOAD_STATE_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     slot;
    bool    loaded;
} ui_load_state_state_t;

int  ui_load_state_init(void);
void ui_load_state_open(void);
void ui_load_state_close(void);
void ui_load_state_tick(int keycode);
void ui_load_state_draw(void);
bool ui_load_state_is_open(void);

#endif /* UI_LOAD_STATE_H */
