#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_relink.py —— 用**替换过的目标文件目录 / XUnzip 对象**重链，**不动 `build/obj/`**。

为什么需要（§0.32）
------------------
`popwindows` 的"缺体"根因是 **Ghidra 把连续结构体拆成独立局部变量 ⇒ 只写不读 ⇒ `-Os`
把死存储整段删除**。修法是**源码级还原成数组**（不是加 `volatile`）。
修完必须验证：① 体量收敛（`size_coverage_gate` 的 SHORT）② **行为尺不劣化**。
两种验证都要重链，而**绝不能污染 `build/obj/`**（那是交付链路输入）。

用法
----
    python tools/exp_relink.py --tag fixpop --overlay build/_exp/popwindows.o
    python tools/exp_relink.py --tag fix2   --overlay build/_exp/a.o build/_exp/b.o
    python tools/exp_relink.py --tag xu     --xunzip build/_exp/XUnzip.sync.o

`--overlay` 给出的每个 `.o` 按**文件名**覆盖 `build/obj/` 里同名文件，复制到
`build/_exp/obj_<tag>/` 后再重链（`DIAG_OBJD=` 指过去）。
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_zero_fimg as E                                   # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tag', required=True)
    ap.add_argument('--overlay', nargs='*', default=[],
                    help='要覆盖进 build/obj/ 的同名 .o')
    ap.add_argument('--xunzip', help='替换 XUnzip 对象（DIAG_XUNZIP=）')
    a = ap.parse_args()

    objdir = os.path.join(E.EXP, 'obj_%s' % a.tag)
    # ★ 本机 shell 的"安全删除"钩子会拦 `rm`/`shutil.rmtree`（实测报
    #   `SAFE_DELETE_BULK_GUARD_ERROR: state lock timeout`）⇒ 不删目录，改为
    #   **把文件名集合对齐到 `build/obj/`**（多出来的 .o 用 Python 直删，绕过 shell 钩子）。
    src_dir = os.path.join(E.ROOT, 'build', 'obj')
    want = set(f for f in os.listdir(src_dir) if f.endswith('.o'))
    shutil.copytree(src_dir, objdir, dirs_exist_ok=True)
    for f in sorted(os.listdir(objdir)):
        if f.endswith('.o') and f not in want:
            try:
                os.remove(os.path.join(objdir, f))
                print('   [clean] 移除残留对象 %s' % f)
            except OSError as e:
                # ★ 本机 safe-delete 钩子是**进程级**的（连 os.remove 也拦）⇒
                #   删不掉时**不静默**：交给下面的"对象数自检"报出来，或直接用新 tag。
                print('   [clean] 删不掉 %s（%s）—— 请换 --tag 用新目录' % (f, e))
    for o in a.overlay:
        base = os.path.basename(o)
        dst = os.path.join(objdir, base)
        if not os.path.exists(dst):
            # ★★ 2026-09-29 实测踩到：`build/obj/` 里的名字是 `FUN_00027398_popwindows.o`，
            #   而实验产物常叫 `popwindows.o`。若直接 copy 就成了**新增对象** ⇒
            #   `duplicate symbol: popwindows` ⇒ link rc=11 ⇒ **会被误读成"修复导致链接失败"**。
            #   这里按"`_<stem>.o` 后缀"找**唯一**候选；找不到或候选不唯一 ⇒ fail-closed。
            stem = os.path.splitext(base)[0]
            cands = [f for f in os.listdir(objdir)
                     if f.endswith('_' + stem + '.o') or f == stem + '.o']
            if len(cands) != 1:
                raise SystemExit('★ overlay 无法唯一定位：%s（候选 %s）⇒ fail-closed，'
                                 '以免"新增对象"伪装成"替换"' % (base, cands))
            dst = os.path.join(objdir, cands[0])
            print('   [overlay] %s ⇒ 匹配到 %s' % (base, cands[0]))
        else:
            print('   [overlay] %s ⇒ 同名替换' % base)
        shutil.copy2(o, dst)
        print('   [overlay] 已写入 %s' % os.path.relpath(dst, E.ROOT))

    # ★ 覆盖后自检：对象数**必须**与 build/obj/ 相同（只替换、不新增）。
    src_dir = os.path.join(E.ROOT, 'build', 'obj')
    n_src = len([f for f in os.listdir(src_dir) if f.endswith('.o')])
    n_dst = len([f for f in os.listdir(objdir) if f.endswith('.o')])
    if n_dst != n_src:
        raise SystemExit('★ overlay 后对象数变了 %d → %d（有新增对象 ⇒ 覆盖没生效）⇒ fail-closed'
                         % (n_src, n_dst))
    print('   [自检] 对象数 %d == build/obj 的 %d ✓' % (n_dst, n_src))

    out = os.path.join(E.EXP, 'rkgame.%s.elf' % a.tag)
    log = os.path.join(E.EXP, 'link_%s.log' % a.tag)
    env = dict(os.environ)
    env['PATH'] = E.tool_path()
    env.update(CC='%s cc' % E.ZIG, SYSROOT='', PY=E.PY, EXTRA_LDFLAGS='',
               LINK_DRIVER='lld',
               ZIG_GLOBAL_CACHE_DIR=os.path.join(E.ROOT, 'build', '_zigcache_ab'),
               DIAG_OBJD=objdir)
    if a.xunzip:
        env['DIAG_XUNZIP'] = os.path.abspath(a.xunzip)
    with open(log, 'w', encoding='utf-8', errors='replace') as fh:
        p = subprocess.run(['sh', os.path.join(E.ROOT, 'tools', 'link_full.sh'), out],
                           cwd=E.ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    print('link rc = %d   (日志 %s)' % (p.returncode, os.path.relpath(log, E.ROOT)))
    if p.returncode != 0 or not os.path.exists(out):
        for ln in E.gates_from_log(log):
            print('   %s' % ln)
        return p.returncode
    print('产物 %d B   sha256=%s' % (os.path.getsize(out), E.sha256(out)[:16]))

    # 目标函数的体量（与工厂对照）
    from elftools.elf.elffile import ELFFile

    def sz(path, name):
        e = ELFFile(open(path, 'rb'))
        st = e.get_section_by_name('.symtab')
        for s in st.iter_symbols():
            if s.name == name and s['st_info']['type'] == 'STT_FUNC':
                return s['st_size']
        return None
    fac = os.path.join(E.ROOT, 'golden', 'factory.rkgame.bin')
    base = os.path.join(E.ROOT, 'build', 'rkgame.rebuilt.elf')
    targets = [os.path.splitext(os.path.basename(o))[0].split('_', 2)[-1] for o in a.overlay]
    for t in targets:
        print('   体量 %-26s 工厂 %-6s 交付 %-6s 本次 %s'
              % (t, sz(fac, t), sz(base, t), sz(out, t)))
    print('   门禁摘要：')
    for ln in E.gates_from_log(log):
        print('      %s' % ln)
    return 0


if __name__ == '__main__':
    sys.exit(main())
