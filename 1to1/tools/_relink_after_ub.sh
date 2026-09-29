#!/bin/sh
# _relink_after_ub.sh —— 只重编本轮改动过的对象 + 重链 + 全部门禁
set -u
cd /d/output/rkgame-1to1 || exit 9
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
CC="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe cc"
export ZIG_GLOBAL_CACHE_DIR="$PWD/build/_zigcache_ab"
FID="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"

echo "=== 1) 只重编改动过的 5 个对象 ==="
for f in \
  src/proprietary/misc/FUN_002b4e20_gpsp_unzip.c \
  src/proprietary/core/FUN_002b7510_run_game.c \
  src/proprietary/core/FUN_00016f08_FilePreEmu.c \
  src/proprietary/mui/FUN_0001bf80_mui_DisplayGameSum.c \
  src/proprietary/mui/FUN_000171f8_mui_LoadSetting.c ; do
  b=$(basename "$f" .c)
  if $CC -c -Os -w -Wno-error=implicit-function-declaration -I src/compat $ARCH $FID \
        "$f" -o "build/obj/$b.o" 2>report/_r75_cc_err.txt; then
    echo "   ok  $b.o ($(stat -c%s build/obj/$b.o) B)"
  else
    echo "   ERR $b : $(head -3 report/_r75_cc_err.txt)"
    exit 1
  fi
done

echo "=== 2) 重链（内含 exit12/13/14/15/16/17/18 七道门禁）==="
CC="$CC" SYSROOT="" PY="$PY" EXTRA_LDFLAGS="" sh tools/link_full.sh build/rkgame.rebuilt.elf \
    > report/_r75_link.txt 2>&1
rc=$?
echo "   link rc=$rc  size=$(stat -c%s build/rkgame.rebuilt.elf 2>/dev/null || echo 0)"
grep -aE "结论|PASS|FAIL|SHORT|命中文件数|判决" report/_r75_link.txt | tail -14

echo "=== 3) ABI + 导入核对 ==="
"$PY" tools/abi_check.py build/rkgame.rebuilt.elf 2>&1 | tail -2
"$PY" - <<'PYEOF'
from elftools.elf.elffile import ELFFile
def imp(p):
    e=ELFFile(open(p,'rb')); d=e.get_section_by_name('.dynsym')
    return {s.name for s in d.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'}
F=imp('golden/factory.rkgame.bin'); O=imp('build/rkgame.rebuilt.elf')
print('  工厂导入 %d 我方 %d 交集 %d' % (len(F),len(O),len(F&O)))
PYEOF

echo "=== 4) 行为尺 ==="
"$PY" tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf --out report/_r75_diff.txt > report/_r75_diff_stdout.txt 2>&1
grep -a "共有函数\|汇总：PASS\|自洽校验" report/_r75_diff.txt | head -4
echo DONE
