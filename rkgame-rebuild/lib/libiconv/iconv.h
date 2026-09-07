/* ============================================================
 * iconv.h - libiconv 字符编码转换库接口（简化版）
 * ============================================================
 *
 * 原厂 libiconv 符号分析：636 个符号，859 KB
 * 支持：GBK, Big5, JIS, UTF-8 等 30+ 种字符集
 *
 * 本实现：简化版，支持基本编码转换
 * 目标：100% 还原原厂功能
 * ============================================================ */

#ifndef ICONV_H
#define ICONV_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stddef.h>

/* iconv_t 类型 */
typedef void *iconv_t;

#define ICONV_CONST const

/* 特殊值 */
#define ICONV_ERR ((size_t)-1)

/* ---- 核心 API ---- */

/* 打开转换描述符 */
iconv_t iconv_open(const char *tocode, const char *fromcode);

/* 关闭转换描述符 */
int iconv_close(iconv_t cd);

/* 执行转换 */
size_t iconv(iconv_t cd, 
              char **inbuf, size_t *inbytesleft,
              char **outbuf, size_t *outbytesleft);

/* 重置转换描述符 */
int iconv_reset(iconv_t cd);

#ifdef __cplusplus
}
#endif

#endif /* ICONV_H */
