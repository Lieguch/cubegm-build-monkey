/* ============================================================
 * ui_joystick_setting.h — 手柄映射设置（对齐原厂 mui_joystick_setting）
 * ============================================================
 *
 * 原厂 mui_joystick_setting @ 0x1d3a8：
 *   编辑 joystick.zip 中的手柄 profile（VID_PID_REV → 按钮映射）
 *   用户可按 A/B/X/Y/方向键 输入当前按键映射
 * ============================================================ */

#ifndef UI_JOYSTICK_SETTING_H
#define UI_JOYSTICK_SETTING_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;         /* 当前编辑的按钮索引 (0-20) */
    int     profile_index;  /* 当前编辑的 profile 索引 */
} ui_joystick_setting_state_t;

int  ui_joystick_setting_init(void);
void ui_joystick_setting_open(void);
void ui_joystick_setting_close(void);
void ui_joystick_setting_tick(int keycode);
void ui_joystick_setting_draw(void);
bool ui_joystick_setting_is_open(void);

#endif /* UI_JOYSTICK_SETTING_H */
