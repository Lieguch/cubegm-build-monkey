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

# ---------- 匿名 blob 覆盖类型（Ghidra _N_M_ 字段访问） ----------
# 事实（取自源码实测）：_N_M_ 表示「偏移 N 字节、宽 M 字节」的字段；实测只用 M∈{1,4}，
# 且所有 M=4 字段的 N 均为 4 的倍数。故可精确构造：
#   每个 4 字节槽 S 放一个 union{ 匿名struct{_S_1_,_S+1_1_,_S+2_1_,_S+3_1_} ; unsigned int _S_4_ }
# C11 允许匿名 struct 提升成员名，故 X._8_4_ / X._9_1_ 均能正确解析到真实偏移。
import re as _re
import glob as _g2
_pairs = set()
_owners = {}
for _p in _g2.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
    _t = open(_p, encoding='utf-8', errors='replace').read()
    for _m in _re.finditer(r'\b([A-Za-z_]\w*)\s*\.\s*_(\d+)_(\d+)_', _t):
        _owners.setdefault(_m.group(1), set()).add((int(_m.group(2)), int(_m.group(3))))
        _pairs.add((int(_m.group(2)), int(_m.group(3))))
if _pairs:
    _maxoff = max(n + m for n, m in _pairs)
    _slots = (_maxoff + 3) // 4
    _l = ['', '/* ---- 匿名 blob 覆盖类型：Ghidra _N_M_ 字段访问（偏移 N、宽 M） ---- */',
          'typedef struct {']
    for _s in range(_slots):
        _b = _s * 4
        _l.append('    union {')
        _l.append('        struct { unsigned char _%d_1_, _%d_1_, _%d_1_, _%d_1_; };'
                  % (_b, _b + 1, _b + 2, _b + 3))
        _l.append('        unsigned int _%d_4_;' % _b)
        _l.append('    };')
    _l.append('} gh_blob_t;')
    # ★ 必须插在**全局声明之前**（否则使用点在定义之前 -> unknown type name）
    glines[4:4] = _l
    print('gh_blob_t: 定义已插入第 4 行前; slots=%d, 覆盖 %d 个字段引用, 涉及 %d 个对象'
          % (_slots, len(_pairs), len(_owners)))

    # 被以上述方式访问的全局/对象，改用 gh_blob_t 声明
    _need_retype = {k for k in _owners
                    if k not in ('param_1', 'param_2', 'param_3', 'param_4', 'param_5',
                                 'param_6', 'param_7', 'param_8', 'param_9', 'param_10')
                    and not k.startswith(('uVar', 'iVar', 'cVar', 'bVar', 'pVar', 'local_',
                                          'acStack_', 'auStack_', 'aStack_', 'uStack_', 'iStack_',
                                          'pStack_', 'fStack_', 'sStack_'))}
    # 过滤：只对「仅以 ._N_M_ 访问、未被当数组下标」的对象重定型，避免引入新破坏
    _arraylike = set()
    for _p in _g2.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
        _t = open(_p, encoding='utf-8', errors='replace').read()
        for _m in _re.finditer(r'\b([A-Za-z_]\w*)\s*\[', _t):
            _arraylike.add(_m.group(1))
        # 取址/整体使用也视为不可重定型
        for _m in _re.finditer(r'&\s*([A-Za-z_]\w*)\b', _t):
            _arraylike.add(_m.group(1))
    _need_retype = {k for k in _owners
                    if k not in _arraylike
                    and not k.startswith(('param_', 'uVar', 'iVar', 'cVar', 'bVar', 'pVar',
                                          'local_', 'acStack_', 'auStack_', 'aStack_',
                                          'uStack_', 'iStack_', 'pStack_', 'fStack_', 'sStack_'))}
    _gl_out = []
    _n_ret = 0
    _re_extern = _re.compile(r'extern\s+[\w\s\*]+?\s+\*?(\w+)\s*(\[[^\]]*\])?\s*;')
    for _ln in glines:
        _mm2 = _re_extern.search(_ln)
        if _mm2 and _mm2.group(1) in _need_retype:
            # 注意：不得把原声明（含 /* */）嵌进注释 —— C 注释不嵌套
            _gl_out.append('extern gh_blob_t %s;  /* retyped: Ghidra _N_M_ 字段访问 */'
                           % _mm2.group(1))
            _n_ret += 1
        else:
            _gl_out.append(_ln)
    glines = _gl_out
    print('retyped to gh_blob_t: %d (候选 %d, 因数组/取址用法排除 %d)'
          % (_n_ret, len(_owners), len(_owners) - len(_need_retype)))

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

