/* ============================================================
 * thumbnail.c — 游戏缩略图提取（WQW .dat 容器）
 * ============================================================
 *
 * 工厂实证（Ghidra FUN_00014f84_mui_DisplayThumbnail @ 0x14f84）：
 *   1. mui_extract_basepath(path)  — "000/kof97.zip" → "000"
 *   2. mui_extract_basename(path)  — "000/kof97.zip" → "kof97"
 *   3. sprintf("%s/%s/%s.dat", root_path, basepath, basepath)
 *      → "/sdcard/cubegm/000/000.dat"
 *   4. OpenZipU(dat_path, 0, 2)    — 打开 WQW 容器
 *   5. sprintf("%s_%03d.raw", basename, index)
 *      → "kof97_000.raw"
 *   6. FindZipItemA + UnzipItem    — 提取缩略图
 *
 * 缩略图格式：RGB565 小图（尺寸由 Thumbnail_region / Game_ThumbnailRect 配置）
 *
 * 本实现：
 *   - thumb_extract(game_path) — 从 <NNN>/<NNN>.dat 提取第一个缩略图
 *   - thumb_has(game_path)     — 检查 <NNN>.dat 是否存在且含缩略图
 *   - thumb_extract_nth(game_path, n) — 提取第 n 个缩略图
 *
 * 缓存策略：按游戏路径缓存，避免重复解压
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <sys/stat.h>

#include "rkgame.h"
#include "debug.h"
#include "thumbnail.h"

/* 缩略图缓存 */
#define THUMB_CACHE_MAX   32

typedef struct {
    char          game_path[GL_PATH_LEN];
    unsigned char *data;
    size_t         size;
    int            width;
    int            height;
    bool           valid;
} thumb_cache_entry_t;

static thumb_cache_entry_t g_thumb_cache[THUMB_CACHE_MAX];
static int g_thumb_cache_count = 0;

/* ============================================================
 * 路径辅助（对齐工厂 mui_extract_basepath / mui_extract_basename）
 * ============================================================ */

/* 提取目录部分： "000/kof97.zip" → "000" */
static void thumb_extract_basepath(const char *src, char *dst, int dst_size)
{
    strncpy(dst, src, dst_size - 1);
    dst[dst_size - 1] = '\0';
    char *slash = strrchr(dst, '/');
    if (!slash) slash = strrchr(dst, '\\');
    if (!slash) {
        dst[0] = '\0';
        return;
    }
    *slash = '\0';
}

/* 提取文件名去扩展名： "000/kof97.zip" → "kof97" */
static void thumb_extract_basename(const char *src, char *dst, int dst_size)
{
    const char *slash = strrchr(src, '/');
    if (!slash) slash = strrchr(src, '\\');
    if (slash) {
        while (*slash == '/' || *slash == '\\') slash++;
    } else {
        slash = src;
    }
    strncpy(dst, slash, dst_size - 1);
    dst[dst_size - 1] = '\0';
    char *dot = strrchr(dst, '.');
    if (dot) *dot = '\0';
}

/* ============================================================
 * thumb_has — 检查游戏是否有缩略图
 *
 * 逻辑：
 *   1. 从 game_path 提取 basepath（如 "000"）
 *   2. 检查 <work_path>/<basepath>/<basepath>.dat 是否存在
 *   3. 若是 WQW 容器，检查是否含 <basename>_*.raw
 * ============================================================ */

bool thumb_has(const char *game_path)
{
    if (!game_path || !game_path[0]) return false;

    char basepath[128], basename[128];
    thumb_extract_basepath(game_path, basepath, sizeof(basepath));
    thumb_extract_basename(game_path, basename, sizeof(basename));

    if (!basepath[0]) return false;

    /* 构造 .dat 路径 */
    char dat_path[512];
    snprintf(dat_path, sizeof(dat_path), "%s%s/%s.dat",
             work_path, basepath, basepath);

    if (!wqw_is_container(dat_path)) return false;

    /* 构造缩略图名（第一个：index=0） */
    char thumb_name[200];
    snprintf(thumb_name, sizeof(thumb_name), "%s_000.raw", basename);

    unsigned char *data = NULL;
    size_t size = 0;
    if (wqw_extract(dat_path, thumb_name, &data, &size) == 0 && size > 0) {
        free(data);
        return true;
    }
    return false;
}

/* ============================================================
 * thumb_extract — 提取第一个缩略图（index=0）
 *
 * 返回：
 *   0   = 成功，*out_data 指向 malloc 的缓冲区（调用者 free）
 *  -1   = 失败
 *
 * 缓存：相同 game_path 不重复解压
 * ============================================================ */

int thumb_extract(const char *game_path,
                  unsigned char **out_data, size_t *out_size,
                  int *out_w, int *out_h)
{
    return thumb_extract_nth(game_path, 0, out_data, out_size, out_w, out_h);
}

