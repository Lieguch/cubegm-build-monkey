#!/bin/sh
# =============================================================================
# cnb_gates.sh —— 在 CNB 云开发（Linux x86_64）里跑**本机跑不了**的门禁。
#
# 为什么需要它（2026-09-28）
#   本机是 Windows/Git Bash：11 道门禁依赖 `arm-linux-gnueabihf-objdump` / `readelf`，
#   在 Windows 上**跑不了** —— 这件事一直只能写在"诚实声明"里，从未真正关闭。
#   CNB 云开发是 x86_64 Linux（8 核），是唯一能在 CI 之外跑它们的平台。
#
# 用法（在工作区内）:
#   sh tools/cnb_gates.sh                 # 跑全部
#   sh tools/cnb_gates.sh scan_symbol_delta scan_cxx_abi
#
# 前置：`golden/factory.rkgame.bin` 与 `build/rkgame.rebuilt.elf` 都就位。
# =============================================================================
set -u
cd "$(dirname "$0")/.." || exit 9
OUT="${CGM_GATE_LOG:-/tmp/cnb_gates.txt}"
: > "$OUT"

say() { echo "$@"; echo "$@" >> "$OUT"; }

say "== 环境 =="
say "  $(uname -m) / nproc=$(nproc) / python=$(python3 -V 2>&1)"
for f in golden/factory.rkgame.bin build/rkgame.rebuilt.elf; do
    if [ -f "$f" ]; then say "  OK $f $(stat -c%s "$f") B"; else say "  ★缺 $f"; fi
done

# ---- 依赖：多路兜底（apt 两种包名 + pip 三种姿势）----
need_apt=0
command -v arm-linux-gnueabihf-objdump >/dev/null 2>&1 || need_apt=1
if [ "$need_apt" = "1" ]; then
    say "== 装 binutils-arm-linux-gnueabihf =="
    (apt-get install -y -q binutils-arm-linux-gnueabihf >/tmp/_apt.log 2>&1 \
     || sudo apt-get install -y -q binutils-arm-linux-gnueabihf >>/tmp/_apt.log 2>&1)
    say "  apt rc=$? objdump=$(command -v arm-linux-gnueabihf-objdump || echo 缺)"
fi
OBJ=$(command -v arm-linux-gnueabihf-objdump || echo "")
[ -n "$OBJ" ] || { say "★★ 无 arm objdump ⇒ 这些门禁无法跑（本机同样缺，这就是本脚本存在的理由）"; }

# python 依赖：先 apt（离线可用），再 pip（三个 index 兜底）
python3 -c "import elftools" 2>/dev/null || {
    say "== 装 python 依赖 =="
    (apt-get install -y -q python3-pyelftools >/tmp/_apt2.log 2>&1 || true)
    python3 -c "import elftools" 2>/dev/null || {
        for idx in "" "-i https://pypi.tuna.tsinghua.edu.cn/simple" "-i https://mirrors.aliyun.com/pypi/simple"; do
            python3 -m pip install -q --break-system-packages $idx pyelftools capstone unicorn >>/tmp/_pip.log 2>&1 && break
            python3 -m pip install -q --user $idx pyelftools capstone unicorn >>/tmp/_pip.log 2>&1 && break
        done
    }
}
say "  pyelftools=$(python3 -c 'import elftools;print("OK")' 2>&1 | tail -1) capstone=$(python3 -c 'import capstone;print("OK")' 2>&1 | tail -1) unicorn=$(python3 -c 'import unicorn;print("OK")' 2>&1 | tail -1)"

# ---- 跨平台门禁：ABI / PT_INTERP / 假桩产物（★ 不依赖 arm objdump）----
#  为什么必须是独立一块：下面 ALL 里的门禁**全都依赖 arm-linux-gnueabihf-objdump**，
#  而这几条只读 ELF 头 / 只需一个 armhf 编译器 —— 装在 Windows/CNB 都能跑，没理由等 objdump。
#  ★ 它们守住的是"设备能不能 exec 起来 / 沙箱里 driver.so 能不能被桩喂饱"这一层：
#    真机 `execve` 只认 PT_INTERP 的绝对路径；driver.so 只认 libdrm/libasound 的导出符号。
#  ★ 第 163 轮新增 `sh tools/driver_stub_elf_gate.sh`（假桩产物级第三腿）：
#    源级判据只管"符号写在桩源里"，产物级对**编出来的 DSO 的 .dynsym** 断覆盖，
#    并造 objcopy 反例自证判别力。它的 rc=3 = "无 objcopy，反例腿跳过"
#    ⇒ 计"前置缺失"而非失败（与下面 ALL 循环同一口径）。
say ""
say "== 跨平台门禁：ABI / PT_INTERP / 假桩产物 =="
fail=0
for spec in "tools/abi_check.py build/rkgame.rebuilt.elf" \
            "tools/enforce_interp.py --check build/rkgame.rebuilt.elf" \
            "tools/seg_page_audit.py build/rkgame.rebuilt.elf" \
            "tools/seg_page_audit.py --selftest build/rkgame.rebuilt.elf golden/factory.rkgame.bin" \
            "tools/ssh_literal_guard.py tools/cnb_ladder.sh" \
            "tools/ssh_literal_guard.py --selftest" \
            "tools/pre_device_gate.py build/rkgame.rebuilt.elf golden/factory.rkgame.bin golden/device_rootfs_min" \
            "tools/fimg_ref_audit.py build/rkgame.rebuilt.elf golden/factory.rkgame.bin" \
            "tools/_r165_abi_selftest.py" \
            "sh tools/driver_stub_elf_gate.sh"; do
    say "########## $spec ##########"
    case "$spec" in
        sh\ *) sh $spec >>"$OUT" 2>&1 ;;
        *) python3 $spec >>"$OUT" 2>&1 ;;
    esac
    rc=$?
    say "  [$spec] rc=$rc"
    if [ "$rc" = "0" ]; then :;
    elif [ "$rc" = "3" ]; then say "      （前置缺失，不计入失败）";
    else fail=$((fail + 1)); fi
