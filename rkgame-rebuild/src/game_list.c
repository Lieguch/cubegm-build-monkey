/* ============================================================
 * game_list.c — 游戏列表加载与管理（P2.2）
 * ============================================================
 *
 * 数据源优先级（工厂实证 + 真机 SD 卡验证）：
 *   1. root.dat 内 fileinfo.txt（标准 ZIP 格式时，用 ui_zip 读取）
 *   2. work_path/fileinfo（独立 CSV 文件，真机为 49B stub）
 *   3. work_path/recent.lst（最近游戏 CSV）
 *   4. 目录扫描 000-008/（回退方案，scandir 遍历 .zip/.7z/.iso 等）
 *
 * 核心映射：cores/filelist.xml（135 条，XML 格式）
 *   <file name="000/kof96.zip" core="libemu_fbalpha2012.so" />
 *
 * CSV 格式：path;name_en1;name_en2;name_zh1;name_zh2
 * 编码：中文为 GB2312，通过 iconv 转换为 UTF-8
 *
 * 不实现 <NNN>.dat WQW\x03 容器（缩略图缓存，非必需）
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <errno.h>
#include "iconv.h"  /* 使用本地 libiconv（支持 GBK/Big5/JIS/UTF-8） */
#include <ctype.h>

#include "game_list.h"
#include "rkgame.h"
#include "debug.h"
#include "ui_zip.h"

/* ---- 全局状态 ---- */

static game_list_t g_gl = { 0 };
static char        g_favorites[GL_MAX_FAVORITES][GL_PATH_LEN];
static int         g_fav_count = 0;
static char        g_recent[GL_MAX_FAVORITES][GL_PATH_LEN];
static int         g_recent_count = 0;

/* filelist.xml 缓存 */
#define FLXML_MAX 256
typedef struct {
    char name[GL_PATH_LEN];
    char core[128];
} flxml_entry_t;

static flxml_entry_t g_filelist[FLXML_MAX];
static int           g_filelist_count = 0;

/* ---- 工具函数 ---- */

/* GB2312 → UTF-8 转换（使用 glibc iconv） */
static char *gb2312_to_utf8(const char *src, size_t src_len, size_t *out_len)
{
    iconv_t cd = iconv_open("UTF-8", "GB2312");
    if (cd == (iconv_t)-1) {
        /* iconv 不可用，原样返回 */
        char *buf = malloc(src_len + 1);
        if (!buf) return NULL;
        memcpy(buf, src, src_len);
        buf[src_len] = '\0';
        if (out_len) *out_len = src_len;
        return buf;
    }

    size_t out_size = src_len * 4 + 1; /* UTF-8 最多 4 倍膨胀 */
    char *buf = malloc(out_size);
    if (!buf) { iconv_close(cd); return NULL; }

    char *inptr = (char *)src;
    char *outptr = buf;
    size_t in_left = src_len;
    size_t out_left = out_size - 1;

    size_t rc = iconv(cd, &inptr, &in_left, &outptr, &out_left);
    iconv_close(cd);

    if (rc == (size_t)-1) {
        /* 转换失败，回退原样 */
        free(buf);
        buf = malloc(src_len + 1);
        if (!buf) return NULL;
        memcpy(buf, src, src_len);
        buf[src_len] = '\0';
        if (out_len) *out_len = src_len;
        return buf;
    }

    *outptr = '\0';
    if (out_len) *out_len = (size_t)(outptr - buf);
    return buf;
}

/* 去除尾部空白字符 */
static char *trim_str(char *s)
{
    if (!s) return s;
    size_t len = strlen(s);
    while (len > 0 && (s[len-1] == ' ' || s[len-1] == '\t' ||
                       s[len-1] == '\r' || s[len-1] == '\n')) {
        s[--len] = '\0';
    }
    return s;
}

