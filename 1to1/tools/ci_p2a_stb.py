#!/usr/bin/env python3
"""
ci_p2a_stb.py — P2-A：stb_truetype 版本锁定（CI 专用，须 Linux + ARM 交叉工具链）

方法（非猜测）：
  1. 从金标准取原厂 stbtt_* 的**每函数机器码字节数**（= 指令数 × 4）
  2. 逐个候选版本：下载 stb_truetype.h -> 编译 -> objdump -t 取每函数尺寸
  3. 比对：函数集覆盖率 + 逐函数尺寸偏差 -> 输出匹配度排序

用法:
  CC=arm-linux-gnueabihf-gcc OBJDUMP=arm-linux-gnueabihf-objdump \
  python3 tools/ci_p2a_stb.py golden/factory.funcs.json report/p2a_stb.txt
"""
import json, gzip, os, re, subprocess, sys, urllib.request, ssl, tempfile

CC = os.environ.get('CC', 'arm-linux-gnueabihf-gcc')
OBJDUMP = os.environ.get('OBJDUMP', 'arm-linux-gnueabihf-objdump')

# stb_truetype.h 历史锚点（覆盖 v1.19 ~ v1.26）
CANDIDATES = [
    ('v1.19', '4b5d6a3a'),  # 占位：CI 内改为真实 sha 列表
]
# 真实锚点由 tools/stb_range.py 生成后写入；此处按 tag 注释版本逐版抓取最新提交
VERSION_ANCHORS = {
    'v1.19': None, 'v1.20': None, 'v1.21': 'f7d1cd58', 'v1.22': '787f1d64',
    'v1.23': '7a69424f', 'v1.24': 'e140649c', 'v1.25': 'be901954', 'v1.26': '6e9f34d5',
}


def load_golden(p):
    if p.endswith('.gz'):
        return json.load(gzip.open(p, 'rt', encoding='utf-8'))
    return json.load(open(p, encoding='utf-8'))


def golden_stb_sizes(gold):
    out = {}
    for name, f in gold['functions'].items():
        if name.startswith('stbtt_'):
            base = re.sub(r'\.(isra|part|constprop)(\.\d+)?$', '', name)
            out[base] = f['n'] * 4          # ARM32：每条指令 4 字节
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'ci'})
    with urllib.request.urlopen(req, timeout=90,
                                context=ssl._create_unverified_context()) as r:
        return r.read()


def compile_and_sizes(header_bytes, workdir):
    hp = os.path.join(workdir, 'stb_truetype.h')
    cp = os.path.join(workdir, 'tu.c')
    op = os.path.join(workdir, 'tu.o')
    open(hp, 'wb').write(header_bytes)
    open(cp, 'w').write('#define STB_TRUETYPE_IMPLEMENTATION\n#include "stb_truetype.h"\n')
    r = subprocess.run([CC, '-O2', '-fno-inline-functions-called-once', '-c', cp, '-o', op],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None, r.stderr[:300]
    r = subprocess.run([OBJDUMP, '-t', op], capture_output=True, text=True)
    sizes = {}
    for ln in r.stdout.splitlines():
        p = ln.split()
        if len(p) >= 6 and p[2] in ('F', '.text') and p[3] == '.text':
            name = p[-1]
            try:
                sizes[name] = int(p[1], 16)
            except ValueError:
                pass
    if not sizes:
        # 取证转储：不猜，直接看 objdump 真实输出与产物状态
        print('!! objdump 提取 0 个函数，转储取证:')
        print('   .o exists=%s size=%s' % (os.path.exists(op),
                                           os.path.getsize(op) if os.path.exists(op) else -1))
        print('   objdump rc=%d stderr=%s' % (r.returncode, r.stderr[:200]))
        print('   --- objdump -t stdout (first 30 lines) ---')
        for ln in r.stdout.splitlines()[:30]:
            print('   |' + ln)
        print('   --- end ---')
    return sizes, None


def main():
    gold_path = sys.argv[1] if len(sys.argv) > 1 else 'golden/factory.funcs.json.gz'
    out_path = sys.argv[2] if len(sys.argv) > 2 else 'report/p2a_stb.txt'
    g = golden_stb_sizes(load_golden(gold_path))
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    lines = []
    lines.append('原厂 stb_truetype 函数 %d 个（金标准机器码尺寸）' % len(g))
    lines.append('CC=%s' % CC)
    lines.append('')
    lines.append('%-8s %-11s %6s %6s %8s %8s %9s' %
                 ('版本', 'sha', 'cand', '覆盖', '尺寸全等', '尺寸±10%', '平均偏差%'))
    rows = []
    for ver, sha in VERSION_ANCHORS.items():
        if not sha:
            lines.append('%-8s %-11s  (无锚点，跳过)' % (ver, '-'))
            continue
        try:
            hb = fetch('https://raw.githubusercontent.com/nothings/stb/%s/stb_truetype.h' % sha)
        except Exception as e:
            lines.append('%-8s %-11s  fetch ERR %s' % (ver, sha, str(e)[:40]))
            continue
        with tempfile.TemporaryDirectory() as wd:
            sizes, err = compile_and_sizes(hb, wd)
        if sizes is None:
            lines.append('%-8s %-11s  compile ERR %s' % (ver, sha, err[:60]))
            continue
        common = set(g) & set(sizes)
        cover = len(common)
        exact = sum(1 for k in common if sizes[k] == g[k])
        near = sum(1 for k in common if g[k] and abs(sizes[k] - g[k]) / g[k] <= 0.10)
        devs = [abs(sizes[k] - g[k]) / g[k] for k in common if g[k]]
        avg = 100.0 * sum(devs) / len(devs) if devs else 999
        rows.append((avg, ver, sha, len(sizes), cover, exact, near))
        lines.append('%-8s %-11s %6d %6d %8d %8d %8.1f' %
                     (ver, sha, len(sizes), cover, exact, near, avg))
    lines.append('')
    if rows:
        rows.sort()
        best = rows[0]
        lines.append('★ 最佳匹配（按平均尺寸偏差）: %s (%s)  cand=%d 覆盖=%d 尺寸全等=%d 平均偏差=%.1f%%'
                     % (best[1], best[2], best[3], best[4], best[5], best[0]))
        lines.append('  注：绝对尺寸受编译器版本影响；若工具链与原厂不一致，')
        lines.append('      仅「函数集合」与「相对排序」可用于定版，绝对尺寸需匹配工具链后复验。')
    txt = '\n'.join(lines)
    open(out_path, 'w', encoding='utf-8').write(txt)
    print(txt)
    # 硬门禁（假绿防护）：所有候选覆盖为 0 = 作业未真正生效，必须失败
    if rows and all(r[4] == 0 for r in rows):
        print('::error::P2-A 覆盖全为 0，作业未真正生效')
        sys.exit(1)
    if not rows:
        print('::error::P2-A 无任何候选可编译')
        sys.exit(1)


if __name__ == '__main__':
    main()
