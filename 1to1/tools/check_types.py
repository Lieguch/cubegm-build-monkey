#!/usr/bin/env python3
"""
check_types.py — 生成物「类型可解析性」本地自检。

目的：终止「改一处 -> 推一次 -> CI 报下一个错」的往返试错。
     在本地就把 headers 里所有类型 token 校验一遍，未解析的立即报出。

校验对象：src/compat/ghidra_compat.h / globals.h / proto.h
判定：声明中出现的每个类型 token 必须属于
      ① gh_* typedef ② 标准 C 类型 ③ 已知 struct/union 标签 ④ 参数名/函数名
用法: python tools/check_types.py
"""
import os, re, sys

# ★ 2026-09-24：原先是硬编码本机路径 `D:/output/rkgame-1to1/src/compat`，而下面两个循环
#   都是 `if not os.path.exists(p): continue` ⇒ 在 **CI 上三个文件全不在** ⇒ 校验集合为空
#   ⇒ 输出 0 问题 ⇒ 该步骤在 CI 里**看起来 PASS、其实什么都没查**（实测：CI run 35954789674
#   的“类型可解析性自检”步骤 success，而它扫了 0 个文件）。
#   同类病见 GAP 16.86/16.87 与 `scan_call_args.py` 的 `[SKIP] … return 0`。
#   修法：① 路径从 `__file__` 推（仓内自洽，本地/CI 同解）；② **先做存在性硬失败**。
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'compat')
FILES = ['ghidra_compat.h', 'globals.h', 'proto.h']
_missing = [f for f in FILES if not os.path.exists(os.path.join(ROOT, f))]
if _missing:
    sys.stderr.write('★ 校验对象缺失 %s：%s\n  本自检**不做静默跳过**（跳过 = 假绿 ⇒ 看起来 PASS 其实没查）。\n'
                     % (ROOT, _missing))
    sys.exit(2)

STD = {
    'void', 'int', 'char', 'short', 'long', 'float', 'double', 'unsigned', 'signed',
    'size_t', 'ssize_t', 'const', 'volatile', 'struct', 'union', 'enum', 'void',
    'FILE', 'time_t', 'pthread_t', 'va_list', '__gnuc_va_list', 'bool', '_Bool',
    'int8_t', 'int16_t', 'int32_t', 'int64_t', 'uint8_t', 'uint16_t', 'uint32_t',
    'uint64_t', 'intptr_t', 'uintptr_t', 'ptrdiff_t', 'wchar_t', 'mode_t', 'off_t',
    'sig_atomic_t', 'clock_t', 'DIR', 'struct_timeval', 'tm', 'tm_unz_s', 'unz_s',
    'unz_file_info_s', 'unz_file_info_internal_s', 'unz_global_info_s', 'ZIPENTRY',
    'ZIPENTRYW', 'HZIP__', 'inflate_huft_s', 'z_stream_s', 'inflate_blocks_state',
    'inflate_codes_state', 'pthread_attr_t', '__int32_t', '__timezone_ptr_t',
    'longlong', 'ulonglong', 'code', 'byte', 'uint', 'ulong', 'ushort', 'uchar',
    'undefined', 'undefined1', 'undefined2', 'undefined4', 'undefined8',
}

# 自己 typedef 出来的名字
defined = set()
for f in FILES:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        continue
    t = open(p, encoding='utf-8', errors='replace').read()
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    for m in re.finditer(r'typedef\s+[\w\s\*]+?\s+(\w+)\s*;', t):
        defined.add(m.group(1))
    # 多行 struct/union typedef： "... } NAME ;"
    for m in re.finditer(r'\}\s*(\w+)\s*;', t):
        defined.add(m.group(1))

KNOWN = STD | defined

# 收集所有声明行里的类型 token（去掉函数名与参数名）
unresolved = {}
for f in FILES:
    p = os.path.join(ROOT, f)
    if not os.path.exists(p):
        continue
    for ln in open(p, encoding='utf-8', errors='replace'):
        s = re.sub(r'/\*.*?\*/', ' ', ln)      # 剥行内块注释
        s = re.sub(r'//.*$', ' ', s)           # 剥行注释
        s = s.strip()
        if not s.startswith(('extern', 'typedef')):
            continue
        # 去掉函数名与参数名：形如 "<type> name(" / "<type> name;"
        body = re.sub(r'\([^)]*\)', '()', s)          # 参数表整体折叠
        body = re.sub(r'\b(param_\d+)\b', '', body)
        body = body.replace('extern', ' ').replace('typedef', ' ')
        body = re.sub(r'\[[^\]]*\]', '', body)
        body = re.sub(r'[;\(\),]', ' ', body)
        body = body.replace('*', ' ')
        toks = body.split()
        if len(toks) >= 1:
            # 最后一个 token 是变量/函数名，其余是类型
            for tok in toks[:-1] if len(toks) > 1 else toks:
                if tok in KNOWN or tok.isdigit():
                    continue
                unresolved.setdefault(tok, []).append('%s: %s' % (f, s[:90]))

print('typedef 定义: %d 个' % len(defined))
print('未解析类型 token: %d 个' % len(unresolved))
for tok, where in sorted(unresolved.items(), key=lambda x: -len(x[1]))[:30]:
    print('  %-28s x%-4d  例: %s' % (tok, len(where), where[0][:70]))
sys.exit(1 if unresolved else 0)
