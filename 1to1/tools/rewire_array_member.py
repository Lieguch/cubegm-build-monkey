import re, glob

# 13 个数组全局：成员访问 NAME._N_M_ → (NAME_blob)._N_M_（匿名嵌套 union 需调用处括号）
NAMES = ["P1_Table","fontname","m_joysticktab","m_menulog","m_statetab",
         "InputDeviceInfo","SoundPlayer","fpsbuf","game_joy_key",
         "mui_Effect0","mui_Effect1","mui_MenuMusic","spi_id","ze"]
# 精确匹配 NAME._<off>_<w>_ 且 NAME 后紧跟 .（排除 &NAME / NAME[ 干扰）
pat = re.compile(r'(?<![&\w])(' + '|'.join(NAMES) + r')\s*\.\s*_(\d+)_(\d)_')

files_changed = 0
sites = 0
for f in glob.glob('src/proprietary/*/*.c', recursive=True):
    t = open(f, encoding='utf-8').read()
    if not pat.search(t):
        continue
    t2, n = pat.subn(lambda m: f'({m.group(1)}_blob)._{m.group(2)}_{m.group(3)}_', t)
    open(f, 'w', encoding='utf-8').write(t2)
    files_changed += 1
    sites += n
    print(f'{f}  sites={n}')
print('---')
print('files changed:', files_changed, ' total member sites rewritten:', sites)
