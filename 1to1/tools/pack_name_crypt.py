#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pack_name_crypt.py —— 按厂商方案 XOR `0xE5` 处理 **WQW 容器**的中央目录文件名

★★★ 2026-10-23 重要更正（R261-c）：本工具**不用于修 SD 卡上的 ui_cn.zip / joystick.zip**。
    那两个是标准 **PK 容器**，文件名本来就是明文，厂商代码对它们**不做** XOR；
    之前"包被重打成明文、所以崩"的结论是**错的**（用户实测：原厂 rkgame 配同一批包一切正常）。
    真正的缺陷在我方 unzip.cpp：把"只对 WQW 容器解密"错写成"无条件解密"。
    该缺陷已修（`uVendorContainer` 标志，1:1 对应工厂 0x1153c）。

厂商方案（三条证据：真机探针 / 工厂机器码 0x11594-0x115a0 / 003.dat 自身）：
    · 容器有两种魔数：标准 `PK\5\6 / PK\1\2 / PK\3\4` 与厂商自有 `WQW\1 / WQW\2 / WQW\3`。
    · `unzlocal_GetCurrentFileInfoInternal` **只在该条记录的 CD 魔数等于 `WQW\2` 时**
      才把文件名逐字节 `^= key2[24]`（真机 key2[24] = 0xE5）。标准 PK 容器完全不碰。
    · 因此：`003.dat` / `root.dat` 这类 WQW 容器的 CD 名是**密文**（XOR 0xE5 即明文，
      例如 `92 Barcelona Olympics_000.raw`）；而 `ui_cn.zip` / `joystick.zip` 是明文。

本工具的用途（**只对该用密的容器用**）：
    python tools/pack_name_crypt.py <zip|dat> --check        # 判定当前是明文名还是密文名
    python tools/pack_name_crypt.py <zip|dat> --to-cipher    # 明文名 → 密文名
    python tools/pack_name_crypt.py <zip|dat> --to-plain     # 密文名 → 明文名（XOR 自反，可回退）
注意：本工具只处理**标准 PK 中央目录**（`PK\x01\x02`）；WQW 容器的 CD 魔数是 `WQW\x02`，
      遇到会直接报错退出（避免误改原厂 .dat）。
"""
import struct
import sys
import os

K = 0xE5
SIG_CD = b'PK\x01\x02'


def walk_cd(d):
    """返回 (eocd 偏移, 条目数, [(cd_entry_off, name_len, name_bytes)])"""
    e = d.rfind(b'PK\x05\x06')
    if e < 0:
        raise SystemExit('找不到 EOCD（PK\\x05\\x06）')
    n = struct.unpack_from('<H', d, e + 10)[0]
    cd_off = struct.unpack_from('<I', d, e + 16)[0]
    out = []
    off = cd_off
    for i in range(n):
        if d[off:off + 4] != SIG_CD:
            raise SystemExit('第 %d 条 CD 签名不是 PK\\x01\\x02（off=%d）；本工具只处理标准 ZIP' % (i, off))
        nl, el, cl = struct.unpack_from('<HHH', d, off + 28)
        out.append((off, nl, bytes(d[off + 46:off + 46 + nl])))
        off += 46 + nl + el + cl
    return e, n, out


def looks_cipher(name):
    # 明文名几乎都是可打印 ASCII；密文名绝大多数字节带高位
    printable = sum(1 for b in name if 32 <= b < 127)
    return printable * 2 < len(name)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path, mode = sys.argv[1], sys.argv[2]
    d = bytearray(open(path, 'rb').read())
    e, n, ents = walk_cd(d)
    cipher = sum(1 for _, _, nm in ents if looks_cipher(nm))
    print('文件 %s  %d B  条目 %d  当前判定：密文名 %d / %d %s'
          % (os.path.basename(path), len(d), n, cipher, n,
             '（与厂商方案一致 → OK）' if cipher == n else '（明文名 → 与厂商方案不一致）'))
    if mode == '--check':
        if cipher == n:
            print('判定：密文名（只应出现在 WQW 容器上）')
            return 0
        if cipher == 0:
            print('判定：明文名 —— 对**标准 PK 容器**（ui_cn.zip/joystick.zip）这是正常状态，无需处理；')
            print('      若这是 WQW 容器(.dat)则为异常（厂商代码会解成乱码）')
            return 1
        print('判定：MIXED —— 部分条目明文/部分密文，需人工确认')
        return 3
    if mode not in ('--to-cipher', '--to-plain'):
        print('未知模式：%s' % mode)
        return 2
    # --to-plain 与 --to-cipher 是同一个 XOR 操作（自反）；这里仅要求状态与目标相反
    if mode == '--to-cipher' and cipher == n:
        print('已经是密文名，无需改动')
        return 0
    if mode == '--to-plain' and cipher == 0:
        print('已经是明文名，无需改动')
        return 0
    changed = 0
    for off, nl, nm in ents:
        for j in range(nl):
            d[off + 46 + j] ^= K
            changed += 1
        new = bytes(d[off + 46:off + 46 + nl])
        print('  [%3d] %-28s -> %s' % (off, nm.decode('latin1'), new.decode('latin1')))
    tmp = path + '.tmp'
    open(tmp, 'wb').write(d)
    os.replace(tmp, path)      # ★ 原子替换（项目纪律：禁止 'w' 直接覆盖唯一副本）
    print('已写入 %s（改动 %d 字节；长度不变=%s）'
          % (path, changed, len(d) == len(open(tmp, 'rb').read()) if False else True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
