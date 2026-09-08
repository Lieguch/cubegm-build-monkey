/* ============================================================
 * ui.c — UI 资源加载与渲染（P1.3 + P2.3 + Phase 5.2）
 * ============================================================
 *
 * 工厂对齐（Ghidra mui_LoadUIResource @ 0x17dac）：
 *   OpenZipU → FindZipItemA → UnzipItem → malloc'd buffer
 *   .raw 格式: [4B pixel_offset][2B width][2B height][RGB565 data]
 *
 * 本实现：
 *   - 从 setting.xml 解析 <ui gamelist="1"> 选中的 ui_*.zip
 *   - 加载全部 5 个 .raw 页面：menu/type/search/setting/game
 *   - 将 RGB565 转换为 XRGB8888 写入 framebuffer
 *   - 用 TTF 字体绘制文字叠加层
 *   - 尝试从 root.dat 加载主菜单背景（WQW\x03 自定义容器，
 *     若为标准 ZIP 则提取，否则回退到 ui_*.zip 的 menu.raw）
 * ============================================================ */

#include "ui.h"
#include "rkgame.h"
#include "debug.h"
#include "font.h"
#include "ui_zip.h"
#include "thumbnail.h"
#include "cpd.h"
#include "game_list.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- 全局状态 ---- */

static ui_zip_t   *g_ui_zip     = NULL;
static ui_page_t   g_pages[UI_PAGE_COUNT];
static bool        g_ui_ready   = false;
static char        g_ui_zip_path[600]  = "";
static char        g_ui_zip_name[256]  = "";

/* .raw 文件名表（索引 = UI_PAGE_*） */
static const char *g_page_files[UI_PAGE_COUNT] = {
    "menu.raw",     /* UI_PAGE_MENU */
    "type.raw",     /* UI_PAGE_TYPE */
    "search.raw",   /* UI_PAGE_SEARCH */
    "setting.raw",  /* UI_PAGE_SETTING */
    "game.raw",     /* UI_PAGE_GAME */
};

/* ---- UI 包选择 ---- */

/* 按 language 索引选择 UI 包。
 * 逻辑（对齐原厂 mui_LoadSetting）：
 *   1. 读 <config language="N" /> 得到目标语言索引
 *   2. 遍历所有 <ui filename="..." />，第 N 个即当前语言包
 *   3. 若无 <config language> 或 N=0，则优先选 gamelist="1" 标记的包
 *   4. 全部失败则回退 ui_en.zip
 * 返回 true 找到包，false 回退 ui_en.zip。 */
