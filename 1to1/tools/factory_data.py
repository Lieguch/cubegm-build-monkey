#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""factory_data —— 工厂反汇编数据的**唯一**加载入口（消除"有的工具只找 .json"这类复发坑）。

背景（真实教训，出现过两次）：
  · 本地同时有 `golden/factory.funcs.json`（21 MB，未压缩，**不入库**）
    与 `golden/factory.funcs.json.gz`（3.67 MB，**入库**，CI 只有这一份）。
  · 任何"只找 .json"的工具会**本地绿、CI 红**：`prop_equiv.py` 首跑 CI 就因此失败过；
    2026-09-23 `mmio_width_audit.py` 又犯一次（1to1-qemu-behav exit 15）。
  ⇒ 规矩：**凡读这份数据，一律用本模块**，不要自己拼路径。

用法：
    from factory_data import load_factory_funcs
    F = load_factory_funcs()          # dict: 函数名 -> {'t1': [...], 'addr': ..., ...}
"""
import gzip
import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BASE = os.path.join(ROOT, 'golden', 'factory.funcs.json')


def factory_funcs_path():
    """返回实际存在的数据文件路径。两者都不在时抛 IOError（**硬失败**，不静默返回空）。"""
    for p in (_BASE, _BASE + '.gz'):
        if os.path.exists(p):
            return p
    raise IOError('读不到 golden/factory.funcs.json(.gz) —— 缺失金标准数据，无法判定')


def load_factory_funcs():
    """加载并返回 `functions` 字典（函数名 → 反汇编/元数据）。"""
    p = factory_funcs_path()
    if p.endswith('.gz'):
        raw = gzip.open(p, 'rb').read()
    else:
        raw = io.open(p, 'rb').read()
    d = json.loads(raw.decode('utf-8'))
    if 'functions' not in d:
        raise IOError('%s 结构异常：缺 `functions` 键' % p)
    return d['functions']


if __name__ == '__main__':
    p = factory_funcs_path()
    F = load_factory_funcs()
    print('  数据文件: %s（%d B）' % (p, os.path.getsize(p)))
    print('  函数数  : %d' % len(F))
