/* config.h — libiconv 1.17 目标侧最小配置（ARM32 Linux / musl+glibc 通用）
 * 说明：GNU libiconv 的 configure 会生成完整 config.h；此处仅提供 icov.c 与
 * converters.h 实际引用的宏。未定义的宏 = 关闭对应可选分支（AIX/OSF1/ZOS/EXTRA 等）。
 */
#ifndef LIBCONV_CONFIG_H
#define LIBCONV_CONFIG_H

#define PACKAGE "libiconv"
#define VERSION "1.17"

/* 运行时能力（Linux 均有） */
#define HAVE_UNISTD_H 1
#define HAVE_ALLOCA 1
#define HAVE_MBRTOWC 1
#define HAVE_WCRTOMB 1
#define HAVE_MBSINIT 1
#define HAVE_MBSRTOWCS 1
#define HAVE_WCSRTOMBS 1
#define HAVE_PTHREAD 1

/* 关键：本体重就是 libiconv 实现，禁用系统 iconv 转发 */
#define HAVE_ICONV 0

/* 不启用二进制重定位（避免 libcharset/relocatable 依赖） */
#define ENABLE_RELOCATABLE 0

/* ★★ 由**工厂二进制取证**反推的 configure 事实（2026-09-27，纪律 26/27）
 *   判据不是"猜测"，而是**工厂动态导入符号表**（113 个，权威、可复算）：
 *     · 工厂导入 `nl_langinfo`、**不导入 `getenv`** ⇒ localcharset.c 走 `nl_langinfo(CODESET)` 分支
 *       ⇒ `HAVE_LANGINFO_CODESET` **必须为 1**。
 *     · 实测反证：未定义时 `#if HAVE_LANGINFO_CODESET` 判 0 ⇒ 我方 localcharset.o 引用 `getenv`
 *       （`locale_charset` 一行分歧 `calls_ext F=['nl_langinfo'] O=['getenv','getenv','getenv']`）。
 *   ★ 纪律 27 提醒：**不许**用"我们自己的产物"当工厂事实来源；此处的来源是 golden/factory.rkgame.bin。
 */
#define HAVE_LANGINFO_CODESET 1

/* 由 configure 生成的关键宏（config.h.in 权威值） */
#define ICONV_CONST /* empty by default */

#endif /* LIBCONV_CONFIG_H */
