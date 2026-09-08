/* ============================================================
 * stringpool.h — 字符串池（对齐原厂 stringpool_contents 3.6 KB）
 * ============================================================
 *
 * 原厂 rkgame 中所有 UI 文字以 (hash, ptr) 形式存放在静态字符串池。
 * 本实现提供同语义 API：
 *   - 单例数组（4096 项），支持按 key 查找、追加、导出
 *   - 供 mui_* 各 UI 模块调用 stringpool_get/put
 * ============================================================ */

#ifndef STRINGPOOL_H
#define STRINGPOOL_H

#include <stddef.h>

#define STRINGPOOL_MAX 4096
#define STRINGPOOL_STR_LEN 128

typedef struct {
    const char *key;    /* 标签（如 "menu.title"），可为 NULL */
    char        value[STRINGPOOL_STR_LEN];
} stringpool_entry_t;

/* 初始化（幂等） */
void stringpool_init(void);

/* 按 key 追加（若已存在则更新） */
void stringpool_put(const char *key, const char *value);

/* 按 key 查找 */
const char *stringpool_get(const char *key);

/* 按索引读取（用于遍历 UI 显示） */
const stringpool_entry_t *stringpool_at(unsigned int idx);
unsigned int stringpool_count(void);

/* 清空 */
void stringpool_clear(void);

/* 别名（原厂 stringpool_contents 是数据表符号） */
extern stringpool_entry_t stringpool_contents[STRINGPOOL_MAX];

#endif /* STRINGPOOL_H */
