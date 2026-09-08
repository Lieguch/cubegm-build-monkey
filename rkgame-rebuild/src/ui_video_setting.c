/* ui_video_setting.c — 视频设置 */

#include "ui_video_setting.h"
#include "rkgame.h"
#include "font.h"
#include "debug.h"

#include <string.h>

static ui_video_setting_state_t s_v;

int ui_video_setting_init(void)
{
    memset(&s_v, 0, sizeof(s_v));
    s_v.resolution = 0;
    s_v.refresh = g_cfg.displayfps;
    s_v.scanline = 0;
    s_v.rotation = 0;
    return 0;
}

void ui_video_setting_open(void)  { s_v.open = true; }
void ui_video_setting_close(void) { s_v.open = false; }
bool ui_video_setting_is_open(void) { return s_v.open; }

void ui_video_setting_tick(int keycode)
{
    if (!s_v.open) return;
    #define KEY_OK 0
    #define KEY_CANCEL 1
    #define KEY_LEFT 12
    #define KEY_RIGHT 13

    if (keycode == KEY_CANCEL) { s_v.open = false; return; }
    if (keycode == KEY_OK) { s_v.open = false; return; }
    if (keycode == KEY_LEFT) { s_v.rotation = (s_v.rotation + 270) % 360; }
    else if (keycode == KEY_RIGHT) { s_v.rotation = (s_v.rotation + 90) % 360; }
}

void ui_video_setting_draw(void)
{
    if (!s_v.open) return;
    if (font_is_ready()) {
        int y = 100;
        font_draw_text("Video Settings", 150, y, 0x00ff00);
        y += 30;
        char line[60];
        snprintf(line, sizeof(line), "Refresh: %d Hz", s_v.refresh);
        font_draw_text(line, 150, y, 0xffffff); y += 28;
        snprintf(line, sizeof(line), "Rotation: %d°", s_v.rotation);
        font_draw_text(line, 150, y, 0xffffff); y += 28;
        snprintf(line, sizeof(line), "Scanline: %s", s_v.scanline ? "ON" : "OFF");
        font_draw_text(line, 150, y, 0xffffff); y += 28;
        font_draw_text("B=Back  L/R=Rotate", 150, y + 10, 0x888888);
    }
}
