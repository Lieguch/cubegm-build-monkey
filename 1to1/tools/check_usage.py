import re, glob, os
# named globals that get _N_M_ member access
globs = ["P1_Table","fontname","joy_key_mask","m_joysticktab","m_menulog","m_statetab"]
# Also the PTR_ ones accessed via . not ->? Check those too:
ptrs = ["InputDeviceInfo","RF_joy_key","SoundPlayer","TimeCountReg","fpsbuf",
        "frame_time_last","game_joy_key","inTimeVal","mui_Effect0","mui_Effect1",
        "mui_MenuMusic","outTimeVal","progress_stepcount","spi_id"]

# Build a usage map across all function files
allfiles = glob.glob('src/proprietary/**/*.c', recursive=True)
def uses(name):
    member = idx = addr = 0
    mfiles=set(); ifiles=set(); afiles=set()
    for f in allfiles:
        t=open(f,encoding='utf-8',errors='replace').read()
        mem=re.findall(re.escape(name)+r'\._[0-9]+_[0-9]+', t)
        arr=re.findall(re.escape(name)+r'\s*\[\s*[^\]]', t)
        adr=re.findall(r'&\s*'+re.escape(name)+r'(?![\w\[])', t)
        if mem: mfiles.add(f); member+=len(mem)
        if arr: ifiles.add(f); idx+=len(arr)
        if adr: afiles.add(f); addr+=len(adr)
    return member, idx, addr, mfiles, ifiles, afiles

for n in globs+ptrs:
    member, idx, addr, mf, inf, af = uses(n)
    print(f'{n:18s} member={member:4d} arrayidx={idx:3d} addr-of={addr:3d}')
    # list member files (short)
    for f in sorted(mf):
        print(f'      .m  {os.path.relpath(f)}')
    for f in sorted(inf):
        print(f'      []  {os.path.relpath(f)}')
    for f in sorted(af):
        print(f'      &   {os.path.relpath(f)}')