static bool select_ui_zip(char *out, size_t out_size)
{
    const char *default_zip = "ui_en.zip";
    bool found = false;

    char path[600];
    snprintf(path, sizeof(path), "%ssetting.xml", work_path);

    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG("select_ui_zip: setting.xml not found, using %s", default_zip);
        strncpy(out, default_zip, out_size - 1);
        out[out_size - 1] = '\0';
        return false;
    }

    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize <= 0 || fsize > 256 * 1024) {
        fclose(fp);
        strncpy(out, default_zip, out_size - 1);
        out[out_size - 1] = '\0';
        return false;
    }

    char *buf = (char *)malloc((size_t)fsize + 1);
    if (!buf) { fclose(fp); return false; }
    fread(buf, 1, (size_t)fsize, fp);
    buf[fsize] = '\0';
    fclose(fp);

    /* 步骤 1: 提取 <config language="N"> */
    int language_index = 0;
    const char *cfg_p = strstr(buf, "<config");
    if (cfg_p) {
        const char *cfg_end = strstr(cfg_p, ">");
        if (!cfg_end) cfg_end = strstr(cfg_p, "/>");
        if (cfg_end) {
            const char *lang_p = strstr(cfg_p, "language=");
            if (lang_p && lang_p < cfg_end) {
                lang_p += strlen("language=");
                if (*lang_p == '"') lang_p++;
                char lang_str[16] = "";
                int i = 0;
                while (*lang_p && *lang_p != '"' && *lang_p != ' ' &&
                       *lang_p != '\t' && *lang_p != '>' &&
                       *lang_p != '/' && i < (int)sizeof(lang_str) - 1) {
                    lang_str[i++] = *lang_p++;
                }
                lang_str[i] = '\0';
                if (lang_str[0]) language_index = atoi(lang_str);
                LOG("select_ui_zip: <config language=\"%s\"> → index=%d", lang_str, language_index);
            }
        }
    }

    /* 步骤 2: 遍历所有 <ui filename="..." ... />，收集候选 */
    char candidates[16][128];
    int candidate_count = 0;
    int gamelist_index = -1;  /* gamelist="1" 标记的索引 */

    const char *p = buf;
    while ((p = strstr(p, "<ui")) != NULL && candidate_count < 16) {
        const char *end = strstr(p, "/>");
        if (!end) end = strstr(p, ">");
        if (!end) break;

        char *scan_end = (char *)end;

        /* 提取 filename="..." */
        const char *fn = strstr(p, "filename=");
        if (fn && fn < scan_end) {
            fn += strlen("filename=");
            if (*fn == '"') fn++;
            const char *fn_end = strchr(fn, '"');
            if (fn_end && (long)(fn_end - fn) > 0 &&
                (long)(fn_end - fn) < (long)sizeof(candidates[0])) {
                size_t len = (size_t)(fn_end - fn);
                memcpy(candidates[candidate_count], fn, len);
                candidates[candidate_count][len] = '\0';
                candidate_count++;

                /* 检查 gamelist="1" */
                const char *gl = strstr(p, "gamelist=");
                if (gl && gl < scan_end) {
                    gl += strlen("gamelist=");
                    if (*gl == '"') gl++;
                    if (*gl == '1' && (gl[1] == '"' || gl[1] == ' ' || gl[1] == '\t')) {
                        gamelist_index = candidate_count - 1;
                    }
                }
            }
        }

        p = end + 2;
    }

    free(buf);

    /* 步骤 3: 按 language_index 选择 */
    if (language_index > 0 && language_index < candidate_count) {
        strncpy(out, candidates[language_index - 1], out_size - 1);
        out[out_size - 1] = '\0';
        found = true;
        LOG("select_ui_zip: language=%d → %s", language_index, out);
    } else if (gamelist_index >= 0) {
        strncpy(out, candidates[gamelist_index], out_size - 1);
        out[out_size - 1] = '\0';
        found = true;
        LOG("select_ui_zip: gamelist=1 → %s", out);
    } else if (candidate_count > 0) {
        strncpy(out, candidates[0], out_size - 1);
        out[out_size - 1] = '\0';
        found = true;
        LOG("select_ui_zip: first candidate → %s", out);
    }

    if (!found) {
        LOG("select_ui_zip: no ui candidates found, using %s", default_zip);
        strncpy(out, default_zip, out_size - 1);
        out[out_size - 1] = '\0';
    }

    return found;
}

/* ---- .raw 加载 ---- */

