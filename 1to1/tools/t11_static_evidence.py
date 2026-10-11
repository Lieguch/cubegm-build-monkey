#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""t11_static_evidence.py —— T11 的**静态判据集**（不依赖 qemu / 不依赖设备）

★ 为什么要有这个（第 138/139 轮的方向决策）：
  T11 原本想用「模拟启动链的运行时行为」验收，但第 138 轮已取证：
  **qemu 环境与工厂自相矛盾**（同一 sysroot 下工厂侧 `exit=1`/`Exec format error`，
  我方侧正常加载并跑出 51274 条 syscall）⇒ 运行时里程碑**不能作为 1:1 的验收标准**，
  只能当参考。
  ⇒ T11 改为「**静态事实 + 布局对齐**」验收：每一条都是**可逐位比对的硬事实**，
     不受 qemu 版本、容器重建、宿主环境影响。

判据清单（每条都必须 PASS；任何一条 FAIL 即整体 FAIL，不允许 SKIP）：

  E1  指针表逐位一致      globals.h 的 279 个 PTR_* 在产物中与工厂逐位相同
  E2  GOT 槽正确          GOT 区（工厂 .got）非零槽数与工厂一致
  E3  数据对象地址绑定    被镜像节区的每个工厂对象，我方同名符号同址
  E4  key2 语义同构      unzlocal_SearchCentralDir 的签名来源与工厂机器码一致
  E5  SD 卡必备资源在位   font.ttf / ui_cn.zip / cores/filelist.xml 存在且非空
  E6  符号账本无漂移      gen_ledger_from_elf.py --check

★ 反假绿纪律（E1/E2 的教训）：
  「读不到」**不等于**「一致」。本脚本任何一条在**证据缺失**时报 **FAIL**，
  并写明「这是没测到，不是一致」—— 与 tools/behav_diff.py 的 B6 口径一致。

用法：
    python3 tools/t11_static_evidence.py                # 人读
    python3 tools/t11_static_evidence.py --json         # 机读
