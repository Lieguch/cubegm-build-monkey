#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_zero_fimg.py —— **删除实验**：把 `.fimg_*` 镜像的**内容**换全零（保持 `.size` 与 VMA），
重新链接，看能不能过全部本地门禁。

为什么需要它（缺口 P2，§0.29-F）
--------------------------------
交付产物里 `.fimg_text` 携带 **2,957,704 B 原厂机器码**（工厂 `.text` 逐字节副本）、
`.fimg_rodata` 携带 **856,920 B** 原厂只读数据，用途只是"地址垫"。
静态仪器（`tools/fimg_content_gate.py`，符号表界定反汇编 + 相对偏移解算）给出：
**`.fimg_text` STRONG 引用 0、`.fimg_rodata` STRONG 引用 0**；只有 `.fimg_data`(7)/
`.fimg_bss`(6) 被 movw/movt 绝对引用。
⇒ 若"内容可全零"成立，产物就**不再携带任何原厂字节**（只剩地址空间占位）。

★ 但这只是**静态**结论。静态判据在本项目已连续三次误判（纪律 62 + 指令立即数 + 相对偏移），
  所以终局必须由**实验**背书：**全零 → 链接 → 门禁 → 行为尺**。

预登记判据（纪律 61：先写死，再跑）
----------------------------------
| case       | 动作                                  | 期望 |
|------------|---------------------------------------|------|
| `base`     | 不改任何东西                          | 产物 sha **必须 == b21a3f12cdb2a84e…**（可复现性锚点） |
| `ztext`    | `factory_text.bin` 全零（同尺寸）     | link rc=0；门禁全过；行为尺 **DIVERGE 不上升**（目标 = 基线 40） |
| `ztext_ro` | 上面 + `factory_rodata.bin` 全零      | link rc=0；行为尺 **DIVERGE 不上升** |

任一项不达标 ⇒ 该段内容**必须携带**，并把静态仪器挖出的"最小必需集合"作为交付结论
（而不是"整段 2.96 MB"）。

安全
----
* 三个 case 都**只写 `build/_exp/`**，**绝不触碰 `build/rkgame.rebuilt.elf`**。
* 改 `src/data/factory_*.bin` 前后有 `try/finally` 恢复；备份在 `build/_exp/bak/`。
* 零化后**重新读回验证全零**（fail-closed）。

用法
----
    python tools/exp_zero_fimg.py            # 跑 base + ztext + ztext_ro
    python tools/exp_zero_fimg.py ztext      # 只跑一个 case
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, 'build', '_exp')
BAK = os.path.join(EXP, 'bak')
DATA = os.path.join(ROOT, 'src', 'data')

PY = r'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe'
# ★ 本脚本可能被**系统 python** 启动（无 pyelftools）⇒ 显式补 venv 的 site-packages。
_VENV_SP = r'C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages'
if os.path.isdir(_VENV_SP) and _VENV_SP not in sys.path:
    sys.path.insert(0, _VENV_SP)
ZIG = (r'C:\Users\Administrator\.workbuddy\binaries\python\envs\default'
       r'\Lib\site-packages\ziglang\zig.exe')
# 交付臂基线（§0.28：arm C 接管链接后的产物）
BASE_SHA = 'b21a3f12cdb2a84e'

# 段 → 镜像文件
SEG_FILE = {
    'text': 'factory_text.bin',
    'rodata': 'factory_rodata.bin',
    'data': 'factory_data.bin',
    'data_rel_ro_local': 'factory_data_rel_ro_local.bin',
}
CASES = {
    'base': [],
    'ztext': ['text'],
    'ztext_ro': ['text', 'rodata'],
}
# 段 → 产物里的段名（用于**内容级**校验零化是否真的落进产物）
SEG_SEC = {
    'text': '.fimg_text',
    'rodata': '.fimg_rodata',
    'data': '.fimg_data',
    'data_rel_ro_local': '.fimg_data_rel_ro_local',
}


def verify_seg_in_artifact(elf, seg):
    """返回 (非零字节数, 段大小)；段不存在返回 None。

    ★ 为什么必须做**内容级**校验：2026-09-29 实测第一次跑删除实验时，
      `.fimg_text` 全零化后产物 sha **与对照完全相同** —— 因为 zig 的缓存键
      **不追踪 `.incbin` 引用的文件**，直接复用了旧的 `factory_local.o`。
      sha 相同会被误读成"内容不需要"，实际是**假绿**。内容级校验能直接揭穿它。
    """
    from elftools.elf.elffile import ELFFile
    e = ELFFile(open(elf, 'rb'))
    s = e.get_section_by_name(SEG_SEC[seg])
    if s is None:
        return None
    d = s.data()
    return sum(1 for b in d if b), len(d)


def tool_path():
    """显式构造 PATH（本机 Git Bash 偶发 PATH 丢失；且 zig.exe 需要 cygpath 提供 Windows 路径）。"""
    pg = r'C:\Users\Administrator\.workbuddy\binaries\PortableGit\versions'
    extra = []
    if os.path.isdir(pg):
        for v in os.listdir(pg):
            for sub in ('usr/bin', 'bin', 'mingw64/bin'):
                p = os.path.join(pg, v, sub)
                if os.path.isdir(p):
                    extra.append(p)
    return os.pathsep.join(extra + [os.environ.get('PATH', '')])


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def backup_all():
    os.makedirs(BAK, exist_ok=True)
    for f in SEG_FILE.values():
        src = os.path.join(DATA, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(BAK, f))


def restore_all():
    for f in SEG_FILE.values():
        b = os.path.join(BAK, f)
        if os.path.exists(b):
            shutil.copy2(b, os.path.join(DATA, f))


