import re, glob, os
globs = ["P1_Table","fontname","m_joysticktab","m_menulog","m_statetab",
"InputDeviceInfo","RF_joy_key","SoundPlayer","TimeCountReg","fpsbuf",
"frame_time_last","game_joy_key","inTimeVal","mui_Effect0","mui_Effect1",
"mui_MenuMusic","outTimeVal","progress_stepcount","spi_id"]
# declared sizes from globals.h
decl = {
"P1_Table":220,"fontname":32,"m_joysticktab":924,"m_menulog":444,"m_statetab":144,
"InputDeviceInfo":None,"RF_joy_key":None,"SoundPlayer":None,"TimeCountReg":None,
"fpsbuf":None,"frame_time_last":None,"game_joy_key":None,"inTimeVal":8,
"mui_Effect0":None,"mui_Effect1":None,"mui_MenuMusic":None,"outTimeVal":8,
"progress_stepcount":None,"spi_id":None,
}
for n in globs:
    offs=set(); m1=set(); m4=set(); m2=set()
    for f in glob.glob('src/proprietary/**/*.c', recursive=True):
        t=open(f,encoding='utf-8',errors='replace').read()
        for m in re.finditer(re.escape(n)+r'\._([0-9]+)_([0-9]+)_', t):
            o=int(m.group(1)); w=int(m.group(2))
            offs.add(o)
            if w==1:m1.add(o)
            elif w==2:m2.add(o)
            elif w==4:m4.add(o)
    mx=max(offs)+ (4 if m4 else (1 if m1 else 0)) if offs else 0
    print(f'{n:18s} decl={str(decl.get(n)):6s} max_off_needed={mx:4d}  m1_cnt={len(m1)} m2_cnt={len(m2)} m4_cnt={len(m4)}')
