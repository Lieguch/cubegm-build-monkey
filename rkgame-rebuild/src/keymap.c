/* ============================================================
 * keymap.c — 每核心键位映射（InitKeyMapping0fEmuType / SaveKeyMappingConfigFile）
 * ============================================================
 *
 * 原厂行为（Ghidra 反编译实证）：
 *   - InitKeyMapping0fEmuType(core_name)：加载 cores/keymap_<core>.xml
 *   - SaveKeyMappingConfigFile()：保存当前键位映射到文件
 *   - 每个核心可以有独立的按键绑定
 *   - 默认使用全局 joystick.zip 映射
 *
 * 文件格式（简化 XML）：
 *   <keymap core="libemu_fbalpha2012.so">
 *     <bind from="KEY_A" to="0"/>
 *     <bind from="KEY_B" to="1"/>
 *     ...
 *   </keymap>
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#include "rkgame.h"
#include "debug.h"

#define KEYMAP_MAX_BINDINGS 32
#define KEYMAP_MAX_BINDINGS_PER_FILE 64

typedef struct {
    uint32_t from_key;   /* 源按键 bitmask */
    int      to_slot;    /* 目标槽位 (0-31) */
    bool     used;
} keymap_binding_t;

/* 当前活动的键位映射 */
static keymap_binding_t g_keymap[KEYMAP_MAX_BINDINGS_PER_FILE];
static int g_keymap_count = 0;
static char g_current_core[128] = {0};

/* 初始化：加载指定核心的键位映射文件 */
int InitKeyMapping0fEmuType(const char *core_name)
{
    if (!core_name || !core_name[0]) {
        g_keymap_count = 0;
        g_current_core[0] = '\0';
        return 0;
    }

    char path[600];
    snprintf(path, sizeof(path), "%skeymap_%s", work_path, core_name);

    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG("InitKeyMapping0fEmuType: %s not found, using global mapping", path);
        g_keymap_count = 0;
        strncpy(g_current_core, core_name, sizeof(g_current_core) - 1);
        return 0;
    }

    g_keymap_count = 0;
    char line[512];
    while (fgets(line, sizeof(line), fp)) {
        /* 解析 <bind from="KEY_X" to="N"/> */
        char from[64], to_str[32];
        if (sscanf(line, "from=\"%63[^\"]\" to=\"%31[^\"]",
                   from, to_str) == 2 ||
            sscanf(line, "to=\"%31[^\"]\" from=\"%63[^\"]",
                   to_str, from) == 2) {
            uint32_t from_key = 0;
            int to_slot = 0;

            /* 解析按键名 */
            if (strcmp(from, "KEY_A") == 0) from_key = (1u << 4);
            else if (strcmp(from, "KEY_B") == 0) from_key = (1u << 5);
            else if (strcmp(from, "KEY_X") == 0) from_key = (1u << 6);
            else if (strcmp(from, "KEY_Y") == 0) from_key = (1u << 7);
            else if (strcmp(from, "KEY_L1") == 0) from_key = (1u << 8);
            else if (strcmp(from, "KEY_R1") == 0) from_key = (1u << 9);
            else if (strcmp(from, "KEY_L2") == 0) from_key = (1u << 10);
            else if (strcmp(from, "KEY_R2") == 0) from_key = (1u << 11);
            else if (strcmp(from, "KEY_START") == 0) from_key = (1u << 12);
            else if (strcmp(from, "KEY_SELECT") == 0) from_key = (1u << 13);
            else if (strcmp(from, "KEY_UP") == 0) from_key = (1u << 0);
            else if (strcmp(from, "KEY_DOWN") == 0) from_key = (1u << 1);
            else if (strcmp(from, "KEY_LEFT") == 0) from_key = (1u << 2);
            else if (strcmp(from, "KEY_RIGHT") == 0) from_key = (1u << 3);

            to_slot = atoi(to_str);
            if (from_key && to_slot >= 0 && to_slot < 32 &&
                g_keymap_count < KEYMAP_MAX_BINDINGS_PER_FILE) {
                g_keymap[g_keymap_count].from_key = from_key;
                g_keymap[g_keymap_count].to_slot = to_slot;
                g_keymap[g_keymap_count].used = true;
                g_keymap_count++;
            }
        }
    }
    fclose(fp);

    strncpy(g_current_core, core_name, sizeof(g_current_core) - 1);
    LOG("InitKeyMapping0fEmuType: loaded %d bindings for %s from %s",
        g_keymap_count, core_name, path);
    return g_keymap_count;
}

