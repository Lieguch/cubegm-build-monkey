import re, glob, os

# 目标：在 globals.h 中，找出所有 "extern unsigned int NAME;" 但使用证据表明
# NAME 实际持有指针值（mmap/malloc/free/munmap/vfprintf/fopen/fread/fwrite/fclose 等）
# 的全局。这些被 Ghidra undefined4 兜底误标，是假绿的最大单一根因。
# 判据（全为强证据，非猜测）：
#   1) NAME = malloc/fopen/mmap/recv/dlopen 结果
#   2) free(NAME) / munmap(NAME, ...) / fclose(NAME) / dlopen 结果赋给 NAME
#   3) NAME == (void *)0  比较
#   4) 作为指针参数传给 vfprintf/fseek/fread 等
POINTER_CANDIDATE_RE = re.compile(
    r'(?:'
    r'\bNAME\s*=\s*(?:malloc|fopen|mmap|dlopen|recv|calloc|realloc|shmat|open64|open)\b'
    r'|free\s*\(\s*NAME\s*\)'
    r'|munmap\s*\(\s*NAME'
    r'|fclose\s*\(\s*NAME\s*\)'
    r'|dlclose\s*\(\s*NAME'
    r'|NAME\s*==\s*\(void\s*\*\)0'
    r'|NAME\s*=\s*\(void\s*\*\)0'
    r'|vfprintf\s*\(\s*NAME'
    r'|fread\s*\([^,]+,\s*\S+,\s*\S+,\s*NAME'
    r'|fwrite\s*\([^,]+,\s*\S+,\s*\S+,\s*NAME'
    r')',
)

gh = open('src/compat/globals.h', encoding='utf-8', errors='replace').read()
decls = re.findall(r'extern unsigned int (\w+);', gh)

all_src = []
for f in glob.glob('src/proprietary/*/*.c', recursive=True):
    all_src.append(open(f, encoding='utf-8', errors='replace').read())

suspects = []
for name in decls:
    pat = POINTER_CANDIDATE_RE.pattern.replace('NAME', re.escape(name))
    rx = re.compile(pat)
    for src in all_src:
        hits = rx.findall(src)
        if hits:
            # 额外排除：如果同时有 NAME[i] 数组下标用法，则不能改成指针（保留）
            arruse = re.search(re.escape(name) + r'\s*\[\s*\w', src)
            if arruse:
                suspects.append((name, 'HAS_ARRAY_USE', src.split('\\')[-1] if '\\' in src else ''))
            else:
                suspects.append((name, 'POINTER_OK', ''))
            break

seen = set()
print('=== 误标为 unsigned int 实为指针的全局（强证据）===')
for name, verdict, _ in suspects:
    if name in seen:
        continue
    seen.add(name)
    print(f'  {name:24s} {verdict}')
print('\n总计:', len(seen))