done

# ---- 门禁清单（每个：名字 → 需要的额外参数）----
# ★ R242 新增 artifact_freshness：产物新鲜度（`.o` 不得旧于 `.c`，ELF 不得落后）
#   来历：`build/obj` 23 个过期 `.o` 导致 `FBA_Load` 的 `sprintf` 缺第 4 参 ⇒ core 名 `(null)`
#   ⇒ 连续多轮围绕 `unsupport.` 的归因前提不成立。rc=2 计入失败；rc=3(不适用) 不计。
ALL="artifact_freshness scan_symbol_delta scan_cxx_abi scan_livein_args scan_kr_argcount scan_dead_loop ci_p2a_stb"
WANT="${*:-$ALL}"
say ""
say "== 跑门禁 =="
for t in $WANT; do
    [ -f "tools/$t.py" ] || { say "  -- $t 不存在，跳过"; continue; }
    # ★★ 参数**逐字对齐 CI**（`.github/workflows/1to1-verify.yml`）。
    #   实测教训：`scan_symbol_delta` 的台账**只在显式传 `--pending` 时才读**
    #   ⇒ 漏传参数会把"已知债务"报成"新增违规"（假失败）。
    # ★★ 每个门禁**各自**的参数（照抄 .github/workflows/1to1-verify.yml）。
    #   实测教训：给 `ci_p2a_stb` 传 `--objdump <path>` 会被它当成 golden json 的文件名
    #   ⇒ `FileNotFoundError: '--objdump'` ⇒ **假失败**（它没有参数解析，只吃两个位置参数）。
    args=""
    case "$t" in
        artifact_freshness)
            args="--src src/proprietary --obj build/obj --elf build/rkgame.rebuilt.elf" ;;
        scan_symbol_delta)
            args="--ours build/rkgame.rebuilt.elf --pending tools/upstream_api_pending.txt"
            [ -n "$OBJ" ] && args="--objdump $OBJ $args" ;;
        scan_cxx_abi)
            args="--factory golden/factory.rkgame.bin --ours build/rkgame.rebuilt.elf --ledger tools/cxx_abi_pending.txt"
            [ -n "$OBJ" ] && args="--objdump $OBJ $args" ;;
        scan_livein_args)
            args="--factory golden/factory.rkgame.bin --ours build/rkgame.rebuilt.elf --ledger tools/livein_args_pending.txt"
            [ -n "$OBJ" ] && args="--objdump $OBJ $args" ;;
        scan_kr_argcount)
            args="--root . --fa golden/factory.rkgame.bin"
            [ -n "$OBJ" ] && args="--objdump $OBJ $args"
            [ -f tools/kr_argcount_pending.txt ] && args="$args --pending tools/kr_argcount_pending.txt" ;;
        ci_p2a_stb)
            args="golden/factory.funcs.json.gz report/p2a_stb.txt" ;;
        scan_dead_loop)
            args="" ;;
    esac
    say "########## $t ##########"
    timeout 900 python3 "tools/$t.py" $args >>"$OUT" 2>&1
    rc=$?
    say "  [$t] rc=$rc"
    # rc=3 一律视为"**前置缺失**"（如 scan_dead_loop 需要 build/obj）——不是门禁不通过。
    if [ "$rc" = "0" ]; then :;
    elif [ "$rc" = "3" ]; then say "      （前置缺失，不计入失败）";
    else fail=$((fail + 1)); fi
done
say ""
say "== 摘要（非零即需处理）=="
grep -aE "rc=[0-9]+$|结论|★" "$OUT" | tail -25
say "== 失败项数 = $fail ；完整日志 $OUT =="
exit 0
