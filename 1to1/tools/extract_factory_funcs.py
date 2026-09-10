import re, json, os, collections

F = r'D:/output/rkgame/decompiled/01-static/functions.txt'
funcs = []
for ln in open(F, encoding='utf-8', errors='replace'):
    m = re.match(r'^([0-9a-f]{8})\s+(\d+)\s+(\S+)', ln)
    if m:
        funcs.append((int(m.group(1), 16), int(m.group(2)), m.group(3)))

components = {
    'stb_truetype': lambda n: n.startswith('stbtt_'),
    'mini-XML':     lambda n: n.startswith('mxml_') or n.startswith('_mxml'),
    'XUnzip':       lambda n: n.startswith('_Z') or n.startswith('TUnzip') or n.startswith('XZip'),
    'HelixMP3':     lambda n: n.startswith('xmp3_') or n in (
                        'DequantBlock', 'WinPrevious', 'FreqInvertRescale', 'WinNumPrev',
                        'DecodeHuffman', 'UnpackScaleFactors', 'IMDCT', 'FDCT32'),
    'zlib':         lambda n: n.startswith('inflate') or n.startswith('deflate')
                              or n.startswith('crc32') or n.startswith('adler32')
                              or n in ('zlibVersion', 'zlibCompileFlags', 'compress', 'uncompress'),
}

out = {}
for name, pred in components.items():
    hits = [(a, s, n) for a, s, n in funcs if pred(n)]
    out[name] = [{'addr': '0x%08x' % a, 'size': s, 'name': n} for a, s, n in hits]
    print('%-14s %4d 函数  %7d B' % (name, len(hits), sum(s for _, s, _ in hits)))

os.makedirs(r'D:/output/rkgame-1to1/upstream', exist_ok=True)
json.dump(out, open(r'D:/output/rkgame-1to1/upstream/factory_component_funcs.json',
                    'w', encoding='utf-8'), indent=1, ensure_ascii=False)

print()
print('--- stb_truetype 原厂函数名全表 (%d) ---' % len(out['stb_truetype']))
for i, f in enumerate(out['stb_truetype']):
    print('  %-42s %5d' % (f['name'], f['size']), end='\n' if i % 2 else '')
print()
print('--- mini-XML 原厂函数名全表 (%d) ---' % len(out['mini-XML']))
for f in out['mini-XML']:
    print('  %-34s %5d' % (f['name'], f['size']))
print()
print('--- XUnzip 原厂符号 (%d, 前 20) ---' % len(out['XUnzip']))
for f in out['XUnzip'][:20]:
    print('  %-48s %5d' % (f['name'], f['size']))