def zero_seg(seg):
    """把某段的镜像文件内容换全零（保持尺寸），并读回自检。"""
    f = os.path.join(DATA, SEG_FILE[seg])
    if not os.path.exists(f):
        raise SystemExit('!! 缺镜像文件 %s' % f)
    n = os.path.getsize(f)
    with open(f, 'wb') as fh:
        fh.write(b'\x00' * n)
    if os.path.getsize(f) != n:
        raise SystemExit('!! 尺寸变了 %s' % f)
    with open(f, 'rb') as fh:
        if fh.read() != b'\x00' * n:
            raise SystemExit('!! 零化自检失败 %s' % f)
    print('   [zero] %s → %d B 全零（读回自检 OK）' % (SEG_FILE[seg], n))
    return n


def run_link(out, tag):
    env = dict(os.environ)
    env['PATH'] = tool_path()
    env['CC'] = '%s cc' % ZIG
    env['SYSROOT'] = ''
    env['PY'] = PY
    env['EXTRA_LDFLAGS'] = ''
    env['LINK_DRIVER'] = 'lld'
    env['ZIG_GLOBAL_CACHE_DIR'] = os.path.join(ROOT, 'build', '_zigcache_ab')
    log = os.path.join(EXP, 'link_%s.log' % tag)
    with open(log, 'w', encoding='utf-8', errors='replace') as fh:
        p = subprocess.run(['sh', os.path.join(ROOT, 'tools', 'link_full.sh'), out],
                           cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    return p.returncode, log


def gates_from_log(log):
    """从链接日志里抠关键门禁结论（不自己判，只转载）。"""
    keys = ('FAIL', 'WARN', 'SHORT', '未建模', 'PASS', '结论', 'rc=', 'exit')
    out = []
    if not os.path.exists(log):
        return out
    with open(log, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            s = ln.rstrip()
            if any(k in s for k in keys) and len(s) < 160:
                out.append(s.strip())
    return out[-14:]


def one_case(tag, segs):
    print('=' * 92)
    print('CASE %s   （零化段: %s）' % (tag, ', '.join(segs) if segs else '无（对照）'))
    print('=' * 92)
    out = os.path.join(EXP, 'rkgame.zero_%s.elf' % tag)
    try:
        for s in segs:
            zero_seg(s)
        rc, log = run_link(out, tag)
    finally:
        restore_all()
        print('   [restore] src/data/*.bin 已恢复原样')
    print('   link rc = %d   （日志 %s）' % (rc, os.path.relpath(log, ROOT)))
    rec = {'case': tag, 'segs': segs, 'rc': rc, 'out': out}
    if rc == 0 and os.path.exists(out):
        rec['size'] = os.path.getsize(out)
        rec['sha'] = sha256(out)
        print('   产物 %d B   sha256=%s' % (rec['size'], rec['sha']))
        if tag == 'base':
            ok = rec['sha'].startswith(BASE_SHA)
            print('   ★ 可复现性锚点：期望 %s… ⇒ %s' % (BASE_SHA, '✓ 一致' if ok else '★ 不一致！'))
            rec['repro'] = ok
        # ★ 内容级校验：零化后产物里对应段**必须**真的全零；对照（base）必须非零。
        checks = []
        for seg in ('text', 'rodata'):
            r = verify_seg_in_artifact(out, seg)
            if r is None:
                continue
            nz, tot = r
            want_zero = seg in segs
            ok = (nz == 0) if want_zero else (nz > 0)
            checks.append((SEG_SEC[seg], nz, tot, want_zero, ok))
            print('   [内容校验] %-16s 非零 %9d / %9d   期望%s ⇒ %s'
                  % (SEG_SEC[seg], nz, tot, '全零' if want_zero else '非零',
                     '✓' if ok else '★★ 不符（假绿！）'))
        rec['checks'] = checks
        # 内容门禁（用静态仪器复核零化后的产物）
        gp = subprocess.run([PY, os.path.join(ROOT, 'tools', 'fimg_content_gate.py'), out],
                            cwd=ROOT, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
        rec['gate'] = gp.stdout
    else:
        print('   ★ 链接失败；日志尾部：')
        for ln in gates_from_log(log):
            print('      %s' % ln)
    print()
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cases', nargs='*', default=None)
    a = ap.parse_args()
    os.makedirs(EXP, exist_ok=True)
    todo = a.cases or ['base', 'ztext', 'ztext_ro']
    for c in todo:
        if c not in CASES:
            raise SystemExit('未知 case %s（可选 %s）' % (c, list(CASES)))
    backup_all()
    print('已备份 src/data/factory_*.bin → %s\n' % os.path.relpath(BAK, ROOT))
    recs = []
    try:
        for c in todo:
            recs.append(one_case(c, CASES[c]))
    finally:
        restore_all()
        print('最终恢复完成。')
    print('=' * 92)
    print('%-10s %-8s %-12s %-20s %s' % ('case', 'rc', 'size', 'sha256(前16)', '备注'))
    for r in recs:
        note = ''
        if r.get('repro'):
            note = '可复现✓'
        elif r['case'] == 'base':
            note = '★ 可复现性不一致（见下）'
        bad = [c[0] for c in r.get('checks', []) if not c[4]]
        if bad:
            note += '  ★★假绿: ' + ','.join(bad)
        print('%-10s %-8s %-12s %-20s %s'
              % (r['case'], r['rc'], r.get('size', '-'), (r.get('sha', '-') or '-')[:16], note))
    return 0


if __name__ == '__main__':
    sys.exit(main())
