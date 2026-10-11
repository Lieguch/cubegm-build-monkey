"""从**工厂 ELF 的 `.symtab`** 直接生成/补齐 `ledger/factory_globals.tsv`。

为什么需要这个工具（2026-10-05 第 138 轮）：
  台账 `ledger/factory_globals.tsv` 原本由 `tools/gen_factory_globals.py` 从
  **Ghidra 导出的 `symtab.txt`** 生成。但那份导出**不在仓库里**
  （`golden/ghidra-perfn.tar.gz` 只有 `03-per-function/*.c`，没有 symtab），
  ⇒ 台账无法重生成 ⇒ 新镜像段（如本轮补的 `.got`）在台账里**永远缺行**
  ⇒ `dup_sym_gate` 检查 1 报「这些对象没有任何判据在守它们」。

  ⇒ 权威来源应该是**工厂二进制自己的 `.symtab`**（ELF 标准，事实的最终出处），
     不该依赖某个中间导出文件是否还在。

行为：
  * `--fill`（默认）：只**补齐缺失行**，不改动已有行 ⇒ 幂等、不覆盖人工登记。
    已存在的行若内容与 ELF 不一致，**报出来但不静默改**（避免掩盖漂移）。
  * `--check`：只报告差异，rc=2 表示有差异（供 CI 用）。

判据口径：
  * 收 `.data` / `.rodata` / `.bss` / `.data.rel.ro*` / `.got` 这几个
    **被镜像覆盖**的数据段（与 `gen_data_module.SEC_DEF` 同源，见 `MIRRORED`）。
  * `size == 0` 的对象也收（`_GLOBAL_OFFSET_TABLE_` 就是 `size=0`）——
    只按「有名字 + 落在镜像段」判定，不按 size 过滤。
"""
import os
import sys

from elftools.elf.elffile import ELFFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, 'ledger', 'factory_globals.tsv')
FACTORY = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')

# 与 tools/gen_data_module.py 的 SEC_DEF 同源（被镜像覆盖的段）
MIRRORED = {'.text', '.rodata', '.data.rel.ro', '.data.rel.ro.local',
            '.data', '.got', '.bss'}

HEADER = 'name\taddr\tsize\tsection\tbind\ttype\tparent'


def read_ledger(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    import io
    with io.open(path, encoding='utf-8', errors='replace') as fh:
        head = fh.readline()
        if not head.startswith('name\t'):
            return rows
        for line in fh:
            f = line.rstrip('\n').split('\t')
            if len(f) < 4:
                continue
            rows[(f[0], f[1])] = f
    return rows


def elf_objects(path):
    """工厂 .symtab 里落在镜像段内的具名数据对象。"""
    out = {}
    with open(path, 'rb') as fh:
        e = ELFFile(fh)
        for s in e.get_section_by_name('.symtab').iter_symbols():
            if not s.name or s['st_value'] == 0:
                continue
            if s['st_info']['type'] not in ('STT_OBJECT', 'STT_TLS'):
                continue
            sh = s['st_shndx']
            if not isinstance(sh, int) or sh >= e.num_sections():
                continue
            sec = e.get_section(sh)
            if sec.name not in MIRRORED:
                continue
            out[(s.name, '%08x' % s['st_value'])] = [
                s.name, '%08x' % s['st_value'], '%08x' % s['st_size'],
                sec.name,
                {'STB_LOCAL': 'l', 'STB_GLOBAL': 'g', 'STB_WEAK': 'w'}.get(
                    s['st_info']['bind'], '?'),
                {'STT_OBJECT': 'O', 'STT_TLS': 'T'}.get(s['st_info']['type'], '?'),
                '',
            ]
    return out


def main():
    args = sys.argv[1:]
    check_only = '--check' in args
    elf_objects_map = elf_objects(FACTORY)
    led = read_ledger(LEDGER)

    missing = [(k, v) for k, v in sorted(elf_objects_map.items()) if k not in led]
    # 已存在但内容不一致（只报不改 —— 漂移要人来判）
    drift = []
    for k, v in sorted(elf_objects_map.items()):
        if k in led:
            old = led[k]
            for i, col in ((2, 'size'), (3, 'section'), (4, 'bind'), (5, 'type')):
                if old[i] != v[i]:
                    drift.append((k, col, old[i], v[i]))

    print('  工厂镜像段对象: %d  台账已有: %d  缺失: %d  内容漂移: %d'
          % (len(elf_objects_map), len(led), len(missing), len(drift)))
    for (name, addr), v in missing[:12]:
        print('    + %-28s @%s size=%s %s' % (name, addr, v[2], v[3]))
    if len(missing) > 12:
        print('    ... 还有 %d 条' % (len(missing) - 12))
    for (name, addr), col, oldv, newv in drift[:8]:
        print('    ! %-24s @%s %s: 台账=%s ELF=%s' % (name, addr, col, oldv, newv))

    if check_only:
        return 2 if (missing or drift) else 0
    if not missing:
        return 0
    import io
    lines = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding='utf-8', errors='replace') as fh:
            lines = fh.read().rstrip('\n').split('\n')
    have = set(led.keys())
    for (name, addr), v in missing:
        lines.append('\t'.join(v))
    tmp = LEDGER + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    os.replace(tmp, LEDGER)
    print('  已补齐 %d 行 → %s' % (len(missing), LEDGER))
    return 0


if __name__ == '__main__':
    sys.exit(main())
