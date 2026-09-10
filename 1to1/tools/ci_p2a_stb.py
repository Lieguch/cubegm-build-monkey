#!/usr/bin/env python3
"""
ci_p2a_stb.py — P2-A：stb_truetype 版本锁定（CI 专用，跨编译器鲁棒）

为什么不用「函数尺寸」定版：
  首版实测 Ubuntu GCC 11 与原厂工具链平均尺寸偏差 49.6%，全版本不可区分
  —— 编译器版本差异淹没了版本差异。尺寸不是可靠指纹。

改用**结构语义指纹**（见 tools/structsig.py）：
  calls 调用符号集合 + imms 立即数多重集 + nblk 基本块数 + ncall 调用点数
  这些对寄存器分配/指令调度不敏感，却对逻辑差异敏感 => 可跨编译器定版。

用法:
  CC=arm-linux-gnueabihf-gcc OBJDUMP=arm-linux-gnueabihf-objdump \
  python3 tools/ci_p2a_stb.py golden/factory.funcs.json.gz report/p2a_stb.txt
"""
import json, gzip, os, re, subprocess, sys, urllib.request, ssl, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import funcdump
import structsig

CC = os.environ.get('CC', 'arm-linux-gnueabihf-gcc')
OBJDUMP = os.environ.get('OBJDUMP', 'arm-linux-gnueabihf-objdump')

# stb_truetype.h 历史锚点（由 tools/stb_range.py 的提交遍历得出）
ANCHORS = [
    ('v1.22', '787f1d64'), ('v1.23', '7a69424f'), ('v1.24', 'e140649c'),
    ('v1.25', 'be901954'), ('v1.26', '6e9f34d5'),
]
SUFFIX = re.compile(r'\.(isra|part|constprop)(\.\d+)?$')


def load_golden(p):
    if p.endswith('.gz'):
        return json.load(gzip.open(p, 'rt', encoding='utf-8'))
    return json.load(open(p, encoding='utf-8'))


def stb_subset(gold):
    """原厂 stbtt_* 子集；剔除编译器拆分产物（.isra/.part/.constprop）与重名。"""
    out = {}
    dup = set()
    for name, f in gold['functions'].items():
        if not name.startswith('stbtt_'):
            continue
        if SUFFIX.search(name):
            continue
        if name in out:
            dup.add(name)
        out[name] = f
    for d in dup:
        out.pop(d, None)
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ci'})
    with urllib.request.urlopen(req, timeout=90,
                                context=ssl._create_unverified_context()) as r:
        return r.read()


def compile_disasm(hb, wd):
    open(os.path.join(wd, 'stb_truetype.h'), 'wb').write(hb)
    open(os.path.join(wd, 'tu.c'), 'w').write(
        '#define STB_TRUETYPE_IMPLEMENTATION\n#include "stb_truetype.h"\n')
    op = os.path.join(wd, 'tu.o')
    r = subprocess.run([CC, '-O2', '-c', os.path.join(wd, 'tu.c'), '-o', op],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, 'compile: ' + r.stderr[:200]
    r = subprocess.run([OBJDUMP, '-d', op], capture_output=True, text=True)
    if r.returncode != 0:
        return None, 'objdump: ' + r.stderr[:200]
    return funcdump.parse(r.stdout)['functions'], None


def main():
    gold_path = sys.argv[1] if len(sys.argv) > 1 else 'golden/factory.funcs.json.gz'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'report/p2a_stb.txt'
    g = stb_subset(load_golden(gold_path))
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)

    L = []
    L.append('原厂 stb_truetype 可比函数 %d 个（结构语义指纹，跨编译器鲁棒）' % len(g))
    L.append('CC=%s' % CC)
    L.append('')
    L.append('%-7s %-10s %6s %6s %6s %6s %6s' %
             ('版本', 'sha', '候选', 'S1', 'S2', 'S3', 'FAIL'))
    rows = []
    for ver, sha in ANCHORS:
        try:
            hb = fetch('https://raw.githubusercontent.com/nothings/stb/%s/stb_truetype.h' % sha)
        except Exception as e:
            L.append('%-7s %-10s  fetch ERR %s' % (ver, sha, str(e)[:40]))
            continue
        with tempfile.TemporaryDirectory() as wd:
            cand, err = compile_disasm(hb, wd)
        if cand is None:
            L.append('%-7s %-10s  %s' % (ver, sha, err[:52]))
            continue
        c = {'S1': 0, 'S2': 0, 'S3': 0, 'FAIL': 0, 'MISSING': 0}
        for name, gf in g.items():
            cf = cand.get(name)
            if cf is None:
                c['MISSING'] += 1
                continue
            c[structsig.cmp_sig(structsig.sig(gf), structsig.sig(cf))] += 1
        cov = len(g) - c['MISSING']
        rows.append((c['S1'], c['S2'], cov, ver, sha, len(cand)))
        L.append('%-7s %-10s %6d %6d %6d %6d %6d' %
                 (ver, sha, len(cand), c['S1'], c['S2'], c['S3'], c['FAIL']))
    L.append('')
    if rows:
        rows.sort(key=lambda x: (-(x[0] + x[1]), -x[2]))
        best = rows[0]
        L.append('★ 最佳匹配（S1+S2 优先）: %s (%s)  S1=%d S2=%d 覆盖=%d/%d 候选函数=%d'
                 % (best[3], best[4], best[0], best[1], best[2], len(g), best[5]))
        L.append('  判据：S1+S2 覆盖率最高且唯一者即定版。')
    txt = '\n'.join(L)
    open(out_path, 'w', encoding='utf-8').write(txt)
    print(txt)

    if not rows:
        print('::error::P2-A 无任何候选可编译')
        sys.exit(1)
    if all(r[0] + r[1] == 0 for r in rows):
        print('::error::P2-A 全部候选结构指纹零命中，作业未真正生效')
        sys.exit(1)


if __name__ == '__main__':
    main()
