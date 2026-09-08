/* ============================================================
 * shoucang.h — 全局收藏管理器（对齐原厂 shoucang 1.4 KB）
 * ============================================================
 *
 * 原厂 shoucang 符号是一个全局函数，负责：
 *   - 内存中维护收藏列表（游戏 ID/名字/路径）
 *   - 加载/保存收藏数据到 saves/shoucang.cfg
 *   - 供 mui_shoucang / mui_menu 等 UI 调用
 * ============================================================ */

#ifndef SHOUCANG_GLOBAL_H
#define SHOUCANG_GLOBAL_H

#include <stdbool.h>

#define SHOUCANG_MAX 128
#define SHOUCANG_NAME_LEN 96
#define SHOUCANG_PATH_LEN 256

typedef struct {
    char name[SHOUCANG_NAME_LEN];
    char path[SHOUCANG_PATH_LEN];
    char type[16];        /* 分类：000..008 */
} shoucang_entry_t;

extern shoucang_entry_t g_shoucang[SHOUCANG_MAX];
extern int g_shoucang_count;

int  shoucang_init(void);
int  shoucang_add(const char *name, const char *path, const char *type);
int  shoucang_remove(const char *path);
int  shoucang_contains(const char *path);
int  shoucang_count_items(void);
int  shoucang_load(const char *path);
int  shoucang_save(const char *path);
void shoucang_clear(void);

/* 原厂 shoucang 是一个入口函数，做初始化 */
void shoucang(void);

#endif /* SHOUCANG_GLOBAL_H */
