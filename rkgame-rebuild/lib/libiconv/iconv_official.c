/* ============================================================
 * iconv_official.c - 官方 libiconv 1.19 转换表集成
 * ============================================================
 *
 * 目的：用 GNU libiconv 1.19 官方源码替换简化桩实现
 * 来源：https://ftp.gnu.org/gnu/libiconv/libiconv-1.19.tar.gz
 * 许可证：LGPL-2.1-or-later
 *
 * 集成方式：
 *   - #define static 使官方 static 函数变为非静态（导出符号）
 *   - 包含官方转换表头文件
 *   - 官方函数直接导出（factory rkgame 用官方签名调用）
 *
 * 支持的编码：
 *   - GBK / GB2312 / CP936 (gbk_mbtowc, gbk_wctomb, gb2312_mbtowc, ...)
 *   - Big5 / CP950 (big5_mbtowc, big5_wctomb)
 *   - JIS X 0208 (jisx0208_mbtowc, jisx0208_wctomb)
 *   - CNS 11643 (cns11643_mbtowc, cns11643_wctomb)
 * ============================================================ */

/* 关键：使官方 static 函数变为非静态（导出符号） */
#define static

/* 官方 libiconv 转换表头文件（converters.h 末尾已 #include 所有） */
#include "official/converters.h"

/* 恢复 static 定义 */
#undef static
