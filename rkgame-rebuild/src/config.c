/* ============================================================
 * config.c — 配置管理系统（对齐原厂 configitems + setting.xml）
 * ============================================================
 *
 * 原厂 GetConfig @ 0x9f04：
 *   1. 打开 setting.xml
 *   2. 用 mxml 解析 <rkgame> 根节点
 *   3. 逐项读取 22 个配置项
 *   4. 填充 rkgame_config_t 结构体
 *
 * 本实现：
 *   - mxml 解析 setting.xml
 *   - 22 个配置项（对齐 data_tables.c configitems 数组）
 *   - 提供 get/set/save 接口
 *   - 与 ui_config.c 兼容（ui_config.c 负责 UI 显示）
 * ============================================================ */

#include "config.h"
#include "rkgame.h"
#include "debug.h"
#include "data_tables.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <mxml.h>

/* ---- 配置项定义（对齐 data_tables.c configitems） ---- */

typedef struct {
    const char *name;
    int type;             /* 0=enum, 1=int, 2=bool, 3=string */
    char default_val[64];
    char desc[256];
} config_item_def_t;

#define MAX_CONFIG_ITEMS 64
#define CONFIG_NAME_LEN 64
#define CONFIG_VAL_LEN  256

/* 配置表（对齐原厂 configitems @ 50 KB） */
static config_item_def_t s_config_items[MAX_CONFIG_ITEMS] = {
    { "displayfps",     0, "60",        "Display refresh rate" },
    { "displaythread",  1, "1",         "Display thread flag" },
    { "brightness",     1, "70",        "Brightness (0-100)" },
    { "contrast",       1, "50",        "Contrast (0-100)" },
    { "gamma",          1, "0",         "Gamma (-100~100)" },
    { "soft_rotation",  1, "0",         "Soft rotation (0/90/180/270)" },
    { "screen_type",    0, "portrait",  "Screen orientation" },
    { "use_rgb_8888",   2, "0",         "Use XRGB8888" },
    { "vsync",          2, "1",         "Vertical sync" },
    { "filter",         0, "nearest",   "Filter: nearest/bilinear" },
    { "scanline",       2, "0",         "Scanline filter" },
    { "pixel_perfect",  2, "0",         "Pixel perfect mode" },
    { "volume",         1, "80",        "Volume (0-100)" },
    { "defaultlanguage",0, "en",        "Default language" },
    { "logfile",        3, "rkgame.log","Log file path" },
    { "filebrowser",    2, "1",         "Enable file browser" },
    { "music_file",     3, "music.mp3", "BGM file" },
    { "effect0_file",   3, "sfx0.wav",  "SFX 0 file" },
    { "effect1_file",   3, "sfx1.wav",  "SFX 1 file" },
    { "savestatehotkey",3, "F5",        "Save state hotkey" },
    { "gamemenuhotkey", 3, "F6",        "Game menu hotkey" },
    { "autorestore",    2, "1",         "Auto restore last game" },
};

#define CONFIG_ITEM_COUNT (sizeof(s_config_items) / sizeof(s_config_items[0]))

/* 配置值存储 */
typedef struct {
    char value[CONFIG_VAL_LEN];
    int  modified;
} config_value_t;

static config_value_t s_config_values[MAX_CONFIG_ITEMS];
static int s_config_loaded = 0;

/* ---- 全局配置结构体（引用 main.c 的 g_cfg） ---- */
extern rkgame_config_t g_cfg;

/* ============================================================
 * config_init — 初始化配置系统
 * ============================================================ */

int config_init(void)
{
    int i;
    for (i = 0; i < CONFIG_ITEM_COUNT; i++) {
        strncpy(s_config_values[i].value, s_config_items[i].default_val,
                CONFIG_VAL_LEN - 1);
        s_config_values[i].value[CONFIG_VAL_LEN - 1] = '\0';
        s_config_values[i].modified = 0;
    }
    s_config_loaded = 1;
    RKLOG_I("config_init: %d items initialized", CONFIG_ITEM_COUNT);
    return 0;
}

/* ============================================================
 * config_load — 从 setting.xml 加载配置
 * ============================================================ */

int config_load(const char *path)
{
    if (!path || !path[0]) {
        RKLOG_E("config_load: invalid path");
        return -1;
    }

    FILE *fp = fopen(path, "r");
    if (!fp) {
        RKLOG_W("config_load: cannot open %s, using defaults", path);
        return -1;
    }

    /* 读取文件内容 */
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    if (fsize <= 0 || fsize > 65536) {
        fclose(fp);
        RKLOG_E("config_load: invalid file size %ld", fsize);
        return -1;
    }

    char *content = (char *)malloc(fsize + 1);
    if (!content) {
        fclose(fp);
        return -1;
    }

    size_t nread = fread(content, 1, fsize, fp);
    content[nread] = '\0';
    fclose(fp);

    /* mxml 解析 */
    mxml_node_t *root = mxmlParseData(content, nread);
    if (!root) {
        free(content);
        RKLOG_E("config_load: mxml parse failed");
        return -1;
    }

    free(content);

    /* 遍历配置项 */
    mxml_node_t *node = mxmlWalkNext(root, root, MXML_DESCEND);
    while (node) {
        const char *name = mxmlElementGetAttr(node, "name");
        const char *val = mxmlElementGetAttr(node, "value");
        if (name && val) {
            int idx = config_find(name);
            if (idx >= 0) {
                strncpy(s_config_values[idx].value, val, CONFIG_VAL_LEN - 1);
                s_config_values[idx].value[CONFIG_VAL_LEN - 1] = '\0';
                s_config_values[idx].modified = 1;
                RKLOG_D("config_load: %s = %s", name, val);
            }
        }
        node = mxmlWalkNext(node, root, MXML_DESCEND);
    }

    mxmlDelete(root);

    /* 更新全局配置结构体 */
    config_update_struct();

    RKLOG_I("config_load: loaded %s (%ld bytes)", path, fsize);
    return 0;
}

