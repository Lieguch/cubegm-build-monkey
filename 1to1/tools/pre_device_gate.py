#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pre_device_gate.py —— **投放前门禁**：把所有"设备侧能不能加载/能不能跑"的
本地可判条件，做成机械判据。

## 为什么要有它（第 109 轮的教训）
第 109 轮之前的 9 道门禁**全部只查"地址/结构像不像"**，没有一道问
「**设备上这一份到底能不能被 exec、能不能过 ld.so 的符号解析**」。
结果：产物在真机上连 exec 都过不去（`PT_INTERP` 是 Windows 宿主路径），
门禁却全绿、符号命中率 99.5%。⇒ 判据问错了问题。

本门禁把"上机前应当已被本地排除"的失败模式逐条机械化：

  P1  `PT_INTERP` 精确等于 `/lib/ld-linux-armhf.so.3`，且**该文件在设备 rootfs 里真实存在**
  P2  全文件不含工具链宿主痕迹（PortableGit / .workbuddy / site-packages / …）
  P3  ELF 身份字段与工厂一致（e_type / e_machine / e_flags / EI_CLASS/DATA/OSABI/ABIVERSION）
  P4  `DT_NEEDED` 全部能从**设备 rootfs** 找到对应 soname
  P5  ★ 未定义动态符号**全部**能在"设备库导出的符号并集"里找到
      （否则设备上 ld.so 直接 `symbol lookup error` ⇒ 与"零日志"同级）
  P6  ★ 版本需求（GLIBC_/GLIBCXX_/CXXABI_/GCC_）⊆ 设备库提供的版本
  P7  `DT_RPATH`/`DT_RUNPATH` 不存在或只指向设备路径（宿主路径 = 硬伤）
  P8  ★ 我方可执行段里**没有任何直接分支目标落在"不可执行的工厂映像区"**
      （该区在我方产物里是 `--R`，跳进去必 SIGSEGV/SIGILL）
  P9  `DT_INIT`/`DT_INIT_ARRAY` 非空且落在可装载段内（工厂亦非空）
  P10 ★ 「段页共享」：任意被 >1 个 PT_LOAD 覆盖的页，其**最终权限**必须 ⊇ 覆盖它的
      所有段的权限并集。加载器按段逐页 mmap，**后映射的段覆盖权限** ⇒ 若被覆盖掉的是 X
      （实测 `.text` 尾页 + 紧随的 `.ARM.exidx` R 段），跳到该页内任何函数都是**取指故障**
      （`SIGSEGV si_code=2 SEGV_ACCERR`，`si_addr == PC`；该页实测 24 个 FUNC）。
      ★ 规则实现**只有一份**：`tools/seg_page_audit.py`，此处只**转发**（纪律：同一规则禁止写两处）。

用法
    python tools/pre_device_gate.py <ours.elf> <factory.bin> <device_rootfs_dir>
