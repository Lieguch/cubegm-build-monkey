import re, os
t = open('report/local_recon_build.txt', encoding='utf-8', errors='replace').read()
seg = t.split('★ 假绿清单',1)[-1].split('--- 宽松口径失败明细',1)[0]
lines = [l for l in seg.splitlines() if '|' in l and 'src/proprietary/' in l]

# 对每个假绿文件：解析第一条 error 的上下文（文件名:行:列 + 源码行），
# 抽取该行里被误赋值/误传的目标标识符（LHS 变量 或 函数实参首词）。
for l in lines:
    fn = l.split('|',1)[0].replace('\\','/').replace('/','/')
    # 相对路径
    rel = fn
    err = l.split('|',1)[1]
    # 找 "path:line:col: error:"
    m = re.search(r'(\d+):(\d+): error: (.*)', err)
    if not m:
        continue
    line_no = int(m.group(1))
    desc = m.group(3)
    # 读取源码该行
    try:
        src = open(rel, encoding='utf-8', errors='replace').read().splitlines()
        code = src[line_no-1].strip() if line_no <= len(src) else '?'
    except Exception:
        code = '?'
    print(f'{os.path.basename(fn):40s} L{line_no:3d} {desc[:45]:45s} | {code[:50]}')
