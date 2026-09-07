/* ============================================================
 * ui_setting.c — 设置界面实现（对齐原厂 mui_setting）
 * ============================================================
 *
 * 关键逻辑：
 *   - 打开时读取当前 g_cfg
 *   - 每次修改调用 mui_LoadSetting 写回 setting.xml
 *   - 按 OK 关闭
 * ============================================================ */

#include "ui_setting.h"
#include "rkgame.h"
#include "ui.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static ui_setting_state_t s_setting;

int ui_setting_init(void)
{
    memset(&s_setting, 0, sizeof(s_setting));
    s_setting.volume = g_cfg.volume;
    s_setting.language = g_cfg.m_ui;
    s_setting.defaultlanguage = g_cfg.defaultlanguage;
    s_setting.displayfps = g_cfg.displayfps;
    snprintf(s_setting.ui_filename, sizeof(s_setting.ui_filename), "ui_en.zip");
    snprintf(s_setting.save_dir, sizeof(s_setting.save_dir), "%s",
             save_directory[0] ? save_directory : "saves");
    return 0;
}

void ui_setting_open(void)  { s_setting.open = true; s_setting.cursor = 0; }
void ui_setting_close(void) { s_setting.open = false; }
bool ui_setting_is_open(void) { return s_setting.open; }

void ui_setting_tick(int keycode)
{
    (void)keycode;
    /* 简化：无实际按键映射；后续接线到 keymap.c */
}

void ui_setting_draw(void)
{
    if (!s_setting.open) return;
    /* 简化：先绘制 setting.raw 页面（若已加载） */
    if (ui_is_ready()) {
        ui_draw_page(UI_PAGE_SETTING);
    }
}
