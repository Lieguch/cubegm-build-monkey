#!/usr/bin/env python3
"""
funcdump.py — 从 objdump -d 文本提取「逐函数归一化指令序列」。

用途：作为 1:1 重构的差分验证地基。
  - 对原厂 rkgame 反汇编 → 生成金标准参照集 (golden)
  - 对重建产物反汇编   → 生成候选集 (candidate)
  - 由 funcdiff.py 对比两者，输出函数级等价覆盖率

归一化目标：消除「地址布局差异」，保留「语义差异」。
  1. 函数头      00009b58 <main>:                -> 函数边界
  2. 指令行          9b58:\te59f01b0\tldr\tr0, [pc, #432]\t; 9d10 <main+0x1b8>
  3. 分支/引用目标  9d10 <main+0x1b8>             -> @main+0x1b8   (符号化)
                   9a90 <pthread_getspecific@plt>-> @pthread_getspecific@plt
   绝对地址 0x003a81d8 保留原值（.word 数据，语义相关）

输出 JSON：
  {
    "functions": { name: { "addr": "0x9b58", "n": 42,
                           "t1": [ "ldr r0, @main+0x1b8", ... ],   # 归一化后完整指令
                           "t2": [ "ldr", "push", ... ],           # 仅助记符
                           "b":  7 } },                            # 分支/调用数
    "labels": { "0x9b58": "main", ... }
  }
"""
import re, sys, json

RE_FUNC = re.compile(r'^([0-9a-f]{8,16}) <([^>]+)>:\s*$')
RE_INST = re.compile(r'^\s*([0-9a-f]+):\s+([0-9a-f]{8})\s+(\S+)\s*(.*)$')
RE_REF  = re.compile(r'([0-9a-f]{4,16}) <([^>]+)>')


def build_labels(text):
    """地址 -> 符号名（取第一个出现的，即函数定义处的名字）。"""
    labels = {}
    for ln in text.splitlines():
        m = RE_FUNC.match(ln)
        if m:
            labels.setdefault(int(m.group(1), 16), m.group(2))
    return labels


def symbolize(operands, labels):
    """把 '9d10 <main+0x1b8>' 归一化成 '@main+0x1b8'。"""
    def rep(m):
        addr = int(m.group(1), 16)
        sym = m.group(2).split('+')[0]
        off = m.group(2)[len(sym):]          # '+0x1b8' 或 ''
        # 优先用 objdump 给的符号名；若缺失则回落到 labels 表
        if not sym or sym.startswith('0x'):
            sym = labels.get(addr, '0x%x' % addr)
            off = ''
        return '@' + sym + off
    return RE_REF.sub(rep, operands or '')


def strip_comment(operands):
    """去掉 objdump 的 '; ...' 尾注释（其内容已由 ref 归一化吸收）。"""
    if not operands:
        return ''
    i = operands.find(';')
    return (operands[:i] if i >= 0 else operands).strip()


def parse(text):
    labels = build_labels(text)
    funcs = {}
    cur = None
    for ln in text.splitlines():
        m = RE_FUNC.match(ln)
        if m:
            cur = m.group(2)
            funcs[cur] = {'addr': '0x' + m.group(1).lstrip('0') or '0x0',
                          'n': 0, 't1': [], 't2': [], 'b': 0}
            continue
        m = RE_INST.match(ln)
        if not m or cur is None:
            continue
        mnem, operands = m.group(3), m.group(4) or ''
        operands = strip_comment(operands)
        ops_norm = symbolize(operands, labels)
        full = (mnem + ' ' + ops_norm).strip() if ops_norm else mnem
        entry = funcs[cur]
        entry['t1'].append(full)
        entry['t2'].append(mnem)
        entry['n'] += 1
        if mnem.startswith('b') or mnem in ('bl', 'blx', 'bx', 'cbz', 'cbnz') \
           or mnem.startswith('bl') or mnem.startswith('push') or mnem.startswith('pop'):
            if mnem != 'push' and mnem != 'pop':
                entry['b'] += 1
    return {'functions': funcs,
            'labels': {('0x%x' % k): v for k, v in sorted(labels.items())}}


def main():
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding='utf-8', errors='replace').read()
    out = parse(text)
    json.dump(out, open(dst, 'w', encoding='utf-8'), indent=0, ensure_ascii=False)
    nf = len(out['functions'])
    ni = sum(f['n'] for f in out['functions'].values())
    print('parsed %d functions / %d instructions -> %s' % (nf, ni, dst))


if __name__ == '__main__':
    main()
