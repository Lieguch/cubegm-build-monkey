#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ghidra_corpus —— Ghidra 逐函数原始 C 语料的**唯一**加载入口。

背景（这是本项目**反复复发**的一类病，已烧掉三轮 CI）
----------------------------------------------------
门禁需要"权威对照"才能判：`02-ghidra-c/03-per-function/` 是 Ghidra 逐函数反编译输出。
它有 812 个文件、3.3 MB，原先只存在于**开发机**上 ⇒ 任何直接引用它的工具都会：
    本地绿（有目录） + CI 红（`FileNotFoundError`）——`src_transcript_parity.py` 实测如此。
更坏的一种是：工具**捕获不到就静默跳过并返回 0** ⇒ 门禁在 CI 里**根本没跑**，
却显示 PASS（实测 `scan_call_args.py`，CI 日志两次出现 `[SKIP] 找不到工厂反编译目录`）。

**本模块就是这条纪律的落地：凡需要这份语料，一律走这里，不要自己拼路径。**

解析顺序（仓内优先；全都没有 ⇒ 返回 None，由调用方 **fail-closed**）
--------------------------------------------------------------------
    ① 环境变量 `GHIDRA_PERFUNC`（必须过最小语料量，防止指到半包目录）
    ② 仓内 `golden/ghidra-perfn.tar.gz` 解包缓存 `build/_ghidra_perfn/`
    ③ 仓内 `golden/ghidra-perfn.tar.gz`（就地解包；**不做任何批量删除**）
    ④ 开发机路径（仅便利，CI 上不存在）

用法
----
    from ghidra_corpus import resolve_corpus
    d, src = resolve_corpus()
    if d is None:
        sys.exit(2)          # ★ 不要 `return 0`：跳过 ≠ 通过
    print('语料来源:', src)
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS_TGZ = os.path.join(ROOT, 'golden', 'ghidra-perfn.tar.gz')
CORPUS_CACHE = os.path.join(ROOT, 'build', '_ghidra_perfn')
CORPUS_DEV = r'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function'
# ★ 最小语料量：实测真语料 812 个 `.c`。阈值 700 是"截断/半包上传"的兜底 ——
#   半包会让"只在 Ghidra 有"的计数暴涨，却**不会报错**（那是假绿）。宁可 fail-closed。
MIN_CORPUS_C = 700


def corpus_count(d):
    if not d or not isinstance(d, (str, bytes, os.PathLike)):
        return 0
    try:
        return sum(1 for n in os.listdir(d) if n.endswith('.c')) if os.path.isdir(d) else 0
    except OSError:
        return 0


def _find_corpus(dest, min_c=1, exact=None):
    """在 `dest` 下找有效语料目录（tar 里带一层 `03-per-function/`，故下钻一层）。"""
    if not dest:
        return None
    for cand in (os.path.join(dest, '03-per-function'), dest):
        n = corpus_count(cand)
        if n >= min_c and (exact is None or n == exact):
            return cand
    return None


def _is_corpus(d, min_c=1):
    return corpus_count(d) >= min_c


def _tar_c_count(tgz):
    """只读 tar 索引，数它声明了多少个 `.c`（不落盘）。"""
    import tarfile
    with tarfile.open(tgz, 'r:gz') as tf:
        return sum(1 for m in tf.getmembers() if m.name.endswith('.c') and m.isfile())


def _unpack_into(tgz, dest):
    """把语料 tar.gz **直接解到 `dest`** —— 刻意**不做任何批量删除**。

    三个真实坑（都踩过，别再走回头路）：
      ① `tf.extractall(filter='data')` 在 **Windows** 上报 `OSError(22, ERROR_INVALID_FUNCTION)`
         ⇒ 必须留一条无 filter 的回退路径（本 tar 是我们自己生成的纯文件/目录，无链接）；
      ② 用 `shutil.rmtree(dest)` 清旧缓存 ⇒ **本机沙箱的"批量删除守卫"**（>50 文件）会
         直接拦下 `exit 1`（实测 `SAFE_DELETE_BULK_CONFIRM_REQUIRED`，812 文件）；
      ③ 直接解到 `dest` 时若中途失败会留下半包，而半包可能恰好 ≥ 阈值 ⇒ 假绿。
      ⇒ 现方案：**内容不可变 ⇒ 覆盖即幂等**；半包由"解出数必须 == tar 声明数"兜住，不靠删除。
    """
    import tarfile
    import warnings
    os.makedirs(dest, exist_ok=True)
    last = None
    for kwargs in ({'filter': 'data'}, {}):
        try:
            with tarfile.open(tgz, 'r:gz') as tf, warnings.catch_warnings():
                # 无 filter 分支在 3.12–3.13 会告 DeprecationWarning；此处是**有意的**兼容回退
                # （filter='data' 在 Windows 上必失败，见本函数 docstring）⇒ 局部静音，别污染 CI 日志。
                warnings.simplefilter('ignore', DeprecationWarning)
                tf.extractall(dest, **kwargs)
            return
        except Exception as e:
            last = e
            continue
    raise last


