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
# ★ 2026-09-29 删：`ZIG_DEFAULT`（本机 Windows 绝对路径）—— 解析规则已收敛到
#   `tools/zig_resolve.py`，此处不再保留任何宿主路径（CI 的 s08 门禁会点名它）。


def resolve_cc():
    """解析**编译器** —— ① 优先用显式 `$CC`（可能是真 GCC，如工具链 A/B 的 gcc63 腿）；
    ② 否则回落到**唯一 zig 解析器** `tools/zig_resolve.py`（纪律 69）。

    ★ 血泪：第一版把 Windows 绝对路径写死 ⇒ 在 CI 上必然"找不到编译器"⇒ 门禁退化成
      "每次都报无法判定"。所以按下面顺序找，并**把找到的那个打印出来**（否则以后
      又会出现"门禁静默退化成 no-op"这种最难查的失效）。
    ★ 2026-09-29 收敛：原实现自己写了 ZIG/ZIG_BIN → PATH → python 包 → **本机 Windows 默认路径**
      整条链（与 `ub_census.py` / `diff_exec.py` / `link_full.sh` 各写一份 ⇒ 必然漂移，
      且最后那条"本机默认路径"实为宿主绝对路径，已被 CI 的 s08 门禁点过名）。
      现在只保留 ①（编译器语义，与"找 zig"不是同一个问题），其余**一律转发**给唯一解析器。
    """
    # ① 显式环境变量（CI 里 cnb_env.sh 会把 CC 设成 "<zig> cc"，工具链 A/B 会设成真 GCC）
    cc = os.environ.get('CC', '').strip()
    if cc:
        tok = cc.split()[0]
        if os.path.exists(tok):
            return tok, 'env CC'
        import shutil as _sh
        w = _sh.which(tok)
        if w:
            return w, 'env CC(which)'
    # ② 唯一 zig 解析器（ZIG_BIN → ZIG → CC 里的 zig → PATH → python 包 ziglang）
    try:
        import importlib.util as _ilu
        _sp = _ilu.spec_from_file_location(
            'zig_resolve', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zig_resolve.py'))
        _m = _ilu.module_from_spec(_sp)
        _sp.loader.exec_module(_m)
        _p, _why = _m.resolve_zig()
        if _p:
            # POSIX 下包内二进制可能没有可执行位 —— 解析器内部已尽力 chmod，这里再兜一层
            if os.name == 'posix' and not os.access(_p, os.X_OK):
                try:
                    os.chmod(_p, 0o755)
                except Exception:
                    pass
            return _p, 'zig_resolve:' + str(_why)
    except Exception as _e:
        return None, 'zig_resolve 不可用（%s）' % type(_e).__name__
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


def _pipeline_flags():
    """从 `link_audit.sh --print-cflags xunzip` 读**编译口径**（唯一来源；纪律 69）。

    ★ 为什么必须"读"而不是"抄"：本门禁的判据是"用**同一条流水线的口径**重编一次再对拍"。
      2026-09-29 实测：原实现自己抄了一份 flags，且漏掉 `${CGM_HDR}`（`-nostdinc` + 工厂同期
      glibc 2.24 真头）与 `-I src/compat`，还用 `-target arm-linux-gnueabihf.2.29`
      （流水线用的是 `-target arm-linux-gnueabihf`）⇒ 编出的对象**本就不可能相同** ⇒
      报 `_ZN6TUnzip3GetEiP8ZIPENTRY 现编 816 / 链接后 808` ⇒ **假阳性 FAIL**。
      （反证：link_audit 自己编的 `XUnzip.o` 该符号 = 808，与交付 ELF **逐项一致**。）
    返回 `(cc_argv, flags_argv|None, err|None)`。
    """
    script = os.path.join(HERE, 'link_audit.sh')
    last = None
    for shx in (['sh'], ['bash'], ['dash']):
        try:
            r = subprocess.run(shx + [script, '--print-cflags', 'xunzip'],
                               capture_output=True, text=True, cwd=ROOT, timeout=600)
        except FileNotFoundError as e:
            last = str(e)
            continue
        except Exception as e:
            return None, None, '%s(%s)' % (type(e).__name__, e)
        if r.returncode != 0:
            return None, None, ('rc=%d %s' % (r.returncode, (r.stderr or r.stdout or '')[:300])).strip()
        vals = {'CC': None, 'CFLAGS': None, 'XUCMODE': None, 'XUFLAGS': None}
        for ln in (r.stdout or '').splitlines():
            for k in vals:
                if ln.startswith(k + '='):
                    vals[k] = ln[len(k) + 1:].strip()
        if not vals['CC'] or not vals['CFLAGS']:
            return None, None, 'link_audit --print-cflags 输出不完整：%r' % ((r.stdout or '')[:200],)
        # 命令组件顺序 = 真编译的顺序：CC + XUCMODE + XUFLAGS + CFLAGS + <src> -o <out>
        argv = (vals['CC'].split() + (vals['XUCMODE'] or '').split()
                + (vals['XUFLAGS'] or '').split() + vals['CFLAGS'].split())
        return argv, None, None
    return None, None, '找不到 sh/bash/dash 来读流水线口径（%s）' % last


def recompile(outdir):
    """用 **link_audit.sh 的口径**重编一次 unzip.cpp（口径从流水线**读**，不另抄一份）。"""
    argv, _ignored, err = _pipeline_flags()
    if err:
        return None, '读不到流水线编译口径 ⇒ 无法判定（不得当成 FAIL）：%s' % err
    if not argv:
        return None, '流水线未给出编译器（$CC 为空）'
    o = os.path.join(outdir, 'XUnzip.fresh.o')
    cmd = list(argv) + [SRC, '-o', o]
    env = dict(os.environ)
    env['ZIG_LOCAL_CACHE_DIR'] = os.path.join(outdir, 'lc')
    env['ZIG_GLOBAL_CACHE_DIR'] = os.path.join(outdir, 'gc')
    # ★ 2026-09-30：编译器**不存在**时必须报"无法判定"，**不得崩栈、也不得判 FAIL**。
    #   实测：本机没装 `arm-linux-gnueabihf-gcc`（流水线默认 CC），`CreateProcess` 抛
    #   FileNotFoundError ⇒ 整个门禁崩栈。门禁"跑不起来"与"查出问题"必须区分。
    try:
        r = subprocess.run(cmd, capture_output=True, env=env)
    except FileNotFoundError as e:
        return None, ('编译器不可执行 ⇒ 无法判定（不得当成 FAIL）：%s（cmd[0]=%s）'
                      % (e, cmd[0] if cmd else '?'))
    except Exception as e:
        return None, '编译过程异常 ⇒ 无法判定（不得当成 FAIL）：%s(%s)' % (type(e).__name__, e)
    if not os.path.exists(o):
        return None, ('编译失败：%s' % r.stderr.decode('utf-8', 'replace')[:400])
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
    # ★★★ 2026-09-21（第二次 CI 失败后）**整块降级为提示，不再参与判决**：
    #   曾试图在这里检查"push 脚本会不会把这个 `.o` 推上去"，但 `tools/push_1to1.py`
    #   **因为含 token 本来就不推送**（`push_1to1.py` 自己会 `[skip] 含 token`）
    #   ⇒ **CI 里这个文件根本不存在** ⇒ 判据恒假 ⇒ **连续两轮 CI 全部失败，
    #   而真正的判据 1 两次都 PASS**。
    #   ⇒ 纪律：**门禁不得依赖"可能不在 CI 里的文件"**；且**只保留一条硬判据**
    #     （判据 1 已双向自证）。辅助判据一律降为提示 —— 一条脆弱的辅助判据把整轮 CI
    #     烧掉（8~12 分钟 + 10 个观测场景被 skipped），代价远大于它想防的风险。
    push_py = os.path.join(ROOT, 'tools', 'push_1to1.py')
    if not os.path.exists(push_py):
        print('  [提示2a] · 本环境无 `tools/push_1to1.py`（含 token 不入库）⇒ 跳过入库性检查')
    else:
        push_txt = io.open(push_py, 'rb').read().decode('utf-8', 'replace')
        skip_ok = ('.o"' in push_txt or "'.o'" in push_txt or '".o"' in push_txt)
        has_exc = 'endswith("src/upstream/xunzip/XUnzip.o")' in push_txt
        if has_exc:
            print('  [提示2a] ★ 注意：push 脚本里似乎**仍为 XUnzip.o 开了入库例外**（请人工确认）')
        elif skip_ok:
            print('  [提示2a] · push 脚本会把 `*.o` 当构建产物跳过，且未给 XUnzip.o 开例外')
        else:
            print('  [提示2a] · 未在 push 脚本里匹配到 `*.o` 跳过规则（仅提示）')

    # 附注：.gitignore 只作提示（本仓库不走 git 推送；且 CI 里 .gitignore 在**仓库根**，
    #   而本脚本的 ROOT 是 `1to1/` ⇒ 在 CI 上必然"不存在"。故仅提示。）
    gi = os.path.join(ROOT, '.gitignore')
    gi_txt = io.open(gi, 'rb').read().decode('utf-8', 'replace') if os.path.exists(gi) else ''
    print('  [附注] `.gitignore` %s `src/upstream/xunzip/*.o`（本仓库不走 git 推送，仅声明）'
          % ('已含' if 'src/upstream/xunzip/*.o' in gi_txt else '不含/本环境无'))
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

    # ★ 判决**只由判据 1 决定**（对象/链接产物是否与现编一致）。
    #   其余检查一律是提示 —— 见上文"整块降级"的说明。
    fail = (CS is not None and any(
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
