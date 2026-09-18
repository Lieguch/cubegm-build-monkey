#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_implicit_decl.py —— 「调用点缺原型」硬门禁（编译器真值口径）。

## 为什么需要它（2026-09-18 第 47 轮，真实缺陷，机器码级已定案）

`mui_outputxy_t` / `mui_outputxy_length.isra.19` 调用了
`stbtt_GetCodepointBitmapBoxSubpixel` / `stbtt_MakeCodepointBitmapSubpixel` /
`stbtt_GetCodepointHMetrics`，而 `src/compat/proto.h` 里**没有它们的原型**。

C 的隐式声明让调用点按**默认实参提升**传参：

  · `float` 实参被提升为 **double**（我们机器码里可见 `vcvt.f64.f32`）⇒ 落进 d0/d1/d2，
    而真函数按 `s0..s3` 读 float ⇒ **全部错位**；
  · 指针实参 `font` 被排到第 5 个位置 ⇒ **`r0` 从未被设置** ⇒ 被调者入口 r0 = 0；
  · 于是 `stbtt_FindGlyphIndex` 的 `ldr r4,[r0,#4]`（= `info->data`）
    **故障地址恰为 0x4**，pc = `stbtt_FindGlyphIndex+0x8`，lr = `stbtt_GetCodepointBitmapBoxSubpixel+0x2C`
    —— 与崩溃现场逐位吻合。

⇒ 铁律：**调用点缺原型不是"一个警告而已"，是 ABI 级错位。**

## 口径选择：为什么用编译器真值而不是源码启发式

源码启发式（"扫描 `name(` 再查是否声明过"）要维护巨量的白名单（libc/上游/宏），
必然假阳性。而**编译器的判断就是真值**：一条 `-fsyntax-only` 就能给出"这个 TU 里有
哪些调用没有可见原型"。代价是每个文件一次语法检查（无 codegen，很快）。

## 自证（两级，正负双向）

  ① 正向：临时 TU 里写 `zz_undeclared_probe_47(1.0f);` ⇒ **必须**被检出；
  ② 负向：临时 TU 里先 `extern void zz_declared_probe_47(float);` 再调用 ⇒ **必须不**被检出。
  两条都过，才认为本仪器可信（否则 FATAL 退出，拒绝出结论）。

## 台账棘轮

`--ledger` 指定的文件列出已知项（每行一个函数名）。**新增即失败**；
台账项消失只告警（提示删行，避免"源码已修但 CI 用的是旧账"造成假红）。
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile

# clang 措辞随版本变化：旧版 "implicit declaration of function 'X'"，
# clang >= 16 改为 "call to undeclared function 'X'"（且默认是 error）。
PAT_UN = re.compile(r"call to undeclared function '([A-Za-z_]\w*)'")
PAT_IM = re.compile(r"implicit declaration of function '([A-Za-z_]\w*)'")

SELF_UN = 'zz_undeclared_probe_47'
SELF_OK = 'zz_declared_probe_47'


def find_zig(explicit=None):
    """定位 zig（CI 上由 pip 装在 site-packages、**不在 PATH**）。"""
    import shutil
    if explicit:
        return explicit
    c = shutil.which('zig')
    if c:
        return c
    try:
        import ziglang
        p = os.path.join(os.path.dirname(ziglang.__file__), 'zig')
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return 'zig'


def cc_flags(root):
    """与 CI 门禁同一套 include/目标口径；**故意不带** -Wno-error=implicit-function-declaration，
    这样缺原型会以 error 形式出现，而不是靠告警文本匹配。"""
    return [
        '-fsyntax-only',
        '-target', 'arm-linux-gnueabihf',
        '-mfloat-abi=hard', '-mfpu=neon',
        '-I' + os.path.join(root, 'src', 'compat'),
    ]


