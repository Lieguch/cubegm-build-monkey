import re, glob, os, json
# Determine, per target global: decl kind/size, accessed fields, dynamic-array-idx count,
#  and whether any PASSING file references it.
passing=set()
for f in glob.glob('report/pass_files.txt',recursive=True):
    passing=set(open(f).read().split())
# no pass file; instead derive from last report? We have only fail list.
fail_files=[l.split('|',1)[0] for l in open('report/local_recon_build.txt',encoding='utf-8',errors='replace').read().splitlines() if l.startswith('src/proprietary/')]

TARGETS=["P1_Table","fontname","m_joysticktab","m_menulog","m_statetab","InputDeviceInfo",
"SoundPlayer","fpsbuf","game_joy_key","mui_Effect0","mui_Effect1","mui_MenuMusic","spi_id",
"RF_joy_key","TimeCountReg","frame_time_last","inTimeVal","outTimeVal","progress_stepcount"]

def decl_info(n):
    gh=open('src/compat/globals.h',encoding='utf-8',errors='replace').read()
    if re.search(re.escape(n)+r'\s*\[\s*(\d+)\s*\]', gh):
        m=re.search(re.escape(n)+r'\s*\[\s*(\d+)\s*\]',gh); return ('arr',int(m.group(1)))
    if re.search(r'PTR_'+re.escape(n)+r'_\w+', gh): return ('ptr',None)
    return ('?',None)

for n in TARGETS:
    kind,size=decl_info(n)
    acc=set(); dyn=0; ref_files=set()
    for f in glob.glob('src/proprietary/**/*.c',recursive=True):
        t=open(f,encoding='utf-8',errors='replace').read()
        for m in re.finditer(re.escape(n)+r'\._(\d+)_([124])_',t):
            acc.add((int(m.group(1)),int(m.group(2))))
        dyn+=len(re.findall(re.escape(n)+r'\s*\[',t))
        if re.search(re.escape(n)+r'\b',t): ref_files.add(f)
    infail=any(n in open(fw,encoding='utf-8',errors='replace').read() for fw in fail_files)
    print(f'{n:18s} {kind:4s} sz={str(size):5s} fields={len(acc):3d} dynidx={dyn:2d} referenced_by_failing_files={infail}')
