/* ============================================================
 * rkgame-rebuild — core_table.c
 *
 * 复刻原厂 GetCoreIndex + default_core_list 表。
 *
 * ★ 数据源（实证）：
 *   - 原厂 rkgame v1.42 (3,921,108 B, ELF ARM 32-bit)
 *   - default_core_list @ vaddr 0x003b0254, .data 段, size=6800
 *   - 每项 68 字节: [32-byte ext name][4-byte filetype][32-byte core name]
 *   - 硬编码 33 项有效条目（从 ELF file offset 0x3a7254 提取）
 *
 * FileType 位含义（反推自 run_game @ 0x2b7510 分支）：
 *   0x2     = NES/FDS/NFC/UNF → Core_Load
 *   0x4     = SFC/SMC/FIG/GD3/GD7/DX2/BSX/SWC → Core_Load
 *   0x8     = MD/BIN/SMD/GEN/SMS → Core_Load
 *   0x10    = GBA/AGB/GBZ → Gpsp_Load 特例（不通过 Core_Load）
 *   0x20    = GB/GBC/SGB → Core_Load
 *   0x80    = PS1/ISO/IMG/PBP → 需要 fopen（不是 Core_Load）
 *   0x100   = A26 → Core_Load
 *   0x200   = A78 → Core_Load
 *   0x400   = VT3/VT4 → Core_Load
 *   0x800   = CONF (dosbox) → 走 game.cfg 路径
 *   0x10000 = BKP/ZIP → ZIP 容器标志（run_game 用 Filetype>0xffff 判断）
 *
 * 注：BKP/ZIP 的 core_name 为空字符串（原厂行为）。
 * ============================================================ */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include "core_table.h"

uint32_t Filetype = 0;

/*
 * 原厂 33 项硬编码表（顺序敏感，先匹配的先中）。
 * 严格照抄原厂二进制，filetype 位含义见文件头。
 *
 * 空 core_name 的项：
 *   - BKP/ZIP: filetype 0x10000 (ZIP 容器标志)，run_game 走 OpenZipU 路径
 *   - 其余项的 core_name 都是真实的 .so 库名
 */
static const core_entry_t core_table[] = {
    /* ZIP 容器标志 — run_game 会走 OpenZipU 路径 */
    { "BKP",  "",                   0x10000 },
    { "ZIP",  "",                   0x10000 },

    /* SFC / SNES (libemu_sfc.so) — filetype 0x4 */
    { "SMC",  "libemu_sfc.so",      0x4 },
    { "FIG",  "libemu_sfc.so",      0x4 },
    { "SFC",  "libemu_sfc.so",      0x4 },
    { "GD3",  "libemu_sfc.so",      0x4 },
    { "GD7",  "libemu_sfc.so",      0x4 },
    { "DX2",  "libemu_sfc.so",      0x4 },
    { "BSX",  "libemu_sfc.so",      0x4 },
    { "SWC",  "libemu_sfc.so",      0x4 },

    /* NES / FC (libemu_nes.so) — filetype 0x2 */
    { "NES",  "libemu_nes.so",      0x2 },
    { "NFC",  "libemu_nes.so",      0x2 },
    { "FDS",  "libemu_nes.so",      0x2 },
    { "UNF",  "libemu_nes.so",      0x2 },

    /* Virtual Boy (libemu_vrt.so) — filetype 0x400 */
    { "VT3",  "libemu_vrt.so",      0x400 },
    { "VT4",  "libemu_vrt.so",      0x400 },

    /* GBA (libemu_gpsp.so) — filetype 0x10，走 Gpsp_Load 特例 */
    { "GBA",  "libemu_gpsp.so",     0x10 },
    { "AGB",  "libemu_gpsp.so",     0x10 },
    { "GBZ",  "libemu_gpsp.so",     0x10 },

    /* GB / GBC / SGB (libemu_tgbdual.so) — filetype 0x20 */
    { "GBC",  "libemu_tgbdual.so",  0x20 },
    { "GB",   "libemu_tgbdual.so",  0x20 },
    { "SGB",  "libemu_tgbdual.so",  0x20 },

    /* MD / Sega (libemu_md.so) — filetype 0x8 */
    { "BIN",  "libemu_md.so",       0x8 },
    { "MD",   "libemu_md.so",       0x8 },
    { "SMD",  "libemu_md.so",       0x8 },
    { "GEN",  "libemu_md.so",       0x8 },
    { "SMS",  "libemu_md.so",       0x8 },

    /* PS1 (libemu_pcsx.so) — filetype 0x80 */
    { "ISO",  "libemu_pcsx.so",     0x80 },
    { "IMG",  "libemu_pcsx.so",     0x80 },
    { "PBP",  "libemu_pcsx.so",     0x80 },

    /* Atari 2600 (libemu_stella.so) — filetype 0x100 */
    { "A26",  "libemu_stella.so",   0x100 },

    /* Atari 7800 (libemu_prosystem.so) — filetype 0x200 */
    { "A78",  "libemu_prosystem.so",0x200 },

    /* DOS (libemu_dosbox.so) — filetype 0x800，走 game.cfg */
    { "CONF", "libemu_dosbox.so",   0x800 },

    /* 结束标记（NULL 终止） */
    { NULL,   NULL,                 0 },
};

