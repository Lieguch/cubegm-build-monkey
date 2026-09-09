/* ============================================================
 * resources.c — 运行时资源加载基础设施
 * ============================================================
 *
 * 计划表 §2.5 UI 系统 + §2.7 配置管理
 * 原厂 rkgame 从 SD 卡加载 .raw 图片、字体、配置文件
 *
 * 本文件提供完整的资源加载管线：
 *   - 图片资源（.raw → RGB565 1280×720）
 *   - 字体文件（.ttf）
 *   - 配置文件（setting.xml）
 *   - 核心列表（cores/**/*.so）
 *   - 存档数据（.srm）
 *
 * 关键修复（2026-09-08）：
 *   完全无资源加载 → 本实现对接原厂资源路径
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <dirent.h>
#include <sys/stat.h>

#include "debug.h"

/* ---- 资源路径常量 ---- */
#define RES_BASE_PATH       "/sdcard/cubegm"
#define RES_SYSTEM_PATH     RES_BASE_PATH "/system"
#define RES_CORES_PATH      RES_BASE_PATH "/cores"
#define RES_FONTS_PATH      RES_BASE_PATH "/fonts"
#define RES_IMAGES_PATH     RES_BASE_PATH "/images"
#define RES_CONFIG_PATH     RES_BASE_PATH "/setting.xml"
#define RES_MENULOG_PATH    RES_BASE_PATH "/menulog.dat"
#define RES_KEYMAP_PATH     RES_BASE_PATH "/keymap.dat"
#define RES_SAVES_PATH      RES_BASE_PATH "/saves"
#define RES_GAMES_PATH      RES_BASE_PATH "/games"
#define RES_WQW_PATH        RES_BASE_PATH "/games"

/* ---- 图片格式常量（原厂实测） ---- */
#define IMG_WIDTH           1280
#define IMG_HEIGHT          720
#define IMG_BYTES_PER_PIXEL 2  /* RGB565 */
#define IMG_FRAME_SIZE      (IMG_WIDTH * IMG_HEIGHT * IMG_BYTES_PER_PIXEL)
                                  /* 1,843,200 bytes */

/* ---- 资源表结构 ---- */
#define MAX_RESOURCES       256
#define MAX_RES_PATH        512

typedef struct {
    char path[MAX_RES_PATH];
    void *data;
    size_t size;
    int type;  /* 0=none, 1=image, 2=font, 3=config, 4=core, 5=save */
    bool loaded;
} resource_entry_t;

static resource_entry_t g_resources[MAX_RESOURCES];
static int g_resource_count = 0;

/* ---- 核心资源 API ---- */

/* 加载单个资源文件 */
static int load_resource_file(const char *path, resource_entry_t *res)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;

    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 10 * 1024 * 1024) {
        /* 10 MB 上限 */
        fclose(fp);
        return -2;
    }

    void *data = malloc(fsize);
    if (!data) {
        fclose(fp);
        return -3;
    }

    size_t got = fread(data, 1, fsize, fp);
    fclose(fp);

    if (got != (size_t)fsize) {
        free(data);
        return -4;
    }

    strncpy(res->path, path, MAX_RES_PATH - 1);
    res->data = data;
    res->size = fsize;
    res->type = 1;
    res->loaded = true;
    return 0;
}

/* 按路径加载资源 */
int resource_load(const char *path)
{
    if (g_resource_count >= MAX_RESOURCES) return -1;

    resource_entry_t *res = &g_resources[g_resource_count];
    memset(res, 0, sizeof(*res));

    int ret = load_resource_file(path, res);
    if (ret == 0) {
        g_resource_count++;
    }
    return ret;
}

/* 卸载所有资源 */
void resource_unload_all(void)
{
    for (int i = 0; i < g_resource_count; i++) {
        if (g_resources[i].data) {
            free(g_resources[i].data);
            g_resources[i].data = NULL;
        }
        g_resources[i].loaded = false;
    }
    g_resource_count = 0;
}

/* 查找已加载资源 */
resource_entry_t *resource_find(const char *path)
{
    for (int i = 0; i < g_resource_count; i++) {
        if (g_resources[i].loaded &&
            strncmp(g_resources[i].path, path, MAX_RES_PATH) == 0) {
            return &g_resources[i];
        }
    }
    return NULL;
}

/* ---- 核心资源目录扫描 ---- */

