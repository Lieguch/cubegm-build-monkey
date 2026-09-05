/* ============================================================
 * rkgame-rebuild — DRM/KMS framebuffer + 最小文本菜单
 * ============================================================
 *
 * 目标：
 *   1. 用 /dev/dri/card0 + dumb-buffer 方案打开 DRM/KMS 输出
 *   2. 提供 disp_flip() 给 libretro 核心的 video_refresh 回调
 *   3. 提供 disp_draw_text() 给菜单渲染（5x7 位图字体）
 *   4. 当 DRM 不可用（qemu、无显示器、权限不足）时优雅降级为
 *      log-only 模式，绝不崩溃
 *
 * 依赖：
 *   - libdrm-dev  (xf86drm.h, xf86drmMode.h)
 *   - linux-libc-dev  (linux/drm.h, linux/drm_mode.h)
 *   - 编译期通过 #if __has_include("xf86drm.h") 决定是否启用 DRM
 *
 * 输出模式：
 *   - 首选 1280x720（设备原厂 UI 分辨率）
 *   - 回退：任意 >=640x480 的已连接模式
 *   - 像素格式：DRM_FORMAT_XRGB8888（32-bit，little-endian）
 * ============================================================ */

#if defined(__has_include)
#  if __has_include("xf86drm.h")
#    define HAVE_DRM 1
#  endif
#endif

#ifndef HAVE_DRM
#define HAVE_DRM 0
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <sys/select.h>

#if HAVE_DRM
#include <xf86drm.h>
#include <xf86drmMode.h>
#endif

#include "rkgame.h"
#include "debug.h"

/* ---- 全局状态 ---- */

static int      g_dri_fd     = -1;
static uint32_t g_crtc_id    = 0;
static uint32_t g_connector_id = 0;
static uint32_t g_fb_id      = 0;
static uint32_t g_bo_handle  = 0;
static int      g_fb_w       = 0;
static int      g_fb_h       = 0;
static int      g_fb_pitch   = 0;
static void    *g_fb_mem     = NULL;
static bool     g_drm_ready  = false;

#if HAVE_DRM
static drmModeModeInfo g_mode;
#endif

/* ---- 5x7 位图字体（ASCII 32-126） ----
 * 每字符 7 字节（7 行），每字节低 5 位 = 5 列像素
 */
