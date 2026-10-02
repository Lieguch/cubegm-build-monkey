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
    # ★★★★★ 2026-10-01（第 109 轮）根修：**不许再用「全文件子串搜索」找 INTERP**。
    #   旧实现 `i = d.find(b'/lib/ld-linux')` 会让宿主路径
    #   `C:/.../PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3` **截出** `'/lib/ld-linux-armhf.so.3'`
    #   ⇒ 门禁判 PASS，而真机上内核 execve 直接 ENOENT ⇒ 进程根本不启动 ⇒ 「开机失败 + 零日志」。
    #   这正是纪律 62 的同类错误：**子串包含不是相等**。
    #   现在只认**程序头里 p_type==PT_INTERP 的那一段字节**。
    interp = None
    if len(d) >= 52:
        e_phoff = struct.unpack_from('<I', d, 28)[0]
        e_phentsize = struct.unpack_from('<H', d, 42)[0]
        e_phnum = struct.unpack_from('<H', d, 44)[0]
        if e_phoff + e_phnum * e_phentsize <= len(d):
            for _i in range(e_phnum):
                _o = e_phoff + _i * e_phentsize
                _t, _off, _va, _pa, _fsz = struct.unpack_from('<5I', d, _o)
                if _t == 3 and _off + _fsz <= len(d):
                    interp = d[_off:_off + _fsz].split(b'\x00')[0].decode('ascii', 'replace')
                    break
    # 宿主痕迹（ARM 目标上无合法来源）
    host_marks = []
    for m in (b'PortableGit', b'.workbuddy', b'site-packages', b'AppData',
              b'C:/Users', b'C:\\', b'/c/Users', b'ziglang'):
        j = d.find(m)
        while j >= 0:
            host_marks.append((j, m.decode('latin-1')))
            j = d.find(m, j + 1)
    needed = []
    for lib in (b'libc.so.6', b'libz.so.1', b'libdl.so.2', b'libm.so.6',
                b'libpthread.so.0', b'libstdc++.so.6', b'libgcc_s.so.1'):
        if lib in d:
            needed.append(lib.decode())
    return {'e_type': e_type, 'e_machine': e_machine, 'e_flags': e_flags,
            'interp': interp, 'size': len(d), 'needed': needed,
            'host_marks': sorted(host_marks)}, None


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 1
    if sys.argv[1] == '--selftest':
        return selftest(sys.argv[2])
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
    # P1b：INTERP 必须是绝对 POSIX 路径（宿主盘符 / 反斜杠一律不合格）
    abs_ok = bool(info['interp']) and info['interp'].startswith('/') \
        and ':' not in info['interp'] and '\\' not in info['interp']
    if not abs_ok:
        fails += 1
    print('  [%s] %-12s got=%s  want=%s'
          % ('PASS' if abs_ok else 'FAIL', 'interp-abs',
             info['interp'], '以 / 开头的 POSIX 绝对路径'))
    # P3：全文件不得含工具链宿主痕迹（ARM 目标上无合法来源）
    hm = info['host_marks']
    if hm:
        fails += 1
        print('  [FAIL] %-12s 命中 %d 处：%s'
              % ('host-marks', len(hm),
                 ', '.join('0x%x:%s' % (o, m) for o, m in hm[:6])))
    else:
        print('  [PASS] %-12s 无宿主路径痕迹' % 'host-marks')
    print('  [INFO] size=%d  needed=%s' % (info['size'], ','.join(info['needed']) or '-'))
    print('-' * 62)
    print('  结果: %s (%d 项失败)' % ('PASS' if fails == 0 else 'FAIL', fails))
    return 0 if fails == 0 else 2


def selftest(path):
    """自证：把 INTERP 换成宿主路径 ⇒ interp-abs 必须 FAIL；同时校验对干净产物必须 PASS。

    纯内存，不落临时文件（规避本机沙箱删除守卫）。
    """
    import io as _io
    d0 = _io.open(path, 'rb').read()
    info0, err = read_elf(path)
    ok0 = (err is None and info0['interp'] == DEFAULT_INTERP and not info0['host_marks'])
    print('  ① 原始产物（期望 PASS）: %s interp=%r host_marks=%d'
          % ('PASS' if ok0 else 'FAIL', info0['interp'] if not err else err,
             len(info0['host_marks']) if not err else -1))
    # 构造一个"宿主路径但含 /lib/ld-linux 子串"的坏文件（正是旧实现被骗过的形态）
    off = struct.unpack_from('<I', d0, 28)[0]
    phent = struct.unpack_from('<H', d0, 42)[0]
    phnum = struct.unpack_from('<H', d0, 44)[0]
    bad = b'C:/Users/x/PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3\x00'
    toff = tfsz = None
    for i in range(phnum):
        o = off + i * phent
        t, o2, va, pa, fsz = struct.unpack_from('<5I', d0, o)
        if t == 3:
            toff, tfsz = o2, fsz
    rc_bad = 11
    if toff is not None and tfsz >= len(bad):
        b = bytearray(d0)
        b[toff:toff + tfsz] = bad + b'\x00' * (tfsz - len(bad))
        # 直接调用内部判据（不写盘）
        import io as _i2
        fake = path
        _orig = _i2.open

        class _B(object):
            def __init__(self, x):
                self._x = x

            def read(self):
                return bytes(b)
        try:
            _i2.open = lambda *a, **k: _B(b)
            import sys as _s
            argv_bak = _s.argv
            _s.argv = ['abi_check.py', fake]
            import io as _io3
            buf = _io3.StringIO()
            out_bak = _s.stdout
            _s.stdout = buf
            try:
                rc_bad = main()
            finally:
                _s.stdout = out_bak
                _s.argv = argv_bak
            txt = buf.getvalue()
        finally:
            _i2.open = _orig
        # 旧实现会对这个文件判 PASS（因为子串命中）；新实现必须 FAIL
        print('  ② 宿主路径 + 含 "/lib/ld-linux" 子串（旧实现被骗过的形态，预期 rc=2）: rc=%d'
              % rc_bad)
        for line in txt.splitlines():
            if 'interp' in line or 'host-marks' in line or '结果' in line:
                print('       %s' % line)
    ok = ok0 and rc_bad == 2
    print('  自证结果：%s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
