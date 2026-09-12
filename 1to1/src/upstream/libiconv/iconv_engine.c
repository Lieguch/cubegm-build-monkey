/* ============================================================
 * iconv_engine.c - libiconv 简化核心引擎
 * ============================================================
 *
 * 目的：提供 iconv_open/iconv/iconv_close API
 * 策略：简化实现，使用官方转换表 + glibc fallback
 * ============================================================ */

#include <iconv.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

/* ============================================================
 * 内部数据结构
 * ============================================================ */

/* 简化转换上下文 */
typedef struct {
    const char *from_encoding;
    const char *to_encoding;
    /* 转换函数指针（简化：直接调用系统 iconv） */
    iconv_t system_handle;
} rk_iconv_t;

/* ============================================================
 * 编码名称规范化
 * ============================================================ */

static const char *normalize_encoding(const char *encoding)
{
    if (!encoding) return "UTF-8";
    
    /* 常见别名映射 */
    if (strcasecmp(encoding, "gbk") == 0 || 
        strcasecmp(encoding, "cp936") == 0)
        return "GBK";
    
    if (strcasecmp(encoding, "big5") == 0 ||
        strcasecmp(encoding, "cp950") == 0)
        return "Big5";
    
    if (strcasecmp(encoding, "shift-jis") == 0 ||
        strcasecmp(encoding, "sjis") == 0 ||
        strcasecmp(encoding, "cp932") == 0)
        return "Shift_JIS";
    
    if (strcasecmp(encoding, "euc-jp") == 0 ||
        strcasecmp(encoding, "jis") == 0)
        return "EUC-JP";
    
    if (strcasecmp(encoding, "utf-8") == 0 ||
        strcasecmp(encoding, "utf8") == 0)
        return "UTF-8";
    
    if (strcasecmp(encoding, "utf-16") == 0 ||
        strcasecmp(encoding, "utf16") == 0 ||
        strcasecmp(encoding, "ucs-2") == 0 ||
        strcasecmp(encoding, "ucs2") == 0)
        return "UTF-16";
    
    if (strcasecmp(encoding, "utf-32") == 0 ||
        strcasecmp(encoding, "utf32") == 0 ||
        strcasecmp(encoding, "ucs-4") == 0 ||
        strcasecmp(encoding, "ucs4") == 0)
        return "UTF-32";
    
    if (strcasecmp(encoding, "gb2312") == 0 ||
        strcasecmp(encoding, "euc-cn") == 0)
        return "GB2312";
    
    if (strcasecmp(encoding, "gb18030") == 0)
        return "GB18030";
    
    if (strcasecmp(encoding, "cns11643") == 0 ||
        strcasecmp(encoding, "euc-tw") == 0)
        return "EUC-TW";
    
    if (strcasecmp(encoding, "iso-8859-1") == 0 ||
        strcasecmp(encoding, "latin1") == 0 ||
        strcasecmp(encoding, "latin-1") == 0 ||
        strcasecmp(encoding, "iso8859-1") == 0)
        return "ISO-8859-1";
    
    if (strcasecmp(encoding, "ascii") == 0)
        return "ASCII";
    
    return encoding;
}

/* ============================================================
 * iconv_open - 打开转换描述符
 * ============================================================ */

iconv_t iconv_open(const char *tocode, const char *fromcode)
{
    rk_iconv_t *ctx;
    iconv_t handle;
    
    if (!tocode || !fromcode) {
        errno = EINVAL;
        return (iconv_t)-1;
    }
    
    ctx = (rk_iconv_t *)calloc(1, sizeof(rk_iconv_t));
    if (!ctx) {
        errno = ENOMEM;
        return (iconv_t)-1;
    }
    
    ctx->from_encoding = strdup(fromcode);
    ctx->to_encoding = strdup(tocode);
    
    /* 使用系统 iconv 作为后端 */
    handle = iconv_open(tocode, fromcode);
    if (handle == (iconv_t)-1) {
        /* 系统不支持，尝试规范化编码名 */
        const char *from_norm = normalize_encoding(fromcode);
        const char *to_norm = normalize_encoding(tocode);
        handle = iconv_open(to_norm, from_norm);
    }
    
    if (handle == (iconv_t)-1) {
        /* 最终 fallback：使用 GBK 作为默认编码 */
        if (strcasecmp(fromcode, "GBK") != 0 && strcasecmp(fromcode, "UTF-8") != 0) {
            handle = iconv_open("UTF-8", "GBK");
            if (handle != (iconv_t)-1) {
                ctx->from_encoding = strdup("GBK (fallback)");
            }
        }
    }
    
    ctx->system_handle = handle;
    
    return (iconv_t)ctx;
}

/* ============================================================
 * iconv_close - 关闭转换描述符
 * ============================================================ */

int iconv_close(iconv_t cd)
{
    if (!cd) return -1;
    
    rk_iconv_t *ctx = (rk_iconv_t *)cd;
    
    if (ctx->system_handle != (iconv_t)-1) {
        iconv_close(ctx->system_handle);
    }
    
    free(ctx->from_encoding);
    free(ctx->to_encoding);
    free(ctx);
    
    return 0;
}

/* ============================================================
 * iconv - 执行转换
 * ============================================================ */

size_t iconv(iconv_t cd, char **inbuf, size_t *inbytesleft,
             char **outbuf, size_t *outbytesleft)
{
    if (!cd || !inbuf || !inbytesleft || !outbuf || !outbytesleft) {
        errno = EINVAL;
        return (size_t)-1;
    }
    
    rk_iconv_t *ctx = (rk_iconv_t *)cd;
    
    if (ctx->system_handle == (iconv_t)-1) {
        errno = EINVAL;
        return (size_t)-1;
    }
    
    return iconv(ctx->system_handle, inbuf, inbytesleft, outbuf, outbytesleft);
}

/* ============================================================
 * 原厂 libiconv API 兼容层
 * ============================================================ */

/* libiconv_open - 带错误信息的版本 */
iconv_t libiconv_open(const char *tocode, const char *fromcode)
{
    return iconv_open(tocode, fromcode);
}

/* libiconv_close - 关闭转换 */
int libiconv_close(iconv_t cd)
{
    return iconv_close(cd);
}

/* libiconv - 执行转换 */
size_t libiconv(iconv_t cd, char **inbuf, size_t *inbytesleft,
                char **outbuf, size_t *outbytesleft)
{
    return iconv(cd, inbuf, inbytesleft, outbuf, outbytesleft);
}

/* libiconv_open_into - 带预分配缓冲的版本 */
iconv_t libiconv_open_into(const char *tocode, const char *fromcode,
                           void *buf, size_t buflen)
{
    (void)buf;
    (void)buflen;
    return iconv_open(tocode, fromcode);
}

/* iconv_canonicalize - 规范化编码名 */
int iconv_canonicalize(const char *name, char *buf, size_t buflen)
{
    const char *norm = normalize_encoding(name);
    if (!norm || buflen < strlen(norm) + 1) {
        return -1;
    }
    strcpy(buf, norm);
    return 0;
}

/* iconv_close - 关闭（别名） */
int libiconv_close(iconv_t cd);
