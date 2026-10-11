#!/bin/sh
# =============================================================================
# driver_stub_elf_gate.sh —— 假桩门禁的**产物级第三腿**（第 163 轮新增）。
#
# 为什么需要它
#   driver_stub_coverage.py 的源级判据（符号名出现在桩源文本里）只能证明"写了"，
#   不能证明"编译器/链接器真把它导出成了动态符号"。本脚本在**有 armhf 交叉编译器**
#   的环境（CNB 云开发 / GitHub Actions）里把桩真正编译成 DSO，再对**产物的 .dynsym**
#   断覆盖，并造一个**反例**证明判据有判别力。
#
# 三腿（judging-tool-self-test 的自证要求）
#   腿1 真桩源            → 必须 PASS
#   腿2 删一个符号的桩源   → 必须 FAIL 且点名
#   腿3 真桩产物           → 必须 PASS（对**编出来的 DSO 的 .dynsym** 断覆盖）
#   腿4 反例（判别力）     → 4a 少给一个桩产品 ⇒ 必须 FAIL 且点名；
#                          4b objcopy --localize-dynamic-symbol 抹单个符号 ⇒ 必须 FAIL 且点名
#   ★ 踩坑（2026-10-07）：objcopy --localize-symbol 只改 .symtab，**不改 .dynsym**
#     ⇒ 抹完门禁仍 PASS（假绿）。动态符号必须用 --localize-dynamic-symbol
#     （binutils>=2.39；旧版只走 4a）。
#
# ★ 本机（Windows）没有 armhf 编译链时**不要**硬跑：产物会是错的架构，
#   driver_stub_coverage.py 的 EM_ARM 断言会拦下并给出明确原因（而不是假装通过）。
#
# 用法: sh tools/driver_stub_elf_gate.sh [outdir]    （默认 outdir=build/stublib）
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9
OUT="${1:-build/stublib}"
PY="${PY:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

# ---- 选 armhf 交叉编译器：真 arm-gcc 优先，否则 zig（PATH 或 python 包）----
# ★★ 绝不接受宿主 gcc：cgm_cc_probe.sh 的兜底里有 `gcc`，在本机/CI 宿主上会选出
#   x86_64 编译器 ⇒ 产物是 ELF64 ⇒ 后面 EM_ARM 断言失败。所以这里**主动**把
#   CC 钉成 armhf 目标，而不是让探测脚本退到宿主 gcc。
pick_arm_cc() {
    if command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then return 0; fi
    if command -v arm-buildroot-linux-gnueabihf-gcc >/dev/null 2>&1; then return 0; fi
    if command -v zig >/dev/null 2>&1; then return 0; fi
    _z="$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null)"
    if [ -n "$_z" ] && [ -x "$_z" ]; then
        chmod +x "$_z" 2>/dev/null || true
        export CC="$_z cc"
        return 0
    fi
    # 都缺 ⇒ 试装 ziglang（pip，秒级，走云端网络）；仍失败就 fail-closed
    "$PY" -m pip install -q --break-system-packages ziglang >/dev/null 2>&1 \
        || "$PY" -m pip install -q --user ziglang >/dev/null 2>&1 || true
    _z="$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null)"
    if [ -n "$_z" ] && [ -x "$_z" ]; then
        chmod +x "$_z" 2>/dev/null || true
        export CC="$_z cc"
        return 0
    fi
    return 1
}
if ! pick_arm_cc; then
    echo "!! 无 armhf 交叉编译器（arm-gcc / zig 均缺）⇒ 造不出真桩，fail-closed（exit 13）" >&2
    exit 13
fi
echo "== 编译器 =="; echo "   CC=${CC:-（由 cgm_cc_probe 选）}"

echo
echo "== 腿0：把两个桩编译成 armhf DSO =="
sh tools/build_libdrm_stub.sh   "$OUT" || exit 1
sh tools/build_libasound_stub.sh "$OUT" || exit 1
ls -la "$OUT" | sed 's/^/   /'
command -v file >/dev/null 2>&1 && file "$OUT"/lib*.so.2 | sed 's/^/   /'

