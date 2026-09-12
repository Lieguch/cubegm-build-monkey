import re
names = ["IR_JoyKey","InputDeviceInfo","OutRect","P1_Table","RF_joy_key","SoundPlayer",
"TimeCountReg","fontname","fpsbuf","frame_time_last","game","game_joy_key","inTimeVal",
"joy_key","local_118","m_joysticktab","m_menulog","m_statetab","mui_Effect0","mui_Effect1",
"mui_MenuMusic","outTimeVal","progress_stepcount","spi_id","this_frame","ze"]
gh = open('src/compat/globals.h', encoding='utf-8', errors='replace').read()
# find the extern declaration line for each name
for n in names:
    pat = re.compile(r'^\s*extern\s+([^\n;]*\b' + re.escape(n) + r')\s*;', re.M)
    m = pat.search(gh)
    if m:
        line = m.group(1)
        kind = 'BLOB' if 'gh_blob_t' in line else ('ARR' if '[' in line else 'OTHER')
        print(f'{n:20s} {kind:6s} | {line.strip()}')
    else:
        # maybe not extern; search raw
        for ln in gh.splitlines():
            if n in ln and ('extern' in ln or ln.strip().startswith(n)):
                print(f'{n:20s} FOUND?   | {ln.strip()[:80]}')
                break
        else:
            print(f'{n:20s} MISSING| (no extern decl found)')
