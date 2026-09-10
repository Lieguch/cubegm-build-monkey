/* ============================================================
 * wqw.c — WQW\x03 容器格式解析（SF3000/RK3036G 私有格式）
 * ============================================================
 *
 * 完整逆向结果（2026-09-07，基于 Ghidra 反编译 + root.dat 字节实测）：
 *
 *   WQW = ZIP 变体，仅 magic 替换（PK→WQW）+ filename XOR 加密。
 *   数据本身是标准 zlib deflate（method=8），无需 XOR。
 *
 *   key2 全局数组（rkgame BSS 0x3e190c, 28 字节）字段映射：
 *     [0..3]   "WQ\x01" + 0x00  (v01 EOCD magic)
 *     [4..7]   "WQ\x02" + 0x00  (v02 CD magic)
 *     [8..11]  "PK\x03\x04"     (标准 LFH，非加密变体)
 *     [12..15] "WQW\x03" + 0x00 (加密 LFH magic)
 *     [16..23] 保留
 *     [24]     0xE5              (filename XOR key)
 *     [25..27] 保留
 *
 * 布局（每个文件独立 [LFH + compressed data] 序列，之后 CD 聚集，最后 EOCD）：
 *
 *   [LFH#0 (30B) + name#0 + extra#0][Data#0 (csize)]
 *   [LFH#1 (30B) + name#1 + extra#1][Data#1]
 *   ...
 *   [LFH#N][Data#N]
 *   [CD#0 (46B + name + extra + comment)]
 *   ...
 *   [CD#N]
 *   [EOCD (22B)]
 *
 * 实测验证（root.dat, 725,382 bytes, 10 entries）：
 *   v03 #0 @ 0:       "000.raw"      csize=687    usize=691200
 *   v03 #1 @ 724:     "001.raw"      csize=687    usize=691200
 *   ...
 *   v03 #8 @ 5792:    "008.raw"      csize=687    usize=691200
 *   v03 #9 @ 6516:    "fileinfo.txt" csize=718267 usize=2373964
 *   EOCD @ 725360:    cd_offset=724825, cd_size=535, total=10
 *
 * 关键：v03 压缩数据是标准 zlib raw deflate（wbits=-15），
 *      不需要 XOR。只有 v03/v02 里的 filename 字段用 XOR 0xE5。
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/stat.h>
#include <zlib.h>

#include "rkgame.h"
#include "debug.h"

/* WQW magic (little-endian) */
#define WQW_MAGIC_V03   0x03575157u   /* "WQW\x03" LFH */
#define WQW_MAGIC_V02   0x02575157u   /* "WQW\x02" CD  */
#define WQW_MAGIC_V01   0x01575157u   /* "WQW\x01" EOCD */
#define WQW_XOR_KEY     0xE5u         /* filename XOR key */
#define WQW_MAX_FILES   256
#define WQW_MAX_NAME    256

/* WQW entry and container types defined in rkgame.h */

/* Helpers */

static uint16_t rd16(const unsigned char *p)
{
    return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}

