/* ============================================================
 * ui_video_setting.h — 视频设置（对齐原厂 mui_video_setting）
 * ============================================================
 *
 * 原厂 mui_video_setting @ 0x1cb60：
 *   视频参数：分辨率、刷新率、扫描线、旋转
 * ============================================================ */

#ifndef UI_VIDEO_SETTING_H
#define UI_VIDEO_SETTING_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     resolution;   /* 0=1280x720, 1=720x480 */
    int     refresh;      /* 30/60 */
    int     scanline;     /* 0/1 */
    int     rotation;     /* 0/90/180/270 */
} ui_video_setting_state_t;

int  ui_video_setting_init(void);
void ui_video_setting_open(void);
void ui_video_setting_close(void);
void ui_video_setting_tick(int keycode);
void ui_video_setting_draw(void);
bool ui_video_setting_is_open(void);

#endif /* UI_VIDEO_SETTING_H */
