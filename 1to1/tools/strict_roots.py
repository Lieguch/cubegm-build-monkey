import re, os
from collections import Counter, defaultdict

t = open('report/local_recon_build.txt', encoding='utf-8', errors='replace').read()
seg = t.split('★ 假绿清单',1)[-1].split('--- 宽松口径失败明细',1)[0]
lines = [l for l in seg.splitlines() if '|' in l and 'src/proprietary/' in l]

# 从每个假绿文件的第一条 error 里，抓 "passing 'X' to parameter of type 'Y'"
# 或 "assigning to 'A' from 'B'"，定位涉及的标识符
files = defaultdict(list)
for l in lines:
    fn = l.split('|',1)[0].replace('\\','/').split('/')[-1]
    body = l.split('|',1)[1]
    for m in re.finditer(r"passing\s+'([^']+)'", body):
        files[fn].append('PASS:' + m.group(1))
    for m in re.finditer(r"assigning to\s+'([^']+)'\s+from\s+'([^']+)'", body):
        files[fn].append('ASSIGN:' + m.group(2) + '->' + m.group(1))

# 汇总：被误传的实参类型 / 被赋值的参数类型
pat = Counter()
for fn, items in files.items():
    for it in items:
        pat[it.split(':',1)[1]] += 1

print('=== 假绿实参/赋值类型分布（前 25）===')
for k,v in pat.most_common(25):
    print(f'  {v:3d}  {k}')

print('\n=== 涉及文件 → 首条类型冲突 ===')
for fn in sorted(files):
    print(f'  {fn:42s} {files[fn][0]}')