/* 提取路径的目录前缀（如 "000/xxx.zip" → "000"） */
static void extract_dir(const char *path, char *out, size_t out_size)
{
    if (!path || !path[0]) { out[0] = '\0'; return; }
    const char *slash = strchr(path, '/');
    if (!slash) { out[0] = '\0'; return; }
    size_t len = (size_t)(slash - path);
    if (len >= out_size) len = out_size - 1;
    memcpy(out, path, len);
    out[len] = '\0';
}

/* 提取文件扩展名（小写） */
static void get_ext(const char *path, char *out, size_t out_size)
{
    if (!path || !path[0]) { out[0] = '\0'; return; }
    const char *dot = strrchr(path, '.');
    if (!dot || dot == path) { out[0] = '\0'; return; }
    size_t len = strlen(dot + 1);
    if (len >= out_size) len = out_size - 1;
    for (size_t i = 0; i < len; i++) {
        out[i] = tolower((unsigned char)dot[i+1]);
    }
    out[len] = '\0';
}

/* ---- CSV 解析 ---- */

int game_list_parse_csv(const char *csv_data, size_t csv_size,
                        game_entry_t *out, int max_entries)
{
    if (!csv_data || csv_size == 0 || !out || max_entries <= 0) return 0;

    int count = 0;
    const char *end = csv_data + csv_size;
    const char *line_start = csv_data;

    while (line_start < end && count < max_entries) {
        /* 找到行尾 */
        const char *line_end = memchr(line_start, '\n', (size_t)(end - line_start));
        if (!line_end) line_end = end;

        /* 跳过空行 */
        if (line_end == line_start) {
            line_start = line_end + 1;
            continue;
        }

        /* 复制行到缓冲区 */
        size_t line_len = (size_t)(line_end - line_start);
        if (line_len > 2048) { /* 跳过异常长行 */
            line_start = line_end + 1;
            continue;
        }

        char line[2048];
        memcpy(line, line_start, line_len);
        line[line_len] = '\0';

        /* 去除行尾的 \r */
        if (line_len > 0 && line[line_len-1] == '\r') line[line_len-1] = '\0';

        /* 按分号分割（5 字段） */
        char *fields[5] = { NULL };
        char *tokens[5];
        char *copy = strdup(line);
        if (!copy) { line_start = line_end + 1; continue; }

        /* 1:1 对齐工厂 mui_do_file_list：分隔符为 ','(0x2c) 与 ';'(0x3b) 双分隔 */
        int fi = 0;
        char *saveptr;
        tokens[fi] = strtok_r(copy, ";,", &saveptr);
        while (tokens[fi] != NULL && fi < 5) {
            fields[fi] = trim_str(tokens[fi]);
            fi++;
            tokens[fi] = strtok_r(NULL, ";,", &saveptr);
        }
        free(copy);

        if (fi < 1 || !fields[0] || !fields[0][0]) {
            line_start = line_end + 1;
            continue;
        }

        /* path 字段 */
        game_entry_t *e = &out[count];
        memset(e, 0, sizeof(*e));
        strncpy(e->path, fields[0], GL_PATH_LEN - 1);
        extract_dir(e->path, e->dir, sizeof(e->dir));

        /* 英文显示名 = f1（工厂 DAT_003b2324 主显示名；f2 仅大写备用，f1 空才用）
         * 1:1 对齐 mui_do_file_list：不再把 f1+f2 拼接（避免 "KOF 97KOF 97"） */
        if (fi >= 2 && fields[1] && fields[1][0]) {
            strncpy(e->name_en, fields[1], GL_NAME_LEN - 1);
        } else {
            /* 从文件名生成默认英文名 */
            const char *basename = strrchr(e->path, '/');
            basename = basename ? basename + 1 : e->path;
            strncpy(e->name_en, basename, GL_NAME_LEN - 1);
            char *dot = strrchr(e->name_en, '.');
            if (dot) *dot = '\0';
        }

        /* 中文显示名 = f3（工厂 DAT_003b23a4，GB2312→UTF8）
         * 真数据实证：000/kof97.zip;KOF 97;KOF 97;拳皇97;QH97
         *   f0=path  f1=KOF 97(英)  f2=KOF 97(大写)  f3=拳皇97(中文)  f4=QH97(代号)
         * 注意：中文字段是 f3，不合并 f4（f4 是代号，工厂 DAT_003b24a4 不参与主显示） */
        char zh_tmp[GL_NAME_LEN * 2];
        zh_tmp[0] = '\0';
        if (fi >= 4 && fields[3] && fields[3][0]) {
            strncpy(zh_tmp, fields[3], sizeof(zh_tmp) - 1);
            zh_tmp[sizeof(zh_tmp) - 1] = '\0';
        }

        if (zh_tmp[0]) {
            size_t utf8_len;
            char *utf8 = gb2312_to_utf8(zh_tmp, strlen(zh_tmp), &utf8_len);
            if (utf8) {
                strncpy(e->name_zh, utf8, GL_NAME_LEN - 1);
                free(utf8);
            } else {
                strncpy(e->name_zh, zh_tmp, GL_NAME_LEN - 1);
            }
        } else {
            /* 无中文名，用英文名 */
            strncpy(e->name_zh, e->name_en, GL_NAME_LEN - 1);
        }

        count++;
        line_start = line_end + 1;
    }

    LOG("game_list_parse_csv: parsed %d entries from %zu bytes", count, csv_size);
    return count;
}