退出码：0=全 PASS，1=有 FAIL，2=证据缺失（同样算不通过）
"""

from __future__ import print_function

import argparse
import io
import json
import os
import re
import struct
import sys

OURS = 'build/rkgame.rebuilt.elf'
FAC = 'golden/factory.rkgame.bin'
GH = 'src/compat/globals.h'
SDCARD = 'golden/sdcard_min'

# 工厂 .got 段（地址/长度取自工厂节表，见 ledger/factory_layout.tsv）
FAC_GOT_ADDR = 0x3B1CFC
FAC_GOT_SIZE = 0x478

# T11 关心的 SD 卡资源：(相对路径, 最小字节数)
SDCARD_FILES = [
    ('font.ttf', 100000),
    ('ui_cn.zip', 10000),
    ('cores/filelist.xml', 100),
]

# 必须在 **ui_cn.zip 内部**的资源（实测：SD 卡根目录没有 ui.cfg，它在 zip 里）
SDCARD_ZIP_ENTRIES = ['ui.cfg']

results = []


def add(name, ok, detail, evidence_missing=False):
    results.append({'name': name, 'ok': bool(ok),
                    'missing': bool(evidence_missing), 'detail': detail})


def read_at(elf, va, n=4):
    for s in elf.iter_sections():
        if s['sh_type'] == 'SHT_PROGBITS' and s['sh_addr'] <= va < s['sh_addr'] + s['sh_size']:
            d = s.data()
            return d[va - s['sh_addr']: va - s['sh_addr'] + n]
    return None


def e1_ptr_table(elf, fac):
    """E1: globals.h 的 PTR_* 逐位一致。"""
    if not os.path.exists(GH):
        add('E1 PTR_* 逐位一致', False, 'globals.h 不存在', True)
        return
    t = io.open(GH, encoding='utf-8', errors='replace').read()
    pairs = re.findall(r'/\* @(0x[0-9a-fA-F]+) pointer \*/\s*extern\s+\S+\s*\*\s*(PTR_\w+)\s*;', t)
    if not pairs:
        add('E1 PTR_* 逐位一致', False, 'globals.h 里没解析到 PTR_* 声明', True)
        return
    ok = bad = miss = 0
    bads = []
    for a, nm in pairs:
        va = int(a, 16)
        x, y = read_at(elf, va), read_at(fac, va)
        if x is None or y is None:
            miss += 1
            continue
        if x == y:
            ok += 1
        else:
            bad += 1
            if len(bads) < 4:
                bads.append('%s@%s ours=%#010x fac=%#010x'
                            % (nm, a, struct.unpack('<I', x)[0], struct.unpack('<I', y)[0]))
    detail = '共 %d 条：一致 %d / 不一致 %d / 读不到 %d' % (len(pairs), ok, bad, miss)
    if bads:
        detail += '；差异样本：' + '; '.join(bads)
    # 「读不到」也算不通过（反假绿）
    add('E1 PTR_* 逐位一致', ok == len(pairs) and miss == 0, detail, miss > 0 and bad == 0)


def e2_got_slots(elf, fac):
    """E2: GOT 区非零槽数一致。"""
    def nz(x, lo, hi):
        c = 0
        for va in range(lo, hi, 4):
            b = read_at(x, va)
            if b and struct.unpack('<I', b)[0] != 0:
                c += 1
        return c
    lo, hi = FAC_GOT_ADDR, FAC_GOT_ADDR + FAC_GOT_SIZE
    a, b = nz(elf, lo, hi), nz(fac, lo, hi)
    add('E2 GOT 非零槽数一致', a == b and b > 0,
        '我方 %d / 工厂 %d（区间 [%#x,%#x) 共 %d 槽）'
        % (a, b, lo, hi, (hi - lo) // 4), a == 0 and b == 0)


def e3_data_binding(elf, fac):
    """E3: 被镜像节区的工厂对象，我方同名符号同址。"""
    # 复用 dup_sym_gate 的检查 3 判据：直接调它，避免同一规则写两处
    import subprocess
    try:
        rc = subprocess.call([sys.executable, 'tools/dup_sym_gate.py'],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as ex:
        add('E3 数据对象地址绑定', False, '无法运行 dup_sym_gate.py：%s' % ex, True)
        return
    add('E3 数据对象地址绑定', rc == 0, 'dup_sym_gate rc=%d（0=948 对象全落工厂地址）' % rc)


def e4_key2_semantics():
    """E4: key2 语义同构 —— 判据是「源码用的全局名/地址与工厂一致」。"""
    src = 'src/upstream/xunzip/unzip.cpp'
    if not os.path.exists(src):
        add('E4 key2 语义同构', False, '%s 不存在' % src, True)
        return
    t = io.open(src, encoding='utf-8', errors='replace').read()
    problems = []
    if 'extern unsigned char key2[28]' not in t:
        problems.append('未声明 key2[28]（工厂 symtab: val=0x3e190c size=28）')
    # 工厂比对 key2[4..7] 或 key2[0..3] 两组 4 字节（反编译 F59..F78）
    if 'key2[4]' not in t or 'key2[0]' not in t:
        problems.append('未同时比对 key2[0..3] 与 key2[4..7]（工厂是两个 4 字节签名）')
    # 工厂 F16/F18：movw r3,#65534 ; cmp r5,r3 ⇒ 阈值字面量是 0xfffe（不是标准版 0xffff）。
    # ★ 判据只认**字面量本身**，不限定写法（`0xfffe` / `65534` 都对）——
    #   上一版写成查 '0x0fffe'（多一个 0）⇒ 恒判 FAIL，是判据自身的错，已修。
    if '0xfffe' not in t.replace(' ', '') and '65534' not in t:
        problems.append('uMaxBack 阈值既无 0xfffe 也无 65534'
                        '（工厂 F16/F18 用 65534，非标准版 0xffff）')
    add('E4 key2 语义同构', not problems,
        '；'.join(problems) if problems else
        'key2 声明/两组签名/0xfffe 阈值 均与工厂一致')


def e5_sdcard_files():
    """E5: 必备资源在位 —— SD 卡根目录 + ui_cn.zip 内部条目。

    ★ 第 139 轮修正：初版把 `ui.cfg` 当成 SD 卡根目录下的文件，
      实测**根目录没有 ui.cfg**（它在 ui_cn.zip 内）⇒ 那是判据自身的事实错误，
      不是资源缺失。已改为「根目录文件」+「zip 内条目」两段分别判。
    """
    rows = []
    ok = True
    missing = False
    for rel, minsz in SDCARD_FILES:
        p = os.path.join(SDCARD, rel)
        if not os.path.exists(p):
            rows.append('%s ★缺' % rel)
            ok = False
            missing = True
            continue
        sz = os.path.getsize(p)
        if sz < minsz:
            rows.append('%s %d B < %d B' % (rel, sz, minsz))
            ok = False
        else:
            rows.append('%s %d B' % (rel, sz))
    # zip 内条目
    zp = os.path.join(SDCARD, 'ui_cn.zip')
    if os.path.exists(zp):
        try:
            import zipfile
            names = zipfile.ZipFile(zp).namelist()
            for want in SDCARD_ZIP_ENTRIES:
                hit = [n for n in names if want in n]
                if hit:
                    rows.append('zip:%s ✓' % hit[0])
                else:
                    rows.append('zip:%s ★不在 zip 内（共 %d 项）' % (want, len(names)))
                    ok = False
                    missing = True
        except Exception as ex:                      # noqa: BLE001
            rows.append('zip 读取失败：%s' % ex)
            ok = False
            missing = True
    add('E5 SD 卡资源在位', ok, '；'.join(rows), missing)


def e6_ledger():
    """E6: 符号账本无漂移（调权威工具，不重述其规则）。"""
    import subprocess
    if not os.path.exists('tools/gen_ledger_from_elf.py'):
        add('E6 符号账本无漂移', False, 'gen_ledger_from_elf.py 不存在', True)
        return
    try:
        rc = subprocess.call([sys.executable, 'tools/gen_ledger_from_elf.py', '--check'],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except OSError as ex:
        add('E6 符号账本无漂移', False, '无法运行：%s' % ex, True)
        return
    add('E6 符号账本无漂移', rc == 0, 'gen_ledger_from_elf.py --check rc=%d' % rc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    from elftools.elf.elffile import ELFFile
    for p in (OURS, FAC):
        if not os.path.exists(p):
            print('★ 缺少 %s —— 这是「没测到」，不是「一致」' % p)
            return 2
    elf = ELFFile(open(OURS, 'rb'))
    fac = ELFFile(open(FAC, 'rb'))

    e1_ptr_table(elf, fac)
    e2_got_slots(elf, fac)
    e3_data_binding(elf, fac)
    e4_key2_semantics()
    e5_sdcard_files()
    e6_ledger()

    nfail = sum(1 for r in results if not r['ok'])
    nmiss = sum(1 for r in results if r['missing'])
    if args.json:
        print(json.dumps({'results': results, 'fail': nfail, 'missing': nmiss},
                         ensure_ascii=False, indent=2))
    else:
        print('=' * 78)
        print('T11 静态判据集（不依赖 qemu / 不依赖设备）')
        print('=' * 78)
        for r in results:
            mark = 'PASS' if r['ok'] else ('MISS' if r['missing'] else 'FAIL')
            print('[%s] %-24s %s' % (mark, r['name'], r['detail']))
        print('-' * 78)
        print('汇总：%d 条，PASS %d / FAIL %d（其中证据缺失 %d）'
              % (len(results), len(results) - nfail, nfail, nmiss))
        if nfail:
            print('★ 不通过。注意：证据缺失也算不通过（反假绿纪律）。')
    return 1 if nfail else 0


if __name__ == '__main__':
    sys.exit(main())
