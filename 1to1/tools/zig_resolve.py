#!/usr/bin/env python3
"""zig_resolve.py — **zig 可执行文件的唯一解析器**（纪律 69：同一规则禁止写两处）。

为什么必须收敛成一处（真实代价，4 次复发）：
  ① `ub_census.py` 曾把 Windows 的 `zig.exe` 绝对路径**写死** ⇒ Linux 上 UB 门禁**必然 FAIL**，
     云开发整轮实验白跑（link rc=18）—— §0.26-B6；
  ② `diff_exec.py::_zig()` 同族缺陷 ⇒ Linux 上返回 None —— §0.26-B6；
  ③ `ub_census.py` 修好后又在**链尾**留了一个"本机 Windows 默认路径"兜底（纯冗余）
     ⇒ CI 的「宿主绝对路径门禁」判 FAIL(exit 17) —— §0.36-A；
  ④ `link_full.sh` **只从 `CC` 变量里抠 "zig"** ⇒ 编译器对齐实验（CC=工厂同期 GCC 6.3）
     的 gcc63 两条腿**必然** `exit 3`（"请设 ZIG_BIN"）⇒ `toolchain-ab` 连续红 —— §0.36-I。

⇒ 结论：**"去哪里找 zig" 只有一个答案**，放在这里；其余脚本一律调用它，不得各写一份。

解析顺序（先显式、后环境、最后兜底；**找不到就 fail-closed 并列出试过的候选**）：
  1. `$ZIG_BIN`       （显式指定；CI / 实验腿用它）
  2. `$ZIG`           （历史别名，保留兼容）
  3. `$CC` 里含 zig   （`"<zig> cc"` 这种形态；**不含 zig 的 CC 一律忽略**，见 ④ 的教训）
  4. `PATH` 上的 `zig`
  5. Python 包 `ziglang` 自带的二进制（Windows 是 `zig.exe`，Linux 是 `zig`）
  ★ 不写任何"本机绝对路径"兜底：那种候选只在本机成立，必然在 CI 上变成假红/假绿。

用法
====
  python3 tools/zig_resolve.py            # 打印 zig 路径（供 shell 用 `$(...)` 取值）
  python3 tools/zig_resolve.py --why      # 打印 "路径<TAB>来源"
  python3 tools/zig_resolve.py --self-test
退出码：0 = 找到；2 = 找不到（并把候选清单打到 stderr）。
"""
import os
import shutil
import sys

# ★ 不设"本机默认路径"兜底（原因见模块 docstring ③）。要用本机路径请设 ZIG_BIN。


def _usable(p):
    """路径可用性：存在 + （POSIX 下）可执行。Windows 无 X_OK 语义 ⇒ 只查存在。"""
    if not p:
        return False
    if not os.path.isfile(p):
        return False
    if os.name == 'posix' and not os.access(p, os.X_OK):
        return False
    return True


def _from_cc(cc):
    """`$CC` 形如 `"<zig> cc"` ⇒ 取第一段；**不含 zig 的 CC 一律忽略**。"""
    cc = (cc or '').strip()
    if not cc or 'zig' not in cc:
        return None
    tok = cc.split()[0]
    if _usable(tok):
        return tok
    w = shutil.which(tok)
    return w if _usable(w) else None


def _from_python_package():
    """pip 装的 `ziglang` 包：包里就躺着二进制（Windows `zig.exe` / Linux `zig`）。

    ★ POSIX 下 pip 装出来的二进制**可能没有可执行位** ⇒ 尽力 `chmod +x` 后再判可用
      （原 `check_obj_fresh.py` 自己做过这一步；收敛到此处时**不能丢**，否则 CI 上
      解析会退化成"找不到 zig"）。
    """
    try:
        import ziglang
    except Exception:
        return None
    d = os.path.dirname(os.path.abspath(ziglang.__file__))
    for nm in ('zig.exe', 'zig'):
        c = os.path.join(d, nm)
        if os.path.isfile(c) and os.name == 'posix' and not os.access(c, os.X_OK):
            try:
                os.chmod(c, 0o755)
            except Exception:
                pass
        if _usable(c):
            return c
    return None


