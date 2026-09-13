#!/bin/sh
# ============================================================
# gen_compat_all.sh — 兼容层生成「全流水线」（★ 顺序不可颠倒）
#
# 血泪 ①：gen_compat.py 单独跑会把 ghidra_compat.h 写成**未改名**版本
#   （typedef unsigned int uint/ulong/ushort/uchar …），与系统头冲突，
#   且 gh_u4 等类型消失 → 4 个文件立即编译失败。
# 血泪 ②：gen_compat.py 只生成 globals.h 的**主块**。缺补丁区
#   （named_array_blobs.h include + 4 条大对象/常量兜底 + 2 条重名拆分声明）
#   会让编译通过率从 100% 崩到 48%（103/213 实测）。
#
# 完整顺序 = gen_compat → normalize_types(gh_ 前缀) → fix_ptr_globals(指针类型)
#          → patch_globals_extra(补丁区) → check_types(本地拦截)
#
# 用法: PY=python sh tools/gen_compat_all.sh
# ============================================================
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python}"

echo "== 1/5 gen_compat.py（生成 ghidra_compat.h / globals.h / proto.h 主块）"
"$PY" "$ROOT/tools/gen_compat.py"

echo "== 2/5 normalize_types.py（全部 gh_ 前缀改名；★ 必须紧跟其后）"
"$PY" "$ROOT/tools/normalize_types.py"

echo "== 3/5 fix_ptr_globals.py（指针类全局 undefined4 → void*）"
"$PY" "$ROOT/tools/fix_ptr_globals.py"

echo "== 4/5 patch_globals_extra.py（★ 补丁区：missing 会崩到 48%）"
"$PY" "$ROOT/tools/patch_globals_extra.py"

echo "== 5/5 check_types.py（本地类型门禁）"
"$PY" "$ROOT/tools/check_types.py"

echo "== 完成"