const char *core_lookup_by_ext(const char *ext)
{
    if (!ext || !*ext) return NULL;

    /* 1. 硬编码表（原厂 DAT_003b0278） */
    for (int i = 0; core_table[i].ext; i++) {
        if (strcmp(core_table[i].ext, ext) == 0) {
            return core_table[i].core_name;
        }
    }

    /* 2. 动态 config.xml 表（SeletEmuCore @ 0x3c9aec） */
    if (g_cfg_xml_loaded) {
        for (int i = 0; i < g_cfg_xml_count; i++) {
            if (strcmp(g_cfg_xml[i].ext, ext) == 0) {
                return g_cfg_xml[i].core_name;
            }
        }
    }

    return NULL;
}

int GetCoreIndex(const char *ext)
{
    if (!ext || !*ext) return -1;
    for (int i = 0; core_table[i].ext; i++) {
        if (strcmp(core_table[i].ext, ext) == 0) {
            /* 原厂：Filetype = *(uint*)(&DAT_003b0274 + idx*0x44) | Filetype */
            Filetype |= core_table[i].filetype;
            return i;
        }
    }
    return -1;
}

/* ============================================================
 * cores/config.xml 加载（SeletEmuCore @ 0x3c9aec）
 * ============================================================
 *
 * 工厂实证：core_info_list @ 0x3c9aec (.bss, 40 × 512 bytes) 在
 * SeletEmuCore() 时从 cores/config.xml 动态填充，用于 UI 选 core。
 *
 * 格式（CubeGM open-source replacement）：
 *   <core>
 *     <emucore name="..." file="..." />
 *     <supported_extensions>EXT1</supported_extensions>
 *     <supported_extensions>EXT2</supported_extensions>
 *   </core>
 *
 * 用途：扩展名 → core .so 文件名映射（作为硬编码表的补充）。
 */

#define CFG_XML_MAX_CORES  40
#define CFG_XML_MAX_EXTS   16

typedef struct {
    char core_name[96];
    char exts[CFG_XML_MAX_EXTS][16];
    int  ext_count;
} cfg_xml_core_t;

static cfg_xml_core_t g_cfg_xml_cores[CFG_XML_MAX_CORES];
static int            g_cfg_xml_core_count = 0;

/* 扁平化的 ext → core_name 映射（供 core_lookup_by_ext 快速查找） */
typedef struct {
    char ext[16];
    char core_name[96];
} cfg_xml_entry_t;

static cfg_xml_entry_t g_cfg_xml[CFG_XML_MAX_CORES * CFG_XML_MAX_EXTS];
static int             g_cfg_xml_count = 0;
static bool            g_cfg_xml_loaded = false;