int thumb_extract_nth(const char *game_path, int index,
                      unsigned char **out_data, size_t *out_size,
                      int *out_w, int *out_h)
{
    if (!game_path || !out_data || !out_size) return -1;
    if (index < 0) return -1;

    /* 检查缓存 */
    char cache_key[GL_PATH_LEN + 16];
    snprintf(cache_key, sizeof(cache_key), "%s#%d", game_path, index);
    for (int i = 0; i < g_thumb_cache_count; i++) {
        if (g_thumb_cache[i].valid &&
            strcmp(g_thumb_cache[i].game_path, cache_key) == 0) {
            *out_data = g_thumb_cache[i].data;
            *out_size = g_thumb_cache[i].size;
            if (out_w) *out_w = g_thumb_cache[i].width;
            if (out_h) *out_h = g_thumb_cache[i].height;
            return 0;
        }
    }

    /* 提取路径 */
    char basepath[128], basename[128];
    thumb_extract_basepath(game_path, basepath, sizeof(basepath));
    thumb_extract_basename(game_path, basename, sizeof(basename));

    if (!basepath[0]) return -1;

    char dat_path[512];
    snprintf(dat_path, sizeof(dat_path), "%s%s/%s.dat",
             work_path, basepath, basepath);

    char thumb_name[200];
    snprintf(thumb_name, sizeof(thumb_name), "%s_%03d.raw", basename, index);

    /* 从 WQW 容器提取 */
    unsigned char *data = NULL;
    size_t size = 0;
    if (wqw_extract(dat_path, thumb_name, &data, &size) != 0 || size == 0) {
        ERR("thumb_extract: failed for %s (index=%d)", game_path, index);
        return -1;
    }

    /* 解析 RGB565 header（前 8 字节：[4B offset][2B width][2B height]） */
    int w = 0, h = 0, offset = 0;
    if (size >= 8) {
        offset = (int)(data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24));
        w = (int)(data[4] | (data[5] << 8));
        h = (int)(data[6] | (data[7] << 8));
    }

    *out_data = data;
    *out_size = size;
    if (out_w) *out_w = w;
    if (out_h) *out_h = h;

    /* 写入缓存 */
    int slot = -1;
    for (int i = 0; i < g_thumb_cache_count; i++) {
        if (!g_thumb_cache[i].valid) { slot = i; break; }
    }
    if (slot < 0 && g_thumb_cache_count < THUMB_CACHE_MAX) {
        slot = g_thumb_cache_count++;
    }
    if (slot >= 0) {
        strncpy(g_thumb_cache[slot].game_path, cache_key,
                sizeof(g_thumb_cache[slot].game_path) - 1);
        g_thumb_cache[slot].data = data;  /* 转移所有权 */
        g_thumb_cache[slot].size = size;
        g_thumb_cache[slot].width = w;
        g_thumb_cache[slot].height = h;
        g_thumb_cache[slot].valid = true;
    } else {
        /* 缓存满，不缓存，调用者负责 free */
        if (slot < 0) {
            /* 不放入缓存，调用者需要 free */
            return 0;
        }
    }

    LOG("thumb_extract: %s index=%d -> %dx%d (%zu B)",
        game_path, index, w, h, size);
    return 0;
}

/* ============================================================
 * thumb_count — 获取游戏有多少张缩略图
 *
 * 扫描 <NNN>/<NNN>.dat 里的 <basename>_000.raw, _001.raw, ...
 * ============================================================ */

int thumb_count(const char *game_path)
{
    if (!game_path) return 0;

    char basepath[128], basename[128];
    thumb_extract_basepath(game_path, basepath, sizeof(basepath));
    thumb_extract_basename(game_path, basename, sizeof(basename));

    if (!basepath[0]) return 0;

    char dat_path[512];
    snprintf(dat_path, sizeof(dat_path), "%s%s/%s.dat",
             work_path, basepath, basepath);

    if (!wqw_is_container(dat_path)) return 0;

    int count = 0;
    for (int i = 0; i < 64; i++) {
        char thumb_name[200];
        snprintf(thumb_name, sizeof(thumb_name), "%s_%03d.raw", basename, i);
        unsigned char *data = NULL;
        size_t size = 0;
        if (wqw_extract(dat_path, thumb_name, &data, &size) == 0 && size > 0) {
            free(data);
            count++;
        } else {
            break;  /* 连续缺失，停止 */
        }
    }
    return count;
}

/* ============================================================
 * thumb_cache_free — 释放所有缩略图缓存
 * ============================================================ */

void thumb_cache_free(void)
{
    for (int i = 0; i < THUMB_CACHE_MAX; i++) {
        if (g_thumb_cache[i].valid && g_thumb_cache[i].data) {
            free(g_thumb_cache[i].data);
        }
        g_thumb_cache[i].valid = false;
    }
    g_thumb_cache_count = 0;
    LOG("thumb_cache_free: all cached thumbnails freed");
}
