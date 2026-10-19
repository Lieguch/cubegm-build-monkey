#!/usr/bin/env python3
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

★ R202 事故留档：本文件曾因 `open(p,'w', newline='\\n')`（heredoc 把 \\n 变成字面
  两字符）触发 Python 参数校验失败，而 `'w'` 打开时**已当场截断**原文件 ⇒ 0 字节。
  纪律：改本仓文件一律用 Write/Edit 工具，或"写 .tmp → 校验 → os.replace"。

用法:
  from core_selector import CoreSelector
  cs = CoreSelector()
  r = cs.select_core("000/kof96.zip")
  r.status  # OK / AMBIGUOUS / NONE
  r.core    # "libemu_fbalpha2012.so"（OK 时）
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))

# 结果状态（显式三态，不用 None 混表达）
OK = 'OK'
AMBIGUOUS = 'AMBIGUOUS'
NONE = 'NONE'


class Result(object):
    __slots__ = ('status', 'core', 'candidates', 'layer', 'reason')

    def __init__(self, status, core=None, candidates=None, layer=None, reason=''):
        self.status = status
        self.core = core
        self.candidates = candidates or []
        self.layer = layer
        self.reason = reason

    def __repr__(self):
        if self.status == OK:
            return 'Result(OK, %s, layer=%s)' % (self.core, self.layer)
        if self.status == AMBIGUOUS:
            return 'Result(AMBIGUOUS, %d cands=%s)' % (len(self.candidates), self.candidates)
        return 'Result(NONE, %s)' % self.reason


def _load_tsv(path, cols):
    """读 TSV ⇒ list[dict]。文件不存在 ⇒ 显式报错（不静默返回空）。"""
    if not os.path.exists(path):
        raise IOError('缺数据文件: %s' % path)
    rows = []
    with open(path, encoding='utf-8') as f:
        header = f.readline().rstrip('\n').split('\t')
        assert header == cols, 'TSV 头不符: %s != %s' % (header, cols)
        for ln, line in enumerate(f, 2):
            line = line.rstrip('\n')
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) != len(cols):
                raise ValueError('%s:%d 列数 %d != %d' % (path, ln, len(parts), len(cols)))
            rows.append(dict(zip(cols, parts)))
    return rows


class CoreSelector(object):
    def __init__(self, root=None):
        root = root or ROOT
        # ① 逐 ROM 覆盖表（filelist.xml，最高优先）
        self.rom_map = {}
        for r in _load_tsv(os.path.join(root, 'tools', 'device_core_map.tsv'),
                           ['folder', 'rom', 'core']):
            self.rom_map['%s/%s' % (r['folder'], r['rom'])] = r['core']
        # ② 真机 GetCoreIndex 静态表（33 项，扩展名 → core **一对一**）
        self.ext_map = {}
        for r in _load_tsv(os.path.join(root, 'tools', 'device_getcoreindex_table.tsv'),
                           ['index', 'extension', 'core', 'flag_bit']):
            if r['core']:
                self.ext_map[r['extension'].upper()] = r['core']
        # ③ ROM 标识表（二进制内嵌，最低优先）
        self.rid_map = {}
        for r in _load_tsv(os.path.join(root, 'tools', 'device_romid_core_map.tsv'),
                           ['rom_id', 'core']):
            self.rid_map[r['rom_id'].upper()] = r['core']

    # ---------- 三层 ----------
    def _by_rom(self, rel):
        if rel in self.rom_map:
            return Result(OK, self.rom_map[rel], layer='filelist.xml')
        return None

    def _by_ext(self, rel):
        """② 按扩展名查真机 GetCoreIndex 表（R202：一对一，无歧义）。"""
        ext = rel.rsplit('.', 1)[-1].upper() if '.' in rel else ''
        core = self.ext_map.get(ext)
        if core:
            return Result(OK, core, layer='GetCoreIndex(ext=%s)' % ext)
        return None

    def _by_romid(self, rid):
        if rid and rid.upper() in self.rid_map:
            return Result(OK, self.rid_map[rid.upper()], layer='romid(%s)' % rid.upper())
        return None

    # ---------- 主入口 ----------
    def select_core(self, rel_path, rom_id=None):
        """rel_path 形如 "000/kof96.zip"（folder/rom）。

        rom_id 为可选（ROM 内部标识，3-4 大写）；不给则跳过第③层。
        """
        rel = rel_path.lstrip('/')
        r = self._by_rom(rel)
        if r:
            return r
        r = self._by_ext(rel)
        if r:
            return r
        r = self._by_romid(rom_id)
        if r:
            return r
        return Result(NONE, reason='三层均未命中: %s' % rel)


if __name__ == '__main__':
    # 人读自检：用真机 filelist.xml 里实际出现的 135 条逐条跑一遍，
    # 统计三层命中分布。这是**可复算**的验收，不是抽样。
    cs = CoreSelector()
    rows = _load_tsv(os.path.join(ROOT, 'tools', 'device_core_map.tsv'),
                     ['folder', 'rom', 'core'])
    stat = {OK: 0, AMBIGUOUS: 0, NONE: 0}
    layer_stat = {}
    mismatch = []
    for r in rows:
        res = cs.select_core('%s/%s' % (r['folder'], r['rom']))
        stat[res.status] += 1
        if res.status == OK:
            key = res.layer.split('(')[0]
            layer_stat[key] = layer_stat.get(key, 0) + 1
            # 第①层必须与 filelist.xml 声明的 core 一致（否则选择器错了）
            if res.core != r['core']:
                mismatch.append((r['folder'], r['rom'], r['core'], res.core))
    print('=== core_selector 自检（真机 135 条全量）===')
    print('总数 %d：OK=%d AMBIGUOUS=%d NONE=%d' % (
        len(rows), stat[OK], stat[AMBIGUOUS], stat[NONE]))
    print('命中层分布:', layer_stat)
    print('与 filelist.xml 声明不一致:', len(mismatch))
    for m in mismatch[:5]:
        print('   ★ %s/%s 声明=%s 选到=%s' % m)
    print()
    print('★ 判据：第①层必须 100% 命中且与 filelist.xml 声明**逐条一致**'
          '（不一致即选择器 bug，不是数据问题）')
    print('★ R202：第②层用真机 GetCoreIndex 33 项静态表（一对一），'
          '一对多场景已由真机表消除，不再报 AMBIGUOUS')
