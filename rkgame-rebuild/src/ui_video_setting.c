/* ============================================================
 * ui_video_setting.c — 视频设置（对齐原厂 mui_video_setting）
 * ============================================================ */

#include "ui_video_setting.h"
#include "rkgame.h"
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
void ui_video_setting_tick(int keycode) { (void)keycode; }
void ui_video_setting_draw(void) { (void)s_v; }
