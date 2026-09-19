#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_proto_vs_upstream.py —— 「proto.h 声明 vs 上游头文件真签名」对拍门禁。

## 为什么需要它（2026-09-18 第 47 轮的真实缺陷）

`src/compat/proto.h` 是**我们自己写**的声明表（Ghidra 类型 + 手写参数表），
而上游库的真签名写在 `src/upstream/**` 的头文件里。两者一旦不一致，
**编译器不会报错**（那是合法声明），但 ABI 会错位。已实测：

    extern float stbtt_ScaleForPixelHeight(float param_1, void *param_2);
    真签名：float stbtt_ScaleForPixelHeight(const stbtt_fontinfo *info, float height);

顺序与类型都是反的。同类还有「参数个数不对」（如 `stbtt_GetFontVMetrics` 少第 4 参），
以及「缺原型」（由 `tools/scan_implicit_decl.py` 覆盖）。

## 判据为什么只看「元数 + 每个参数的 float 位 + 返回值 float 性」

不能用类型名直接比：proto.h 用 `gh_u1/gh_u4/void *`，上游用 `unsigned char */int/stbtt_fontinfo *`，
别名不同会全员假阳性。而 **AAPCS 的浮点/整数分类**才是 ABI 关键：
  · 参数个数错 ⇒ 寄存器/栈槽错位（必错）；
  · 第 k 个参数「是不是 float」错 ⇒ 该参数进 s 寄存器还是 r 寄存器就错了（必错）；
  · 返回值 float 与否 ⇒ 返回在 s0 还是 r0（必错）。
这三项对类型别名鲁棒，且正好覆盖 ABI 的真实风险面。

## 自证（正负双向）

  ① 构造性：合成一对（上游 `void f(void*,float,float)` vs 我们 `void f(float,float,void*)`）
     必须被判定为不一致；
  ② 状态感知：本项目**已修好**的 4 个 stbtt 函数必须**不被报出**（若被报出 ⇒ 判据或修法有问题）。
