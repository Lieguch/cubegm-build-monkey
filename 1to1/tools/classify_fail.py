import re
from collections import Counter, defaultdict

raw = open('report/local_recon_build.txt', encoding='utf-8', errors='replace').read()
# 只读「宽松口径失败明细」节（报告现含「假绿清单」+「宽松口径失败明细」两节，避免重复计数）
seg = raw.split('--- 宽松口径失败明细', 1)
body = seg[1] if len(seg) > 1 else raw
lines = body.splitlines()
fail_files = [l for l in lines if l.startswith('src/proprietary/')]
print('宽松口径失败文件:', len(fail_files))

cls = Counter()
ident_names = Counter()
other_samples = []
for l in fail_files:
    errpart = l.split('|', 1)[1] if '|' in l else ''
    for m in re.finditer(r'error: (.*)', errpart):
        t = m.group(1).strip()
        if 'is not a structure or union' in t:
            cls['member-not-struct'] += 1
        elif 'use of undeclared identifier' in t:
            cls['undeclared-ident'] += 1
            nm = re.search(r"'([^']+)'", t)
            ident_names[nm.group(1) if nm else '?'] += 1
        elif 'indirection requires pointer operand' in t:
            cls['indirection'] += 1
        elif 'conflicting types' in t:
            cls['conflicting-types'] += 1
        elif 'incomplete type' in t:
            cls['incomplete-type'] += 1
        elif 'used type' in t:
            cls['used-type-array'] += 1
        else:
            cls['other'] += 1
            other_samples.append(t)
for k, v in cls.most_common():
    print(f'{k:20s} {v}')
print('\n--- undeclared identifier names ---')
for k, v in ident_names.most_common():
    print(f'  {k:30s} {v}')
print('\n--- other samples ---')
for s in other_samples[:15]:
    print('  ', s)
