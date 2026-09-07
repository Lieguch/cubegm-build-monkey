/* ============================================================
 * thumbnail.h — 游戏缩略图提取（WQW .dat 容器）
 * ============================================================
 *
 * 工厂实证（Ghidra FUN_00014f84_mui_DisplayThumbnail @ 0x14f84）：
 *   缩略图在 <NNN>/<NNN>.dat (WQW 容器) 里，文件名 <base>_%03d.raw
 *   格式：RGB565，前 8 字节 header [4B offset][2B width][2B height]
 * ============================================================ */

#ifndef THUMBNAIL_H
#define THUMBNAIL_H

#include <stdbool.h>
#include <stddef.h>

/* 检查游戏是否有缩略图 */
bool thumb_has(const char *game_path);

/* 提取第一个缩略图 (index=0) */
int  thumb_extract(const char *game_path,
                   unsigned char **out_data, size_t *out_size,
                   int *out_w, int *out_h);

/* 提取第 n 个缩略图 */
int  thumb_extract_nth(const char *game_path, int index,
                       unsigned char **out_data, size_t *out_size,
                       int *out_w, int *out_h);

/* 获取游戏缩略图数量 */
int  thumb_count(const char *game_path);

/* 释放所有缩略图缓存 */
void thumb_cache_free(void);

#endif /* THUMBNAIL_H */
