#!/usr/bin/env python3
"""
gen_compat.py v2 — 生成「类型兼容层 + 全局声明 + 函数原型」三件套。

★ v2 关键改进：全局类型**取自 Ghidra 导出的真实类型**（ledger/ghidra_types.tsv），
   不再按尺寸猜测。v1 曾把 work_path 误判为 unsigned int[64]（真值 undefined1[256]），
   会导致 arr[i] 按 4 字节索引 -> 语义错误。

类型来源分工：
  全局符号 -> Ghidra ExportTypes.java 导出的 DATA 行（含真实 DataType 与长度）
  函数原型 -> 反编译产物 00_rkgame_ALL.c 的签名行（Ghidra 反编译器的推断签名）
"""
import os, re

DEC = r'D:/output/rkgame/decompiled'
OUT = r'D:/output/rkgame-1to1/src/compat'
ALL = os.path.join(DEC, '02-ghidra-c', '00_rkgame_ALL.c')
TSV = r'D:/output/rkgame-1to1/ledger/ghidra_types.tsv'

os.makedirs(OUT, exist_ok=True)

COMPAT = r'''/* ============================================================
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
typedef unsigned char       bool;           /* Ghidra bool -> 1 字节（改名后为 gh_bool） */

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
'''
open(os.path.join(OUT, 'ghidra_compat.h'), 'w', encoding='utf-8').write(COMPAT)
print('wrote ghidra_compat.h')

# ---------- Ghidra 类型名 -> C 类型 ----------
SCALAR = {
    'undefined1': 'unsigned char', 'undefined2': 'unsigned short',
    'undefined4': 'unsigned int', 'undefined8': 'unsigned long long',
    'undefined': 'unsigned char',
    'byte': 'unsigned char', 'uchar': 'unsigned char', 'ushort': 'unsigned short',
    'uint': 'unsigned int', 'ulong': 'unsigned int', 'ulonglong': 'unsigned long long',
    'longlong': 'long long', 'bool': 'unsigned char',
    'int': 'int', 'char': 'char', 'long': 'long', 'short': 'short',
    'size_t': 'size_t', 'ssize_t': 'long',
    'float': 'float', 'double': 'double',
    'string': 'char *', 'pointer': 'void *', 'code': 'void *',
    'void': 'void', 'term': 'void',
}
RESERVED = {'stderr', 'stdout', 'stdin', 'errno', 'environ', 'optarg',
            '_IO_stdin_used', '__stdin_used'}


def declare(name, ghidra_name, length):
    """返回完整的 C 声明（含正确的数组语法）。"""
    m = re.match(r'^(\w+)\[(\d+)\]$', ghidra_name)
    if m:
        cb = SCALAR.get(m.group(1), 'unsigned char')
        return 'extern %s %s[%s];' % (cb, name, m.group(2))
    cb = SCALAR.get(ghidra_name)
    if cb in (None, 'void'):
        if length == 1:
            cb = 'unsigned char'
        elif length == 2:
            cb = 'unsigned short'
        elif length == 4:
            cb = 'unsigned int'
        elif length == 8:
            cb = 'unsigned long long'
        else:
            return 'extern unsigned char %s[%d];' % (name, max(1, length))
    return 'extern %s %s;' % (cb, name)


# ---------- 全局声明（真实类型） ----------
glines = ['/* globals.h — 全局/静态变量声明（类型取自 Ghidra ExportTypes 导出） */',
          '#ifndef RK_GLOBALS_H', '#define RK_GLOBALS_H',
          '#include "ghidra_compat.h"', '']
n_glob = skipped = 0
declared = set()
for ln in open(TSV, encoding='utf-8', errors='replace'):
    p = ln.rstrip('\n').split('\t')
    if len(p) < 5 or p[0] != 'DATA':
        continue
    addr, name, gtype, length = p[1], p[2], p[3], p[4]
    try:
        length = int(length)
    except ValueError:
        length = 0
    if name in RESERVED or name.startswith('__') or re.match(r'^_Z', name):
        skipped += 1
        continue
    if not re.match(r'^[A-Za-z_]\w*$', name) or name in declared:
        skipped += 1
        continue
    declared.add(name)
    glines.append('/* @0x%s %s */ %s' % (addr, gtype, declare(name, gtype, length)))
    n_glob += 1
glines += ['', '/* ---- 兜底：源码引用但符号表未覆盖的 DAT_/UNK_（Ghidra 内联字面量命名） ---- */']
import glob as _glob
_refs = set()
for _p in _glob.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
    _t = open(_p, encoding='utf-8', errors='replace').read()
    _refs |= set(re.findall(r'\b((?:DAT|UNK)_[0-9a-f]+)\b', _t))
_miss = sorted(_refs - declared)
for _m in _miss:
    # 用法均为 &DAT_xxxx（取地址），声明为字节数组即可
    glines.append('/* fallback */ extern unsigned char %s[];' % _m)
