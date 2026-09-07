/* ============================================================
 * rkgame-rebuild — core_table.h
 *
 * 复刻原厂 GetCoreIndex + default_core_list 表。
 *
 * 原厂实证（Ghidra 反编译 + ELF 符号表 + LOAD 段解析）：
 *   - default_core_list @ 0x003b0254, size=6800 (100 × 68 bytes, .data 段)
 *   - 每项 68 字节: [32-byte ext name][4-byte filetype][32-byte core name]
 *   - 硬编码 33 项有效条目（其余 67 项零初始化）
 *   - GetCoreIndex(ext) 逐项 strcmp 到 ext 字段（不是 name！），
 *     命中则 OR filetype 到全局 Filetype，返回 index
 *   - core 名通过 Core_Load(path, default_core_list[idx].corename) 加载
 *   - 另有 core_info_list @ 0x3c9aec (.bss, 40 × 512 bytes) 在
 *     SeletEmuCore() 时从 cores/config.xml 动态填充，用于 UI 选 core
 *
 * 本表严格照抄原厂 33 项，filetype 位含义反推自 run_game 分支：
 *   0x2    = NES  (Filetype 用于 Core_Load 分支)
 *   0x4    = SFC  (libemu_sfc.so)
 *   0x8    = MD   (libemu_md.so)
 *   0x10   = GBA  (libemu_gpsp.so, 也走 Gpsp_Load 特例)
 *   0x20   = GB   (libemu_tgbdual.so)
 *   0x40   = (未用)
 *   0x80   = PS1  (libemu_pcsx.so)
 *   0x100  = A26  (libemu_stella.so)
 *   0x200  = A78  (libemu_prosystem.so)
 *   0x400  = VB   (libemu_vrt.so)
 *   0x800  = DOS  (libemu_dosbox.so, 走 game.cfg)
 *   0x10000 = ZIP 容器标志 (run_game: if Filetype > 0xffff 走 OpenZipU)
 * ============================================================ */

#ifndef CORE_TABLE_H
#define CORE_TABLE_H

#include <stdbool.h>

/* 扩展名 → core 映射（与原厂 DAT_003b0278 表结构一致） */
typedef struct {
    const char *ext;       /* 大写扩展名，如 "N64"、"GBA" */
    const char *core_name; /* core .so 文件名（不含 .so）；可为 NULL */
    uint32_t    filetype;  /* 原厂 DAT_003b0274[i*0x44] 的 filetype 位 */
} core_entry_t;

/* 全局 FileType 位（原厂 GetCoreIndex 会 OR 到这个全局） */
extern uint32_t Filetype;

/* 按扩展名查表。返回 core_name 指针（未找到 NULL） */
const char *core_lookup_by_ext(const char *ext);

/* 原厂风格：返回 core 索引（0-based），未找到返回 -1，并 OR Filetype 到全局 */
int GetCoreIndex(const char *ext);

/* 从文件名提取大写扩展名（不含点），如 "game.n64" → "N64" */
char *GetFilenameExt(const char *path, char *out, size_t out_size);

/* 加载 cores/config.xml（SeletEmuCore @ 0x3c9aec），动态扩展 ext→core 映射。
 * work_path 为工作目录（如 "/sdcard/cubegm/"）。
 * 返回加载的 ext→core 条目数；0 = 未找到或解析失败（使用硬编码表）。 */
int load_cores_config_xml(const char *work_path);

#endif /* CORE_TABLE_H */
