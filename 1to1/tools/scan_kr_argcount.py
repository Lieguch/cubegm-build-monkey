#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""K&R 空参声明的「漏参」机械对账 —— 以**工厂反汇编**为权威（技能铁律 105）。

为什么需要（2026-09-17 实测事故）：
  `src/compat/proto.h` 里 107 个函数被写成 K&R 空参声明（`extern gh_u4 mxmlLoadFile();`），
  于是调用点漏参**编译器不报错**；ARM 上被漏掉的参数就是**寄存器里的垃圾**
  ⇒ "同一二进制在不同场景下崩/不崩"的幽灵故障：
    · `mxmlLoadFile(0,fp)` 漏第 3 参 `cb`（类型推断回调）
      ⇒ `mxml_load_data` 内 `blx r10`，r10 = 0x3a / 0x00（随场景漂移）。
    · `mxmlDelete()` 一个实参都没传。
  这一类缺陷静态（源码层）完全看不出来，只会在跑到那一行时炸，而且崩点漂移。

权威来源选择（踩过的坑）：
  · Ghidra per-function 的 `/* name(args) */` 注释**只有极少数文件有** ⇒ 已实测不可用（零交集）；
  · Ghidra 渲染的函数签名本身也**不可信**（`mxmlLoadFile()` 就是被渲染成 0 参的）；
  · ⇒ 唯一权威 = **工厂机器码**：数每个 `bl <目标>` 之前有多少个参数寄存器（r0..r3）被写过。
    实测样例（手工核对过）：工厂 `mxmlLoadFile` 的每处调用都是
    `mov r2,#0` / `mov r1,fp` / `mov r0,#0` ⇒ 3 参 —— 与我们源码的 2 参不一致，即本次缺陷。

自证（铁律 101）：工具内置**三个手工核对过的锚点**（mxmlLoadFile=3 / mxmlDelete=1 /
mxmlSaveFile=3），跑之前先断言反汇编解析器能把它们量对；量不对就拒绝出结论。

