#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R202 补丁：core_selector.py 第②层改用真机 GetCoreIndex 33 项静态表。"""
import io

P = 'tools/core_selector.py'
s = io.open(P, encoding='utf-8').read()

# 1) 文件头说明整体替换
head_end = s.index('import os')
NEW_HEAD = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core_selector.py —— rkgame core 选择器（R197 建 / R202 定稿）

三层权威数据（全部来自真机实测，不得用上游 SF3000 cores.md 代替）：
  ① `tools/device_core_map.tsv`             135 条，逐 ROM 文件覆盖（最高优先）
  ② `tools/device_getcoreindex_table.tsv`   33 条，**真机 `GetCoreIndex` 静态表**
     （`golden/factory.rkgame.bin` 的 `.data` 0x3b0254 起，68 B/项：
      扩展名在 +0x00、位标志在 +0x20、core 名在 +0x24）
     —— R202 定案：这是真机**实际运行**的"扩展名→core"权威映射，一对一，无歧义。
  ③ `tools/device_romid_core_map.tsv`       30 条，ROM 标识（二进制内嵌，最低优先）

★ R202 关键修正：第②层原用 `config.xml` 派生的 28 扩展名表（一对多、需报歧义），
  但反汇编 + `.data` 提取证明**真机运行的是另一份独立的 33 项静态表**：
    · SMC/FIG/SFC/GD3/GD7/DX2/BSX/SWC → `libemu_sfc.so`（不选 snes9x/snes9x2010）
    · NES → `libemu_nes.so`（不选 nestopia）
    · GBC/GB/SGB → `libemu_tgbdual.so`（不选 mgba）
    · BIN/MD/SMD/GEN/SMS → `libemu_md.so`
    · **GBA → `libemu_gpsp.so`**（而 config.xml 里 GBA 只有 mgba/vbam ⇒ 两表不同源）
    · BKP/ZIP 的 core 为空 ⇒ 不经此表（ZIP 需先解压看内部文件）
  ⇒ `config.xml` **不是**运行时权威（可能是菜单显示用或已过时）；真机表才是。

算法（`select_core`）：
  ① filelist.xml 命中 ⇒ 直接返回（逐 ROM 覆盖，最高优先）
  ② 按扩展名查真机 `GetCoreIndex` 表（**一对一，无歧义**）
  ③ 按 ROM 标识查二进制内嵌表
  ④ 都没有 ⇒ NONE（如实报"无"，不猜）

★ 判据纪律（本项目反复强调）：
  · "无法确定"与"确定"必须分开（AMBIGUOUS / NONE 是独立结果，不是异常）；
  · 所有数据来自 TSV，本文件不写死任何 core 名。

用法:
  from core_selector import CoreSelector
  cs = CoreSelector()
  r = cs.select_core("000/kof96.zip")
  r.status  # OK / AMBIGUOUS / NONE
  r.core    # "libemu_fbalpha2012.so"（OK 时）
"""
'''
s = NEW_HEAD + s[head_end:]

# 2) __init__ 数据源
OLD_INIT = """        # ② 扩展名表（一个扩展名 → 多 core，保留全部候选）
        self.ext_map = {}
        for r in _load_tsv(os.path.join(root, 'tools', 'device_ext_core_map.tsv'),
                           ['core_name', 'core_file', 'extension']):
            self.ext_map.setdefault(r['extension'].upper(), set()).add(r['core_file'])"""
NEW_INIT = """        # ② 真机 GetCoreIndex 静态表（33 项，扩展名 → core **一对一**）
        #   ★ R202：取代原先 config.xml 派生的多对多表 —— 真机运行的是这份。
        self.ext_map = {}
        for r in _load_tsv(os.path.join(root, 'tools', 'device_getcoreindex_table.tsv'),
                           ['index', 'extension', 'core', 'flag_bit']):
            if r['core']:
                self.ext_map[r['extension'].upper()] = r['core']"""
if OLD_INIT not in s:
    raise SystemExit('INIT anchor not found')
s = s.replace(OLD_INIT, NEW_INIT)

# 3) _by_ext 改一对一
i0 = s.index('    def _by_ext(self, rel):')
i1 = s.index('    def _by_romid(self, rid):')
NEW_EXT = '''    def _by_ext(self, rel):
        """② 按扩展名查真机 GetCoreIndex 表（R202：一对一，无歧义）。

        真机表在 .data 静态存在，每扩展名唯一一个 core（BKP/ZIP 两项 core 为空
        ⇒ 不经此表，落到③/④）。
        """
        ext = rel.rsplit('.', 1)[-1].upper() if '.' in rel else ''
        core = self.ext_map.get(ext)
        if core:
            return Result(OK, core, layer='GetCoreIndex(ext=%s)' % ext)
        return None

'''
s = s[:i0] + NEW_EXT + s[i1:]

# 4) 自检段补说明
OLD_TAIL = """    print('★ 判据：第①层必须 100% 命中且与 filelist.xml 声明**逐条一致**'
          '（不一致即选择器 bug，不是数据问题）')"""
NEW_TAIL = """    print('★ 判据：第①层必须 100% 命中且与 filelist.xml 声明**逐条一致**'
          '（不一致即选择器 bug，不是数据问题）')
    print('★ R202：第②层用真机 GetCoreIndex 33 项静态表（一对一），'
          '一对多场景已由真机表消除，不再报 AMBIGUOUS')"""
if OLD_TAIL in s:
    s = s.replace(OLD_TAIL, NEW_TAIL)

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('patched core_selector.py')