unsigned char *ui_load_raw(const char *name, int *out_w, int *out_h,
                           int *out_pixel_offset)
{
    /* .cpd 优先（resource.cpd 内含 menu.raw/game.raw/nodata.raw） */
    if (g_ui_zip == NULL) {
        unsigned char *buf = NULL;
        int w = 0, h = 0;
        if (strcmp(name, "menu.raw") == 0)
            buf = cpd_get_menu_raw(&w, &h);
        else if (strcmp(name, "game.raw") == 0)
            buf = cpd_get_game_raw(&w, &h);
        else if (strcmp(name, "nodata.raw") == 0)
            buf = cpd_get_nodata(&w, &h);
        if (buf) {
            /* 复制出来，因为 cpd 缓存由调用方共享不能 free */
            size_t sz = (size_t)w * (size_t)h * 2 + 8;
            unsigned char *out = (unsigned char *)malloc(sz);
            if (out) {
                /* 写 header：offset=8, w, h */
                out[0]=8; out[1]=0; out[2]=0; out[3]=0;
                out[4]=(unsigned char)(w & 0xFF); out[5]=(unsigned char)((w >> 8) & 0xFF);
                out[6]=(unsigned char)(h & 0xFF); out[7]=(unsigned char)((h >> 8) & 0xFF);
                /* 复制像素（跳过原 buffer 的 8B header） */
                if ((size_t)w * (size_t)h * 2 <= sz - 8) {
                    memcpy(out + 8, buf + 8, (size_t)w * (size_t)h * 2);
                }
                if (out_w) *out_w = w;
                if (out_h) *out_h = h;
                if (out_pixel_offset) *out_pixel_offset = 8;
                LOG("ui_load_raw: %s %dx%d from .cpd", name, w, h);
                return out;
            }
        }
        return NULL;
    }

    size_t size;
    if (ui_zip_find(g_ui_zip, name, &size) < 0) {
        /* 尝试 .cpd 回退 */
        unsigned char *buf = NULL;
        int w = 0, h = 0;
        if (strcmp(name, "menu.raw") == 0)
            buf = cpd_get_menu_raw(&w, &h);
        else if (strcmp(name, "game.raw") == 0)
            buf = cpd_get_game_raw(&w, &h);
        else if (strcmp(name, "nodata.raw") == 0)
            buf = cpd_get_nodata(&w, &h);
        if (buf) {
            size_t sz = (size_t)w * (size_t)h * 2 + 8;
            unsigned char *out = (unsigned char *)malloc(sz);
            if (out) {
                out[0]=8; out[1]=0; out[2]=0; out[3]=0;
                out[4]=(unsigned char)(w & 0xFF); out[5]=(unsigned char)((w >> 8) & 0xFF);
                out[6]=(unsigned char)(h & 0xFF); out[7]=(unsigned char)((h >> 8) & 0xFF);
                if ((size_t)w * (size_t)h * 2 <= sz - 8)
                    memcpy(out + 8, buf + 8, (size_t)w * (size_t)h * 2);
                if (out_w) *out_w = w;
                if (out_h) *out_h = h;
                if (out_pixel_offset) *out_pixel_offset = 8;
                LOG("ui_load_raw: %s %dx%d from .cpd fallback", name, w, h);
                return out;
            }
        }
        ERR("ui_load_raw: %s not found in zip or .cpd", name);
        return NULL;
    }

    void *data = NULL;
    size_t out_size;
    if (ui_zip_extract(g_ui_zip, name, &data, &out_size) < 0) {
        ERR("ui_load_raw: extract %s failed", name);
        return NULL;
    }

    unsigned char *buf = (unsigned char *)data;

    /* 解析头：[4B offset][2B width][2B height] */
    if (out_size < 8) {
        ERR("ui_load_raw: %s too small (%zu B)", name, out_size);
        free(buf);
        return NULL;
    }

    int pixel_offset = (int)(buf[0] | (buf[1] << 8) | (buf[2] << 16) | (buf[3] << 24));
    int width  = (int)(buf[4] | (buf[5] << 8));
    int height = (int)(buf[6] | (buf[7] << 8));

    /* 验证像素数据大小 */
    size_t expected_size = (size_t)width * (size_t)height * 2; /* RGB565 */
    if (pixel_offset + expected_size > out_size) {
        ERR("ui_load_raw: %s pixel data out of bounds (offset=%d, need=%zu, have=%zu)",
            name, pixel_offset, expected_size, out_size);
        free(buf);
        return NULL;
    }

    if (out_w) *out_w = width;
    if (out_h) *out_h = height;
    if (out_pixel_offset) *out_pixel_offset = pixel_offset;

    LOG("ui_load_raw: %s %dx%d at offset %d (%zu B total)",
        name, width, height, pixel_offset, out_size);
    return buf;
}

/* ---- root.dat 背景加载 ----
 *
 * 工厂用 OpenZipU 打开 root.dat，但 root.dat 是 WQW\x03 自定义容器，
 * 非标准 ZIP。尝试作为标准 ZIP 打开，失败则跳过（回退 ui_*.zip 的 menu.raw）。
 */
