/* ============================================================
 * rkgame-rebuild — cpd.h
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
 * 我方现有 ui_zip.c 已支持 ZIP 解压，本模块复用其 API。
 * ============================================================ */

#ifndef CPD_H
#define CPD_H

#include <stdbool.h>
#include <stddef.h>
#include "ui_zip.h"

/* 资源缓存（从 resource.cpd 提取） */
typedef struct {
    /* game.raw: 游戏列表布局 */
    unsigned char *game_raw;
    size_t         game_raw_size;
    int            game_raw_w, game_raw_h;

    /* menu.raw: 菜单布局 */
    unsigned char *menu_raw;
    size_t         menu_raw_size;
    int            menu_raw_w, menu_raw_h;

    /* nodata.raw: 无数据占位图 (320×240 RGB565) */
    unsigned char *nodata_raw;
    size_t         nodata_raw_size;
    int            nodata_raw_w, nodata_raw_h;

    /* ui.cfg: UI 布局配置 */
    unsigned char *ui_cfg;
    size_t         ui_cfg_size;

    /* 是否已加载 */
    bool           loaded;
} cpd_resource_t;

/* UI_Res.cpd 缓存 */
typedef struct {
    /* 平台背景图（640×480 BGRA raw） */
    unsigned char **bg_raw;          /* [platform_index] */
    size_t         *bg_size;
    int            *bg_w, *bg_h;
    int            bg_count;

    /* 图标精灵表 */
    unsigned char **icon_raw;
    size_t         *icon_size;
    int            *icon_w, *icon_h;
    int            icon_count;

    bool           loaded;
} cpd_ui_res_t;

/* 全局资源缓存 */
extern cpd_resource_t g_cpd_resource;
extern cpd_ui_res_t   g_cpd_ui_res;

/* 加载 resource.cpd（提取 game.raw/menu.raw/nodata.raw/ui.cfg） */
int  cpd_load_resource(const char *work_path);

/* 加载 UI_Res.cpd（提取背景+图标） */
int  cpd_load_ui_res(const char *work_path);

/* 释放所有 cpd 资源 */
void cpd_free_all(void);

/* 获取 nodata 占位图（无封面时使用） */
unsigned char *cpd_get_nodata(int *out_w, int *out_h);

/* 获取 menu.raw（优先 resource.cpd，回退 ui_*.zip） */
unsigned char *cpd_get_menu_raw(int *out_w, int *out_h);

/* 获取 game.raw（优先 resource.cpd，回退 ui_*.zip） */
unsigned char *cpd_get_game_raw(int *out_w, int *out_h);

/* 获取平台背景图（从 UI_Res.cpd） */
unsigned char *cpd_get_bg_raw(int platform_index, int *out_w, int *out_h);

/* 诊断：打印 cpd 加载状态 */
void cpd_report(void);

#endif /* CPD_H */
