#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_vs_factory.py —— 「我们的进度 vs 原厂 rkgame」的**一次性权威审计**。

为什么需要它（而不是再看一遍 diff_exec 的汇总行）：
  diff_exec 的报头只给 `PASS/DIVERGE/...` 四个数，**不回答"发散落在谁的代码里"**。
  而"发散落在上游第三方库"与"发散落在我们自写的专有代码"是**完全不同性质**的两件事：
  前者多半是**版本错配**（根解 = 对齐版本），后者才是我们的实现缺陷。
  ⇒ 混淆这两者，就会把"追着第三方库的版本差异打补丁"当成进度 —— 那就是绕圈。

本工具产出的四段，对应审计要回答的四个问题：
  A. 指纹：两侧的编译器 / 链接器 / libc 构建头 / 上游库版本各是什么？（决定"1:1 机器码保真"是否可达）
  B. 结构：ELF 头 / 节区 / 动态段 / 依赖库 —— 哪些是契约（必须一致）、哪些是实现细节（允许不同）
  C. 覆盖：工厂函数按**来源分桶**（上游 vs 专有），各有几个、多少字节、我们提供了多少
  D. 行为：PASS/DIVERGE 按**来源分桶** —— 发散到底压在哪一边

★ 纪律（沿用项目既有判据）：
  · 所有比例都print出**分子/分母**，不用单一百分比；
  · 「未分类」桶必须**列名**，不得静默并入其它桶；
  · 元数据（st_size/节区/bind）一律从 ELF **读**，不手写常量。

用法：
  python tools/audit_vs_factory.py                       # 全量（跑 diff_exec 的 compare）
  python tools/audit_vs_factory.py --no-exec             # 只做 A/B/C（秒级，不跑差分）
  python tools/audit_vs_factory.py --self-test           # 自证（不依赖本项目数据）
