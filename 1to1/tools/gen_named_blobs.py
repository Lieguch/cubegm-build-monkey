import re, glob, json, os

ROOT='.'
GLOBS=["P1_Table","fontname","m_joysticktab","m_menulog","m_statetab",
"InputDeviceInfo","RF_joy_key","SoundPlayer","TimeCountReg","fpsbuf",
"frame_time_last","game_joy_key","inTimeVal","mui_Effect0","mui_Effect1",
"mui_MenuMusic","outTimeVal","progress_stepcount","spi_id"]

# 1) read declared sizes / kinds from globals.h
gh=open('src/compat/globals.h',encoding='utf-8',errors='replace').read()
decl={}
for n in GLOBS:
    # array decl: extern unsigned char NAME[S];
    ma=re.search(re.escape(n)+r'\s*\[\s*(\d+)\s*\]', gh)
    mp=re.search(r'PTR_'+re.escape(n)+r'_\w+', gh)
    if ma: decl[n]=('arr',int(ma.group(1)))
    elif mp: decl[n]=('ptr',None)
    else:
        mb=re.search(r'gh_blob_t\s+'+re.escape(n), gh)
        decl[n]=('blob444',444) if mb else ('?',None)

# 2) collect (offset,width) accessed per global
accessed={}
for n in GLOBS:
    acc=set()
    for f in glob.glob('src/proprietary/**/*.c',recursive=True):
        t=open(f,encoding='utf-8',errors='replace').read()
        for m in re.finditer(re.escape(n)+r'\._(\d+)_([124])_', t):
            acc.add((int(m.group(1)),int(m.group(2))))
    accessed[n]=sorted(acc)

for n in GLOBS:
    d=decl.get(n)
    acc=accessed[n]
    mx=(max(o+w for o,w in acc)) if acc else 0
    print(f'{n:18s} {str(d):14s} accessed_fields={len(acc):3d} max_span={mx}')
    # show a few
    if acc and len(acc)<=12:
        print('    ', acc)
