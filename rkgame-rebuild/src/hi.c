/* ============================================================
 * hi.c — 全局高分榜实现
 * ============================================================ */

#include "hi.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

hi_entry_t hi[HI_MAX_ENTRIES];

int hi_add(const char *name, unsigned int score)
{
    const char *n = name ? name : "P1";
    /* 找插入位置（降序） */
    int idx = HI_MAX_ENTRIES - 1;
    for (int i = 0; i < HI_MAX_ENTRIES; i++) {
        if (score >= hi[i].score) { idx = i; break; }
    }
    if (idx >= HI_MAX_ENTRIES) return -1;
    /* 从尾部上移 */
    if (idx < HI_MAX_ENTRIES - 1) {
        for (int i = HI_MAX_ENTRIES - 1; i > idx; i--) {
            hi[i] = hi[i - 1];
        }
    }
    strncpy(hi[idx].name, n, sizeof(hi[idx].name) - 1);
    hi[idx].name[sizeof(hi[idx].name) - 1] = '\0';
    hi[idx].score = score;
    return idx;
}

void hi_clear(void)
{
    memset(hi, 0, sizeof(hi));
}

int hi_save(const char *path)
{
    if (!path) return -1;
    FILE *fp = fopen(path, "w");
    if (!fp) return -1;
    int n = 0;
    for (int i = 0; i < HI_MAX_ENTRIES; i++) {
        if (hi[i].score == 0 && hi[i].name[0] == '\0') continue;
        fprintf(fp, "%s\t%u\n", hi[i].name, hi[i].score);
        n++;
    }
    fclose(fp);
    return n;
}

int hi_load(const char *path)
{
    if (!path) return -1;
    FILE *fp = fopen(path, "r");
    if (!fp) return -1;
    hi_clear();
    int n = 0;
    char line[128];
    while (n < HI_MAX_ENTRIES && fgets(line, sizeof(line), fp)) {
        char name[64];
        unsigned int score = 0;
        if (sscanf(line, "%63s\t%u", name, &score) == 2) {
            strncpy(hi[n].name, name, sizeof(hi[n].name) - 1);
            hi[n].score = score;
            n++;
        }
    }
    fclose(fp);
    return n;
}