def resolve_corpus():
    """返回 `(目录, 来源说明)`；找不到时 `(None, 'MISSING...')`（**调用方必须 fail-closed**）。"""
    env = os.environ.get('GHIDRA_PERFUNC')
    # ★ env 也必须过「最小语料量」：否则一个指向半包/空目录的 env 会被采纳 ⇒ 假绿。
    #   （这条是 `src_transcript_parity.py --self-test` 跑出来的，首版只判 min_c=1。）
    if _is_corpus(env, MIN_CORPUS_C):
        return env, 'env:GHIDRA_PERFUNC(%d .c)' % corpus_count(env)
    # ① 已解包缓存（**先查子目录**：`.c` 在 `03-per-function/` 里，只查 `CORPUS_CACHE` 本身
    #    永远为 0 ⇒ 每跑一次都重新解包 —— 实测代价：本地被沙箱"批量删除守卫"拦下 exit 1）
    c = _find_corpus(CORPUS_CACHE, MIN_CORPUS_C)
    if c:
        return c, 'repo:golden/ghidra-perfn.tar.gz(已解包, %d .c)' % corpus_count(c)
    # ② 仓内 tar.gz
    if os.path.exists(CORPUS_TGZ):
        try:
            expect = _tar_c_count(CORPUS_TGZ)
        except Exception as e:
            sys.stderr.write('★ golden/ghidra-perfn.tar.gz 索引不可读：%r\n' % (e,))
            return None, 'MISSING(tar 损坏)'
        if expect < MIN_CORPUS_C:
            return None, 'MISSING(tar 只声明 %d 个 .c（< %d 下限）)' % (expect, MIN_CORPUS_C)
        try:
            _unpack_into(CORPUS_TGZ, CORPUS_CACHE)
        except Exception as e:
            sys.stderr.write('★ golden/ghidra-perfn.tar.gz 解包失败：%r\n' % (e,))
            return None, 'MISSING(tar 损坏)'
        c = _find_corpus(CORPUS_CACHE, MIN_CORPUS_C, exact=expect)
        if c:
            return c, 'repo:golden/ghidra-perfn.tar.gz(本次解包 %d/%d .c)' % (corpus_count(c), expect)
        return None, 'MISSING(解出 %d ≠ tar 声明 %d)' % (corpus_count(CORPUS_CACHE), expect)
    if _is_corpus(CORPUS_DEV):
        return CORPUS_DEV, 'dev:本机路径(%d .c)' % corpus_count(CORPUS_DEV)
    return None, 'MISSING'


REPAIR_HINT = (
    '\n★ 前置缺失败：找不到 Ghidra 逐函数语料。\n'
    '  本判据**不做静默跳过**（静默跳过 = 假绿 ⇒ 门禁看起来 PASS 其实没跑）。\n'
    '  修复任选其一：\n'
    '    ① 确认仓库里存在 `golden/ghidra-perfn.tar.gz`（应随仓交付，253 KB）；\n'
    '    ② 或设环境变量 GHIDRA_PERFUNC=<目录> 指向 `03-per-function/`；\n'
    '    ③ 或把本机 `D:/output/rkgame/decompiled/02-ghidra-c/03-per-function` 放回原处。\n\n')


def self_test():
    """语料解析的**三态自证**（`src_transcript_parity.py --self-test` 会调用）。"""
    global CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV
    import tarfile
    import tempfile
    saved = (CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV)
    saved_env = os.environ.pop('GHIDRA_PERFUNC', None)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-14s %s' % (tag, got, '✓' if good else '★ FAIL'))

    d = tempfile.mkdtemp()
    try:
        good = os.path.join(d, 'good')
        os.makedirs(good)
        for i in range(MIN_CORPUS_C):
            open(os.path.join(good, 'FUN_%08x_x.c' % i), 'w').write('int f(void){ a(); return 0; }\n')
        thin = os.path.join(d, 'thin')
        os.makedirs(thin)
        for i in range(3):
            open(os.path.join(thin, 'FUN_%08x_x.c' % i), 'w').write('int f(void){return 0;}\n')
        tgz = os.path.join(d, 'perfn.tar.gz')
        with tarfile.open(tgz, 'w:gz') as tf:
            tf.add(thin, arcname='03-per-function')
        good_tgz = os.path.join(d, 'good.tar.gz')
        with tarfile.open(good_tgz, 'w:gz') as tf:
            tf.add(good, arcname='03-per-function')
        CORPUS_TGZ = os.path.join(d, 'nope.tar.gz')
        CORPUS_CACHE = os.path.join(d, 'nope_cache')
        CORPUS_DEV = os.path.join(d, 'nope_dev')

        got, _src = resolve_corpus()
        chk('反例 三者皆无 → None（fail-closed）', got, None)

        os.environ['GHIDRA_PERFUNC'] = good
        got, _src = resolve_corpus()
        chk('正例 GHIDRA_PERFUNC 指向语料 → 采用', got, good)
        os.environ['GHIDRA_PERFUNC'] = thin
        got, _src = resolve_corpus()
        chk('反例 GHIDRA_PERFUNC 指向不足语料 → 不采用', got, None)
        os.environ.pop('GHIDRA_PERFUNC', None)

        CORPUS_TGZ = good_tgz
        got, src = resolve_corpus()
        chk('正例 只有仓内 tar.gz → 解包并采用', got, os.path.join(CORPUS_CACHE, '03-per-function'))
        chk('      来源标注含 tar.gz', 'tar.gz' in src, True)
        # ★ 幂等：第二次不得重新解包（缓存命中）
        got2, src2 = resolve_corpus()
        chk('正例 第二次调用命中缓存（幂等）', got2, got)

        CORPUS_TGZ = tgz
        CORPUS_CACHE = os.path.join(d, 'thin_cache')
        got, _src = resolve_corpus()
        chk('反例 tar.gz 半包（不足 %d）→ None' % MIN_CORPUS_C, got, None)
    finally:
        if saved_env is not None:
            os.environ['GHIDRA_PERFUNC'] = saved_env
        CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV = saved
    return ok


if __name__ == '__main__':
    d, s = resolve_corpus()
    print('语料: %s' % d)
    print('来源: %s' % s)
    sys.exit(0 if d else 2)
