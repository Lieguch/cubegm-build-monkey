import re, os, json, ssl, urllib.request

CTX = ssl._create_unverified_context()
TOK = os.environ.get('GH_TOKEN', '')   # 从环境变量读取，禁止硬编码


def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'vm', 'Authorization': 'Bearer ' + TOK})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.read()


F = json.load(open(r'D:/output/rkgame-1to1/upstream/factory_component_funcs.json', encoding='utf-8'))
fw = {re.sub(r'\.(isra|part|constprop)(\.\d+)?$', '', f['name']) for f in F['stb_truetype']}

# 取 stb_truetype.h 全部历史提交（分页），建立版本 -> 函数集
commits = []
for pg in (1, 2, 3):
    commits += json.loads(get(
        'https://api.github.com/repos/nothings/stb/commits?path=stb_truetype.h&per_page=100&page=%d' % pg))
print('历史提交总数:', len(commits))

rows = []
for c in commits:
    sha, date = c['sha'], c['commit']['author']['date'][:10]
    try:
        txt = get('https://raw.githubusercontent.com/nothings/stb/%s/stb_truetype.h' % sha).decode('utf-8', 'replace')
    except Exception:
        continue
    ver = re.search(r'stb_truetype\.h - (v[\d.]+)', txt)
    names = set(re.findall(r'\b(stbtt_+\w+)\s*\(', txt))
    miss = fw - names                 # 原厂有、候选无  -> 候选太旧
    rows.append((date, sha[:8], ver.group(1) if ver else '?', len(names), len(miss), sorted(miss)))

rows.sort()
print()
print('%-12s %-9s %-7s %5s %6s  %s' % ('日期', 'sha', '版本', 'cand', '原厂缺失', '缺失样本'))
for d, s, v, n, m, ml in rows:
    print('%-12s %-9s %-7s %5d %6d  %s' % (d, s, v, n, m, ','.join(ml[:3])[:44]))

ok = [r for r in rows if r[4] == 0]
print()
if ok:
    print('★ 覆盖全部 81 个原厂函数的版本区间: %s (%s) .. %s (%s)' % (ok[0][0], ok[0][2], ok[-1][0], ok[-1][2]))
    print('  -> 精确版本需在 CI 用同工具链编译后按函数尺寸/指令序列比对落定（P2-A 门禁）')
else:
    print('！无任何版本覆盖全部 81 个原厂函数 —— 需检查是否为定制/裁剪版')
