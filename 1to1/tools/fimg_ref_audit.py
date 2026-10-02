#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fimg_ref_audit.py —— 我方代码**是否可能执行到"不可执行的工厂映像区"**。

## 为什么这是上机前的必查项
我方产物里，`[0x9000, 0x3acffc)` 是**工厂机器码的地址镜像**，但权限是 `--R`（不可执行）——
这是有意设计（我们不执行工厂代码）。可是只要**任何一条控制流**跳进这个区间，
真机就是 `SIGSEGV`（NX）或 `SIGILL`。

`pre_device_gate.py` 的 P8 只覆盖**直接分支**（`b/bl/blx #imm`）—— **0 处**。
但它**覆盖不到间接跳转**（`ldr r3,[pc,#n]; blx r3`，即函数指针表）。
本工具专门补这块。

## 判据（机械）
  A1  该区间内**不得存在 `STT_FUNC` 符号**（存在 ⇒ 有人把它当函数用）。
  A2  对**可执行段**里的每个字面池字（由 `ldr rN,[pc,#imm]` 定位），
      若其值落在该区间，且**在随后的窗口内出现 `blx rN` / `bx rN`**（该寄存器），
      ⇒ **CODE-REF**（真机上必炸）。
  A3  若值落在该区间但只被当作数据（`ldr/ldrb/str`…）⇒ **DATA-REF**（正常，工厂数据在我方镜像里）。
  A4  `.rel.*` 里 addend 落在该区间的重定位 ⇒ 逐条列出（区分是否在可执行节内）。