static uint32_t rd32(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Decrypt filename (XOR 0xE5) */
static void wqw_decrypt_name(const unsigned char *src, int len, char *dst)
{
    int n = len < WQW_MAX_NAME - 1 ? len : WQW_MAX_NAME - 1;
    for (int i = 0; i < n; i++) {
        dst[i] = (char)(src[i] ^ WQW_XOR_KEY);
    }
    dst[n] = '\0';
}

/* ============================================================
 * wqw_inflate_raw — raw deflate 解压（wbits=-15）
 *
 * 根因（本地真 root.dat 实测 2026-09-09）：
 *   WQW\x03 容器的压缩数据是 RAW DEFLATE（无 2 字节 zlib 头），
 *   zlib 格式 uncompress() 认头 → 报 "incorrect header check"。
 *   全部 10 条目（000.raw~008.raw + fileinfo.txt）本地实证：
 *     uncompress(zlib) 全 FAIL，inflateInit2(-15) 全 OK。
 *   故工厂 OpenZipU/UnzipItem 走的是 raw inflate，本实现须一致。
 *
 * 返回 0 成功（*out_data 指向 malloc 缓冲，调用者 free），-1 失败。
 * ============================================================ */
static int wqw_inflate_raw(const unsigned char *comp, uLong comp_len,
                           unsigned char **out_data, size_t *out_size,
                           uLong expected_usize)
{
    z_stream zs;
    memset(&zs, 0, sizeof(zs));
    zs.next_in = (unsigned char *)comp;
    zs.avail_in = (uInt)comp_len;

    /* 先按 expected_usize 分配；raw 流可能略小于/等于它 */
    size_t cap = (expected_usize > 0) ? (size_t)expected_usize : (size_t)comp_len + 64;
    unsigned char *buf = (unsigned char *)malloc(cap);
    if (!buf) return -1;

    zs.next_out = buf;
    zs.avail_out = (uInt)cap;

    /* -15 = raw deflate */
    if (inflateInit2(&zs, -15) != Z_OK) {
        free(buf);
        return -1;
    }

    int ret = inflate(&zs, Z_FINISH);
    if (ret != Z_STREAM_END && ret != Z_OK) {
        /* 数据比 expected 大？再给一次机会：扩大缓冲重试 */
        inflateEnd(&zs);
        free(buf);
        cap = comp_len * 4 + 256;
        buf = (unsigned char *)malloc(cap);
        if (!buf) return -1;
        memset(&zs, 0, sizeof(zs));
        zs.next_in = (unsigned char *)comp;
        zs.avail_in = (uInt)comp_len;
        zs.next_out = buf;
        zs.avail_out = (uInt)cap;
        if (inflateInit2(&zs, -15) != Z_OK) { inflateEnd(&zs); free(buf); return -1; }
        ret = inflate(&zs, Z_FINISH);
        if (ret != Z_STREAM_END && ret != Z_OK) {
            /* D1 诊断（2026-09-10）：真机可定位 zlib 版本/流错误/缓冲大小 */
            ERR("wqw_inflate_raw: inflate fail ret=%d (%s) zlib=%s "
                "in=%lu/%lu out=%lu/%lu",
                ret, zs.msg ? zs.msg : "?", zlibVersion(),
                (unsigned long)zs.avail_in, (unsigned long)comp_len,
                (unsigned long)zs.total_out, (unsigned long)cap);
            inflateEnd(&zs);
            free(buf);
            return -1;
        }
    }
    inflateEnd(&zs);

    *out_data = buf;
    *out_size = (size_t)(zs.total_out);
    return 0;
}

/* ============================================================
 * wqw_is_container — 检查文件是否以 "WQW\x03" 开头
 * ============================================================ */

bool wqw_is_container(const char *path)
{
    FILE *fp = fopen(path, "rb");
    if (!fp) return false;
    unsigned char magic[4] = {0};
    size_t r = fread(magic, 1, 4, fp);
    fclose(fp);
    return (r == 4 && magic[0] == 'W' && magic[1] == 'Q' &&
            magic[2] == 'W' && magic[3] == 0x03);
}

/* ============================================================
 * wqw_find_eocd — 从文件末尾向后扫描 WQW\x01 EOCD
 * ============================================================ */

static int wqw_find_eocd(const unsigned char *data, size_t size,
                         uint32_t *cd_offset, uint32_t *cd_size, uint16_t *count)
{
    /* EOCD = 22 bytes + optional comment (up to 65535) */
    if (size < 22) return -1;

    size_t search_end = size - 22;
    size_t search_start = (search_end >= 65557) ? (search_end - 65557) : 0;

    for (size_t i = search_end; i >= search_start; i--) {
        if (data[i] == 'W' && data[i + 1] == 'Q' &&
            data[i + 2] == 'W' && data[i + 3] == 0x01) {
            *cd_offset = rd32(&data[i + 16]);
            *cd_size   = rd32(&data[i + 12]);
            *count     = rd16(&data[i + 8]);
            LOG("wqw_eocd: found at %zu, cd_offset=%u, cd_size=%u, count=%u",
                i, *cd_offset, *cd_size, *count);
            return 0;
        }
    }
    return -1;
}

/* ============================================================
 * wqw_parse — 解析完整容器
 * ============================================================ */

int wqw_parse(const char *path, wqw_container_t *out)
{
    memset(out, 0, sizeof(*out));

    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;

    struct stat st;
    if (fstat(fileno(fp), &st) != 0) { fclose(fp); return -1; }
    size_t size = (size_t)st.st_size;

    unsigned char *data = (unsigned char *)malloc(size);
    if (!data) { fclose(fp); return -1; }
    if (fread(data, 1, size, fp) != size) {
        free(data); fclose(fp); return -1;
    }
    fclose(fp);

    /* 定位 EOCD */
    uint32_t cd_offset, cd_size;
    uint16_t count;
    if (wqw_find_eocd(data, size, &cd_offset, &cd_size, &count) != 0) {
        free(data);
        return -1;
    }

    if (cd_offset >= size || cd_offset + cd_size > size) {
        ERR("wqw_parse: CD out of bounds (cd_offset=%u, size=%zu)", cd_offset, size);
        free(data);
        return -1;
    }

    /* 遍历 CD entries */
    int n = count < WQW_MAX_FILES ? count : WQW_MAX_FILES;
    uint32_t pos = cd_offset;
    int i = 0;

    for (i = 0; i < n; i++) {
        if (pos + 46 > size) break;

        wqw_entry_t *e = &out->entries[i];
        memset(e, 0, sizeof(*e));

        uint32_t sig = rd32(&data[pos]);
        if (sig != WQW_MAGIC_V02) {
            LOG("wqw_parse: CD entry %d magic mismatch at %u (0x%08x)",
                i, pos, sig);
            i--;
            break;
        }

        e->method     = rd16(&data[pos + 10]);
        e->time       = rd16(&data[pos + 12]);
        e->date       = rd16(&data[pos + 14]);
        e->crc        = rd32(&data[pos + 16]);
        e->csize      = rd32(&data[pos + 20]);
        e->usize      = rd32(&data[pos + 24]);

        uint16_t namelen    = rd16(&data[pos + 28]);
        uint16_t extralen   = rd16(&data[pos + 30]);
        uint16_t commentlen = rd16(&data[pos + 32]);
        e->lfh_offset = rd32(&data[pos + 42]);

        /* 解密文件名 */
        e->namelen = namelen;
        if (pos + 46 + namelen <= size) {
            wqw_decrypt_name(&data[pos + 46], namelen, e->name);
        } else {
            e->name[0] = '\0';
        }

        /* 计算压缩数据绝对偏移：LFH header + LFH name + LFH extra */
        if (e->lfh_offset + 30 <= size) {
            uint16_t lfh_namelen  = rd16(&data[e->lfh_offset + 26]);
            uint16_t lfh_extralen = rd16(&data[e->lfh_offset + 28]);
            e->data_offset = e->lfh_offset + 30 + lfh_namelen + lfh_extralen;
        } else {
            e->data_offset = 0;
        }

        pos += 46 + namelen + extralen + commentlen;
    }

    out->count = i;
    free(data);

    LOG("wqw_parse: %s — %d entries (cd_offset=%u)",
        path, out->count, cd_offset);
    return out->count;
}

/* ============================================================
 * wqw_extract — 提取容器内指定文件（按名称匹配）
 *
 * 流程：
 *   1. 解析容器
 *   2. 找到匹配 entry
 *   3. 从 data_offset 读 csize 字节
 *   4. zlib uncompress (deflate) 得到 usize 字节
 *   5. CRC 校验（可选）
 *
 * 返回 0 成功，-1 失败。调用者负责 free(*out_data)。
 * ============================================================ */

int wqw_extract(const char *path, const char *filename,
                unsigned char **out_data, size_t *out_size)
{
    wqw_container_t c;
    int n = wqw_parse(path, &c);
    if (n <= 0) return -1;

    int idx = -1;
    for (int i = 0; i < n; i++) {
        if (strcmp(c.entries[i].name, filename) == 0) {
            idx = i;
            break;
        }
    }
    if (idx < 0) {
        ERR("wqw_extract: '%s' not found in %s", filename, path);
        return -1;
    }

    const wqw_entry_t *e = &c.entries[idx];
    if (e->csize == 0 || e->data_offset == 0) {
        ERR("wqw_extract: invalid entry (csize=%u, data_off=%u)",
            e->csize, e->data_offset);
        return -1;
    }

    /* 读取压缩数据 */
    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;
    if (fseek(fp, (long)e->data_offset, SEEK_SET) != 0) { fclose(fp); return -1; }

    unsigned char *comp = (unsigned char *)malloc(e->csize);
    if (!comp) { fclose(fp); return -1; }
    if (fread(comp, 1, e->csize, fp) != e->csize) {
        free(comp); fclose(fp);
        ERR("wqw_extract: short read at %s:%u", path, e->data_offset);
        return -1;
    }
    fclose(fp);

    /* 解压
     * method==0：stored（未压缩），直接拷贝 csize 字节
     * method==8：RAW DEFLATE（wbits=-15；本地真 root.dat 实证 2026-09-09，
     *            全部条目均为 raw deflate，zlib 格式 uncompress 报 header check） */
    unsigned char *decomp = NULL;
    size_t decomp_size = 0;
    if (e->method == 0) {
        if (e->csize > e->usize) { free(comp); return -1; }
        decomp = (unsigned char *)malloc(e->csize ? e->csize : 1);
        if (!decomp) { free(comp); return -1; }
        memcpy(decomp, comp, e->csize);
        decomp_size = e->csize;
        LOG("wqw_extract: %s -> stored %u B (method=0)", filename, e->csize);
    } else if (wqw_inflate_raw(comp, (uLong)e->csize, &decomp, &decomp_size, e->usize) != 0) {
        free(comp);
        ERR("wqw_extract: raw-inflate failed for %s", filename);
        return -1;
    }
    free(comp);

    *out_data = decomp;
    *out_size = decomp_size;

    /* CRC 校验 */
    uint32_t crc = crc32(0L, Z_NULL, 0);
    crc = crc32(crc, decomp, decomp_size);
    if (crc != e->crc) {
        LOG("wqw_extract: CRC mismatch for %s (expected 0x%08x, got 0x%08x)",
            filename, e->crc, crc);
    }

    LOG("wqw_extract: %s -> %s (%zu B, method=%u)",
        filename, path, *out_size, e->method);
    return 0;
}

/* ============================================================
 * wqw_list — 列出容器内所有文件名（调试用）
 * ============================================================ */

int wqw_list(const char *path)
{
    wqw_container_t c;
    int n = wqw_parse(path, &c);
    if (n <= 0) return 0;

    LOG("wqw_list: %s — %d entries:", path, n);
    for (int i = 0; i < n; i++) {
        LOG("  #%d: '%s'  csize=%u  usize=%u  method=%u  data_off=0x%x",
            i, c.entries[i].name, c.entries[i].csize,
            c.entries[i].usize, c.entries[i].method,
            c.entries[i].data_offset);
    }
    return n;
}

/* ============================================================
 * wqw_extract_index — 按索引提取（用于遍历）
 * ============================================================ */

int wqw_extract_index(const char *path, int index,
                      unsigned char **out_data, size_t *out_size,
                      char *out_name, size_t name_size)
{
    wqw_container_t c;
    int n = wqw_parse(path, &c);
    if (n <= 0 || index < 0 || index >= n) return -1;

    if (name_size > 0 && out_name) {
        strncpy(out_name, c.entries[index].name, name_size - 1);
        out_name[name_size - 1] = '\0';
    }

    /* 复用 extract 逻辑：临时构造 filename 查找 */
    const wqw_entry_t *e = &c.entries[index];
    if (e->csize == 0 || e->data_offset == 0) return -1;

    FILE *fp = fopen(path, "rb");
    if (!fp) return -1;
    if (fseek(fp, (long)e->data_offset, SEEK_SET) != 0) { fclose(fp); return -1; }

    unsigned char *comp = (unsigned char *)malloc(e->csize);
    if (!comp) { fclose(fp); return -1; }
    if (fread(comp, 1, e->csize, fp) != e->csize) {
        free(comp); fclose(fp); return -1;
    }
    fclose(fp);

    unsigned char *decomp = NULL;
    size_t decomp_size = 0;
    if (e->method == 0) {
        if (e->csize > e->usize) { free(comp); return -1; }
        decomp = (unsigned char *)malloc(e->csize ? e->csize : 1);
        if (!decomp) { free(comp); return -1; }
        memcpy(decomp, comp, e->csize);
        decomp_size = e->csize;
    } else if (wqw_inflate_raw(comp, (uLong)e->csize, &decomp, &decomp_size, e->usize) != 0) {
        free(comp);
        return -1;
    }
    free(comp);

    *out_data = decomp;
    *out_size = decomp_size;
    return 0;
}