echo
echo "== 腿1+2+3：driver_stub_coverage.py --selftest --elf =="
# ★ 输出落盘后**完整 cat**：第一轮在云端跑时异常 traceback 被 `tail` 截掉，
#   只看到 "[selftest] rc=1" 而看不到原因 ⇒ 白跑一趟。从此判据类输出一律全量可见。
LOG="/tmp/_stub_selftest_$$.txt"
PYTHONUNBUFFERED=1 "$PY" tools/driver_stub_coverage.py --selftest \
    --elf "$OUT/libdrm.so.2" --elf "$OUT/libasound.so.2" >"$LOG" 2>&1
rc=$?
sed 's/^/   /' "$LOG"
echo "   [selftest] rc=$rc"
[ "$rc" = 0 ] || { echo "★★ 产物级门禁的正例没过（上方为完整输出）"; rm -f "$LOG"; exit 1; }
rm -f "$LOG"

echo
echo "== 腿4（反例）：产物级判别力自证 =="
NEG="/tmp/_neg_$$.txt"
neg_fail=0

# --- 4a：只给 drm 桩、不给 alsa 桩 ⇒ 20 个 snd_pcm_* 必须被判缺失 ---
#   这是最朴素也最可靠的反例：**真桩产品**确实没导出那 20 个符号 ⇒ 门禁必须 FAIL 并点名。
"$PY" tools/driver_stub_coverage.py --elf "$OUT/libdrm.so.2" >"$NEG" 2>&1
rcn=$?
echo "   --- 4a 反例输出（尾 6 行）---"; tail -6 "$NEG" | sed 's/^/   /'
echo "   [4a] rc=$rcn（期望非 0）"
if [ "$rcn" = 0 ]; then
    echo "★★★ 假绿（4a）：不给 alsa 桩，门禁竟还 PASS ⇒ 判据无判别力"
    neg_fail=1
elif ! grep -q snd_pcm_open "$NEG"; then
    echo "★★ 4a FAIL 了但没点名缺失的 snd_pcm_* 符号"
    neg_fail=1
else
    echo "   4a OK：正确 FAIL 并点名 snd_pcm_*"
fi

# --- 4b：objcopy --localize-dynamic-symbol 抹掉单个 drmModeAddFB2 ⇒ 必须点名 ---
#   ★ --localize-symbol 只改 .symtab，**不动 .dynsym**（第 163 轮实测踩过：
#     抹完门禁仍 PASS ⇒ 假绿）。动态符号必须用 --localize-dynamic-symbol（binutils>=2.39）。
OBJCOPY=$(command -v arm-linux-gnueabihf-objcopy || command -v objcopy || echo "")
if [ -n "$OBJCOPY" ]; then
    BAD="$OUT/libdrm.stripped.so"
    cp "$OUT/libdrm.so.2" "$BAD"
    if "$OBJCOPY" --localize-dynamic-symbol=drmModeAddFB2 "$BAD" 2>/dev/null; then
        "$PY" tools/driver_stub_coverage.py --elf "$BAD" --elf "$OUT/libasound.so.2" >"$NEG" 2>&1
        rcb=$?
        echo "   --- 4b 反例输出（尾 6 行）---"; tail -6 "$NEG" | sed 's/^/   /'
        echo "   [4b] rc=$rcb（期望非 0）"
        if [ "$rcb" = 0 ]; then
            echo "★★★ 假绿（4b）：抹掉 drmModeAddFB2 后门禁仍 PASS"
            neg_fail=1
        elif ! grep -q drmModeAddFB2 "$NEG"; then
            echo "★★ 4b FAIL 了但没点名 drmModeAddFB2"
            neg_fail=1
        else
            echo "   4b OK：正确 FAIL 并点名 drmModeAddFB2"
        fi
    else
        echo "   4b 跳过：objcopy 不支持 --localize-dynamic-symbol（binutils<2.39），反例只靠 4a"
    fi
else
    echo "   4b 跳过：无 objcopy，反例只靠 4a"
fi
rm -f "$NEG"

[ "$neg_fail" = 0 ] || exit 1

echo
echo "== 产物级假桩门禁全部通过（腿1+2+3 正例 + 腿4 反例）=="
exit 0