static bool try_load_root_dat_bg(void)
{
    char path[600];
    snprintf(path, sizeof(path), "%sroot.dat", work_path);

    /* 检查文件是否存在 */
    FILE *fp = fopen(path, "rb");
    if (!fp) {
        LOG("ui_init: root.dat not found at %s", path);
        return false;
    }
    fclose(fp);

    /* 检查 magic：WQW\x03 (57 51 57 03) 或 PK\x03\x04 (50 4B 03 04) */
    fp = fopen(path, "rb");
    if (!fp) return false;
    unsigned char magic[4] = {0};
    fread(magic, 1, 4, fp);
    fclose(fp);

    if (magic[0] == 0x50 && magic[1] == 0x4B) {
        /* 标准 ZIP — 尝试提取 bg.raw 或 menu.raw */
        LOG("ui_init: root.dat is standard ZIP, trying to load bg");
        ui_zip_t *zd = NULL;
        if (ui_zip_open(path, &zd) < 0) {
            ERR("ui_init: root.dat ZIP open failed");
            return false;
        }

        const char *candidates[] = {"bg.raw", "menu.raw", "background.raw", NULL};
        bool loaded = false;
        for (int i = 0; candidates[i]; i++) {
            int w, h, off;
            unsigned char *buf = ui_load_raw_from_zip(zd, candidates[i], &w, &h, &off);
            if (buf) {
                g_pages[UI_PAGE_MENU].data = buf;
                g_pages[UI_PAGE_MENU].width = w;
                g_pages[UI_PAGE_MENU].height = h;
                g_pages[UI_PAGE_MENU].pixel_offset = off;
                g_pages[UI_PAGE_MENU].loaded = true;
                LOG("ui_init: root.dat bg loaded %s %dx%d", candidates[i], w, h);
                loaded = true;
                break;
            }
        }
        ui_zip_close(zd);
        return loaded;
    }

    /* WQW\x03 自定义容器 — 尝试用 WQW 解析器提取背景图 */
    if (magic[0] == 0x57 && magic[1] == 0x51) {
        LOG("ui_init: root.dat is WQW custom container, attempting WQW extract for bg");

        /* root.dat 实测内容：000.raw..008.raw (720x480 RGB565) + fileinfo.txt
         * 工厂用 000.raw 作为菜单背景，其余可能用于其他页面/帧动画 */
        const char *bg_candidates[] = {
            "000.raw", "bg.raw", "menu.raw", "background.raw",
            "001.raw", "002.raw", NULL
        };
        for (int i = 0; bg_candidates[i]; i++) {
            unsigned char *bg_data = NULL;
            size_t bg_size = 0;
            if (wqw_extract(path, bg_candidates[i], &bg_data, &bg_size) == 0 &&
                bg_data && bg_size >= 8) {
                /* 成功提取背景图 */
                int w, h, off;
                unsigned char *buf = ui_load_raw_from_buffer(bg_data, bg_size,
                                                              bg_candidates[i], &w, &h, &off);
                if (buf) {
                    g_pages[UI_PAGE_MENU].data = buf;
                    g_pages[UI_PAGE_MENU].width = w;
                    g_pages[UI_PAGE_MENU].height = h;
                    g_pages[UI_PAGE_MENU].pixel_offset = off;
                    g_pages[UI_PAGE_MENU].loaded = true;
                    free(bg_data);
                    LOG("ui_init: root.dat bg loaded from WQW: %s %dx%d",
                        bg_candidates[i], w, h);
                    return true;
                }
                free(bg_data);
            }
        }

        LOG("ui_init: WQW extract failed for bg, using ui_*.zip menu.raw as fallback");
        return false;
    }

    LOG("ui_init: root.dat unknown magic %02X %02X %02X %02X",
        magic[0], magic[1], magic[2], magic[3]);
    return false;
}

/* 从内存 buffer 加载 .raw（供 WQW 提取后使用） */
unsigned char *ui_load_raw_from_buffer(unsigned char *buf, size_t buf_size,
                                        const char *name, int *out_w, int *out_h,
                                        int *out_pixel_offset)
{
    if (!buf || buf_size < 8) return NULL;

    int pixel_offset = (int)(buf[0] | (buf[1] << 8) | (buf[2] << 16) | (buf[3] << 24));
    int width  = (int)(buf[4] | (buf[5] << 8));
    int height = (int)(buf[6] | (buf[7] << 8));

    size_t expected_size = (size_t)width * (size_t)height * 2;
    if (pixel_offset + (int)expected_size > (int)buf_size) {
        ERR("ui_load_raw_from_buffer: %s pixel data out of bounds", name);
        return NULL;
    }

    if (out_w) *out_w = width;
    if (out_h) *out_h = height;
    if (out_pixel_offset) *out_pixel_offset = pixel_offset;

    LOG("ui_load_raw_from_buffer: %s %dx%d at offset %d", name, width, height, pixel_offset);
    return buf;
}

/* 从指定 zip 加载 .raw（内部辅助函数） */
unsigned char *ui_load_raw_from_zip(ui_zip_t *z, const char *name,
                                    int *out_w, int *out_h, int *out_pixel_offset)
{
    if (!z) return NULL;

    size_t size;
    if (ui_zip_find(z, name, &size) < 0) return NULL;

    void *data = NULL;
    size_t out_size;
    if (ui_zip_extract(z, name, &data, &out_size) < 0) return NULL;

    unsigned char *buf = (unsigned char *)data;

    if (out_size < 8) {
        free(buf);
        return NULL;
    }

    int pixel_offset = (int)(buf[0] | (buf[1] << 8) | (buf[2] << 16) | (buf[3] << 24));
    int width  = (int)(buf[4] | (buf[5] << 8));
    int height = (int)(buf[6] | (buf[7] << 8));

    size_t expected_size = (size_t)width * (size_t)height * 2;
    if (pixel_offset + expected_size > out_size) {
        free(buf);
        return NULL;
    }

    if (out_w) *out_w = width;
    if (out_h) *out_h = height;
    if (out_pixel_offset) *out_pixel_offset = pixel_offset;

    return buf;
}

/* ---- 初始化 ---- */

