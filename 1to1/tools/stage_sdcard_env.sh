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

# ★★★ 场景 K / L：合成 `NNN/` 游戏目录 + 占位游戏文件（`file_info_list` 的**真正来源**）
#    依据 ①：`dir_serial_list`（readdir 扫目录）把目录项名字拷进 `file_info_list`
#      （`src/proprietary/misc/FUN_0002142c_dir_serial_list.c:69`：strcpy + 记 d_type）。
#    依据 ②（第 49 轮实测定案）：**父目录必须是 `root_path`，而 `root_path = /sdcard`** ——
#      `main_Menu` 把 work_path(`/sdcard/cubegm/`) 剥两层得到 `/sdcard`；
#      `mui_type.c:61` 是 `sprintf("%s/%03d/%03d.dat", root_path, N, N)`，
#      `mui_DisplayThumbnail.c:42` 是 `"%s/%s/%s.dat"` ⇒ 缩略图包在 `/sdcard/NNN/NNN.dat`；
#      我们侧的 strace 实测打开过 `"/sdcard//.dat"`（空 basepath）**证实了 root_path=/sdcard**。
#    ⇒ 两种口径（严格单变量，用于钉死"父目录"这一个变量）：
#        `CGM_GAMEDIRS=1` → 建在 `$WORK`（= /sdcard/cubegm）…**对照口径（错）**
#        `CGM_GAMEDIRS=2` → 建在 `$(dirname $WORK)`（= /sdcard = root_path）…**正确口径**
#    内容 = `cores/filelist.xml` 的 135 个 `name=`（只造名字；占位文件 22 B 空 ZIP）。
#    ★★ 未启用时**显式清理**两处残留：/sdcard 与 /sdcard/cubegm 都是跨场景共享的。
_GD_DIRS="000 002 004"
_GD_BASE=""
case "${CGM_GAMEDIRS:-0}" in
    1) _GD_BASE="$WORK" ;;
    2) _GD_BASE="$(dirname "$WORK")" ;;
    0) _GD_BASE="" ;;
    *) echo "FATAL CGM_GAMEDIRS 只支持 1($WORK) / 2(dirname $WORK)（收到 '$CGM_GAMEDIRS'）"; exit 1 ;;
esac
if [ -n "$_GD_BASE" ]; then
    _TOOLS_G="$(dirname "$0")"
    _PY_G="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
    if [ -z "$_PY_G" ]; then echo "FATAL 找不到 python3/python，无法合成游戏目录"; exit 1; fi
    echo "   [GAMEDIRS] 父目录 = $_GD_BASE（CGM_GAMEDIRS=$CGM_GAMEDIRS）"
    "$_PY_G" "$_TOOLS_G/make_gamedirs.py" --golden "$GOLDEN" --work "$_GD_BASE" \
        || { echo "FATAL 合成游戏目录失败"; exit 1; }
    if [ -n "${CGM_STAGE_EVIDENCE:-}" ]; then
        mkdir -p "$(dirname "$CGM_STAGE_EVIDENCE")" 2>/dev/null || true
        printf 'GAMEDIRS_BUILT base=%s mode=%s dirs=%s files=%s\n' \
            "$_GD_BASE" "$CGM_GAMEDIRS" \
            "$(ls -d "$_GD_BASE"/[0-9][0-9][0-9] 2>/dev/null | wc -l | tr -d ' ')" \
            "$(find "$_GD_BASE"/[0-9][0-9][0-9] -type f 2>/dev/null | wc -l | tr -d ' ')" \
            >> "$CGM_STAGE_EVIDENCE"
    fi
else
    _gd_rm=0
    for _b in "$WORK" "$(dirname "$WORK")"; do
        for _d in $_GD_DIRS; do
            if [ -e "$_b/$_d" ]; then rm -rf "$_b/$_d"; _gd_rm=$((_gd_rm + 1)); fi
        done
    done
    if [ "$_gd_rm" != "0" ]; then
        echo "   [GAMEDIRS] 开关缺省 ⇒ 已显式清理 $_gd_rm 个残留游戏目录（两处父目录都查了）"
    else
        echo "   [GAMEDIRS] 开关缺省，两处父目录均无残留（= 场景 J 的预期状态）"
    fi