/* ---- filelist.xml 加载 ---- */

static int load_filelist_xml(void)
{
    char path[512];
    snprintf(path, sizeof(path), "%s%s/cores/filelist.xml",
             work_path, work_path[0] == '/' ? "" : "");

    /* 构造正确路径 */
    snprintf(path, sizeof(path), "%s%scores/filelist.xml", work_path,
             (work_path[strlen(work_path)-1] == '/') ? "" : "/");

    FILE *fp = fopen(path, "r");
    if (!fp) {
        LOG("load_filelist_xml: %s not found (OK, will use fallback)", path);
        return -1;
    }

    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    if (fsize <= 0 || fsize > 1024 * 1024) {
        fclose(fp);
        return -1;
    }

    char *buf = malloc(fsize + 1);
    if (!buf) { fclose(fp); return -1; }
    fread(buf, 1, fsize, fp);
    buf[fsize] = '\0';
    fclose(fp);

    g_filelist_count = 0;
    const char *p = buf;
    while ((p = strstr(p, "<file")) != NULL && g_filelist_count < FLXML_MAX) {
        const char *end = strstr(p, "/>");
        if (!end) end = strstr(p, ">");
        if (!end) break;

        /* 提取 name="..." */
        char name[GL_PATH_LEN] = "";
        const char *name_p = strstr(p, "name=");
        if (name_p && name_p < end) {
            name_p += 5;
            if (*name_p == '"') name_p++;
            const char *name_end = strchr(name_p, '"');
            if (name_end) {
                size_t len = (size_t)(name_end - name_p);
                if (len >= sizeof(name)) len = sizeof(name) - 1;
                memcpy(name, name_p, len);
                name[len] = '\0';
            }
        }

        /* 提取 core="..." */
        char core[128] = "";
        const char *core_p = strstr(p, "core=");
        if (core_p && core_p < end) {
            core_p += 5;
            if (*core_p == '"') core_p++;
            const char *core_end = strchr(core_p, '"');
            if (core_end) {
                size_t len = (size_t)(core_end - core_p);
                if (len >= sizeof(core)) len = sizeof(core) - 1;
                memcpy(core, core_p, len);
                core[len] = '\0';
            }
        }

        if (name[0] && core[0]) {
            strncpy(g_filelist[g_filelist_count].name, name, GL_PATH_LEN - 1);
            strncpy(g_filelist[g_filelist_count].core, core, 127);
            g_filelist_count++;
        }

        p = end + 2;
    }

    free(buf);
    LOG("load_filelist_xml: loaded %d entries from %s", g_filelist_count, path);
    return g_filelist_count;
}