用法：python tools/scan_kr_argcount.py [--root .] [--fa golden/factory.rkgame.bin]
退出码 0 = 无漏参；1 = 有漏参；2 = 工具自证失败（不算通过）。
"""
import argparse
import glob
import os
import re
import subprocess
import sys

PROTO = 'src/compat/proto.h'
SRC_DIR = 'src/proprietary'

# ---- 自证锚点：手工用机器码核对过的真实参数个数（见模块 docstring）----
ANCHORS = {'mxmlLoadFile': 3, 'mxmlDelete': 1, 'mxmlSaveFile': 3}


def find_objdump(explicit=None):
    """objdump 可能不在 PATH（Windows/Git Bash 下实测）⇒ 显式发现，而不是让 subprocess 崩掉。"""
    import shutil
    if explicit:
        return explicit
    # ★ 实测踩坑（2026-09-17，CI）：Ubuntu 的 `/usr/bin/objdump` 对本工程这类 ARM32 ELF
    #   会直接报 `can't disassemble for architecture UNKNOWN`（`-t` 能读，`-d` 不行）。
    #   workflow 里已装 `arm-linux-gnueabihf-objdump` ⇒ 优先用之；否则用 `objdump -m arm` 兜底。
    for name in ('arm-linux-gnueabihf-objdump', 'arm-none-eabi-objdump'):
        c = shutil.which(name)
        if c:
            return c
    c = shutil.which('objdump')
    if c:
        return c
    for cand in (r'C:/Program Files/Git/usr/bin/objdump.exe',
                 r'C:/Program Files (x86)/Git/usr/bin/objdump.exe',
                 r'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin/objdump.exe',
                 r'C:/objdump', r'/c/objdump',
                 '/usr/bin/objdump', r'C://objdump', r'C:/objdump'):
        if os.path.exists(cand):
            return cand
    return 'objdump'


def symtab(elf, objdump='objdump'):
    out = subprocess.run([objdump, '-t', elf], capture_output=True, text=True).stdout
    m = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) >= 6 and p[2] == 'F' and p[1].isdigit() or (len(p) >= 6 and 'F' in line and p[1] == 'F'):
            pass
        # 形如: 002c1f7c g     F .text	0000002c              mxmlLoadFile
        if len(p) == 6 and p[1] in 'glw' and p[2] == 'F':
            try:
                m[p[5]] = int(p[0], 16)
            except ValueError:
                pass
    return m


def disasm(elf, out_path, objdump='objdump'):
    """生成/复用反汇编缓存。

    ★★ 实测事故（2026-09-17）：objdump 不存在时 `open(out_path,'w')` **已经创建了空文件**，
    随后 mtime 比 ELF 新 ⇒ 后续运行把它当"有效缓存"复用 ⇒ 量到 0 处调用、锚点全部失败。
    这正是"仪器静默降级"的典型形态。故这里**必须校验产物非平凡**，否则强制重生成。"""
    need = True
    if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(elf):
        try:
            if os.path.getsize(out_path) > 1_000_000:      # 工厂 ~758k 行 ⇒ >1MB 才算有效
                need = False
        except OSError:
            need = True
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    if need:
        tmp = out_path + '.tmp'
        r = None
        for extra in ([], ['-m', 'arm']):      # ★ 兜底：宿主 objdump 不支持 ARM 时显式指定
            with open(tmp, 'w', encoding='utf-8') as f:
                r = subprocess.run([objdump, '-d', '--no-show-raw-insn'] + extra + [elf],
                                   stdout=f, stderr=subprocess.PIPE, text=True)
            if r.returncode == 0 and os.path.getsize(tmp) > 1_000_000:
                break
        if r.returncode != 0 or os.path.getsize(tmp) < 1_000_000:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise SystemExit('  [FATAL] objdump 反汇编失败（objdump=%s, rc=%d）：%s'
                             '  ⇒ 请安装 arm-linux-gnueabihf-objdump 或改用支持 ARM 的 objdump'
                             % (objdump, r.returncode, (r.stderr or '')[:200]))
        os.replace(tmp, out_path)
    return out_path


PAT_CALL = re.compile(r'^\s*([0-9a-f]+):\s+bl\s+([0-9a-f]+)\s*<')
PAT_INS = re.compile(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$')


def build_call_index(dis_path):
    """一次扫过反汇编，建 target_addr -> [行号] 的索引。

    ★ 性能：工厂反汇编 ~758k 行；若每个函数都重扫一遍（35 个函数）要 2600 万行次，
    在 CI 上是几十秒的浪费且容易触发超时。一次建索引 = 单次线性。"""
    idx = {}
    for i, l in enumerate(open(dis_path, encoding='utf-8', errors='replace')):
        m = PAT_CALL.match(l)
        if m:
            idx.setdefault(int(m.group(2), 16), []).append(i)
    return idx, open(dis_path, encoding='utf-8', errors='replace').read().splitlines()


def factory_arity(lines, call_index, fa_addr):
    """工厂里对 fa_addr 的每处 bl，回溯数 r0..r3 中被写过的个数，取最大值。"""
    pat_ins = PAT_INS
    idx = call_index.get(fa_addr, [])
    best = 0
    for i in idx:
        regs = set()
        for j in range(i - 1, max(-1, i - 12), -1):
            m = pat_ins.match(lines[j])
            if not m:
                continue
            mn, ops = m.group(2), m.group(3)
            # ★ 控制流边界：任何分支（b/bl/bx/beq/bne/ble/...）或带 pc/lr 的 push/pop
            #   都会切断"参数寄存器由哪条指令设置"的直线推理 ⇒ 停止回溯。
            #   实测教训：不切边界时，mxmlDelete（1 参）会被量成 3 参（越界吃到上一个调用的 r1/r2）。
            if mn.startswith('b'):
                break
            if mn in ('push', 'pop') and ('pc' in ops or 'lr' in ops):
                break
            tgt = None
            mm = re.match(r'(r[0-9]+)', ops)
            if mm:
                tgt = mm.group(1)
            if tgt in ('r0', 'r1', 'r2', 'r3'):
                if mn in ('mov', 'movw', 'movt', 'ldr', 'adr', 'add', 'sub', 'orr', 'mvn', 'movs'):
                    regs.add(tgt)
        best = max(best, len(regs))
    return best, len(idx)


def parse_kr_names(proto_path):
    s = open(proto_path, encoding='utf-8', errors='replace').read()
    return set(re.findall(r'extern\s+[A-Za-z_][\w \*]*?\b([A-Za-z_]\w*)\s*\(\s*\)\s*;', s))


def strip_comments_and_strings(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    s = re.sub(r'//[^\n]*', ' ', s)
    s = re.sub(r'"(\\.|[^"\\])*"', '""', s)
    s = re.sub(r"'(\\.|[^'\\])*'", "''", s)
    return s


def count_args(argstr):
    argstr = argstr.strip()
    if argstr == '':
        return 0
    depth = 0
    n = 1
    for ch in argstr:
        if ch in '([{':
            depth += 1
        elif ch in ')]}':
            depth -= 1
        elif ch == ',' and depth == 0:
            n += 1
    return n


def scan_calls(root, names):
    out = []
    pats = {n: re.compile(r'(?<![A-Za-z0-9_])' + re.escape(n) + r'\s*\(') for n in names}
    for p in glob.glob(os.path.join(root, SRC_DIR, '**', '*.c'), recursive=True):
        code = strip_comments_and_strings(open(p, encoding='utf-8', errors='replace').read())
        for n, pat in pats.items():
            for m in pat.finditer(code):
                i = m.end()
                depth, j = 1, i
                while j < len(code) and depth > 0:
                    if code[j] == '(':
                        depth += 1
                    elif code[j] == ')':
                        depth -= 1
                    j += 1
                if depth != 0:
                    continue
                args = code[i:j - 1]
                if len(args) > 400:
                    continue
                # 跳过函数定义（形如 "void foo(void) {" ——以 '{' 收尾的 0 参定义）
                tail = code[j:j + 3]
                if args.strip() in ('void', '') and '{' in tail:
                    continue
                out.append((n, p, count_args(args)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--fa', default='golden/factory.rkgame.bin')
    ap.add_argument('--objdump', default=None, help='objdump 路径（Windows/Git Bash 下可能不在 PATH）')
    ap.add_argument('--pending', default=None,
                    help='已知待修台账（每行 "name factory_arity"）：其中的违例计为台账项、不判失败；'
                         '**新增**违例一律判失败（棘轮语义）')
    ap.add_argument('--write-pending', action='store_true', help='把当前违例写成台账后退出 0')
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    fa = os.path.join(root, a.fa)
    if not os.path.exists(fa):
        print('  [SKIP] 无金标准二进制 %s ⇒ 跳过（CI 上须存在）' % fa)
        return 0
    od = find_objdump(a.objdump)
    print('  objdump = %s' % od)
    dis = disasm(fa, os.path.join(root, 'build', '_fa_dis_kr.txt'), od)
    sym = symtab(fa, od)
    CALLIDX, LINES = build_call_index(dis)

    # ---- 自证：锚点必须量对 ----
    for n, want in ANCHORS.items():
        if n not in sym:
            print('  [FATAL] 自证失败：工厂符号表里没有锚点 %s' % n)
            return 2
        got, ncalls = factory_arity(LINES, CALLIDX, sym[n])
        if got != want:
            print('  [FATAL] 自证失败：锚点 %s 量到 %d 参（期望 %d，%d 处调用）'
                  ' ⇒ 反汇编参数识别器不可信，拒绝出结论' % (n, got, want, ncalls))
            return 2
    print('  自证通过（锚点 %s 全部量对）'
          % ', '.join('%s=%d' % (k, v) for k, v in ANCHORS.items()))

    kr = parse_kr_names(os.path.join(root, PROTO))
    calls = scan_calls(root, kr)
    if len(kr) < 20 or len(calls) < 50:
        print('  [FATAL] 自证失败：K&R 声明 %d / 调用点 %d（阈值 20/50）' % (len(kr), len(calls)))
        return 2

    ours = {}
    for n, p, argc in calls:
        ours.setdefault(n, {'max': 0, 'sites': []})
        ours[n]['max'] = max(ours[n]['max'], argc)
        ours[n]['sites'].append((argc, os.path.relpath(p, root)))

    bad, checked = [], 0
    for n, info in sorted(ours.items()):
        if n not in sym:
            continue
        want, ncalls = factory_arity(LINES, CALLIDX, sym[n])
        if want == 0 or ncalls == 0:
            continue
        checked += 1
        if info['max'] < want:
            low = sorted([s for s in info['sites'] if s[0] < want])
            bad.append((n, want, info['max'], ncalls, low[0] if low else info['sites'][0]))

    print('  K&R 声明 %d 条 / 我们源码调用点 %d 个 / 可对账函数 %d 个'
          % (len(kr), len(calls), checked))
    pend = set()
    if a.pending and os.path.exists(a.pending):
        for ln in open(a.pending, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                pend.add(tuple(ln.split()[:2]))

    if a.write_pending:
        with open(a.pending or 'tools/kr_argcount_pending.txt', 'w', encoding='utf-8', newline='\n') as f:
            f.write('# K&R 漏参·已知待修台账（棘轮）。格式: <函数名> <工厂真实参数>\n')
            f.write('# 新增违例不在本台账内 ⇒ 门禁直接失败。修好一项就删一行。\n')
            for n, want, got, ncalls, _ in bad:
                f.write('%s %d\n' % (n, want))
        print('  已写入台账：%d 项' % len(bad))
        return 0

    known = [b for b in bad if (b[0], str(b[1])) in pend]
    new_ = [b for b in bad if (b[0], str(b[1])) not in pend]
    if known:
        print('  台账内已知待修：%d 项（不判失败，但必须逐项修并删行）' % len(known))
    if new_:
        print('  ★★ 新增漏参 %d 个函数（不在台账内 ⇒ 判失败）：' % len(new_))
        for n, want, got, ncalls, (lowa, lowp) in new_:
            print('     %-30s 工厂 %d 参 / 我们最多 %d 参  (工厂 %d 处调用；最少处: %s)'
                  % (n, want, got, ncalls, lowp))
        return 1
    if not known:
        print('  ✓ 未发现漏参（台账亦为空）')
    else:
        print('  ✓ 无新增漏参（台账剩余 %d 项待修）' % len(known))
    return 0


if __name__ == '__main__':
    sys.exit(main())
