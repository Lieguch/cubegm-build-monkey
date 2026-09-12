/* tchar.h — 非 UNICODE 构建的 POSIX shim（TCHAR = char）。
 * 工厂事实：.text 含 GetZipItemA（char 版），无 W-only 转换调用。 */
#ifndef XUNZIP_TCHAR_SHIM_H
#define XUNZIP_TCHAR_SHIM_H

#include <string.h>
#include <stdio.h>

#define _tcscat  strcat
#define _tcscpy  strcpy
#define _tcslen  strlen
#define _tcsncmp strncmp
#define _tcsrchr strrchr
#define _tcsstr  strstr
#define _tcsncpy strncpy
#define _tcsicmp strcasecmp
#define _tcschr  strchr
#define _stprintf sprintf
#define _tfopen  fopen
#define _T(x)    x
#define TEXT(x)  x

#endif /* XUNZIP_TCHAR_SHIM_H */
