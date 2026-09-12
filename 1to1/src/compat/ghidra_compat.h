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
typedef int                 gh_code();         /* 无原型函数指针类型：gh_code * = int(*)()，可 (*p)(任意实参) 调用，返回值 r0/int，ARM32 4B 指针 */
typedef unsigned char       gh_bool;           /* Ghidra bool -> 1 字节（改名后为 gh_bool） */
/* 局部 4 字节标量的「整数 + 字节视图」（Ghidra 对同一栈槽既用 _N_4_ 又用 _N_1_ 访问） */
typedef union { gh_u4 _u32; struct { gh_u1 _0_1_, _1_1_, _2_1_, _3_1_; }; } gh_u32_bytes_t;

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

/* Ghidra 把内联 VFP 指令渲染成假函数：
   证据：AudioProcess / UIDebug / mui_outputxy_length 处汇编为 `vmov s15,r0` + `vcvt.f32.s32 s15,s15`，
   无 bl 调用，工厂符号表中不存在 VectorSignedToFloat / VectorUnsignedToFloat。
   第二实参是 FPSCR 舍入模式（Ghidra 渲染），宏按默认舍入，不保留该实参。 */
#define VectorSignedToFloat(v, ...)     ((float)(int)(v))
#define VectorUnsignedToFloat(v, ...)   ((float)(unsigned)(v))

#define CARRY4(a,b,...)    ((gh_u4)((gh_u4)(a) + (gh_u4)(b)) < (gh_u4)(a))  /* 无符号加法进位（原定义 b>a 有误，已按 ARM C 条件位改正） */
#define CARRY2(a,b,...)    ((gh_u2)((gh_u2)(a) + (gh_u2)(b)) < (gh_u2)(a))
#define CARRY1(a,b,...)    ((gh_u1)((gh_u1)(a) + (gh_u1)(b)) < (gh_u1)(a))
#define SBORROW4(a,b,...)  ((int)(((int)(a) - (int)(b)) < 0))
#define SBORROW1(a,b,...)  ((int)(((int)(a) - (int)(b)) < 0))
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

/* ============================================================
 * struct tag 兼容：glibc 只有 struct timeval / struct dirent，无裸 typedef。
 * Ghidra C 代码按 bare name（timeval/dirent）引用 → 补 typedef。
 * ============================================================ */
typedef struct timeval    timeval;
typedef struct dirent     dirent;
/* 注意：glibc 有 extern int timezone;（全局变量），故不加 typedef struct timezone timezone;
 * 代码中 timezone 局部变量须写 struct timezone */

/* glibc 内部类型名（Ghidra 按 bare name 引用）：
 *  __timezone_ptr_t = struct timezone*（gettimeofday 第 2 参，见 tsv 真实签名）
 *  __selector/__cmp = scandir 的选择/比较函数类型；__selector* 即函数指针，
 *                     与调用点 (__selector*)0x0 / alphasort 实参完全匹配 glibc。 */
typedef struct timezone *__timezone_ptr_t;
typedef int __selector (const struct dirent *);
typedef int __cmp    (const struct dirent *, const struct dirent *);

/* glibc CRT .init_array（__libc_csu_init 用 &__frame_dummy_init_array_entry 赋给 gh_undef**） */
extern gh_undef * __frame_dummy_init_array_entry;

/* TUnzip：C++ XUnzip 类的 this 指针，仅指针用 → 不完整 struct 即可 */
struct TUnzip { unsigned char _raw[0x240]; }; /* 证据：OpenZipU = operator_new(0x240) */
typedef struct TUnzip     TUnzip;

/* ZIPENTRY：XZip(XUnzip C++) 的条目描述符。唯一 _N_M_ 访问 = ze._296_4_
 * （偏移 296 的 4 字节 = 解压后尺寸，作 malloc 实参；证据：01-static 反编译
 *  全量 grep 仅此一个偏移，无其他字段访问）。用带 padding 的 union 精确
 *  表达偏移 296，_raw 覆盖到 300B（296+4）。尺寸=300B 非猜测，来自唯一访问。 */
typedef union {
    unsigned char  _raw[300];
    struct {
        unsigned char  _pad[296];
        unsigned int   _296_4_;
    };
} ZIPENTRY;
/* glibc/OpenSSL 类型（仅指针出现） */
typedef struct EVP_PKEY_CTX EVP_PKEY_CTX;
/* glibc CRT weak 钩子 _init：K&R 空原型（接受任意实参，忠实于原厂 weak void _init(void)） */
extern void _init();

/* ============================================================
 * 标量全局 blob 覆盖（方案 A · 6 个，证据：_N_M_ 访问来自 213 个函数文件）
 * 原标量声明保留；这些联合体只提供 _N_M_ 字段；成员访问通过 NAME_blob 宏指针 cast。
 * ============================================================ */

/* 8-byte double-word pair：_0_4_ @ 偏移0 · _4_4_ @ 偏移4 */
typedef struct {
    unsigned int _0_4_;
    unsigned int _4_4_;
} u64_pair_blob_t;

/* 4-byte half-word pair：_0_2_ @ 偏移0 · _2_2_ @ 偏移2 */
typedef struct {
    unsigned short _0_2_;
    unsigned short _2_2_;
} u32_pair_blob_t;

/* 指针 cast 宏：把全局标量视作 blob 联合体 */
#define frame_time_last_blob    (*(u64_pair_blob_t*)&frame_time_last)
#define progress_stepcount_blob (*(u64_pair_blob_t*)&progress_stepcount)
#define RF_joy_key_blob         (*(u64_pair_blob_t*)&RF_joy_key)
#define inTimeVal_blob          (*(u64_pair_blob_t*)&inTimeVal)
#define outTimeVal_blob         (*(u64_pair_blob_t*)&outTimeVal)
#define TimeCountReg_blob       (*(u32_pair_blob_t*)&TimeCountReg)

#endif /* GHIDRA_COMPAT_H */
