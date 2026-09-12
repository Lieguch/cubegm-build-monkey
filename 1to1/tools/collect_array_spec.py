import re, glob, os
from collections import defaultdict

ARRAYS = ["P1_Table","fontname","m_joysticktab","m_menulog","m_statetab",
          "InputDeviceInfo","SoundPlayer","fpsbuf","game_joy_key",
          "mui_Effect0","mui_Effect1","mui_MenuMusic","spi_id"]

# 1) 真实声明尺寸（globals.h）
gh = open('src/compat/globals.h', encoding='utf-8').read()
declsize = {}
for n in ARRAYS:
    m = re.search(r'extern (?:unsigned char|char)\s+' + re.escape(n) + r'\[(\d+)\];', gh)
    declsize[n] = int(m.group(1)) if m else None

# 2) 完整 (offset,width) 字段集合 + 字节下标用法 + &NAME 用法
fields = {n: set() for n in ARRAYS}
byteidx = defaultdict(set)   # n -> 是否 NAME[i] 字节下标
amptake = defaultdict(int)   # n -> &NAME 出现数
for f in glob.glob('src/proprietary/*/*.c', recursive=True):
    t = open(f, encoding='utf-8').read()
    for n in ARRAYS:
        for m in re.finditer(re.escape(n) + r'\s*\.\s*_(\d+)_(\d)_', t):
            fields[n].add((int(m.group(1)), int(m.group(2))))
        for m in re.finditer(re.escape(n) + r'\s*\[', t):
            byteidx[n].add(f)
        amptake[n] += len(re.findall(r'&\s*' + re.escape(n) + r'(?![\w\[])', t))

for n in ARRAYS:
    fs = sorted(fields[n])
    mx = max(o+w for o,w in fs) if fs else 0
    widths = sorted({w for _,w in fs})
    print(f'{n:16s} decl={declsize[n]:4} fields={len(fs):3d} max_span={mx:4d} widths={widths} byteidx_files={len(byteidx[n])} &NAME={amptake[n]}')
    if len(fs) <= 12:
        print(f'              {fs}')