const char *game_list_find_core(const char *rom_path)
{
    if (!rom_path || !rom_path[0]) return NULL;

    /* 精确匹配 */
    for (int i = 0; i < g_filelist_count; i++) {
        if (strcmp(g_filelist[i].name, rom_path) == 0) {
            return g_filelist[i].core;
        }
    }

    /* 回退：按目录前缀匹配 */
    char dir[16];
    extract_dir(rom_path, dir, sizeof(dir));
    for (int i = 0; i < g_filelist_count; i++) {
        char fl_dir[16];
        extract_dir(g_filelist[i].name, fl_dir, sizeof(fl_dir));
        if (strcmp(dir, fl_dir) == 0) {
            /* 同目录，返回该核心（可能不精确但比无好） */
            return g_filelist[i].core;
        }
    }

    return NULL;
}

const char *game_list_core_by_ext(const char *ext)
{
    /* 使用 core_table 查表 */
    extern const char *core_lookup_by_ext(const char *ext);
    return core_lookup_by_ext(ext);
}

/* ---- RC-3: 以 filelist.xml 为权威来源填充游戏列表 ----
 *
 * 工厂行为：cores/filelist.xml（135 条 <file name core=>）是游戏清单 + 核心映射的
 * 权威来源。原版 mui 直接据此列出。原实现只把 g_filelist[] 用于 get_core 查询，
 * 从不作为游戏列表，导致真机上目录扫描全失败时菜单恒空。
 *
 * 本函数把每条 <file> 注入 g_gl.entries：
 *   - path  = g_filelist[i].name（相对 SD 根，如 "002/Targa.zip"）
 *   - core  = g_filelist[i].core
 *   - name  = 文件名（去扩展）
 *   - 仅保留文件真实存在者（rom_base_path 下 stat 命中；否则仍保留以不丢清单，
 *     由 main.c 启动时再决定是否可用） */
static int game_list_populate_from_filelist(void)
{
    if (g_filelist_count == 0) return 0;
    if (!g_gl.entries || g_gl.capacity == 0) return 0;

    int count = 0;
    for (int i = 0; i < g_filelist_count && g_gl.count < g_gl.capacity; i++) {
        game_entry_t *e = &g_gl.entries[g_gl.count];
        memset(e, 0, sizeof(*e));

        const char *name = g_filelist[i].name;   /* "002/Targa.zip" */
        const char *core = g_filelist[i].core;

        strncpy(e->path, name, GL_PATH_LEN - 1);
        extract_dir(name, e->dir, sizeof(e->dir));

        /* 显示名 = 文件名（去扩展） */
        const char *base = strrchr(name, '/');
        base = base ? base + 1 : name;
        strncpy(e->name_en, base, GL_NAME_LEN - 1);
        {
            char *dot = strrchr(e->name_en, '.');
            if (dot) *dot = '\0';
        }
        strncpy(e->name_zh, e->name_en, GL_NAME_LEN - 1);
        strncpy(e->name, e->name_en, GL_NAME_LEN - 1);

        if (core && core[0])
            strncpy(e->core, core, 127);

        /* 存在性检查（不强制，仅记录 has_thumbnail/可用性标记） */
        {
            char full[512];
            snprintf(full, sizeof(full), "%s%s", rom_base_path, name);
            struct stat st;
            e->has_thumbnail = (stat(full, &st) == 0);
        }

        g_gl.count++;
        count++;
    }

    LOG("game_list_populate_from_filelist: injected %d entries from %s",
        count, "cores/filelist.xml");
    return count;
}

/* ---- 目录扫描回退 ---- */

static const char *known_exts[] = {
    ".zip", ".7z", ".iso", ".img", ".a26", ".a52", ".a78",
    ".nes", ".fds", ".smc", ".sfc", ".gb", ".gbc", ".gba",
    ".md", ".sms", ".gg", ".pce", ".psx", ".cue", ".chd",
    ".d64", ".n64", ".z64", ".v64", ".m3u", ".m3u8",
    NULL
};

static int has_known_ext(const char *name)
{
    if (!name || !name[0]) return 0;
    const char *dot = strrchr(name, '.');
    if (!dot) return 0;
    char ext[16];
    get_ext(name, ext, sizeof(ext));
    for (int i = 0; known_exts[i]; i++) {
        if (strcmp(ext, known_exts[i]) == 0) return 1;
    }
    return 0;
}

