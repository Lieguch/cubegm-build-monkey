/* ============================================================
 * hi.h — 全局高分榜（对齐原厂 hi 符号）
 * ============================================================ */

#ifndef HI_H
#define HI_H

#define HI_MAX_ENTRIES 20

typedef struct {
    char name[16];       /* 玩家名 */
    unsigned int score;  /* 分数 */
} hi_entry_t;

extern hi_entry_t hi[HI_MAX_ENTRIES];

/* 记录一局分数，返回插入位置（0..HI_MAX_ENTRIES-1），-1 表示未上榜 */
int hi_add(const char *name, unsigned int score);

/* 清空榜单 */
void hi_clear(void);

/* 保存/加载 hi.scores 文件（简单文本格式） */
int hi_save(const char *path);
int hi_load(const char *path);

#endif /* HI_H */
