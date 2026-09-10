import re, os, json, shutil, collections

ROOT = r'D:/output/rkgame-1to1'
PF = r'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function'
FUNCS = r'D:/output/rkgame/decompiled/01-static/functions.txt'

# ---- 1. 复算专有函数集（与源树还原表同规则） ----
UP_PREFIX = ('stbtt_', 'mxml', '_mxml', 'inflate', 'deflate', 'crc32', 'adler32',
             '_Z', 'TUnzip', 'XZip', 'xmp3_', 'DequantBlock', 'WinPrevious',
             'FreqInvert', 'mp3', 'imdct', 'subband', 'polyphase', 'dqchan',
             'huffman', 'hufftabs', 'bitstream', 'scalfact', 'stproc', 'trigtabs',
             'dct32', 'dequant', 'crtstuff', 'deregister_tm', 'register_tm',
             'frame_dummy', '__do_global', 'call_weak_fn', 'iconv', 'localcharset',
             'unicode_', 'wchar_', 'libiconv', 'iso2022', 'aliases', 'mb_',
             'index_', 'CompareUTF8', '__div', '__udiv', '__mod', '__umod',
             '__aeabi', '__float', '__fix', '__cmp', 'MP3Decode', 'MP3Init',
             'MP3FindSyncWord', 'MP3GetLastFrameInfo', 'MP3FreeDecoder')
KW = ('mbtowc', 'wctomb', 'mbsinit', 'mbstowcs', 'wcstombs')
ICONV_RE = re.compile(r'^(ascii|utf8|utf16|utf32|ucs2|ucs4|cp\d|gbk|gb2312|big5|hkscs|sjis|jis|'
                      r'iso8859|koi8|euc|ksc|tis|viscii|armscii|mac_|dec_|nextstep|atarist|'
                      r'riscos|hp_|mulelao|georgian|vietcomb|johab|isoir)')

funcs = []
for ln in open(FUNCS, encoding='utf-8', errors='replace'):
    m = re.match(r'^([0-9a-f]{8})\s+(\d+)\s+(\S+)', ln)
    if m:
        funcs.append((int(m.group(1), 16), int(m.group(2)), m.group(3)))

# 已知模块（用于把 <artificial> 里散落的专有函数归类）
MODULE_OF_FILE = {
    'main.c': 'main', 'EmuRun.c': 'core', 'joystick.c': 'input',
    'ui_jkt.c': 'mui', 'gpio_lib.c': 'hw', 'os_windows_rk.c': 'sys',
    'XUnzip.cpp': 'upstream', 'mxml-attr.c': 'upstream', 'iconv.c': 'upstream',
}


def classify(n):
    if n.startswith('mui_') or n in ('shoucang', 'main_Menu', 'PauseMenu', 'SeletEmuCore',
                                     'mui_DispBlock', 'IsShoucang', 'popwindows',
                                     'popoffwindows', 'outputxy', 'uidraw'):
        return 'mui'
    if n.startswith(('sfc_', 'spi_', 'SPI_', 'snor_', 'sflash', 'UpdateROM', 'ShareMem',
                     'GetRomInfo', 'sunxi')):
        return 'flash'
    if n.startswith(('Init', 'Deinit', 'disp', 'Sound', 'Audio', 'DrawFrame', 'PlayFrame',
                     'video_', 'lcd', 'hdmi', 'dispFlip', 'volume')):
        return 'hw'
    if n.startswith(('joy', 'Joy', 'ReadUSBJoy', 'TestUSBJoy', 'buttontoi', 'key')) or \
       'Joystick' in n:
        return 'input'
    if n.startswith(('GetConfig', 'config', 'SaveKey', 'LoadKey', 'InitKeyMapping')):
        return 'config'
    # 模拟器核心加载器（专有：每个 libemu_*.so 一个 *_Load 入口）
    if (n.endswith('_Load') and n != 'Core_Load') or n.startswith(('EmuCore', 'filelist_run_game',
                                                                  'FilePreEmu', 'TestRun',
                                                                  'TestLibz0', 'run_game')):
        return 'core'
    if n.startswith(('Core_', 'Load_Proc', 'EmuRun', 'environment', 'retro',
                     'LoadEmu', 'UnloadEmu', 'log_dummy')):
        return 'core'
    if n == 'main' or n.startswith('main'):
        return 'main'
    return 'misc'


prop = []
for a, s, n in funcs:
    if any(n.startswith(p) for p in UP_PREFIX):
        continue
    if any(k in n for k in KW) or ICONV_RE.match(n):
        continue
    prop.append((a, s, n))

# ---- 2. 建立工作区 ----
for sub in ('src/proprietary', 'src/upstream', 'ledger', 'report'):
    os.makedirs(os.path.join(ROOT, sub), exist_ok=True)
for mod in ('main', 'mui', 'core', 'hw', 'input', 'config', 'flash', 'sys', 'misc'):
    os.makedirs(os.path.join(ROOT, 'src/proprietary', mod), exist_ok=True)

# 索引单函数文件：addr -> filename
by_addr = {}
for fn in os.listdir(PF):
    m = re.match(r'^FUN_([0-9a-f]{8})_(.+)\.c$', fn)
    if m:
        by_addr[int(m.group(1), 16)] = fn

rows = []
copied = 0
for a, s, n in prop:
    mod = classify(n)
    fn = by_addr.get(a)
    dest = ''
    if fn:
        d = os.path.join(ROOT, 'src/proprietary', mod,
                         'FUN_%08x_%s.c' % (a, re.sub(r'[^\w.]', '_', n)))
        if not os.path.exists(d):
            try:
                shutil.copyfile(os.path.join(PF, fn), d)
                copied += 1
            except Exception:
                pass
        dest = os.path.relpath(d, ROOT).replace('\\', '/')
    rows.append({'addr': '0x%08x' % a, 'size': s, 'name': n,
                 'module': mod, 'src': dest, 'status': 'TODO', 'tier': ''})

json.dump(rows, open(os.path.join(ROOT, 'ledger', 'functions.json'), 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)

# ---- 3. 台账 CSV ----
csv = ['addr,size,name,module,status,tier,src']
for r in sorted(rows, key=lambda x: (-x['size'])):
    csv.append('%s,%d,%s,%s,%s,%s,%s' % (r['addr'], r['size'], r['name'], r['module'],
                                         r['status'], r['tier'], r['src']))
open(os.path.join(ROOT, 'ledger', 'functions.csv'), 'w', encoding='utf-8').write('\n'.join(csv))

by_mod = collections.Counter(r['module'] for r in rows)
by_mod_b = collections.Counter()
for r in rows:
    by_mod_b[r['module']] += r['size']

print('专有函数 %d 个 / %d B，已拷入工作区 %d 个' % (len(rows), sum(r['size'] for r in rows), copied))
print()
print('%-10s %6s %10s' % ('模块', '函数', '字节'))
for m, c in by_mod.most_common():
    print('%-10s %6d %10d' % (m, c, by_mod_b[m]))
print()
print('台账: ledger/functions.csv + ledger/functions.json')
print('工作区: src/proprietary/{main,mui,core,hw,input,config,flash,sys,misc}/')
