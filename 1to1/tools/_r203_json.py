#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
d = json.load(open('golden/factory.funcs.json', encoding='utf-8'))
print('顶层键:', list(d.keys()))
for k, v in d.items():
    print(' ', k, '->', type(v).__name__, len(v) if hasattr(v, '__len__') else v)
    if isinstance(v, dict):
        ks = list(v.keys())[:5]
        print('    样本键:', ks)
        for k2 in ks:
            print('      ', repr(k2), '=>', repr(v[k2])[:120])