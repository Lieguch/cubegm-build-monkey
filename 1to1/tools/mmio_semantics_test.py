#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mmio_semantics_test —— 「设备寄存器访问语义」的类级门禁（自证型）。

为什么需要它
------------
真机 SIGBUS 的根因是：**指向 mmap 设备寄存器的指针不是 volatile** ⇒ 编译器
 ① 把 32 位读**窄化**成 `ldrh`（宽度变了 ⇒ SFC 总线错误）
 ② 把「先写 [base]、再读 [base+0x2C]」**重排**成「先读、后写」（顺序变了）
这是"重编后机器码与原厂语义不同"这一**类**的两个成员。逐个上机抓太贵，所以把
**类的边界条件**做成可离线复跑的实验：换任何编译器/任何优化档，这几条断言都必须成立。

四条断言（每条都有对应的反例，见 --selftest）
--------------------------------------------
A. **非 volatile 指针 + 只用低半字** ⇒ 必须出现 `ldrh`（证明"窄化"真实存在）
   —— 这是"缺陷态"，门禁要能**看见**它，否则说明门禁是假绿。
B. **整块寄存器指针声明 volatile** ⇒ 必须 `ldr` 且 `str` 在 `ldr` **之前**（宽度+顺序都对）
   —— 这是"正确态"。
C. **只对单次访问强转 volatile** ⇒ 宽度对了、**顺序仍错**（★ 关键反例：
   `*(volatile u32*)&regs[0xb]` 挡不住重排）⇒ 纪律：**必须整块指针 volatile**。
D. **内联汇编访问原语** ⇒ `ldr`/`str` 必须落在 `@APP/@NO_APP` 之间 ⇒ 编译器零自由度。

用法：
    python tools/mmio_semantics_test.py                 # 跑断言（PASS/FAIL）
    python tools/mmio_semantics_test.py --selftest      # 额外自证：缺陷态必须被抓到
