/* ============================================================
 * ui_config.c — 配置加载实现
 * ============================================================
 *
 * 使用 lib/mxml 解析 XML（替换原有手工字符串解析）
 *
 * 原厂 mui_LoadSetting @ 0x171f8 解析 6 项：
 *   <config language="...">  → g_cfg.m_ui
 *   <config volume="...">    → g_cfg.volume
 *   <defaultlanguage>        → g_cfg.defaultlanguage
 *   <displayfps>             → g_cfg.displayfps
 *   <save_directory>         → save_directory (全局 char[])
 *   <music><bgm file="..">   → g_cfg.music_file
 * ============================================================ */

#include "ui_config.h"
#include "rkgame.h"
#include "mxml.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>

/* 字符串属性解析辅助 */
static const char *mxml_attr_or(mxml_node_t *n, const char *k, const char *def)
{
    if (!n) return def;
    const char *v = mxml_get_attr(n, k);
    return v ? v : def;
}

static int mxml_attr_int(mxml_node_t *n, const char *k, int def)
{
    if (!n) return def;
    const char *v = mxml_get_attr(n, k);
    if (!v) return def;
    char *end = NULL;
    long val = strtol(v, &end, 0);
    if (end == v) return def;
    return (int)val;
}

/* 递归遍历，查找元素并处理 */
static void apply_element(mxml_node_t *node)
{
    if (!node || node->type != MXML_ELEMENT || !node->value) return;
    const char *name = node->value;
    int visited = 0;

    if (strcmp(name, "config") == 0) {
        /* <config language="..." volume="..."> */
        const char *lang = mxml_get_attr(node, "language");
        if (lang) g_cfg.m_ui = mxml_attr_int(node, "language", g_cfg.m_ui);
        (void)lang;
        g_cfg.volume = mxml_attr_int(node, "volume", g_cfg.volume);
        visited = 1;
    } else if (strcmp(name, "language") == 0 || strcmp(name, "languageid") == 0) {
        g_cfg.m_ui = mxml_attr_int(node, "value", g_cfg.m_ui);
        visited = 1;
    } else if (strcmp(name, "volume") == 0) {
        g_cfg.volume = mxml_attr_int(node, "value", g_cfg.volume);
        visited = 1;
    } else if (strcmp(name, "defaultlanguage") == 0) {
        g_cfg.defaultlanguage = mxml_attr_int(node, "value", g_cfg.defaultlanguage);
        visited = 1;
    } else if (strcmp(name, "displayfps") == 0) {
        g_cfg.displayfps = mxml_attr_int(node, "value", g_cfg.displayfps);
        visited = 1;
    } else if (strcmp(name, "save_directory") == 0) {
        const char *sd = mxml_get_attr(node, "directory");
        if (!sd) sd = mxml_get_attr(node, "value");
        if (!sd) sd = mxml_get_content(node);
        if (sd) snprintf(save_directory, sizeof(save_directory), "%s", sd);
        visited = 1;
    } else if (strcmp(name, "filebrowser") == 0) {
        const char *fb = mxml_get_attr(node, "value");
        if (!fb) fb = mxml_get_content(node);
        if (fb) snprintf(g_cfg.filebrowser, sizeof(g_cfg.filebrowser), "%s", fb);
        visited = 1;
    } else if (strcmp(name, "music") == 0 || strcmp(name, "bgm") == 0) {
        const char *f = mxml_get_attr(node, "file");
        if (f) snprintf(g_cfg.music_file, sizeof(g_cfg.music_file), "%s", f);
        visited = 1;
    } else if (strcmp(name, "effect0") == 0) {
        const char *f = mxml_get_attr(node, "file");
        if (f) snprintf(g_cfg.effect0_file, sizeof(g_cfg.effect0_file), "%s", f);
        visited = 1;
    } else if (strcmp(name, "effect1") == 0) {
        const char *f = mxml_get_attr(node, "file");
        if (f) snprintf(g_cfg.effect1_file, sizeof(g_cfg.effect1_file), "%s", f);
        visited = 1;
    } else if (strcmp(name, "autorun") == 0) {
        const char *f = mxml_get_attr(node, "file");
        const char *d = mxml_get_attr(node, "driver");
        if (f) snprintf(g_cfg.autorun_path, sizeof(g_cfg.autorun_path), "%s", f);
        if (d) snprintf(g_cfg.autorun_driver, sizeof(g_cfg.autorun_driver), "%s", d);
        visited = 1;
    } else if (strcmp(name, "displaythread") == 0) {
        g_cfg.displaythread = mxml_attr_int(node, "value", g_cfg.displaythread);
        visited = 1;
    } else if (strcmp(name, "softrotation") == 0) {
        g_cfg.soft_rotation = mxml_attr_int(node, "value", g_cfg.soft_rotation);
        visited = 1;
    } else if (strcmp(name, "logfile") == 0) {
        const char *lf = mxml_get_attr(node, "value");
        if (!lf) lf = mxml_get_content(node);
        if (lf) snprintf(g_cfg.logfile, sizeof(g_cfg.logfile), "%s", lf);
        visited = 1;
    }

    (void)visited;
    (void)mxml_attr_or;  /* 保留符号 */
}

int mui_LoadSetting(const char *path)
{
    if (!path) return -1;
    mxml_node_t *root = mxml_load_file(path);
    if (!root) {
        RKLOG_W("mui_LoadSetting: cannot open %s", path);
        return -1;
    }

    /* 遍历所有节点（BFS） */
    mxml_node_t *queue[256];
    int qh = 0, qt = 0;
    queue[qt++] = root;
    int count = 0;
    while (qh < qt) {
        mxml_node_t *n = queue[qh++];
        apply_element(n);
        count++;
        for (mxml_node_t *c = n->child; c && qt < 256; c = c->next) {
            queue[qt++] = c;
        }
    }

    mxml_delete(root);
    RKLOG_I("mui_LoadSetting: %s (%d nodes; vol=%d lang=%d fps=%d save=%s)",
            path, count, g_cfg.volume, g_cfg.m_ui, g_cfg.displayfps, save_directory);
    return 0;
}

int mui_LoadConfig(const char *path)
{
    if (!path) return -1;
    mxml_node_t *root = mxml_load_file(path);
    if (!root) {
        RKLOG_W("mui_LoadConfig: cannot open %s", path);
        return -1;
    }
    int count = 0;
    mxml_node_t *n = root->child;
    while (n) {
        if (n->type == MXML_ELEMENT && n->value &&
            (strcmp(n->value, "core") == 0 || strcmp(n->value, "system") == 0)) {
            count++;
        }
        n = n->next;
    }
    mxml_delete(root);
    RKLOG_I("mui_LoadConfig: %s (%d cores)", path, count);
    return 0;
}
