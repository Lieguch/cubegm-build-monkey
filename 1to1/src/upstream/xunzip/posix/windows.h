/* windows.h — POSIX shim for Wischik zip_utils (unzip.cpp) on ARM32 Linux.
 * 1:1 移植层：只覆盖 unzip.cpp 实际用到的 API。
 *
 * ★ 类型宽度必须与工厂一致（mangled 名是指纹）：
 *   - DWORD = unsigned int   （_Z17FormatZipMessageUjPcj / _Z7lufopenPvjjPj 中是 'j'，
 *     若用 unsigned long 会错成 'm' —— Windows 上 DWORD 是 unsigned long，工厂变体改成了 uint）
 *   - WORD  = unsigned short, BOOL = int, HANDLE = void*
 *   - TCHAR = char（非 UNICODE 构建，工厂 .text 含 GetZipItemA 且符号为 char 版）
 */
#ifndef XUNZIP_WINDOWS_SHIM_H
#define XUNZIP_WINDOWS_SHIM_H

#define _POSIX_C_SOURCE 200809L

#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <time.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>

typedef unsigned int   DWORD;
typedef unsigned short WORD;
typedef unsigned char  BYTE;
typedef int            BOOL;
typedef void          *HANDLE;
typedef char           TCHAR;
typedef const TCHAR   *LPCTSTR;
typedef TCHAR         *LPTSTR;
typedef unsigned long  ULONGLONG;
typedef long           LONG;

/* windows.h DECLARE_HANDLE：HZIP = struct HZIP__*（mangled '6HZIP__' 指纹） */
#define DECLARE_HANDLE(name) struct name##__ { int unused; }; typedef struct name##__ *name

#define MAX_PATH              260
#define INVALID_HANDLE_VALUE  ((HANDLE)-1L)
#define GENERIC_READ          0x80000000U
#define GENERIC_WRITE         0x40000000U
#define FILE_SHARE_READ       0x00000001U
#define FILE_SHARE_WRITE      0x00000002U
#define OPEN_EXISTING         3
#define CREATE_ALWAYS         2
#define FILE_ATTRIBUTE_NORMAL   0x00000080U
#define FILE_ATTRIBUTE_READONLY 0x00000001U
#define FILE_ATTRIBUTE_HIDDEN   0x00000002U
#define FILE_ATTRIBUTE_SYSTEM   0x00000004U
#define FILE_ATTRIBUTE_DIRECTORY 0x00000010U
#define FILE_ATTRIBUTE_ARCHIVE  0x00000020U
#define FILE_BEGIN            0
#define FILE_CURRENT          1
#define FILE_END              2
#define FILE_TYPE_DISK        1
#define CP_ACP                0
#define TRUE                  1
#define FALSE                 0
#define DUPLICATE_SAME_ACCESS 2

typedef struct _FILETIME { DWORD dwLowDateTime; DWORD dwHighDateTime; } FILETIME;
typedef struct _SYSTEMTIME {
  WORD wYear, wMonth, wDayOfWeek, wDay, wHour, wMinute, wSecond, wMilliseconds;
} SYSTEMTIME;

/* HANDLE = int 文件描述符（字节宽 4，与 Windows HANDLE 一致） */
static inline int _wfd(HANDLE h) { return (int)(intptr_t)h; }

static inline HANDLE CreateFile(LPCTSTR fn, DWORD access, DWORD share, void *sa,
                                DWORD create, DWORD attr, void *tmpl)
{
  (void)share; (void)sa; (void)attr; (void)tmpl;
  int flags = O_RDONLY;
  if (access & GENERIC_WRITE)
    flags = (create == CREATE_ALWAYS) ? (O_WRONLY | O_CREAT | O_TRUNC) : O_WRONLY;
  int fd = open(fn, flags, 0644);
  return (fd < 0) ? INVALID_HANDLE_VALUE : (HANDLE)(intptr_t)fd;
}

static inline BOOL ReadFile(HANDLE h, void *buf, DWORD len, DWORD *red, void *ol)
{
  (void)ol;
  ssize_t r = read(_wfd(h), buf, len);
  if (red) *red = (DWORD)(r < 0 ? 0 : r);
  return r >= 0;
}

static inline BOOL WriteFile(HANDLE h, const void *buf, DWORD len, DWORD *writ, void *ol)
{
  (void)ol;
  ssize_t r = write(_wfd(h), buf, len);
  if (writ) *writ = (DWORD)(r < 0 ? 0 : r);
  return r >= 0;
}

static inline DWORD SetFilePointer(HANDLE h, LONG dist, LONG *high, DWORD whence)
{
  (void)high;
  static const int w[3] = { SEEK_SET, SEEK_CUR, SEEK_END };
  off_t r = lseek(_wfd(h), (off_t)dist, w[whence]);
  return (r == (off_t)-1) ? 0xFFFFFFFFU : (DWORD)r;
}

