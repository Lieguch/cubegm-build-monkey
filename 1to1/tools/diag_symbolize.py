#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
diag_symbolize.py —— 把设备端诊断产物还原成可读报告

输入
    <diag_elf>              诊断版 rkgame（本地那份，用于把地址变成符号名）
    <frames.bin|snap.bin>   函数轨迹环形缓冲（cgm_diag.c dump_ring 的输出）
可选
    --maps <maps.start.txt> 启动时 /proc/self/maps（判断地址属于哪个模块）
    --crash <crash.txt>     崩溃报告（原样摘录关键段）
    --tail N                只输出最后 N 帧（默认 4000）
    --out <path>            输出文件（默认 report/diag_symbolized.txt）

输出
    ① 摘要：帧数 / 最深栈 / 覆盖函数数
    ② ★ 崩溃前轨迹（最后 tail 帧，按调用深度缩进的调用树）
    ③ 热点函数 Top 40（被调用次数）
    ④ 最深栈快照（完整调用链 —— 最可能指出"卡在哪/崩在哪"）
    ⑤ 未能落进本模块的地址单独列出（需要 maps 才能判归属）

★ 纪律（本项目已登记的仪器失效教训）
   · 地址一律 8 位小写十六进制
   · "0 命中"必须能区分"没走到"与"符号化失败" ⇒ 分别统计 mapped/unmapped
   · 输出里显式打印每个数的口径，避免下游误读