fi

# ★★★ 场景 M/N/O：给 `ui_cn.zip` 的 `ui.cfg` 补 `GameList_count`（列表闸门 `DAT_003af394` 的来源）
#    依据：`mui_LoadConfig` 用 `get_value_from_items("GameList_count", ...)` 取该值
#      （configitems ← ui_cn.zip 的 ui.cfg）；而 golden 的 ui.cfg（242 B）只有 [Setting]/Recover*。
#      `DAT_003af394` 是**所有列表循环的统一上界**（mui_do_file_list:68 / dir_serial_list:82 /
#      mui_menu / mui_type / DisplayPage_list）；为 0 时 file_info_list（readdir 填充）与
#      root.dat 的 fileinfo（文本解析填充）**两条路径都不被消费** ⇒ `/sdcard//.dat`（实测 29 行）。
#    ★ 不需要"缺省显式清理"：ui_cn.zip 每次 stage 都从 golden 重新拷贝 ⇒ 天然无残留。
if [ "${CGM_UICFG:-0}" = "1" ]; then
    _TOOLS_U="$(dirname "$0")"
    _PY_U="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
    if [ -z "$_PY_U" ]; then echo "FATAL 找不到 python3/python，无法补 ui.cfg"; exit 1; fi
    "$_PY_U" "$_TOOLS_U/patch_uicfg.py" --zip "$WORK/ui_cn.zip" \
        || { echo "FATAL 补 ui.cfg 失败"; exit 1; }
    if [ -n "${CGM_STAGE_EVIDENCE:-}" ]; then
        mkdir -p "$(dirname "$CGM_STAGE_EVIDENCE")" 2>/dev/null || true
        printf 'UICFG_PATCHED zip=%s size=%s\n' "$WORK/ui_cn.zip" "$(wc -c < "$WORK/ui_cn.zip" | tr -d ' ')" >> "$CGM_STAGE_EVIDENCE"
    fi
fi
# ★★★ 场景 P：合成 `cubegm/allfiles.lst`（游戏索引，独立逆向资料的确切格式）
#    外部依据（github.com/LiamJ74/R36S-V2.6_Wiki，同族固件独立逆向 Wiki）：
#      · 位置 SD 卡 `cubegm/allfiles.lst`；格式（逐字）
#        `Platform/filename.ext|Display Name|UPPERCASE NAME|Chinese Name|Abbreviated`
#      · 运行时 `rkgame` 启动时 **读列表文件**："loads ... game lists from allfiles.lst / filelist.csv"
#      · 菜单看不到游戏的官方解释：**"allfiles.lst is out of sync with actual ROM files"**
#    本机铁证：`cores/filelist.xml` 的 `name="002/xxx.zip"` ⇒ Platform 段取 `NNN`（本机是数字目录）。
#    ★ 与 golden 无冲突：生成在 $WORK 内（= /sdcard/cubegm/），stage 每次重建 ⇒ 天然无残留。
if [ "${CGM_ALLFILES:-0}" = "1" ]; then
    _TOOLS_A="$(dirname "$0")"
    _PY_A="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
    if [ -z "$_PY_A" ]; then echo "FATAL 找不到 python3/python，无法合成 allfiles.lst"; exit 1; fi
    "$_PY_A" "$_TOOLS_A/make_allfiles.py" --golden "$GOLDEN" --work "$WORK" \
        || { echo "FATAL 合成 allfiles.lst 失败"; exit 1; }
    if [ -n "${CGM_STAGE_EVIDENCE:-}" ]; then
        mkdir -p "$(dirname "$CGM_STAGE_EVIDENCE")" 2>/dev/null || true
        printf 'ALLFILES_BUILT file=%s size=%s lines=%s\n' "$WORK/allfiles.lst" \
            "$(wc -c < "$WORK/allfiles.lst" | tr -d ' ')" \
            "$(wc -l < "$WORK/allfiles.lst" | tr -d ' ')" >> "$CGM_STAGE_EVIDENCE"
    fi
fi
ls -la "$WORK"
