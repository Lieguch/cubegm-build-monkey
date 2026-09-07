/* ============================================================
 * font.h — TTF 字体加载与渲染（P1.2）
 * ============================================================
 *
 * 工厂实证（Ghidra 反编译 mui_InitFont @ 0x1ecac）：
 *   stbtt_InitFont(font, fontbuffer, 0);
 *   fontbuffer = malloc(file_size)，从 work_path/font.ttf 读取
 *   若失败，回退从 ui_*.zip 元素 m_ui+0x16+0x20 读取
 *
 * 本实现：
 *   - font_init() 加载 work_path/font.ttf
 *   - font_draw_text() 使用 stbtt_GetCodepointBitmap 渲染每个字符
 *   - 与 disp_draw_pixel 集成，直接写入 DRM framebuffer
 *   - DRM 不可用或字体加载失败时优雅降级（no-op）
 * ============================================================ */

#ifndef FONT_H
#define FONT_H

#include <stdint.h>
#include <stdbool.h>

/* 字体初始化：从 work_path/font.ttf 加载。
 * 返回 0 成功，-1 失败（字体不可用，调用方应回退到 5x7 位图）。 */
int  font_init(void);

/* 释放字体资源 */
void font_shutdown(void);

/* 字体是否可用 */
bool font_is_ready(void);

/* 绘制文本（XRGB8888 颜色）。
 * 返回绘制后的 x 坐标（advance 后）。 */
int  font_draw_text(int x, int y, const char *text, uint32_t color);

/* 返回文本宽度（像素），不绘制。 */
int  font_text_width(const char *text);

/* 字体高度（像素），由 font_init 时设定，默认 24px */
int  font_pixel_height(void);

#endif /* FONT_H */
