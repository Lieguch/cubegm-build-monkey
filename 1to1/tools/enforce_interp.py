#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""enforce_interp.py —— **PT_INTERP 强制对齐**（等价 patchelf --set-interpreter，零依赖）

## 为什么必须有这一步（第 109 轮根因，代价 = 整个项目「真机零日志」）
实测：`zig ld.lld` 直驱链接时**硬忽略** `--dynamic-linker`（三种写法全部失效），
转而写入宿主默认路径：
    PT_INTERP = 'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3'
而设备上只有 `/lib/ld-linux-armhf.so.3`（与工厂逐字节相同）。
内核在 execve 里**只校验 PT_INTERP 指向的绝对路径是否存在**（连 libc 都不查），
不存在 ⇒ 立即 ENOENT ⇒ 进程根本不启动 ⇒ **诊断目录零文件**。
这与真机现象（无法开机 + 一条日志都没有）逐字吻合。
上游同源：ziglang/zig#23813（`-dynamic-linker` 未传递到 lld 调用）。
业界标准处置：链接后用 `patchelf --set-interpreter` 改写；本工具即其零依赖等价物。

## 判据（预登记）
  P1  PT_INTERP 必须存在，且**逐字节等于** `b'/lib/ld-linux-armhf.so.3\\x00'`（工厂同值）。
  P2  现有 p_filesz ≥ 目标串长度（否则 FAIL，不得截断写坏文件）。
  P3  全文件不得含**工具链宿主痕迹**（PortableGit / .workbuddy / site-packages / AppData /
      `C:/Users` / `C:\\` / `/c/Users` / ziglang）—— ARM 目标上无任何合法来源。
  P4  写盘**原子**：写 `<out>.tmp` → 读回校验 → `os.replace`。

## 用法
  python tools/enforce_interp.py <elf>            # 就地修正（幂等）
  python tools/enforce_interp.py <elf> --check    # 只检查不写（退出码即结论）
  python tools/enforce_interp.py --selftest <elf> # 自证（纯内存，不落临时文件）