def resolve_zig():
    """→ `(路径|None, 来源|试过的候选清单)`。

    找到时返回 `(abs_path, 来源说明)`；找不到时 `(None, [试过的候选...])`。
    """
    tried = []
    for var in ('ZIG_BIN', 'ZIG'):
        v = (os.environ.get(var) or '').strip()
        if _usable(v):
            return os.path.abspath(v), var
        tried.append('%s=%s' % (var, v or '(空)'))
    cc = (os.environ.get('CC') or '').strip()
    p = _from_cc(cc)
    if p:
        return os.path.abspath(p), 'CC 里的 zig'
    tried.append('CC=%s（其中不含可用 zig）' % (cc or '(空)'))
    w = shutil.which('zig')
    if _usable(w):
        return os.path.abspath(w), 'PATH'
    tried.append('PATH 上的 zig')
    p = _from_python_package()
    if p:
        return p, 'python 包 ziglang'
    tried.append('python 包 ziglang（不可用或包内无二进制）')
    return None, tried


def main(argv):
    if '--self-test' in argv:
        chk = []

        def c(tag, got, want):
            chk.append((tag, got, want))

        # 正例：CC 里带 zig ⇒ 能取到（用当前解释器冒充可执行为真）
        _saved = {k: os.environ.get(k) for k in ('ZIG_BIN', 'ZIG', 'CC')}
        try:
            for k in _saved:
                os.environ.pop(k, None)
            _py = os.path.abspath(sys.executable)
            os.environ['ZIG_BIN'] = _py
            c('正例  ZIG_BIN 优先', resolve_zig()[1], 'ZIG_BIN')
            os.environ.pop('ZIG_BIN', None)
            os.environ['ZIG'] = _py
            c('正例  ZIG_BIN 缺失时用 ZIG', resolve_zig()[1], 'ZIG')
            os.environ.pop('ZIG', None)
            os.environ['CC'] = _py + ' cc'          # 解释器路径里不含 "zig"
            c('反例  CC **不含 zig** ⇒ 来源**不得**是 CC（toolchain-ab 的 gcc63 腿就是这种 CC）',
              resolve_zig()[1] != 'CC 里的 zig', True)
            _real, _rwhy = (None, None)
            for _k in ('ZIG_BIN', 'ZIG'):
                os.environ.pop(_k, None)
            _real, _rwhy = _from_python_package(), 'python 包 ziglang'
            if _real:                                # 用真实 zig 路径造一个"含 zig 的 CC"
                os.environ['CC'] = _real + ' cc'
                c('正例  CC 含 zig 且路径真实存在 ⇒ 取第一段',
                  resolve_zig()[1], 'CC 里的 zig')
            else:                                    # 环境里没有 zig 包时跳过该锚点
                c('（跳过）本环境无 ziglang 包，无法构造"含 zig 的 CC"', True, True)
            # 反例：CC 含 zig 但路径不存在 ⇒ 必须继续往下找，不得返回坏路径
            os.environ['CC'] = '/no/such/ziglang/zig cc'
            _r = resolve_zig()
            c('反例  CC 含 zig 但路径不存在 ⇒ 不得返回它', _r[0] is None or _r[1] != 'CC 里的 zig', True)
            for k, v in _saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        finally:
            for k, v in _saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        # 正例：真实环境必须能找到 zig（本机/CI 都应满足；找不到说明环境缺依赖）
        _p, _why = resolve_zig()
        c('正例  当前环境能解析到 zig（本机与 CI 都必须成立）', _p is not None, True)

        bad = 0
        for tag, got, want in chk:
            ok = (got == want)
            bad += 0 if ok else 1
            print('   %s  %-58s got=%s' % ('✓' if ok else '★FAIL', tag[:58], got))
        print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
        return 2 if bad else 0

    p, why = resolve_zig()
    if not p:
        print('!! zig_resolve：找不到 zig 编译器 ⇒ fail-closed（不得退化成 no-op）', file=sys.stderr)
        print('   试过的候选：%s' % ' ; '.join(why), file=sys.stderr)
        print('   修：设 ZIG_BIN=<zig 路径>，或 pip install ziglang'
              '（Linux 下二进制名是 zig，不是 zig.exe）', file=sys.stderr)
        return 2
    if '--why' in argv:
        print('%s\t%s' % (p, why))
    else:
        print(p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
