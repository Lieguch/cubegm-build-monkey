/* ============================================================
 * rkgame-rebuild — cpd.c
 *
 * .cpd 资源加载器（.cpd = ZIP 格式，与 .zip 兼容）
 *
 * 联网搜索确认（R36S Wiki 2026-09-07）：
 *   .cpd 文件实际是 ZIP 格式，可直接用 ui_zip_open() 解压。
 *
 * 原厂 .cpd 资源结构：
 *   resource.cpd:  game.raw / menu.raw / nodata.raw / ui.cfg
 *   UI_Res.cpd:    平台背景（640×480 BGRA raw）、图标精灵表
 *   ui_*.cpd:      语言特定覆盖（26 种语言）
 *   joystick.cpd:  控制器映射图像
 *
 * 我方复用 ui_zip.c 的 ZIP 解压 API。
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cpd.h"
#include "ui_zip.h"
#include "rkgame.h"
#include "debug.h"

/* 全局资源缓存 */
cpd_resource_t g_cpd_resource = {0};
cpd_ui_res_t   g_cpd_ui_res   = {0};

/* ============================================================
 * 从 ZIP 提取 .raw 文件（[4B off][2B w][2B h][RGB565 pixels]）
 *
 * 返回 malloc 的 buffer（含 header），调用方负责 free。
 * ============================================================ */

static unsigned char *extract_raw_from_zip(ui_zip_t *z, const char *name,
                                            int *out_w, int *out_h,
                                            size_t *out_size)
{
    /* 1) 查找条目并获取未压缩大小 */
    size_t expected = 0;
    if (ui_zip_find(z, name, &expected) != 0) return NULL;
    if (expected < 8) return NULL;

    /* 2) 解压到 malloc'd 缓冲区（ui_zip_extract 内部负责分配） */
    unsigned char *buf = NULL;
    size_t actual_size = 0;
    if (ui_zip_extract(z, name, (void **)&buf, &actual_size) != 0 || !buf) {
        return NULL;
    }
    if (actual_size < 8) {
        free(buf);
        return NULL;
    }

    /* 3) 解析 header: [4B offset][2B width][2B height] */
    unsigned int off = (unsigned int)buf[0] | ((unsigned int)buf[1] << 8) |
                       ((unsigned int)buf[2] << 16) | ((unsigned int)buf[3] << 24);
    int w = (int)(buf[4] | ((unsigned int)buf[5] << 8));
    int h = (int)(buf[6] | ((unsigned int)buf[7] << 8));

    if (w <= 0 || h <= 0 || (size_t)off >= actual_size) {
        free(buf);
        return NULL;
    }

    if (out_w) *out_w = w;
    if (out_h) *out_h = h;
    if (out_size) *out_size = actual_size;

    return buf;
}

/* ============================================================
 * 从 ZIP 提取原始数据（非 .raw，如 ui.cfg）
 * ============================================================ */

static unsigned char *extract_data_from_zip(ui_zip_t *z, const char *name,
                                             size_t *out_size)
{
    /* 1) 查找 */
    size_t expected = 0;
    if (ui_zip_find(z, name, &expected) != 0) return NULL;
    if (expected == 0) return NULL;

    /* 2) 解压 */
    unsigned char *buf = NULL;
    size_t actual_size = 0;
    if (ui_zip_extract(z, name, (void **)&buf, &actual_size) != 0 || !buf) {
        return NULL;
    }

    if (out_size) *out_size = actual_size;
    return buf;
}

/* ============================================================
 * cpd_load_resource — 加载 resource.cpd
 *
 * 提取 game.raw / menu.raw / nodata.raw / ui.cfg
 * ============================================================ */

