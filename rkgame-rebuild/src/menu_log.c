/* ============================================================
 * menu_log.c — LoadMenuLog / SaveMenuLog（对齐原厂二进制格式）
 * ============================================================
 *
 * 原厂 menu.log 格式（Ghidra 反编译实证 0x211f8 / 0x21388）：
 *   - 固定 0x1bc (444) 字节二进制 blob
 *   - fwrite(m_menulog, 1, 0x1bc, fp) / fread(m_menulog, 1, 0x1bc, fp)
 *   - 存储 UI 状态（选中索引、滚动位置、页面等）
 *   - AutoRestoreKey 位掩码控制哪些字段在重启后保留
 *
 * 我方实现：
 *   - 定义 menu_log_t 结构体（444 字节），匹配原厂字段布局
 *   - 核心字段：selected_index / scroll_offset / current_page
 *   - 保留字段用于未来扩展
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>

#include "rkgame.h"
#include "debug.h"

/* 原厂 m_menulog 结构体（444 字节 = 0x1bc）
 * 字段布局基于 Ghidra 反编译偏移量推断 */
typedef struct {
    /* 前 0x11c 字节：UI 状态字段（与原厂 m_menulog 对齐） */
    int  ui_state[0x11c / 4];      /* 0x000 - 0x11B: 预留 UI 状态 */

    /* AutoRestoreKey 控制的字段 */
    int  field_284;                /* 0x11C: AutoRestoreKey & 1 */
    int  field_288;                /* 0x120 */
    int  field_292;                /* 0x124: AutoRestoreKey & 2 */
    int  field_296;                /* 0x128 */
    int  field_300;                /* 0x12C */
    int  field_304;                /* 0x130 */
    int  field_308;                /* 0x134: AutoRestoreKey & 4 */
    int  field_312;                /* 0x138 */
    int  field_316;                /* 0x13C: AutoRestoreKey & 8 */
    int  field_320;                /* 0x140 */
    int  field_324;                /* 0x144: AutoRestoreKey & 0x10 */
    int  field_328;                /* 0x148 */
    int  field_332;                /* 0x14C */

    /* 0x150 - 0x1B3: 100 字节数据区 */
    unsigned char data_block[100]; /* 0x150 - 0x1AB */

    /* 尾部字段 */
    int  field_436;                /* 0x1B4 */
    int  field_440;                /* 0x1B8 */
    /* 总计 0x1BC = 444 字节 */
} menu_log_t;

/* 全局 menu.log 状态 */
static menu_log_t g_menulog = {0};
static int  g_menulog_dirty = 0;

/* 验证结构体大小 = 444 字节 */
_Static_assert(sizeof(menu_log_t) == 0x1bc, "menu_log_t must be 444 bytes");

/* AutoRestoreKey（从 setting.xml 的 <autorestore> 读取，存储在 g_cfg.autorestore） */

/* ============================================================
 * LoadMenuLog — 读取二进制 menu.log（对齐原厂 0x211f8）
 * ============================================================ */

int LoadMenuLog(void)
{
    char path[600];
    snprintf(path, sizeof(path), "%smenu.log", work_path);

    FILE *fp = fopen(path, "rb");
    if (!fp) {
        /* 文件不存在：初始化默认值（对齐原厂 0x211f8 memset + defaults） */
        memset(&g_menulog, 0, sizeof(g_menulog));
        g_menulog.field_292 = 1;
        g_menulog.field_324 = 1;
        g_menulog.field_304 = -1;   /* 0xffffffff */
        g_menulog.field_332 = -1;   /* 0xffffffff */
        LOG("LoadMenuLog: %s not found, initialized defaults (444B binary)", path);
        return 0;
    }

    size_t n = fread(&g_menulog, 1, sizeof(g_menulog), fp);
    fclose(fp);

    if (n < sizeof(g_menulog)) {
        LOG("LoadMenuLog: %s truncated (%zu/%zu bytes), filled remainder",
            path, n, sizeof(g_menulog));
        /* 用默认值填充剩余部分 */
        memset((unsigned char *)&g_menulog + n, 0, sizeof(g_menulog) - n);
    }

    /* AutoRestoreKey 位掩码：控制哪些字段在重启后保留 */
    int auto_key = g_cfg.autorestore;

    if (!(auto_key & 1)) {
        g_menulog.field_284 = 0;
        g_menulog.field_288 = 0;
    }
    if (!(auto_key & 2)) {
        g_menulog.field_296 = 0;
        g_menulog.field_300 = 0;
        g_menulog.field_292 = 1;
        g_menulog.field_304 = -1;
    }
    if (!(auto_key & 4)) {
        g_menulog.field_312 = 0;
        g_menulog.field_308 = 0;
    }
    if (!(auto_key & 8)) {
        g_menulog.field_320 = 0;
        g_menulog.field_316 = 0;
    }
    if (!(auto_key & 0x10)) {
        g_menulog.field_324 = 1;
        g_menulog.field_332 = -1;
        g_menulog.field_328 = auto_key & 0x10;
        memset(g_menulog.data_block, (unsigned char)(auto_key & 0x10), 100);
        g_menulog.field_436 = auto_key & 0x10;
        g_menulog.field_440 = auto_key & 0x10;
    }

    LOG("LoadMenuLog: loaded %zu bytes from %s (autorestore=0x%x)",
        n, path, auto_key);
    return (int)n;
}

/* ============================================================
 * SaveMenuLog — 写入二进制 menu.log（对齐原厂 0x21388）
 * ============================================================ */

int SaveMenuLog(void)
{
    char path[600];
    snprintf(path, sizeof(path), "%smenu.log", work_path);

    FILE *fp = fopen(path, "wb");
    if (!fp) {
        ERR("SaveMenuLog: cannot open %s for write", path);
        return -1;
    }

    size_t n = fwrite(&g_menulog, 1, sizeof(g_menulog), fp);
    fflush(fp);

    /* fsync 确保持久化（对齐原厂 0x21388 fsync 调用） */
    int fd = fileno(fp);
    if (fd >= 0) fsync(fd);

    fclose(fp);
    LOG("SaveMenuLog: saved %zu bytes to %s", n, path);
    return (int)n;
}

/* ============================================================
 * UI 状态更新接口
 * ============================================================ */

/* 更新菜单选中索引（存储在 field_284） */
void menu_log_set_selected(int idx)
{
    g_menulog.field_284 = idx;
    g_menulog_dirty = 1;
}

int menu_log_get_selected(void)
{
    return g_menulog.field_284;
}

/* 更新滚动偏移（存储在 field_288） */
void menu_log_set_scroll(int offset)
{
    g_menulog.field_288 = offset;
    g_menulog_dirty = 1;
}

int menu_log_get_scroll(void)
{
    return g_menulog.field_288;
}

/* 更新当前页面（存储在 field_292） */
void menu_log_set_page(int page)
{
    g_menulog.field_292 = page;
    g_menulog_dirty = 1;
}

int menu_log_get_page(void)
{
    return g_menulog.field_292;
}

/* 标记脏数据（下次 SaveMenuLog 时写入） */
void menu_log_mark_dirty(void)
{
    g_menulog_dirty = 1;
}

int menu_log_is_dirty(void)
{
    return g_menulog_dirty;
}

/* 重置为默认状态 */
void menu_log_reset(void)
{
    memset(&g_menulog, 0, sizeof(g_menulog));
    g_menulog.field_292 = 1;
    g_menulog.field_324 = 1;
    g_menulog.field_304 = -1;
    g_menulog.field_332 = -1;
    g_menulog_dirty = 1;
    LOG("menu_log_reset: state reset to defaults");
}
