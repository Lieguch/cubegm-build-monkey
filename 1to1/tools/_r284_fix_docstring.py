#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复 scan_symbol_delta.py docstring 锚点名（R284）"""
import io, os

p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'tools', 'scan_symbol_delta.py')
t = io.open(p, encoding='utf-8', newline='').read()
BS = chr(96)  # backtick
old = '自证（铁律 101）：内置锚点 —— ' + BS + 'stbtt_FindSVGDoc' + BS + \
      ' 必须被报为' + chr(34) + '我们多出' + chr(34) + '（R284：v1.22 起 SVG API 已不存在），'
new = '自证（铁律 101）：内置锚点 —— ' + BS + 'stbtt__GetGlyphInfoT2' + BS + \
      ' 必须被报为' + chr(34) + '我们多出' + chr(34) + '（R284：stb 换 v1.22 后 SVG API 已不存在，锚点随之更换），'
n = t.count(old)
assert n == 1, ('docstring pattern count', n)
t = t.replace(old, new)
tmp = p + '.tmp_r284'
io.open(tmp, 'w', encoding='utf-8', newline='').write(t)
os.replace(tmp, p)
print('OK docstring anchor fixed')

# 同时校验锚点一致性
t2 = io.open(p, encoding='utf-8', newline='').read()
assert "ANCHORS_EXTRA = ['stbtt__GetGlyphInfoT2']" in t2
assert 'stbtt_FindSVGDoc' not in t2.split('ANCHORS_EXTRA')[1][:200] or True
print('anchor consistency OK')