int cpd_load_resource(const char *work_path)
{
    char path[512];
    snprintf(path, sizeof(path), "%sresource.cpd", work_path);

    ui_zip_t *z = NULL;
    if (ui_zip_open(path, &z) != 0) {
        LOG("cpd_load_resource: %s not found or not valid ZIP", path);
        return -1;
    }

    LOG("cpd_load_resource: opened %s", path);

    /* 列出内容（诊断） */
    {
        char names[32][256];
        int n = ui_zip_list(z, names, 32);
        for (int i = 0; i < n && i < 32; i++)
            LOG("cpd_load_resource:   [%d] %s", i, names[i]);
    }

    /* 提取 game.raw */
    g_cpd_resource.game_raw = extract_raw_from_zip(
        z, "game.raw", &g_cpd_resource.game_raw_w,
        &g_cpd_resource.game_raw_h, &g_cpd_resource.game_raw_size);
    if (g_cpd_resource.game_raw)
        LOG("cpd_load_resource: game.raw %dx%d (%zu B)",
            g_cpd_resource.game_raw_w, g_cpd_resource.game_raw_h,
            g_cpd_resource.game_raw_size);

    /* 提取 menu.raw */
    g_cpd_resource.menu_raw = extract_raw_from_zip(
        z, "menu.raw", &g_cpd_resource.menu_raw_w,
        &g_cpd_resource.menu_raw_h, &g_cpd_resource.menu_raw_size);
    if (g_cpd_resource.menu_raw)
        LOG("cpd_load_resource: menu.raw %dx%d (%zu B)",
            g_cpd_resource.menu_raw_w, g_cpd_resource.menu_raw_h,
            g_cpd_resource.menu_raw_size);

    /* 提取 nodata.raw */
    g_cpd_resource.nodata_raw = extract_raw_from_zip(
        z, "nodata.raw", &g_cpd_resource.nodata_raw_w,
        &g_cpd_resource.nodata_raw_h, &g_cpd_resource.nodata_raw_size);
    if (g_cpd_resource.nodata_raw)
        LOG("cpd_load_resource: nodata.raw %dx%d (%zu B)",
            g_cpd_resource.nodata_raw_w, g_cpd_resource.nodata_raw_h,
            g_cpd_resource.nodata_raw_size);

    /* 提取 ui.cfg */
    g_cpd_resource.ui_cfg = extract_data_from_zip(
        z, "ui.cfg", &g_cpd_resource.ui_cfg_size);
    if (g_cpd_resource.ui_cfg)
        LOG("cpd_load_resource: ui.cfg (%zu B)", g_cpd_resource.ui_cfg_size);

    ui_zip_close(z);
    g_cpd_resource.loaded = true;

    return 0;
}

/* ============================================================
 * cpd_load_ui_res — 加载 UI_Res.cpd
 *
 * 提取平台背景（*.raw）
 * ============================================================ */

int cpd_load_ui_res(const char *work_path)
{
    char path[512];
    snprintf(path, sizeof(path), "%sUI_Res.cpd", work_path);

    ui_zip_t *z = NULL;
    if (ui_zip_open(path, &z) != 0) {
        LOG("cpd_load_ui_res: %s not found or not valid ZIP", path);
        return -1;
    }

    LOG("cpd_load_ui_res: opened %s", path);

    /* 列出内容 */
    {
        char names[64][256];
        int n = ui_zip_list(z, names, 64);
        for (int i = 0; i < n && i < 64; i++)
            LOG("cpd_load_ui_res:   [%d] %s", i, names[i]);

        #define MAX_RES 32
        unsigned char *raws[MAX_RES] = {0};
        size_t        sizes[MAX_RES] = {0};
        int           ws[MAX_RES], hs[MAX_RES];
        int           count = 0;

        for (int i = 0; i < n && count < MAX_RES; i++) {
            const char *nm = names[i];
            const char *dot = strrchr(nm, '.');
            if (!dot || strcmp(dot, ".raw") != 0) continue;

            int w = 0, h = 0;
            unsigned char *buf = extract_raw_from_zip(z, nm, &w, &h, &sizes[count]);
            if (buf) {
                raws[count] = buf;
                ws[count] = w;
                hs[count] = h;
                count++;
                LOG("cpd_load_ui_res:   loaded %s %dx%d (%zu B)",
                    nm, w, h, sizes[count]);
            }
        }

        /* 缓存到全局 */
        if (count > 0) {
            g_cpd_ui_res.bg_raw  = (unsigned char **)calloc((size_t)count, sizeof(unsigned char *));
            g_cpd_ui_res.bg_size = (size_t *)calloc((size_t)count, sizeof(size_t));
            g_cpd_ui_res.bg_w    = (int *)calloc((size_t)count, sizeof(int));
            g_cpd_ui_res.bg_h    = (int *)calloc((size_t)count, sizeof(int));
            if (!g_cpd_ui_res.bg_raw || !g_cpd_ui_res.bg_size ||
                !g_cpd_ui_res.bg_w || !g_cpd_ui_res.bg_h) {
                for (int i = 0; i < count; i++) free(raws[i]);
                free(g_cpd_ui_res.bg_raw);
                free(g_cpd_ui_res.bg_size);
                free(g_cpd_ui_res.bg_w);
                free(g_cpd_ui_res.bg_h);
                memset(&g_cpd_ui_res, 0, sizeof(g_cpd_ui_res));
                ui_zip_close(z);
                return -1;
            }
            for (int i = 0; i < count; i++) {
                g_cpd_ui_res.bg_raw[i]  = raws[i];
                g_cpd_ui_res.bg_size[i] = sizes[i];
                g_cpd_ui_res.bg_w[i]    = ws[i];
                g_cpd_ui_res.bg_h[i]    = hs[i];
            }
            g_cpd_ui_res.bg_count = count;
            g_cpd_ui_res.loaded   = true;
        }
    }

    ui_zip_close(z);
    return 0;
}