"""
import argparse
import io
import os
import re
import sys

NL = chr(10)


def strip_comments(t):
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    t = re.sub(r'//[^\n]*', ' ', t)
    return t


# 声明：<ret ...> name ( <params> ) ;      （尽量减少误匹配：ret 段不含 ';' ',' '='）
DECL = re.compile(r'([A-Za-z_][\w \t\*]*?)\b([A-Za-z_]\w*)\s*\(([^;{}]*?)\)\s*;', re.S)

# 只在这些上游头里找真签名（libiconv 的字集表不是 API）
SKIP_DIR = 'libiconv'


def truth_headers(root):
    out = []
    base = os.path.join(root, 'src', 'upstream')
    for dp, _dn, fs in os.walk(base):
        rel = os.path.relpath(dp, base).replace(os.sep, '/')
        for f in sorted(fs):
            if not f.endswith('.h'):
                continue
            if rel.startswith(SKIP_DIR) and f != 'iconv.h':
                continue
            out.append(os.path.join(dp, f))
    return out


def split_params(p):
    """顶层逗号切分（忽略括号/方括号内的逗号）。"""
    parts, d, cur = [], 0, ''
    for c in p:
        if c in '([':
            d += 1
        if c in ')]':
            d -= 1
        if c == ',' and d == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += c
    if cur.strip():
        parts.append(cur)
    return [x.strip() for x in parts if x.strip()]


def sig_of(ret, params):
    """(元数, 每个参数是否 float, 返回值是否 float, 是否变参)。

    ★★ K&R 声明（`extern void f();` —— 括号内为空）**不参与元数比较**：
      C 里 `()` 的含义是"参数不可知/不检查"，与"零参数"完全不同。
      把它当 0 参比会**必然假阳性**（实测：`MP3FreeDecoder` 被误报 0 参 vs 上游 1 参）。
      K&R 声明的调用点安全性由 `tools/scan_call_args.py`（按工厂反编译逐调用点对数）覆盖。
    """
    ps = split_params(params)
    variadic = any('...' in x for x in ps)
    ps = [x for x in ps if '...' not in x]
    if len(ps) == 0:
        return None                      # K&R / 不可知 ⇒ 不比较
    if len(ps) == 1 and ps[0] == 'void':
        ps = []
    isf = tuple(('float' in x and 'double' not in x) for x in ps)
    retf = ('float' in ret and 'double' not in ret)
    return (len(ps), isf, retf, variadic)


def parse_decls(text):
    """{函数名: [(元数, float掩码, 返回值float, 变参), ...]}；K&R 声明（返回 None）被丢弃。"""
    t = strip_comments(text)
    out = {}
    for m in DECL.finditer(t):
        ret, name, params = m.group(1), m.group(2), m.group(3)
        if name in ('if', 'while', 'for', 'switch', 'return', 'sizeof'):
            continue
        if '#' in ret:                      # 宏内的拼接
            continue
        sig = sig_of(ret, params)
        if sig is None:                     # K&R ⇒ 不可比较
            continue
        out.setdefault(name, []).append(sig)
    return out


def load_proto(root):
    p = os.path.join(root, 'src', 'compat', 'proto.h')
    return parse_decls(io.open(p, encoding='utf-8', errors='replace').read())


def load_upstream(root):
    up = {}
    for p in truth_headers(root):
        try:
            d = parse_decls(io.open(p, encoding='utf-8', errors='replace').read())
        except OSError:
            continue
        for n, sigs in d.items():
            up.setdefault(n, []).extend(sigs)
    return up


def first_float_ret(sig):
    return sig[2]


def compare(proto, up):
    """返回 [(name, proto_sig, up_sig)]，只报「元数 或 float 掩码 或 返回值 float 性」不同。"""
    bad = []
    for n, sigs in sorted(proto.items()):
        if n not in up:
            continue
        ps = sigs[0]
        # 上游对同一名字可能有多条（不同头文件的重载/不同版本），任一条与 proto 相容即算通过
        ok = False
        for us in up[n]:
            if us[0] == ps[0] and us[1] == ps[1] and us[2] == ps[2]:
                ok = True
                break
        if not ok:
            bad.append((n, ps, up[n][0]))
    return bad


def selfcheck(proto, up, root):
    """① 构造性：合成样本必须被判定不一致；② 状态感知：已修的 4 个 stbtt 必须不被报出。"""
    # ① 构造性
    fake_proto = {'zz_swap_probe_47': [(3, (False, True, True), False, False)]}
    fake_up = {'zz_swap_probe_47': [(3, (True, True, False), False, False)]}
    got = compare(fake_proto, fake_up)
    ok1 = len(got) == 1
    print('  [selfcheck-1] 构造性样本（float 掩码互换）-> %s' % ('被判定不一致 ✓' if ok1 else '未判定 ✗'))
    # ② 状态感知：已修的 4 个 stbtt 函数
    fixed = ['stbtt_ScaleForPixelHeight', 'stbtt_GetCodepointBitmapBoxSubpixel',
             'stbtt_MakeCodepointBitmapSubpixel', 'stbtt_GetCodepointHMetrics']
    bad_names = {n for n, _a, _b in compare(proto, up)}
    ok2 = True
    for n in fixed:
        if n in proto and n in up:
            state = '不一致 ✗' if n in bad_names else '一致 ✓'
            if n in bad_names:
                ok2 = False
            print('  [selfcheck-2] 已修项 %-36s -> %s' % (n, state))
        else:
            print('  [selfcheck-2] 已修项 %-36s -> （两侧未同时声明，跳过）' % n)
    if not (ok1 and ok2):
        sys.exit('  [FATAL] 自证失败 ⇒ 仪器不可信，拒绝出结论')


def fmt(sig):
    arity, mask, retf, var = sig
    return '%d 参 [%s]%s%s' % (arity, ''.join('f' if x else 'i' for x in mask),
                               ' ->float' if retf else ' ->int/void', ' ...' if var else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--ledger', default=None)
    ap.add_argument('--write-ledger', action='store_true')
    ap.add_argument('--top', type=int, default=30)
    a = ap.parse_args()
    root = a.root
    if not os.path.isdir(os.path.join(root, 'src', 'compat')):
        print('  [SKIP] 找不到 %s/src/compat' % root)
        return 0
    proto = load_proto(root)
    up = load_upstream(root)
    print('  proto.h 声明函数 %d 个；上游头文件提供真签名 %d 个；可比对 %d 个'
          % (len(proto), len(up), len(set(proto) & set(up))))
    selfcheck(proto, up, root)

    bad = compare(proto, up)
    print()
    print('  不一致 %d 个：' % len(bad))
    for n, ps, us in bad[:a.top]:
        print('     %-44s 我们 %-22s 上游 %s' % (n[:44], fmt(ps), fmt(us)))
    if len(bad) > a.top:
        print('     ...（共 %d 个）' % len(bad))

    names = [n for n, _a, _b in bad]
    if a.write_ledger:
        path = a.ledger or 'tools/proto_vs_upstream_pending.txt'
        with open(path, 'w', encoding='utf-8', newline=NL) as f:
            f.write('# 「proto.h 声明 vs 上游真签名」不一致台账（棘轮）。格式: <函数名>' + NL)
            f.write('# 逐项按上游头文件改正（顺序/类型/个数），改好一项**删一行**。' + NL)
            for n in names:
                f.write(n + NL)
        print()
        print('  已写入台账：%d 项（%s）' % (len(names), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend = set()
        for ln in io.open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                pend.add(ln)
        newv = [n for n in names if n not in pend]
        gone = sorted(pend - set(names))
        if gone:
            print()
            print('  ' + chr(0x2605) + ' 台账条目已消失（= 已改正）⇒ 请删行保持棘轮语义：%s' % gone[:8])
        if newv:
            print()
            print('  ' + chr(0x2605) + chr(0x2605) + ' 新增不一致 %d 个（不在台账内 ⇒ 判失败）：' % len(newv))
            for n, ps, us in [(x[0], x[1], x[2]) for x in bad if x[0] in newv][:a.top]:
                print('     %-44s 我们 %-22s 上游 %s' % (n[:44], fmt(ps), fmt(us)))
            return 1
        print()
        print('  [PASS] 无新增不一致（台账剩余 %d 项）' % len(pend))
        return 0

    if bad:
        print()
        print('  [FAIL] 存在 %d 个与上游真签名不一致的声明（未提供台账 ⇒ 从严判失败）' % len(bad))
        return 1
    print()
    print('  ✓ 与上游头文件真签名全部一致（元数 / float 掩码 / 返回值 float 性）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
