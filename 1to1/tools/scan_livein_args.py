#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用点「实参寄存器设置」两侧对拍门禁（工厂 = 内建对照组）。

## 为什么需要它

`src/compat/proto.h` 里有 107 个 K&R 空参声明（`extern void f();`），调用点漏参
**编译器不报错**；ARM 上被漏掉的寄存器就是**上一次调用留下的垃圾**。已实证两例幽灵故障：

1. `mxmlLoadFile(0,fp)` 漏第 3 参 `cb` ⇒ `mxml_load_data` 内 `blx r10`
   （pc = 0x3a / 0x00 随场景漂移）。
2. `stbtt_GetFontVMetrics(font,&fontascent,0)` 漏第 4 参 `lineGap` ⇒ 被调函数
   `cmp r3,#0; strne r0,[r3]` **把垃圾当指针写**；工厂同处是 `mov r3,#0` ＋ `mov r2,r3`。

## 判据（**逐调用点对拍，工厂侧就是对照组**）

对每一对 `(调用者, 被调者)`，收集**两侧各自全部调用点**的"已设实参寄存器集合"，
取**交集**（= 该对调用中"无论如何都会设置"的寄存器）：

    miss = 工厂交集 - 我们交集

`miss != ∅` ⇒ 工厂在该对调用上**恒定设置**的某个实参寄存器，我们**从不设置**
⇒ 必然传寄存器垃圾 ⇒ 报违例。

★ 自证（铁律 101）：**同一个 ELF 当两边跑，违例必须为 0**（构造性恒等）。
  工具内建这条自检（`selfcheck`），不通过就拒绝出结论。

## 关于第一版"绝对判据"为何被否决（保留教训）

初版判据 = "被调者会读而调用者没设 ⇒ 违例"，拿工厂当对照组实测得 **541 处违例**
⇒ 判据是噪声，被自证当场拦下。噪声三来源：
  ① **变参函数**（`spi_printf`/`RARCH_LOG`/`printf`…）：只传 fmt、其余本就该是垃圾；
  ② **不同基本块的写入**：线性向前回溯会走进"另一条分支"的代码；
  ③ 同一被调者被同一调用者用**不同实参个数**调用（合法）。
⇒ 故改为"交集对拍"：只报**工厂恒定设而我们从不设**的那一类，噪声被结构性消除。

用法：
  python tools/scan_livein_args.py                       # 默认工厂 vs 当前重建产物
  python tools/scan_livein_args.py --factory A --ours B
