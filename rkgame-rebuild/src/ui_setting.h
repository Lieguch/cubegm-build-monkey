/* ============================================================
 * ui_setting.h — 设置界面（对齐原厂 mui_setting）
 * ============================================================
 *
 * 原厂 mui_setting @ 0x18d78：
 *   显示 setting.raw，允许修改：
 *     - volume (0-100)
 *     - language (0=zh-CN, 1=zh-TW, 2=ja-JP, 3=en-US)
 *     - defaultlanguage
 *     - displayfps (30/60)
 *     - ui filename (selected_ui_zip)
 *     - save_directory
 *
 *   修改后调用 mui_LoadSetting 保存回 setting.xml
 * ============================================================ */

#ifndef UI_SETTING_H
#define UI_SETTING_H

#include <stdbool.h>

/* 设置界面状态 */
typedef struct {
    bool    open;           /* 界面是否打开 */
    int     cursor;         /* 当前编辑项 (0=volume, 1=language, ...) */
    int     volume;
    int     language;
    int     defaultlanguage;
    int     displayfps;
    char    ui_filename[64];
    char    save_dir[128];
} ui_setting_state_t;

int  ui_setting_init(void);
void ui_setting_open(void);
void ui_setting_close(void);
void ui_setting_tick(int keycode);   /* 处理按键 */
void ui_setting_draw(void);
bool ui_setting_is_open(void);

#endif /* UI_SETTING_H */
