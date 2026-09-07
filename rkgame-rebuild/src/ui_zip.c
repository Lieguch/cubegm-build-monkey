/* ============================================================
 * ui_zip.c — 精简 ZIP 读取器（P1.3）
 * ============================================================
 *
 * 工厂对齐（Ghidra mui_menu_ui.c）：
 *   OpenZipU / FindZipItemA / UnzipItem — minizip API
 *
 * 本实现：
 *   - EOCD 扫描 → 中央目录 → 本地头 → 解压
 *   - stored (method=0) 直接 memcpy
 *   - deflate (method=8) 用 inflateInit2(-15) raw deflate
 *   - 工厂 rkgame NEEDED=libz.so.1 已链接
 * ============================================================ */

#include "ui_zip.h"
#include "debug.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

/* ZIP 签名常量 */
#define ZIP_SIG_LOCAL   0x04034b50u
#define ZIP_SIG_CD      0x02014b50u
#define ZIP_SIG_EOCD    0x06054b50u

#define ZIP_METHOD_STORE  0
#define ZIP_METHOD_DEFLATE 8

#define ZIP_MAX_COMMENT   65535
#define ZIP_MAX_EXTRA     65535

/* 中央目录条目 */
typedef struct {
    char     name[256];
    uint16_t method;
    uint32_t comp_size;
    uint32_t uncomp_size;
    uint32_t local_hdr_offset;
    uint16_t name_len;
    uint16_t extra_len;
} zip_cd_entry_t;

struct ui_zip {
    FILE             *fp;
    uint32_t         cd_offset;
    uint32_t         cd_count;
    zip_cd_entry_t   *entries;
};

/* 读 16/32 位 LE 辅助 */
static uint16_t rd_u16(const uint8_t *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}
static uint32_t rd_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* ---- 打开 zip ---- */

int ui_zip_open(const char *path, ui_zip_t **out)
{
    if (!path || !out) return -1;

    FILE *fp = fopen(path, "rb");
    if (!fp) {
        ERR("ui_zip_open: cannot open %s", path);
        return -1;
    }

    /* 获取文件大小 */
    fseek(fp, 0, SEEK_END);
    long fsize = ftell(fp);
    if (fsize < 22) {
        ERR("ui_zip_open: %s too small (%ld B)", path, fsize);
        fclose(fp);
        return -1;
    }

    /* 扫描 EOCD：从文件末尾向前搜索 0x06054b50 */
    /* EOCD 最小 22 字节，comment 最多 65535 字节 */
    long scan_start = fsize - 22 - ZIP_MAX_COMMENT;
    if (scan_start < 0) scan_start = 0;

    fseek(fp, scan_start, SEEK_SET);
    long scan_len = fsize - scan_start;
    uint8_t *scan_buf = (uint8_t *)malloc((size_t)scan_len);
    if (!scan_buf) { fclose(fp); return -1; }

    long nread = (long)fread(scan_buf, 1, (size_t)scan_len, fp);
    if (nread != scan_len) {
        free(scan_buf);
        fclose(fp);
        return -1;
    }

    uint32_t eocd_off = 0;
    int found = 0;
    for (long i = nread - 22; i >= 0; i--) {
        if (scan_buf[i] == 0x50 && scan_buf[i+1] == 0x4b &&
            scan_buf[i+2] == 0x05 && scan_buf[i+3] == 0x06) {
            eocd_off = (uint32_t)i;
            found = 1;
            break;
        }
    }
    free(scan_buf);

    if (!found) {
        ERR("ui_zip_open: %s is not a valid zip (no EOCD)", path);
        fclose(fp);
        return -1;
    }

    /* 读 EOCD */
    fseek(fp, scan_start + eocd_off, SEEK_SET);
    uint8_t eocd[22];
    if (fread(eocd, 1, 22, fp) != 22) {
        fclose(fp);
        return -1;
    }

    uint16_t cd_count  = rd_u16(eocd + 10);
    uint32_t cd_size   = rd_u32(eocd + 12);
    uint32_t cd_offset = rd_u32(eocd + 16);
    (void)cd_size;

    /* 读中央目录 */
    if (cd_count == 0) {
        fclose(fp);
        return -1;
    }

    ui_zip_t *z = (ui_zip_t *)calloc(1, sizeof(ui_zip_t));
    if (!z) { fclose(fp); return -1; }

    z->entries = (zip_cd_entry_t *)calloc(cd_count, sizeof(zip_cd_entry_t));
    if (!z->entries) { free(z); fclose(fp); return -1; }

    fseek(fp, (long)cd_offset, SEEK_SET);

    for (int i = 0; i < cd_count; i++) {
        uint8_t hdr[46];
        if (fread(hdr, 1, 46, fp) != 46) {
            ERR("ui_zip_open: CD entry %d read failed", i);
            break;
        }

        /* 校验签名 */
        if (rd_u32(hdr) != ZIP_SIG_CD) {
            ERR("ui_zip_open: CD entry %d bad signature 0x%08x",
                i, rd_u32(hdr));
            break;
        }

        zip_cd_entry_t *e = &z->entries[i];
        e->method           = rd_u16(hdr + 10);
        e->comp_size        = rd_u32(hdr + 20);
        e->uncomp_size      = rd_u32(hdr + 24);
        e->name_len         = rd_u16(hdr + 28);
        e->extra_len        = rd_u16(hdr + 30);
        e->local_hdr_offset = rd_u32(hdr + 42);

        /* 读文件名 */
        uint16_t nlen = e->name_len;
        if (nlen >= 256) nlen = 255;
        if (fread(e->name, 1, nlen, fp) != nlen) break;
        e->name[nlen] = '\0';

        /* 跳过 extra + comment */
        fseek(fp, e->extra_len + rd_u16(hdr + 32), SEEK_CUR);
    }

    z->fp          = fp;
    z->cd_offset   = cd_offset;
    z->cd_count    = cd_count;

    *out = z;
    LOG("ui_zip_open: %s (%d entries)", path, cd_count);
    return 0;
}