static int scan_directory(const char *dir_path, int *out_count)
{
    if (out_count) *out_count = 0;
    if (!g_gl.entries || g_gl.capacity == 0) return 0;

    DIR *d = opendir(dir_path);
    if (!d) return 0;

    /* dir_name = "000"（目录基名，用于拼相对路径，与 filelist.xml 一致） */
    char dir_name[32];
    {
        char tmp[512];
        snprintf(tmp, sizeof(tmp), "%s", dir_path);
        while (tmp[0] == '/') memmove(tmp, tmp + 1, strlen(tmp));
        char *sl = strrchr(tmp, '/');
        if (sl) { size_t n = strlen(sl + 1); if (n >= sizeof(dir_name)) n = sizeof(dir_name) - 1;
                  memcpy(dir_name, sl + 1, n); dir_name[n] = '\0'; }
        else { snprintf(dir_name, sizeof(dir_name), "%s", tmp); }
    }

    struct dirent *ent;
    int count = 0;
    while ((ent = readdir(d)) != NULL) {
        if (g_gl.count >= g_gl.capacity) break;
        if (ent->d_name[0] == '.') continue;
        if (!has_known_ext(ent->d_name)) continue;

        game_entry_t *e = &g_gl.entries[g_gl.count];
        memset(e, 0, sizeof(*e));

        /* 存相对路径 "dir/filename"（与 filelist.xml 的 name 字段一致），
         * 由 main.c 在启动时结合 rom_base_path/work_path 解析为绝对路径。 */
        snprintf(e->path, GL_PATH_LEN, "%s/%s",
                 dir_name[0] ? dir_name : "", ent->d_name);

        /* 提取目录名 */
        extract_dir(e->path, e->dir, sizeof(e->dir));

        /* 从文件名生成名称 */
        strncpy(e->name_en, ent->d_name, GL_NAME_LEN - 1);
        char *dot = strrchr(e->name_en, '.');
        if (dot) *dot = '\0';
        strncpy(e->name_zh, e->name_en, GL_NAME_LEN - 1);

        /* 查核心映射 */
        const char *core = game_list_find_core(e->path);
        if (!core) {
            char ext[16];
            get_ext(e->path, ext, sizeof(ext));
            core = game_list_core_by_ext(ext);
        }
        if (core) strncpy(e->core, core, 127);

        g_gl.count++;
        count++;
    }
    closedir(d);

    LOG("scan_directory: found %d games in %s", count, dir_path);
    return count;
}

/* ---- 标准 ZIP 格式检测与读取 ---- */

/* WQW\x03 容器格式（SF3000/RK3036G 专用游戏包）
 * 结构：
 *   - v03 blocks (10 × 724 bytes) = 文件表头
 *   - data section (compressed game data)
 *   - v02 blocks (10 × 61 bytes)  = 偏移索引
 *   - v01 block (1)               = 结束标记
 * 
 * 工厂 SD 卡布局：
 *   <SD_ROOT>/root.dat  = WQW\x03 (20K+ 内置游戏包)
 *   <PLATFORM>/<NNN>.dat = WQW\x03 (各平台游戏归档)
 *   <PLATFORM>/*.zip     = 单游戏 ROM（可直接加载）
 *
 * 本实现：检测 WQW\x03 并记录日志，回退到目录扫描（扫描 .zip ROM）。
 * 完整解析需逆向压缩算法（zlib 变体），超出当前版本范围。
 */