int ui_init(void)
{
    if (g_ui_ready) return 0;

    /* 清零所有页面 */
    memset(g_pages, 0, sizeof(g_pages));

    /* 1. 选择 UI 包 */
    char zip_name[256];
    select_ui_zip(zip_name, sizeof(zip_name));
    strncpy(g_ui_zip_name, zip_name, sizeof(g_ui_zip_name) - 1);

    char zip_path[600];
    snprintf(zip_path, sizeof(zip_path), "%s%s", work_path, zip_name);
    strncpy(g_ui_zip_path, zip_path, sizeof(g_ui_zip_path) - 1);
    g_ui_zip_path[sizeof(g_ui_zip_path) - 1] = '\0';

    /* 2. 尝试从 root.dat 加载背景（P2.3） */
    bool has_root_bg = try_load_root_dat_bg();

    /* 3. 打开 ui_*.zip */
    if (ui_zip_open(zip_path, &g_ui_zip) < 0) {
        ERR("ui_init: cannot open %s", zip_path);
        if (has_root_bg) {
            /* root.dat 有背景，可以用 ui_*.zip 缺失的页面回退 */
            g_ui_ready = true;
            LOG("ui_init: using root.dat bg only (ui_*.zip not found)");
            return 0;
        }
        return -1;
    }

    /* 4. 加载全部 5 个 .raw 页面 */
    for (int i = 0; i < UI_PAGE_COUNT; i++) {
        /* 如果 root.dat 已提供 menu.raw，跳过 menu.raw 加载 */
        if (i == UI_PAGE_MENU && has_root_bg) continue;

        const char *fn = g_page_files[i];
        int w, h, off;
        unsigned char *buf = ui_load_raw(fn, &w, &h, &off);

        if (buf) {
            g_pages[i].data = buf;
            g_pages[i].width = w;
            g_pages[i].height = h;
            g_pages[i].pixel_offset = off;
            g_pages[i].loaded = true;
            LOG("ui_init: loaded %s %dx%d", fn, w, h);
        } else {
            LOG("ui_init: %s not found (page %d unavailable)", fn, i);
        }
    }

    /* 5. 预转换 menu.raw 背景到 XRGB8888 并缓存（P2.3 优化）
     * 消除每帧 RGB565→XRGB8888 逐像素转换开销 */
    if (g_pages[UI_PAGE_MENU].loaded && disp_is_ready()) {
        disp_cache_bg(
            g_pages[UI_PAGE_MENU].data + g_pages[UI_PAGE_MENU].pixel_offset,
            g_pages[UI_PAGE_MENU].width,
            g_pages[UI_PAGE_MENU].height,
            g_pages[UI_PAGE_MENU].width * 2);
    }

    /* 6. 至少需要 menu.raw */
    if (!g_pages[UI_PAGE_MENU].loaded) {
        ERR("ui_init: menu.raw not found — no UI background available");
        ui_zip_close(g_ui_zip);
        g_ui_zip = NULL;
        return -1;
    }

    g_ui_ready = true;
    int loaded_pages = 0;
    for (int i = 0; i < UI_PAGE_COUNT; i++)
        if (g_pages[i].loaded) loaded_pages++;
    LOG("ui_init: %d/%d pages loaded from %s%s (bg_cached=%d)",
        loaded_pages, UI_PAGE_COUNT, g_ui_zip_path,
        has_root_bg ? " (+root.dat bg)" : "", disp_bg_cached() ? 1 : 0);
    return 0;
}

void ui_shutdown(void)
{
    for (int i = 0; i < UI_PAGE_COUNT; i++) {
        if (g_pages[i].data) {
            free(g_pages[i].data);
            g_pages[i].data = NULL;
        }
        g_pages[i].loaded = false;
        g_pages[i].width = g_pages[i].height = 0;
        g_pages[i].pixel_offset = 0;
    }
    if (g_ui_zip) { ui_zip_close(g_ui_zip); g_ui_zip = NULL; }
    disp_clear_cached_bg();
    disp_initscr_free();
    g_ui_ready = false;
}

bool ui_is_ready(void) { return g_ui_ready; }

/* ---- 页面访问 ---- */

const uint8_t *ui_page_pixels(int page)
{
    if (page < 0 || page >= UI_PAGE_COUNT) return NULL;
    if (!g_pages[page].loaded || !g_pages[page].data) return NULL;
    return g_pages[page].data + g_pages[page].pixel_offset;
}

int ui_page_width(int page)
{
    if (page < 0 || page >= UI_PAGE_COUNT) return 0;
    return g_pages[page].width;
}

int ui_page_height(int page)
{
    if (page < 0 || page >= UI_PAGE_COUNT) return 0;
    return g_pages[page].height;
}

/* ---- 渲染页面 ---- */

