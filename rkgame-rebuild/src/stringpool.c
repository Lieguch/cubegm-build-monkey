/* ============================================================
 * stringpool.c — 字符串池实现
 * ============================================================ */

#include "stringpool.h"
#include <string.h>

stringpool_entry_t stringpool_contents[STRINGPOOL_MAX];
static unsigned int g_pool_count = 0;
static int          g_pool_init = 0;

void stringpool_init(void)
{
    if (g_pool_init) return;
    g_pool_count = 0;
    g_pool_init  = 1;
}

void stringpool_clear(void)
{
    memset(stringpool_contents, 0, sizeof(stringpool_contents));
    g_pool_count = 0;
}

void stringpool_put(const char *key, const char *value)
{
    stringpool_init();
    if (!key || !value) return;

    /* 找已存在 */
    for (unsigned int i = 0; i < g_pool_count; i++) {
        if (stringpool_contents[i].key && strcmp(stringpool_contents[i].key, key) == 0) {
            strncpy(stringpool_contents[i].value, value,
                    STRINGPOOL_STR_LEN - 1);
            stringpool_contents[i].value[STRINGPOOL_STR_LEN - 1] = '\0';
            return;
        }
    }

    if (g_pool_count < STRINGPOOL_MAX) {
        stringpool_entry_t *e = &stringpool_contents[g_pool_count];
        memset(e, 0, sizeof(*e));
        e->key = key;
        strncpy(e->value, value, STRINGPOOL_STR_LEN - 1);
        g_pool_count++;
    }
}

const char *stringpool_get(const char *key)
{
    if (!key) return NULL;
    for (unsigned int i = 0; i < g_pool_count; i++) {
        if (stringpool_contents[i].key &&
            strcmp(stringpool_contents[i].key, key) == 0)
            return stringpool_contents[i].value;
    }
    return NULL;
}

const stringpool_entry_t *stringpool_at(unsigned int idx)
{
    if (idx >= g_pool_count) return NULL;
    return &stringpool_contents[idx];
}

unsigned int stringpool_count(void) { return g_pool_count; }