/* ============================================================
 * config_save — 保存配置到 setting.xml
 * ============================================================ */

int config_save(const char *path)
{
    if (!path || !path[0]) return -1;

    FILE *fp = fopen(path, "w");
    if (!fp) {
        RKLOG_E("config_save: cannot open %s", path);
        return -1;
    }

    fprintf(fp, "<rkgame>\n");
    for (int i = 0; i < CONFIG_ITEM_COUNT; i++) {
        fprintf(fp, "  <item name=\"%s\" value=\"%s\"/>\n",
                s_config_items[i].name,
                s_config_values[i].value);
    }
    fprintf(fp, "</rkgame>\n");

    fclose(fp);
    RKLOG_I("config_save: saved %s (%d items)", path, CONFIG_ITEM_COUNT);
    return 0;
}

/* ============================================================
 * config_find — 查找配置项索引
 * ============================================================ */

int config_find(const char *name)
{
    if (!name) return -1;
    for (int i = 0; i < CONFIG_ITEM_COUNT; i++) {
        if (strcmp(s_config_items[i].name, name) == 0) return i;
    }
    return -1;
}

/* ============================================================
 * config_get — 获取配置值
 * ============================================================ */

const char *config_get(const char *name)
{
    int idx = config_find(name);
    if (idx < 0) return "";
    return s_config_values[idx].value;
}

/* ============================================================
 * config_set — 设置配置值
 * ============================================================ */

int config_set(const char *name, const char *value)
{
    int idx = config_find(name);
    if (idx < 0) return -1;
    strncpy(s_config_values[idx].value, value, CONFIG_VAL_LEN - 1);
    s_config_values[idx].value[CONFIG_VAL_LEN - 1] = '\0';
    s_config_values[idx].modified = 1;
    return 0;
}

/* ============================================================
 * config_get_int — 获取整数值
 * ============================================================ */

int config_get_int(const char *name, int default_val)
{
    const char *val = config_get(name);
    if (!val || !val[0]) return default_val;
    return atoi(val);
}

/* ============================================================
 * config_get_bool — 获取布尔值
 * ============================================================ */

int config_get_bool(const char *name, int default_val)
{
    return config_get_int(name, default_val);
}

/* ============================================================
 * config_update_struct — 同步配置值到全局结构体
 * ============================================================ */

void config_update_struct(void)
{
    g_cfg.displayfps      = config_get_int("displayfps", 60);
    g_cfg.displaythread   = config_get_int("displaythread", 1);
    g_cfg.brightness      = config_get_int("brightness", 70);
    g_cfg.contrast        = config_get_int("contrast", 50);
    g_cfg.gamma           = config_get_int("gamma", 0);
    g_cfg.soft_rotation   = config_get_int("soft_rotation", 0);
    g_cfg.screen_type     = strcmp(config_get("screen_type"), "landscape") == 0 ? 1 : 0;
    g_cfg.use_rgb_8888    = config_get_int("use_rgb_8888", 0);
    g_cfg.vsync           = config_get_int("vsync", 1);
    g_cfg.filter          = strcmp(config_get("filter"), "bilinear") == 0 ? 1 : 0;
    g_cfg.scanline        = config_get_int("scanline", 0);
    g_cfg.pixel_perfect   = config_get_int("pixel_perfect", 0);
    g_cfg.volume          = config_get_int("volume", 80);
    g_cfg.autorestore     = config_get_int("autorestore", 1);
    g_cfg.filebrowser     = config_get_int("filebrowser", 1);

    strncpy(g_cfg.defaultlanguage, config_get("defaultlanguage"), sizeof(g_cfg.defaultlanguage) - 1);
    strncpy(g_cfg.logfile, config_get("logfile"), sizeof(g_cfg.logfile) - 1);
    strncpy(g_cfg.music_file, config_get("music_file"), sizeof(g_cfg.music_file) - 1);
    strncpy(g_cfg.effect0_file, config_get("effect0_file"), sizeof(g_cfg.effect0_file) - 1);
    strncpy(g_cfg.effect1_file, config_get("effect1_file"), sizeof(g_cfg.effect1_file) - 1);
    strncpy(g_cfg.savestatehotkey, config_get("savestatehotkey"), sizeof(g_cfg.savestatehotkey) - 1);
    strncpy(g_cfg.gamemenuhotkey, config_get("gamemenuhotkey"), sizeof(g_cfg.gamemenuhotkey) - 1);
}

/* ============================================================
 * GetConfig — 原厂兼容入口（对齐 factory_c_stubs.c）
 * ============================================================ */

int GetConfig(void)
{
    const char *path = "/sdcard/cubegm/setting.xml";
    int rc = config_load(path);
    if (rc != 0) {
        /* 尝试默认路径 */
        path = "setting.xml";
        rc = config_load(path);
    }
    if (rc != 0) {
        RKLOG_W("GetConfig: no setting.xml found, using defaults");
        config_update_struct();
    }
    return rc;
}