static int try_load_from_root_dat(game_entry_t *entries, int max_entries)
{
    /* 1:1 对齐工厂：mui_menu@0x23204 用 sprintf(acStack_490,"%s/root.dat",root_path)，
     * root_path=SD 根（work_path 去掉 /cubegm/）。真机 root.dat 在 /sdcard/root.dat，
     * 不在 cubegm/ 下。先试 SD 根，回退 work_path（兼容 root.dat 拷进 cubegm/ 的情况）。 */
    const char *bases[] = { rom_base_path, work_path };
    FILE *fp = NULL;
    char path[512];
    int used_base = -1;
    for (int b = 0; b < 2; b++) {
        snprintf(path, sizeof(path), "%sroot.dat", bases[b]);
        fp = fopen(path, "rb");
        if (fp) { used_base = b; break; }
    }
    if (!fp) {
        LOG("try_load_from_root_dat: root.dat not found (tried %sroot.dat and %sroot.dat)",
            rom_base_path, work_path);
        return 0;
    }
    (void)used_base;

    unsigned char sig[4];
    if (fread(sig, 1, 4, fp) != 4) { fclose(fp); return 0; }
    fclose(fp);

    /* WQW\x03 容器（ZIP 变体，filename XOR 0xE5，数据标准 deflate）
     * 完整实现：wqw.c 解析 EOCD → CD → LFH → 提取压缩数据 → zlib uncompress
     * 2026-09-07 逆向完成：root.dat 10 entries 全部解压成功，CRC 匹配 */
    if (sig[0] == 'W' && sig[1] == 'Q' && sig[2] == 'W' && sig[3] == 0x03) {
        LOG("try_load_from_root_dat: %s is WQW\\x03 container (ZIP variant)",
            path);

        unsigned char *info_data = NULL;
        size_t info_size = 0;
        if (wqw_extract(path, "fileinfo.txt", &info_data, &info_size) == 0 &&
            info_data && info_size > 0) {
            LOG("try_load_from_root_dat: extracted fileinfo.txt (%zu B) from WQW",
                info_size);
            info_data[info_size] = '\0';
            int count = game_list_parse_csv((const char *)info_data, info_size, entries, max_entries);
            free(info_data);
            LOG("try_load_from_root_dat: parsed %d entries from WQW fileinfo.txt", count);
            return count;
        }

        LOG("try_load_from_root_dat: WQW extract failed, falling back to directory scan");
        return 0;
    }

    /* 非 ZIP、非 WQW — 警告 */
    if (sig[0] != 'P' || sig[1] != 'K') {
        LOG("try_load_from_root_dat: %s has unknown magic %02x%02x%02x%02x "
            "(not ZIP, not WQW)", path, sig[0], sig[1], sig[2], sig[3]);
        return 0;
    }

    /* 标准 ZIP — 尝试用 ui_zip 读取 fileinfo.txt */
    ui_zip_t *z = NULL;
    if (ui_zip_open(path, &z) < 0) {
        LOG("try_load_from_root_dat: cannot open %s as ZIP", path);
        return 0;
    }

    size_t info_size;
    if (ui_zip_find(z, "fileinfo.txt", &info_size) < 0) {
        LOG("try_load_from_root_dat: fileinfo.txt not found in %s", path);
        ui_zip_close(z);
        return 0;
    }

    void *info_data = NULL;
    size_t info_out_size;
    if (ui_zip_extract(z, "fileinfo.txt", &info_data, &info_out_size) < 0) {
        ERR("try_load_from_root_dat: extract fileinfo.txt failed");
        ui_zip_close(z);
        return 0;
    }

    int count = game_list_parse_csv((const char *)info_data, info_out_size,
                                     entries, max_entries);
    free(info_data);
    ui_zip_close(z);
    return count;
}

/* ---- 游戏列表加载 ---- */