static inline BOOL CloseHandle(HANDLE h) { return close(_wfd(h)) == 0; }

static inline DWORD GetFileType(HANDLE h)
{
  struct stat st;
  if (fstat(_wfd(h), &st) != 0) return 0;
  return S_ISREG(st.st_mode) ? FILE_TYPE_DISK : 0; /* 管道/其它 → 不可 seek，语义同 Windows */
}

/* GetCurrentProcess/DuplicateHandle：rkgame 只走 ZIP_FILENAME 路径；dup() 保持语义 */
static inline HANDLE GetCurrentProcess(void) { return (HANDLE)1; }
static inline BOOL DuplicateHandle(HANDLE sp, HANDLE src, HANDLE dp, HANDLE *dst,
                                   DWORD acc, BOOL inh, DWORD opt)
{
  (void)sp; (void)dp; (void)acc; (void)inh; (void)opt;
  int n = dup(_wfd(src));
  if (n < 0) return FALSE;
  *dst = (HANDLE)(intptr_t)n;
  return TRUE;
}

static inline DWORD GetCurrentDirectory(DWORD n, LPTSTR buf)
{
  return getcwd(buf, n) ? (DWORD)strlen(buf) : 0;
}

/* ---- 时间：FILETIME = 100ns since 1601-01-01（Windows 语义，可观察行为=文件时间戳）---- */
#define WINFT_EPOCH_DIFF 11644473600ULL   /* 1601→1970 秒差 */

static inline void _unix_to_ft(unsigned long long sec, FILETIME *ft)
{
  unsigned long long t = (sec + WINFT_EPOCH_DIFF) * 10000000ULL;
  ft->dwLowDateTime  = (DWORD)(t & 0xFFFFFFFFU);
  ft->dwHighDateTime = (DWORD)(t >> 32);
}
static inline unsigned long long _ft_to_unix(const FILETIME *ft)
{
  unsigned long long t = ((unsigned long long)ft->dwHighDateTime << 32) | ft->dwLowDateTime;
  return t / 10000000ULL - WINFT_EPOCH_DIFF;
}

static inline BOOL SystemTimeToFileTime(const SYSTEMTIME *st, FILETIME *ft)
{
  /* days-from-civil（Howard Hinnant 算法） */
  long y = st->wYear, m = st->wMonth;
  y -= m <= 2;
  long era = (y >= 0 ? y : y - 399) / 400;
  unsigned long yoe = (unsigned long)(y - era * 400);
  unsigned long doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + st->wDay - 1;
  unsigned long doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
  long days = era * 146097 + (long)doe - 719468;
  unsigned long long sec = (unsigned long long)days * 86400ULL
                         + st->wHour * 3600ULL + st->wMinute * 60ULL + st->wSecond;
  _unix_to_ft(sec, ft);
  return TRUE;
}

static inline BOOL DosDateTimeToFileTime(WORD dosdate, WORD dostime, FILETIME *ft)
{
  unsigned long day  = (dosdate >> 5) & 0x1F;
  unsigned long mon  = ((dosdate >> 8) & 0x0F); if (mon < 1) mon = 1;
  unsigned long year = 1980 + ((dosdate >> 9) & 0x7F);
  SYSTEMTIME st;
  st.wYear = (WORD)year; st.wMonth = (WORD)mon; st.wDay = (WORD)day;
  st.wHour = (WORD)((dostime >> 11) & 0x1F); st.wMinute = (WORD)((dostime >> 5) & 0x3F);
  st.wSecond = (WORD)((dostime & 0x1F) * 2); st.wMilliseconds = 0; st.wDayOfWeek = 0;
  return SystemTimeToFileTime(&st, ft);
}

#include <sys/stat.h>
/* musl 特性宏差异：直接声明，避免依赖特性宏开关 */
extern "C" int futimens(int fd, const struct timespec times[2]);

static inline BOOL CreateDirectory(LPCTSTR fn, void *sa)
{ (void)sa; return ::mkdir(fn, (mode_t)0777) == 0; }

static inline void ZeroMemory(void *p, DWORD n) { memset(p, 0, n); }

static inline BOOL SetFileTime(HANDLE h, const FILETIME *ct, const FILETIME *at, const FILETIME *mt)
{
  struct timespec ts[2];
  unsigned long long a = _ft_to_unix(at), m = _ft_to_unix(mt);
  ts[0].tv_sec = (time_t)a; ts[0].tv_nsec = 0;
  ts[1].tv_sec = (time_t)m; ts[1].tv_nsec = 0;
  return futimens(_wfd(h), ts) == 0;
}

#endif /* XUNZIP_WINDOWS_SHIM_H */
