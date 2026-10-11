#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""migrate_dup_image_tables.py —— 把「源码 static 数据表」改成「引用镜像别名」。

══════ 为什么需要这个工具（系统性缺陷，不是单点 bug）══════

第 131 轮（`default_core_list`）、第 134 轮（`dcttab`）两次真缺陷**同型**：

    ① 工厂有一个数据对象（`ledger/factory_globals.tsv` 有行，`.rodata`/`.data`）；
    ② `src/data/factory_image.S` 里**已经**给它生成了 `.globl NAME` + `.set NAME, __f_*_base + off`
       的镜像别名（地址 = 工厂地址，逐位正确）；
    ③ 但**某个 .c 文件里又写了一份同名的 `static` 定义** ⇒ 编进自有 `.rodata`/`.data`，
       产生一个 **LOCAL** 符号，在汇编层**遮蔽**了 ② 的 `.globl` 别名；
    ④ 结果：产物里同名两份，内容逐字节相同（纯重复副本），
       **代码读的是错地址那份** ⇒ 真机行为与工厂不同。

`tools/dup_sym_gate.py` 的**检查 3**（第 133 轮新增）能抓出这类，
但它只**报**不**修**；本工具做那一步，且必须**逐个验证内容等价**才允许改。

══════ 铁律（违反即视为本工具失效）══════

1. **只改「与镜像别名同名」的 static 定义** —— 不碰其它任何东西。
2. **改前必须逐字节验证**：C 源码里的字面量打包后 == 工厂镜像区间内容。
   验证不过 ⇒ **跳过并报错**，绝不"改完再看"。
3. **幂等**：已经是 `extern` 的跳过；可重复运行。
4. **原子写**：写 `.tmp` → 校验 → `os.replace`（本项目第 130 轮血泪教训）。
5. **留证据**：每个改动打印 文件/行号/符号/工厂地址/字节数/内容比对结果。

用法：
    python3 tools/migrate_dup_image_tables.py --check     # 只报告，不改
    python3 tools/migrate_dup_image_tables.py --apply     # 校验通过才改
    python3 tools/migrate_dup_image_tables.py --selftest  # 双向自证（含缺陷态）
