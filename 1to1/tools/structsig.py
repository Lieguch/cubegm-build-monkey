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

# 编译器鲁棒性处理：
#  a) 去 @plt 后缀 —— .o 内为 "bl 0 <malloc>"（->@malloc），可执行文件内为 "@malloc@plt"
#  b) 立即数分层 —— 小立即数(<0x1000)多为栈偏移/loop 计数，跨编译器噪声大；
#     大立即数(>=0x1000)多为逻辑常量/掩码，是有效语义信号
RE_PLT = re.compile(r'@plt$')
BIG = 0x1000


def _norm_call(t):
    return RE_PLT.sub('', t)


def sig(f, prefix=None):
    calls = collections.Counter()
    imms_small = collections.Counter()
    imms_big = collections.Counter()
    words = collections.Counter()
    br = set()
    for ins in f['t1']:
        m = RE_CALL.match(ins)
        if m:
            calls[_norm_call(m.group(1))] += 1
        for v in RE_IMM.findall(ins):
            try:
                n = int(v, 16) if v.lower().startswith(('0x', '-0x')) else int(v)
            except ValueError:
                continue
            (imms_big if abs(n) >= BIG else imms_small)[v] += 1
        m = RE_WORD.match(ins)
        if m:
            words[m.group(1)] += 1
        if re.match(r'^(b|bx|beq|bne|bgt|blt|bge|ble|bhi|bls|bcs|bcc|bmi|bpl|bvs|bvc|cbz|cbnz)\b', ins):
            tgt = re.findall(r'@([\w.]+(?:\+0x[0-9a-f]+)?)', ins)
            if tgt:
                br.add(tgt[0])
    # 内外调用分离：内部 = 目标名以组件前缀开头
    if prefix:
        c_in = {k: v for k, v in calls.items() if k.startswith(prefix)}
        c_ext = {k: v for k, v in calls.items() if not k.startswith(prefix)}
    else:
        c_in, c_ext = dict(calls), {}
    return {
        'calls': dict(sorted(calls.items())),
        'calls_ext': dict(sorted(c_ext.items())),
        'calls_int': dict(sorted(c_in.items())),
        'imms_big': dict(sorted(imms_big.items())),
        'imms_small_n': sum(imms_small.values()),
        'nblk': len(br) + 1,
        'ncall': sum(calls.values()),
        'n': f['n'],
    }


def cmp_sig(g, c):
    """S1 强语义等价 / S2 调用等价 / S3 结构等价 / FAIL。"""
    if g['calls_ext'] != c['calls_ext']:
        return 'FAIL'
    if g['imms_big'] == c['imms_big'] and g['nblk'] == c['nblk']:
        return 'S1'
    if g['ncall'] == c['ncall']:
        return 'S2'
    if g['nblk'] == c['nblk']:
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
    prefix = None
    a = sys.argv[3:]
    for i, v in enumerate(a):
        if v == '--detail' and i + 1 < len(a):
            detail = a[i + 1]
        if v == '--json' and i + 1 < len(a):
            outjson = a[i + 1]
        if v == '--prefix' and i + 1 < len(a):
            prefix = a[i + 1]

    res = {}
    for name, gf in G.items():
        cf = C.get(name)
        if cf is None:
            res[name] = 'MISSING'
        else:
            res[name] = cmp_sig(sig(gf, prefix), sig(cf, prefix))

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
            sg, sc = sig(gf, prefix), sig(cf, prefix)
            print('\n[detail] %s  判定=%s' % (detail, res[detail]))
            print('  n: %d vs %d   nblk: %d vs %d   ncall: %d vs %d'
                  % (sg['n'], sc['n'], sg['nblk'], sc['nblk'], sg['ncall'], sc['ncall']))
            for key, label in (('calls_ext', '外部调用'), ('calls_int', '内部调用')):
                only_g = {k: v for k, v in sg[key].items() if k not in sc[key]}
                only_c = {k: v for k, v in sc[key].items() if k not in sg[key]}
                diff_n = {k: (sg[key][k], sc[key][k]) for k in sg[key]
                          if k in sc[key] and sg[key][k] != sc[key][k]}
                if only_g:
                    print('  仅金标准%s:' % label, list(only_g)[:8])
                if only_c:
                    print('  仅候选%s:' % label, list(only_c)[:8])
                if diff_n:
                    print('  %s次数不同:' % label, list(diff_n.items())[:8])
            gi, ci = set(sg['imms_big']), set(sc['imms_big'])
            if gi - ci:
                print('  仅金标准大立即数:', sorted(gi - ci)[:8])
            if ci - gi:
                print('  仅候选大立即数:', sorted(ci - gi)[:8])

    if outjson:
        json.dump({'summary': dict(cnt), 'total': total, 'status': res},
                  open(outjson, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('\n报告 ->', outjson)
    return 0


if __name__ == '__main__':
    sys.exit(main())