exit: 0=PASS / 1=断言失败 / 11=仪器自身不可用（找不到编译器 / 编不出）
"""
import io
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

C_SRC = r'''/* 由 tools/mmio_semantics_test.py 生成，勿手改 */
typedef unsigned int u32;

/* A: 非 volatile 指针 + 只用低半字（= 修复前的真实形状） */
int A2(u32 *regs) { regs[0] = 0x80000000u; return (int)((regs[0xb] & 0xffffu) > 3); }

/* B: 整块寄存器指针 volatile（= 采用的写法） */
int B2(volatile u32 *regs) { regs[0] = 0x80000000u; return (int)((regs[0xb] & 0xffffu) > 3); }

/* C: 只对单次访问强转 volatile（★ 反例：顺序仍会被重排） */
int C2(u32 *regs) { regs[0] = 0x80000000u; return (int)((*(volatile u32 *)&regs[0xb] & 0xffffu) > 3); }

/* D: 内核式访问原语（内联汇编） */
static inline u32 rd32(const volatile void *p)
{ u32 v; __asm__ __volatile__("ldr %0, [%1]" : "=r"(v) : "r"(p) : "memory"); return v; }
static inline void wr32(volatile void *p, u32 v)
{ __asm__ __volatile__("str %0, [%1]" : : "r"(v), "r"(p) : "memory"); }
int D2(volatile u32 *regs)
{ wr32(&regs[0], 0x80000000u); return (int)((rd32(&regs[0xb]) & 0xffffu) > 3); }
'''


def find_cc():
    """多级解析编译器（CI 与本地路径不同；找不到必须硬失败，不能静默跳过）。"""
    cands = []
    env = os.environ.get('CC')
    if env:
        cands.append(env)
    cands += ['arm-linux-gnueabihf-gcc']
    zig = os.path.join(os.path.dirname(os.path.dirname(sys.executable)),
                       'Lib/site-packages/ziglang/zig.exe')
    if os.path.exists(zig):
        cands.append(zig + ' cc')
    zig2 = 'C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe'
    if os.path.exists(zig2):
        cands.append(zig2 + ' cc')
    for c in cands:
        exe = c.split()[0]
        try:
            r = subprocess.run([exe] + c.split()[1:] + ['--version'],
                               capture_output=True, timeout=90)
            if r.returncode == 0:
                return c.split(), (r.stdout + r.stderr).decode('utf-8', 'replace').split('\n')[0]
        except Exception:
            continue
    return None, None


def compile_asm(cc, srcc, out):
    # zig 的 `cc` 子命令已含 -c 语义，多传 -c 会告警但无害；不用 shell，避免引号/反斜杠问题。
    cmd = list(cc) + ['-S', '-Os',
                      '-target', 'arm-linux-gnueabihf', '-mfloat-abi=hard', '-mfpu=neon',
                      '-fno-stack-protector', '-o', out, srcc]
    if 'gcc' in cc[0]:
        cmd = list(cc) + ['-S', '-Os', '-march=armv7-a', '-mfloat-abi=hard', '-mfpu=neon',
                          '-fno-pic', '-fno-stack-protector', '-o', out, srcc]
    env = dict(os.environ)
    env.setdefault('ZIG_GLOBAL_CACHE_DIR',
                   os.path.join(tempfile.gettempdir(), 'zgc_mmio_test'))
    os.makedirs(env['ZIG_GLOBAL_CACHE_DIR'], exist_ok=True)
    r = subprocess.run(cmd, capture_output=True, env=env, timeout=300)
    return r.returncode == 0, (r.stdout + r.stderr).decode('utf-8', 'replace')


def bodies(asm):
    """把汇编切成 {函数名: [指令行]}，忽略 .cfi/.fnstart 之类的伪指令。"""
    out = {}
    cur = None
    for l in asm.split('\n'):
        raw = l.rstrip()
        # 标签行可能带尾随注释：`A2:                    @ @A2`（clang）或 `A2:`（gcc）
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):(\s|@|$)', raw)
        if m and m.group(1) in ('A2', 'B2', 'C2', 'D2'):
            cur = m.group(1)
            out[cur] = []
            continue
        s = raw.strip()
        if cur is None or not s:
            continue
        if s.startswith(('.', '@ %bb', '@ --', '@APP', '@NO_APP')):
            if s in ('@APP', '@NO_APP'):
                out[cur].append(s)
            continue
        out[cur].append(s)
    return out


def judge(b, verbose=True):
    """返回 (缺陷列表, 通过项列表)。"""
    bad, ok = [], []
    a = b.get('A2', [])
    a_ldrh = [x for x in a if x.startswith('ldrh')]
    if a_ldrh:
        ok.append('A 缺陷态可见：非 volatile + 只用低半字 ⇒ %s（窄化真实存在）' % a_ldrh[0][:40])
    else:
        bad.append('A 未复现窄化（本编译器在当前档位不窄化）—— 门禁的"缺陷态"失效，结论不可用')

    c = b.get('B2', [])
    ld = [i for i, x in enumerate(c) if x.startswith('ldr')]
    st = [i for i, x in enumerate(c) if x.startswith('str')]
    if ld and st and min(st) < min(ld):
        ok.append('B 正确态：%s → %s（先写后读，宽度 32 位）' % (c[min(st)][:26], c[min(ld)][:26]))
    else:
        bad.append('B 顺序/宽度不对：str=%s ldr=%s ⇒ 整块 volatile 未生效' % (c[min(st)] if st else '-', c[min(ld)] if ld else '-'))

    e = b.get('C2', [])
    e_ld = [i for i, x in enumerate(e) if x.startswith('ldr')]
    e_st = [i for i, x in enumerate(e) if x.startswith('str')]
    e_narrow = [x for x in e if x.startswith('ldrh')]
    if not e_narrow and e_ld and e_st and min(e_ld) < min(e_st):
        ok.append('C ★反例证实：单次强转 volatile 只锁宽度、**不锁顺序**（%s 早于 %s）'
                  % (e[min(e_ld)][:22], e[min(e_st)][:22]))
    elif e_narrow:
        bad.append('C 单次强转竟然仍窄化(%s) —— 与 C 反例前提不符，请人工复核' % e_narrow[0][:30])
    else:
        ok.append('C 单次强转的产出于本编译器下顺序正确（反例不成立，注意 B 仍是唯一稳妥写法）')

    d = b.get('D2', [])
    if '@APP' in d and '@NO_APP' in d:
        ok.append('D 访问原语：ldr/str 落在 @APP/@NO_APP 内 ⇒ 编译器零自由度（内核做法）')
    else:
        bad.append('D 内联汇编未按预期出现 @APP/@NO_APP ⇒ 原语写法有问题')

    if verbose:
        for x in ok:
            print('  [OK] %s' % x)
        for x in bad:
            print('  [!!] %s' % x)
    return bad, ok


def main():
    cc, ver = find_cc()
    if not cc:
        print('  ★ 找不到可用编译器（CC / arm-linux-gnueabihf-gcc / zig）—— 这是仪器不可用，必须硬失败')
        return 11
    print('  [编译器] %s   （%s）' % (' '.join(cc), ver[:70]))
    tmp = tempfile.gettempdir()
    src = os.path.join(tmp, 'cgm_mmio_semantics.c')
    asm = os.path.join(tmp, 'cgm_mmio_semantics.s')
    io.open(src, 'w', encoding='utf-8', newline='\n').write(C_SRC)
    okc, log = compile_asm(cc, src, asm)
    if not okc or not os.path.exists(asm):
        print('  ★ 编译失败 —— 仪器不可用，硬失败（不允许"跳过即为通过"）')
        print(log[-1500:])
        return 11
    b = bodies(io.open(asm, encoding='utf-8', errors='replace').read())
    missing = [k for k in ('A2', 'B2', 'C2', 'D2') if k not in b]
    if missing:
        print('  ★ 汇编里缺函数 %s ⇒ 解析器或源码有误，硬失败' % missing)
        return 11

    print('  ---- 四条断言 ----')
    bad, ok = judge(b)

    if '--selftest' in sys.argv:
        print()
        print('  ---- 自证：把"正确态"伪造成"非 volatile"形态，A 类断言必须失效/被抓 ----')
        fake = dict(b)
        fake['A2'] = b.get('B2', [])          # 用正确态冒充缺陷态
        fb, _ = judge(fake, verbose=False)
        if any('未复现窄化' in x for x in fb):
            print('  [OK] 自证通过：喂入"看起来正常"的样本 ⇒ 门禁能识别缺陷态失效')
        else:
            print('  [!!] 自证失败：门禁对"缺陷态被掉包"无感 ⇒ 判据不成立')
            bad.append('selftest')

    print()
    if bad:
        print('  ---- 判决：FAIL（%d 项）----' % len(bad))
        return 1
    print('  ---- 判决：PASS（%d 项）----' % len(ok))
    print('  纪律：**凡从 mmap 设备基址派生的指针，一律整块声明 volatile**；'
          '只对单次访问强转 volatile 挡不住重排（见 C）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
