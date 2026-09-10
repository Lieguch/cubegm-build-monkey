/* ============================================================
 * ui_setting.c — 设置界面实现（对齐原厂 mui_setting @ 0x18d78）
 * ============================================================ */

#include "ui_setting.h"
#include "rkgame.h"
#include "ui.h"
#include "ui_config.h"
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
    if (!s_setting.open) return;
    #define KEY_UP 10
    #define KEY_DOWN 11
    #define KEY_OK 0
    #define KEY_CANCEL 1
    #define KEY_LEFT 12
    #define KEY_RIGHT 13

    int items = 5; /* volume, language, defaultlanguage, displayfps, save_dir */
    /* 1:1 原厂 language 值域 = number[] "0".."8"（9 个 <ui> 候选），clamp 到 [0,8] */
    #define LANG_MIN 0
    #define LANG_MAX 8

    if (keycode == KEY_UP) {
        s_setting.cursor = (s_setting.cursor - 1 + items) % items;
    } else if (keycode == KEY_DOWN) {
        s_setting.cursor = (s_setting.cursor + 1) % items;
    } else if (keycode == KEY_LEFT) {
        if (s_setting.cursor == 0 && s_setting.volume > 0) s_setting.volume--;
        else if (s_setting.cursor == 1 && s_setting.language > LANG_MIN) s_setting.language--;
        else if (s_setting.cursor == 2 && s_setting.defaultlanguage > 0) s_setting.defaultlanguage--;
        else if (s_setting.cursor == 3 && s_setting.displayfps > 0) s_setting.displayfps--;
    } else if (keycode == KEY_RIGHT) {
        if (s_setting.cursor == 0 && s_setting.volume < 100) s_setting.volume++;
        else if (s_setting.cursor == 1 && s_setting.language < LANG_MAX) s_setting.language++;
        else if (s_setting.cursor == 2) s_setting.defaultlanguage++;
        else if (s_setting.cursor == 3) s_setting.displayfps++;
    } else if (keycode == KEY_CANCEL) {
        s_setting.open = false;
    } else if (keycode == KEY_OK) {
        /* 保存设置。
         * 1:1 原厂 mui_setting L529-575：language 变更时只写回 <config language="N">
         * （保持 9 个 <ui> 候选块），走 SaveLanguageSetting（字符串原地改
         * language="N" + fsync，不重序列化），绝不用全量重写的 config_save_setting。 */
        if (s_setting.language != g_cfg.m_ui) {
            g_cfg.m_ui = s_setting.language;
            if (SaveLanguageSetting(s_setting.language) == 0) {
                RKLOG_I("ui_setting: language switched to %d (ui_list kept, reload on next boot)",
                        s_setting.language);
            }
        }
        g_cfg.volume = s_setting.volume;
        g_cfg.defaultlanguage = s_setting.defaultlanguage;
        g_cfg.displayfps = s_setting.displayfps;
        RKLOG_I("ui_setting: saved vol=%d lang=%d fps=%d",
                s_setting.volume, s_setting.language, s_setting.displayfps);
        s_setting.open = false;
    }
}

void ui_setting_draw(void)
{
    if (!s_setting.open) return;
    if (ui_is_ready()) ui_draw_page(UI_PAGE_SETTING);

    if (font_is_ready()) {
        int y = 50;
        font_draw_text("Settings", 20, y, 0x00ff00);
        y += 30;

        const char *labels[] = { "Volume", "Language", "Default Lang", "Display FPS", "Save Dir" };
        for (int i = 0; i < 5; i++) {
            const char *prefix = (i == s_setting.cursor) ? " > " : "   ";
            char line[80];
            if (i == 0) snprintf(line, sizeof(line), "%s%s: %d", prefix, labels[i], s_setting.volume);
            else if (i == 1) snprintf(line, sizeof(line), "%s%s: %d", prefix, labels[i], s_setting.language);
            else if (i == 2) snprintf(line, sizeof(line), "%s%s: %d", prefix, labels[i], s_setting.defaultlanguage);
            else if (i == 3) snprintf(line, sizeof(line), "%s%s: %d", prefix, labels[i], s_setting.displayfps);
            else snprintf(line, sizeof(line), "%s%s: %s", prefix, labels[i], s_setting.save_dir);
            font_draw_text(line, 20, y + i * 28,
                           (i == s_setting.cursor) ? 0x00ff00 : 0xffffff);
        }
        font_draw_text("A=Save  B=Cancel  L/R=Adjust  U/D=Select",
                       20, y + 5 * 28 + 10, 0x888888);
    }
}