static const unsigned char font_5x7[] = {
    0x00,0x00,0x00,0x00,0x00,0x00,0x00, /* 32 ' ' */
    0x00,0x00,0x5F,0x00,0x00,0x00,0x00, /* 33 '!' */
    0x00,0x07,0x00,0x07,0x00,0x00,0x00, /* 34 '"' */
    0x00,0x14,0x7F,0x14,0x7F,0x14,0x00, /* 35 '#' */
    0x00,0x24,0x2A,0x7F,0x2A,0x12,0x00, /* 36 '$' */
    0x00,0x23,0x13,0x08,0x64,0x62,0x00, /* 37 '%' */
    0x00,0x36,0x49,0x55,0x22,0x50,0x00, /* 38 '&' */
    0x00,0x05,0x03,0x00,0x05,0x03,0x00, /* 39 '\'' */
    0x00,0x1C,0x22,0x41,0x41,0x82,0x00, /* 40 '(' */
    0x00,0x41,0x22,0x1C,0x41,0x22,0x00, /* 41 ')' */
    0x00,0x14,0x08,0x3E,0x08,0x14,0x00, /* 42 '*' */
    0x00,0x08,0x08,0x3E,0x08,0x08,0x00, /* 43 '+' */
    0x00,0x80,0x60,0x00,0x20,0x10,0x00, /* 44 ',' */
    0x00,0x08,0x08,0x08,0x08,0x08,0x00, /* 45 '-' */
    0x00,0x60,0x60,0x00,0x00,0x00,0x00, /* 46 '.' */
    0x00,0x20,0x10,0x08,0x04,0x02,0x00, /* 47 '/' */
    0x00,0x3E,0x51,0x49,0x45,0x3E,0x00, /* 48 '0' */
    0x00,0x00,0x42,0x7F,0x40,0x00,0x00, /* 49 '1' */
    0x00,0x42,0x61,0x51,0x49,0x46,0x00, /* 50 '2' */
    0x00,0x21,0x41,0x45,0x4B,0x31,0x00, /* 51 '3' */
    0x00,0x18,0x14,0x12,0x7F,0x10,0x00, /* 52 '4' */
    0x00,0x27,0x45,0x45,0x45,0x39,0x00, /* 53 '5' */
    0x00,0x3C,0x4A,0x49,0x49,0x30,0x00, /* 54 '6' */
    0x00,0x01,0x71,0x09,0x05,0x03,0x00, /* 55 '7' */
    0x00,0x36,0x49,0x49,0x49,0x36,0x00, /* 56 '8' */
    0x00,0x06,0x49,0x49,0x29,0x1E,0x00, /* 57 '9' */
    0x00,0x00,0x36,0x36,0x00,0x00,0x00, /* 58 ':' */
    0x00,0x00,0x56,0x36,0x00,0x00,0x00, /* 59 ';' */
    0x00,0x08,0x14,0x22,0x41,0x00,0x00, /* 60 '<' */
    0x00,0x14,0x14,0x14,0x14,0x14,0x00, /* 61 '=' */
    0x00,0x00,0x41,0x22,0x14,0x08,0x00, /* 62 '>' */
    0x00,0x02,0x01,0x51,0x09,0x06,0x00, /* 63 '?' */
    0x00,0x32,0x49,0x79,0x41,0x3E,0x00, /* 64 '@' */
    0x00,0x7E,0x11,0x11,0x11,0x7E,0x00, /* 65 'A' */
    0x00,0x7F,0x49,0x49,0x49,0x36,0x00, /* 66 'B' */
    0x00,0x3E,0x41,0x41,0x41,0x22,0x00, /* 67 'C' */
    0x00,0x7F,0x41,0x41,0x22,0x1C,0x00, /* 68 'D' */
    0x00,0x7F,0x49,0x49,0x49,0x41,0x00, /* 69 'E' */
    0x00,0x7F,0x09,0x09,0x09,0x01,0x00, /* 70 'F' */
    0x00,0x3E,0x41,0x49,0x49,0x7A,0x00, /* 71 'G' */
    0x00,0x7F,0x08,0x08,0x08,0x7F,0x00, /* 72 'H' */
    0x00,0x00,0x41,0x7F,0x41,0x00,0x00, /* 73 'I' */
    0x00,0x20,0x40,0x41,0x3F,0x01,0x00, /* 74 'J' */
    0x00,0x7F,0x08,0x14,0x22,0x41,0x00, /* 75 'K' */
    0x00,0x7F,0x40,0x40,0x40,0x40,0x00, /* 76 'L' */
    0x00,0x7F,0x02,0x0C,0x02,0x7F,0x00, /* 77 'M' */
    0x00,0x7F,0x04,0x08,0x10,0x7F,0x00, /* 78 'N' */
    0x00,0x7F,0x02,0x02,0x02,0x7F,0x00, /* 79 'O' */
    0x00,0x7F,0x09,0x09,0x09,0x06,0x00, /* 80 'P' */
    0x00,0x7F,0x02,0x04,0x08,0x7F,0x00, /* 81 'Q' */
    0x00,0x7F,0x09,0x19,0x29,0x46,0x00, /* 82 'R' */
    0x00,0x46,0x49,0x49,0x49,0x31,0x00, /* 83 'S' */
    0x00,0x01,0x01,0x7F,0x01,0x01,0x00, /* 84 'T' */
    0x00,0x3F,0x40,0x40,0x40,0x3F,0x00, /* 85 'U' */
    0x00,0x1F,0x20,0x40,0x20,0x1F,0x00, /* 86 'V' */
    0x00,0x3F,0x40,0x38,0x40,0x3F,0x00, /* 87 'W' */
    0x00,0x63,0x14,0x08,0x14,0x63,0x00, /* 88 'X' */
    0x00,0x03,0x04,0x78,0x04,0x03,0x00, /* 89 'Y' */
    0x00,0x61,0x51,0x49,0x45,0x43,0x00, /* 90 'Z' */
    0x00,0x00,0x7F,0x41,0x41,0x00,0x00, /* 91 '[' */
    0x00,0x02,0x04,0x08,0x10,0x20,0x00, /* 92 '\' */
    0x00,0x00,0x41,0x41,0x7F,0x00,0x00, /* 93 ']' */
    0x00,0x04,0x02,0x01,0x02,0x04,0x00, /* 94 '^' */
    0x00,0x40,0x40,0x40,0x40,0x40,0x00, /* 95 '_' */
    0x00,0x00,0x01,0x02,0x04,0x00,0x00, /* 96 '`' */
    0x00,0x20,0x54,0x54,0x54,0x78,0x00, /* 97 'a' */
    0x00,0x7F,0x48,0x44,0x44,0x38,0x00, /* 98 'b' */
    0x00,0x38,0x44,0x44,0x44,0x20,0x00, /* 99 'c' */
    0x00,0x38,0x44,0x44,0x48,0x7F,0x00, /* 100 'd' */
    0x00,0x38,0x54,0x54,0x54,0x18,0x00, /* 101 'e' */
    0x00,0x08,0x7E,0x09,0x01,0x02,0x00, /* 102 'f' */
    0x00,0x18,0x54,0x54,0x54,0x7C,0x00, /* 103 'g' */
    0x00,0x7F,0x08,0x04,0x04,0x78,0x00, /* 104 'h' */
    0x00,0x00,0x44,0x7D,0x40,0x00,0x00, /* 105 'i' */
    0x00,0x20,0x40,0x44,0x3D,0x00,0x00, /* 106 'j' */
    0x00,0x7F,0x10,0x28,0x44,0x00,0x00, /* 107 'k' */
    0x00,0x00,0x41,0x7F,0x40,0x00,0x00, /* 108 'l' */
    0x00,0x7C,0x04,0x18,0x04,0x7C,0x00, /* 109 'm' */
    0x00,0x7C,0x08,0x04,0x04,0x78,0x00, /* 110 'n' */
    0x00,0x38,0x44,0x44,0x44,0x38,0x00, /* 111 'o' */
    0x00,0x7C,0x14,0x14,0x14,0x08,0x00, /* 112 'p' */
    0x00,0x08,0x14,0x14,0x18,0x7C,0x00, /* 113 'q' */
    0x00,0x7C,0x08,0x04,0x04,0x08,0x00, /* 114 'r' */
    0x00,0x48,0x54,0x54,0x54,0x20,0x00, /* 115 's' */
    0x00,0x04,0x3F,0x44,0x40,0x20,0x00, /* 116 't' */
    0x00,0x3C,0x40,0x40,0x20,0x7C,0x00, /* 117 'u' */
    0x00,0x1C,0x20,0x40,0x20,0x1C,0x00, /* 118 'v' */
    0x00,0x3C,0x40,0x30,0x40,0x3C,0x00, /* 119 'w' */
    0x00,0x44,0x28,0x10,0x28,0x44,0x00, /* 120 'x' */
    0x00,0x0C,0x50,0x50,0x50,0x3C,0x00, /* 121 'y' */
    0x00,0x44,0x64,0x54,0x4C,0x44,0x00, /* 122 'z' */
    0x00,0x08,0x36,0x41,0x36,0x08,0x00, /* 123 '{' */
    0x00,0x00,0x7F,0x7F,0x00,0x00,0x00, /* 124 '|' */
    0x00,0x08,0x41,0x36,0x08,0x08,0x00, /* 125 '}' */
    0x00,0x08,0x04,0x08,0x04,0x08,0x00, /* 126 '~' */
};

