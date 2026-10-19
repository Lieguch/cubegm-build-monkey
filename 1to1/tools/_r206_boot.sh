#!/bin/sh
# _r206_boot.sh —— 云端一键：全量重编 + 三点启动链验证（工厂对照 / 我方产物）
# 在 CNB 云开发工作区（已 reset 到最新 main）里跑，经 cnb_ws_run.sh 调用。
# 判据（对齐 cnb_devqemu.sh）：工厂必 RAN（阳性对照）；我方产物至少能被 ld.so 加载；
# strace 末尾显示走到哪一步。产出自带 BOOTVERIFY-DONE 哨兵。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "===== [A] 全量重编（FORCE_BUILD=1，无陈旧缓存）====="
FORCE_BUILD=1 sh "$ROOT/tools/cnb_env.sh" 2>&1 | tail -18

echo ""
echo "===== [B] 三点启动链验证（qemu-arm-static + 设备真 sysroot /arm-root-device）====="
Q="$(command -v qemu-arm-static)"
echo "qemu = $Q"
[ -n "$Q" ] || { echo "!! qemu-arm-static 缺失"; exit 11; }

run_point() {
  label="$1"; bin="$2"
  echo "########## $label :: $bin ##########"
  if [ ! -f "$bin" ]; then
    echo "  SKIP（文件不存在）"
    return
  fi
  cp -f "$bin" /sdcard/cubegm/rkgame 2>/dev/null || { echo "  cp 失败"; return; }
  chmod +x /sdcard/cubegm/rkgame
  ( cd /sdcard/cubegm && timeout 30 "$Q" -L /arm-root-device -strace ./rkgame \
      > /tmp/o_$label.txt 2> /tmp/e_$label.txt )
  rc=$?
  echo "  exit=$rc"
  echo "  --- stderr 头 5 行 ---"
  head -5 "/tmp/e_$label.txt" | sed 's/^/    /'
  echo "  --- strace 末尾 8 行（走到哪一步）---"
  tail -8 "/tmp/e_$label.txt" | sed 's/^/    /'
  echo "  --- 里程碑关键字 ---"
  for kw in ld.so.cache driver.so libemu font.ttf ui_cn.zip cores /dev/mem /dev/dri ioctl menu.log setting.xml; do
    c=$(grep -ac "$kw" "/tmp/e_$label.txt" 2>/dev/null || echo 0)
    [ "$c" -gt 0 ] && echo "    hit$c  $kw"
  done
  if grep -qE '^qemu-arm[a-z0-9-]*:' "/tmp/e_$label.txt"; then
    echo "    ★ LOAD-FAILED：qemu 无法加载（解释器/依赖不可达）"
    grep -m1 -E '^qemu-arm[a-z0-9-]*:' "/tmp/e_$label.txt" | sed 's/^/      /'
  elif [ "$rc" = "124" ]; then
    echo "    RAN-AND-TIMEOUT（活着/忙等）"
  else
    echo "    RAN-AND-DIED rc=$rc"
  fi
}

run_point FACTORY "$ROOT/golden/factory.rkgame.bin"
run_point OURS    "$ROOT/build/rkgame.rebuilt.elf"
echo "BOOTVERIFY-DONE"