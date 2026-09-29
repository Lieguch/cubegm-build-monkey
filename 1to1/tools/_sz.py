#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_sz.py —— 打印若干 ELF 里指定 STT_FUNC 的 size（用于体量收敛核对）。

★ 为什么单独成文件：在 `python - <<'PY'` 的 heredoc / `python -c` 里写这些代码
  在本机会踩坑（用户记忆里已登记：反斜杠/引号被 shell 吃掉）。**写成文件再跑**。
★ 用 `io.BytesIO` 读字节，避免任何文本模式解码路径。
"""
import io
import os
import sys

from elftools.elf.elffile import ELFFile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def funcs(path):
    with open(path, 'rb') as fh:
        data = fh.read()
    e = ELFFile(io.BytesIO(data))
    st = e.get_section_by_name('.symtab')
    if st is None:
        return {}
    return {s.name: s['st_size'] for s in st.iter_symbols()
            if s.name and s['st_info']['type'] == 'STT_FUNC' and s['st_value']}


def main():
    names = sys.argv[1].split(',')
    fac = funcs(os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    base = funcs(os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    print('%-30s %8s %8s   %s' % ('symbol', 'factory', 'deliver', 'others'))
    for n in names:
        others = []
        for p in sys.argv[2:]:
            f = funcs(p)
            others.append('%s=%s' % (os.path.basename(p), f.get(n)))
        f, b = fac.get(n), base.get(n)
        ratio = ('%.3f' % (b / f)) if (f and b) else '-'
        print('%-30s %8s %8s(%s)   %s' % (n, f, b, ratio, ' '.join(others)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
