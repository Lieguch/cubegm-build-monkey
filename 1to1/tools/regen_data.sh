#!/bin/sh
# ============================================================
# regen_data.sh — 重新生成工厂数据镜像 + 别名 + 链接脚本
#
# 依赖 audit 产物 report/_link_syms.tsv（我们的 .o + 上游 .o 的符号表）。
# 顺序很重要：
#   1) 从 _link_syms.tsv 取「全量 UNDEF 名单」→ 作为 gen_data_module 的 --missing
#      （★ 必须用全量 UNDEF，不能用「分类后的 MISSING」，否则会丢别名：
#        曾因用 17 条的 MISSING 重生成，导致 934 个别名退化成 17 个）
#   2) gen_data_module.py  → factory_image.S（工厂字节镜像 + g/l 别名）+ factory_*.bin + factory.ld
#   3) gen_local_alias.py  → factory_local.S（镜像未覆盖的局部数据对象 + crc_table）
#      ★ 该步会自动跳过 factory_image.S 已别名的符号，避免重复定义
#
# 用法: PY=... sh tools/regen_data.sh
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python}"
ELF="${FACTORY_ELF:-D:/output/rkgame/rkgame}"
SYMTAB="${FACTORY_SYMTAB:-D:/output/rkgame/decompiled/01-static/symtab.txt}"
SYMS="$ROOT/report/_link_syms.tsv"

winpath() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}

if [ ! -f "$SYMS" ]; then
    echo "缺 $SYMS —— 请先跑 tools/link_audit.sh"
    exit 1
fi

awk -F'\t' '$1=="UNDEF"{print $2}' "$SYMS" | sort -u > "$ROOT/report/_undef_all.txt"
echo "== 全量 UNDEF: $(wc -l < "$ROOT/report/_undef_all.txt") 个 =="

$PY "$(winpath "$ROOT/tools/gen_data_module.py")" \
    --elf "$ELF" \
    --layout "$(winpath "$ROOT/ledger/factory_layout.tsv")" \
    --globals "$(winpath "$ROOT/ledger/factory_globals.tsv")" \
    --missing "$(winpath "$ROOT/report/_undef_all.txt")" \
    --outdir "$(winpath "$ROOT")"

$PY "$(winpath "$ROOT/tools/gen_local_alias.py")" \
    "$SYMTAB" "$(winpath "$SYMS")" \
    "$(winpath "$ROOT/ledger/factory_layout.tsv")" \
    "$(winpath "$ROOT/src/data/factory_local.S")"

n_img=$(grep -cE "\.set [A-Za-z_]" "$ROOT/src/data/factory_image.S" 2>/dev/null || echo 0)
n_loc=$(grep -cE "\.set [A-Za-z_]" "$ROOT/src/data/factory_local.S" 2>/dev/null || echo 0)
echo "== 别名: factory_image.S $n_img 个 / factory_local.S $n_loc 个 =="
