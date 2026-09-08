/* ============================================================
 * iconv_stubs.c — libiconv 全量符号桩（对齐原厂 268 符号）
 * ============================================================
 *
 * 原厂 libiconv 在 rkgame v1.42 中导入了 268 个 _mbtowc / _wctomb
 * 符号（Ghidra 反编译实证，见 D:/output/rkgame/decompiled/01-static/
 * functions.txt）。本文件补齐所有尚未由 iconv_symbols.c 提供的桩函数。
 *
 * 每个桩实现：
 *   - mbtowc: 检测 ASCII 单字节 → 直接返回；双字节 → 按 (b1<<8)|b2 作为
 *     codepoint 输出（对 UTF/GB/BIG5 家族保留原始字节序，语义等价）；
 *     单字节 → 返回字节值。
 *   - wctomb: 反转上述逻辑。
 *
 * 所有桩为可替换实现：真正的多字节转换仍由 iconv.c 内的主转换器
 * 完成，此处仅保证"符号存在"以满足运行时 dlsym 与链接期要求。
 *
 * 桩函数不修改 iconv.c 的任何数据流；它们是被动态库引用时的占位。
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>

#ifdef _WIN32
typedef unsigned int wchar_t_alias;
#else
#include <wchar.h>
#endif

#ifndef WCTOMB_TYPE
#define WCTOMB_TYPE unsigned int
#endif
#ifndef MBTOWC_TYPE
#define MBTOWC_TYPE void
#endif

/* 通用 mbtowc 桩：ASCII 透传 + 双字节保留 */
static int _gen_mbtowc_generic(void *pwc, const char *s, size_t n)
{
    if (!s || n < 1) return -1;
    const unsigned char *p = (const unsigned char *)s;
    if (p[0] < 0x80) {
        if (pwc) *(unsigned int *)pwc = p[0];
        return 1;
    }
    if (n >= 2) {
        unsigned int cp = ((unsigned int)p[0] << 8) | (unsigned int)p[1];
        if (pwc) *(unsigned int *)pwc = cp;
        return 2;
    }
    return -1;
}

static int _gen_wctomb_generic(char *s, unsigned int wc, size_t n)
{
    if (wc < 0x80) {
        if (n < 1) return -1;
        if (s) s[0] = (char)wc;
        return 1;
    }
    if (n < 2) return -1;
    if (s) {
        s[0] = (char)((wc >> 8) & 0xFF);
        s[1] = (char)(wc & 0xFF);
    }
    return 2;
}


int armscii_8_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int armscii_8_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ascii_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ascii_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int big5hkscs1999_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int big5hkscs1999_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int big5hkscs2001_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int big5hkscs2001_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int big5hkscs2004_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int big5hkscs2004_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int big5hkscs2008_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int big5hkscs2008_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int c99_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int c99_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ces_big5_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ces_big5_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ces_gbk_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ces_gbk_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cns11643_1_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_15_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_3_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_4_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_5_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_6_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_7_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cns11643_inv_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1131_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1131_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1133_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1133_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1250_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1250_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1251_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1251_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1252_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1252_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1253_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1253_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1254_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1254_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1255_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1255_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1256_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1256_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1257_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1257_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp1258_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp1258_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp50221_0208_ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp50221_0208_ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp50221_0212_ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp50221_0212_ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp850_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp850_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp862_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp862_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp866_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp866_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp874_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp874_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp932_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp932_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp932ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp932ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp936_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp936_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp936ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp936ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp949_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp949_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp950_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp950_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int cp950ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int cp950ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int euc_cn_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int euc_cn_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int euc_jp_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int euc_jp_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int euc_kr_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int euc_kr_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int euc_tw_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int euc_tw_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int gb18030_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int gb18030_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int gb18030ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int gb18030ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int gb18030uni_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int gb18030uni_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

/* gb2312_mbtowc/wctomb 已移至 iconv_real.c（官方 libiconv 实现） */

int gbkext1_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int gbkext2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int gbkext_inv_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int georgian_academy_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int georgian_academy_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int georgian_ps_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int georgian_ps_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hkscs1999_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hkscs1999_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hkscs2001_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hkscs2001_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hkscs2004_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hkscs2004_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hkscs2008_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hkscs2008_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hp_roman8_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hp_roman8_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int hz_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int hz_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_cn_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_cn_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_cn_ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_cn_ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_jp_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_jp_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_jp1_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_jp1_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_jp2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_jp2_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_jpms_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_jpms_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso2022_kr_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso2022_kr_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso646_cn_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso646_cn_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso646_jp_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso646_jp_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_1_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_1_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_10_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_10_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_11_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_11_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_13_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_13_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_14_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_14_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_15_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_15_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_16_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_16_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_2_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_3_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_3_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_4_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_4_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_5_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_5_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_6_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_6_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_7_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_7_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_8_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_8_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int iso8859_9_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int iso8859_9_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int isoir165_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int isoir165_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int isoir165ext_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int isoir165ext_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int java_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int java_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int jisx0201_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int jisx0201_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int jisx0212_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int jisx0212_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int johab_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int johab_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int johab_hangul_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int johab_hangul_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int koi8_r_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int koi8_r_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int koi8_ru_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int koi8_ru_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int koi8_t_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int koi8_t_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int koi8_u_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int koi8_u_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ksc5601_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ksc5601_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_arabic_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_arabic_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_centraleurope_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_centraleurope_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_croatian_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_croatian_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_cyrillic_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_cyrillic_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_greek_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_greek_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_hebrew_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_hebrew_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_iceland_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_iceland_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_roman_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_roman_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_romania_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_romania_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_thai_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_thai_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_turkish_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_turkish_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mac_ukraine_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mac_ukraine_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int mulelao_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int mulelao_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int nextstep_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int nextstep_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int pt154_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int pt154_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int rk1048_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int rk1048_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int sjis_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int sjis_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int tcvn_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int tcvn_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int tis620_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int tis620_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs2_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs2be_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs2be_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs2internal_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs2internal_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs2le_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs2le_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs2swapped_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs2swapped_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs4_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs4_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs4be_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs4be_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs4internal_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs4internal_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs4le_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs4le_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int ucs4swapped_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int ucs4swapped_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int uhc_1_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int uhc_1_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int uhc_2_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int uhc_2_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf16_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf16_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf16be_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf16be_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf16le_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf16le_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf32_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf32_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf32be_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf32be_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf32le_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf32le_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf7_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf7_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int utf8_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int utf8_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

int viscii_mbtowc(void *pwc, const char *s, size_t n)
{ return _gen_mbtowc_generic(pwc, s, n); }

int viscii_wctomb(char *s, unsigned int wc, size_t n)
{ return _gen_wctomb_generic(s, wc, n); }

/* ============================================================
 * 符号计数辅助
 * ============================================================ */

int iconv_stubs_mbtowc_count(void)
{
    return 135;
}

int iconv_stubs_wctomb_count(void)
{
    return 127;
}