/* ---- 查找条目 ---- */

static int find_entry(const ui_zip_t *z, const char *name)
{
    for (int i = 0; i < z->cd_count; i++) {
        if (strcmp(z->entries[i].name, name) == 0)
            return i;
    }
    return -1;
}

int ui_zip_find(const ui_zip_t *z, const char *name, size_t *out_size)
{
    int idx = find_entry(z, name);
    if (idx < 0) return -1;
    if (out_size) *out_size = (size_t)z->entries[idx].uncomp_size;
    return 0;
}

/* ---- 解压 ---- */

int ui_zip_extract(const ui_zip_t *z, const char *name,
                   void **out_data, size_t *out_size)
{
    int idx = find_entry(z, name);
    if (idx < 0) return -1;

    const zip_cd_entry_t *e = &z->entries[idx];
    size_t usize = (size_t)e->uncomp_size;
    size_t csize = (size_t)e->comp_size;

    uint8_t *out = (uint8_t *)malloc(usize > 0 ? usize : 1);
    if (!out) return -1;

    /* 读本地文件头，获取实际数据偏移 */
    fseek(z->fp, (long)e->local_hdr_offset, SEEK_SET);
    uint8_t lhdr[30];
    if (fread(lhdr, 1, 30, z->fp) != 30) {
        free(out);
        return -1;
    }

    if (rd_u32(lhdr) != ZIP_SIG_LOCAL) {
        ERR("ui_zip_extract: %s local header bad signature", name);
        free(out);
        return -1;
    }

    uint16_t l_name_len = rd_u16(lhdr + 26);
    uint16_t l_extra_len = rd_u16(lhdr + 28);
    uint32_t l_comp_size = rd_u32(lhdr + 18);
    uint32_t l_uncomp_size = rd_u32(lhdr + 22);

    /* 优先用本地头的值（更准确） */
    usize = (size_t)l_uncomp_size;
    csize = (size_t)l_comp_size;
    if (usize == 0 && e->uncomp_size > 0) usize = (size_t)e->uncomp_size;
    if (csize == 0 && e->comp_size > 0)   csize = (size_t)e->comp_size;

    /* 跳过 name + extra */
    fseek(z->fp, (long)(l_name_len + l_extra_len), SEEK_CUR);

    /* 读压缩数据 */
    uint8_t *cbuf = (uint8_t *)malloc(csize > 0 ? csize : 1);
    if (!cbuf) { free(out); return -1; }

    long nread = (long)fread(cbuf, 1, (size_t)csize, z->fp);
    if ((long)csize != nread) {
        free(cbuf);
        free(out);
        return -1;
    }

    /* 解压 */
    if (e->method == ZIP_METHOD_STORE) {
        /* 存储模式：直接拷贝 */
        if (usize != csize) {
            /* 大小不一致，用较小的 */
            size_t n = usize < csize ? usize : csize;
            memcpy(out, cbuf, n);
            if (out_size) *out_size = n;
            else *out_size = usize;
        } else {
            memcpy(out, cbuf, usize);
        }
    } else if (e->method == ZIP_METHOD_DEFLATE) {
        /* Deflate 模式：用 inflateInit2(-15) raw deflate */
        z_stream strm;
        memset(&strm, 0, sizeof(strm));

        if (inflateInit2(&strm, -15) != Z_OK) {
            free(cbuf);
            free(out);
            return -1;
        }

        strm.next_in  = cbuf;
        strm.avail_in = (uInt)csize;
        strm.next_out = out;
        strm.avail_out = (uInt)usize;

        int ret = inflate(&strm, Z_FINISH);
        inflateEnd(&strm);

        if (ret != Z_STREAM_END) {
            ERR("ui_zip_extract: inflate failed for %s (ret=%d)", name, ret);
            free(cbuf);
            free(out);
            return -1;
        }

        *out_size = usize - strm.avail_out;
    } else {
        ERR("ui_zip_extract: unsupported method %u for %s", e->method, name);
        free(cbuf);
        free(out);
        return -1;
    }

    free(cbuf);
    *out_data = out;
    return 0;
}

/* ---- 关闭 ---- */

void ui_zip_close(ui_zip_t *z)
{
    if (!z) return;
    if (z->fp) fclose(z->fp);
    if (z->entries) free(z->entries);
    free(z);
}

/* ---- 列表（调试用） ---- */

int ui_zip_list(const ui_zip_t *z, char names[][256], int max_entries)
{
    int n = z->cd_count < max_entries ? z->cd_count : max_entries;
    for (int i = 0; i < n; i++) {
        strncpy(names[i], z->entries[i].name, 255);
        names[i][255] = '\0';
    }
    return n;
}
