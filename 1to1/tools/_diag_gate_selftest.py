# -*- coding: utf-8 -*-
"""
_diag_gate_selftest.py —— tools/diag_wraps.sh 自检门禁的三态自证

纪律（本项目 GAP 16.57）：门禁上线必须做**三态自证**
    ① 正常态 PASS
    ② **缺陷态 FAIL**（且缺陷必须是"真能触发"的那种）
    ③ CI/近似态 PASS（挪走可能在目标环境里不存在的文件）

★ 关键教训（我第一次造错了缺陷态）：
    `-wrap=X` **只在有东西引用 `X` 时**才会产生"未定义 `__wrap_X`"。
    往列表塞一个**无人引用**的假符号 ⇒ 门禁不会响、链接也不会报错（实测 exit 0）。
    ⇒ 缺陷态必须用**被引用**的符号：这里用 `fflush`（rkgame 里确有调用，
      第一次真链接时就是它报的 `undefined symbol: __wrap_fflush`）。
"""
import io
import os
import shutil
import subprocess

ROOT = 'D:/output/rkgame-1to1'
WRAPC = os.path.join(ROOT, 'src', 'diag', 'cgm_wrap.c')
GATE = os.path.join(ROOT, 'tools', 'diag_wraps.sh')
BAK = os.path.join(ROOT, 'build', '_cgm_wrap.c.bak')

env = dict(os.environ)
env['ROOT'] = ROOT
env['PY'] = 'C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe'
env['CC'] = 'zig cc'

FAIL = 0


def run_gate():
    r = subprocess.run(['sh', GATE], cwd=ROOT, capture_output=True, env=env)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace').strip()


print('=== 三态自证：tools/diag_wraps.sh ===')
print()

# ① 正常态
rc, out = run_gate()
print('① 正常态        exit=%d   %s' % (rc, out.split('\n')[-1][:100]))
if rc != 0:
    FAIL += 1; print('   ✗ 正常态必须 exit 0')

# ② 缺陷态：把 __wrap_fflush 改名（用被引用的符号造真缺陷）
os.makedirs(os.path.dirname(BAK), exist_ok=True)
shutil.copy2(WRAPC, BAK)
src = io.open(WRAPC, encoding='utf-8').read()
assert '__wrap_fflush' in src, '锚点 __wrap_fflush 未命中'
io.open(WRAPC, 'w', encoding='utf-8', newline='\n').write(
    src.replace('__wrap_fflush', '__BROKEN_fflush'))
rc2, out2 = run_gate()
print('② 缺陷态(去实现) exit=%d   %s' % (rc2, out2.split('\n')[0][:100]))
if rc2 != 11:
    FAIL += 1; print('   ✗ 缺陷态必须 exit 11')

# ③ 近似态：把 cgm_wrap.c 挪走（模拟"目标环境里这个文件不存在"）
os.rename(WRAPC, BAK + '.moved')
rc3, out3 = run_gate()
print('③ 近似态(文件缺) exit=%d   %s' % (rc3, out3.split('\n')[0][:100]))
if rc3 != 11:
    FAIL += 1; print('   ✗ 文件读不到也必须硬失败（否则门禁恒真）')
os.rename(BAK + '.moved', WRAPC)

# 还原
shutil.copy2(BAK, WRAPC)
src2 = io.open(WRAPC, encoding='utf-8').read()
restored = ('__wrap_fflush' in src2) and ('__BROKEN_fflush' not in src2)
print('④ 还原           %s' % ('✓ cgm_wrap.c 已还原' if restored else '✗ 还原失败！'))
if not restored:
    FAIL += 1
rc4, out4 = run_gate()
print('   正常态复跑     exit=%d' % rc4)
if rc4 != 0:
    FAIL += 1

os.remove(BAK)
print()
print('  结果：%s' % ('✓ 三态全过' if FAIL == 0 else '✗ %d 项未过' % FAIL))
raise SystemExit(0 if FAIL == 0 else 1)
