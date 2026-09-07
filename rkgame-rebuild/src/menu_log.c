/* ============================================================
 * menu_log.c — LoadMenuLog / SaveMenuLog（对齐原厂 mui_menu 行为）
 * ============================================================
 *
 * 原厂 menu.log 格式（Ghidra 反编译实证）：
 *   每行一个游戏路径，按最后访问时间排序（最新的在前）
 *   格式：`path` （纯路径，无 CSV 字段）
 *   最大 32 条
 *
 * 用途：
 *   - 启动时 LoadMenuLog() 读取上次菜单状态（最近打开的游戏列表）
 *   - 退出时 SaveMenuLog() 保存当前列表
 *   - 与 recent.lst / favorites.lst 互补：menu.log 是"菜单恢复"，
 *     recent.lst 是"最近运行"，favorites.lst 是"收藏"
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "rkgame.h"
#include "debug.h"

#define MENU_LOG_MAX  32

static char g_menu_log[MENU_LOG_MAX][512];
static int  g_menu_log_count = 0;

/* 加载 menu.log */
int LoadMenuLog(void)
{
    char path[600];
    snprintf(path, sizeof(path), "%smenu.log", work_path);

    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG("LoadMenuLog: %s not found, starting empty", path);
        g_menu_log_count = 0;
        return 0;
    }

    g_menu_log_count = 0;
    char line[600];
    while (g_menu_log_count < MENU_LOG_MAX && fgets(line, sizeof(line), fp)) {
        size_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        if (len > 0 && len < 512) {
            strncpy(g_menu_log[g_menu_log_count], line, 511);
            g_menu_log[g_menu_log_count][511] = '\0';
            g_menu_log_count++;
        }
    }
    fclose(fp);
    LOG("LoadMenuLog: loaded %d entries from %s", g_menu_log_count, path);
    return g_menu_log_count;
}

/* 保存 menu.log */
int SaveMenuLog(void)
{
    char path[600];
    snprintf(path, sizeof(path), "%smenu.log", work_path);

    FILE *fp = fopen(path, "w");
    if (!fp) {
        ERR("SaveMenuLog: cannot open %s for write", path);
        return -1;
    }

    for (int i = 0; i < g_menu_log_count; i++) {
        fprintf(fp, "%s\n", g_menu_log[i]);
    }
    fclose(fp);
    LOG("SaveMenuLog: saved %d entries to %s", g_menu_log_count, path);
    return g_menu_log_count;
}

/* 获取 menu.log 条目（只读） */
const char *menu_log_get(int idx)
{
    if (idx < 0 || idx >= g_menu_log_count) return NULL;
    return g_menu_log[idx];
}

int menu_log_count(void) { return g_menu_log_count; }

/* 添加/更新一条记录（移到最前面） */
void menu_log_add(const char *path)
{
    if (!path || !path[0]) return;

    /* 如果已存在，先移除 */
    for (int i = 0; i < g_menu_log_count; i++) {
        if (strcmp(g_menu_log[i], path) == 0) {
            /* 后移所有条目 */
            for (int j = i; j < g_menu_log_count - 1; j++) {
                strncpy(g_menu_log[j], g_menu_log[j+1], 511);
                g_menu_log[j][511] = '\0';
            }
            g_menu_log_count--;
            break;
        }
    }

    /* 插入到最前面 */
    if (g_menu_log_count >= MENU_LOG_MAX) g_menu_log_count--;
    for (int i = g_menu_log_count; i > 0; i--) {
        strncpy(g_menu_log[i], g_menu_log[i-1], 511);
        g_menu_log[i][511] = '\0';
    }
    strncpy(g_menu_log[0], path, 511);
    g_menu_log[0][511] = '\0';
    if (g_menu_log_count < MENU_LOG_MAX) g_menu_log_count++;
}