def run_cc(zig, root, path):
    r = subprocess.run([zig, 'cc'] + cc_flags(root) + [path],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def parse_undeclared(text):
    names = set()
    for m in PAT_UN.finditer(text):
        names.add(m.group(1))
    for m in PAT_IM.finditer(text):
        names.add(m.group(1))
    return names


def scan(zig, root, jobs=None):
    """返回 {函数名: set(相对路径)}。

    ★ 并行（2026-09-18）：213 个文件串行 `-fsyntax-only` 实测 ~70s，而 GitHub Actions
      分钟数是有预算的。纯子进程负载 ⇒ 线程池即可（GIL 不构成瓶颈）。
    """
    from concurrent.futures import ThreadPoolExecutor
    found = {}
    base = os.path.join(root, 'src', 'proprietary')
    files = []
    for dp, _dn, fs in os.walk(base):
        for f in sorted(fs):
            if f.endswith('.c'):
                files.append(os.path.join(dp, f))
    if jobs is None:
        # ★ 默认并行度取 **4** 而非 8：实测 `--jobs 8` 在这台 Windows 机器上
        #   直接 `OSError [WinError 1455] 页面文件太小`（zig cc 单进程内存占用不小，
        #   8 个并发瞬间冲破提交内存）⇒ 后续运行全崩。CI 上更是共享 runner，取 4 更稳。
        jobs = min(4, (os.cpu_count() or 2) * 2)

    def one(p):
        """返回 (path, set|None)；**None 表示"该文件的结论未知"**。

        ★★ 绝不允许把"编译/派生失败"当作"无缺原型"：那会让门禁在不完整输入上给绿色，
          正是本项目反复吃亏的"仪器静默降级"。故失败必须向上冒泡并判 FATAL。
        """
        try:
            return p, parse_undeclared(run_cc(zig, root, p))
        except OSError:
            return p, None

    failed = []
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for p, names in ex.map(one, files):
            if names is None:
                failed.append(os.path.relpath(p, root).replace('\\', '/'))
                continue
            for n in names:
                found.setdefault(n, set()).add(
                    os.path.relpath(p, root).replace('\\', '/'))
    if failed:
        sys.exit('  [FATAL] %d 个文件未能完成语法检查（结论未知 ⇒ 拒绝出结论）：%s'
                 % (len(failed), failed[:6]))
    return found, len(files)


def selfcheck(zig, root):
    """两级自证：正向必须抓到未声明调用；负向必须不抓已声明调用。"""
    d = tempfile.mkdtemp(prefix='cgm_imp_')
    bad = os.path.join(d, 'probe_bad.c')
    good = os.path.join(d, 'probe_good.c')
    with open(bad, 'w', encoding='utf-8') as f:
        f.write('void t(void){ %s(1.0f); }\n' % SELF_UN)
    with open(good, 'w', encoding='utf-8') as f:
        f.write('extern void %s(float);\nvoid t(void){ %s(1.0f); }\n' % (SELF_OK, SELF_OK))
    gb = parse_undeclared(run_cc(zig, root, bad))
    gg = parse_undeclared(run_cc(zig, root, good))
    ok1 = SELF_UN in gb
    ok2 = SELF_OK not in gg
    print('  [selfcheck-1] 正向样本 %-24s -> %s' % (SELF_UN, '被检出 ✓' if ok1 else '未检出 ✗'))
    print('  [selfcheck-2] 负向样本 %-24s -> %s' % (SELF_OK, '未被检出 ✓' if ok2 else '被误报 ✗'))
    if not (ok1 and ok2):
        sys.exit('  [FATAL] 自证失败 ⇒ 仪器不可信，拒绝出结论')
    try:
        os.remove(bad)
        os.remove(good)
        os.rmdir(d)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--zig', default=None)
    ap.add_argument('--ledger', default=None)
    ap.add_argument('--write-ledger', action='store_true')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--no-selfcheck', action='store_true')
    ap.add_argument('--jobs', type=int, default=None, help='并行度（默认 min(8, cpu*2)）')
    a = ap.parse_args()

    root = a.root
    if not os.path.isdir(os.path.join(root, 'src', 'proprietary')):
        print('  [SKIP] 找不到 %s/src/proprietary' % root)
        return 0
    zig = find_zig(a.zig)
    print('  zig = %s' % zig)

    if not a.no_selfcheck:
        selfcheck(zig, root)

    found, nf = scan(zig, root, a.jobs)
    names = sorted(found)
    print()
    print('  已语法检查 %d 个 .c；检出「调用点缺原型」的函数 %d 个' % (nf, len(names)))
    for n in names[:a.top]:
        fl = sorted(found[n])
        print('     %-34s %d 个文件  （例：%s）' % (n, len(fl), fl[0]))
    if len(names) > a.top:
        print('     ...（共 %d 个）' % len(names))

    if a.write_ledger:
        path = a.ledger or 'tools/implicit_decl_pending.txt'
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 「调用点缺原型」已知项台账（棘轮）。格式: <函数名>' + '\n')
            f.write('# 背景：隐式声明 ⇒ 默认实参提升 ⇒ float 按 double 传、指针寄存器错位。' + '\n')
            f.write('# 逐项在 proto.h（或对应头）补真原型，改好一项**删一行**。' + '\n')
            for n in names:
                f.write(n + '\n')
        print()
        print('  已写入台账：%d 项（%s）' % (len(names), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend = set()
        for ln in open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                pend.add(ln)
        newv = [n for n in names if n not in pend]
        gone = sorted(pend - set(names))
        if gone:
            print()
            print('  ★ 台账条目已消失（= 已补原型）⇒ 请删除以下行以保持棘轮语义：')
            for n in gone:
                print('     %s' % n)
        if newv:
            print()
            print('  ★★ 新增「调用点缺原型」%d 个（不在台账内 ⇒ 判失败）：' % len(newv))
            for n in newv[:a.top]:
                print('     %-34s %s' % (n, sorted(found[n])[0]))
            return 1
        print()
        print('  [PASS] 无新增缺原型调用（台账剩余 %d 项）' % len(pend))
        return 0

    if names:
        print()
        print('  [FAIL] 存在 %d 个缺原型调用（未提供台账 ⇒ 从严判失败）' % len(names))
        return 1
    print()
    print('  ✓ 全部调用点均有可见原型')
    return 0


if __name__ == '__main__':
    sys.exit(main())
