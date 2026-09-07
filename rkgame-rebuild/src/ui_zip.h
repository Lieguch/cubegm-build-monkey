/* ============================================================
 * ui_zip.h — 精简 ZIP 读取器（P1.3 基础组件）
 * ============================================================
 *
 * 工厂实证（Ghidra mui_menu_ui.c）：
 *   OpenZipU(path, 0, 2)       — 打开 zip
 *   FindZipItemA(handle, name, 1, &item, ze) — 查找条目
 *   UnzipItem(handle, item, buf, 0, 3) — 解压到内存
 *
 * 本实现：
 *   - 支持 stored (method=0) 和 deflate (method=8) 两种压缩
 *   - 使用 libz inflateInit2(-15) 做 raw deflate 解压
 *   - 工厂 rkgame NEEDED=libz.so.1，已链接
 *   - 返回 malloc'd 缓冲区，调用方负责 free
 * ============================================================ */

#ifndef UI_ZIP_H
#define UI_ZIP_H

#include <stddef.h>
#include <stdint.h>

typedef struct ui_zip ui_zip_t;

/* 打开 zip 文件。成功返回 0，失败返回 -1。 */
int  ui_zip_open(const char *path, ui_zip_t **out);

/* 查找条目。成功返回 0 并填充 out_size（未压缩大小），失败返回 -1。 */
int  ui_zip_find(const ui_zip_t *z, const char *name, size_t *out_size);

/* 解压条目到 malloc'd 缓冲区。成功返回 0，失败返回 -1。
 * out_data 由调用方负责 free。 */
int  ui_zip_extract(const ui_zip_t *z, const char *name,
                    void **out_data, size_t *out_size);

/* 关闭并释放资源 */
void ui_zip_close(ui_zip_t *z);

/* 列出 zip 内所有文件名（用于调试）。返回条目数。 */
int  ui_zip_list(const ui_zip_t *z, char names[][256], int max_entries);

#endif /* UI_ZIP_H */