退出: 0=全 PASS；2=有 FAIL；11=读不到输入
"""
import bisect
import glob
import io
import os
import struct
import subprocess
import sys

PT_LOAD, PT_DYNAMIC, PT_INTERP = 1, 2, 3
HOST_MARKS = [b'PortableGit', b'.workbuddy', b'site-packages', b'AppData',
              b'C:/Users', b'C:\\', b'/c/Users', b'ziglang']
WANT_INTERP = '/lib/ld-linux-armhf.so.3'

# 版本需求前缀 → 由哪个 soname 提供
VER_OWNER = ('GLIBC_', 'GLIBCXX_', 'CXXABI_', 'GCC_')


def hdr(d):
    if d[:4] != b'\x7fELF':
        raise ValueError('不是 ELF')
    e_type, e_machine = struct.unpack_from('<HH', d, 16)
    e_version, e_entry, e_phoff, e_shoff, e_flags = struct.unpack_from('<5I', d, 20)
    ehsize, phentsize, phnum, shentsize, shnum, shstrndx = struct.unpack_from('<6H', d, 40)
    return dict(cls=d[4], data=d[5], osabi=d[7], abiver=d[8],
                e_type=e_type, e_machine=e_machine, e_entry=e_entry,
                e_phoff=e_phoff, e_shoff=e_shoff, e_flags=e_flags,
                phentsize=phentsize, phnum=phnum,
                shentsize=shentsize, shnum=shnum, shstrndx=shstrndx)


def phdrs(d):
    H = hdr(d)
    out = []
    for i in range(H['phnum']):
        o = H['e_phoff'] + i * H['phentsize']
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        out.append(dict(type=t, off=off, vaddr=va, filesz=fsz, memsz=msz, flags=fl, align=al))
    return out


def v2o(phs, va):
    for p in phs:
        if p['type'] == PT_LOAD and p['vaddr'] <= va < p['vaddr'] + p['filesz']:
            return p['off'] + (va - p['vaddr'])
    return None


def dynamic(d):
    """返回 dict: 'needed'[list], 'rpath', 'runpath', 'init', 'init_array', 'strtab'(va)"""
    phs = phdrs(d)
    dt = {}
    for p in phs:
        if p['type'] != PT_DYNAMIC:
            continue
        off, end = p['off'], p['off'] + p['filesz']
        ents = []
        while off + 8 <= end:
            tag, val = struct.unpack_from('<iI', d, off)
            off += 8
            if tag == 0:
                break
            ents.append((tag, val))
        strtab_va = next((v for t, v in ents if t == 5), None)
        so = v2o(phs, strtab_va) if strtab_va is not None else None

        def s(i):
            if so is None:
                return '?'
            e = d.find(b'\x00', so + i)
            return d[so + i:e].decode('latin-1')

        dt['needed'] = [s(v) for t, v in ents if t == 1]
        for t, v in ents:
            if t == 15:
                dt['rpath'] = s(v)
            elif t == 29:
                dt['runpath'] = s(v)
            elif t == 12:
                dt['init'] = v
            elif t == 26:
                dt['init_array'] = v
            elif t == 27:
                dt['init_arraysz'] = v
        break
    dt.setdefault('needed', [])
    return dt


def _dynsym_manual(d):
    """不依赖节表：用 DT_SYMTAB/DT_STRTAB/DT_HASH|DT_GNU_HASH 读 .dynsym。

    返回 (undef_names, defined_names)。
    """
    phs = phdrs(d)
    dt_ents = {}
    for p in phs:
        if p['type'] != PT_DYNAMIC:
            continue
        off, end = p['off'], p['off'] + p['filesz']
        while off + 8 <= end:
            tag, val = struct.unpack_from('<iI', d, off)
            off += 8
            if tag == 0:
                break
            dt_ents[tag] = val
    symtab = dt_ents.get(6)
    strtab = dt_ents.get(5)
    if symtab is None or strtab is None:
        return None
    so = v2o(phs, symtab)
    stro = v2o(phs, strtab)
    if so is None or stro is None:
        return None
    # 符号个数：优先 DT_HASH(nchain)，其次 DT_GNU_HASH 扫描，最后退化为"读到全零"
    n = None
    if 4 in dt_ents:            # DT_HASH: nbucket, nchain
        ho = v2o(phs, dt_ents[4])
        if ho is not None:
            n = struct.unpack_from('<I', d, ho + 4)[0]
    if n is None:
        # GNU_HASH 兜底：解析 bucket 最大值 + 链
        n = 0
        if 0x6ffffef5 in dt_ents:   # DT_GNU_HASH
            ho = v2o(phs, dt_ents[0x6ffffef5])
            if ho is not None:
                nbucket, symoff, bloom_sz, bloom_shift = struct.unpack_from('<4I', d, ho)
                buckets = struct.unpack_from('<%dI' % nbucket, d, ho + 16)
                # 粗略上限：按文件剩余空间估算（够用即可）
                maxb = max(buckets) if buckets else 0
                n = max(maxb, 1)
                # 逐个 bucket 沿链走到链尾
                for b in set(buckets):
                    if b == 0:
                        continue
                    i = b
                    while True:
                        o = ho + 16 + 4 * nbucket + 4 * (i - symoff)
                        if o + 4 > len(d):
                            break
                        chain = struct.unpack_from('<I', d, o)[0]
                        n = max(n, i)
                        if chain & 1:
                            break
                        i += 1
                        if i > 200000:
                            break
                n = n + 1
    undef, defined = [], set()
    for i in range(min(n or 0, 200000)):
        o = so + i * 16
        if o + 16 > len(d):
            break
        name, value, size, info, other, shndx = struct.unpack_from('<IIIBBH', d, o)
        if name == 0:
            continue
        e = d.find(b'\x00', stro + name)
        nm = d[stro + name:e].decode('latin-1')
        if not nm:
            continue
        if shndx == 0:
            undef.append(nm)
        else:
            defined.add(nm)
    return undef, defined


def _verneed_manual(d):
    """返回需要的版本名列表（不依赖节表）。"""
    phs = phdrs(d)
    ents = {}
    for p in phs:
        if p['type'] != PT_DYNAMIC:
            continue
        off, end = p['off'], p['off'] + p['filesz']
        while off + 8 <= end:
            tag, val = struct.unpack_from('<iI', d, off)
            off += 8
            if tag == 0:
                break
            ents[tag] = val
    strtab = ents.get(5)
    stro = v2o(phs, strtab) if strtab is not None else None
    vo = v2o(phs, ents.get(0x6ffffffe)) if ents.get(0x6ffffffe) else None   # DT_VERNEED
    if vo is None or stro is None:
        return []
    names = []
    off = vo
    for _ in range(64):
        if off + 16 > len(d):
            break
        vn_ver, vn_cnt, vn_file, vn_aux, vn_next = struct.unpack_from('<HHIII', d, off)
        aux = off + vn_aux
        for _j in range(vn_cnt):
            if aux + 16 > len(d):
                break
            h, fl, other, nameoff, nxt = struct.unpack_from('<IHHII', d, aux)
            e = d.find(b'\x00', stro + nameoff)
            names.append(d[stro + nameoff:e].decode('latin-1'))
            if nxt == 0:
                break
            aux += nxt
        if vn_next == 0:
            break
        off += vn_next
    return names


def _verdef_manual(d):
    phs = phdrs(d)
    ents = {}
    for p in phs:
        if p['type'] != PT_DYNAMIC:
            continue
        off, end = p['off'], p['off'] + p['filesz']
        while off + 8 <= end:
            tag, val = struct.unpack_from('<iI', d, off)
            off += 8
            if tag == 0:
                break
            ents[tag] = val
    stro = v2o(phs, ents.get(5)) if ents.get(5) else None
    vo = v2o(phs, ents.get(0x6ffffffc)) if ents.get(0x6ffffffc) else None   # DT_VERDEF
    # ★ 易错点（我自己在这栽过一次）：DT_VERDEF=0x6ffffffc，0x6ffffffd 是 DT_VERDEFNUM。
    #   用 NUM 的值当地址 ⇒ 读到垃圾 ⇒ "设备库只提供 1 个版本"的假 FAIL。
    if vo is None or stro is None:
        return set()
    out = set()
    off = vo
    for _ in range(64):
        if off + 20 > len(d):
            break
        vd_ver, vd_flags, vd_ndx, vd_cnt, vd_hash, vd_aux, vd_next = struct.unpack_from('<HHHHIII', d, off)
        aux = off + vd_aux
        for _j in range(vd_cnt):
            if aux + 8 > len(d):
                break
            nameoff, nxt = struct.unpack_from('<II', d, aux)
            e = d.find(b'\x00', stro + nameoff)
            out.add(d[stro + nameoff:e].decode('latin-1'))
            if nxt == 0:
                break
            aux += nxt
        if vd_next == 0:
            break
        off += vd_next
    return out


def read_lib(path):
    """读一个设备库：返回 (exported_names, provided_versions)。支持 Windows 上的符号链接文件。"""
    try:
        d = io.open(path, 'rb').read()
    except Exception:
        return set(), set()
    if d[:4] != b'\x7fELF':
        # Windows 上 symlink 可能被落成"文本文件"（内容是目标名）
        try:
            tgt = d.decode('latin-1').strip().split('\n')[0].strip()
            cand = os.path.join(os.path.dirname(path), tgt)
            if tgt and os.path.isfile(cand) and os.path.abspath(cand) != os.path.abspath(path):
                return read_lib(cand)
        except Exception:
            pass
        return set(), set()
    try:
        _, defined = _dynsym_manual(d) or (None, set())
    except Exception:
        defined = set()
    try:
        vers = _verdef_manual(d)
    except Exception:
        vers = set()
    return defined, vers


def device_libs(root):
    """递归收集设备 rootfs 里的 ELF 库（按文件名 + soname 均可索引）。"""
    idx_name, idx_soname = {}, {}
    names, vers = set(), set()
    for pat in ('**/*.so', '**/*.so.*'):
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            dn, dv = read_lib(p)
            if not dn and not dv:
                continue
            idx_name[os.path.basename(p)] = (dn, dv)
            names |= dn
            vers |= dv
    return idx_name, names, vers


# ------------------------------------------------------------------ P8：分支目标
def branch_audit(d, phs):
    """返回 (bad_direct, warn_consts, text_ranges)"""
    import capstone
    exec_ranges, data_ranges = [], []
    for p in phs:
        if p['type'] != PT_LOAD or p['filesz'] == 0:
            continue
        (exec_ranges if (p['flags'] & 1) else data_ranges).append(
            (p['vaddr'], p['vaddr'] + p['filesz']))
    bad = []
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    md.detail = True
    md.skipdata = True
    # ★ 不写 `capstone.ARM_INS_B`：不同版本导出位置不同（实测 5.x 没有该顶层属性）。
    #   直接用助记符字符串判断，跨版本稳定。
    try:
        IMM = capstone.arm.ARM_OP_IMM
    except AttributeError:
        IMM = None
    for lo, hi in exec_ranges:
        code = None
        for p in phs:
            if p['type'] == PT_LOAD and p['vaddr'] == lo:
                code = d[p['off']:p['off'] + min(p['filesz'], hi - lo)]
        if not code:
            continue
        for ins in md.disasm(code, lo):
            mn = (ins.mnemonic or '').lower()
            if mn not in ('b', 'bl', 'blx'):
                continue
            ops = ins.operands
            if not ops:
                continue
            if IMM is not None and ops[0].type != IMM:
                continue
            t = ops[0].imm
            for dl, dh in data_ranges:
                if dl <= t < dh:
                    bad.append((ins.address, t, mn))
                    break
    return bad, exec_ranges, data_ranges


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 11
    ours_p, fac_p, root = sys.argv[1], sys.argv[2], sys.argv[3]
    for p in (ours_p, fac_p):
        if not os.path.isfile(p):
            print('!! 读不到 %s' % p)
            return 11
    if not os.path.isdir(root):
        print('!! 读不到设备 rootfs 目录 %s' % root)
        return 11
    A = io.open(ours_p, 'rb').read()
    B = io.open(fac_p, 'rb').read()
    HA, HB = hdr(A), hdr(B)
    PA = phdrs(A)
    fails, warns = [], []

    def chk(cond, tag, detail, warn_only=False):
        print('  [%s] %-22s %s' % ('PASS' if cond else ('WARN' if warn_only else 'FAIL'), tag, detail))
        if not cond:
            (warns if warn_only else fails).append(tag)

    print('=' * 100)
    print('投放前门禁  ours=%s' % ours_p)
    print('=' * 100)

    # P1 -----------------------------------------------------------------
    ip = [p for p in PA if p['type'] == PT_INTERP]
    interp = ''
    if ip:
        interp = A[ip[0]['off']:ip[0]['off'] + ip[0]['filesz']].split(b'\x00')[0].decode('latin-1')
    dev_ld = os.path.join(root, WANT_INTERP.lstrip('/'))
    dev_ld_ok = False
    if os.path.exists(dev_ld) or os.path.lexists(dev_ld):
        tgt = dev_ld
        for _ in range(4):
            try:
                b = io.open(tgt, 'rb').read()
            except Exception:
                break
            if b[:4] == b'\x7fELF':
                dev_ld_ok = True
                break
            t = b.decode('latin-1', 'replace').strip().split('\n')[0].strip()
            if not t:
                dev_ld_ok = True   # Windows 上 symlink 落成空文件，但目标确实存在
                break
            cand = t if os.path.isabs(t) else os.path.join(os.path.dirname(tgt), t)
            if not os.path.exists(cand):
                break
            tgt = cand
    chk(interp == WANT_INTERP, 'P1 interp', 'PT_INTERP=%r（期望 %r）' % (interp, WANT_INTERP))
    chk(os.path.exists(dev_ld) or os.path.lexists(dev_ld), 'P1 interp-exists',
        '设备侧 %s %s' % (WANT_INTERP, '存在' if (os.path.exists(dev_ld) or os.path.lexists(dev_ld)) else '**不存在**'))

    # P2 -----------------------------------------------------------------
    hits = []
    for m in HOST_MARKS:
        i = A.find(m)
        while i >= 0:
            hits.append((i, m.decode('latin-1')))
            i = A.find(m, i + 1)
    chk(not hits, 'P2 host-marks', '宿主痕迹 %d 处 %s' % (len(hits), hits[:4]))

    # P3 -----------------------------------------------------------------
    same = all(HA[k] == HB[k] for k in ('cls', 'data', 'osabi', 'abiver', 'e_type', 'e_machine', 'e_flags'))
    chk(same, 'P3 elf-identity',
        'cls/data/osabi/abiver/type/machine/flags %s' % ('全同' if same else
        ' '.join('%s=%s/%s' % (k, HA[k], HB[k]) for k in
                 ('cls', 'data', 'osabi', 'abiver', 'e_type', 'e_machine', 'e_flags') if HA[k] != HB[k])))

    # P4/P5/P6/P9 --------------------------------------------------------
    dt = dynamic(A)
    idx_name, names, vers = device_libs(root)
    print('  [INFO] 设备库索引 %d 个文件，导出符号 %d 个，提供版本 %d 个'
          % (len(idx_name), len(names), len(vers)))
    missing_needed = [n for n in dt.get('needed', []) if n not in idx_name]
    chk(not missing_needed, 'P4 needed', 'DT_NEEDED=%s；设备缺 %s' % (dt.get('needed'), missing_needed))

    undef, defined_own = _dynsym_manual(A) or ([], set())
    missing_syms = sorted(set(undef) - names)
    chk(not missing_syms, 'P5 undef-symbols',
        '导入 %d 个；设备库缺 %d 个 %s' % (len(set(undef)), len(missing_syms), missing_syms[:8]))

    need_vers = sorted({v for v in _verneed_manual(A) if v.startswith(VER_OWNER)})
    missing_vers = [v for v in need_vers if v not in vers]
    chk(not missing_vers, 'P6 ver-needs',
        '需要 %d 个版本；设备缺 %s' % (len(need_vers), missing_vers[:8]))

    bad_path = []
    for k in ('rpath', 'runpath'):
        if dt.get(k):
            bad_path.append('%s=%s' % (k, dt[k]))
    chk(not bad_path, 'P7 rpath', '无 RPATH/RUNPATH' if not bad_path else str(bad_path))

    init = dt.get('init', 0)
    ia = dt.get('init_array', 0)
    load_ok = (init == 0 or v2o(PA, init) is not None) and (ia == 0 or v2o(PA, ia) is not None)
    chk(load_ok and (init or ia), 'P9 init-chain',
        'DT_INIT=0x%x DT_INIT_ARRAY=0x%x（落段内=%s）' % (init, ia, load_ok))

    # P8 -----------------------------------------------------------------
    try:
        bad, exr, dar = branch_audit(A, PA)
        print('  [INFO] 可执行段 %s' % [('0x%x-0x%x' % e) for e in exr])
        print('  [INFO] 不可执行段 %s' % [('0x%x-0x%x' % e) for e in dar])
        chk(not bad, 'P8 branch-to-nonexec',
            '直接分支落入不可执行段 %d 处 %s' % (len(bad), bad[:5]))
    except ImportError:
        chk(False, 'P8 branch-to-nonexec', '缺 capstone，无法判定', warn_only=True)

    # P10 ----------------------------------------------------------------
    # ★ 规则不在此处重述 —— 直接**转发**给唯一实现 `tools/seg_page_audit.py`
    #   （纪律：同一规则禁止写两处；消费者只许转发或读取，不许另写一份描述）。
    seg_tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'seg_page_audit.py')
    try:
        r = subprocess.run([sys.executable, seg_tool, ours_p],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode('utf-8', 'replace')
        n_viol = out.count('\u2605 \u9875 0x')
        chk(r.returncode == 0, 'P10 seg-page-share',
            '被权限覆盖的共享页 %d 个（页内函数不可达 ⇒ 调用即取指故障）' % n_viol)
        if r.returncode != 0:
            for ln in out.splitlines():
                s = ln.strip()
                if s.startswith('\u2605 \u9875') or '\u7f3a ' in s:
                    print('        %s' % s)
    except Exception as e:
        chk(False, 'P10 seg-page-share', '无法运行 seg_page_audit.py: %s' % e, warn_only=True)

    print('-' * 100)
    print('  结果: %s   FAIL=%d %s   WARN=%d %s'
          % ('PASS' if not fails else 'FAIL', len(fails), fails, len(warns), warns))
    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
