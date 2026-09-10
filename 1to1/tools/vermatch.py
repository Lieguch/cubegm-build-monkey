#!/usr/bin/env python3
"""
vermatch.py — 上游组件版本指纹匹配器（P2-A 核心工具，非猜测）

原理：二进制里每个组件的**函数名集合**是强版本指纹（内部函数随版本增删）。
      逐个拉取上游候选版本源码 → 抽取函数名集合 → 与原厂集合比对 → 输出匹配度排序。

用法:
  vermatch.py stb        # 匹配 stb_truetype
  vermatch.py mxml       # 匹配 mini-XML
"""
import re, os, sys, json, ssl, urllib.request, urllib.error, difflib

CTX = ssl._create_unverified_context()
TOK = os.environ.get('GH_TOKEN', '')   # 从环境变量读取，禁止硬编码


def get(url, token=False):
    h = {'User-Agent': 'vermatch', 'Accept': 'application/vnd.github+json'}
    if token:
        h['Authorization'] = 'Bearer ' + TOK
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.read()


FACTORY = json.load(open(r'D:/output/rkgame-1to1/upstream/factory_component_funcs.json',
                         encoding='utf-8'))


def extract_names(text, prefix):
    """从 C 源码抽取指定前缀的函数定义名（含 static / 内部函数）。"""
    names = set()
    for m in re.finditer(r'\b(' + prefix + r'_[\w]+)\s*\(', text):
        names.add(m.group(1))
    return names


def score(fwant, fgot):
    inter = fwant & fgot
    return len(inter), len(fwant), len(fgot)


def report(label, fwant, fgot):
    i, w, g = score(fwant, fgot)
    miss = sorted(fwant - fgot)
    extra = sorted(fgot - fwant)
    print('  %-26s 匹配 %3d/%3d  候选多出 %3d  Jaccard=%.3f'
          % (label, i, w, len(extra), i / max(1, len(fwant | fgot))))
    if miss[:6]:
        print('       原厂有候选无: %s%s' % (', '.join(miss[:6]), ' …' if len(miss) > 6 else ''))
    if extra[:6]:
        print('       候选有原厂无: %s%s' % (', '.join(extra[:6]), ' …' if len(extra) > 6 else ''))
    return i / max(1, len(fwant | fgot))


def match_stb():
    fwant = {f['name'] for f in FACTORY['stb_truetype']}
    # 归一化：去掉 .isra/.part/.constprop 后缀（编译器产物）
    fwant = {re.sub(r'\.(isra|part|constprop)(\.\d+)?$', '', n) for n in fwant}
    print('原厂 stb_truetype 函数 %d 个（已归一化编译器后缀）' % len(fwant))
    print()
    # 取 stb_truetype.h 的历史提交，抽样
    commits = json.loads(get(
        'https://api.github.com/repos/nothings/stb/commits?path=stb_truetype.h&per_page=40',
        token=True))
    print('stb_truetype.h 提交历史 %d 条，抽样比对:' % len(commits))
    best = []
    seen = set()
    for c in commits:
        sha = c['sha']
        date = c['commit']['author']['date'][:10]
        try:
            raw = get('https://raw.githubusercontent.com/nothings/stb/%s/stb_truetype.h' % sha)
        except Exception as e:
            print('   fetch %s ERR %s' % (sha[:8], e))
            continue
        txt = raw.decode('utf-8', 'replace')
        fgot = extract_names(txt, 'stbtt')
        j = score(fwant, fgot)[0] / max(1, len(fwant | fgot))
        best.append((j, sha[:10], date, len(fgot), txt))
        print('   %s %s  cand=%3d  jaccard=%.3f' % (sha[:8], date, len(fgot), j))
    best.sort(key=lambda x: -x[0])
    print()
    print('=== 最佳匹配 ===')
    for j, sha, date, n, _ in best[:3]:
        print('   %.3f  %s  %s  cand_funcs=%d' % (j, sha, date, n))
    if best:
        j, sha, date, n, txt = best[0]
        m = re.search(r'stb_truetype[^\n]{0,80}', txt)
        print('   header 注释: %s' % (m.group(0)[:80] if m else '—'))
        report('%s (%s)' % (sha, date), fwant, extract_names(txt, 'stbtt'))


def match_mxml():
    fwant = {re.sub(r'\.(isra|part|constprop)(\.\d+)?$', '', f['name'])
             for f in FACTORY['mini-XML']}
    print('原厂 mini-XML 函数 %d 个' % len(fwant))
    print()
    tags = json.loads(get('https://api.github.com/repos/michaelrsweet/mxml/tags?per_page=40',
                          token=True))
    print('mini-XML 标签 %d 个，逐一比对:' % len(tags))
    best = []
    for t in tags:
        name = t['name']
        try:
            tree = json.loads(get(
                'https://api.github.com/repos/michaelrsweet/mxml/git/trees/%s?recursive=1'
                % t['sha'], token=True))
        except Exception as e:
            continue
        srcs = [x['path'] for x in tree.get('tree', [])
                if x['path'].endswith('.c') and x['path'].startswith('mxml')]
        if not srcs:
            srcs = [x['path'] for x in tree.get('tree', [])
                    if x['path'].endswith('.c') and 'mxml' in x['path'].lower()]
        if not srcs:
            continue
        blob = ''
        for s in srcs[:12]:
            try:
                blob += get('https://raw.githubusercontent.com/michaelrsweet/mxml/%s/%s'
                            % (t['sha'], s)).decode('utf-8', 'replace')
            except Exception:
                pass
        fgot = extract_names(blob, 'mxml')
        j = score(fwant, fgot)[0] / max(1, len(fwant | fgot))
        best.append((j, name, len(fgot)))
        print('   %-14s cand=%3d  jaccard=%.3f' % (name, len(fgot), j))
    best.sort(key=lambda x: -x[0])
    print()
    print('=== 最佳匹配 ===')
    for j, name, n in best[:3]:
        print('   %.3f  %s  cand_funcs=%d' % (j, name, n))


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'stb'
    if what == 'stb':
        match_stb()
    elif what == 'mxml':
        match_mxml()