/* ---- 颜色（XRGB8888, little-endian） ---- */
#define CLR_BLACK   0x00000000u
#define CLR_WHITE   0xFF000000u
#define CLR_GRAY    0xFF808080u
#define CLR_RED     0xFF0000FFu
#define CLR_GREEN   0xFF00FF00u
#define CLR_BLUE    0xFFFF0000u
#define CLR_YELLOW  0xFF00FFFFu
#define CLR_CYAN    0xFFFF00FFu

/* ============================================================
 * DRM/KMS 初始化
 * ============================================================ */

#if HAVE_DRM

static int drm_cleanup(void)
{
    if (g_fb_mem) {
        munmap(g_fb_mem, (size_t)g_fb_pitch * g_fb_h);
        g_fb_mem = NULL;
    }
    if (g_fb_id && g_dri_fd >= 0) {
        drmModeRmFB(g_dri_fd, g_fb_id);
        g_fb_id = 0;
    }
    if (g_bo_handle && g_dri_fd >= 0) {
        struct drm_mode_destroy_dumb dm = { .handle = g_bo_handle };
        ioctl(g_dri_fd, DRM_IOCTL_MODE_DESTROY_DUMB, &dm);
        g_bo_handle = 0;
    }
    if (g_dri_fd >= 0) {
        close(g_dri_fd);
        g_dri_fd = -1;
    }
    g_crtc_id = 0;
    g_connector_id = 0;
    g_fb_w = g_fb_h = g_fb_pitch = 0;
    g_drm_ready = false;
    return 0;
}