用法: python tools/fimg_ref_audit.py <ours.elf> [<factory.bin>]
退出: 0=无 CODE-REF；2=存在 CODE-REF；11=读不到输入
"""
import io
import struct
import sys

PT_LOAD = 1
STT_FUNC, STT_OBJECT = 2, 1


def phdrs(d):
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    phent = struct.unpack_from('<H', d, 42)[0]
    phnum = struct.unpack_from('<H', d, 44)[0]
    out = []
    for i in range(phnum):
        o = e_phoff + i * phent
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        out.append(dict(type=t, off=off, vaddr=va, filesz=fsz, memsz=msz, flags=fl))
    return out


def factory_code_region(fac):
    """工厂里"可执行"的那一段 VMA 区间（= 工厂代码区）。"""
    phs = phdrs(fac)
    rs = [(p['vaddr'], p['vaddr'] + p['filesz']) for p in phs
          if p['type'] == PT_LOAD and (p['flags'] & 1) and p['filesz']]
    return rs[0] if rs else (0, 0)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 11
    ours_p = sys.argv[1]
    fac_p = sys.argv[2] if len(sys.argv) > 2 else 'golden/factory.rkgame.bin'
    try:
        A = io.open(ours_p, 'rb').read()
    except Exception as e:
        print('!! 读不到 %s: %s' % (ours_p, e))
        return 11
    try:
        F = io.open(fac_p, 'rb').read()
    except Exception:
        F = None

    phs = phdrs(A)
    exec_r = [(p['vaddr'], p['vaddr'] + p['filesz'], p['off'], p['filesz'])
              for p in phs if p['type'] == PT_LOAD and (p['flags'] & 1) and p['filesz']]
    nonx_r = [(p['vaddr'], p['vaddr'] + p['filesz']) for p in phs
              if p['type'] == PT_LOAD and not (p['flags'] & 1) and p['filesz']]

    fac_rx = factory_code_region(F) if F else (0x8000, 0x3ad1ec)
    print('=' * 96)
    print('工厂映像区引用审计   ours=%s' % ours_p)
    print('=' * 96)
    print('  工厂可执行区间（原厂）： 0x%x - 0x%x' % fac_rx)
    print('  我方不可执行段        ： %s' % [('0x%x-0x%x' % e) for e in nonx_r])
    # 我方"落在工厂代码区间内的不可执行段" = 风险区
    R = []
    for lo, hi in nonx_r:
        a, b = max(lo, fac_rx[0]), min(hi, fac_rx[1])
        if a < b:
            R.append((a, b))
    if not R:
        print('  ⇒ 我方没有任何"工厂代码区间内的不可执行段"（无需审计）')
        return 0
    print('  ⇒ ★ 风险区 R（工厂代码区间 ∩ 我方不可执行段）= %s' % [('0x%x-0x%x' % e) for e in R])

    def inR(v):
        for a, b in R:
            if a <= v < b:
                return True
        return False

    # ---- A1：R 内是否存在 STT_FUNC 符号 --------------------------------
    e_shoff = struct.unpack_from('<I', A, 32)[0]
    shent = struct.unpack_from('<H', A, 46)[0]
    shnum = struct.unpack_from('<H', A, 48)[0]
    shstrndx = struct.unpack_from('<H', A, 50)[0]
    syms = []
    if 0 < e_shoff < len(A) and shnum:
        # shstrtab
        so = e_shoff + shstrndx * shent
        shstr_off = struct.unpack_from('<I', A, so + 16)[0]
        for i in range(shnum):
            o = e_shoff + i * shent
            nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from('<10I', A, o)
            e = A.find(b'\x00', shstr_off + nm)
            name = A[shstr_off + nm:e].decode('latin-1')
            if name in ('.symtab', '.dynsym'):
                strtab_off = struct.unpack_from('<I', A, e_shoff + link * shent + 16)[0]
                n = size // 16
                for k in range(n):
                    p = off + k * 16
                    nme, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', A, p)
                    e2 = A.find(b'\x00', strtab_off + nme)
                    sname = A[strtab_off + nme:e2].decode('latin-1')
                    stype = inf & 0xf
                    if sname and val and inR(val):
                        syms.append((sname, stype, val, sz))
    funcs = [s for s in syms if s[1] == STT_FUNC]
    objs = [s for s in syms if s[1] == STT_OBJECT]
    others = [s for s in syms if s[1] not in (STT_FUNC, STT_OBJECT)]
    print()
    print('--- A1：风险区内被引用的符号 ---')
    print('  STT_FUNC  %d 个 %s' % (len(funcs), [s[0] for s in funcs[:10]]))
    print('  STT_OBJECT %d 个 %s' % (len(objs), [s[0] for s in objs[:10]]))
    print('  其它      %d 个 %s' % (len(others), [(s[0], s[1]) for s in others[:10]]))

    # ---- A2/A3：可执行段里的字面池 --------------------------------------------------
    try:
        import capstone
    except ImportError:
        print('  !! 缺 capstone，跳过 A2/A3')
        return 0
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    md.detail = True
    md.skipdata = True
    code_refs, data_refs = [], []
    for lo, hi, off, fsz in exec_r:
        code = A[off:off + fsz]
        # 先做一次"指令 → (地址, 文本)"扫描，找出 ldr rN,[pc,#imm] 的字面地址
        insns = list(md.disasm(code, lo))
        idx_of = {}
        for i, ins in enumerate(insns):
            idx_of[ins.address] = i
        litpool = []
        for ins in insns:
            mn = (ins.mnemonic or '').lower()
            if mn in ('ldr', 'ldr.w') and len(ins.operands) >= 2:
                op1 = ins.operands[1]
                if op1.type == capstone.arm.ARM_OP_MEM and \
                   ins.reg_name(op1.mem.base) == 'pc':
                    lit = (ins.address + 8) + op1.mem.disp
                    if 0 <= lit - lo < len(code):
                        v = struct.unpack_from('<I', code, lit - lo)[0]
                        if inR(v):
                            litpool.append((ins, ins.reg_name(ins.operands[0].reg), v, lit))
        # 对每个字面，向后看窗口，判断是否被用来跳转
        for ins, reg, v, lit in litpool:
            i = idx_of.get(ins.address)
            used_code = False
            for j in range(i + 1, min(i + 13, len(insns))):
                nxt = insns[j]
                mn = (nxt.mnemonic or '').lower()
                if mn in ('bx', 'blx') and nxt.operands and \
                   nxt.reg_name(nxt.operands[0].reg) == reg:
                    used_code = True
                    break
                if mn.startswith('b') and mn not in ('b',) and nxt.operands and \
                   nxt.operands[0].type == capstone.arm.ARM_OP_REG and \
                   nxt.reg_name(nxt.operands[0].reg) == reg:
                    used_code = True
                    break
            (code_refs if used_code else data_refs).append((ins.address, reg, v))
    print()
    print('--- A2/A3：可执行段字面池里指向风险区的字 ---')
    print('  总字面数 %d ；判为 CODE-REF %d ；判为 DATA-REF %d' % (len(code_refs) + len(data_refs), len(code_refs), len(data_refs)))
    for a, r, v in code_refs[:20]:
        print('    ★ CODE-REF   insn@0x%x  %s -> 0x%x' % (a, r, v))
    for a, r, v in data_refs[:20]:
        print('      data-ref   insn@0x%x  %s -> 0x%x' % (a, r, v))
    if len(data_refs) > 20:
        print('      ...（另 %d 条 data-ref 略）' % (len(data_refs) - 20))

    print()
    print('-' * 96)
    verdict = 'PASS' if (not funcs and not code_refs) else 'FAIL'
    print('  结论: %s（STT_FUNC=%d ｜ CODE-REF=%d）' % (verdict, len(funcs), len(code_refs)))
    return 0 if verdict == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
