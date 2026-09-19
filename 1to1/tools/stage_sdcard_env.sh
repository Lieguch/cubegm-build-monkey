#!/bin/sh
# ============================================================
# stage_sdcard_env.sh — 铺一个「真机同款最小 SD 环境」到工作目录
#
# 为什么必须"两侧同路径"：
#   工厂 rkgame 用 get_executable_path() 取 /proc/self/exe 的目录作为 work_path，
#   再用 work_path 拼出所有资源路径（setting.xml / cores/config.xml / menu.log /
#   joystick.zip / saves / states …）。
#   若把两个二进制放在各自仓库目录里跑，work_path 不同 ⇒ main() 打印的
#   `directory:` 行不同、能读到的资源也不同 ⇒ 差分比的是**路径差异**而不是代码差异。
#   ⇒ 两侧都必须从 **同一个绝对路径** 运行（真机就是 /sdcard/cubegm/rkgame）。
#
# 用法: stage_sdcard_env.sh <workdir> <golden_env_dir>
# ============================================================
set -u

WORK="${1:?usage: stage_sdcard_env.sh <workdir> <golden_env_dir>}"
GOLDEN="${2:?golden env dir required}"

if [ ! -d "$GOLDEN" ]; then
    echo "FATAL 缺少最小环境目录: $GOLDEN"
    echo "      （golden/sdcard_min/ —— 由原厂 SD 卡只读拷贝而来，含 setting.xml / menu.log /"
    echo "        cores/config.xml / joystick.zip / favorites.lst / recent.lst / fileinfo）"
    exit 1
fi

# 每次都从干净状态开始：上一次运行可能改写了 menu.log / saves / states
rm -rf "$WORK"
mkdir -p "$WORK"

# 拷贝环境（-R 保留子目录结构；不保留时间戳可比性无关紧要）
# MANIFEST.sha256 只用于核验，不属于"设备环境"，不铺进运行目录
(cd "$GOLDEN" && tar cf - --exclude=MANIFEST.sha256 .) | (cd "$WORK" && tar xf -) || {
    echo "FATAL 拷贝最小环境失败"; exit 1
}

# 运行期目录（空目录在 git 里存不住，必须显式建）
mkdir -p "$WORK/saves" "$WORK/states"

# ★ 校验清单：环境必须与仓库内的 MANIFEST 一致，避免"环境被悄悄换掉"导致差分结论失真
MAN="$GOLDEN/MANIFEST.sha256"
if [ -f "$MAN" ]; then
    bad=0
    while read -r h p; do
        [ -n "${p:-}" ] || continue
        got=$(sha256sum "$WORK/$p" 2>/dev/null | cut -d' ' -f1)
        if [ "$got" != "$h" ]; then
            echo "   [MANIFEST-FAIL] $p  期望 ${h%%????????????????????????????????}… 实际 ${got%%????????????????????????????????}…"
            bad=$((bad+1))
        fi
    done < "$MAN"
    if [ "$bad" != "0" ]; then
        echo "FATAL 最小环境与 MANIFEST 不符（$bad 项）"; exit 1
    fi
    echo "   最小环境已铺好并核验 MANIFEST：$(wc -l < "$MAN" | tr -d ' ') 个文件"
else
    echo "   [warn] 无 MANIFEST.sha256，未做环境完整性核验"
fi

# ★★ 场景 G/H：起始屏幕注入（严格单变量）
#    `main_Menu` 的屏幕分派 = `switch (menulog[0])`：
#      0=mui_menu  1=mui_type  2=mui_recent  3=mui_shoucang  4=mui_search  5=mui_setting
#    原厂 golden/sdcard_min/menu.log 头 4 字节 = `05 00 00 00` ⇒ 一开机就停在「设置页」
#    里 `while(true)` 循环 ⇒ 另外 5 个屏幕函数（合计 ~26 KB 的 mui 代码）永远走不到。
#    ⇒ 本开关**只改写头 4 字节**，其余 440 字节保持原厂原样（这是 E vs G 可归因的前提）。
#    ★ 默认关（不设 = 完全用原厂 menu.log）；两侧共用同一份 ⇒ 差分公平。
#    ★ 不需要 -E 转发：本脚本在**宿主**侧铺环境，guest 不读这个变量。
if [ -n "${CGM_MENULOG_SCREEN:-}" ]; then
    case "$CGM_MENULOG_SCREEN" in
        0|1|2|3|4|5) ;;
        *) echo "FATAL CGM_MENULOG_SCREEN 必须是 0..5（收到 '$CGM_MENULOG_SCREEN'）"; exit 1 ;;
    esac
    if [ ! -f "$WORK/menu.log" ]; then
        echo "FATAL CGM_MENULOG_SCREEN 已设但 $WORK/menu.log 不存在"; exit 1
    fi
    python3 -c "import struct,sys;p=sys.argv[1];v=int(sys.argv[2]);d=bytearray(open(p,'rb').read());o=struct.unpack_from('<I',d,0)[0];struct.pack_into('<I',d,0,v);open(p,'wb').write(bytes(d));print('   [MENULOG-INJECT] screen %d -> %d (%d bytes untouched)'%(o,v,len(d)-4))" \
        "$WORK/menu.log" "$CGM_MENULOG_SCREEN" || { echo "FATAL menu.log 注入失败"; exit 1; }
    if [ -n "${CGM_STAGE_EVIDENCE:-}" ]; then
        mkdir -p "$(dirname "$CGM_STAGE_EVIDENCE")" 2>/dev/null || true
        printf 'MENULOG_INJECT screen=%s file=%s size=%s\n' \
            "$CGM_MENULOG_SCREEN" "$WORK/menu.log" "$(wc -c < "$WORK/menu.log" | tr -d ' ')" >> "$CGM_STAGE_EVIDENCE"
    fi