int load_cores_config_xml(const char *work_path)
{
    char path[512];
    snprintf(path, sizeof(path), "%s%scores/config.xml",
             work_path,
             (work_path[strlen(work_path) - 1] == '/') ? "" : "/");

    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG("load_cores_config_xml: %s not found (OK, using hardcoded table)",
            path);
        return 0;
    }

    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize <= 0 || fsize > 1024 * 1024) {
        fclose(fp);
        return 0;
    }

    char *buf = (char *)malloc((size_t)fsize + 1);
    if (!buf) { fclose(fp); return 0; }
    fread(buf, 1, (size_t)fsize, fp);
    buf[fsize] = '\0';
    fclose(fp);

    g_cfg_xml_core_count = 0;
    g_cfg_xml_count = 0;

    /* 遍历 <core>...</core> 块 */
    const char *p = buf;
    while ((p = strstr(p, "<core>")) != NULL &&
           g_cfg_xml_core_count < CFG_XML_MAX_CORES) {
        const char *block_end = strstr(p, "</core>");
        if (!block_end) break;

        cfg_xml_core_t *core = &g_cfg_xml_cores[g_cfg_xml_core_count];
        core->ext_count = 0;
        core->core_name[0] = '\0';

        /* 提取 <emucore file="..."> */
        const char *em_p = strstr(p, "<emucore");
        if (em_p && em_p < block_end) {
            const char *file_p = strstr(em_p, "file=");
            if (file_p && file_p < block_end) {
                file_p += 5;
                if (*file_p == '"') file_p++;
                const char *file_end = strchr(file_p, '"');
                if (file_end) {
                    size_t len = (size_t)(file_end - file_p);
                    if (len >= sizeof(core->core_name))
                        len = sizeof(core->core_name) - 1;
                    memcpy(core->core_name, file_p, len);
                    core->core_name[len] = '\0';
                }
            }
        }

        /* 提取所有 <supported_extensions>...</supported_extensions> */
        const char *ext_p = p + 6;  /* 跳过 "<core>" */
        while (ext_p < block_end) {
            ext_p = strstr(ext_p, "<supported_extensions>");
            if (!ext_p || ext_p >= block_end) break;
            ext_p += strlen("<supported_extensions>");
            const char *ext_end = strstr(ext_p, "</supported_extensions>");
            if (!ext_end || ext_end > block_end) break;

            if (core->ext_count < CFG_XML_MAX_EXTS) {
                size_t len = (size_t)(ext_end - ext_p);
                if (len >= sizeof(core->exts[0]))
                    len = sizeof(core->exts[0]) - 1;
                memcpy(core->exts[core->ext_count], ext_p, len);
                core->exts[core->ext_count][len] = '\0';
                core->ext_count++;
            }
            ext_p = ext_end + 21;  /* 跳过 "</supported_extensions>" */
        }

        /* 扁平化到 g_cfg_xml */
        if (core->core_name[0] && core->ext_count > 0) {
            for (int i = 0; i < core->ext_count &&
                         g_cfg_xml_count < (int)(sizeof(g_cfg_xml) / sizeof(g_cfg_xml[0]));
                 i++) {
                strncpy(g_cfg_xml[g_cfg_xml_count].ext,
                        core->exts[i], sizeof(g_cfg_xml[0].ext) - 1);
                strncpy(g_cfg_xml[g_cfg_xml_count].core_name,
                        core->core_name, sizeof(g_cfg_xml[0].core_name) - 1);
                g_cfg_xml_count++;
            }
        }

        g_cfg_xml_core_count++;
        p = block_end + 7;  /* 跳过 "</core>" */
    }

    free(buf);
    g_cfg_xml_loaded = (g_cfg_xml_count > 0);

    LOG("load_cores_config_xml: %d cores, %d ext→core entries from %s",
        g_cfg_xml_core_count, g_cfg_xml_count, path);
    return g_cfg_xml_count;
}

char *GetFilenameExt(const char *path, char *out, size_t out_size)
{
    if (!path || out_size == 0) return NULL;
    const char *dot = strrchr(path, '.');
    if (!dot || dot == path) {
        out[0] = '\0';
        return out;
    }
    size_t len = strlen(dot + 1);
    if (len >= out_size) len = out_size - 1;
    for (size_t i = 0; i < len; i++) {
        out[i] = (char)toupper((unsigned char)dot[1 + i]);
    }
    out[len] = '\0';
    return out;
}