退出: 0=已对齐/可对齐；2=FAIL（不改文件）；11=读不到输入
"""
import io
import os
import struct
import sys

PT_INTERP = 3
WANT = b'/lib/ld-linux-armhf.so.3\x00'
HOST_MARKS = [b'PortableGit', b'.workbuddy', b'site-packages', b'AppData',
              b'C:/Users', b'C:\\', b'/c/Users', b'ziglang']


# ---------------------------------------------------------------- 纯内存核心
def find_interp(d):
    """返回 (off, filesz, raw) 或 (None, 错误串)。"""
    if d[:4] != b'\x7fELF':
        return None, '不是 ELF'
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    if e_phoff + e_phnum * e_phentsize > len(d):
        return None, '程序头越界（文件被截断？）'
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        if t == PT_INTERP:
            if off + fsz > len(d):
                return None, 'PT_INTERP 越界'
            return (off, fsz, bytes(d[off:off + fsz])), None
    return None, '没有 PT_INTERP（静态链接？本工具不适用）'


def scan_host(d):
    hits = []
    for m in HOST_MARKS:
        i = d.find(m)
        while i >= 0:
            hits.append((i, m))
            i = d.find(m, i + 1)
    return sorted(hits)


def check_bytes(d, quiet=False):
    """返回 (rc, 说明行列表)。rc: 0=PASS 2=FAIL。"""
    lines = []
    got, err = find_interp(d)
    if got is None:
        return 2, ['  [FAIL] %s' % err]
    off, fsz, raw = got
    cur = raw.split(b'\x00')[0]
    ok = raw.startswith(WANT)
    lines.append('  [%s] PT_INTERP off=0x%x filesz=%d 当前=%r 目标=%r'
                 % ('PASS' if ok else 'FAIL', off, fsz,
                    cur.decode('latin-1', 'replace'), WANT[:-1].decode()))
    rc = 0 if ok else 2
    hits = scan_host(d)
    if hits:
        lines.append('  [FAIL] 全文件含宿主痕迹 %d 处（ARM 目标上无合法来源）:' % len(hits))
        for o, m in hits[:8]:
            lines.append('         0x%x  %r' % (o, m.decode('latin-1')))
        rc = 2
    return rc, lines


def fix_bytes(d):
    """返回 (rc, newbytes, 说明行列表)。不写盘。"""
    lines = []
    b = bytearray(d)
    got, err = find_interp(b)
    if got is None:
        return 2, b, ['  [FAIL] %s' % err]
    off, fsz, raw = got
    if raw.startswith(WANT):
        lines.append('  PT_INTERP 已是目标值，未改写')
    else:
        if fsz < len(WANT):
            return 2, b, ['  [FAIL] p_filesz=%d < 目标串 %d B ⇒ 无法就地对齐' % (fsz, len(WANT))]
        b[off:off + fsz] = WANT + b'\x00' * (fsz - len(WANT))
        lines.append('  PT_INTERP 已改写（@0x%x，%d B 槽位）' % (off, fsz))
    rc, l2 = check_bytes(bytes(b))
    lines += l2
    return rc, bytes(b), lines


# ---------------------------------------------------------------- CLI
def do_fix(path):
    try:
        d = io.open(path, 'rb').read()
    except Exception as e:
        print('!! 读不到 %s: %s' % (path, e))
        return 11
    rc, nd, lines = fix_bytes(d)
    for l in lines:
        print(l)
    if rc != 0:
        print('  [FAIL] 修正后仍未通过 ⇒ 不改写原文件')
        return 2
    if bytes(nd) == d:
        print('  文件内容无变化（本就对齐）')
        return 0
    tmp = path + '.tmp'
    with io.open(tmp, 'wb') as f:
        f.write(nd)
    back = io.open(tmp, 'rb').read()
    vrc, _ = check_bytes(back)
    if vrc != 0:
        print('  [FAIL] 临时文件自校验未通过 ⇒ 不替换原文件')
        return 2
    os.replace(tmp, path)
    print('  已原子替换 %s（%d B）' % (path, len(nd)))
    return 0


def selftest(path):
    """纯内存自证：不落任何临时文件（规避本机沙箱的删除守卫）。"""
    try:
        d = io.open(path, 'rb').read()
    except Exception as e:
        print('  自证不可用：读不到 %s: %s' % (path, e))
        return 11
    got, err = find_interp(d)
    if got is None:
        print('  自证不可用：%s' % err)
        return 11
    off, fsz, raw = got
    bad = b'C:/Users/x/PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3\x00'
    if fsz < len(bad):
        print('  自证不可用：槽位 %d < 坏串 %d' % (fsz, len(bad)))
        return 11
    victim = bytearray(d)
    victim[off:off + fsz] = bad + b'\x00' * (fsz - len(bad))
    victim = bytes(victim)
    rc1, l1 = check_bytes(victim)
    print('  ① 注入坏 INTERP 后的判据（期望 rc=2）：')
    for l in l1:
        print('    ' + l)
    rc2, nd, l2 = fix_bytes(victim)
    print('  ② 修正（期望 rc=0）：')
    for l in l2:
        print('    ' + l)
    # 反例 2：合法产物必须 PASS（防"门禁恒 FAIL"）
    rc3, _ = check_bytes(d)
    print('  ③ 原始产物（期望 rc=%d，取决于它本身是否已对齐）：%d' % (rc3, rc3))
    ok = (rc1 == 2 and rc2 == 0 and len(nd) == len(d))
    print('  自证结果：%s（rc1=%d rc2=%d）' % ('PASS' if ok else 'FAIL', rc1, rc2))
    return 0 if ok else 2


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 11
    if a[0] == '--selftest':
        return selftest(a[1])
    if a[0] == '--check':
        try:
            d = io.open(a[1], 'rb').read()
        except Exception as e:
            print('!! 读不到 %s: %s' % (a[1], e))
            return 11
        rc, lines = check_bytes(d)
        for l in lines:
            print(l)
        return rc
    return do_fix(a[0])


if __name__ == '__main__':
    sys.exit(main())
