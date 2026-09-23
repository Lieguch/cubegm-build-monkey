#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fidelity_compare —— 把「同一份源码、不同编译器」的产物与**工厂**逐函数对拍。

回答的问题（单向、可判定）
--------------------------
「换成与原厂同族的 GCC，机器码会不会**更接近**工厂？」——这是 ROUTE-DECISION §五④ 的判决实验。
本工具不回答"能不能跑"，只给出**形状距离**的两个可复核刻度：

  M1 体积比 r = ours/factory，报告：±15% 命中数 / 精确到字节数 / 中位数
     （★ 声明：体积比**不是功能进度尺**（GAP 16.43），但作为"两个编译器在完全相同条件下谁更像工厂"
       的**相对**判据是合法的 —— 它比较的是同一条输入、同一组判据。）
  M2 指令助记符直方图的 L1 距离（归一化后），越小越像
     —— 比体积比更结构化：能区分"同样大但指令种类不同"。

两侧都用**同一个反汇编器**（`tools/arm_dis.py`）与**同一份工厂数据**，避免口径漂移。

用法：
    python tools/fidelity_compare.py --set clang=build/obj --set gcc=build/gcc_obj
    python tools/fidelity_compare.py --set clang=build/obj --selftest
exit: 0=正常出数 / 11=仪器不可用
"""
import argparse
import gzip
import importlib.util
import io
import json
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_ad():
    spec = importlib.util.spec_from_file_location(
        'ad', os.path.join(ROOT, 'tools', 'arm_dis.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def factory_data():
    """返回 (sizes{name:size}, hist{name:{mnem:cnt}})。"""
    p = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
    sizes = {}
    if os.path.exists(p):
        d = open(p, 'rb').read()
        es = struct.unpack_from('<H', d, 46)[0]
        sh = struct.unpack_from('<I', d, 32)[0]
        n = struct.unpack_from('<H', d, 48)[0]
        SH = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
        for s in SH:
            if s[1] != 2:
                continue
            stro = SH[s[6]][4]
            ent = s[9] or 16
            for j in range(s[5] // ent):
                nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
                if nmn == 0 or (inf & 0xF) != 2 or sz == 0 or shx == 0:
                    continue
                k = d.index(b'\x00', stro + nmn)
                sizes.setdefault(d[stro + nmn:k].decode('utf-8', 'replace'), sz)
    hist = {}
    fp = os.path.join(ROOT, 'golden', 'factory.funcs.json')
    fg = fp + '.gz'
    if os.path.exists(fp):
        F = json.load(io.open(fp, encoding='utf-8'))['functions']
    elif os.path.exists(fg):
        F = json.loads(gzip.open(fg, 'rb').read().decode())['functions']
    else:
        raise IOError('缺 factory.funcs.json(.gz)')
    for nm, t in F.items():
        h = {}
        for x in t.get('t1', []):
            s = x.strip()
            if not s or s.startswith('.word'):
                continue
            m = re.match(r'^([a-zA-Z][\w\.]*)', s)
            if m:
                h[m.group(1)] = h.get(m.group(1), 0) + 1
        if h:
            hist[nm] = h
    return sizes, hist


def obj_sizes(d):
    """目录下所有 .o 的函数 (名字 → 字节数)。"""
    out = {}
    if not os.path.isdir(d):
        return out
    for f in os.listdir(d):
        if not f.endswith('.o'):
            continue
        p = os.path.join(d, f)
        try:
            b = open(p, 'rb').read()
            es = struct.unpack_from('<H', b, 46)[0]
            sh = struct.unpack_from('<I', b, 32)[0]
            n = struct.unpack_from('<H', b, 48)[0]
            SH = [struct.unpack_from('<10I', b, sh + i * es) for i in range(n)]
        except Exception:
            continue
        for s in SH:
            if s[1] != 2:
                continue
            stro = SH[s[6]][4]
            ent = s[9] or 16
            for j in range(s[5] // ent):
                nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', b, s[4] + j * ent)
                if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                    continue
                k = b.index(b'\x00', stro + nmn)
                nm = b[stro + nmn:k].decode('utf-8', 'replace')
                out.setdefault(nm, sz)
    return out


def obj_hist(d, ad):
    """目录下所有 .o 里每个函数的助记符直方图（同一个反汇编器）。"""
    out = {}
    if not os.path.isdir(d):
        return out
    class E:
        pass
    e = E()
    for f in sorted(os.listdir(d)):
        if not f.endswith('.o'):
            continue
        p = os.path.join(d, f)
        b = open(p, 'rb').read()
        es = struct.unpack_from('<H', b, 46)[0]
        sh = struct.unpack_from('<I', b, 32)[0]
        n = struct.unpack_from('<H', b, 48)[0]
        SH = [struct.unpack_from('<10I', b, sh + i * es) for i in range(n)]
        e.d = b
        for s in SH:
            if s[1] != 2:
                continue
            stro = SH[s[6]][4]
            ent = s[9] or 16
            for j in range(s[5] // ent):
                nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', b, s[4] + j * ent)
                if nmn == 0 or (inf & 0xF) != 2 or sz == 0 or shx == 0:
                    continue
                k = b.index(b'\x00', stro + nmn)
                nm = b[stro + nmn:k].decode('utf-8', 'replace')
                # ★ `st_shndx` 是 **1 基**的节头表索引（0 = SHN_UNDEF）⇒ 直接 SH[shx]，
                #   写成 SH[shx-1] 会取到空节（flags=0）⇒ 所有函数被跳过、直方图为空（假绿）。
                if shx >= len(SH):
                    continue
                sec = SH[shx]
                if not (sec[2] & 4):          # 只取可执行节
                    continue
                off = sec[4] + (val - sec[3]) if sec[3] <= val < sec[3] + sec[5] else sec[4]
                h = {}
                for q in range(0, min(sz, sec[5]), 4):
                    if off + q + 4 > len(b):
                        break
                    w = struct.unpack_from('<I', b, off + q)[0]
                    try:
                        txt = ad.dec(w, val + q, e)[0]
                    except Exception:
                        txt = None
                    if not txt:
                        continue
                    m = re.match(r'^([a-zA-Z][\w\.]*)', txt.strip())
                    if m:
                        h[m.group(1)] = h.get(m.group(1), 0) + 1
                if h:
                    out[nm] = h
    return out


def l1(a, b):
    """两个计数直方图归一化后的 L1 距离（0=完全相同）。"""
    sa, sb = sum(a.values()), sum(b.values())
    if not sa or not sb:
        return None
    keys = set(a) | set(b)
    return sum(abs(a.get(k, 0) / sa - b.get(k, 0) / sb) for k in keys)


def evaluate(name, sizes, hist, fsizes, fhist, verbose=True):
    common = [k for k in fsizes if k in sizes]
    if not common:
        print('  [%s] ★ 无可比函数 —— 仪器不可用' % name)
        return None
    exact = within15 = 0
    ratios = []
    for k in common:
        r = sizes[k] / float(fsizes[k])
        ratios.append(r)
        if sizes[k] == fsizes[k]:
            exact += 1
        if 0.85 <= r <= 1.18:
            within15 += 1
    ratios.sort()
    med = ratios[len(ratios) // 2]
    # 直方图距离（只对有共同反汇编的）
    dists = []
    for k in common:
        if k in fhist and k in hist:
            d = l1(hist[k], fhist[k])
            if d is not None:
                dists.append(d)
    dists.sort()
    dmed = dists[len(dists) // 2] if dists else float('nan')
    if verbose:
        print('  [%-8s] 可比函数 %3d  精确 %3d (%4.1f%%)  ±15%% %3d (%4.1f%%)  中位比 %.3f  '
              '直方图L1 中位 %.3f (n=%d)'
              % (name, len(common), exact, 100.0 * exact / len(common),
                 within15, 100.0 * within15 / len(common), med, dmed, len(dists)))
    return dict(n=len(common), exact=exact, within15=within15,
                med=med, dmed=dmed, dists=dists)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', action='append', default=[],
                    help='name=dir，可多次；dir 里是同一份源码用某编译器编出的 *.o')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if not a.set:
        print('  用法: fidelity_compare.py --set clang=build/obj --set gcc=build/gcc_obj')
        return 11
    try:
        fsizes, fhist = factory_data()
    except Exception as e:
        print('  ★ 读不到工厂数据：%s —— 硬失败（不允许退化成"没有基准也能比"）' % e)
        return 11
    if not fsizes:
        print('  ★ 工厂符号表为空 —— 硬失败')
        return 11
    print('  [基准] 工厂函数 %d 个（有 size）/ 有反汇编 %d 个' % (len(fsizes), len(fhist)))
    try:
        ad = load_ad()
    except Exception as e:
        print('  ★ 反汇编器不可用：%s —— 硬失败' % e)
        return 11

    res = {}
    for spec in a.set:
        if '=' not in spec:
            print('  ★ --set 需要 name=dir 形式：%s' % spec)
            return 11
        nm, d = spec.split('=', 1)
        d = d if os.path.isabs(d) else os.path.join(ROOT, d)
        if not os.path.isdir(d):
            print('  ★ 目录不存在：%s —— 硬失败' % d)
            return 11
        s = obj_sizes(d)
        h = obj_hist(d, ad)
        print('  [%-8s] .o 解析：函数 %d 个 / 有反汇编 %d 个' % (nm, len(s), len(h)))
        res[nm] = evaluate(nm, s, h, fsizes, fhist)

    if a.selftest:
        print()
        print('  ---- 自证：把"工厂自己"当输入 ⇒ 体积比必须全 1.0、直方图距离必须 0 ----')
        ok = True
        for nm, r in res.items():
            if r is None:
                ok = False
        if len(res) < 2:
            print('  · 自证需要 ≥2 个 --set 才能对比；此处先做"跨集一致性"检查')
        # 直接对拍工厂自身
        self_r = evaluate('self', fsizes, fhist, fsizes, fhist)
        if self_r['med'] != 1.0 or abs(self_r['dmed']) > 1e-9:
            print('  [!!] 自证失败：工厂自比中位比=%.6f 距离=%.6f ⇒ 判据有假偏差'
                  % (self_r['med'], self_r['dmed']))
            return 11
        print('  ✓ 自证通过：工厂自比 中位比=1.000、直方图距离=0.000')

    print()
    print('  ---- 结论 ----')
    names = [n for n in res if res[n]]
    if len(names) >= 2:
        a0, b0 = names[0], names[1]
        ra, rb = res[a0], res[b0]
        better = []
        better.append('±15%% 命中：%s %.1f%% vs %s %.1f%%'
                      % (a0, 100.0 * ra['within15'] / ra['n'],
                         b0, 100.0 * rb['within15'] / rb['n']))
        better.append('中位体积比：%s %.3f vs %s %.3f（越接近 1.000 越好）'
                      % (a0, ra['med'], b0, rb['med']))
        better.append('直方图 L1 中位：%s %.3f vs %s %.3f（越小越好）'
                      % (a0, ra['dmed'], b0, rb['dmed']))
        for x in better:
            print('    ' + x)
    return 0


if __name__ == '__main__':
    sys.exit(main())
