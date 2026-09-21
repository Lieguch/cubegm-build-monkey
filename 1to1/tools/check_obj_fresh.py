#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游对象**新鲜度**门禁 —— 防止「陈旧预编译对象」静默污染所有判据。

## 要防的是什么（2026-09-21，GAP 16.56 —— 同一根因已复发三次）

`src/upstream/xunzip/XUnzip.o` 曾被"必须入库"，而构建脚本用**源码哈希缓存**决定是否重编。
实测失效实况：
  · 记账哈希 == 当前源码哈希 ⇒ 永远判定"无需重编"；
  · 仓库里的 `.o`（147,896 B，**带 7 个 `.debug_*` 节**）**不是由当前源码编出来的**；
  · `build/rkgame.rebuilt.elf` 的 zip 符号与**陈旧对象逐字一致** ⇒ 一直在链接它。
后果：整整一族符号（`TUnzip::*`、`unz*`、`unzStringFileNameCompare`）的 size 偏离工厂
1.5×~48×，而**源码其实是对的**（同源码用项目 CFLAGS 重编只要 0.96 秒，命中工厂 21/30、
7 个精确到字节）。更贵的是：**判据不报错，只让你读出错误结论** ——
本项目因此把"源码不对"当成根因，做了一件完全没必要的大改。

## 判据（两条，都很便宜）

1. **`rebuilt.elf` 里的符号必须与"现编对象"一致** —— 即重新编一次该对象，逐符号比
   `st_size`；有差异 ⇒ 说明链接的不是现编对象 ⇒ FAIL。
2. **上游预编译对象不得入库** —— 仓库里存在 `src/upstream/xunzip/*.o` ⇒ FAIL
   （正确做法：构建时编，产物不入库）。

