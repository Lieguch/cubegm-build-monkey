#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""interp_of.py —— 打印一个 ELF 的 **真实 PT_INTERP 段**（不是全文件子串搜索）。

存在的理由（第 108/109 轮的根因取证）
------------------------------------------------------------------
`tools/abi_check.py` 用 `d.find(b'/lib/ld-linux')` **在整个文件里做子串搜索**
⇒ 当解释器是宿主路径 `C:/.../PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3` 时，
  它截出来的是 `'/lib/ld-linux-armhf.so.3'` ⇒ **判 PASS**，而真机上必然 ENOENT。
本工具只认 **程序头里 p_type==PT_INTERP 的那一段字节**，并打印其原样与长度。

用法: python tools/interp_of.py <elf> [<elf> ...]
退出: 0 = 打印完成；11 = 读不到输入
"""
import io
import struct
import sys

PT_INTERP = 3


def interp_of(path):
    try:
        d = io.open(path, 'rb').read()
    except Exception as e:
        print('!! 读不到 %s: %s' % (path, e))
        return None
    if d[:4] != b'\x7fELF':
        print('!! %s 不是 ELF' % path)
        return None
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        if t == PT_INTERP:
            raw = d[off:off + fsz]
            return raw.split(b'\x00')[0].decode('latin-1')
    return ''


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 11
    rc = 0
    for p in sys.argv[1:]:
        s = interp_of(p)
        if s is None:
            rc = 11
            continue
        flag = ''
        if not s:
            flag = '  ★ 无 PT_INTERP（静态链接）'
        elif not s.startswith('/'):
            flag = '  ★★ 不是绝对 POSIX 路径 ⇒ 设备上内核 execve 必 ENOENT'
        elif s != '/lib/ld-linux-armhf.so.3':
            flag = '  ★ 非设备侧标准路径'
        print('%-46s  PT_INTERP = %r%s' % (p, s, flag))
    return rc


if __name__ == '__main__':
    sys.exit(main())
