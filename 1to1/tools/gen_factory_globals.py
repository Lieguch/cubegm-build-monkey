#!/usr/bin/env python3
"""
gen_factory_globals.py — 从工厂二进制符号表提取**权威全局布局**账本。

输入：`01-static/symtab.txt`（`nm -S` 风格，含 地址 / 绑定 / 类型 / 段 / 尺寸 / 名字）
输出：`ledger/factory_globals.tsv`（与 `ledger/factory_globals_report.txt`）

用途（P3 链接的数据段供应）：
  - 重建只产出**函数**，全局变量（.data/.rodata/.bss）需按工厂布局精确重建；
  - 本账本给出每个符号的权威 addr/size/section，且**识别别名关系**
    （小符号若落在更大符号的地址区间内，则它是该大对象的字段，必须以 alias 方式定义，
     否则链接期各占一份空间 → 破坏原厂内存布局与烧死在指令里的绝对地址）。

输出列（TAB）：
  name  addr  size  section  bind  type  parent
  其中 parent 非空 = 该符号是 parent 的字段（alias），不得独立分配空间。

用法:
  python3 tools/gen_factory_globals.py <symtab.txt> [out.tsv]
"""
import os
import re
import sys

# nm -S 行：地址(8) SP 绑定(1) SP 类型(1) SP 段名 TAB 尺寸(8) [可见性] 空格... 名字
# ★ 2026-09-25（GAP 17.13）：旧正则的名字段是 `(\S+)\s*$`，**遇到可见性前缀就整行不匹配**
#   ⇒ `003af004 l O .data 00000000 .hidden __dso_handle` 这类行被**静默丢弃**。
#   实测该形态共 16 行，其中落在**被镜像节区**的数据对象恰好 1 个（`__dso_handle`，`.data`）
#   —— 正是 `dup_sym_gate.py` 第一次实跑就报出来的那 1 条缺口。
RE_OBJ = re.compile(
    r'^([0-9a-f]{8})\s+([a-zA-Z ])\s*([a-zA-Z?])\s+(\S+)\s*\t([0-9a-f]{8})\s+'
    r'(?:\.(?:hidden|protected|internal)\s+)?(\S+)\s*$')
SEC_KEEP = ('.data', '.bss', '.rodata', '.data.rel.ro', '.data.rel.ro.local',
            '.init_array', '.fini_array')
# ★ 2026-09-25（GAP 17.13）：`.data.rel.ro.local` 曾经**不在白名单**里 ⇒ 该节 8 个 LOCAL
#   对象全部漏进不了账本。其中 `ArchivePath@0x3AE610` 与一个 GLOBAL 同名 ⇒ 生成器
#   （`gen_data_module.py` 的 `syms.setdefault` 首次命中）只能绑到 GLOBAL 0x3E18D4，
#   而工厂**代码引用的是 LOCAL 那个** ⇒ 真机读错内存（差分执行器实测：工厂读 0x3AE650、
#   我们读 0x3E1914，差值 0x32C4 = 0x3E18D4 − 0x3AE610 恰好相等）。
#   注意工厂的节名是 `.data.rel.ro.local`（带 `.local` 后缀）——旧白名单只写了
#   `.data.rel.ro`，**差一个后缀**，这正是漏掉整节的原因。


def parse(path):
    rows = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_OBJ.match(line.rstrip('\n'))
        if not m:
            continue
        addr, bind, typ, sec, size, name = m.groups()
        if sec not in SEC_KEEP:
            continue
        if typ not in ('O', 'o', 'R', 'r', 'B', 'b', 'D', 'd', 'V', 'v'):
            continue
        rows.append(dict(name=name, addr=int(addr, 16), size=int(size, 16),
                         section=sec, bind=bind, type=typ))
    return rows


def assign_parents(rows):
    """按地址升序扫描，把落在更大符号区间内的小符号标记为该大符号的字段(alias)。"""
    rs = sorted(rows, key=lambda r: (r['addr'], -r['size']))
    placed = []          # 已确定为「独立对象」的 (addr, end, name)
    for r in rs:
        parent = None
        for (a, e, n) in placed:
            if a < r['addr'] < e and r['addr'] + max(r['size'], 1) <= e:
                parent = n
                break
        r['parent'] = parent or ''
        if not parent and r['size'] > 0:
            placed.append((r['addr'], r['addr'] + r['size'], r['name']))
    return rows


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ledger', 'factory_globals.tsv')
    rows = assign_parents(parse(src))
    rows.sort(key=lambda r: r['addr'])

    os.makedirs(os.path.dirname(out), exist_ok=True)
    # ★ 2026-09-25：`newline='\n'` —— 旧代码在 Windows 上以文本模式写，账本成了 **CRLF**，
    #   而仓内其余生成物（factory_image.S / factory.ld / factory_local.S）都是 LF。
    #   后果：任何按行比较的工具（含 `_prediff`）会把整份文件报成"全行不同"，
    #   掩盖真实差异。此处统一为 LF（内容逐行等价，仅换行符变化）。
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('name\taddr\tsize\tsection\tbind\ttype\tparent\n')
        for r in rows:
            f.write('%s\t%08x\t%08x\t%s\t%s\t%s\t%s\n' % (
                r['name'], r['addr'], r['size'], r['section'],
                r['bind'], r['type'], r['parent']))

    secs = {}
    for r in rows:
        d = secs.setdefault(r['section'], [0, 0, 0])
        d[0] += 1
        d[1] += r['size']
        if not r['parent']:
            d[2] += 1
    aliases = [r for r in rows if r['parent']]

    L = []
    A = L.append
    A('=' * 66)
    A('工厂权威全局布局账本（来源：%s）' % os.path.basename(src))
    A('=' * 66)
    A('数据类符号总数 : %d' % len(rows))
    A('独立对象数     : %d' % (len(rows) - len(aliases)))
    A('别名字段数     : %d   ← 落在更大对象区间内，定义时必须 alias' % len(aliases))
    A('')
    A('%-14s %8s %10s %10s' % ('section', 'count', 'bytes', 'independent'))
    for s, (c, b, ind) in sorted(secs.items()):
        A('%-14s %8d %10d %10d' % (s, c, b, ind))
    A('')
    A('--- 别名样例（前 40，显示 字段 -> 父对象）---')
    for r in aliases[:40]:
        A('  %-24s @%08x size=%-6d -> %s' % (r['name'], r['addr'], r['size'], r['parent']))
    if len(aliases) > 40:
        A('  ... 共 %d 条' % len(aliases))
    A('')
    A('--- 最大独立对象（前 20）---')
    ind = [r for r in rows if not r['parent']]
    for r in sorted(ind, key=lambda x: -x['size'])[:20]:
        A('  %-24s @%08x size=%-8d %s' % (r['name'], r['addr'], r['size'], r['section']))
    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    rep = out.replace('.tsv', '_report.txt')
    open(rep, 'w', encoding='utf-8').write(txt)
    sys.stderr.write('ledger -> %s\nreport -> %s\n' % (out, rep))
    return 0


if __name__ == '__main__':
    sys.exit(main())
