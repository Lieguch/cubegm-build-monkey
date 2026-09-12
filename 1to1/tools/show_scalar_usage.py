import re, glob
TARGETS = {
 "frame_time_last": None,
 "progress_stepcount": None,
 "RF_joy_key": None,
 "inTimeVal": None,
 "outTimeVal": None,
 "TimeCountReg": None,
}
for n in TARGETS:
    print("="*70)
    print("GLOBAL:", n)
    for f in sorted(glob.glob('src/proprietary/**/*.c', recursive=True)):
        txt = open(f, encoding='utf-8', errors='replace').read().splitlines()
        for i, ln in enumerate(txt, 1):
            if re.search(r'\b'+re.escape(n)+r'\b', ln):
                print(f'  {f}:{i}: {ln.strip()}')
