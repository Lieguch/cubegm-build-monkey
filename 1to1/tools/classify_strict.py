import re
from collections import Counter
t = open('report/local_recon_build.txt', encoding='utf-8', errors='replace').read()
# 假绿区块在 “★ 假绿清单” 与 “--- 宽松口径失败明细” 之间
seg = t.split('★ 假绿清单',1)[-1].split('--- 宽松口径失败明细',1)[0]
lines = [l for l in seg.splitlines() if '|' in l and 'src/proprietary/' in l]
print('假绿文件数:', len(lines))
# 每个文件取前 3 错的 error 描述聚类
cls = Counter()
for l in lines:
    err = l.split('|',1)[1]
    for m in re.finditer(r'error: ([^|]+)', err):
        d = m.group(1).strip()
        if 'pointer to integer' in d or ('integer' in d and 'pointer' in d):
            cls['int/pointer 混用(全局误标)'] += 1
        elif 'incompatible pointer types' in d:
            cls['pointer 类型不匹配'] += 1
        elif 'incompatible function pointer' in d:
            cls['function pointer 不匹配'] += 1
        elif 'implicit declaration' in d:
            cls['未声明函数'] += 1
        elif 'incomplete type' in d:
            cls['不完整类型'] += 1
        elif 'too few' in d or 'too many' in d:
            cls['参数个数不符'] += 1
        else:
            cls['other: '+d[:40]] += 1
for k,v in cls.most_common():
    print(f'  {v:3d}  {k}')
print('\n=== 各假绿文件首错(便于定位全局根因) ===')
for l in lines:
    fn = l.split('|',1)[0].replace('\\','/')
    err = l.split('|',1)[1]
    m = re.search(r'error: .{0,90}', err)
    print(f'  {fn.split("/")[-1]:40s} {m.group(0) if m else "?"}')
