/* ============================================================
 * data_tables.h — 内嵌数据表（P2-3）
 * ============================================================
 *
 * 对齐原厂 rkgame v1.42 中的 6 大数据表：
 *   - configitems (50 KB)  — 配置项定义（key → type/default/desc）
 *   - file_info_list (41 KB)  — 文件信息表（扩展名/图标/分类）
 *   - file_info_list_ext (6.4 KB)  — file_info_list 扩展字段
 *   - items (16 KB)      — 菜单/设置项列表
 *   - aliases (7.4 KB)   — 别名映射
 *   - sbi (8.7 KB)       — SBI 数据（保存状态索引）
 *
 * 本模块将这些静态表作为编译期常量内置，并提供统一访问 API。
 * ============================================================ */

#ifndef DATA_TABLES_H
#define DATA_TABLES_H

#include <stdbool.h>

/* ---- configitems ---- */
typedef enum {
    CFG_TYPE_INT = 1,
    CFG_TYPE_STRING,
    CFG_TYPE_BOOL,
    CFG_TYPE_PATH,
    CFG_TYPE_ENUM
} cfg_type_t;

typedef struct {
    const char *key;
    cfg_type_t  type;
    const char *default_value;
    const char *description;
} config_item_def_t;

/* ---- file_info_list ---- */
typedef struct {
    const char *ext;         /* 文件扩展名 */
    const char *icon_raw;    /* 对应 icon.raw 条目名 */
    const char *category;    /* 分类名（"000","001"...） */
} file_info_def_t;

typedef struct {
    const char *ext;
    int         supported;   /* 1=支持 0=不支持 */
    int         default_core;  /* 默认 core 索引 */
} file_info_ext_def_t;

/* ---- items（UI 菜单项） ---- */
typedef struct {
    const char *label;       /* UI 显示文字 */
    const char *action;      /* 动作 ID */
} ui_item_def_t;

/* ---- aliases（文件扩展名别名） ---- */
typedef struct {
    const char *alias;
    const char *canonical;
} alias_def_t;

/* ---- sbi（保存状态索引） ---- */
typedef struct {
    int slot;
    const char *description;
} sbi_def_t;

/* ---- mi（原厂 6.9 KB 表：菜单项信息/快捷键映射） ---- */
typedef struct {
    const char *name;       /* 菜单项名 */
    int         shortcut;   /* 快捷键扫描码 (0-52) */
    int         enabled;    /* 1=启用 0=禁用 */
} mi_def_t;

/* 全局表（const） */
extern const config_item_def_t  configitems[];
extern const file_info_def_t    file_info_list[];
extern const file_info_ext_def_t file_info_list_ext[];
extern const ui_item_def_t      items[];
extern const alias_def_t        aliases[];
extern const sbi_def_t          sbi[];
extern const mi_def_t           mi[];

/* 表大小 */
#define CONFIGITEMS_COUNT    (sizeof(configitems) / sizeof(configitems[0]))
#define FILE_INFO_COUNT      (sizeof(file_info_list) / sizeof(file_info_list[0]))
#define FILE_INFO_EXT_COUNT  (sizeof(file_info_list_ext) / sizeof(file_info_list_ext[0]))
#define ITEMS_COUNT          (sizeof(items) / sizeof(items[0]))
#define ALIASES_COUNT        (sizeof(aliases) / sizeof(aliases[0]))
#define SBI_COUNT            (sizeof(sbi) / sizeof(sbi[0]))
#define MI_COUNT             (sizeof(mi) / sizeof(mi[0]))

/* 访问 API */
const config_item_def_t *configitems_find(const char *key);
const file_info_def_t   *file_info_find(const char *ext);
const file_info_ext_def_t *file_info_ext_find(const char *ext);
const alias_def_t       *alias_find(const char *alias);
const mi_def_t          *mi_find(const char *name);

/* 数据表版本检查 */
int data_tables_init(void);
void data_tables_report(void);

#endif /* DATA_TABLES_H */