"""
import argparse
import os
import re
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


# --------------------------------------------------------------------------
# 纯函数：可自证的部分
# --------------------------------------------------------------------------
IDENT_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')

# Itanium ABI 名字里的 `_Z`/`_ZN` + 长度前缀标识符；用于把 `_Z7lufreadPvjjP6LUFILE` 还原成 `lufread`


# 工厂的 zlib / unzip 是**以 C++ 编译**的（`#include` 进 .cpp ⇒ 名字被 mangle），
# 且 zlib 在本项目里是**外部库**（DT_NEEDED libz.so.1，src/upstream 下没有 zlib 源码）
# ⇒ 必须单列"外部/工具链提供"，不能混进"我们的实现缺陷"里。
ZLIB_RE = re.compile(r'(inflate|deflate|zlib|adler32|crc32|zcalloc|zcfree|zError|z_stream|'
                     r'huft|inftrees|infblock|z_?version)', re.I)
XUNZIP_RE = re.compile(r'(unz|luf|zip|ZIPENTRY|HZIP)', re.I)
# 编译器/CRT 样板：不是"谁实现的功能"，而是工具链产物 ⇒ 单列，且**不应**计入保真缺口
RUNTIME_RE = re.compile(
    r'^(_start|_init|_fini|call_weak_fn|frame_dummy|register_tm_clones|deregister_tm_clones|'
    r'__do_global_dtors_aux|__libc_csu_init|__libc_csu_fini|__gmon_start__|'
    r'__aeabi_[a-z0-9_]+|__divsi3|__udivsi3|__modsi3|__umodsi3|__divdi3|__udivdi3|'
    r'__gnu_[a-z0-9_]+|_Unwind_[A-Za-z0-9_]+|[A-Za-z_]*_thunk)$')


def demangle_candidates(name):
    """→ 该名字的"可读候选"集合（原样 + Itanium 长度前缀拆出的标识符片段）。

    只实现**长度前缀**这一段（`\\d+<name>`），不做完整 demangle —— 我们只需要
    "这些标识符里有没有上游库的符号名"，完整 demangle 是无谓的复杂度。
    `_Z7lufreadPvjjP6LUFILE` ⇒ {'lufread'}；`_ZN6TUnzip3GetEiP8ZIPENTRY` ⇒ {'TUnzip','Get'}。
    """
    out = {name}
    if not name.startswith('_Z'):
        return out
    s = name[2:]
    if s.startswith('N'):
        s = s[1:]
    i = 0
    while i < len(s):
        m = re.match(r'(\d+)', s[i:])
        if not m:
            break
        n = int(m.group(1))
        j = i + len(m.group(1))
        if n <= 0 or j + n > len(s):
            break
        out.add(s[j:j + n])
        i = j + n
    return out


def classify(name, prop_set, up_idx):
    """→ (桶, 库名或专有模块或 None)

    桶 ∈ {'proprietary', 'upstream', 'both', 'external', 'runtime', 'unknown'}。
    `proprietary` 优先：ledger/functions.csv 是**逐函数确认过**的清单（含地址与模块）。
    """
    if name in prop_set:
        cands = demangle_candidates(name)
        libs = set()
        for c in cands:
            libs |= up_idx.get(c, set())
        return ('both', ','.join(sorted(libs))) if libs else ('proprietary', None)

    cands = demangle_candidates(name)
    libs = set()
    for c in cands:
        libs |= up_idx.get(c, set())
    if libs:
        return 'upstream', ','.join(sorted(libs))

    # 名前缀兜底：zlib / xunzip 在工厂里是 C++ 内联进来的（源码不在 src/upstream 顶层）
    if ZLIB_RE.search(name):
        return 'external', 'zlib(libz.so.1)'
    if XUNZIP_RE.search(name):
        return 'external', 'xunzip(zip_utils.cpp)'
    if RUNTIME_RE.match(name):
        return 'runtime', None
    return 'unknown', None


def bucket_key(name, prop, prop_set, up_idx):
    """→ 报告里用的**桶标签**（唯一真源，C/D 两段共用，避免两处逻辑漂移）。"""
    bucket, lib = classify(name, prop_set, up_idx)
    if bucket in ('proprietary', 'both'):
        return '专有:' + (prop.get(name) or '?')
    if bucket == 'upstream':
        return '上游:' + (lib or '?')
    if bucket == 'external':
        return '外部:' + (lib or '?')
    if bucket == 'runtime':
        return '运行时/CRT'
    return '未分类'


def build_upstream_index(root):
    """→ {标识符: {上游库名}}。库名 = src/upstream/<lib> 的一级子目录名。

    ★ 为什么不按"函数名出现在哪个 .c 里"精确归因：一个标识符可能被多个库引用
      （例如 `strdup`）。本工具只做**桶级**归因，冲突时把全部候选库名列出 —— 不静默归并。
    """
    idx = collections.defaultdict(set)
    base = os.path.join(root, 'src', 'upstream')
    for lib in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        p = os.path.join(base, lib)
        if not os.path.isdir(p):
            continue
        libname = lib.split('-')[0]
        for dirpath, _dirs, files in os.walk(p):
            for fn in files:
                if not fn.endswith(('.c', '.h', '.cpp', '.hpp', '.cc')):
                    continue
                try:
                    txt = open(os.path.join(dirpath, fn), encoding='utf-8',
                               errors='replace').read()
                except OSError:
                    continue
                for m in IDENT_RE.finditer(txt):
                    idx[m.group(0)].add(libname)
    return idx


def selftest():
    chk = []

    def c(label, got, want):
        chk.append((label, got, want))

    up = {'mxmlLoadFile': {'mxml'}, 'inflate': {'xunzip', 'zlib'}, 'shared': {'a', 'b'}}
    prop = {'mui_setting', 'main_Menu'}
    c('专有优先于上游（同名冲突 ⇒ both 桶，不静默归并）',
      classify('shared', prop | {'shared'}, up)[0], 'both')
    c('纯专有', classify('mui_setting', prop, up), ('proprietary', None))
    c('纯上游并给出库名', classify('mxmlLoadFile', prop, up), ('upstream', 'mxml'))
    c('多库引用 ⇒ 库名逗号列出（不任选其一）', classify('inflate', prop, up)[1], 'xunzip,zlib')
    c('★ mangle 名还原（_Z7lufread… ⇒ lufread ⇒ xunzip 外部库桶）',
      classify('_Z7lufreadPvjjP6LUFILE', prop, up), ('external', 'xunzip(zip_utils.cpp)'))
    c('★ mangle 名命中上游索引时按上游归（_ZN6TUnzip3Get… 拆出 Get/TUnzip）',
      demangle_candidates('_ZN6TUnzip3GetEiP8ZIPENTRY'), {'_ZN6TUnzip3GetEiP8ZIPENTRY', 'TUnzip', 'Get'})
    c('★ 长度前缀解析不得越界（畸形串必须安全返回原名）',
      demangle_candidates('_Z99short'), {'_Z99short'})
    c('★ _Z11zlibVersionv ⇒ zlibVersion ⇒ 外部库桶（不得算我方缺陷）',
      classify('_Z11zlibVersionv', prop, up), ('external', 'zlib(libz.so.1)'))
    c('★ 编译器/CRT 样板单列 runtime，不计入"谁实现的功能"',
      classify('__aeabi_idivmod', prop, up)[0], 'runtime')
    c('★ _start 也是 CRT（不是我们的逻辑）', classify('_start', prop, up)[0], 'runtime')
    c('★ zlib 符号不得落进"我方实现缺陷"桶（真实索引下 inflate 可能命中 xunzip）',
      classify('_Z7inflateP10z_stream_si', prop, {})[1], 'zlib(libz.so.1)')
    c('未知必须单列 unknown，不得并入任何桶', classify('__ghidra_synth_9', prop, up)[0], 'unknown')

    # 标识符正则：至少 3 字符（避免 a/i 之类噪音把短符号全判成上游）
    ids = set(m.group(0) for m in IDENT_RE.finditer('int a; int mxmlLoadFile(void);'))
    c('正则过滤掉 1~2 字符标识符', ('a' in ids), False)
    c('正则保留真标识符', ('mxmlLoadFile' in ids), True)
    return chk


# --------------------------------------------------------------------------
# A. 指纹
# --------------------------------------------------------------------------
def section_comment(path):
    from elftools.elf.elffile import ELFFile
    out = []
    try:
        with open(path, 'rb') as f:
            e = ELFFile(f)
            for s in e.iter_sections():
                if s.name in ('.comment', '.note.gnu.gold-version', '.note.gnu.build-id'):
                    out.append((s.name, s.data()))
    except Exception as ex:                                   # pragma: no cover
        out.append(('ERR', str(ex).encode()))
    return out


def needed(path):
    from elftools.elf.elffile import ELFFile
    out = []
    with open(path, 'rb') as f:
        e = ELFFile(f)
        d = e.get_section_by_name('.dynamic')
        if d:
            for t in d.iter_tags():
                if t.entry.d_tag == 'DT_NEEDED':
                    out.append(t.needed)
    return sorted(out)


def rodata_version_strings(path, limit=4000000):
    """从文件里抽"版本风格"的字面串（只读前 limit 字节的 .rodata 更省，但简化为全文件扫描）。"""
    d = open(path, 'rb').read(limit)
    pats = {
        'GCC/编译器标签': rb'GCC: \([^)\x00]{0,40}\)[^\x00]{0,20}',
        'glibc 构建头': rb'glibc-[0-9][0-9.]*',
        'A 装载器内核头': rb'\.armv7a-libre',
        'gold 链接器': rb'GNU gold[^\x00]{0,20}',
    }
    out = {}
    for k, p in pats.items():
        hits = sorted(set(m.group(0).decode('latin1') for m in re.finditer(p, d)))
        if hits:
            out[k] = hits[:6]
    return out


# --------------------------------------------------------------------------
# B. 结构
# --------------------------------------------------------------------------
def elf_summary(path):
    from elftools.elf.elffile import ELFFile
    with open(path, 'rb') as f:
        e = ELFFile(f)
        h = e.header
        secs = [(s.name, s['sh_addr'], s['sh_size'], s['sh_type'])
                for s in e.iter_sections() if s['sh_size'] or s.name]
        ph = [(s['p_type'], s['p_vaddr'], s['p_memsz'], s['p_flags'])
              for s in e.iter_segments()]
        return dict(
            cls=h['e_ident']['EI_CLASS'], machine=h['e_machine'], type=h['e_type'],
            entry=h['e_entry'], flags=h['e_flags'], nsec=h['e_shnum'],
            nph=h['e_phnum'], secs=secs, ph=ph,
        )


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--steps', type=int, default=3000)
    ap.add_argument('--no-exec', action='store_true', help='跳过行为差分（只做 A/B/C）')
    ap.add_argument('--out', default=os.path.join(ROOT, 'report', 'audit_vs_factory.txt'))
    ap.add_argument('--cache', default=os.path.join(ROOT, 'build', '_audit_verdicts.json'),
                    help='判定缓存（重跑秒级；输入指纹变化自动失效）')
    ap.add_argument('--selftest', dest='self_test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        chk = selftest()
        bad = [x for x in chk if x[1] != x[2]]
        for lab, got, want in chk:
            print('  %s %s' % ('OK  ' if got == want else 'FAIL', lab))
            if got != want:
                print('        got=%r want=%r' % (got, want))
        print('  self-test: %d 条，失败 %d 条' % (len(chk), len(bad)))
        return 1 if bad else 0

    L = []

    def w(s='', *rest):
        L.append(s if not rest else (s % rest))

    w('=' * 100)
    w('审计：我们的重建进度 vs 原厂 rkgame')
    w('=' * 100)
    w('  工厂 = %s' % os.path.relpath(a.factory, ROOT))
    w('  我方 = %s' % os.path.relpath(a.ours, ROOT))

    # ---------- A. 指纹 ----------
    w('')
    w('【A】构建指纹 —— 决定「1:1 机器码保真」是否可达')
    w('-' * 100)
    for tag, p in (('工厂', a.factory), ('我方', a.ours)):
        cm = section_comment(p)
        tagline = ' | '.join('%s=%s' % (n, v.replace(b'\x00', b' / ').decode('latin1').strip())
                             for n, v in cm) or '（无 .comment / 无 gold-version 节）'
        w('  %s .comment : %s' % (tag, tagline))
    for tag, p in (('工厂', a.factory), ('我方', a.ours)):
        rs = rodata_version_strings(p)
        w('  %s 其他指纹:' % tag)
        for k in sorted(rs):
            w('      %-16s %s' % (k, rs[k]))
    w('  %-4s DT_NEEDED: %s' % ('工厂', ' '.join(needed(a.factory))))
    w('  %-4s DT_NEEDED: %s' % ('我方', ' '.join(needed(a.ours))))

    # ---------- B. 结构 ----------
    w('')
    w('【B】ELF 结构（契约 vs 实现细节）')
    w('-' * 100)
    sf, so = elf_summary(a.factory), elf_summary(a.ours)
    for k in ('cls', 'machine', 'type', 'entry', 'flags', 'nsec', 'nph'):
        vf = sf[k]
        vo = so[k]
        if isinstance(vf, int):
            vf, vo = hex(vf), hex(vo)
        mark = '＝' if str(vf) == str(vo) else '≠'
        w('  %s %-9s 工厂=%-14s 我方=%s' % (mark, k, vf, vo))
    phf = collections.Counter(t for t, _a, _b, _c in sf['ph'])
    pho = collections.Counter(t for t, _a, _b, _c in so['ph'])
    w('  程序头类型计数  工厂=%s' % dict(phf))
    w('                  我方=%s' % dict(pho))

    # ---------- C. 覆盖 ----------
    from elftools.elf.elffile import ELFFile
    with open(a.factory, 'rb') as f:
        ef = ELFFile(f)
        ffuncs = {s.name: (s['st_value'], s['st_size'])
                  for s in ef.get_section_by_name('.symtab').iter_symbols()
                  if s.name and s['st_info']['type'] == 'STT_FUNC' and s['st_value']}
        ftext = None
        for s in ef.iter_sections():
            if s.name in ('.text',):
                ftext = (s['sh_addr'], s['sh_addr'] + s['sh_size'])
    with open(a.ours, 'rb') as f:
        eo = ELFFile(f)
        otext = None
        for s in eo.iter_sections():
            if s.name == '.text':
                otext = (s['sh_addr'], s['sh_addr'] + s['sh_size'])
        ofuncs = {}
        for s in eo.get_section_by_name('.symtab').iter_symbols():
            if s.name and s['st_info']['type'] == 'STT_FUNC' and s['st_value']:
                ofuncs.setdefault(s.name, []).append(s['st_value'])

    prop = {}
    csvp = os.path.join(ROOT, 'ledger', 'functions.csv')
    if os.path.exists(csvp):
        for ln in open(csvp, encoding='utf-8'):
            p = ln.rstrip('\n').split(',')
            if len(p) >= 4 and p[2]:
                prop[p[2]] = p[3]
    prop_set = set(prop)
    up_idx = build_upstream_index(ROOT)

    w('')
    w('【C】函数覆盖（工厂有名 FUNC 为分母；按**来源**分桶）')
    w('-' * 100)
    w('  工厂有名 FUNC = %d ；我方 .text = [0x%x, 0x%x)' % (len(ffuncs), otext[0], otext[1]))
    w('  我方符号表 FUNC 名 = %d ；专有清单(ledger/functions.csv) = %d ；上游标识符索引 = %d'
      % (len(ofuncs), len(prop_set), len(up_idx)))

    rows = collections.defaultdict(lambda: dict(n=0, bytes=0, placed=0, placed_bytes=0,
                                                in_text=0, names=[]))
    unknown_names = []
    for n, (va, sz) in sorted(ffuncs.items()):
        key = bucket_key(n, prop, prop_set, up_idx)
        r = rows[key]
        r['n'] += 1
        r['bytes'] += sz
        addrs = ofuncs.get(n)
        if addrs:
            r['placed'] += 1
            r['placed_bytes'] += sz
            # "由我们重编" = 落在我们自己的 .text 里
            if any(otext[0] <= x < otext[1] for x in addrs):
                r['in_text'] += 1
        if key == '未分类':
            unknown_names.append(n)

    # 按来源大类聚合
    agg = collections.defaultdict(lambda: dict(n=0, bytes=0, in_text=0, placed=0))
    for k, r in rows.items():
        big = k.split(':')[0]
        agg[big]['n'] += r['n']
        agg[big]['bytes'] += r['bytes']
        agg[big]['in_text'] += r['in_text']
        agg[big]['placed'] += r['placed']
    w('')
    w('  ---- 大类 ----')
    w('  %-10s %6s %10s %12s %10s  %s' % ('来源', '函数数', '字节', '字节占比', '落 .text', '落位率'))
    tb = sum(v['bytes'] for v in agg.values())
    for big in sorted(agg, key=lambda k: -agg[k]['bytes']):
        v = agg[big]
        w('  %-10s %6d %10d %11.1f%% %10d  %5.1f%%'
          % (big, v['n'], v['bytes'], 100.0 * v['bytes'] / max(tb, 1),
             v['in_text'], 100.0 * v['in_text'] / max(v['n'], 1)))
    w('')
    w('  ---- 细分（库 / 专有模块）----')
    w('  %-26s %6s %10s %10s' % ('桶', '函数数', '字节', '落 .text'))
    for k in sorted(rows, key=lambda k: -rows[k]['bytes']):
        r = rows[k]
        w('  %-26s %6d %10d %10d' % (k[:26], r['n'], r['bytes'], r['in_text']))
    if unknown_names:
        w('')
        w('  ★ 未分类（既不在专有清单、也不在上游标识符索引）共 %d 个，**全部列名**：'
          % len(unknown_names))
        for i in range(0, len(unknown_names), 4):
            w('      ' + '  '.join('%-26s' % x for x in unknown_names[i:i + 4]))

    # ---------- D. 行为 ----------
    if not a.no_exec:
        import diff_exec as D
        BF, BO = D.Bin(a.factory), D.Bin(a.ours)
        common = sorted(set(BF.funcs) & set(BO.funcs))
        w('')
        w('【D】行为差分（每函数 3 组输入，--steps %d），按来源分桶' % a.steps)
        w('-' * 100)
        w('  可比函数（两侧同名 FUNC）= %d' % len(common))

        # ★ 判据与 diff_exec 批量路径**同口径**：void 函数的 r0 不作返回值判据
        #   （原因见 GAP 17.12.A2：void 函数的 r0 只是残留值，不是输出）。
        void_fns, vmsg = D.void_fns_from_corpus()
        w('  返回类型：%s' % vmsg)

        # ★ 判定缓存：`compare` 是全流程唯一昂贵步骤（全量 ~90 s），而审计在每次修复后都要重跑。
        #   key 含两侧 ELF 的 (mtime,size,sha256前16) + steps + void 集合规模 ⇒ 任何输入变化都失效。
        import hashlib
        import json

        def _dig(p):
            st = os.stat(p)
            return [st.st_mtime, st.st_size,
                    hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]]

        # ★ 缓存 key **必须含"尺子自身"的指纹**：模型/判据改了而产物没变时，
        #   旧判定会静默复用 ⇒ 报告与工具不一致（"缓存骗人"是这类工具最经典的烂法）。
        ck = {'factory': _dig(a.factory), 'ours': _dig(a.ours), 'steps': a.steps,
              'void': len(void_fns or ()),
              'ruler': [_dig(os.path.join(HERE, f)) for f in ('diff_exec.py', 'libc_model.py')],
              'nomodel': os.environ.get('CGM_NO_LIBC_MODEL') == '1',
              'ver': 4}
        cache = None
        if a.cache and os.path.exists(a.cache):
            try:
                cache = json.load(open(a.cache, encoding='utf-8'))
            except Exception:
                cache = None
        fresh = bool(cache) and cache.get('key') == ck
        verdicts = dict(cache['verdicts']) if fresh else {}
        details = dict(cache.get('details') or {}) if fresh else {}
        if fresh and len(details) != len(verdicts):
            fresh = False
            verdicts, details = {}, {}
        if fresh:
            w('  ★ 命中判定缓存 %s ⇒ 复用 %d 条判定（输入指纹未变）'
              % (os.path.relpath(a.cache, ROOT), len(verdicts)))

        beh = collections.defaultdict(lambda: collections.Counter())
        for i, n in enumerate(common):
            if n in verdicts:
                v = verdicts[n]
            else:
                v, rows = D.compare(BF, BO, n, a.steps, void_fns=void_fns)
                if v == 'TRUNC':
                    v2, _r2 = D.compare(BF, BO, n, a.steps * D.ESCALATE_FACTOR,
                                        void_fns=void_fns)
                    if v2 != 'TRUNC':
                        v = v2
                verdicts[n] = v
                details[n] = sorted({str(t) for r in rows if len(r) > 8 and r[8]
                                     for t in r[8]})[:12]
                if (i + 1) % 50 == 0:
                    sys.stderr.write('   ... %d/%d\n' % (i + 1, len(common)))
            beh[bucket_key(n, prop, prop_set, up_idx)][v] += 1
        if a.cache:
            os.makedirs(os.path.dirname(a.cache) or '.', exist_ok=True)
            with open(a.cache, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump({'key': ck, 'verdicts': verdicts, 'details': details}, fh,
                          ensure_ascii=False, sort_keys=True)

        w('')
        w('  ---- 每个桶的判定矩阵 ----')
        w('  %-26s %6s %8s %8s %8s %8s' % ('桶', '可比', 'PASS', 'DIVERGE', 'INFO', 'TRUNC'))
        for k in sorted(beh, key=lambda k: (-beh[k]['DIVERGE'], -sum(beh[k].values()))):
            c = beh[k]
            w('  %-26s %6d %8d %8d %8d %8d'
              % (k[:26], sum(c.values()), c['PASS'], c['DIVERGE'], c['INFO'], c['TRUNC']))
        tot = collections.Counter()
        for c in beh.values():
            tot.update(c)
        w('  %-26s %6d %8d %8d %8d %8d'
          % ('合计', sum(tot.values()), tot['PASS'], tot['DIVERGE'], tot['INFO'], tot['TRUNC']))

        # ★ 发散名单**直接从 verdicts 派生**（与上面的矩阵同源），杜绝"表与名单不同源"。
        by_bucket = collections.defaultdict(list)
        for n, v in verdicts.items():
            if v == 'DIVERGE':
                by_bucket[bucket_key(n, prop, prop_set, up_idx)].append(n)
        n_listed = sum(len(v) for v in by_bucket.values())
        w('')
        w('  ★ 一致性自检：名单总数 %d  vs  矩阵 DIVERGE 合计 %d  ⇒ %s'
          % (n_listed, tot['DIVERGE'],
             '一致' if n_listed == tot['DIVERGE'] else '★不一致（工具缺陷，结论不可用）'))
        w('')
        w('  ---- 全部 DIVERGE 函数（按桶，**不截断**）----')
        for k in sorted(by_bucket, key=lambda k: (-len(by_bucket[k]), k)):
            names = sorted(by_bucket[k])
            w('  [%s] %d 个：' % (k, len(names)))
            for i in range(0, len(names), 3):
                w('      ' + '  '.join('%-30s' % x for x in names[i:i + 3]))
        big = collections.Counter()
        for k, names in by_bucket.items():
            big[k.split(':')[0]] += len(names)
        w('')
        w('  ---- 大类汇总 ----')
        for k in sorted(big, key=lambda k: -big[k]):
            w('  %-12s %3d 个发散' % (k, big[k]))

        # ---- E. 把 84 条发散归到**根因类别**（可操作的修复清单）-----------------
        w('')
        w('【E】发散 → 根因类别（这是"下一步打哪里"的清单）')
        w('-' * 100)
        w('  分类规则（只按**主导差异**分，互斥；每类给出"该改什么"）：')
        w('    WIDTH-R   同址**两侧都读**、宽度不同 ⇒ **真实的声明宽度缺陷**：')
        w('                                    工厂读 4B / 我们读 1B ⇒ 读到的**值不同**。')
        w('                                    修法：按**指令的真实访存宽度**改 C 声明')
        w('    W-RANGE   写覆盖区间不一致（已做同向合并后仍不同）⇒ 真丢失/多余的写')
        w('    R-SET     读集合不同（一侧读、另一侧完全不读）⇒ 可能真缺失，也可能内联/私有副本')
        w('    FINAL     `data-final` 不同    ⇒ 真语义差异（函数最终留下的状态不同）')
        w('    CRASH     停止方式不同         ⇒ 一侧崩、一侧正常返回（最优先）')
        w('    RET       返回值不同           ⇒ 真语义差异')
        w('    CALLONLY  仅外部调用集合不同   ⇒ 大概率纯函数被 CSE / 少一次调用')
        w('    INSTR     仅"未建模调用"不同   ⇒ **仪器**（模型还缺函数），不是代码缺陷')
        w('')
        RX_W = re.compile(r"^data-writes")
        RX_R = re.compile(r'^data-reads 仅F=\[(.*?)\] 仅O=\[(.*?)\]')
        # ★ 展示串的格式是 `<名字>+<偏移>:<宽度>:<读写>@0x<地址> ×N`
        #   ⇒ 正则必须按这个**顺序**取（宽度/读写在前、地址在后）。写反了会静默
        #   一条都匹配不到，而"匹配不到"表现为"这一类为 0"—— 又一个"静默漏"。
        RX_PAIR = re.compile(r':(\d+):([RW])@0x([0-9a-f]+)')

        def width_pairs(ds):
            """→ 存在「同地址、**两侧都读**、宽度不同」的对？返回 (True, 例子)。

            ★ 这一类才是**真实的声明宽度缺陷**：工厂读 4 字节、我们读 1 字节 ⇒ 读到的值不同。
            必须与"一侧根本没读"（R-SET，可能是仪器/内联）严格分开 —— 混在一起会
            把一个可操作的清单变成不可操作的清单。
            """
            for d in ds:
                m = RX_R.match(d)
                if not m:
                    continue
                kf = {a: w for w, _rw, a in RX_PAIR.findall(m.group(1))}
                ko = {a: w for w, _rw, a in RX_PAIR.findall(m.group(2))}
                both = set(kf) & set(ko)
                bad = [(a, kf[a], ko[a]) for a in both if kf[a] != ko[a]]
                if bad:
                    return True, bad[:3]
            return False, []

        def classify_kind(ds):
            """主导差异类别（互斥）。优先级 = 修复优先级（真语义在前，疑似仪器在后）。"""
            if any(d.startswith('stop ') for d in ds):
                return 'CRASH'
            if any(d.startswith('data-final') for d in ds):
                return 'FINAL'
            if any(d.startswith('ret ') for d in ds):
                return 'RET'
            ok, _ex = width_pairs(ds)
            if ok:
                return 'WIDTH-R'
            if any(RX_W.match(d) for d in ds):
                return 'W-RANGE'
            if any(d.startswith('data-reads') for d in ds):
                return 'R-SET'
            if any(d.startswith('calls_ext') for d in ds):
                return 'CALLONLY'
            return '其他'

        kinds = collections.defaultdict(list)
        for n in sorted(by_bucket and [x for v in by_bucket.values() for x in v] or []):
            pass
        all_div = sorted(x for vs in by_bucket.values() for x in vs)
        for n in all_div:
            kinds[classify_kind(details.get(n) or [])].append(n)
        w('  %-10s %5s   %s' % ('类别', '个数', '函数（前 12）'))
        for k in sorted(kinds, key=lambda k: -len(kinds[k])):
            w('  %-10s %5d   %s' % (k, len(kinds[k]), ', '.join(kinds[k][:12])))
        w('')
        w('  ---- 逐条：类别 + 所属桶 + 首个差异原文（前 60 条）----')
        for i, n in enumerate(all_div[:60], 1):
            k = classify_kind(details.get(n) or [])
            bkt = bucket_key(n, prop, prop_set, up_idx)
            first = (details.get(n) or [''])[0]
            w('  %3d. %-10s %-24s %-30s %s' % (i, k, n[:30], bkt[:24], first[:110]))

    txt = '\n'.join(L) + '\n'
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt)
    print(txt)
    print('→ 已写入 %s' % a.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