print('fallback DAT_/UNK_ declarations: %d' % len(_miss))

glines += ['', '#endif']
open(os.path.join(OUT, 'globals.h'), 'w', encoding='utf-8').write('\n'.join(glines))
print('wrote globals.h (%d globals, %d skipped)' % (n_glob, skipped))

# ---------- 函数原型（反编译签名行） ----------
lines = open(ALL, encoding='utf-8', errors='replace').read().splitlines()
protos, seen = [], set()

# ★ 只声明**专有函数**：上游组件的原型（如 zlib C++ 内部的 inflate_blocks_state）
#   会引用不可用的类型，包含进来会让每个 .c 都编译失败。
import json as _json
_prop = {r['name'] for r in _json.load(
    open(r'D:/output/rkgame-1to1/ledger/functions.json', encoding='utf-8'))}
print('proprietary function names: %d' % len(_prop))

# ★ 同时声明「被专有代码实际调用」的全部函数（上游组件 API 等）。
#   证据：find_undeclared.py 显示 FindZipItemA/GetZipItemA/libiconv*/mxml*/compress 等未被声明。
import glob as _g
_CALL = re.compile(r'\b([A-Za-z_]\w*)\s*\(')
_KW = {'if', 'while', 'for', 'switch', 'return', 'sizeof', 'do', 'else', 'case', 'break',
       'continue', 'goto', 'default', 'void', 'int', 'char', 'long', 'short', 'unsigned',
       'signed', 'float', 'double', 'const', 'struct', 'union', 'enum', 'typedef', 'extern',
       'static', 'inline', 'volatile'}
_called = set()
for _p in _g.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
    _t = open(_p, encoding='utf-8', errors='replace').read()
    _t = re.sub(r'/\*.*?\*/', ' ', _t, flags=re.S)
    _t = re.sub(r'//[^\n]*', ' ', _t)
    _t = re.sub(r'"(?:[^"\\]|\\.)*"', '""', _t)
    for _m in _CALL.finditer(_t):
        _n2 = _m.group(1)
        if _n2 not in _KW and not _n2.startswith(('gh_', '__builtin', '__asm')):
            _called.add(_n2)
print('called names (from proprietary code): %d' % len(_called))
_want = _prop | _called

# 允许出现的类型词（其余视为未知类型 -> 跳过该原型）
_ALLOWED_TYPES = set(SCALAR) | {
    'void', 'int', 'char', 'long', 'short', 'float', 'double', 'unsigned', 'signed',
    'size_t', 'ssize_t', 'short', 'const', 'struct', 'union',
}
i, n = 0, len(lines)
while i < n:
    if lines[i].startswith('/* ===='):
        while i < n and '*/' not in lines[i]:
            i += 1
        i += 1
        while i < n and (not lines[i].strip() or lines[i].lstrip().startswith('/*')):
            i += 1
        if i < n:
            cand = lines[i].strip()
            m = re.match(r'^([A-Za-z_][\w \*]*?[\w\*])\s+(\*?)(\w+)\s*\((.*)\)\s*$', cand)
            if m:
                ret, star, fname, args = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
                if ' ' in ret and ret.split()[0] not in ('unsigned', 'signed', 'long', 'struct',
                                                         'union', 'const', 'volatile'):
                    ret = ret.split()[0]
                cand = '%s %s%s(%s)' % (ret, star, fname, args)
                if fname in _want and fname not in seen:
                    # 类型健全性：所有类型词必须在允许集合内
                    tnames = set(re.findall(r'\b([A-Za-z_]\w*)\b', ret + ' ' + args))
                    unknown = {x for x in tnames
                               if x not in _ALLOWED_TYPES and x != fname
                               and not x.isdigit() and not x.startswith('param_')}
                    ret_ok = (ret in _ALLOWED_TYPES) or (' ' in ret and
                                                         ret.split()[0] in _ALLOWED_TYPES)
                    if unknown and ret_ok:
                        # 参数类型不可解析 -> 用 K&R 式非原型声明（C 语言为此场景设计：
                        # 接受任意实参、保留正确返回类型）。**不是猜类型**，是显式声明"未知"。
                        seen.add(fname)
                        protos.append('extern %s %s%s(); /* K&R: 参数类型不可解析 */'
                                      % (ret, star, fname))
                    elif not unknown:
                        seen.add(fname)
                        protos.append('extern ' + cand + ';')
        continue
    i += 1

plines = ['/* proto.h — 函数原型（反编译签名行） */', '#ifndef RK_PROTO_H',
          '#define RK_PROTO_H', '#include "ghidra_compat.h"', '#include "globals.h"', '']
plines += protos
plines += ['', '#endif']
open(os.path.join(OUT, 'proto.h'), 'w', encoding='utf-8').write('\n'.join(plines))
print('wrote proto.h (%d prototypes)' % len(protos))