# ★ 取证：调用点的**实参个数**与**值用法**（用于判定原型是否可信、返回类型是否必须非 void）
def _scan_calls(text):
    """返回 (arity_by_name, value_used_names)。括号配平，非经验猜测。"""
    arity, val = {}, set()
    for m in re.finditer(r'([=(\[,]|return\s+|\b)\s*([A-Za-z_]\w*)\s*\(', text):
        pre, name = m.group(1), m.group(2)
        if name in _KW or name.startswith(('gh_', '__builtin', '__asm')):
            continue
        i = m.end()
        depth, args, buf, n = 1, 0, '', len(text)
        while i < n and depth > 0:
            c = text[i]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    if buf.strip():
                        args += 1
                    break
            elif c == ',' and depth == 1:
                args += 1
                buf = ''
                i += 1
                continue
            buf += c
            i += 1
        arity.setdefault(name, set()).add(args)
        if pre in ('=', '[') or pre.startswith('return') or pre == '(':
            # '(' 前缀也可能是类型转换，保守只认 = 与 return
            if pre in ('=', '[') or pre.startswith('return'):
                val.add(name)
    return arity, val


_ARITY, _VALUE_USED = {}, set()
for _p in _g.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
    _t = open(_p, encoding='utf-8', errors='replace').read()
    _t = re.sub(r'/\*.*?\*/', ' ', _t, flags=re.S)
    _t = re.sub(r'//[^\n]*', ' ', _t)
    _t = re.sub(r'"(?:[^"\\]|\\.)*"', '""', _t)
    _a, _v = _scan_calls(_t)
    for _k, _s in _a.items():
        _ARITY.setdefault(_k, set()).update(_s)
    _VALUE_USED |= _v

# 函数体是否出现 return 非空值
_BODY_VALRET = set()
for _p in _g.glob(r'D:/output/rkgame-1to1/src/proprietary/*/*.c'):
    _t = open(_p, encoding='utf-8', errors='replace').read()
    _t = re.sub(r'/\*.*?\*/', ' ', _t, flags=re.S)
    _mm = re.search(r'\b(\w+)\s*\([^;]*\)\s*\{\s*(.*)$', _t, re.S)
    if _mm and re.search(r'\breturn\s+[^;]+;', _mm.group(2)):
        _BODY_VALRET.add(_mm.group(1))
print('arity info: %d names; value-used: %d; body-value-return: %d'
      % (len(_ARITY), len(_VALUE_USED), len(_BODY_VALRET)))

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
                    # ① 返回类型：声明 void 但「被当作值使用」或「体内 return 值」-> 必须非 void
                    ret_fixed = ret
                    if 'void' in ret and (fname in _VALUE_USED or fname in _BODY_VALRET):
                        ret_fixed = 'undefined4'

                    # ② 参数：调用点实参数与声明参数数不符 -> K&R 非原型声明（显式声明"参数未知"）
                    _a = args.strip()
                    decl_n = 0 if _a in ('void', '') else _a.count(',') + 1
                    call_ar = _ARITY.get(fname, set())
                    kr = False
                    if call_ar and (decl_n not in call_ar or len(call_ar) > 1):
                        kr = True

                    # ③ 类型健全性：类型词必须在允许集合内
                    tnames = set(re.findall(r'\b([A-Za-z_]\w*)\b', ret_fixed + ' ' + args))
                    unknown = {x for x in tnames
                               if x not in _ALLOWED_TYPES and x != fname
                               and not x.isdigit() and not x.startswith('param_')}
                    if unknown:
                        kr = True

                    seen.add(fname)
                    if kr:
                        protos.append('extern %s %s%s(); /* K&R: 参数不可信/不可解析 */'
                                      % (ret_fixed, star, fname))
                    else:
                        protos.append('extern %s %s%s(%s);' % (ret_fixed, star, fname, args))
        continue
    i += 1

plines = ['/* proto.h — 函数原型（反编译签名行） */', '#ifndef RK_PROTO_H',
          '#define RK_PROTO_H', '#include "ghidra_compat.h"', '#include "globals.h"', '']
plines += protos
plines += ['', '#endif']
open(os.path.join(OUT, 'proto.h'), 'w', encoding='utf-8').write('\n'.join(plines))
print('wrote proto.h (%d prototypes)' % len(protos))