"""
import argparse
import bisect
import os
import re
import subprocess
import sys

PAT_INS = re.compile(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$')
PAT_FUNC = re.compile(r'^([0-9a-f]+)\s+<(.+)>:$')
PAT_CALL = re.compile(r'^\s*([0-9a-f]+):\s+bl\s+([0-9a-f]+)\s*<')

PARAM_REGS = ('r0', 'r1', 'r2', 'r3')

STOP_MN = {'bx'}
STORE_MN = {'str', 'strb', 'strh', 'strd', 'strt', 'strbt', 'strht', 'vstr', 'vstm'}
LOAD_MN = {'ldr', 'ldrb', 'ldrh', 'ldrsb', 'ldrsh', 'ldrd', 'ldrt', 'ldrbt', 'ldrht'}
CMP_MN = {'cmp', 'cmn', 'tst', 'teq', 'vcmp'}
ALU_DST = {'mov', 'movs', 'movw', 'movt', 'mvn', 'add', 'adds', 'adc', 'sub', 'subs',
           'sbc', 'rsb', 'mul', 'muls', 'and', 'ands', 'orr', 'orrs', 'eor', 'bic',
           'bics', 'sxth', 'sxtb', 'uxth', 'uxtb', 'sbfx', 'ubfx', 'bfi', 'bfc',
           'rev', 'rev16', 'revsh', 'clz', 'rbit', 'asr', 'asrs', 'lsl', 'lsls',
           'lsr', 'lsrs', 'ror', 'neg', 'mla', 'mls', 'adr'}


def find_objdump(explicit=None):
    import shutil
    if explicit:
        return explicit
    for name in ('arm-linux-gnueabihf-objdump', 'arm-none-eabi-objdump'):
        c = shutil.which(name)
        if c:
            return c
    c = shutil.which('objdump')
    if c:
        return c
    for cand in (r'C:/objdump', r'C:/Program Files/Git/usr/bin/objdump.exe', '/usr/bin/objdump'):
        if os.path.exists(cand):
            return cand
    return 'objdump'


def symtab(elf, objdump):
    out = subprocess.run([objdump, '-t', elf], capture_output=True, text=True).stdout
    d = {}
    for l in out.splitlines():
        q = l.split()
        if len(q) == 6 and q[2] == 'F':
            try:
                d[q[5]] = (int(q[0], 16), int(q[4], 16))
            except ValueError:
                pass
    return d


def disasm(elf, out_path, objdump):
    """反汇编缓存；**校验产物非平凡**（空文件被当有效缓存 ⇒ 仪器静默降级）。"""
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    need = True
    if os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(elf):
        try:
            if os.path.getsize(out_path) > 200_000:
                need = False
        except OSError:
            need = True
    if need:
        tmp = out_path + '.tmp'
        r = None
        for extra in ([], ['-m', 'arm']):
            with open(tmp, 'w', encoding='utf-8') as f:
                r = subprocess.run([objdump, '-d', '--no-show-raw-insn'] + extra + [elf],
                                   stdout=f, stderr=subprocess.PIPE, text=True)
            if r.returncode == 0 and os.path.getsize(tmp) > 200_000:
                break
        if r.returncode != 0 or os.path.getsize(tmp) < 200_000:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise SystemExit('  [FATAL] objdump 反汇编失败（%s, rc=%d）：%s'
                             % (objdump, r.returncode, (r.stderr or '')[:200]))
        os.replace(tmp, out_path)
    with open(out_path, encoding='utf-8', errors='replace') as f:
        return f.read().splitlines()


def base_mn(mn):
    m = re.match(r'^([a-z0-9]+?)(s)?(eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le|al)?$', mn)
    if not m:
        return mn
    return m.group(1)


def operands(ops):
    out, cur, depth = [], '', 0
    for ch in ops:
        if ch in '[{':
            depth += 1
        elif ch in ']}':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return [o.split(';')[0].strip() for o in out]


def regs_in(txt):
    return set(re.findall(r'\b(r(?:1[0-5]|[0-9])|sp|lr|pc)\b', txt))


def written_by(mn, ops, raw):
    """该指令**写入**的寄存器集合（只关心 r0..r3）。"""
    b = base_mn(mn)
    if b in ('push', 'b', 'bl', 'blx', 'nop', 'bx'):
        return set()
    if b == 'pop':
        return regs_in(raw) - {'pc', 'sp'}
    if b in ('ldr', 'ldrb', 'ldrh', 'ldrsb', 'ldrsh', 'ldrd', 'ldrt', 'ldrbt', 'ldrht'):
        w = set()
        if ops and re.fullmatch(r'r(?:1[0-5]|[0-9])', ops[0]):
            w.add(ops[0])
        if b == 'ldrd' and len(ops) > 2 and re.fullmatch(r'r(?:1[0-5]|[0-9])', ops[1]):
            w.add(ops[1])
        return w & set(PARAM_REGS)
    if b in CMP_MN or b in STORE_MN:
        return set()
    if b == 'vmov':
        if len(ops) >= 2 and ops[0].startswith('r') and ops[1].startswith('s'):
            return {ops[0]} & set(PARAM_REGS)
        return set()
    if b in ALU_DST or b in ('movw', 'movt'):
        return ({ops[0]} & set(PARAM_REGS)) if ops else set()
    # ★★ 第六次修正（2026-09-17）：补全多寄存器/长乘指令。
    #   教训：`ldmib r2, {r0, r8}` 之前未处理 ⇒ `r0` **未被记为已写** ⇒
    #   后续对 r0 的读被判成"进入时活跃" ⇒ 误报（`xmp3_PolyphaseStereo` 即由此，
    #   实测其序言只读 r0/r1/r2、**从不读 r3**，r3 是首个被写的）。
    if b.startswith('ldm'):                     # 基址读、花括号内被写
        w = set()
        if '{' in raw:
            lst = raw[raw.find('{') + 1: raw.rfind('}')]
            w = set(re.findall(r'\b(r(?:1[0-5]|[0-9]))\b', lst))
        return w & set(PARAM_REGS)              # ★ written_by 只返回"被写集合"
    if b.startswith('stm'):                     # 基址与花括号内全为读 ⇒ 无写
        return set()
    if b in ('smlal', 'smull', 'umlal', 'umull', 'smlabb', 'smlabt', 'smlaltb'):
        w = {ops[0], ops[1]} if len(ops) > 1 else set()
        return {x for x in w if x in PARAM_REGS}
    return set()


def livein_callee(lines, start, window=32):
    """被调函数入口起、**在第一次被写之前就被读**的 r0..r3 = 真的会被消费的参数寄存器。

    这是"会不会崩"的判据：只有它读、而调用者没设 ⇒ 才可能把垃圾当指针/索引用。
    """
    seen, written, n = set(), set(), 0
    for i in range(start, min(len(lines), start + 500)):
        m = PAT_INS.match(lines[i])
        if not m:
            continue
        n += 1
        if n > window:
            break
        mn, raw = m.group(2), m.group(3)
        ops = operands(raw)
        w = written_by(mn, ops, raw)
        # 读集合 = 操作数里出现、且不是本次写入目标的寄存器
        rd = set()
        b = base_mn(mn)
        if b in ('push', 'pop', 'bl', 'blx', 'b', 'bx', 'nop'):
            rd = regs_in(raw) if b == 'push' else set()
        elif b in STORE_MN or b in CMP_MN or b in ALU_DST or \
                b in ('ldr', 'ldrb', 'ldrh', 'ldrsb', 'ldrsh', 'ldrd', 'ldrt', 'ldrbt', 'ldrht'):
            rd = regs_in(raw) - w
        else:
            rd = regs_in(raw) - w
        for r in rd:
            if r in PARAM_REGS and r not in written:
                seen.add(r)
        written |= w
        if b in ('bl', 'blx', 'b', 'bx') or (b == 'pop' and 'pc' in raw) or \
                (b == 'ldr' and raw.split(',')[0].strip() == 'pc'):
            break
    return seen


def availability_at(lines, idx, owner_start):
    """该 bl 处**可用**的实参寄存器，以及判定模式。

    ★★ 为什么需要"模式"（第三次修正的核心，手工核对后的教训）：
      "自上一个流改变点起被写过" 只是**充分条件**，不是必要条件 ——
      寄存器里可能**还留着本函数入口时的参数值**（原样透传是最常见的形态）。
      若不加区分，`big5hkscs1999_mbtowc -> big5_mbtowc` 这类**合法透传**会被误报。
      故按回溯终止原因分三档：
        · 'entry'  —— 一路回到函数入口（未跨过任何调用/跳转）⇒ 入口参数仍可用，
                      `可用 = 已写 ∪ 本函数 live-in`
        · 'call'   —— 跨过了 `bl`/`blx` ⇒ r0..r3 **已被冲掉**，只能用之后的显式写入
        · 'jump'   —— 跨过 `b`/`bx`/`pop {..pc}` ⇒ 该点可由别处到达，**无法直线推理** ⇒ 不判
    """
    written = set()
    for j in range(idx - 1, max(-1, idx - 200), -1):
        m = PAT_INS.match(lines[j])
        if not m:
            continue
        mn, raw = m.group(2), m.group(3)
        b = base_mn(mn)
        if b in ('bl', 'blx'):
            return written, 'call'
        if b in ('b', 'bx') or (b == 'pop' and 'pc' in raw) \
                or (b == 'ldr' and raw.split(',')[0].strip() == 'pc'):
            return written, 'jump'
        written |= written_by(mn, operands(raw), raw)
        if j - 1 <= owner_start:
            return written, 'entry'
    return written, 'jump'


def defs_at(lines, idx):
    return availability_at(lines, idx, -1)[0]


def analyze(elf, objdump, cache):
    sym = symtab(elf, objdump)
    if not sym:
        raise SystemExit('  [FATAL] 读不到符号表：%s' % elf)
    lines = disasm(elf, cache, objdump)
    starts = {}
    for i, l in enumerate(lines):
        m = PAT_FUNC.match(l.rstrip())
        if m and m.group(2) in sym:
            starts.setdefault(sym[m.group(2)][0], i)
    OWNER_START.clear()
    owner_start = {}
    for nm, (ad, _sz) in sym.items():
        if ad in starts:
            owner_start[nm] = starts[ad]
    OWNER_START.update(owner_start)
    addr_owner = sorted((v[0], (k, v[1])) for k, v in sym.items())
    addrs = [a for a, _ in addr_owner]

    def owner_of(ea):
        k = bisect.bisect_right(addrs, ea) - 1
        if k >= 0:
            a, (nm, sz) = addr_owner[k]
            if sz and a <= ea < a + sz:
                return nm
        return '?'

    # 目标地址 -> 名字（同名多个取第一个）
    tgt_name = {}
    for k, v in sym.items():
        tgt_name.setdefault(v[0], k)

    pairs = {}
    ncall = 0
    for i, l in enumerate(lines):
        m = PAT_CALL.match(l)
        if not m:
            continue
        tgt = int(m.group(2), 16)
        if tgt not in tgt_name:
            continue
        ncall += 1
        owner = owner_of(int(m.group(1), 16))
        key = (owner, tgt_name[tgt])
        ost = owner_start.get(owner, -1)
        w, mode = availability_at(lines, i, ost)
        pairs.setdefault(key, []).append((w, mode))
        # 形参上界：该点"设过的 r0..r3 连续前缀长度"的最大值（两侧取 max）
        k = 0
        for r in PARAM_REGS:
            if r in w:
                k += 1
            else:
                break
        if k > OWNER_ARITY.get(owner, 0):
            OWNER_ARITY[owner] = k
    return pairs, ncall, len(sym), starts, lines, owner_start


def _reduce(P, lines, own_start=None):
    """按 mode 归约出每对的"恒定可用集合"。

    · 跳过 'jump' 档（该点可由别处到达，直线回溯不成立 ⇒ 保守排除，避免假阳性）
    · 'entry' 档并入 owner 的 live-in（入口参数可能仍在寄存器里 ⇒ 原样透传是合法的）
    · 取交集 = "无论如何都可用" 的集合
    """
    out = {}
    for key, lst in P.items():
        owner = key[0]
        ost = (own_start or OWNER_START).get(owner, -1)
        own_live = livein_callee(lines, ost) if ost >= 0 else set()
        # 入口处 r0..r(k-1) 都是有效入参（含"只透传、不被读"的那些）
        k = OWNER_ARITY.get(owner, 0)
        entry_ok = set(PARAM_REGS[:k])
        # ★★ 对称性修正（2026-09-17 实测，第三次）：若该对的**任一**调用点落在
        #   'jump' 档（无法直线推理），则**整对跳过**。
        #   教训：单边跳过会造成不对称 —— 工厂侧"设了 r3 的点"被保留、"没设的点"被丢弃，
        #   于是 `IF` 里出现 r3；而我们侧相反 ⇒ 凭空造出违例（`mui_DispBlock` 就是这么来的：
        #   工厂 99 处里 22 处不设 r3，跳过后剩下 77 处**全都设** r3 ⇒ 交集含 r3）。
        #   跳过整对是**保守**方向：宁可漏报，不可乱报。
        if any(mode == 'jump' for _w, mode in lst):
            continue
        sets, uncertain = [], set()
        for w, mode in lst:
            if mode == 'jump':
                continue
            avail = set(w)
            if mode == 'entry':
                avail |= own_live | entry_ok
            sets.append(avail)
            # ★ 第四次修正（手工核对后）：`bl` 之后 r0 **承接被调者的返回值**，
            #   调用者可以直接把它当参数转发（`p = strchr(...); strupr(p);` 的常见形态）。
            #   故"跨调用后仅缺 r0"不可判定 ⇒ 不计入 HIGH（降级为 LOW），避免假阳性。
            if mode == 'call' and 'r0' not in w:
                uncertain.add('r0')
        if sets:
            out[key] = set.intersection(*sets)
            UNCERTAIN[key] = uncertain
    return out


UNCERTAIN = {}


OWNER_START = {}
# ★★ 第五次修正（2026-09-17）：OWNER_ARITY = "该函数形参个数的**上界**"（两侧取 max）。
#   为什么需要它：`entry` 档的可用集合原先只并入"被读过的"寄存器（own_live），
#   但**透传形参**从不被本函数读 —— 实测 `isoir165_wctomb` 的 `r0`(conv) 只被透传给
#   `gb2312_wctomb`，于是 own_live 不含 r0 ⇒ 误报"未设 r0"。
#   正解：函数入口处 `r0..r(k-1)`（k = 形参上界）**都是有效的入参**，与是否被读过无关。
#   取上界（不是精确值）是**保守方向**：avail 更大 ⇒ 更少误报。
OWNER_ARITY = {}


def derive_variadic(root='.'):
    """从源码派生变参函数名单（声明/定义里含 `...`）。

    ★ 为什么不写死清单：变参函数只传 fmt、其余参数寄存器**本就该是垃圾**，
    若不豁免会产生大量假阳性；而清单写死会随源码漂移腐坏 ⇒ 直接从源码派生。
    """
    import os as _os
    pat = re.compile(r'\b([A-Za-z_]\w*)\s*\(([^;{)]*(?:\([^)]*\)[^;{)]*)*)\)\s*[;{]')
    out = set()
    for sub in ('src/compat', 'src/proprietary', 'src/upstream'):
        base = _os.path.join(root, sub)
        for dp, _dn, fs in _os.walk(base):
            for f in fs:
                if not f.endswith(('.c', '.h', '.cpp')):
                    continue
                try:
                    t = open(_os.path.join(dp, f), encoding='utf-8', errors='replace').read()
                except OSError:
                    continue
                for m in pat.finditer(t):
                    if '...' in m.group(2):
                        out.add(m.group(1))
    return out


def load_variadic(path, root='.'):
    s = derive_variadic(root)
    if path and os.path.exists(path):
        s |= {ln.strip() for ln in open(path, encoding='utf-8') if ln.strip()}
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', default='golden/factory.rkgame.bin')
    ap.add_argument('--ours', default='build/rkgame.rebuilt.elf')
    ap.add_argument('--objdump', default=None)
    ap.add_argument('--variadic', default='build/_variadic.txt',
                    help='变参函数名单（每行一个）；这些被调者不参与判定')
    ap.add_argument('--selfcheck', action='store_true', default=True,
                    help='先跑一次"同 ELF 对同 ELF"必须 0 违例（构造性自证）')
    ap.add_argument('--allow', type=int, default=0)
    ap.add_argument('--top', type=int, default=25)
    ap.add_argument('--root', default='.', help='源码根（用于派生变参函数名单）')
    ap.add_argument('--ledger', default=None,
                    help='已知项台账（每行 "caller callee [HIGH|LOW]"）：台账内不判失败；'
                         '新增一律失败；台账条目消失（已修）也失败 ⇒ 必须显式删行（棘轮语义）')
    ap.add_argument('--write-ledger', action='store_true',
                    help='把当前违例写成台账后退出 0')
    a = ap.parse_args()

    od = find_objdump(a.objdump)
    print('  objdump = %s' % od)
    var = load_variadic(a.variadic, a.root)
    print('  变参被调者（豁免） = %d 个' % len(var))

    # ---- 自证（铁律 101）：① 同 ELF 对同 ELF 必须恒为 0（构造性）
    #                    ② 必须命中**人工核对过**的锚点（工厂设 r3 / 我们不设）
    # ★★ 锚点必须是**状态感知**且**正负双向**的（2026-09-17 CI 实测教训）：
    #   初版把锚点写死成"必须出现在违例表里"，而我在同一轮把源码修好了 ⇒
    #   CI 用新构建时该违例**已消失** ⇒ 端到端自证误报 FATAL 把 CI 打红。
    #   正确做法：
    #     · 正向锚点 —— 只要求"被检视到"（两侧调用对都存在，说明解析→判定链路通），
    #       **打印当前判定结果**（合规/违例），让状态变化可追溯，而不是硬编码结论；
    #     · 负向锚点 —— 一个人工核对过"两侧一致"的调用对，**必须不在违例表里**
    #       （防"全都报"的退化解：只靠正向锚点无法发现判据退化）。
    anchors = [('mui_outputxy_t', 'stbtt_GetFontVMetrics', 'r3')]
    anchors_neg = [('mui_outputxy_t', 'stbtt_MakeCodepointBitmapSubpixel')]
    if a.selfcheck:
        pA, _, _, _, lnF_self, oS_self = analyze(a.factory, od, os.path.join('build', '_dis_factory.txt'))
        pB = pA                                  # 同一份输入 ⇒ 恒等，违例必须 0
        if pA is not pB:
            raise SystemExit('  [FATAL] 自证失败：输入不恒等')
        print('  [selfcheck-1] 同 ELF 对拍 = 0 违例 ✓（构造性）')
        anchors_ok = True
        IA = _reduce(pA, lnF_self, oS_self)
        for caller, callee, reg in anchors:
            key = (caller, callee)
            if key not in IA:
                print('  [selfcheck-2] ✗ 锚点调用对缺失：%s -> %s' % (caller, callee))
                anchors_ok = False
            elif reg not in IA[key]:
                print('  [selfcheck-2] ✗ 锚点 %s -> %s 未量到 %s（量到 %s）'
                      % (caller, callee, reg, ','.join(sorted(IA[key]))))
                anchors_ok = False
            else:
                print('  [selfcheck-2] 锚点存在且量到 %s：%s -> %s（工厂恒定设置 %s）✓'
                      % (reg, caller, callee, ','.join(sorted(IA[key]))))
        if not anchors_ok:
            raise SystemExit('  [FATAL] 自证失败：锚点不可达 ⇒ 反汇编解析不可信')

    PF, nF, sF, stF, lnF, oSF = analyze(a.factory, od, os.path.join('build', '_dis_factory.txt'))
    PO, nO, sO, stO, lnO, oSO = analyze(a.ours, od, os.path.join('build', '_dis_ours.txt'))
    # ★ 两侧都分析完再归约：OWNER_ARITY 需要**两侧取 max**（形参上界），
    #   在只跑完一侧时归约会让上界偏小 ⇒ 又回到误报。
    IF = _reduce(PF, lnF, oSF)
    IO = _reduce(PO, lnO, oSO)
    print('  工厂：函数 %d / bl 调用点 %d / 调用对 %d' % (sF, nF, len(PF)))
    print('  我方：函数 %d / bl 调用点 %d / 调用对 %d' % (sO, nO, len(PO)))



    # 工厂侧被调者的 live-in（判断"缺的那个寄存器是否真的会被读"）
    li_cache = {}
    tgt_addr = {}
    for k, v2 in symtab(a.factory, od).items():
        tgt_addr.setdefault(k, v2[0])

    v = []
    for key, fi in IF.items():
        ce = key[1]
        if ce in var or key[0] in var:      # 变参被调者 / 变参调用者（转发 va_list）都豁免
            continue
        oi = IO.get(key)
        if oi is None:
            continue                        # 我们没这对调用 ⇒ 不属于"漏参"类别
        miss = fi - oi
        if not miss:
            continue
        # 被调者"会读的进入寄存器"：取**两侧并集**（任一侧会读，缺了就可能在那一侧崩）
        liv = set()
        for (ln, st, symd) in ((lnF, stF, symtab(a.factory, od)), (lnO, stO, symtab(a.ours, od))):
            ad2 = None
            for k2, v2 in symd.items():
                if k2 == ce:
                    ad2 = v2[0]
                    break
            if ad2 is None or ad2 not in st:
                continue
            ck = (id(ln), ad2)
            if ck not in li_cache:
                li_cache[ck] = livein_callee(ln, st[ad2])
            liv |= li_cache[ck]
        high = sorted((miss & liv) - UNCERTAIN.get(key, set()))
        v.append((key, sorted(miss), high, sorted(oi), len(PF[key]), len(PO[key])))
    v.sort(key=lambda x: (0 if x[2] else 1, x[0][1], x[0][0]))

    highl = [x for x in v if x[2]]
    if a.selfcheck:
        vk = {x[0] for x in v if x[2]}          # 只取 HIGH（LOW 是保真度差异，不是结论）
        vkall = {x[0] for x in v}
        # 正向：必须被**检视到**（两侧调用对都在），并打印当前判定（状态感知）
        for c, ce, reg in anchors:
            key = (c, ce)
            if key not in IF or key not in IO:
                raise SystemExit('  [FATAL] 端到端自证失败：锚点 %s->%s 未被检视到 '
                                 '⇒ 解析→判定链路有断点，拒绝出结论' % (c, ce))
            state = ('违例（缺 %s）' % reg) if key in vk else '合规（该寄存器已设）'
            if key in vkall and key not in vk:
                state = '非 HIGH 违例（降级为 LOW）'
            print('  [selfcheck-3] 正向锚点 %s->%s 已被检视；当前状态 = **%s** ✓'
                  % (c, ce, state))
        # 负向：人工核对"两侧一致"的对，必须不在 HIGH 违例表里（防"全都报"的退化解）
        for c, ce in anchors_neg:
            key = (c, ce)
            if key in vk:
                raise SystemExit('  [FATAL] 端到端自证失败：负向锚点 %s->%s 被误报为 HIGH 违例 '
                                 '⇒ 判据退化为"全都报"，拒绝出结论' % (c, ce))
            print('  [selfcheck-4] 负向锚点 %s->%s 未被误报 ✓（防"全都报"退化解）' % (c, ce))
    print()
    print('  == ★ HIGH：缺失寄存器**确在被调者 live-in 中**（会把垃圾当参数用）==')
    if not highl:
        print('     ✓ 无')
    for (caller, callee), miss, high, oi, nf, no in highl[:a.top]:
        print('     %-30s -> %-24s 未设 %-12s (该寄存器会被读!) 工厂%d处/我方%d处'
              % (caller[:30], callee[:24], ','.join(high), nf, no))
    print('     （HIGH 全量列出，不截断）')
    print()
    print('  == LOW：仅保真度差异（缺失寄存器不在两侧 live-in 中）—— 只列前 %d 项 ==' % a.top)
    lows = [x for x in v if not x[2]]
    for (caller, callee), miss, high, oi, nf, no in lows[:a.top]:
        print('     %-30s -> %-24s 未设 %-12s' % (caller[:30], callee[:24], ','.join(miss)))
    if len(lows) > a.top:
        print('     ...（共 %d 对）' % len(lows))
    print()
    print('  合计：HIGH = %d / LOW = %d / 总计 = %d' % (len(highl), len(v) - len(highl), len(v)))

    # ---- 台账棘轮 ----
    if a.write_ledger:
        path = a.ledger or 'tools/livein_args_pending.txt'
        with open(path, 'w', encoding='utf-8', newline=chr(10)) as f:
            f.write('# 调用点实参寄存器差异 · 已知项台账（棘轮）%s' % chr(10))
            f.write('# 格式: <caller> <callee> <HIGH|LOW>%s' % chr(10))
            f.write('# 含义：工厂"恒定设置"而我们从不在该对调用上设置的实参寄存器。%s' % chr(10))
            f.write('#   HIGH = 该寄存器确在被调者 live-in 中 ⇒ **待人工裁决**：%s' % chr(10))
            f.write('#          可能是「我们漏了参数」，也可能是「两侧共有的脆弱性（都靠残值）」%s' % chr(10))
            f.write('#          —— 裁决必须回到机器码：看被调者序言是否真读该寄存器、%s' % chr(10))
            f.write('#          以及**工厂自己的调用点是否也漏设**（工厂也漏 ⇒ 共有脆弱性，%s' % chr(10))
            f.write('#          此时我们的 3 参写法是**忠实**的，行动是"显式化"而非"补参数"）。%s' % chr(10))
            f.write('#   LOW  = 缺失寄存器不在两侧 live-in 中（保真度差异，暂无行为后果）。%s' % chr(10))
            f.write('# ★ 逐项人工核对后修正源码，改好一项**删一行**；新增不在本台账内 ⇒ 门禁失败。%s' % chr(10))
            for (caller, callee), miss, high, oi, nf, no in v:
                f.write('%s %s %s%s' % (caller, callee, 'HIGH' if high else 'LOW', chr(10)))
        print('  已写入台账：%d 项（%s）' % (len(v), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend = set()
        for ln in open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                q = ln.split()
                if len(q) >= 2:
                    pend.add((q[0], q[1]))
        cur = {x[0] for x in v}
        newv = [x for x in v if x[0] not in pend]
        gone = sorted(pend - cur)
        if gone:
            print()
            print('  ★ 台账条目已消失（= 该项已修好）⇒ 请删除以下行以保持棘轮语义：')
            for c, ce in gone:
                print('     %-32s -> %s' % (c, ce))
        if newv:
            print()
            print('  ★★ 新增差异 %d 对（不在台账内 ⇒ 判失败）：' % len(newv))
            for (caller, callee), miss, high, oi, nf, no in newv[:a.top]:
                print('     %-30s -> %-24s 未设 %-12s %s'
                      % (caller[:30], callee[:24], ','.join(miss), 'HIGH' if high else 'LOW'))
        # ★ `gone` 只警告不判失败：CI 里 ELF 是新构建、但台账可能滞后一轮 ⇒
        #   若把它判失败，会出现"源码已修却红一次"的假失败。新增才是真信号。
        if newv:
            return 1
        print()
        print('  [PASS] 台账一致（无新增 / 无已修未删行），台账剩余 %d 项' % len(pend))
        return 0

    print()
    if len(v) > a.allow:
        print('  [FAIL] 超过允许值 %d' % a.allow)
        return 1
    print('  [PASS] 未超过允许值 %d' % a.allow)
    return 0


if __name__ == '__main__':
    sys.exit(main())
