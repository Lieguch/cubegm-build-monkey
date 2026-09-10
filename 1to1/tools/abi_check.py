#!/usr/bin/env python3
"""
abi_check.py — ABI 门禁：重建产物必须与原厂 ELF 规格逐字段一致。

本门禁**不依赖编译器版本**，是 P3 的硬关卡。
原厂规格（实测自 D:/output/rkgame/rkgame）：
  e_type    = 0x2   (ET_EXEC，非 PIE)
  e_machine = 0x28  (EM_ARM)
  e_flags   = 0x5000400  (EABIv5 + hard-float)
  .interp   = /lib/ld-linux-armhf.so.3
  必需动态库: libc.so.6 等

用法:
  abi_check.py <binary> [--expect-interp /lib/ld-linux-armhf.so.3]
退出: 0=全通过  2=有失败
"""
import struct, sys

EXPECT = {
    'e_type': 0x2,
    'e_machine': 0x28,
    'e_flags': 0x5000400,
}
DEFAULT_INTERP = '/lib/ld-linux-armhf.so.3'


def read_elf(p):
    d = open(p, 'rb').read()
    if d[:4] != b'\x7fELF':
        return None, 'not an ELF'
    ei_class = d[4]          # 1=32bit 2=64bit
    ei_data = d[5]           # 1=LE 2=BE
    if ei_class != 1:
        return None, 'not ELF32 (ei_class=%d)' % ei_class
    if ei_data != 1:
        return None, 'not little-endian (ei_data=%d)' % ei_data
    if len(d) < 52:
        return None, 'truncated ELF header'
    e_type = struct.unpack_from('<H', d, 16)[0]
    e_machine = struct.unpack_from('<H', d, 18)[0]
    e_flags = struct.unpack_from('<I', d, 36)[0]
    i = d.find(b'/lib/ld-linux')
    interp = d[i:d.index(b'\x00', i)].decode('ascii', 'replace') if i != -1 else None
    needed = []
    for lib in (b'libc.so.6', b'libz.so.1', b'libdl.so.2', b'libm.so.6',
                b'libpthread.so.0', b'libstdc++.so.6', b'libgcc_s.so.1'):
        if lib in d:
            needed.append(lib.decode())
    return {'e_type': e_type, 'e_machine': e_machine, 'e_flags': e_flags,
            'interp': interp, 'size': len(d), 'needed': needed}, None


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    p = sys.argv[1]
    exp_interp = DEFAULT_INTERP
    if '--expect-interp' in sys.argv:
        exp_interp = sys.argv[sys.argv.index('--expect-interp') + 1]
    info, err = read_elf(p)
    print('=' * 62)
    print('ABI 门禁  %s' % p)
    print('=' * 62)
    if err:
        print('  [FAIL] %s' % err)
        return 2
    fails = 0

    def chk(name, got, want):
        nonlocal fails
        ok = (got == want)
        if not ok:
            fails += 1
        print('  [%s] %-12s got=%s  want=%s'
              % ('PASS' if ok else 'FAIL', name,
                 (('0x%x' % got) if isinstance(got, int) else got),
                 (('0x%x' % want) if isinstance(want, int) else want)))

    chk('e_type', info['e_type'], EXPECT['e_type'])
    chk('e_machine', info['e_machine'], EXPECT['e_machine'])
    chk('e_flags', info['e_flags'], EXPECT['e_flags'])
    chk('interp', info['interp'], exp_interp)
    print('  [INFO] size=%d  needed=%s' % (info['size'], ','.join(info['needed']) or '-'))
    print('-' * 62)
    print('  结果: %s (%d 项失败)' % ('PASS' if fails == 0 else 'FAIL', fails))
    return 0 if fails == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