int game_list_load(void)
{
    g_gl.count = 0;
    g_gl.selected = 0;
    g_gl.offset = 0;

    if (!g_gl.entries) {
        g_gl.capacity = GL_MAX_GAMES;
        g_gl.entries = calloc((size_t)g_gl.capacity, sizeof(game_entry_t));
        if (!g_gl.entries) {
            ERR("game_list_load: calloc failed");
            return -1;
        }
    }

    /* 加载 filelist.xml */
    load_filelist_xml();

    /* 加载收藏 */
    {
        char fav_path[512];
        snprintf(fav_path, sizeof(fav_path), "%sfavorites.lst", work_path);
        FILE *fp = fopen(fav_path, "r");
        if (fp) {
            char line[GL_PATH_LEN];
            g_fav_count = 0;
            while (fgets(line, sizeof(line), fp) && g_fav_count < GL_MAX_FAVORITES) {
                trim_str(line);
                if (line[0]) {
                    strncpy(g_favorites[g_fav_count], line, GL_PATH_LEN - 1);
                    g_fav_count++;
                }
            }
            fclose(fp);
        }
    }

    /* 加载最近列表 */
    {
        char rec_path[512];
        snprintf(rec_path, sizeof(rec_path), "%srecent.lst", work_path);
        FILE *fp = fopen(rec_path, "r");
        if (fp) {
            char line[GL_PATH_LEN];
            g_recent_count = 0;
            while (fgets(line, sizeof(line), fp) && g_recent_count < GL_MAX_FAVORITES) {
                trim_str(line);
                if (line[0]) {
                    strncpy(g_recent[g_recent_count], line, GL_PATH_LEN - 1);
                    g_recent_count++;
                }
            }
            fclose(fp);
        }
    }

    /* 标记收藏状态 */
    for (int i = 0; i < g_gl.count; i++) {
        g_gl.entries[i].is_favorite = false;
    }

    /* 尝试从 root.dat 加载 */
    int count = try_load_from_root_dat(g_gl.entries, g_gl.capacity);

    /* 尝试从 fileinfo 文件加载 */
    if (count == 0) {
        char info_path[512];
        snprintf(info_path, sizeof(info_path), "%sfileinfo", work_path);
        FILE *fp = fopen(info_path, "r");
        if (fp) {
            fseek(fp, 0, SEEK_END);
            long fsize = ftell(fp);
            fseek(fp, 0, SEEK_SET);
            if (fsize > 0 && fsize < 10 * 1024 * 1024) {
                char *buf = malloc(fsize + 1);
                if (buf) {
                    fread(buf, 1, fsize, fp);
                    buf[fsize] = '\0';
                    count = game_list_parse_csv(buf, (size_t)fsize,
                                                g_gl.entries, g_gl.capacity);
                    free(buf);
                }
            }
            fclose(fp);
        }
    }

    /* RC-3: 以 cores/filelist.xml 为权威游戏清单填充（135 条 + 核心映射） */
    if (count == 0) {
        count = game_list_populate_from_filelist();
    }

    /* 回退：目录扫描 000-008。
     * 修复两处根因：
     *  (RC-2a) 原用 work_path=/sdcard/cubegm/ 拼 "000"，但 ROM 目录实际在 SD 根
     *          /sdcard/（rom_base_path），原路径根本不存在 → 恒 0。
     *  (RC-2b) 原 `g_gl.count = count`（count 仍为 0）会把 scan_directory 刚递增
     *          进 g_gl.count 的条目全部清零 → 即使扫到也丢。现用前后差值累加。 */
    if (count == 0) {
        int before = g_gl.count;  /* 扫描前（此时应恒为 0） */
        const char *dirs[] = { "000", "001", "002", "003",
                               "004", "005", "006", "007", "008" };
        const char *bases[] = { rom_base_path, work_path };  /* SD 根优先, 次 cubegm/ */
        for (int b = 0; b < 2 && count == 0; b++) {
            struct stat sb;
            for (int i = 0; i < 9; i++) {
                if (g_gl.count >= g_gl.capacity) break;
                char dir_path[512];
                snprintf(dir_path, sizeof(dir_path), "%s%s",
                         bases[b], dirs[i]);
                if (stat(dir_path, &sb) != 0) continue;  /* 目录不存在则跳过 */
                if (!S_ISDIR(sb.st_mode)) continue;
                scan_directory(dir_path, NULL);
            }
        }
        count = g_gl.count - before;  /* 累加扫描到的条目，而非清零 */
    }

    g_gl.count = count;
    g_gl.loaded = count > 0;

    LOG("game_list_load: total %d games (root.dat=%d, dirs=%d)",
        count, 0, count);

    return g_gl.loaded ? 0 : -1;
}