"""
import io
import os
import re
import struct
import sys
from collections import Counter

MAGIC = 0x43474D44  # 'CGMD'


def load_syms(path):
    """返回 [(addr, size, name)] 已按 addr 排序。"""
    d = io.open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    e_shentsize = struct.unpack_from('<H', d, 46)[0]
    e_shnum = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, e_shoff + i * e_shentsize) for i in range(e_shnum)]
    out = []
    for s in S:
        if s[1] != 2:      # SHT_SYMTAB
            continue
        stroff = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2:
                continue
            k = d.index(b'\x00', stroff + nmn)
            nm = d[stroff + nmn:k].decode('utf-8', 'replace')
            if nm:
                out.append((val, sz, nm))
    out.sort()
    return out


def load_frames(path):
    d = io.open(path, 'rb').read()
    if len(d) < 12:
        return [], 0
    magic, cnt, total = struct.unpack_from('<III', d, 0)
    if magic != MAGIC:
        raise SystemExit('!! %s 不是 cgm_diag 的帧文件（magic=0x%08x）' % (path, magic))
    frames = []
    for i in range(cnt):
        off = 12 + i * 12
        if off + 12 > len(d):
            break
        addr, meta, ms = struct.unpack_from('<III', d, off)
        frames.append((addr, meta, ms))
    return frames, total


def load_maps(path):
    """返回 [(lo, hi, perms, name)]"""
    out = []
    if not path or not os.path.exists(path):
        return out
    for ln in io.open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^([0-9a-f]{8})-([0-9a-f]{8})\s+(\S+)\s+\S+\s+\S+\s+\S+\s*(.*)$', ln.strip())
        if m:
            out.append((int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4)))
    return out


class Sym:
    def __init__(self, syms):
        self.syms = syms
        self.cache = {}

    def of(self, a):
        """返回 (name, offset) 或 ('?', a)。★ 只有地址**落在符号 size 内**才算命中。
        ★★★ 教训（2026-09-21 自证时抓到）：早先版本对"落在符号之后但超出 size"的地址
        返回 `符号名(+0xNNN)` —— 于是 **0x3f000000 被张冠李戴成 `_fini(+0x39f79970)`**。
        这种"看起来有名字"的假命中比 '?' 更危险：它会让人去读一个完全无关的函数。
        ⇒ 超界一律判 '?'，并在报告里单列。"""
        if a in self.cache:
            return self.cache[a]
        lo, hi = 0, len(self.syms) - 1
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            v, sz, nm = self.syms[mid]
            if v <= a:
                best = (v, sz, nm)
                lo = mid + 1
            else:
                hi = mid - 1
        if best is None:
            r = ('?', a)
        else:
            v, sz, nm = best
            r = (nm, a - v) if (sz and a - v < sz) else ('?', a)
        self.cache[a] = r
        return r


def demangle(nm):
    """极简 C++ demangle：够用即可（本产物符号大多是 C 名 + 少量 _Z...）。"""
    try:
        import subprocess
        r = subprocess.run(['c++filt', nm], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return nm


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    elf = sys.argv[1]
    fpath = sys.argv[2]
    ap = sys.argv[3:]
    maps_p = crash_p = None
    tailn = 4000
    outp = os.path.join('report', 'diag_symbolized.txt')
    i = 0
    while i < len(ap):
        if ap[i] == '--maps':
            maps_p = ap[i + 1]; i += 2
        elif ap[i] == '--crash':
            crash_p = ap[i + 1]; i += 2
        elif ap[i] == '--tail':
            tailn = int(ap[i + 1]); i += 2
        elif ap[i] == '--out':
            outp = ap[i + 1]; i += 2
        else:
            i += 1

    syms = load_syms(elf)
    sm = Sym(syms)
    frames, total = load_frames(fpath)
    maps = load_maps(maps_p)

    # 模块归属（用于区分"我们 .text" / ".fimg" / "共享库"）
    modtxt = {}
    for lo, hi, perms, name in maps:
        if 'x' in perms:
            modtxt[(lo, hi)] = name or '(anon)'

    def mod_of(a):
        for (lo, hi), nm in modtxt.items():
            if lo <= a < hi:
                return nm
        return None

    L = []
    W = L.append
    W('=' * 78)
    W('设备诊断产物符号化报告')
    W('  诊断产物 = %s' % elf)
    W('  帧文件   = %s' % fpath)
    W('  解析帧数 = %d   （环形缓冲累计写入 %d 次 ⇒ 被覆盖丢弃 %d）' %
      (len(frames), total, max(0, total - len(frames))))
    W('  符号表   = %d 个 FUNC' % len([1 for v, s, n in syms if s]))
    W('  maps     = %s' % (maps_p if maps_p else '（未提供 —— 只能符号化本模块地址）'))
    W('=' * 78)

    if not frames:
        W('')
        W('!! 帧数为 0。按本项目纪律，"0 命中"必须能区分两种原因：')
        W('   (a) 程序在插桩生效前就退出了（看 trace.log 里有没有 BOOT 行）；')
        W('   (b) 诊断仪没被链进去/没跑起来（看 trace.log 是否为空文件）。')
        W('   ⇒ 先看 trace.log 的第一行。')
    else:
        # ---- ③ 热点 ----
        cnt = Counter()
        unmapped = Counter()
        for addr, meta, ms in frames:
            if meta & 1:
                continue
            nm, off = sm.of(addr)
            if nm == '?':
                unmapped[addr] = unmapped.get(addr, 0) + 1
            else:
                cnt[nm] += 1
        W('')
        W('--- ③ 热点函数 Top 40（按"进入次数"计；含被内联者的外层）---')
        W('  %-6s %s' % ('次数', '函数'))
        for nm, c in cnt.most_common(40):
            W('  %-6d %s' % (c, demangle(nm)[:88]))
        W('  共覆盖 %d 个不同函数' % len(cnt))
        if unmapped:
            W('')
            W('--- 地址不在本产物符号表内（%d 个不同地址）---' % len(unmapped))
            for a, c in unmapped.most_common(20):
                mn = mod_of(a)
                W('  %08x  ×%-5d 模块=%s' % (a, c, mn if mn else '(无 maps，判不了)'))

        # ---- ② 崩溃前轨迹（尾部）----
        W('')
        W('--- ② 末尾 %d 帧：按调用深度还原的调用轨迹（越靠下越接近退出那一刻）---' % min(tailn, len(frames)))
        tail = frames[-tailn:]
        maxdepth = 0
        for addr, meta, ms in tail:
            d = (meta >> 8) & 0xFFFF
            if d > maxdepth:
                maxdepth = d
        for addr, meta, ms in tail:
            isexit = meta & 1
            depth = (meta >> 8) & 0xFFFF
            nm, off = sm.of(addr)
            nm = demangle(nm)
            mark = '<<' if isexit else '>>'
            W('  %8u  %s %s%s' % (ms, '  ' * min(depth, 40), mark,
                                  ('%s+0x%x' % (nm, off)) if off else nm))

        # ---- ④ 最深栈快照 ----
        W('')
        W('--- ④ 最深调用栈（从所有帧里取"深度最大"的那一瞬）---')
        st = []
        best = (0, [])
        for addr, meta, ms in frames:
            if meta & 1:
                if st:
                    st.pop()
            else:
                st.append(addr)
                if len(st) > best[0]:
                    best = (len(st), list(st))
        W('  最深深度 = %d' % best[0])
        for k, a in enumerate(best[1]):
            nm, off = sm.of(a)
            nm = demangle(nm)
            W('   %3d  %08x  %s%s' % (k, a, nm, ('+0x%x' % off) if off else ''))

    # ---- crash.txt 摘录 ----
    if crash_p and os.path.exists(crash_p):
        W('')
        W('--- 崩溃报告 %s ---' % crash_p)
        t = io.open(crash_p, encoding='utf-8', errors='replace').read()
        for ln in t.split('\n'):
            if re.match(r'^(signal=|pc=|r[0-9]+=|node=|  \[)', ln) or 'CRASH' in ln or 'fp chain' in ln:
                W('  ' + ln.rstrip()[:150])

    os.makedirs(os.path.dirname(outp) or '.', exist_ok=True)
    io.open(outp, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('  ✓ 报告 → %s（%d 行）' % (outp, len(L)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
