import re, glob

NAMES = ["frame_time_last","progress_stepcount","RF_joy_key","inTimeVal","outTimeVal","TimeCountReg"]
pat = re.compile(r'\b(' + '|'.join(NAMES) + r')\s*\.\s*_(\d+)_(\d+)_')
hits = {}
for f in glob.glob('src/proprietary/**/*.c', recursive=True):
    t = open(f, encoding='utf-8', errors='replace').read()
    if not pat.search(t):
        continue
    t2 = pat.sub(lambda m: m.group(1) + "_blob._" + m.group(2) + "_" + m.group(3) + "_", t)
    n = len(pat.findall(t))
    open(f, 'w', encoding='utf-8').write(t2)
    hits[f] = n
for f, n in hits.items():
    print(f, n)
print('total files:', len(hits), 'total sites:', sum(hits.values()))