/* ---- 公开 API ---- */

int game_list_init(void)
{
    memset(&g_gl, 0, sizeof(g_gl));
    memset(g_favorites, 0, sizeof(g_favorites));
    memset(g_recent, 0, sizeof(g_recent));
    g_fav_count = 0;
    g_recent_count = 0;
    g_filelist_count = 0;
    return 0;
}

void game_list_free(void)
{
    if (g_gl.entries) { free(g_gl.entries); g_gl.entries = NULL; }
    g_gl.count = g_gl.capacity = 0;
    g_gl.loaded = false;
}

const game_entry_t *game_list_get(int index)
{
    if (index < 0 || index >= g_gl.count) return NULL;
    return &g_gl.entries[index];
}

int game_list_count(void) { return g_gl.count; }
bool game_list_is_loaded(void) { return g_gl.loaded; }

int game_list_add_favorite(const char *rom_path)
{
    if (!rom_path || !rom_path[0]) return -1;
    if (game_list_is_favorite(rom_path)) return 0;
    if (g_fav_count >= GL_MAX_FAVORITES) return -1;

    strncpy(g_favorites[g_fav_count], rom_path, GL_PATH_LEN - 1);
    g_fav_count++;

    /* 标记条目 */
    for (int i = 0; i < g_gl.count; i++) {
        if (strcmp(g_gl.entries[i].path, rom_path) == 0) {
            g_gl.entries[i].is_favorite = true;
            break;
        }
    }
    return 0;
}

int game_list_remove_favorite(const char *rom_path)
{
    if (!rom_path || !rom_path[0]) return -1;
    for (int i = 0; i < g_fav_count; i++) {
        if (strcmp(g_favorites[i], rom_path) == 0) {
            /* 移到末尾后减 1 */
            for (int j = i; j < g_fav_count - 1; j++) {
                strcpy(g_favorites[j], g_favorites[j+1]);
            }
            g_fav_count--;
            g_favorites[g_fav_count][0] = '\0';
            break;
        }
    }
    return 0;
}

bool game_list_is_favorite(const char *rom_path)
{
    if (!rom_path) return false;
    for (int i = 0; i < g_fav_count; i++) {
        if (strcmp(g_favorites[i], rom_path) == 0) return true;
    }
    return false;
}

int game_list_update_recent(const char *rom_path)
{
    if (!rom_path || !rom_path[0]) return -1;

    /* 如果已存在，移到开头 */
    for (int i = 0; i < g_recent_count; i++) {
        if (strcmp(g_recent[i], rom_path) == 0) {
            for (int j = i; j > 0; j--) {
                strcpy(g_recent[j], g_recent[j-1]);
            }
            strcpy(g_recent[0], rom_path);
            return 0;
        }
    }

    /* 新条目，插到开头 */
    if (g_recent_count >= GL_MAX_FAVORITES) return -1;
    for (int i = g_recent_count; i > 0; i--) {
        strcpy(g_recent[i], g_recent[i-1]);
    }
    strcpy(g_recent[0], rom_path);
    g_recent_count++;
    return 0;
}

int game_list_save_recent(void)
{
    char path[512];
    snprintf(path, sizeof(path), "%srecent.lst", work_path);
    FILE *fp = fopen(path, "w");
    if (!fp) return -1;
    for (int i = 0; i < g_recent_count; i++) {
        fprintf(fp, "%s\n", g_recent[i]);
    }
    fclose(fp);
    LOG("game_list_save_recent: saved %d entries to %s", g_recent_count, path);
    return 0;
}

int game_list_save_favorites(void)
{
    char path[512];
    snprintf(path, sizeof(path), "%sfavorites.lst", work_path);
    FILE *fp = fopen(path, "w");
    if (!fp) return -1;
    for (int i = 0; i < g_fav_count; i++) {
        fprintf(fp, "%s\n", g_favorites[i]);
    }
    fclose(fp);
    LOG("game_list_save_favorites: saved %d entries to %s", g_fav_count, path);
    return 0;
}