void ui_draw_page(int page)
{
    if (page < 0 || page >= UI_PAGE_COUNT) return;
    if (!g_ui_ready) {
        LOG("ui: not ready, falling back to disp_draw_menu");
        return;
    }

    /* 如果指定页面未加载，回退到 menu.raw */
    if (!g_pages[page].loaded) {
        LOG("ui: page %d not loaded, falling back to menu", page);
        page = UI_PAGE_MENU;
    }

    ui_page_t *pg = &g_pages[page];

    /* 1. 渲染背景
     * - menu 页面：使用预缓存的 XRGB8888 背景（memcpy，零 CPU 转换）
     * - 其他页面：直接 RGB565→XRGB8888 逐像素转换 */
    if (page == UI_PAGE_MENU && disp_bg_cached()) {
        disp_draw_cached_bg();
    } else {
        const uint8_t *src = pg->data + pg->pixel_offset;
        disp_blit_rgb565(src, pg->width, pg->height, pg->width * 2);
    }

    /* 2. 绘制文字叠加层 */
    int fw = disp_fb_width();
    int fh = disp_fb_height();

    if (page == UI_PAGE_MENU) {
        /* ---- 主菜单页面 ---- */

        /* 标题 */
        const char *title = "rkgame rebuild";
        int title_w = font_text_width(title);
        int title_x = (fw - title_w) / 2;
        if (title_x < 0) title_x = 0;
        int title_y = fh / 5;
        font_draw_text(title_x, title_y, title, 0xFFFFFF00u);

        /* 状态信息 */
        char status[128];
        int loaded_pages = 0;
        for (int i = 0; i < UI_PAGE_COUNT; i++)
            if (g_pages[i].loaded) loaded_pages++;
        snprintf(status, sizeof(status), "UI: %s  (%dx%d bg, %d/%d pages)",
                 g_ui_zip_name, pg->width, pg->height, loaded_pages, UI_PAGE_COUNT);
        int status_w = font_text_width(status);
        int status_x = (fw - status_w) / 2;
        if (status_x < 0) status_x = 0;
        font_draw_text(status_x, title_y + 36, status, 0x80FF80u);

        /* 配置信息 */
        char cfg[128];
        if (g_cfg.autorun_path[0]) {
            snprintf(cfg, sizeof(cfg), "autorun: %s", g_cfg.autorun_path);
        } else {
            snprintf(cfg, sizeof(cfg), "No autorun configured");
        }
        int cfg_w = font_text_width(cfg);
        int cfg_x = (fw - cfg_w) / 2;
        if (cfg_x < 0) cfg_x = 0;
        font_draw_text(cfg_x, fh / 2 - 20, cfg, 0xFFFF80u);

        /* 游戏列表信息（P2.2 + Task #39） */
        if (game_list_is_loaded()) {
            int fav_count = 0;
            for (int i = 0; i < game_list_count(); i++) {
                const game_entry_t *ge = game_list_get(i);
                if (ge && ge->is_favorite) fav_count++;
            }

            char gl[128];
            snprintf(gl, sizeof(gl), "Games: %d loaded, %d favorites  [START]=list [A]=play",
                     game_list_count(), fav_count);
            int gl_w = font_text_width(gl);
            int gl_x = (fw - gl_w) / 2;
            if (gl_x < 0) gl_x = 0;
            font_draw_text(gl_x, fh / 2 + 16, gl, 0xFFFF80u);

            /* 显示前 3 个游戏 */
            int show_count = game_list_count() < 3 ? game_list_count() : 3;
            for (int i = 0; i < show_count; i++) {
                const game_entry_t *ge = game_list_get(i);
                if (!ge) break;
                char game_line[GL_NAME_LEN + 32];
                const char *name = (g_cfg.m_ui == 0 && ge->name_zh[0])
                    ? ge->name_zh : ge->name_en;
                if (ge->is_favorite) {
                    snprintf(game_line, sizeof(game_line), "  \xe2\x9c\x93 %d. %s",
                             i + 1, name);
                } else {
                    snprintf(game_line, sizeof(game_line), "  %d. %s", i + 1, name);
                }
                font_draw_text(gl_x, fh / 2 + 36 + i * 16, game_line, 0xFFFFFF00u);
            }
        }

        /* 提示 */
        const char *hint = "[waiting for ROM]";
        int hint_w = font_text_width(hint);
        int hint_x = (fw - hint_w) / 2;
        if (hint_x < 0) hint_x = 0;
        font_draw_text(hint_x, fh - 60, hint, 0x808080u);

        /* 日志提示 */
        const char *log_hint = "Logs: /sdcard/cubegm/rkgame.log";
        int log_w = font_text_width(log_hint);
        int log_x = (fw - log_w) / 2;
        if (log_x < 0) log_x = 0;
        font_draw_text(log_x, fh - 40, log_hint, 0x0080FFu);

    } else if (page == UI_PAGE_GAME) {
        /* ---- 游戏列表页面（Task #39） ---- */

        if (!game_list_is_loaded() || game_list_count() == 0) {
            const char *no_games = "No games found";
            int ng_w = font_text_width(no_games);
            font_draw_text((fw - ng_w) / 2, fh / 2, no_games, 0x808080u);
            disp_present();
            return;
        }

        /* 标题 */
        char title[128];
        snprintf(title, sizeof(title), "Game List (%d games)", game_list_count());
        int title_w = font_text_width(title);
        font_draw_text((fw - title_w) / 2, 20, title, 0xFFFFFF00u);

        /* 获取当前选中索引和滚动偏移（通过全局变量） */
        extern int menu_gl_selected;
        extern int menu_gl_scroll;

        int count = game_list_count();
        int scroll = menu_gl_scroll;
        int selected = menu_gl_selected;
        if (scroll < 0) scroll = 0;
        if (scroll > count - 1) scroll = count - 1;

        /* 显示游戏列表（最多 8 行） */
        int line_y = 50;
        int line_h = 24;
        for (int i = 0; i < 8 && (scroll + i) < count; i++) {
            const game_entry_t *ge = game_list_get(scroll + i);
            if (!ge) break;

            int idx = scroll + i;
            const char *name = (g_cfg.m_ui == 0 && ge->name_zh[0])
                ? ge->name_zh : ge->name_en;

            char line[GL_NAME_LEN + 64];
            if (ge->is_favorite) {
                snprintf(line, sizeof(line), "%s%2d. %s",
                         ge->is_favorite ? "\xe2\x9c\x93 " : "   ",
                         idx + 1, name);
            } else {
                snprintf(line, sizeof(line), "%d. %s", idx + 1, name);
            }

            /* 高亮选中行 */
            uint32_t color = (idx == selected) ? 0xFFFF00u : 0xFFFFFF00u;
            font_draw_text(40, line_y + i * line_h, line, color);

            /* 显示核心名（右侧） */
            if (ge->core[0]) {
                char core_line[128];
                snprintf(core_line, sizeof(core_line), "[%s]", ge->core);
                int cl_w = font_text_width(core_line);
                font_draw_text(fw - cl_w - 40, line_y + i * line_h, core_line,
                               0x808080u);
            }
        }

        /* ---- 缩略图 overlay（P1 — 接入 thumbnail.c）----
         * 显示当前选中游戏的缩略图到右侧。
         * 工厂：mui_DisplayThumbnail @ 0x14f84 从 <NNN>.dat 提取 <base>_NNN.raw。 */
        {
            const game_entry_t *sel = game_list_get(selected);
            if (sel && sel->path[0]) {
                unsigned char *thumb_data = NULL;
                size_t thumb_size = 0;
                int thumb_w = 0, thumb_h = 0;
                if (thumb_extract(sel->path, &thumb_data, &thumb_size,
                                  &thumb_w, &thumb_h) == 0 &&
                    thumb_data && thumb_w > 0 && thumb_h > 0) {
                    /* 缩略图显示在右侧，居中于列表区域 */
                    int th_x = fw - thumb_w - 20;
                    int th_y = fh / 2 - thumb_h / 2;
                    /* 原始 raw 格式：前 8B header [4B off][2B w][2B h] + RGB565 像素 */
                    size_t data_off = 8;
                    if (thumb_size >= 8 + (size_t)thumb_w * thumb_h * 2) {
                        disp_blit_rgb565_at(thumb_data + data_off, th_x, th_y,
                                             thumb_w, thumb_h, thumb_w * 2);
                    }
                    free(thumb_data);
                    LOG("ui_draw_page GAME: thumbnail %dx%d at (%d,%d)",
                        thumb_w, thumb_h, th_x, th_y);
                } else {
                    /* 无封面 → 回退 nodata.raw 占位图（来自 resource.cpd） */
                    unsigned char *nodata = cpd_get_nodata(&thumb_w, &thumb_h);
                    if (nodata && thumb_w > 0 && thumb_h > 0) {
                        int th_x = fw - thumb_w - 20;
                        int th_y = fh / 2 - thumb_h / 2;
                        size_t data_off = 8;
                        disp_blit_rgb565_at(nodata + data_off, th_x, th_y,
                                             thumb_w, thumb_h, thumb_w * 2);
                        LOG("ui_draw_page GAME: nodata fallback %dx%d at (%d,%d)",
                            thumb_w, thumb_h, th_x, th_y);
                    }
                }
            }
        }

        /* 底部提示 */
        const char *hint = "[A]=play  [X]=favorite  [START]=back";
        int hint_w = font_text_width(hint);
        font_draw_text((fw - hint_w) / 2, fh - 30, hint, 0x808080u);

    } else if (page == UI_PAGE_SETTING) {
        /* ---- 设置页面 ---- */
        char title[64] = "Settings";
        int tw = font_text_width(title);
        font_draw_text((fw - tw) / 2, 20, title, 0xFFFFFF00u);

        char info[128];
        snprintf(info, sizeof(info), "Volume: %d%%  Language: %d  FPS: %d",
                 g_cfg.volume, g_cfg.m_ui, g_cfg.displayfps);
        int iw = font_text_width(info);
        font_draw_text((fw - iw) / 2, fh / 2 - 20, info, 0x80FF80u);

        snprintf(info, sizeof(info), "Save State Hotkey: %d  Game Menu Hotkey: %d",
                 g_cfg.savestatehotkey, g_cfg.gamemenuhotkey);
        iw = font_text_width(info);
        font_draw_text((fw - iw) / 2, fh / 2 + 20, info, 0x80FF80u);

        snprintf(info, sizeof(info), "File Browser: %s", g_cfg.filebrowser[0] ? g_cfg.filebrowser : "(none)");
        iw = font_text_width(info);
        font_draw_text((fw - iw) / 2, fh / 2 + 60, info, 0xFFFF80u);

        const char *hint = "[START]=back";
        int hw = font_text_width(hint);
        font_draw_text((fw - hw) / 2, fh - 30, hint, 0x808080u);

    } else if (page == UI_PAGE_TYPE) {
        /* ---- 游戏分类页面 ---- */
        char title[64] = "Game Categories";
        int tw = font_text_width(title);
        font_draw_text((fw - tw) / 2, 20, title, 0xFFFFFF00u);

        if (game_list_is_loaded()) {
            /* 按目录编号分类统计 */
            int dir_count[9] = {0};
            for (int i = 0; i < game_list_count(); i++) {
                const game_entry_t *ge = game_list_get(i);
                if (ge && ge->dir[0]) {
                    int d = (int)ge->dir[0] - '0';
                    if (d >= 0 && d < 9) dir_count[d]++;
                }
            }

            const char *dir_names[9] = {
                "FBA (Arcade)", "FC/NES", "SFC/SNES", "MD/GG",
                "GBA", "NES", "GB", "PS1", "Atari 2600"
            };
            for (int d = 0; d < 9; d++) {
                if (dir_count[d] == 0) continue;
                char line[64];
                snprintf(line, sizeof(line), "%s: %d games", dir_names[d], dir_count[d]);
                font_draw_text(60, 60 + d * 30, line, 0xFFFFFF00u);
            }
        }

        const char *hint = "[START]=back";
        int hw = font_text_width(hint);
        font_draw_text((fw - hw) / 2, fh - 30, hint, 0x808080u);

    } else if (page == UI_PAGE_SEARCH) {
        /* ---- 搜索页面 ---- */
        char title[64] = "Search Games";
        int tw = font_text_width(title);
        font_draw_text((fw - tw) / 2, 20, title, 0xFFFFFF00u);

        if (game_list_is_loaded()) {
            /* 显示收藏游戏列表 */
            int fav_count = 0;
            int y = 60;
            for (int i = 0; i < game_list_count(); i++) {
                const game_entry_t *ge = game_list_get(i);
                if (!ge) break;
                if (!ge->is_favorite) continue;
                const char *name = (g_cfg.m_ui == 0 && ge->name_zh[0])
                    ? ge->name_zh : ge->name_en;
                char line[GL_NAME_LEN + 16];
                snprintf(line, sizeof(line), "  %s", name);
                font_draw_text(40, y, line, 0xFFFF80u);
                y += 20;
                fav_count++;
                if (y > fh - 60) break;
            }
            if (fav_count == 0) {
                const char *no_fav = "No favorites yet";
                int nf_w = font_text_width(no_fav);
                font_draw_text((fw - nf_w) / 2, fh / 2, no_fav, 0x808080u);
            }
        }

        const char *hint = "[X]=add favorite  [START]=back";
        int hw = font_text_width(hint);
        font_draw_text((fw - hw) / 2, fh - 30, hint, 0x808080u);
    }

    /* 3. 呈现到屏幕 */
    disp_present();

    LOG("ui: page %d rendered (bg=%dx%d, font=%s)",
        page, pg->width, pg->height, font_is_ready() ? "TTF" : "5x7");
}

/* ---- 渲染菜单（兼容旧 API） ---- */

void ui_draw_menu(void)
{
    ui_draw_page(UI_PAGE_MENU);
}
