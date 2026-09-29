#!/bin/sh
# _rebuild_measure.sh —— 全量重编 + 全部本地可跑门禁 + 行为尺
set -u
cd /d/output/rkgame-1to1 || exit 9
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
CC="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe cc"
export ZIG_GLOBAL_CACHE_DIR="$PWD/build/_zigcache_ab"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR" build/obj build/upstream

echo "=== 1/6 重编专有对象（213）==="
OPT=-Os CC="$CC" SYSROOT="" sh tools/link_audit.sh report/_r74_la.txt > report/_r74_compile.txt 2>&1
echo "  rc=$? objs=$(ls -1 build/obj/*.o 2>/dev/null | wc -l)"
grep -a "== 编译" report/_r74_compile.txt | head -2

echo "=== 2/6 重编上游对象 ==="
CC="$CC" SYSROOT="" PY="$PY" sh tools/build_upstream.sh build/upstream >> report/_r74_compile.txt 2>&1
echo "  rc=$? objs=$(ls -1 build/upstream/*.o 2>/dev/null | wc -l)"

echo "=== 3/6 链接 ==="
CC="$CC" SYSROOT="" PY="$PY" EXTRA_LDFLAGS="" sh tools/link_full.sh build/rkgame.rebuilt.elf > report/_r74_link.txt 2>&1
echo "  rc=$? size=$(stat -c%s build/rkgame.rebuilt.elf 2>/dev/null || echo 0)"
if [ ! -s build/rkgame.rebuilt.elf ]; then echo "LINK FAILED"; head -20 report/link_full_err.txt; exit 1; fi

echo "=== 4/6 体量覆盖门禁（B 类盲区）==="
"$PY" tools/size_coverage_gate.py --ours build/rkgame.rebuilt.elf --top 12 2>&1 | tail -12

echo "=== 5/6 ABI + 动态导入核对 ==="
"$PY" tools/abi_check.py build/rkgame.rebuilt.elf 2>&1 | tail -2
"$PY" - <<'PYEOF'
from elftools.elf.elffile import ELFFile
def imp(p):
    e=ELFFile(open(p,'rb')); d=e.get_section_by_name('.dynsym')
    return {s.name for s in d.iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF'}
F=imp('golden/factory.rkgame.bin'); O=imp('build/rkgame.rebuilt.elf')
print('  工厂导入 %d 我方 %d 交集 %d' % (len(F),len(O),len(F&O)))
for k in ('reboot','sync','nl_langinfo','getenv','putc','_IO_putc'):
    print('   %-14s 工厂=%-5s 我方=%s' % (k, k in F, k in O))
PYEOF

echo "=== 6/6 行为尺（全量 3000 步）==="
"$PY" tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf --out report/_r74_diff.txt > report/_r74_diff_stdout.txt 2>&1
echo "  rc=$?"
grep -a "共有函数\|汇总：PASS\|自洽校验" report/_r74_diff.txt | head -4
echo DONE