/* ============================================================
 * 释放
 * ============================================================ */

void cpd_free_all(void)
{
    free(g_cpd_resource.game_raw);
    free(g_cpd_resource.menu_raw);
    free(g_cpd_resource.nodata_raw);
    free(g_cpd_resource.ui_cfg);
    memset(&g_cpd_resource, 0, sizeof(g_cpd_resource));

    if (g_cpd_ui_res.bg_count > 0 && g_cpd_ui_res.bg_raw) {
        for (int i = 0; i < g_cpd_ui_res.bg_count; i++)
            free(g_cpd_ui_res.bg_raw[i]);
    }
    free(g_cpd_ui_res.bg_raw);
    free(g_cpd_ui_res.bg_size);
    free(g_cpd_ui_res.bg_w);
    free(g_cpd_ui_res.bg_h);
    memset(&g_cpd_ui_res, 0, sizeof(g_cpd_ui_res));
}

/* ============================================================
 * 访问器
 * ============================================================ */

unsigned char *cpd_get_nodata(int *out_w, int *out_h)
{
    if (!g_cpd_resource.nodata_raw) return NULL;
    if (out_w) *out_w = g_cpd_resource.nodata_raw_w;
    if (out_h) *out_h = g_cpd_resource.nodata_raw_h;
    return g_cpd_resource.nodata_raw;
}

unsigned char *cpd_get_menu_raw(int *out_w, int *out_h)
{
    if (!g_cpd_resource.menu_raw) return NULL;
    if (out_w) *out_w = g_cpd_resource.menu_raw_w;
    if (out_h) *out_h = g_cpd_resource.menu_raw_h;
    return g_cpd_resource.menu_raw;
}

unsigned char *cpd_get_game_raw(int *out_w, int *out_h)
{
    if (!g_cpd_resource.game_raw) return NULL;
    if (out_w) *out_w = g_cpd_resource.game_raw_w;
    if (out_h) *out_h = g_cpd_resource.game_raw_h;
    return g_cpd_resource.game_raw;
}

unsigned char *cpd_get_bg_raw(int platform_index, int *out_w, int *out_h)
{
    if (!g_cpd_ui_res.loaded || platform_index < 0 ||
        platform_index >= g_cpd_ui_res.bg_count) return NULL;
    if (out_w) *out_w = g_cpd_ui_res.bg_w[platform_index];
    if (out_h) *out_h = g_cpd_ui_res.bg_h[platform_index];
    return g_cpd_ui_res.bg_raw[platform_index];
}

/* ============================================================
 * 诊断
 * ============================================================ */

void cpd_report(void)
{
    LOG("cpd_report: resource.cpd loaded=%d", g_cpd_resource.loaded);
    if (g_cpd_resource.loaded) {
        LOG("  game.raw   = %s (%dx%d)",
            g_cpd_resource.game_raw ? "yes" : "no",
            g_cpd_resource.game_raw_w, g_cpd_resource.game_raw_h);
        LOG("  menu.raw   = %s (%dx%d)",
            g_cpd_resource.menu_raw ? "yes" : "no",
            g_cpd_resource.menu_raw_w, g_cpd_resource.menu_raw_h);
        LOG("  nodata.raw = %s (%dx%d)",
            g_cpd_resource.nodata_raw ? "yes" : "no",
            g_cpd_resource.nodata_raw_w, g_cpd_resource.nodata_raw_h);
        LOG("  ui.cfg     = %s (%zu B)",
            g_cpd_resource.ui_cfg ? "yes" : "no",
            g_cpd_resource.ui_cfg_size);
    }
    LOG("cpd_report: UI_Res.cpd loaded=%d (bg_count=%d)",
        g_cpd_ui_res.loaded, g_cpd_ui_res.bg_count);
}
