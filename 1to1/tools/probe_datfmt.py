"""逆向 `root.dat` / `NNN.dat` 的容器格式（伪装签名的 ZIP）。
只读，不写任何原厂文件。
"""
import struct, zlib, os, sys, collections

R = r'D:/output/原厂SD卡根目录结构'
LOCAL_MAGIC = bytes([0x57, 0x51, 0x57, 0x03])
EOCD_MAGIC  = bytes([0x57, 0x51, 0x57, 0x01])
CDIR_MAGIC  = None   # 待发现

def find_eocd(d):
    """从尾部找 EOCD（伪装签名）。"""
    for magic, label in ((EOCD_MAGIC, 'WQW\\x01'), (b'PK\x05\x06', 'PK\\x05\\x06')):
        i = d.rfind(magic)
        if i >= 0:
            return i, magic, label
    return None, None, None

def parse(path):
    d = open(path, 'rb').read()
    print('=' * 78)
    print('文件: %s   %d B   头 4 = %s' % (os.path.basename(path), len(d), d[:4].hex(' ')))
    eo, magic, label = find_eocd(d)
    if eo is None:
        print('  ★ 找不到 EOCD，中止'); return
    disk, cdisk, n_disk, n_tot, cd_sz, cd_off, clen = struct.unpack_from('<HHHHIIH', d, eo + 4)
    print('  EOCD @%d (%s): 条目数=%d 中央目录 offset=%d size=%d  注释=%d'
          % (eo, label, n_tot, cd_off, cd_sz, clen))
    print('  自洽核对: cd_off+cd_sz+22 = %d  == 文件大小 %d ? %s'
          % (cd_off + cd_sz + 22, len(d), cd_off + cd_sz + 22 == len(d)))
    print('  中央目录处 4 字节 = %s' % d[cd_off:cd_off+4].hex(' '))

    # ---- 前向解析本地记录 ----
    off = 0
    ents = []
    while off + 30 <= len(d) and d[off:off+4] == LOCAL_MAGIC:
        ver, flags, method, tm, dt, crc, csz, usz, fnl, exl = struct.unpack_from('<HHHHHIIIHH', d, off + 4)
        nm = d[off+30:off+30+fnl]
        ds = off + 30 + fnl + exl
        ents.append(dict(off=off, ver=ver, method=method, crc=crc, csz=csz, usz=usz,
                         name=nm, data=ds, exl=exl))
        off = ds + csz
    print('  本地记录 %d 条（解析到 offset=%d）' % (len(ents), off))
    print()
    print('   #   offset    method  csize      usize      name(hex)                  解压后首字节     CRC校验')
    for i, e in enumerate(ents):
        ok = ''
        head = ''
        if e['method'] == 8 and e['data'] + e['csz'] <= len(d):
            try:
                raw = zlib.decompressobj(-15).decompress(d[e['data']:e['data']+e['csz']])
                ok = 'OK' if (zlib.crc32(raw) & 0xffffffff) == e['crc'] else 'CRC✗'
                head = raw[:6].hex(' ')
            except Exception as ex:
                ok = '解压✗'
        elif e['method'] == 0:
            ok = 'stored'
            head = d[e['data']:e['data']+6].hex(' ')
        print('  %2d  %8d  %5d  %9d  %9d  %-24s  %-14s  %s'
              % (i, e['off'], e['method'], e['csz'], e['usz'], e['name'].hex(' '), head, ok))
    # 名称是否可能是被 XOR 的 ASCII（猜 key）
    print()
    print('  --- 名称字节猜测（若为 XOR 后的 ASCII，各位置出现次数最多的 key）---')
    for pos in range(0, 8):
        cnt = collections.Counter()
        for e in ents:
            if pos < len(e['name']):
                b = e['name'][pos]
                for k in range(256):
                    if 0x20 <= (b ^ k) <= 0x7e:
                        cnt[k] += 1
        top = [k for k, v in cnt.most_common(3) if v == max(cnt.values())][:3] if cnt else []
        print('     pos %d: 候选 key = %s' % (pos, ', '.join('0x%02x' % k for k in top) or '无'))
    # 用最常见的单字节 key 试解全部名字
    allb = b''.join(e['name'] for e in ents)
    best = None
    for k in range(256):
        x = bytes(b ^ k for b in allb)
        score = sum(1 for b in x if 0x20 <= b <= 0x7e or b in (0x2e,))
        if best is None or score > best[0]:
            best = (score, k)
    if best and best[0] > len(allb) * 0.8:
        print('     ★ 单字节 key=0x%02x 可读率 %.0f%%: %r' % (best[1], 100.0*best[0]/len(allb),
              bytes(b ^ best[1] for b in allb)))
    else:
        print('     单字节 key 解不出有意义文本（最佳 key=0x%02x 可读率 %.0f%%）'
              % (best[1], 100.0*best[0]/len(allb)))
    return ents

for p in (R + '/root.dat', R + '/002/002.dat'):
    if os.path.exists(p):
        parse(p)
