/* ============================================================
 * font.c — TTF 字体加载与渲染（P1.2）
 * ============================================================
 *
 * 工厂对齐（Ghidra mui_InitFont @ 0x1ecac）：
 *   stbtt_InitFont(font, fontbuffer, 0);
 *   fontbuffer = malloc(file_size)，从 work_path/font.ttf 读取
 *
 * 渲染策略：
 *   - 每个字符独立栅格化（stbtt_GetCodepointBitmap）
 *   - 使用 advance width 做字符间距
 *   - 抗锯齿：alpha 混合到已有 framebuffer 像素
 *   - 默认 24px 字高（在 1280x720 屏幕上清晰可读）
 * ============================================================ */

#include "font.h"
#include "rkgame.h"
#include "debug.h"

#include <stdio.h>
#include <sys/types.h>

/* stb_truetype.h 单次 include（header-only 实现） */
#include "stb_truetype.h"

/* ---- 全局状态 ---- */

static stbtt_fontinfo g_font;
static unsigned char *g_font_data = NULL;   /* malloc'd TTF 文件数据 */
static int            g_font_size = 0;
static int            g_pixel_height = 24;  /* 默认字高 */
static bool           g_font_ready = false;

/* ---- 初始化 ---- */

int font_init(void)
{
    if (g_font_ready) return 0;

    /* 1. 构造路径：work_path + "font.ttf" */
    char path[600];
    snprintf(path, sizeof(path), "%sfont.ttf", work_path);

    /* 2. 读取文件 */
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        /* 回退：尝试 /mnt/sdcard/cubegm/font.ttf（真机挂载点） */
        snprintf(path, sizeof(path), "/mnt/sdcard/cubegm/font.ttf");
        fp = fopen(path, "rb");
    }
    if (!fp) {
        ERR("font_init: cannot open font.ttf (tried %s and /mnt/sdcard/cubegm/font.ttf)",
            work_path);
        return -1;
    }

    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize <= 0 || fsize > 16 * 1024 * 1024) {
        ERR("font_init: invalid font.ttf size = %ld", fsize);
        fclose(fp);
        return -1;
    }

    g_font_data = (unsigned char *)malloc((size_t)fsize);
    if (!g_font_data) {
        ERR("font_init: malloc %ld failed", fsize);
        fclose(fp);
        return -1;
    }

    size_t nread = fread(g_font_data, 1, (size_t)fsize, fp);
    fclose(fp);
    if ((long)nread != fsize) {
        ERR("font_init: fread read %zu of %ld", nread, fsize);
        free(g_font_data);
        g_font_data = NULL;
        return -1;
    }

    /* 3. stbtt_InitFont（工厂一致：offset=0） */
    if (!stbtt_InitFont(&g_font, g_font_data, 0)) {
        ERR("font_init: stbtt_InitFont failed (not a valid TTF?)");
        free(g_font_data);
        g_font_data = NULL;
        return -1;
    }

    g_font_size = fsize;
    g_font_ready = true;
    LOG("font_init: loaded %s (%ld bytes), %d glyphs, pixel_height=%d",
        path, fsize, g_font.numGlyphs, g_pixel_height);
    return 0;
}

void font_shutdown(void)
{
    if (g_font_data) {
        free(g_font_data);
        g_font_data = NULL;
    }
    g_font_ready = false;
    g_font_size = 0;
}

bool font_is_ready(void) { return g_font_ready; }

int font_pixel_height(void) { return g_pixel_height; }

/* ---- 文本宽度测量 ---- */

int font_text_width(const char *text)
{
    if (!g_font_ready || !text) return 0;

    float scale = stbtt_ScaleForPixelHeight(&g_font, (float)g_pixel_height);
    int total = 0;

    for (const char *p = text; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (c == '\t') { total += 4 * g_pixel_height; continue; }
        int advance;
        stbtt_GetCodepointHMetrics(&g_font, (int)c, &advance, NULL);
        total += (int)(advance * scale + 0.5f);
    }
    return total;
}

/* ---- 文本绘制 ---- */

int font_draw_text(int x, int y, const char *text, uint32_t color)
{
    if (!g_font_ready || !text) return x;

    float scale = stbtt_ScaleForPixelHeight(&g_font, (float)g_pixel_height);

    for (const char *p = text; *p; p++) {
        unsigned char c = (unsigned char)*p;

        if (c == '\t') {
            x += 4 * g_pixel_height;
            continue;
        }
        if (c == '\n') {
            x = 0;
            y += g_pixel_height + 4;
            continue;
        }

        /* 1. 获取字形位图（灰度，1 byte/pixel） */
        int w, h, x0, y0;
        unsigned char *bmp = stbtt_GetCodepointBitmap(
            &g_font, 0, scale, (int)c, &w, &h, &x0, &y0);
        if (!bmp) {
            int advance;
            stbtt_GetCodepointHMetrics(&g_font, (int)c, &advance, NULL);
            x += (int)(advance * scale + 0.5f);
            continue;
        }

        /* 2. 渲染到 framebuffer（alpha 混合到现有像素） */
        for (int row = 0; row < h; row++) {
            for (int col = 0; col < w; col++) {
                unsigned char a = bmp[row * w + col];
                if (a == 0) continue;

                int px = x + x0 + col;
                int py = y + y0 + row;

                /* 边界检查（通过 disp_draw_pixel 内部已检查，但提前跳过更快） */
                /* 直接调用 disp_draw_pixel，它内部会检查边界 */
                if (a >= 255) {
                    /* 完全不透明：直接写颜色 */
                    disp_draw_pixel(px, py, color);
                } else {
                    /* 半透明：与现有像素混合 */
                    /* 为简单起见，先读后写。但 disp 没有 read 接口，
                     * 所以这里用近似：将颜色按 alpha 比例调制后写入。
                     * 这在深色背景上效果良好，浅色背景可能略暗。 */
                    uint32_t bg = 0x00000000u; /* 假设黑色背景 */
                    uint8_t r = (uint8_t)((color >> 16) & 0xff);
                    uint8_t g = (uint8_t)((color >> 8) & 0xff);
                    uint8_t b = (uint8_t)(color & 0xff);
                    uint8_t bg_r = (uint8_t)((bg >> 16) & 0xff);
                    uint8_t bg_g = (uint8_t)((bg >> 8) & 0xff);
                    uint8_t bg_b = (uint8_t)(bg & 0xff);
                    uint8_t nr = (uint8_t)((r * a + bg_r * (255 - a)) / 255);
                    uint8_t ng = (uint8_t)((g * a + bg_g * (255 - a)) / 255);
                    uint8_t nb = (uint8_t)((b * a + bg_b * (255 - a)) / 255);
                    uint32_t blended = (uint32_t)nr | ((uint32_t)ng << 8) | ((uint32_t)nb << 16);
                    disp_draw_pixel(px, py, blended);
                }
            }
        }

        /* 3. 释放位图（stb 分配） */
        free(bmp);

        /* 4. 前进到下一个字符（用 advance width） */
        int advance;
        stbtt_GetCodepointHMetrics(&g_font, (int)c, &advance, NULL);
        x += (int)(advance * scale + 0.5f);
    }

    return x;
}
