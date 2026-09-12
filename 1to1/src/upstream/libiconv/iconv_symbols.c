/* ============================================================
 * iconv_symbols.c — libiconv 关键符号（对齐原厂 §2.1）
 * ============================================================
 *
 * 原厂 libiconv 关键符号（Ghidra 反编译实证）：
 *   - gbk_mbtowc / gbk_wctomb         - GBK 字节/宽字符互转
 *   - big5_mbtowc / big5_wctomb       - Big5 字节/宽字符互转
 *   - jisx0208_mbtowc / wctomb        - JIS X 0208
 *   - cns11643_mbtowc / wctomb        - CNS 11643（繁体）
 *   - all_encodings (2.3 KB 表)       - 所有编码清单
 *   - unicode_transliterate (2.1 KB)  - Unicode 转写
 *
 * 本实现：提供同名公开符号，内部调用简化转换。
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <stddef.h>

#ifdef _WIN32
typedef unsigned int wchar_t_alias;
#else
#include <wchar.h>
#endif

/* ============================================================
 * 注意：gbk_mbtowc/wctomb, big5_mbtowc/wctomb, jisx0208_mbtowc/wctomb,
 * cns11643_mbtowc/wctomb 等函数已移至 iconv_real.c
 * 使用官方 libiconv 1.19 源码实现（53,113 行真实转换表）
 * ============================================================ */

/* ============================================================
 * all_encodings — 编码清单表（原厂 2.3 KB）
 * ============================================================ */

typedef struct {
    const char *name;
    const char *category;
    int         is_ascii_compat;
} encoding_entry_t;

const encoding_entry_t all_encodings[] = {
    /* 欧洲 */
    {"ASCII",        "european",  1},
    {"ISO-8859-1",   "european",  1},
    {"ISO-8859-2",   "european",  1},
    {"ISO-8859-3",   "european",  1},
    {"ISO-8859-4",   "european",  1},
    {"ISO-8859-5",   "european",  1},
    {"ISO-8859-7",   "european",  1},
    {"ISO-8859-9",   "european",  1},
    {"ISO-8859-10",  "european",  1},
    {"ISO-8859-13",  "european",  1},
    {"ISO-8859-14",  "european",  1},
    {"ISO-8859-15",  "european",  1},
    {"ISO-8859-16",  "european",  1},
    {"KOI8-R",       "european",  0},
    {"KOI8-U",       "european",  0},
    {"KOI8-RU",      "european",  0},
    {"KOI8-T",       "european",  0},
    {"CP1250",       "european",  1},
    {"CP1251",       "european",  1},
    {"CP1252",       "european",  1},
    {"CP1253",       "european",  1},
    {"CP1254",       "european",  1},
    {"CP1257",       "european",  1},
    {"MacRoman",     "european",  1},
    {"MacCyrillic",  "european",  0},
    {"MacGreek",     "european",  1},
    {"MacTurkish",   "european",  1},
    /* 中东 */
    {"ISO-8859-6",   "semitic",   1},
    {"ISO-8859-8",   "semitic",   1},
    {"CP1255",       "semitic",   1},
    {"CP1256",       "semitic",   1},
    {"MacHebrew",    "semitic",   1},
    {"MacArabic",    "semitic",   1},
    /* 日文 */
    {"EUC-JP",       "japanese",  0},
    {"SHIFT_JIS",    "japanese",  0},
    {"CP932",        "japanese",  0},
    {"ISO-2022-JP",  "japanese",  0},
    /* 中文 */
    {"EUC-CN",       "chinese",   0},
    {"HZ",           "chinese",   0},
    {"GBK",          "chinese",   0},
    {"GB18030",      "chinese",   0},
    {"CP936",        "chinese",   0},
    {"EUC-TW",       "chinese",   0},
    {"BIG5",         "chinese",   0},
    {"CP950",        "chinese",   0},
    {"BIG5-HKSCS",   "chinese",   0},
    /* 韩文 */
    {"EUC-KR",       "korean",    0},
    {"CP949",        "korean",    0},
    {"ISO-2022-KR",  "korean",    0},
    /* 亚非 */
    {"TIS-620",      "thai",      1},
    {"MacThai",      "thai",      1},
    {"VISCII",       "vietnamese",1},
    {"TCVN",         "vietnamese",0},
    {"CP1258",       "vietnamese",1},
    {"ARMSCII-8",    "armenian",  0},
    {"Georgian-Academy", "georgian", 0},
    {"Georgian-PS",    "georgian", 0},
    {"PT154",        "kazakh",    0},
    {"RK1048",       "kazakh",    0},
    /* 平台 */
    {"HP-ROMAN8",    "platform",  1},
    {"NEXTSTEP",     "platform",  0},
    {"RISCOS-LATIN1","platform",  1},
    /* Unicode */
    {"UTF-8",        "unicode",   1},
    {"UTF-16",       "unicode",   0},
    {"UTF-16LE",     "unicode",   0},
    {"UTF-16BE",     "unicode",   0},
    {"UTF-32",       "unicode",   0},
    {"UCS-2",        "unicode",   0},
    {"UCS-4",        "unicode",   0},
    {"UTF-7",        "unicode",   1},
    {NULL, NULL, 0}
};

