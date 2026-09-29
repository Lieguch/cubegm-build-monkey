/*
 * config.h —— Mini-XML v2.9 交叉编译配置（本项目用）
 *
 * ★ 为什么是 2.9（2026-09-27，P0-C 根因修复）：
 *   工厂二进制的**硬证据**把版本夹在 2.7~2.9 之间：
 *     · `mxmlDelete` 里存在 `bl <自身入口>`（真递归）⇒ **< 2.10**
 *       （2.10 为修 CVE-2016-4570 把递归改成了迭代）
 *     · 工厂**没有** `mxml_free` 静态函数（2.10 才引入）⇒ 再一次 ⇒ **< 2.10**
 *     · 工厂**没有** `mxmlElementGetAttrCount/ByIndex`、`mxmlNewOpaquef/SetOpaquef`
 *       （2.11 才引入）⇒ **< 2.11**
 *     · 工厂有 `mxmlFindPath`、`mxmlGet*` 访问器（2.7 引入）⇒ **≥ 2.7**
 *   2.7/2.8/2.9 的库本体差异只在 load 路径的 bug 修复（2.8: UTF-16 读取 / XML 片段；
 *   2.9: MXML_NO_CALLBACK / MXML_TEXT_CALLBACK 的值节点）。
 *   ⇒ 先按 2.9 落地，用 `diff_exec` 的 DIVERGE 数当判据；若 mxml 族仍有残余分歧，
 *     再退 2.8 → 2.7 二分（每一档都必须让 DIVERGE 下降，否则回退）。
 *
 * ★ 旧 pin 为什么是错的：`build_upstream.sh` 曾写「mini-XML v3.3.1（工厂 16 个静态函数
 *   全集比对）」。实测（tools/mxml_version_fingerprint.py）：**库本体静态函数名集合
 *   在 2.6 → 3.1 之间完全一致** ⇒ 那个判据**没有判别力**，不能当版本证据。
 */

/*
 * Include necessary headers...
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>
#include <unistd.h>

/*
 * Version number...
 */

#define MXML_VERSION "Mini-XML v2.9"

/*
 * Inline function support...
 */

#define inline

/*
 * Long long support...
 */

#define HAVE_LONG_LONG 1

/*
 * Do we have the snprintf() and vsnprintf() functions?
 */

#define HAVE_SNPRINTF 1
#define HAVE_VSNPRINTF 1

/*
 * Do we have the strXXX() functions?
 */

#define HAVE_STRDUP 1

/*
 * Do we have threading support?
 */

#define HAVE_PTHREAD_H 1

/*
 * Define prototypes for string functions as needed...
 */

extern char	*_mxml_strdupf(const char *, ...);
extern char	*_mxml_vstrdupf(const char *, va_list);