退出码：0 = 新鲜；2 = 陈旧/入库对象存在；3 = 无法判定（缺编译器/缺文件）。
"""
import io
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UP = os.path.join(ROOT, 'src', 'upstream', 'xunzip')
SRC = os.path.join(UP, 'unzip.cpp')
OBJ = os.path.join(UP, 'XUnzip.o')
ELF = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
ZIG_DEFAULT = ('C:/Users/Administrator/.workbuddy/binaries/python/envs/default/'
               'Lib/site-packages/ziglang/zig.exe')


def resolve_cc():
    """多级解析编译器 —— 必须能在两种环境都跑：本地 Windows（zig.exe）与 CI Linux（pip 装的 ziglang）。

    ★ 血泪：第一版把 Windows 绝对路径写死 ⇒ 在 CI 上必然"找不到编译器"⇒ 门禁退化成
      "每次都报无法判定"。所以按下面顺序找，并**把找到的那个打印出来**（否则以后
      又会出现"门禁静默退化成 no-op"这种最难查的失效）。
    """
    # ① 显式环境变量（CI 里 cnb_env.sh 会把 CC 设成 "<zig> cc"）
    cc = os.environ.get('CC', '').strip()
    if cc:
        tok = cc.split()[0]
        if os.path.exists(tok):
            return tok, 'env CC'
        import shutil as _sh
        w = _sh.which(tok)
        if w:
            return w, 'env CC(which)'
    # ② ZIG / ZIG_BIN
    for k in ('ZIG', 'ZIG_BIN'):
        v = os.environ.get(k, '').strip()
        if v and os.path.exists(v):
            return v, 'env ' + k
    # ③ PATH 上的 zig
    import shutil as _sh
    w = _sh.which('zig')
    if w:
        return w, 'PATH'
    # ④ python 包 ziglang 自带的 zig（CI 用 `pip install ziglang` 装）
    try:
        import ziglang
        cand = os.path.join(os.path.dirname(ziglang.__file__), 'zig')
        if os.path.exists(cand):
            os.chmod(cand, 0o755)
            return cand, 'python pkg ziglang'
    except Exception:
        pass
    # ⑤ 本地 Windows 默认位置
    if os.path.exists(ZIG_DEFAULT):
        return ZIG_DEFAULT, '本地默认路径'
    return None, "未找到"


def syms(path):
    if not path or not os.path.exists(path):
        return None
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        return None
    es = struct.unpack_from('<H', d, 46)[0]
    sh = struct.unpack_from('<I', d, 32)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
    out = {}
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            out.setdefault(d[stro + nmn:k].decode('utf-8', 'replace'), sz)
    return out


# zip 层符号（两边都该有的那批；用于新鲜度比对）
ZIPFAM = lambda n: ('unz' in n.lower()) or ('TUnzip' in n) or ('HZIP' in n)


def recompile(outdir):
    """用 link_audit.sh 的口径重编一次 unzip.cpp。"""
    zig, how = resolve_cc()
    if not zig:
        return None, '找不到编译器（试过 CC/ZIG/ZIG_BIN/PATH/ziglang 包/本地默认路径）'
    o = os.path.join(outdir, 'XUnzip.fresh.o')
    cmd = [zig, 'cc', '-target', 'arm-linux-gnueabihf.2.29',
           '-mfloat-abi=hard', '-mfpu=neon',
           '-c', '-Os', '-w', '-fno-stack-protector',
           '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
           '-std=gnu++98', '-fno-exceptions', '-I', os.path.join(UP, 'posix'),
           SRC, '-o', o]
    env = dict(os.environ)
    env['ZIG_LOCAL_CACHE_DIR'] = os.path.join(outdir, 'lc')
    env['ZIG_GLOBAL_CACHE_DIR'] = os.path.join(outdir, 'gc')
    r = subprocess.run(cmd, capture_output=True, env=env)
    if not os.path.exists(o):
        return None, r.stderr.decode('utf-8', 'replace')[:400]
    return o, None


def main():
    print('=' * 92)
    print('上游对象新鲜度门禁（XUnzip.o 与现编对象逐符号对拍）')
    print('=' * 92)
    work = os.path.join(ROOT, 'build', '_freshchk')
    os.makedirs(work, exist_ok=True)

    # ---------- 判据 2：**真正起作用的机制** —— push 脚本会不会把它推上去 ----------
    #   ★ 修正（2026-09-21）：上一版查 `.gitignore` 是错的口径 —— 本项目**不用 git 推送**
    #     （`push_1to1.py` 走 GitHub Git Data API，自带文件白名单与跳过规则），
    #     所以 `.gitignore` 对"会不会入库"**没有任何约束力**。真正决定的是 push 脚本里的
    #     `rel.endswith((".pyc", ".o", ...))` 那条跳过规则，以及**有没有给它开例外**。
    push_py = os.path.join(ROOT, 'tools', 'push_1to1.py')
    push_txt = io.open(push_py, 'rb').read().decode('utf-8', 'replace') \
        if os.path.exists(push_py) else ''
    skip_ok = ('.o"' in push_txt or "'.o'" in push_txt) and ('.pyc' in push_txt)
    # 例外句式的特征：`if rel.endswith("src/upstream/xunzip/XUnzip.o"):` + 单独的 pass
    has_exc = ('endswith("src/upstream/xunzip/XUnzip.o")' in push_txt
               or "endswith('src/upstream/xunzip/XUnzip.o')" in push_txt)
    if not skip_ok:
        print('  [判据2a] ★ FAIL —— push 脚本里找不到 `*.o` 的跳过规则（构建产物可能被推送）')
    elif has_exc:
        print('  [判据2a] ★ FAIL —— push 脚本里**仍为 XUnzip.o 开了入库例外**（陈旧对象会被钉住）')
    else:
        print('  [判据2a] ✓ push 脚本会把 `*.o` 当构建产物跳过，且未给 XUnzip.o 开例外')

    # 附注：.gitignore 只作提示（本仓库不用 git 推送）
    gi = os.path.join(ROOT, '.gitignore')
    gi_txt = io.open(gi, 'rb').read().decode('utf-8', 'replace') if os.path.exists(gi) else ''
    ign_ok = True
    print('  [附注] 仓库根 .gitignore %s `src/upstream/xunzip/*.o`（本仓库不走 git 推送）'
          % ('已含' if 'src/upstream/xunzip/*.o' in gi_txt else '不含'))
    #   ★ 口径要精确：**本地存在** `*.o` 是正常的（构建产物）；要判的是
    #     "它**会不会被推送进仓库**"。若会 ⇒ 陈旧对象会在仓库里被钉住（历史三次复发）。
    #     判据 = ① `.gitignore` 是否排除它；② 若本地是 git 仓库，它是否被 track。
    # 本地存在 `*.o` 只作提示（构建产物）
    if os.path.exists(OBJ):
        print('  [提示] 本地存在构建产物 %s（%d B）—— 正常，它不再入库' %
              (os.path.relpath(OBJ, ROOT), os.path.getsize(OBJ)))

    if not os.path.exists(SRC):
        print('  ★ 缺 %s' % SRC)
        return 3

    zig, how = resolve_cc()
    print('  [编译器] %s  （来源：%s）' % (zig or '未找到', how))
    fresh, err = recompile(work)
    if fresh is None:
        print('  ★ 现编失败，无法判定：%s' % (err or '')[:200])
        return 3
    FS, CS, ES = syms(fresh), syms(OBJ), syms(ELF)
    print('  [现编] %s  (%d B)' % (os.path.basename(fresh), os.path.getsize(fresh)))
    print('  [仓库/构建对象] %s  (%s)' % (os.path.relpath(OBJ, ROOT),
                                       ('%d B' % os.path.getsize(OBJ)) if os.path.exists(OBJ) else '缺失'))
    print('  [链接产物] %s  (%s)' % (os.path.relpath(ELF, ROOT),
                                   ('%d B' % os.path.getsize(ELF)) if os.path.exists(ELF) else '缺失'))

    if CS is not None:
        keys = sorted(k for k in FS if ZIPFAM(k) and k in CS)
        diff = [(k, FS[k], CS[k]) for k in keys if FS[k] != CS[k]]
        print()
        print('  [判据1] 现编对象 vs 磁盘对象：比对 %d 个 zip 符号，**不一致 %d 个**' % (len(keys), len(diff)))
        for k, a, b in diff[:12]:
            print('        %-52s 现编 %-6d 磁盘 %-6d' % (k[:52], a, b))
        if diff:
            print('  [判据1] ★ FAIL —— 磁盘对象不是由当前源码编出来的（陈旧）')
        else:
            print('  [判据1] ✓ 磁盘对象与现编一致')

    if ES is not None:
        keys = sorted(k for k in FS if ZIPFAM(k) and k in ES)
        bad = [(k, FS[k], ES[k]) for k in keys if FS[k] != ES[k]]
        print()
        print('  [判据1b] 现编对象 vs **链接产物**：比对 %d 个，不一致 %d 个' % (len(keys), len(bad)))
        for k, a, b in bad[:12]:
            print('        %-52s 现编 %-6d 链接后 %-6d' % (k[:52], a, b))
        if bad:
            print('  [判据1b] ★ FAIL —— 链接进 ELF 的不是当前源码的对象（陈旧链接物）')

    fail = (not (skip_ok and not has_exc)) or (CS is not None and any(
        FS[k] != CS[k] for k in FS if ZIPFAM(k) and k in CS)) or (ES is not None and any(
        FS[k] != ES[k] for k in FS if ZIPFAM(k) and k in ES))
    print()
    if fail:
        print('  结论 : FAIL —— 存在陈旧/入库对象，所有基于 size 与反汇编的判据都不可信')
        return 2
    print('  结论 : PASS（对象新鲜，符号判据可信）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
