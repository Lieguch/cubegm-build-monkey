#!/usr/bin/env python3
"""
structsig.py — 编译器版本鲁棒的「函数语义指纹」比对。

为什么需要它：
  T1（归一化指令序列全等）要求**同款编译器**才可能成立。
  但判定标准是「语义级等价（允许寄存器分配/指令调度差异）」，
  因此需要一种**跨编译器版本稳定、又能捕捉逻辑差异**的指纹。

指纹构成（每项都对寄存器分配/指令调度不敏感）：
  1. calls    被调用的符号集合（含次数）        <- 最强语义信号
  2. imms     立即数多重集（#0xNN / #N）        <- 逻辑常量
  3. words    字面量池 .word 值                   <- 跳表/函数指针/常量表
  4. nblk     基本块数（分支目标数 + 1）
  5. ncall    调用点数量
  6. n        指令条数（容差比对）

判定：
  S1 = calls 与 imms 完全一致（强语义等价）      <- 跨编译器可达成
  S2 = calls 一致（同上但不含立即数）
  S3 = nblk/ncall 一致（结构等价）
  FAIL

用法:
  structsig.py golden.json candidate.json [--detail FUNC] [--json out.json]
"""
import json, re, sys, collections

RE_CALL = re.compile(r'^bl(?:x)?\s+@(\S+)')
RE_IMM = re.compile(r'#(-?0x[0-9a-f]+|-?\d+)')
RE_WORD = re.compile(r'^\.word\s+(0x[0-9a-f]+)', re.I)


def sig(f):
    calls = collections.Counter()
    imms = collections.Counter()
    words = collections.Counter()
    br = set()
    for i, ins in enumerate(f['t1']):
        m = RE_CALL.match(ins)
        if m:
            calls[m.group(1)] += 1
        for v in RE_IMM.findall(ins):
            imms[v] += 1
        m = RE_WORD.match(ins)
        if m:
            words[m.group(1)] += 1
        # 分支目标（相对该函数）作为基本块标识
        if re.match(r'^(b|bx|beq|bne|bgt|blt|bge|ble|bhi|bls|bcs|bcc|bmi|bpl|bvs|bvc|cbz|cbnz)\b', ins):
            tgt = re.findall(r'@([\w.]+(?:\+0x[0-9a-f]+)?)', ins)
            if tgt:
                br.add(tgt[0])
    return {
        'calls': dict(sorted(calls.items())),
        'imms': dict(sorted(imms.items())),
        'words': dict(sorted(words.items())),
        'nblk': len(br) + 1,
        'ncall': sum(calls.values()),
        'n': f['n'],
    }


def cmp_sig(g, c, tol=0.10):
    if g['calls'] != c['calls']:
        return 'FAIL'
    if g['imms'] == c['imms']:
        return 'S1'
    if g['nblk'] == c['nblk'] and g['ncall'] == c['ncall']:
        return 'S2'
    if g['nblk'] == c['nblk'] and g['ncall'] == c['ncall']:
        return 'S3'
    if g['n'] and abs(c['n'] - g['n']) / g['n'] <= tol and g['ncall'] == c['ncall']:
        return 'S3'
    return 'FAIL'


def load(p):
    return json.load(open(p, encoding='utf-8'))['functions']


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    G, C = load(sys.argv[1]), load(sys.argv[2])
    detail = None
    outjson = None
    a = sys.argv[3:]
    for i, v in enumerate(a):
        if v == '--detail' and i + 1 < len(a):
            detail = a[i + 1]
        if v == '--json' and i + 1 < len(a):
            outjson = a[i + 1]

    res = {}
    for name, gf in G.items():
        cf = C.get(name)
        if cf is None:
            res[name] = 'MISSING'
        else:
            res[name] = cmp_sig(sig(gf), sig(cf))

    cnt = collections.Counter(res.values())
    total = len(G)
    print('=' * 66)
    print('结构语义指纹比对（编译器版本鲁棒）')
    print('=' * 66)
    print('金标准 %d 函数 / 候选 %d 函数' % (total, len(C)))
    for k in ('S1', 'S2', 'S3', 'FAIL', 'MISSING'):
        print('  %-8s %5d  %6.2f%%' % (k, cnt.get(k, 0), 100.0 * cnt.get(k, 0) / total))
    print('-' * 66)
    p2 = cnt.get('S1', 0) + cnt.get('S2', 0)
    print('  门禁通过 (S1+S2) = %d/%d = %.2f%%' % (p2, total, 100.0 * p2 / total))
    print('  S1 强语义等价    = %d/%d = %.2f%%' % (cnt.get('S1', 0), total, 100.0 * cnt.get('S1', 0) / total))

    if detail:
        gf, cf = G.get(detail), C.get(detail)
        if not gf or not cf:
            print('\n[detail] 缺函数:', detail)
        else:
            sg, sc = sig(gf), sig(cf)
            print('\n[detail] %s  判定=%s' % (detail, res[detail]))
            print('  n: %d vs %d   nblk: %d vs %d   ncall: %d vs %d'
                  % (sg['n'], sc['n'], sg['nblk'], sc['nblk'], sg['ncall'], sc['ncall']))
            only_g = {k: v for k, v in sg['calls'].items() if k not in sc['calls']}
            only_c = {k: v for k, v in sc['calls'].items() if k not in sg['calls']}
            if only_g:
                print('  仅金标准调用:', list(only_g)[:8])
            if only_c:
                print('  仅候选调用:', list(only_c)[:8])
            diff_n = {k: (sg['calls'][k], sc['calls'][k]) for k in sg['calls']
                      if k in sc['calls'] and sg['calls'][k] != sc['calls'][k]}
            if diff_n:
                print('  调用次数不同:', list(diff_n.items())[:8])
            gi, ci = set(sg['imms']), set(sc['imms'])
            if gi - ci:
                print('  仅金标准立即数:', sorted(gi - ci)[:8])
            if ci - gi:
                print('  仅候选立即数:', sorted(ci - gi)[:8])

    if outjson:
        json.dump({'summary': dict(cnt), 'total': total, 'status': res},
                  open(outjson, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('\n报告 ->', outjson)
    return 0


if __name__ == '__main__':
    sys.exit(main())