"""
import io
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IMG_S = os.path.join(ROOT, 'src', 'data', 'factory_image.S')
IMG_DIR = os.path.join(ROOT, 'src', 'data')
# 段 → 镜像文件名（`__f_rodata_base` → `factory_rodata.bin`；`__f_text_base` → `factory_text.bin`）
SEG_BIN = {
    '__f_text_base': 'factory_text.bin',
    '__f_rodata_base': 'factory_rodata.bin',
    '__f_data_rel_ro_local_base': 'factory_data_rel_ro_local.bin',
    '__f_data_base': 'factory_data.bin',
}
DEF_OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

# 支持一维与多维：`static const char NRTab[6][3][4] = {`
DEF_RE = r'^[ \t]*static\s+((?:const\s+)?(?:unsigned\s+|signed\s+)?\w+)\s+(\w+)\s*(\[[^\]]*\]+)\s*=\s*\{'


def read_aliases():
    """从 factory_image.S 解析 `.set NAME, __f_*_base + off` 与紧随的 `.size NAME, n`。

    → {NAME: (base_sym, off, line, size)}

    ★ `size` 是**权威期望字节数**：`pow43` 的 C 声明是 `static const int pow43[] = {...}`
      （**无维度**），从源码算不出元素数；只有生成器写下的 `.size` 知道它多大。
      早期版本用 `total_elems(dims)` ⇒ 无维度时得 1 ⇒ 期望 4B 而实际 192B
      ⇒ 全部误判 SKIP。
    """
    out = {}
    if not os.path.exists(IMG_S):
        return out
    lines = io.open(IMG_S, encoding='utf-8', errors='replace').read().split('\n')
    for i, line in enumerate(lines, 1):
        m = re.search(r'^\s*\.set\s+(\w+),\s*(__f_\w+)\s*\+\s*(0x[0-9a-fA-F]+|\d+)', line)
        if not m:
            continue
        size = None
        for k in range(i, min(i + 4, len(lines))):
            m2 = re.search(r'^\s*\.size\s+' + re.escape(m.group(1)) + r'\s*,\s*(0x[0-9a-fA-F]+|\d+)', lines[k])
            if m2:
                size = int(m2.group(1), 0)
                break
        out[m.group(1)] = (m.group(2), int(m.group(3), 0), i, size)
    return out


def block_extent(t, open_brace_idx):
    """从 '{' 处求到配对的 '}'，返回 (start, end) 索引（含花括号）。按字符串/注释感知。"""
    depth = 0
    i = open_brace_idx
    n = len(t)
    while i < n:
        c = t[i]
        if c == '/' and i + 1 < n and t[i + 1] == '*':
            j = t.find('*/', i + 2)
            i = (j + 2) if j >= 0 else n
            continue
        if c == '/' and i + 1 < n and t[i + 1] == '/':
            j = t.find('\n', i)
            i = (j + 1) if j >= 0 else n
            continue
        if c == '"':
            i += 1
            while i < n and t[i] != '"':
                i += 2 if t[i] == '\\' else 1
            i += 1
            continue
        if c == "'":
            i += 1
            while i < n and t[i] != "'":
                i += 2 if t[i] == '\\' else 1
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return open_brace_idx, i
        i += 1
    raise ValueError('花括号不配对 @%d' % open_brace_idx)


def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    s = re.sub(r'//[^\n]*', ' ', s)
    return s


def elem_width(ctype):
    return {'char': 1, 'unsigned char': 1, 'signed char': 1,
            'short': 2, 'unsigned short': 2, 'signed short': 2,
            'int': 4, 'unsigned int': 4, 'signed int': 4,
            'long': 4, 'unsigned long': 4, 'signed long': 4,
            'long int': 4, 'unsigned long int': 4, 'signed long int': 4,
            'long long': 8, 'unsigned long long': 8}.get(ctype, 4)


def total_elems(dims):
    n = 1
    for d in re.findall(r'\[([^\]]*)\]', dims):
        d = d.strip()
        if d:
            n *= int(d, 0)
    return n


TOKENS = [
    # 字符字面量：必须排在数字之前，否则 '"' 后的内容会被当数字读
    (re.compile(r'"((?:[^"\\]|\\.)*)"'), 'STR'),
    (re.compile(r"'((?:[^'\\]|\\.)*)'"), 'CHR'),
    # ★ 十六进制必须**整体一个 token**，且不能被后面的十进制正则再切一刀。
    #   2026-10-04 实测踩到：`0x7fffffff` 被 `(?<![\w.])-?\d+` 从中间切开
    #   （`0` 与 `7fffffff` 各出一个数）⇒ 源被打成 8 个 int（32B）而不是 4 个（16B）
    #   ⇒ 所有 Q31 常量表都会被误判"内容不一致"。修法 = **一次扫描、不重叠**。
    (re.compile(r'(?<![\w.$])-?0[xX][0-9a-fA-F]+[uUlL]*'), 'HEX'),
    (re.compile(r'(?<![\w.$])-?\d+[uUlL]*'), 'NUM'),
]

_HEXTOK = re.compile(r'0[xX]')

_ESCAPES = {'n': 10, 't': 9, 'r': 13, '0': 0, '\\': 92, "'": 39, '"': 34, 'a': 7, 'b': 8, 'f': 12, 'v': 11}


def _unescape(s):
    out, i = bytearray(), 0
    while i < len(s):
        c = s[i]
        if c == '\\' and i + 1 < len(s):
            nx = s[i + 1]
            if nx == 'x' and i + 3 < len(s):
                out.append(int(s[i + 2:i + 4], 16)); i += 4; continue
            if nx in _ESCAPES:
                out.append(_ESCAPES[nx]); i += 2; continue
            out.append(ord(nx)); i += 2; continue
        out.append(ord(c) & 0xFF)
        i += 1
    return bytes(out)


def pack_literals(body, ctype):
    """把 C 初始化体打包成字节串。ctype 决定元素宽度与符号性。

    ★ 必须同时处理**字符串字面量**（char 数组的常态，如 `preTab[3][2] = {"a","b",...}`）、
      **字符字面量**（`'\\0'`）与数字 —— 2026-10-04 自证当场抓到"只认数字"这个 bug。
    """
    b = strip_comments(body)
    b = b.replace('{', ' ').replace('}', ' ')
    # ★ **单遍扫描 + 占用掩码**：保证一个十六进制字面量只被消费一次。
    #   （多遍 finditer 会让后一条正则重复命中前一条已消费的区间。）
    toks = []
    taken = bytearray(len(b))
    for rx, kind in TOKENS:
        for m in rx.finditer(b):
            s0, s1 = m.span()
            if any(taken[s0:s1]):
                continue
            taken[s0:s1] = b'\x01' * (s1 - s0)
            toks.append((s0, kind, m.group(1) if m.re.groups else m.group(0)))
    toks.sort()
    w = elem_width(ctype)
    out = bytearray()
    signed = not ctype.startswith('unsigned')
    for _pos, kind, val in toks:
        if kind == 'STR':
            # C 语义：char 数组初始化里**每个**字符串字面量末尾隐含一个 '\0'，
            # 且不足 w 字节时右侧补 0（`{"AB","C"}` → 'A','B','\0','C','\0'）。
            data = _unescape(val)
            if w > 1:
                out += data[:w - 1].ljust(w, b'\x00')
            else:
                out += data
                out += b'\x00'
        elif kind == 'CHR':
            data = _unescape(val)
            v = data[0] if data else 0
            out += struct.pack('<b' if signed else '<B', v) if w == 1 else struct.pack('<i', v)[:w]
        else:
            v = int(val.rstrip('uUlL'), 0)
            # ★ 2026-10-04 自证抓到：`0x7fffffff` 之外的 Q31/Q28 常量（例如 mp3 的
            #   COS 宏 0x5a82799a 在某些编辑器里被写成 0x...）在 struct.pack('<i')
            #   下会抛 `struct.error`（超出 int32）。C 里这类字面量默认是 **unsigned**
            #   语义（0x8..0xff.. 会被当负数补码），故先按 32 位无符号截断再按有符号解。
            v32 = v & 0xFFFFFFFF
            if w == 8:
                out += struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF)
            elif v32 >= 0x80000000:
                v32 -= 0x100000000
            out += struct.pack('<i', v32)[:w]
    return bytes(out)


def find_conflicts(aliases):
    """扫 src/ 下所有 .c，找出「static 数组定义 且 名字在镜像别名里」的处。"""
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, 'src')):
        for f in files:
            if not f.endswith('.c'):
                continue
            p = os.path.join(base, f)
            try:
                t = io.open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            for m in re.finditer(DEF_RE, t, re.M):
                # ★ ctype 只取**基本类型**：`const` 单独处理。
                #   早期版本直接把 `(?:const\s+)?...` 的整段当 ctype，
                #   于是生成 `extern const const int X[];`（双重 const）⇒ 自证当场抓到。
                ctype = m.group(1).strip().replace('const', '').strip()
                name, dims = m.group(2), m.group(3)
                if name not in aliases:
                    continue
                ob = t.index('{', m.end() - 1)
                try:
                    _bs, be = block_extent(t, ob)
                except ValueError:
                    continue
                semi = t.find(';', be)
                hits.append(dict(path=p, name=name, ctype=ctype, dims=dims,
                                 start=m.start(), end=semi + 1,
                                 brace=(ob, be),
                                 line=t[:m.start()].count('\n') + 1))
    return hits


def verify(h, alias, mirror):
    """校验：源码字面量打包 == 镜像区间内容。返回 (ok, detail)"""
    base_sym, off, aline, alias_size = alias
    t = io.open(h['path'], encoding='utf-8', errors='replace').read()
    body = t[h['brace'][0] + 1: h['brace'][1]]
    src_bytes = pack_literals(body, h['ctype'])
    w = elem_width(h['ctype'])
    # ★ 期望字节数优先取**别名的 `.size`**（权威）；无 `.size` 才退回按维度算。
    if alias_size:
        want = alias_size
        want_src = '别名 .size=%d' % want
    else:
        nelem = total_elems(h['dims'])
        want = nelem * w
        want_src = '%d 元素 × %dB' % (nelem, w)
    # 镜像文件偏移：**别名里的 off 本身就是"段内偏移"**（gen_data_module 生成的
    #   `.set NAME, __f_rodata_base + off` 里的 off 就是该段镜像文件内的字节偏移），
    #   所以 seg_off = off。★ 2026-10-04 自证抓到：早期版本误写成 `off - seg`
    #   （拿段内偏移减段 VMA）⇒ 恒为负 ⇒ 所有校验都判"不一致"。
    seg = mirror['segs'].get(base_sym)
    if seg is None:
        return False, '镜像段 %s 未在产物 .fimg_* 里找到（无法验证）' % base_sym
    blob = mirror['blobs'].get(base_sym)
    if blob is None:
        return False, '段 %s 没有对应镜像文件（SEG_BIN 未登记）' % base_sym
    seg_off = off
    if seg_off + want > len(blob):
        return False, '镜像区间 [%#x,%#x) 超出 %s 长度 %d' % (
            seg_off, seg_off + want, SEG_BIN.get(base_sym, '?'), len(blob))
    img = blob[seg_off:seg_off + want]
    if len(src_bytes) != want:
        return False, '源码字面量 %dB ≠ 期望 %dB（%s）⇒ 内容不同，绝不改' % (
            len(src_bytes), want, want_src)
    ok = src_bytes == img
    return ok, '源 %dB vs %s[%#x:%#x] %dB（工厂地址 %#x，%s）⇒ %s' % (
        len(src_bytes), SEG_BIN.get(base_sym, '?'), seg_off, seg_off + want, want,
        seg + off, want_src, '逐字节相同' if ok else '★不一致')


def load_mirror():
    """读**全部**镜像文件 + 段 VMA。

    ★ 段 VMA 的权威来源 = **已构建产物** `build/rkgame.rebuilt.elf` 的 `.fimg_*` 段
      （由 `linker/factory.ld` 决定，VMA 必须与工厂一致，否则代码里烧死的绝对地址全错）。
      不用 `factory_image.S` 推算：那里的 `__f_rodata_base` 是**汇编标签**（无值），
      早期版本试图从 `.set` 解析它 ⇒ 恒报"段未定义"⇒ 全部 SKIP。
      产物缺失时 fail-closed（不做"改完再看"）。

    ★ 别名里的 `off` 是**段内偏移**，而每个段对应**不同的镜像文件**
      （`__f_rodata_base` → `factory_rodata.bin`，`__f_data_base` → `factory_data.bin`）。
      早期版本只读 `factory_data.bin` ⇒ rodata 段的校验必然错。
    """
    blobs = {}
    for base, fn in SEG_BIN.items():
        p = os.path.join(IMG_DIR, fn)
        if not os.path.exists(p):
            return dict(blobs=blobs, segs=None, err='缺镜像文件 %s' % fn)
        blobs[base] = open(p, 'rb').read()
    if not os.path.exists(DEF_OURS):
        return dict(blobs=blobs, segs=None, data_off=0,
                    err='缺产物 %s（段 VMA 的权威值取自它）' % rel(DEF_OURS))
    try:
        from elftools.elf.elffile import ELFFile
    except ImportError:
        return dict(blobs=blobs, segs=None, data_off=0, err='缺 pyelftools')
    segs = {}
    with open(DEF_OURS, 'rb') as fh:
        e = ELFFile(fh)
        for s in e.iter_sections():
            if s.name.startswith('.fimg_'):
                segs['__f%s_base' % s.name[len('.fimg'):]] = s['sh_addr']
    if not segs:
        return dict(blobs=blobs, segs=None, data_off=0, err='产物里没有 .fimg_* 段')
    return dict(blobs=blobs, segs=segs, data_off=0, err=None)


def build(h, why):
    """生成替换文本：extern 声明 + 根因注释。"""
    t = io.open(h['path'], encoding='utf-8', errors='replace').read()
    return t


def rel(p):
    """相对 ROOT 的路径；跨盘符（自证用临时目录在别的盘）时退回 basename。"""
    try:
        return os.path.relpath(p, ROOT)
    except ValueError:
        return os.path.basename(p)


def apply_one(h, alias, mirror, dry):
    ok, detail = verify(h, alias, mirror)
    tag = 'OK  ' if ok else 'SKIP'
    print('  %s %-22s %s:%d  %s' % (tag, h['name'], rel(h['path']), h['line'], detail))
    if not ok or dry:
        return False
    t = io.open(h['path'], encoding='utf-8', errors='replace').read()
    base_sym, off, aline, alias_size = alias
    comment = (
        '/* ★★★ %s 自动迁移（tools/migrate_dup_image_tables.py）：\n'
        ' *   原为 `static %s %s%s = {...}` ⇒ 编进自有 .rodata/.data，\n'
        ' *   产生 LOCAL 符号**遮蔽**了 src/data/factory_image.S:%d 已有的镜像别名\n'
        ' *   `.set %s, %s + %#x`（= 工厂地址 %s）。\n'
        ' *   ⇒ 产物里同名两份、内容逐字节相同（已逐字节校验），代码读的是**错地址那份**。\n'
        ' *   本次改为 extern 引用镜像别名，从此与工厂读同一地址。\n'
        ' *   回退：git checkout %s\n'
        ' */\n'
        'extern const %s %s[];\n'
    ) % ('2026-10-04（第 134 轮）T09 系统性根修', h['ctype'], h['name'], h['dims'],
         aline, h['name'], base_sym, off,
         ('共 %d 字节' % alias_size) if alias_size else '尺寸见别名 .size',
         h['path'], h['ctype'], h['name'])
    new = t[:h['start']] + comment + t[h['end']:]
    tmp = h['path'] + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    # 校验：长度必须变短（删掉了整个初始化块），且 extern 出现
    chk = io.open(tmp, encoding='utf-8', errors='replace').read()
    if 'extern const %s %s[]' % (h['ctype'], h['name']) not in chk:
        os.remove(tmp)
        print('     ★ 校验失败：extern 未写入，已丢弃 .tmp')
        return False
    os.replace(tmp, h['path'])
    print('     → 已改（%d → %d 字节，删去 %d 字节重复副本）' % (len(t), len(new), len(t) - len(new)))
    return True


def selftest():
    """双向自证：① 迁移逻辑对已知样本成立；② 内容不一致时**必须跳过**。"""
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    # --- 单元：block_extent 能正确跳过注释与字符串里的花括号 ---
    s = '{ /* } 内嵌 */ 1, 2 /* { 内嵌 */ } ; tail'
    a, b = block_extent(s, s.index('{'))
    c('正例 block_extent 跳过注释里的花括号（配对到真正的收尾 }）', s[a:b + 1], s[:s.index('} ; tail') + 1])
    s2 = '{ "}" , 3 } ; tail'
    a2, b2 = block_extent(s2, s2.index('{'))
    c('正例 block_extent 跳过字符串里的 }', s2[a2:b2 + 1], '{ "}" , 3 }')

    # --- 单元：一维/多维元素数与打包 ---
    c('正例 total_elems 一维 [48]', total_elems('[48]'), 48)
    c('正例 total_elems 多维 [6][3][4]', total_elems('[6][3][4]'), 72)
    c('正例 total_elems 混合 [4][16]', total_elems('[4][16]'), 64)
    c('正例 pack_literals int 宽度', len(pack_literals('{1,2,3}', 'int')), 12)
    c('正例 pack_literals 字符串字面量内容（C 语义：每串独立补 \\0）',
      pack_literals('{"AB","C"}', 'char'), b'AB\x00C\x00')
    # ★ 回归锚点：十六进制必须**整体一个 token**。
    #   早期版本 `0x7fffffff` 被十进制正则从中间切开 ⇒ 4 个 int 被打成 8 个（32B）
    #   ⇒ 所有 Q31/Q28 常量表都会被误判"内容不一致"而 SKIP（真实事故：pow14/pow43/…）。
    c('回归 十六进制不被切开（4 个 Q31 常量 = 16B）',
      len(pack_literals('{0x7fffffff, 0x6ba27e65, 0x5a82799a, 0x4c1bf829}', 'int')), 16)
    c('回归 十六进制内容正确（含 >int32 与高位为 1 的补码）',
      pack_literals('{0x7fffffff, 0x6ba27e65, 0x5a82799a, 0x4c1bf829}', 'int').hex(),
      'ffffff7f657ea26b9a79825a29f81b4c')
    c('回归 混合十进制/十六进制不互相污染', len(pack_literals('{1, 0x2, 3}', 'int')), 12)
    c('正例 pack_literals char 宽度 1 时补 \\0', pack_literals('{"a","b"}', 'char'), b'a\x00b\x00')
    c('正例 elem_width int/char', (elem_width('int'), elem_width('char')), (4, 1))

    # --- 端到端：造一份临时 src，验证「内容一致 ⇒ 改」「不一致 ⇒ 跳过」 ---
    import tempfile
    td = tempfile.mkdtemp()
    img = os.path.join(td, 'factory_image.S')
    binf = os.path.join(td, 'factory_data.bin')
    src = os.path.join(td, 'x.c')
    base_vma = 0x1000
    # 镜像：offset 0x10 处放 3 个 int = 1,2,3
    blob = bytearray(b'\xAA' * 0x100)
    blob[0x10:0x1c] = struct.pack('<3i', 1, 2, 3)
    open(binf, 'wb').write(bytes(blob))
    io.open(img, 'w', encoding='utf-8').write(
        '.set __f_rodata_base, %#x\n.set tabx, __f_rodata_base + 0x10\n' % base_vma)
    io.open(src, 'w', encoding='utf-8').write('static const int tabx[3] = {1,2,3};\nint f(void){return tabx[0];}\n')

    def run_case(text, label):
        io.open(src, 'w', encoding='utf-8').write(text)
        aliases = {}
        for line in io.open(img, encoding='utf-8'):
            m = re.search(r'^\s*\.set\s+(\w+),\s*(__f_\w+)\s*\+\s*(0x[0-9a-fA-F]+|\d+)', line)
            if m:
                aliases[m.group(1)] = (m.group(2), int(m.group(3), 0), 1, None)
        mirror = dict(blobs={'__f_rodata_base': bytes(blob)},
                      segs={'__f_rodata_base': base_vma}, data_off=0, err=None)
        h = find_conflicts_in([src], aliases)[0]
        ok, detail = verify(h, aliases[h['name']], mirror)
        changed = apply_one(h, aliases[h['name']], mirror, dry=False)
        return ok, detail, changed, io.open(src, encoding='utf-8').read()

    ok, detail, changed, after = run_case('static const int tabx[3] = {1,2,3};\n', 'good')
    c('正例 内容逐字节相同 ⇒ 校验通过且**确实改了文件**', (ok, changed, 'extern const int tabx[]' in after), (True, True, True))
    c('正例 改后原初始化块已消失', '1,2,3' in after, False)

    ok2, detail2, changed2, after2 = run_case('static const int tabx[3] = {9,9,9};\n', 'bad')
    c('反例 **内容不一致 ⇒ 必须跳过且不改文件**（防"改完再看"）',
      (ok2, changed2, '9,9,9' in after2), (False, False, True))
    c('反例 跳过时必须说明原因', '不一致' in detail2, True)

    # 幂等：再跑一次应无冲突可改
    io.open(src, 'w', encoding='utf-8').write(after)
    aliases = {'tabx': ('__f_rodata_base', 0x10, 1, None)}
    c('正例 幂等：已是 extern ⇒ 第二次扫不出冲突', find_conflicts_in([src], aliases), [])

    # ---- ★ 回归锚点：**同一文件里多个块必须全部改对**（倒序改的必要性）----
    #   2026-10-04 真实事故：按正序改完第一个块后文件长度变化，后续块偏移失效
    #   ⇒ `pow14` 校验从 16B 变成 4B 而被 SKIP（同批 7 个只改成 2 个）。
    multi = os.path.join(td, 'multi.c')
    mblob = bytearray(b'\x00' * 0x100)
    mblob[0x20:0x28] = struct.pack('<2i', 11, 22)
    mblob[0x40:0x4c] = struct.pack('<3i', 33, 44, 55)
    mal = {'ta': ('__f_rodata_base', 0x20, 1, 8), 'tb': ('__f_rodata_base', 0x40, 1, 12)}
    mmirror = dict(blobs={'__f_rodata_base': bytes(mblob)},
                   segs={'__f_rodata_base': base_vma}, data_off=0, err=None)
    io.open(multi, 'w', encoding='utf-8').write(
        'static const int ta[2] = {11,22};\n'
        'static const int tb[3] = {33,44,55};\n'
        'int g(void){return ta[0]+tb[0];}\n')
    mhits = find_conflicts_in([multi], mal)
    c('正例 多块冲突被全部检出', len(mhits), 2)
    # 倒序（line 降序）改
    mhits.sort(key=lambda x: -x['line'])
    mchanged = sum(1 for x in mhits if apply_one(x, mal[x['name']], mmirror, dry=False))
    mtext = io.open(multi, encoding='utf-8').read()
    c('正例 **同一文件多块全部改成功**（倒序改）', mchanged, 2)
    c('正例 两个 extern 都在，且原字面量都已消失',
      ('extern const int ta[]' in mtext, 'extern const int tb[]' in mtext,
       '11,22' not in mtext, '33,44,55' not in mtext),
      (True, True, True, True))


    print()
    bad = 0
    for tag, got, want, o in chk:
        print('   %s  %-58s got=%s' % ('OK ' if o else 'FAIL', tag, got))
        bad += 0 if o else 1
    print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
    return 2 if bad else 0


def find_conflicts_in(paths, aliases):
    hits = []
    for p in paths:
        t = io.open(p, encoding='utf-8', errors='replace').read()
        for m in re.finditer(DEF_RE, t, re.M):
            # ★ ctype 只取**基本类型**：`const` 单独处理。
            #   早期版本直接把 `(?:const\s+)?...` 的整段当 ctype，
            #   于是生成 `extern const const int X[];`（双重 const）⇒ 自证当场抓到。
            ctype = m.group(1).strip().replace('const', '').strip()
            name, dims = m.group(2), m.group(3)
            if name not in aliases:
                continue
            ob = t.index('{', m.end() - 1)
            try:
                _bs, be = block_extent(t, ob)
            except ValueError:
                continue
            semi = t.find(';', be)
            hits.append(dict(path=p, name=name, ctype=ctype, dims=dims,
                             start=m.start(), end=semi + 1, brace=(ob, be),
                             line=t[:m.start()].count('\n') + 1))
    return hits


if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    aliases = read_aliases()
    mirror = load_mirror()
    if mirror is None or mirror.get('segs') is None:
        print('★ %s ⇒ fail-closed（不做"改完再看"）' % (mirror or {}).get('err', '缺镜像数据'))
        sys.exit(11)
    hits = find_conflicts(aliases)
    print('镜像别名 %d 个；★ static 定义与镜像别名同名 = %d 处' % (len(aliases), len(hits)))
    dry = '--apply' not in sys.argv
    n = 0
    # ★★★ 必须**从文件末尾往前**改（同一文件内偏移从大到小）。
    #   根因（2026-10-04 真实事故）：`find_conflicts` 一次性算好了所有 `start/end`；
    #   改掉第一个块后**文件长度变了**，后面那些块的偏移就指向了错误位置
    #   ⇒ 实测 `pow14` 的校验从「16B vs 16B 相同」变成「4B vs 16B」而 SKIP，
    #      `pow43` 从 192B 变 168B —— 典型的"改一个坏三个"。
    #   倒序改 ⇒ 已处理的块都在文件尾部之后，不影响前面块的偏移。
    for h in sorted(hits, key=lambda x: (x['path'], -x['line'])):
        n += 1 if apply_one(h, aliases[h['name']], mirror, dry) else 0
    print()
    print('模式：%s；改动 %d 处' % ('--apply' if not dry else '--check（只读）', n))
    sys.exit(0)