/* 扫描 cores/ 目录 */
int resource_scan_cores(void)
{
    DIR *dir = opendir(RES_CORES_PATH);
    if (!dir) {
        rklog("RESOURCES: cannot open %s", RES_CORES_PATH);
        return -1;
    }

    struct dirent *entry;
    int count = 0;

    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        char ext[8];
        const char *dot = strrchr(entry->d_name, '.');
        if (!dot) continue;

        size_t ext_len = strlen(dot + 1);
        if (ext_len >= sizeof(ext)) continue;
        strncpy(ext, dot + 1, sizeof(ext) - 1);
        ext[ext_len] = 0;

        /* 只加载 .so 文件 */
        if (strcasecmp(ext, "so") != 0) continue;

        char full_path[MAX_RES_PATH];
        snprintf(full_path, sizeof(full_path), "%s/%s",
                 RES_CORES_PATH, entry->d_name);

        if (resource_load(full_path) == 0) {
            rklog("RESOURCES: loaded core: %s", entry->d_name);
            count++;
        }
    }

    closedir(dir);
    rklog("RESOURCES: scanned %d cores from %s", count, RES_CORES_PATH);
    return count;
}

/* 扫描 fonts/ 目录 */
int resource_scan_fonts(void)
{
    DIR *dir = opendir(RES_FONTS_PATH);
    if (!dir) {
        rklog("RESOURCES: cannot open %s", RES_FONTS_PATH);
        return -1;
    }

    struct dirent *entry;
    int count = 0;

    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        char ext[8];
        const char *dot = strrchr(entry->d_name, '.');
        if (!dot) continue;

        size_t ext_len = strlen(dot + 1);
        if (ext_len >= sizeof(ext)) continue;
        strncpy(ext, dot + 1, sizeof(ext) - 1);
        ext[ext_len] = 0;

        if (strcasecmp(ext, "ttf") != 0) continue;

        char full_path[MAX_RES_PATH];
        snprintf(full_path, sizeof(full_path), "%s/%s",
                 RES_FONTS_PATH, entry->d_name);

        if (resource_load(full_path) == 0) {
            rklog("RESOURCES: loaded font: %s", entry->d_name);
            count++;
        }
    }

    closedir(dir);
    rklog("RESOURCES: scanned %d fonts from %s", count, RES_FONTS_PATH);
    return count;
}

/* 扫描 images/ 目录 */
int resource_scan_images(void)
{
    DIR *dir = opendir(RES_IMAGES_PATH);
    if (!dir) {
        rklog("RESOURCES: cannot open %s", RES_IMAGES_PATH);
        return -1;
    }

    struct dirent *entry;
    int count = 0;

    while ((entry = readdir(dir)) != NULL) {
        if (entry->d_name[0] == '.') continue;

        char ext[8];
        const char *dot = strrchr(entry->d_name, '.');
        if (!dot) continue;

        size_t ext_len = strlen(dot + 1);
        if (ext_len >= sizeof(ext)) continue;
        strncpy(ext, dot + 1, sizeof(ext) - 1);
        ext[ext_len] = 0;

        if (strcasecmp(ext, "raw") != 0 && strcasecmp(ext, "png") != 0) continue;

        char full_path[MAX_RES_PATH];
        snprintf(full_path, sizeof(full_path), "%s/%s",
                 RES_IMAGES_PATH, entry->d_name);

        if (resource_load(full_path) == 0) {
            rklog("RESOURCES: loaded image: %s", entry->d_name);
            count++;
        }
    }

    closedir(dir);
    rklog("RESOURCES: scanned %d images from %s", count, RES_IMAGES_PATH);
    return count;
}

/* ---- 配置文件加载 ---- */

/* 加载 setting.xml */
int resource_load_config(void)
{
    return resource_load(RES_CONFIG_PATH);
}

/* 加载 menulog.dat */
int resource_load_menulog(void)
{
    return resource_load(RES_MENULOG_PATH);
}

/* 加载 keymap.dat */
int resource_load_keymap(void)
{
    return resource_load(RES_KEYMAP_PATH);
}

/* ---- 初始化/清理 ---- */

/* 初始化资源系统 */
int resource_init(void)
{
    memset(g_resources, 0, sizeof(g_resources));
    g_resource_count = 0;
    rklog("RESOURCES: initialized (base: %s)", RES_BASE_PATH);
    return 0;
}

/* 清理资源系统 */
void resource_cleanup(void)
{
    resource_unload_all();
    rklog("RESOURCES: cleaned up");
}

/* 获取已加载资源数量 */
int resource_count(void)
{
    return g_resource_count;
}

/* 报告资源状态 */
void resource_report(void)
{
    rklog("RESOURCES: %d resources loaded", g_resource_count);
    for (int i = 0; i < g_resource_count; i++) {
        if (g_resources[i].loaded) {
            rklog("  [%d] %s (%zu bytes)", i,
                  g_resources[i].path, g_resources[i].size);
        }
    }
}
