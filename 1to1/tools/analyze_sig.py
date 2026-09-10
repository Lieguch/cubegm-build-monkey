#!/usr/bin/env python3
"""
analyze_sig.py — 从反编译产物取证：声明签名 vs 函数体实际行为的**不一致清单**。

目的：CI 实测 131 个失败中，主因是
  a) `void value not ignored as it ought to be` —— 声明为 void，函数体却 return 值
  b) `too few arguments to function`           —— 声明参数少于函数体实际用到的 param_N
本工具**不猜**：直接从 ALL.c 的**函数体文本**推导事实，产出可核对的差异表。

推导规则（纯文本事实，非经验）：
  · 返回类型：函数体内出现 `return <非空表达式>;`  => 声明不能是 void
  · 参数个数：函数体内引用的最大 param_N            => 声明至少要 N 个参数
用法: python tools/analyze_sig.py [--json out.json]
"""
import re, json, sys, os

ALL = r'D:/output/rkgame/decompiled/02-ghidra-c/00_rkgame_ALL.c'
LEDGER = r'D:/output/rkgame-1to1/ledger/functions.json'

PROP = {r['name'] for r in json.load(open(LEDGER, encoding='utf-8'))}
lines = open(ALL, encoding='utf-8', errors='replace').read().splitlines()

SIG_RE = re.compile(r'^([A-Za-z_][\w \*]*?[\w\*])\s+(\*?)(\w+)\s*\((.*)\)\s*$')

rows = []
i, n = 0, len(lines)
while i < n:
    if lines[i].startswith('/* ===='):
        while i < n and '*/' not in lines[i]:
            i += 1
        i += 1
        while i < n and (not lines[i].strip() or lines[i].lstrip().startswith('/*')):
            i += 1
        if i >= n:
            break
        sig = lines[i].strip()
        m = SIG_RE.match(sig)
        if not m:
            i += 1
            continue
        ret, name, args = m.group(1).strip(), m.group(3), m.group(4)
        # 找函数体：从 '{' 所在行起做花括号配平
        j = i + 1
        while j < n and lines[j].strip() != '{':
            j += 1
        depth = 0
        body = []
        started = False
        while j < n:
            ln = lines[j]
            depth += ln.count('{') - ln.count('}')
            body.append(ln)
            if ln.count('{'):
                started = True
            if started and depth <= 0:
                break
            j += 1
        bodytext = '\n'.join(body)

        if name in PROP:
            # 事实 1：是否有 return 非空值
            value_returns = [x for x in re.findall(r'\breturn\s+([^;]+);', bodytext)
                             if x.strip() and x.strip() != '']
            # 事实 2：最大 param_N
            pn = [int(x) for x in re.findall(r'\bparam_(\d+)\b', bodytext)]
            maxp = max(pn) if pn else 0
            _a = args.strip()
            decl_p = 0 if _a in ('void', '') else _a.count(',') + 1
            rows.append({
                'name': name, 'decl_ret': ret, 'decl_args': args.strip(),
                'decl_nparams': decl_p, 'body_max_param': maxp,
                'body_nvalue_return': len(value_returns),
                'ret_mismatch': ('void' in ret and len(value_returns) > 0),
                'params_mismatch': (maxp > decl_p),
            })
        i = j + 1 if j < n else n
    else:
        i += 1

for r in rows:
    r['bad'] = r['ret_mismatch'] or r['params_mismatch']

print('专有函数分析: %d 个' % len(rows))
print('  返回类型不一致 (void 却 return 值): %d' % sum(r['ret_mismatch'] for r in rows))
print('  参数个数不一致 (用了 param_N 但声明不足): %d' % sum(r['params_mismatch'] for r in rows))
print('  两者之一异常: %d' % sum(r['bad'] for r in rows))
print()
print('--- 异常样本 (前 30) ---')
print('%-34s %-10s %-6s %-6s %-6s' % ('函数', '声明返回', '声明参', '体内max', '返回值数'))
for r in [x for x in rows if x['bad']][:30]:
    print('%-34s %-10s %-6d %-6d %-6d' % (r['name'], r['decl_ret'], r['decl_nparams'],
                                          r['body_max_param'], r['body_nvalue_return']))

if '--json' in sys.argv:
    out = sys.argv[sys.argv.index('--json') + 1]
    json.dump(rows, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('\n->', out)
