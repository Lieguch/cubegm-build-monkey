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

/* ---- Ghidra 私有类型 ---- */
typedef unsigned char       undefined;      /* 未定，按 1 字节 */
typedef unsigned char       undefined1;
typedef unsigned short      undefined2;
typedef unsigned int        undefined4;
typedef unsigned long long  undefined8;
typedef unsigned char       byte;
typedef unsigned char       uchar;
typedef unsigned short      ushort;
typedef unsigned int        uint;           /* ILP32：4 字节 */
typedef unsigned int        ulong;          /* ARM32：long=4 字节 */
typedef unsigned long long  ulonglong;
typedef long long           longlong;
typedef void                code;           /* code* -> void* */

/* ---- Ghidra 伪算子 ---- */
#define CONCAT11(a,b)  ((undefined2)((((undefined2)(a) << 8)  | (undefined1)(b))))
#define CONCAT12(a,b)  ((undefined4)((((undefined4)(a) << 16) | (undefined2)(b))))
#define CONCAT13(a,b)  ((undefined4)((((undefined4)(a) << 24) | ((uint)(b) & 0xffffff))))
#define CONCAT22(a,b)  ((undefined4)((((undefined4)(a) << 16) | (undefined2)(b))))
#define CONCAT31(a,b)  ((undefined4)((((undefined4)(a) << 8)  | (undefined1)(b))))
#define CONCAT44(a,b)  ((undefined8)((((undefined8)(a) << 32) | (undefined4)(b))))

#define SUB41(a,b)     ((undefined1)((undefined4)(a) - (undefined4)(b)))
#define SUB42(a,b)     ((undefined2)((undefined4)(a) - (undefined4)(b)))
#define SUB84(a,b)     ((undefined4)((undefined8)(a) - (undefined8)(b)))
#define SUB168(a,b)    ((undefined8)(a))

#define ZEXT12(a)      ((undefined4)(undefined2)(a))
#define ZEXT14(a)      ((undefined4)(undefined1)(a))
#define ZEXT28(a)      ((undefined4)(undefined2)(a))
#define ZEXT48(a)      ((undefined8)(undefined4)(a))
#define SEXT14(a)      ((undefined4)(int)(signed char)(a))
#define SEXT24(a)      ((undefined4)(int)(short)(a))
#define SEXT48(a)      ((undefined8)(long long)(int)(a))

#define CARRY4(a,b,c)      ((uint)(((uint)(b) > (uint)(a)) ? 1 : 0))
#define CARRY1(a,b,c)      ((uint)(((uint)(b) > (uint)(a)) ? 1 : 0))
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