static int drm_find_connector(void)
{
    drmModeRes *res = drmModeGetResources(g_dri_fd);
    if (!res) {
        ERR("drm: GetResources failed: %s", strerror(errno));
        return -1;
    }

    int best = -1;
    for (int i = 0; i < res->count_connectors; i++) {
        drmModeConnector *conn = drmModeGetConnector(g_dri_fd, res->connectors[i]);
        if (!conn) continue;

        if (conn->connector_status != DRM_MODE_CONNECTED) {
            drmModeFreeConnector(conn);
            continue;
        }
        if (conn->count_modes == 0) {
            drmModeFreeConnector(conn);
            continue;
        }

        /* 找最佳模式：首选 1280x720，回退任意 >=640x480 */
        int best_mode = -1;
        int best_score = 0;
        for (int m = 0; m < conn->count_modes; m++) {
            unsigned w = conn->modes[m].hdisplay;
            unsigned h = conn->modes[m].vdisplay;
            if (w < 640 || h < 480) continue;
            int score = 0;
            if (w == 1280 && h == 720) score = 100;
            else if (w == 1920 && h == 1080) score = 90;
            else if (w == 1280 && h == 800) score = 80;
            else if (w == 1024 && h == 768) score = 70;
            else if (w >= 640 && h >= 480) score = 50;
            if (score > best_score) {
                best_score = score;
                best_mode = m;
            }
        }
        if (best_mode < 0) {
            drmModeFreeConnector(conn);
            continue;
        }

        g_connector_id = conn->connector_id;
        g_mode = conn->modes[best_mode];
        g_fb_w = g_mode.hdisplay;
        g_fb_h = g_mode.vdisplay;

        /* 找 encoder → CRTC */
        if (conn->encoder_id) {
            drmModeEncoder *enc = drmModeGetEncoder(g_dri_fd, conn->encoder_id);
            if (enc) {
                g_crtc_id = enc->crtc_id;
                drmModeFreeEncoder(enc);
            }
        }

        drmModeFreeConnector(conn);
        best = best_mode;
        break;
    }

    drmModeFreeResources(res);
    return (g_connector_id && g_crtc_id) ? 0 : -1;
}

