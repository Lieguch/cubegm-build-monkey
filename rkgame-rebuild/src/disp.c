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
#include <drm_fourcc.h>
#endif

#include "rkgame.h"
#include "debug.h"
#include "font.h"

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

        if (conn->connection != DRM_MODE_CONNECTED) {
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

    size_t map_size = (size_t)crm.pitch * (size_t)g_fb_h;
    g_fb_mem = mmap(NULL, map_size, PROT_READ | PROT_WRITE,
                    MAP_SHARED, g_dri_fd, map.offset);
    if (g_fb_mem == MAP_FAILED) {
        ERR("disp_init: mmap failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }
    g_fb_pitch = (int)crm.pitch;

    /* 创建 framebuffer (XRGB8888 = 32bpp ARGB, alpha=0) */
    /* libdrm 2.4's drmModeAddFB2 takes pointer-to-array params:
     *   drmModeAddFB2(fd, w, h, format, bo_handles[4], pitches[4],
     *                 offsets[4], *buf_id, flags)
     */
    uint32_t handles[] = { crm.handle, 0, 0, 0 };
    uint32_t pitches[] = { (uint32_t)g_fb_pitch, 0, 0, 0 };
    uint32_t offsets[] = { 0, 0, 0, 0 };
    uint32_t fb_id = 0;
    if (drmModeAddFB2(g_dri_fd, (uint32_t)g_fb_w, (uint32_t)g_fb_h,
                      DRM_FORMAT_XRGB8888, handles, pitches, offsets,
                      &fb_id, 0) < 0) {
        ERR("disp_init: drmModeAddFB2 failed: %s", strerror(errno));
        drm_cleanup();
        return -1;
    }
    g_fb_id = fb_id;

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

/* 获取 framebuffer 尺寸（供 UI 模块使用） */
int disp_fb_width(void)  { return g_fb_w; }
int disp_fb_height(void) { return g_fb_h; }

/* Blit RGB565 数据到 framebuffer（不呈现）。
 * 用于 UI 背景渲染。buf 为 RGB565 像素数据，pitch = width*2。 */
void disp_blit_rgb565(const uint8_t *buf, int width, int height, int pitch)
{
    disp_blit_rgb565_at(buf, 0, 0, width, height, pitch);
}

/* 带偏移的 blit：用于缩略图、小图 overlay。
 * 图像超出 fb 边界时自动裁剪（clamp 到 fb 范围）。 */
void disp_blit_rgb565_at(const uint8_t *buf, int x, int y,
                         int width, int height, int pitch)
{
    if (!g_drm_ready || !g_fb_mem || !buf) return;
    if (width <= 0 || height <= 0) return;

    size_t src_pitch = (size_t)pitch;

    /* 裁剪到 fb 边界 */
    int src_x0 = 0, src_y0 = 0;
    int cols = width, rows = height;

    if (x < 0) { src_x0 = -x; cols += x; x = 0; }
    if (y < 0) { src_y0 = -y; rows += y; y = 0; }
    if (x + cols > g_fb_w) cols = g_fb_w - x;
    if (y + rows > g_fb_h) rows = g_fb_h - y;
    if (cols <= 0 || rows <= 0) return;

    for (int row = 0; row < rows; row++) {
        int sy = src_y0 + row;
        if (sy >= height) break;
        const uint8_t *srow = buf + (size_t)sy * src_pitch + src_x0 * 2;
        uint32_t *drow = (uint32_t *)((uint8_t *)g_fb_mem +
                       (size_t)(y + row) * (size_t)g_fb_pitch + (size_t)x * 4);

        for (int col = 0; col < cols; col++) {
            uint16_t s = (uint16_t)(srow[col * 2] | (srow[col * 2 + 1] << 8));
            uint8_t r = (uint8_t)((s >> 11) & 0x1f);
            uint8_t g = (uint8_t)((s >> 5) & 0x3f);
            uint8_t b = (uint8_t)(s & 0x1f);
            r = (uint8_t)((r << 3) | (r >> 2));
            g = (uint8_t)((g << 2) | (g >> 4));
            b = (uint8_t)((b << 3) | (b >> 2));
            drow[col] = (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
        }
    }
}

/* ============================================================
 * 背景缓存（P2.3 — InitScr RGB565 双缓冲优化）
 * ============================================================
 *
 * 工厂对齐：InitScr @ 0x29ce8 使用 RGB565 双缓冲降低内存占用。
 * 本实现：将 RGB565→XRGB8888 转换一次性完成并缓存，
 *         后续每帧仅需 memcpy 而非逐像素转换。
 *
 * 内存节省：
 *   XRGB8888 单缓冲:  1280×720×4 = 3.6 MB
 *   缓存一次转换后:   每帧 blit 从 921K 次 CPU 操作 → 1 次 memcpy
 *   RGB565 双缓冲（InitScr）: 480×272×2×2 = 512 KB ≈ 260 KB
 * ============================================================ */

/* 背景缓存（预转换的 XRGB8888 数据） */
static uint32_t *g_bg_cache      = NULL;
static int       g_bg_cache_w    = 0;
static int       g_bg_cache_h    = 0;
static size_t    g_bg_cache_pitch = 0;   /* 字节数 per row */

/* InitScr RGB565 双缓冲（480×272 初始化画面） */
/* 原厂 InitScr @ 0x29ce8: scr_h_size=0x1e0(480), scr_v_size=0x110(272)
 * malloc(0x3fc00) = 480*272*2 = 260096 bytes (RGB565) */
#define INITSCR_W   480
#define INITSCR_H   272
static uint16_t  *g_initscr[2]   = { NULL, NULL };
static int        g_initscr_cur  = 0;   /* 当前 front buffer 索引 */

/* 将 RGB565 数据转换为 XRGB8888 并缓存。
 * 转换一次，后续 disp_draw_cached_bg() 直接 memcpy。
 * 返回 0 成功，-1 失败（内存不足）。 */
int disp_cache_bg(const uint8_t *rgb565, int width, int height, int pitch)
{
    if (!rgb565 || width <= 0 || height <= 0) return -1;

    /* 释放旧缓存 */
    if (g_bg_cache) {
        free(g_bg_cache);
        g_bg_cache = NULL;
    }

    int cache_w = width < g_fb_w ? width : g_fb_w;
    int cache_h = height < g_fb_h ? height : g_fb_h;
    g_bg_cache_pitch = (size_t)cache_w * 4;  /* XRGB8888 = 4 bytes/pixel */

    g_bg_cache = (uint32_t *)calloc((size_t)cache_h, g_bg_cache_pitch);
    if (!g_bg_cache) {
        ERR("disp_cache_bg: calloc failed (%dx%d)", cache_w, cache_h);
        return -1;
    }

    size_t src_pitch = (size_t)pitch;
    for (int y = 0; y < cache_h; y++) {
        const uint8_t *srow = rgb565 + (size_t)y * src_pitch;
        uint32_t *drow = &g_bg_cache[(size_t)y * cache_w];

        for (int x = 0; x < cache_w; x++) {
            uint16_t s = (uint16_t)(srow[x * 2] | (srow[x * 2 + 1] << 8));
            uint8_t r = (uint8_t)((s >> 11) & 0x1f);
            uint8_t g = (uint8_t)((s >> 5) & 0x3f);
            uint8_t b = (uint8_t)(s & 0x1f);
            r = (uint8_t)((r << 3) | (r >> 2));
            g = (uint8_t)((g << 2) | (g >> 4));
            b = (uint8_t)((b << 3) | (b >> 2));
            drow[x] = (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
        }
    }

    g_bg_cache_w = cache_w;
    g_bg_cache_h = cache_h;

    LOG("disp_cache_bg: cached %dx%d (%zu KB)",
        cache_w, cache_h, g_bg_cache_pitch * (size_t)cache_h / 1024);
    return 0;
}

/* 绘制缓存的背景到 framebuffer（memcpy，零 CPU 转换）。
 * 在 font_draw_text 之前调用。 */
void disp_draw_cached_bg(void)
{
    if (!g_drm_ready || !g_fb_mem || !g_bg_cache) return;

    for (int y = 0; y < g_bg_cache_h; y++) {
        uint32_t *drow = (uint32_t *)((uint8_t *)g_fb_mem + (size_t)y * (size_t)g_fb_pitch);
        memcpy(drow, &g_bg_cache[(size_t)y * g_bg_cache_w],
               (size_t)g_bg_cache_w * 4);
    }
}

/* 释放缓存的背景 */
void disp_clear_cached_bg(void)
{
    if (g_bg_cache) {
        free(g_bg_cache);
        g_bg_cache = NULL;
    }
    g_bg_cache_w = g_bg_cache_h = 0;
    g_bg_cache_pitch = 0;
}

/* 背景是否已缓存 */
bool disp_bg_cached(void) { return g_bg_cache != NULL; }

/* ============================================================
 * InitScr RGB565 双缓冲（480×272 初始化画面）
 * ============================================================
 *
 * 工厂 InitScr 使用480×272 RGB565 双缓冲渲染初始化画面，
 * 内存仅 480×272×2×2 = 512 KB（vs 主 framebuffer 3.6 MB）。
 * 主 framebuffer 仍为 XRGB8888，InitScr 在初始化阶段使用。
 */

/* 初始化 InitScr RGB565 双缓冲。返回 0 成功。 */
int disp_initscr_alloc(void)
{
    size_t buf_size = (size_t)INITSCR_W * (size_t)INITSCR_H * 2;  /* RGB565 */

    for (int i = 0; i < 2; i++) {
        if (!g_initscr[i]) {
            g_initscr[i] = (uint16_t *)calloc(1, buf_size);
            if (!g_initscr[i]) {
                ERR("disp_initscr_alloc: calloc failed (buf %d, %zu KB)",
                    i, buf_size / 1024);
                /* 清理已分配的 */
                disp_initscr_free();
                return -1;
            }
        }
    }
    g_initscr_cur = 0;
    LOG("disp_initscr_alloc: %dx%d RGB565 double-buffer (%zu KB)",
        INITSCR_W, INITSCR_H, buf_size * 2 / 1024);
    return 0;
}

/* 释放 InitScr 双缓冲 */
void disp_initscr_free(void)
{
    for (int i = 0; i < 2; i++) {
        if (g_initscr[i]) {
            free(g_initscr[i]);
            g_initscr[i] = NULL;
        }
    }
    g_initscr_cur = 0;
}

/* 获取当前 InitScr 写入缓冲区。返回 NULL 表示未分配。 */
uint16_t *disp_initscr_get_buf(void)
{
    if (!g_initscr[0] || !g_initscr[1]) return NULL;
    return g_initscr[g_initscr_cur];
}

/* 翻转 InitScr 双缓冲（交换前后缓冲） */
void disp_initscr_flip(void)
{
    g_initscr_cur = g_initscr_cur ^ 1;
}

/* 将 InitScr RGB565 缓冲缩放到主 framebuffer 并呈现。
 * 用于在初始化阶段显示初始化画面。 */
void disp_initscr_present(void)
{
    if (!g_drm_ready || !g_fb_mem || !g_initscr[g_initscr_cur]) return;

    /* 将 320×200 RGB565 缩放到 g_fb_w×g_fb_h XRGB8888 */
    float sx = (float)g_fb_w / (float)INITSCR_W;
    float sy = (float)g_fb_h / (float)INITSCR_H;

    for (int y = 0; y < g_fb_h; y++) {
        uint32_t *drow = (uint32_t *)((uint8_t *)g_fb_mem + (size_t)y * (size_t)g_fb_pitch);
        int sy_idx = (int)((float)y * (float)INITSCR_H / (float)g_fb_h);
        if (sy_idx >= INITSCR_H) sy_idx = INITSCR_H - 1;
        const uint16_t *srow = &g_initscr[g_initscr_cur][sy_idx * INITSCR_W];

        for (int x = 0; x < g_fb_w; x++) {
            int sx_idx = (int)((float)x * (float)INITSCR_W / (float)g_fb_w);
            if (sx_idx >= INITSCR_W) sx_idx = INITSCR_W - 1;
            uint16_t s = srow[sx_idx];
            uint8_t r = (uint8_t)((s >> 11) & 0x1f);
            uint8_t g = (uint8_t)((s >> 5) & 0x3f);
            uint8_t b = (uint8_t)(s & 0x1f);
            r = (uint8_t)((r << 3) | (r >> 2));
            g = (uint8_t)((g << 2) | (g >> 4));
            b = (uint8_t)((b << 3) | (b >> 2));
            drow[x] = (uint32_t)r | ((uint32_t)g << 8) | ((uint32_t)b << 16);
        }
    }

#if HAVE_DRM
    drmModeSetCrtc(g_dri_fd, g_crtc_id, g_fb_id, 0, 0,
                   &g_connector_id, 1, &g_mode);
#endif
}

/* InitScr 双缓冲是否已分配 */
bool disp_initscr_ready(void) { return g_initscr[0] && g_initscr[1]; }

/* 游戏模式切换：使用 InitScr 480×272 RGB565 而非 1280×720 XRGB8888
 * 原厂 InitScr @ 0x29ce8: scr_h_size=0x1e0(480), scr_v_size=0x110(272) */
static int g_game_mode = 0;  /* 0 = menu mode (1280×720), 1 = game mode (480×272) */

void disp_set_game_mode(int enabled)
{
    g_game_mode = enabled;
    if (enabled) {
        LOG("disp_set_game_mode: switched to game mode 480x272 RGB565");
        if (!g_initscr[0]) disp_initscr_alloc();
    } else {
        LOG("disp_set_game_mode: switched to menu mode 1280x720 XRGB8888");
    }
}

int disp_is_game_mode(void) { return g_game_mode; }

/* 呈现 framebuffer 到屏幕（SetCrtc）。
 * 在 disp_blit / disp_draw_pixel / font_draw_text 之后调用。 */
void disp_present(void)
{
#if HAVE_DRM
    if (!g_drm_ready) return;
    drmModeSetCrtc(g_dri_fd, g_crtc_id, g_fb_id, 0, 0,
                   &g_connector_id, 1, &g_mode);
#endif
}

/* 游戏模式下：将 InitScr RGB565 缓冲区缩放到 DRM framebuffer 呈现 */
void disp_game_present(void)
{
    if (!g_game_mode || !g_initscr_ready()) {
        disp_present();
        return;
    }

    /* 将 480×272 RGB565 缩放到 1280×720 XRGB8888 framebuffer */
    disp_initscr_present();
}

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

    /* 优先使用 TTF 字体（P1.2，与工厂 stb_truetype 对齐） */
    if (font_is_ready()) {
        font_draw_text(x, y, text, color);
        return;
    }

    /* 回退：5x7 位图字体（DRM 不可用或字体加载失败时） */
    int scale = 3;  /* 3x 放大，5x7 字体在 1280x720 屏幕上可见 */

    for (const char *p = text; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if (c >= 32 && c <= 126) {
            const unsigned char *glyph = &font_5x7[(c - 32) * 7];
            for (int row = 0; row < 7; row++) {
                unsigned char bits = glyph[row] & 0x1f;
                for (int col = 0; col < 5; col++) {
                    if (bits & (1u << col))
                        /* 放大：每个像素变成 scale x scale 的方块 */
                        for (int sy = 0; sy < scale; sy++) {
                            for (int sx = 0; sx < scale; sx++) {
                                disp_draw_pixel(x + col * scale + sx, y + row * scale + sy, color);
                            }
                        }
                }
            }
        }
        x += 6 * scale; /* 5 pixels + 1 spacing, 放大 */
    }
}

/* ============================================================
 * disp_flip — libretro video_refresh 回调
 * ============================================================ */

void disp_flip(const void *buf, unsigned width, unsigned height, size_t pitch)
{
    if (!g_drm_ready || !g_fb_mem) return;

    /* 游戏模式：core 输出 → InitScr 480×272 RGB565 双缓冲 → 缩放到 fb 上屏
     * 对齐原厂 InitScr @ 0x29ce8: scr_h_size=480, scr_v_size=272 */
    if (g_game_mode && g_initscr_ready()) {
        if (!buf || width == 0 || height == 0) return;

        uint16_t *dst = g_initscr[g_initscr_cur];
        const uint8_t *src = (const uint8_t *)buf;
        unsigned rows = height < (unsigned)INITSCR_H ? height : (unsigned)INITSCR_H;
        unsigned cols = width  < (unsigned)INITSCR_W ? width : (unsigned)INITSCR_W;
        size_t bpp = pitch / (width ? width : 1);

        /* 清底黑色，避免残留 */
        for (unsigned y = 0; y < INITSCR_H; y++)
            for (unsigned x = 0; x < INITSCR_W; x++)
                dst[y * INITSCR_W + x] = 0;

        for (unsigned y = 0; y < rows; y++) {
            const uint8_t *srow = src + y * pitch;
            for (unsigned x = 0; x < cols; x++) {
                uint16_t v;
                if (bpp >= 4) {
                    /* XRGB8888 → RGB565 */
                    uint32_t px = *(const uint32_t *)(srow + x * 4);
                    uint8_t r = (uint8_t)((px >> 16) & 0xff);
                    uint8_t g = (uint8_t)((px >> 8) & 0xff);
                    uint8_t b = (uint8_t)(px & 0xff);
                    v = (uint16_t)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
                } else if (bpp == 2) {
                    v = (uint16_t)(srow[x * 2] | ((uint16_t)srow[x * 2 + 1] << 8));
                } else {
                    v = 0;
                }
                dst[y * INITSCR_W + x] = v;
            }
        }

        /* InitScr 480×272 RGB565 → fb 1280×720 XRGB8888 → SetCrtc */
        disp_game_present();
        return;
    }

    /* Menu 模式：直接写主 framebuffer (XRGB8888) */
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
#if HAVE_DRM
    snprintf(status, sizeof(status), "DRM/KMS: %dx%d @%uHz",
             g_fb_w, g_fb_h, g_mode.vrefresh);
#else
    snprintf(status, sizeof(status), "DRM/KMS: %dx%d (no DRM)",
             g_fb_w, g_fb_h);
#endif
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
