/* ============================================================
 * ghidra_compat.h — Ghidra 反编译伪代码 -> 可编译 C 的兼容层
 * 自动生成（tools/gen_compat.py），请勿手改
 * 目标：ARM32 / hard-float / ILP32（long=4B, pointer=4B）
 * ============================================================ */
#ifndef GHIDRA_COMPAT_H
#define GHIDRA_COMPAT_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <ctype.h>
#include <errno.h>
#include <math.h>
#include <time.h>
#include <signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <dirent.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/mman.h>
#include <sys/ioctl.h>

/* ---- Ghidra 私有类型 ---- */
typedef unsigned char       gh_undef;      /* 未定，按 1 字节 */
typedef unsigned char       gh_u1;
typedef unsigned short      gh_u2;
typedef unsigned int        gh_u4;
typedef unsigned long long  gh_u8;
typedef unsigned char       gh_byte;
typedef unsigned char       gh_uchar;
typedef unsigned short      gh_ushort;
typedef unsigned int        gh_uint;           /* ILP32：4 字节 */
typedef unsigned int        gh_ulong;          /* ARM32：long=4 字节 */
typedef unsigned long long  gh_ulonglong;
typedef long long           gh_longlong;
typedef void                gh_code;           /* code* -> void* */
typedef unsigned char       gh_bool;           /* Ghidra bool -> 1 字节（改名后为 gh_bool） */

/* ---- Ghidra 伪算子 ---- */
#define CONCAT11(a,b)  ((gh_u2)((((gh_u2)(a) << 8)  | (gh_u1)(b))))
#define CONCAT12(a,b)  ((gh_u4)((((gh_u4)(a) << 16) | (gh_u2)(b))))
#define CONCAT13(a,b)  ((gh_u4)((((gh_u4)(a) << 24) | ((gh_uint)(b) & 0xffffff))))
#define CONCAT22(a,b)  ((gh_u4)((((gh_u4)(a) << 16) | (gh_u2)(b))))
#define CONCAT31(a,b)  ((gh_u4)((((gh_u4)(a) << 8)  | (gh_u1)(b))))
#define CONCAT44(a,b)  ((gh_u8)((((gh_u8)(a) << 32) | (gh_u4)(b))))

#define SUB41(a,b)     ((gh_u1)((gh_u4)(a) - (gh_u4)(b)))
#define SUB42(a,b)     ((gh_u2)((gh_u4)(a) - (gh_u4)(b)))
#define SUB84(a,b)     ((gh_u4)((gh_u8)(a) - (gh_u8)(b)))
#define SUB168(a,b)    ((gh_u8)(a))

#define ZEXT12(a)      ((gh_u4)(gh_u2)(a))
#define ZEXT14(a)      ((gh_u4)(gh_u1)(a))
#define ZEXT28(a)      ((gh_u4)(gh_u2)(a))
#define ZEXT48(a)      ((gh_u8)(gh_u4)(a))
#define SEXT14(a)      ((gh_u4)(int)(signed char)(a))
#define SEXT24(a)      ((gh_u4)(int)(short)(a))
#define SEXT48(a)      ((gh_u8)(long long)(int)(a))

#define CARRY4(a,b,c)      ((gh_uint)(((gh_uint)(b) > (gh_uint)(a)) ? 1 : 0))
#define CARRY1(a,b,c)      ((gh_uint)(((gh_uint)(b) > (gh_uint)(a)) ? 1 : 0))
#define SBORROW4(a,b,c)    ((int)(((int)(a) - (int)(b)) < 0))
#define SBORROW1(a,b,c)    ((int)(((int)(a) - (int)(b)) < 0))
#define NAN(x)             (0.0f)

/* ---- Ghidra builtin 包装 ---- */
#define builtin_strncpy(d,s,n)  strncpy((char*)(d),(const char*)(s),(n))
#define builtin_strcpy(d,s)     strcpy((char*)(d),(const char*)(s))
#define builtin_strlen(s)       strlen((const char*)(s))
#define builtin_memcpy(d,s,n)   memcpy((void*)(d),(const void*)(s),(n))
#define builtin_memset(d,v,n)   memset((void*)(d),(v),(n))
#define builtin_va_list         __builtin_va_list
#define builtin_va_start(v,l)   __builtin_va_start((v),(l))
#define builtin_va_end(v)       __builtin_va_end((v))

#ifndef true
#define true  1
#define false 0
#endif

#endif /* GHIDRA_COMPAT_H */