#define ALL_ENCODINGS_COUNT ((sizeof(all_encodings) - sizeof(all_encodings[0])) / sizeof(all_encodings[0]))

const char *find_encoding_by_name(const char *name)
{
    if (!name) return NULL;
    for (size_t i = 0; all_encodings[i].name; i++) {
        if (strcasecmp(all_encodings[i].name, name) == 0)
            return all_encodings[i].category;
    }
    return NULL;
}

size_t all_encodings_count(void)
{
    return ALL_ENCODINGS_COUNT;
}

/* ============================================================
 * unicode_transliterate — Unicode 转写（原厂 2.1 KB）
 * ============================================================
 * 把不可表示的 Unicode 字符近似为 ASCII 字符。
 * 本实现：常见 CJK 拼音/假名近似 + 其他走 '?'。
 * ============================================================ */

size_t unicode_transliterate(unsigned int codepoint, char *out, size_t outsz)
{
    if (!out || outsz < 1) return 0;
    out[0] = '\0';

    /* ASCII 直接透传 */
    if (codepoint < 0x80) {
        out[0] = (char)codepoint;
        out[1] = '\0';
        return 1;
    }

    /* Latin 扩展 (0x00C0-0x024F) 转写为 ASCII */
    if (codepoint >= 0x00C0 && codepoint <= 0x00FF) {
        static const char *latin1_map[] = {
            "A", "A", "A", "A", "A", "A", "AE", "C", "E", "E", "E", "E", "I", "I", "I", "I",
            "D", "N", "O", "O", "O", "O", "O", "OE", "U", "U", "U", "U", "U", "U", "U", "Y",
            "a", "a", "a", "a", "a", "a", "ae", "c", "e", "e", "e", "e", "i", "i", "i", "i",
            "d", "n", "o", "o", "o", "o", "o", "oe", "u", "u", "u", "u", "u", "u", "u", "y",
            "?", "ss", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?", "?"
        };
        size_t n = strlen(latin1_map[codepoint - 0x00C0]);
        if (n + 1 > outsz) n = outsz - 1;
        memcpy(out, latin1_map[codepoint - 0x00C0], n);
        out[n] = '\0';
        return n;
    }

    /* CJK 常用汉字拼音（简化：常见 20 个字） */
    if (codepoint >= 0x4E00 && codepoint <= 0x4E20) {
        static const char *cjk_map[] = {
            "yi", "wu", "zhong", "zhong", "er", "shu", "san", "si",
            "wu", "liu", "qi", "ba", "jiu", "shi", "ren", "yue",
            "tian", "di", "ren", "he", "zi", "yang", "nu", "yin",
            "jin", "guo", "qu", "lai"
        };
        size_t n = strlen(cjk_map[codepoint - 0x4E00]);
        if (n + 1 > outsz) n = outsz - 1;
        memcpy(out, cjk_map[codepoint - 0x4E00], n);
        out[n] = '\0';
        return n;
    }

    /* 日文假名（简化） */
    if (codepoint >= 0x3041 && codepoint <= 0x309F) {
        /* Hiragana → romanization (ka, ki, ku...) */
        static const char *hiragana_map[] = {
            "a", "i", "u", "e", "o", "ka", "ki", "ku", "ke", "ko",
            "sa", "shi", "su", "se", "so", "ta", "chi", "tsu", "te", "to",
            "na", "ni", "nu", "ne", "no", "ha", "hi", "fu", "he", "ho",
            "ma", "mi", "mu", "me", "mo", "ya", "yu", "yo", "ra", "ri",
            "ru", "re", "ro", "wa", "wo", "-", "n", "-", "-"
        };
        unsigned int idx = codepoint - 0x3041;
        if (idx < 46) {
            size_t n = strlen(hiragana_map[idx]);
            if (n + 1 > outsz) n = outsz - 1;
            memcpy(out, hiragana_map[idx], n);
            out[n] = '\0';
            return n;
        }
    }

    /* 默认走 '?' */
    out[0] = '?';
    out[1] = '\0';
    return 1;
}
