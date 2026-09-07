/* ============================================================
 * game_list.h — 游戏列表加载与管理（P2.2）
 * ============================================================
 *
 * 工厂实证（Ghidra 反编译）：
 *   mui_menu @ 0x23204: OpenZipU(root.dat) → FindZipItemA("fileinfo.txt")
 *     → UnzipItem → mui_do_file_list(CSV 解析, GB2312→UTF8)
 *   GetFileCore @ 0x22334: 读 cores/filelist.xml 按 <file name= core=> 查核心
 *   mui_run_game @ 0x229f8: fopen(root_path + "/" + path) → Core_Load
 *
 * CSV 格式（分号分隔，5 字段）：
 *   path;name_en1;name_en2;name_zh1;name_zh2
 *   例：000/sengoku3.zip;Sengoku3/...;SENGOKU3/...;战国3/...;ZG3/...
 *
 * filelist.xml 格式（135 条）：
 *   <file name="000/kof96.zip" core="libemu_fbalpha2012.so" />
 *
 * 本实现加载优先级：
 *   1. root.dat → fileinfo.txt（标准 ZIP，若 root.dat 为标准 ZIP 格式）
 *   2. work_path/fileinfo（独立 CSV 文件，若存在）
 *   3. work_path/recent.lst（最近游戏 CSV）
 *   4. 目录扫描 000-008/（回退方案）
 *
 * 核心映射来源：cores/filelist.xml（XML 解析）
 * ============================================================ */

#ifndef GAME_LIST_H
#define GAME_LIST_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#define GL_MAX_GAMES    2048
#define GL_MAX_FAVORITES 256
#define GL_PATH_LEN     512
#define GL_NAME_LEN     256

/* 单个游戏条目 */
typedef struct {
    char     path[GL_PATH_LEN];       /* "000/sengoku3.zip" */
    char     name_en[GL_NAME_LEN];    /* 英文显示名（拼接 en1/en2） */
    char     name_zh[GL_NAME_LEN];    /* 中文显示名（拼接 zh1/zh2） */
    char     core[128];               /* 核心名（从 filelist.xml 查得） */
    char     dir[16];                 /* 目录编号 "000"-"008" */
    bool     is_favorite;             /* 是否在收藏中 */
    bool     has_thumbnail;           /* <NNN>.dat 中是否有缩略图 */
} game_entry_t;

/* 游戏列表 */
typedef struct {
    game_entry_t  *entries;
    int            count;
    int            capacity;
    int            selected;          /* 当前选中索引 */
    int            offset;            /* 滚动偏移 */
    bool           loaded;
} game_list_t;

/* 初始化游戏列表。返回 0 成功，-1 失败。 */
int  game_list_init(void);

/* 加载游戏列表（从所有可用来源）。 */
int  game_list_load(void);

/* 释放资源。 */
void game_list_free(void);

/* 获取条目。返回 NULL 表示越界。 */
const game_entry_t *game_list_get(int index);

/* 按扩展名查找核心名（从 cores/filelist.xml 查）。
 * 返回静态字符串指针，可能为 NULL。 */
const char *game_list_find_core(const char *rom_path);

/* 从扩展名查核心（使用 core_table 回退）。 */
const char *game_list_core_by_ext(const char *ext);

/* 添加收藏。 */
int  game_list_add_favorite(const char *rom_path);

/* 移除收藏。 */
int  game_list_remove_favorite(const char *rom_path);

/* 是否为收藏。 */
bool game_list_is_favorite(const char *rom_path);

/* 更新最近列表。 */
int  game_list_update_recent(const char *rom_path);

/* 保存到文件。 */
int  game_list_save_recent(void);
int  game_list_save_favorites(void);

/* 获取游戏总数。 */
int  game_list_count(void);

/* 游戏列表是否已加载。 */
bool game_list_is_loaded(void);

/* 按 CSV 解析加载（GB2312→UTF8 转换）。返回条目数。 */
int  game_list_parse_csv(const char *csv_data, size_t csv_size,
                         game_entry_t *out, int max_entries);

#endif /* GAME_LIST_H */