fi

# ★★★ 场景 I：补 `/sdcard/root.dat`（**ZIP 包**，内含 `fileinfo.txt`）
#    依据（工厂反编译 decompiled/02-ghidra-c/00_rkgame_ALL.c:19268-19285）：
#      DAT_003af2ac 只在「root.dat 打开成功 **且** 找到 fileinfo.txt」时才被 malloc 填充；
#      失败分支**保持 NULL**，随后 `mui_do_file_list(iVar11, DAT_003af2ac)` 解引用它
#      ⇒ 缺 root.dat 时两侧都会崩（实测：我们崩在 mui_do_file_list+0xf0 的 `ldrb r0,[r0]`，r0=0）。
#    ⇒ 本开关合成该 ZIP；内容取 golden/sdcard_min/fileinfo（49 B = "0,0,...,0"），
#      **不自行编造**。位置 = $(dirname $WORK)/root.dat，即 /sdcard/root.dat
#      （在 CGM_WORK 之外 ⇒ 不进 new_files / changed_files 维度）。
#    ★★ 未启用时**显式删除**：/sdcard 是跨场景共享的，残留会让"缺文件"的场景静默变成"有文件"
#       —— 与场景 C 的 stublib 残留是同一类事故（"每个场景的输入必须完全由该场景自己的开关决定"）。
ROOTDAT="$(dirname "$WORK")/root.dat"
# ★ 先记"是否本来就有"，再删 —— 否则那句提示语永远打不出来（rm 在前，[ -e ] 恒假）。
_rd_had=0; [ -e "$ROOTDAT" ] && _rd_had=1
rm -f "$ROOTDAT"
if [ "${CGM_ROOTDAT:-0}" != "0" ]; then
    case "$CGM_ROOTDAT" in
        1) _rd_mode=fileinfo ;;   # 旧口径（顶层 fileinfo，已实测不成立，仅作对照）
        2) _rd_mode=filelist ;;   # ★ 正确口径：cores/filelist.xml 的 name= 列表
        *) echo "FATAL CGM_ROOTDAT 只支持 1(fileinfo) / 2(filelist)（收到 '$CGM_ROOTDAT'）"; exit 1 ;;
    esac
    # ★ 必须用**相对路径**：本机 Git Bash 的 `pwd` 给的是 `/d/...`，交给 Windows 版
    #   python.exe 会被解释成 `D:\d\...`（实测报 "No such file"）。相对路径对
    #   Linux(CI) 与 Windows(本地) 两侧都成立（都从仓库根调用）。
    _TOOLS="$(dirname "$0")"
    python3 "$_TOOLS/make_rootdat.py" --mode "$_rd_mode" \
        --golden "$GOLDEN" --out "$ROOTDAT" \
        || { echo "FATAL 合成 root.dat 失败（mode=$_rd_mode）"; exit 1; }
    if [ -n "${CGM_STAGE_EVIDENCE:-}" ]; then
        mkdir -p "$(dirname "$CGM_STAGE_EVIDENCE")" 2>/dev/null || true
        printf 'ROOTDAT_BUILT file=%s size=%s\n' "$ROOTDAT" "$(wc -c < "$ROOTDAT" | tr -d ' ')" >> "$CGM_STAGE_EVIDENCE"
    fi
else
    if [ "$_rd_had" = "1" ]; then
        echo "   [ROOTDAT] 开关缺省 ⇒ 已显式移除上一次运行残留的 $ROOTDAT"
    else
        echo "   [ROOTDAT] 开关缺省，且无残留（/sdcard/root.dat 不存在 = 场景 G 的预期状态）"
    fi
fi

ls -la "$WORK"
