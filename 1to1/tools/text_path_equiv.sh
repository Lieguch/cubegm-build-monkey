#!/bin/sh
# text_path_equiv.sh —— 文字路径等价证据（可复跑，零带宽）
#
# 背景（R288）：B6A 的差异块是 245×51 的文字行。要判定"文字路径是否等价"，
# 必须让沙箱**合法**执行相关函数，而不是靠 CORPUS 的假参数（scr_data=0 ⇒ 写址 0x0 早死）。
# 本脚本跑两条 `--fn` 判据：
#   · outputxy1        —— 8×16 ASCII 字形扫描（直接写帧缓冲）
#   · stbtt_InitFont   —— stb TTF 解析（真机字体前 166 KB）
# 两者都应 PASS；任一非 PASS 即退出非 0（说明文字路径存在实质差异）。
#
# 用法：ZIG=<zig路径> sh tools/text_path_equiv.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-python}"
cd "$ROOT" || exit 9

rc=0
# 第三项需要更大预算：真机 CJK 字形 16px 单字实测 21 万~80 万条指令
# （g3 21.2万 / g4 23.6万 / g8 80.5万，F/O 两侧同量级）⇒ 用 300 万步上限。
for spec in "outputxy1:" "stbtt_InitFont:" "stbtt_GetCodepointHMetrics:" \
             "stbtt_GetGlyphBitmapBoxSubpixel:" "mui_outputxy_t:--steps 3000000" \
             "stbtt_MakeGlyphBitmapSubpixel:--steps 3000000"; do
    fn=${spec%%:*}; extra=${spec#*:}
    out=$("$PY" tools/diff_exec.py --fn "$fn" $extra 2>&1)
    verdict=$(printf '%s\n' "$out" | grep -E "^  $fn ⇒" | head -1)
    printf '%s\n' "$verdict"
    case "$verdict" in
        *"⇒ PASS"*) ;;
        *) rc=1; printf '%s\n' "$out" | tail -8 ;;
    esac
done

if [ "$rc" = "0" ]; then
    echo "文字路径等价证据：六项均 PASS"
else
    echo "文字路径等价证据：存在非 PASS 项（见上）"
fi
exit "$rc"
