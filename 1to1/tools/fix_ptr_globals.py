import re
path = 'src/compat/globals.h'
lines = open(path, encoding='utf-8').read().splitlines()

# 12 个纯指针全局（idx=0 且 cast=0，强证据）：
names = {"log_file_fp","GPIO0","GPIO1","GPIO2","handle",
         "fontbuffer","scrbuf","bimapFilebuffer","rotation_buff",
         "ZIP_BUF","romfile","scr_buf"}
# 精确类型（证据）：log_file_fp 持有 stderr/fopen 结果 + vfprintf 实参 → FILE*；
# 其余为 malloc/mmap 句柄 → void*。ARM32 下均 4B，ABI 不变。
NAME_TYPE = {"log_file_fp": "FILE *"}
default_type = "void *"

changed = 0
out = []
for ln in lines:
    m2 = re.match(r'^.*extern unsigned int (\w+);(.*)$', ln)
    if m2 and m2.group(1) in names:
        n = m2.group(1)
        t = NAME_TYPE.get(n, default_type)
        ln = re.sub(r'extern unsigned int ' + n + r';',
                    'extern ' + t + ' ' + n + ';', ln)
        ln = ln.rstrip() + '  /* 类型修正：指针误标(undefined4兜底→真实类型, ARM32 4B ABI不变) */'
        changed += 1
    out.append(ln)

open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('retyped', changed, 'globals -> void*')