int disp_init(void)
{
    g_dri_fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (g_dri_fd < 0) {
        ERR("disp_init: /dev/dri/card0: %s", strerror(errno));
        return -1;
    }

    if (drm_find_connector() < 0) {
        ERR("disp_init: no connected HDMI/TV connector with suitable mode");
        close(g_dri_fd);
        g_dri_fd = -1;
        return -1;
    }

    LOG("disp_init: mode %ux%u @%uHz crtc=%u conn=%u",
        g_fb_w, g_fb_h, g_mode.vrefresh, g_crtc_id, g_connector_id);

    /* 创建 dumb buffer */
    struct drm_mode_create_dumb crm = { 0 };
    crm.width  = (uint32_t)g_fb_w;
    crm.height = (uint32_t)g_fb_h;
    crm.bpp    = 32;
    if (ioctl(g_dri_fd, DRM_IOCTL_MODE_CREATE_DUMB, &crm) < 0) {
        ERR("disp_init: CREATE_DUMB failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }
    g_bo_handle = crm.handle;

    /* 映射 dumb buffer */
    struct drm_mode_map_dumb map = { 0 };
    map.handle = crm.handle;
    if (ioctl(g_dri_fd, DRM_IOCTL_MODE_MAP_DUMB, &map) < 0) {
        ERR("disp_init: MAP_DUMB failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }

    size_t map_size = (size_t)crm.pitches[0] * (size_t)g_fb_h;
    g_fb_mem = mmap(NULL, map_size, PROT_READ | PROT_WRITE,
                    MAP_SHARED, g_dri_fd, map.offset);
    if (g_fb_mem == MAP_FAILED) {
        ERR("disp_init: mmap failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }
    g_fb_pitch = (int)crm.pitches[0];

    /* 创建 framebuffer */
    struct drm_mode_addfb2 addfb = { 0 };
    addfb.handle       = crm.handle;
    addfb.width        = (uint32_t)g_fb_w;
    addfb.height       = (uint32_t)g_fb_h;
    addfb.pixel_format = DRM_FORMAT_XRGB8888;
    addfb.pitch[0]     = (uint32_t)g_fb_pitch;
    addfb.offset[0]    = 0;
    if (ioctl(g_dri_fd, DRM_IOCTL_MODE_ADDFB2, &addfb) < 0) {
        ERR("disp_init: ADDFB2 failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }
    g_fb_id = addfb.fb_id;

    /* 启用 CRTC */
    if (drmModeSetCrtc(g_dri_fd, g_crtc_id, g_fb_id, 0, 0,
                       &g_connector_id, 1, &g_mode) < 0) {
        ERR("disp_init: SetCrtc failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }

    g_drm_ready = true;
    LOG("disp_init: DRM/KMS ready %dx%d pitch=%d crtc=%u conn=%u",
        g_fb_w, g_fb_h, g_fb_pitch, g_crtc_id, g_connector_id);
    return 0;
}

void disp_shutdown(void)
{
    if (!g_drm_ready) return;
    drm_cleanup();
    LOG("disp_shutdown: DRM/KMS released");
}

#else /* !HAVE_DRM */

int disp_init(void)
{
    ERR("disp_init: built without libdrm (DRM/KMS unavailable)");
    return -1;
}

void disp_shutdown(void) { /* no-op */ }

#endif /* HAVE_DRM */

/* ============================================================
 * 公开 API（始终可用，DRM 不可用时为 no-op）
 * ============================================================ */

bool disp_is_ready(void) { return g_drm_ready; }

void disp_set_rotation(uint32_t rot)
{
    (void)rot;
    /* Phase 4 待实现 */
}

void disp_set_colormode(int mode)
{
    (void)mode;
    /* Phase 4 待实现 */
}

/* ---- 像素级操作（DRM 不可用时 no-op） ---- */

void disp_clear(uint32_t color)
{
    if (!g_drm_ready || !g_fb_mem) return;
    uint32_t *row = (uint32_t *)g_fb_mem;
    int wpx = g_fb_pitch / 4;
    for (int y = 0; y < g_fb_h; y++) {
        for (int x = 0; x < wpx; x++)
            row[x] = color;
        row += wpx;
    }
}

void disp_draw_pixel(int x, int y, uint32_t color)
{
    if (!g_drm_ready || !g_fb_mem) return;
    if (x < 0 || x >= g_fb_w || y < 0 || y >= g_fb_h) return;
    ((uint32_t *)g_fb_mem)[y * (g_fb_pitch / 4) + x] = color;
}

void disp_draw_rect(int x, int y, int w, int h, uint32_t color)
{
    for (int dy = 0; dy < h; dy++)
        for (int dx = 0; dx < w; dx++)
            disp_draw_pixel(x + dx, y + dy, color);
}

void disp_draw_text(int x, int y, const char *text, uint32_t color)
{
    if (!g_drm_ready || !g_fb_mem) return;

    for (const char *p = text; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (c >= 32 && c <= 126) {
            const unsigned char *glyph = &font_5x7[(c - 32) * 7];
            for (int row = 0; row < 7; row++) {
                unsigned char bits = glyph[row] & 0x1f;
                for (int col = 0; col < 5; col++) {
                    if (bits & (1u << col))
                        disp_draw_pixel(x + col, y + row, color);
                }
            }
        }
        x += 6; /* 5 pixels + 1 spacing */
    }
}

/* ============================================================
 * disp_flip — libretro video_refresh 回调
 * ============================================================ */

void disp_flip(const void *buf, unsigned width, unsigned height, size_t pitch)
{
    if (!g_drm_ready || !g_fb_mem) return;

    const uint8_t *src = (const uint8_t *)buf;
    uint8_t *dst = (uint8_t *)g_fb_mem;
    unsigned rows = height < (unsigned)g_fb_h ? height : (unsigned)g_fb_h;
    unsigned cols = width < (unsigned)g_fb_w ? width : (unsigned)g_fb_w;

    /* 判断源格式：pitch/width = 2 → RGB565, =4 → XRGB8888 */
    size_t bpp = pitch / width;

    for (unsigned y = 0; y < rows; y++) {
        const uint8_t *srow = src + y * pitch;
        uint32_t *drow = (uint32_t *)(dst + y * g_fb_pitch);

        for (unsigned x = 0; x < cols; x++) {
            uint32_t px;
            if (bpp == 4) {
                /* XRGB8888 → XRGB8888 (直接拷贝) */
                px = *(const uint32_t *)(srow + x * 4);
            } else if (bpp == 2) {
                /* RGB565 → XRGB8888 */
                uint16_t s = *(const uint16_t *)(srow + x * 2);
                uint8_t r = (uint8_t)((s >> 11) & 0x1f);
                uint8_t g = (uint8_t)((s >> 5) & 0x3f);
                uint8_t b = (uint8_t)(s & 0x1f);
                r = (uint8_t)((r << 3) | (r >> 2));
                g = (uint8_t)((g << 2) | (g >> 4));
                b = (uint8_t)((b << 3) | (b >> 2));
                px = (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
            } else {
                px = 0;
            }
            drow[x] = px;
        }
    }

#if HAVE_DRM
    /* 通过 SetCrtc 呈现（单缓冲，非最优但足够用于菜单） */
    drmModeSetCrtc(g_dri_fd, g_crtc_id, g_fb_id, 0, 0,
                   &g_connector_id, 1, &g_mode);
#endif
}

/* ============================================================
 * 菜单渲染（启动画面）
 * ============================================================ */

void disp_draw_menu(void)
{
    if (!g_drm_ready) {
        LOG("menu: DRM not ready, skip rendering");
        return;
    }

    disp_clear(CLR_BLACK);

    int w = g_fb_w;
    int h = g_fb_h;

    /* 标题 */
    const char *title = "rkgame rebuild v1.5.0";
    int title_x = (w - (int)strlen(title) * 6) / 2;
    int title_y = h / 4;
    disp_draw_text(title_x, title_y, title, CLR_WHITE);

    /* 状态 */
    char status[128];
    snprintf(status, sizeof(status), "DRM/KMS: %dx%d @%uHz",
             g_fb_w, g_fb_h, g_mode.vrefresh);
    int status_x = (w - (int)strlen(status) * 6) / 2;
    disp_draw_text(status_x, title_y + 16, status, CLR_GREEN);

    /* 提示 */
    const char *msg1 = "No autorun configured";
    const char *msg2 = "[waiting for ROM]";
    int msg_x = (w - (int)strlen(msg1) * 6) / 2;
    disp_draw_text(msg_x, h / 2 - 8, msg1, CLR_YELLOW);
    int msg2_x = (w - (int)strlen(msg2) * 6) / 2;
    disp_draw_text(msg2_x, h / 2 + 8, msg2, CLR_GRAY);

    /* 分隔线 */
    disp_draw_rect(0, h / 4 - 4, w, 2, CLR_GRAY);

    /* 日志提示 */
    const char *log_hint = "Logs: /sdcard/cubegm/rkgame.log";
    int log_x = (w - (int)strlen(log_hint) * 6) / 2;
    disp_draw_text(log_x, h - 24, log_hint, CLR_BLUE);

#if HAVE_DRM
    drmModeSetCrtc(g_dri_fd, g_crtc_id, g_fb_id, 0, 0,
                   &g_connector_id, 1, &g_mode);
#endif
    LOG("menu: rendered (DRM ready)");
}