/* 保存当前键位映射到文件 */
int SaveKeyMappingConfigFile(void)
{
    if (!g_current_core[0]) {
        ERR("SaveKeyMappingConfigFile: no core name set");
        return -1;
    }

    char path[600];
    snprintf(path, sizeof(path), "%skeymap_%s", work_path, g_current_core);

    FILE *fp = fopen(path, "w");
    if (!fp) {
        ERR("SaveKeyMappingConfigFile: cannot open %s for write", path);
        return -1;
    }

    fprintf(fp, "<keymap core=\"%s\">\n", g_current_core);
    for (int i = 0; i < g_keymap_count; i++) {
        const char *key_name = "KEY_UNKNOWN";
        uint32_t k = g_keymap[i].from_key;
        if (k == (1u << 0)) key_name = "KEY_UP";
        else if (k == (1u << 1)) key_name = "KEY_DOWN";
        else if (k == (1u << 2)) key_name = "KEY_LEFT";
        else if (k == (1u << 3)) key_name = "KEY_RIGHT";
        else if (k == (1u << 4)) key_name = "KEY_A";
        else if (k == (1u << 5)) key_name = "KEY_B";
        else if (k == (1u << 6)) key_name = "KEY_X";
        else if (k == (1u << 7)) key_name = "KEY_Y";
        else if (k == (1u << 8)) key_name = "KEY_L1";
        else if (k == (1u << 9)) key_name = "KEY_R1";
        else if (k == (1u << 10)) key_name = "KEY_L2";
        else if (k == (1u << 11)) key_name = "KEY_R2";
        else if (k == (1u << 12)) key_name = "KEY_START";
        else if (k == (1u << 13)) key_name = "KEY_SELECT";
        fprintf(fp, "  <bind from=\"%s\" to=\"%d\"/>\n", key_name, g_keymap[i].to_slot);
    }
    fprintf(fp, "</keymap>\n");
    fclose(fp);

    LOG("SaveKeyMappingConfigFile: saved %d bindings for %s to %s",
        g_keymap_count, g_current_core, path);
    return g_keymap_count;
}

/* 查询按键映射：返回按键对应的槽位（-1 = 未映射） */
int keymap_lookup(uint32_t key_mask)
{
    for (int i = 0; i < g_keymap_count; i++) {
        if (g_keymap[i].used && g_keymap[i].from_key == key_mask) {
            return g_keymap[i].to_slot;
        }
    }
    return -1;
}

/* 设置按键映射 */
int keymap_set(uint32_t from_key, int to_slot)
{
    /* 查找已有绑定 */
    for (int i = 0; i < g_keymap_count; i++) {
        if (g_keymap[i].used && g_keymap[i].from_key == from_key) {
            g_keymap[i].to_slot = to_slot;
            return 0;
        }
    }
    /* 新增绑定 */
    if (g_keymap_count < KEYMAP_MAX_BINDINGS_PER_FILE) {
        g_keymap[g_keymap_count].from_key = from_key;
        g_keymap[g_keymap_count].to_slot = to_slot;
        g_keymap[g_keymap_count].used = true;
        g_keymap_count++;
        return 0;
    }
    return -1;
}

/* 获取当前核心名 */
const char *keymap_current_core(void) { return g_current_core; }
int keymap_count(void) { return g_keymap_count; }
