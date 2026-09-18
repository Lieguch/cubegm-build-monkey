#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 工作流 `run:` 块的续行链 lint —— 专抓「注释插进 `\\` 续行链」这一类静默失效。

## 为什么需要它（第 44 轮实测事故，代价一整轮 CI）

`1to1-qemu-behav.yml` 的场景 E 步骤曾长这样：

```yaml
run: |
  cd 1to1
  SYSROOT=/arm-root ... CGM_KEY2_SEED=1 ... CGM_DBGUI2=1 \\
  # 关键地址普查（……）
  CGM_TRACE_ADDRS="000119f4 …" \\
    sh tools/ci_qemu_behav.sh \\
      build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu_e || true
```

shell 语义：第 3 行的 `\\` 把第 4 行接上来，于是成为
`CGM_DBGUI2=1 # 关键地址普查（……）` —— **`#` 起注释**，且该行**不以 `\\` 结尾**
⇒ **续行链在此断开**。结果：

* 第 5~7 行变成**另一条命令**（只带 `CGM_TRACE_ADDRS`）；
* **`CGM_KEY2_SEED` / `CGM_KEY2_HOOK` / `CGM_IO_TRACE` / `CGM_DBGUI2` 全部丢失**；
* 观测现象：重建侧退回 `open … ui_cn.zip fail`（key2 未注入的原症状）、
  所有探针证据行消失，而 **行为门禁反而报 PASS**（两侧"同步失败"⇒ 前缀再次对齐）。

⇒ 这是"**门禁假绿 + 实验条件被静默篡改**"双重事故，仅靠肉眼审 YAML 发现不了。
本工具把它变成硬门禁。

## 判据（刻意保守，只报"确定坏"的）

在 `run:` 块（YAML 折叠/保留块标量）内，若某行是**注释行**，且其**上一行以单个 `\\` 结尾**
（即处于续行链中间），则判失败。

不报的情形（避免假阳性）：纯注释块、注释前的行不以 `\\` 结尾、行尾 `\\` 是字符串内容等。

自证（铁律 101）：构造性 —— 把已知的坏样本喂给判据必须命中，把好样本喂进去必须不命中。
"""
import argparse
import os
import re
import sys

try:
    import yaml
except ImportError:                                    # pragma: no cover
    yaml = None


def continues(line):
    """该行是否以「续行反斜杠」结尾（反斜杠前可以有空白）。"""
    return bool(re.search(r'\\[ \t]*$', line))


def is_comment(line):
    return line.lstrip().startswith('#')


def lint_run_block(text):
    """返回 [(行号, 行内容, 上一行内容)] —— 注释插在续行链中间的位置。"""
    bad = []
    lines = text.splitlines()
    for i in range(1, len(lines)):
        if is_comment(lines[i]) and continues(lines[i - 1]):
            bad.append((i + 1, lines[i], lines[i - 1]))
    return bad


def lint_workflow(path):
    """解析 YAML，逐个 job/step 检查 run: 块。YAML 解析失败时退化为整文本扫描。"""
    raw = open(path, encoding='utf-8', errors='replace').read()
    if yaml is None:
        return lint_run_block(raw)
    try:
        doc = yaml.safe_load(raw)
    except Exception as e:                             # noqa: BLE001
        print('  [note] %s YAML 解析失败（%s）⇒ 退化为整文本扫描' % (path, e))
        return lint_run_block(raw)
    bad = []
    for job in (doc.get('jobs') or {}).values():
        for st in (job.get('steps') or []):
            run = st.get('run')
            if not isinstance(run, str):
                continue
            for ln, line, prev in lint_run_block(run):
                bad.append((st.get('name', '(unnamed)'), ln, line.strip()[:60],
                            prev.strip()[-40:]))
    return bad


def selfcheck():
    bad_sample = (
        'cmd A=1 \\\n'
        '# 注释\n'
        'B=2 \\\n'
        '  sh run.sh\n'
    )
    good_samples = [
        '# 注释在最前面\ncmd A=1 \\\nB=2 \\\n  sh run.sh\n',
        'cmd A=1 \\\nB=2 \\\n  sh run.sh\n',
        '# 单独一行注释\nsh run.sh\n',
        'cmd "a \\\\ b"\n# 注释\n',
    ]
    ok = True
    if not lint_run_block(bad_sample):
        print('  [selfcheck] ✗ 坏样本未被命中')
        ok = False
    for s in good_samples:
        if lint_run_block(s):
            print('  [selfcheck] ✗ 好样本被误报：%r' % s[:40])
            ok = False
    if ok:
        print('  [selfcheck] 构造性自证：1 坏样本命中 + %d 好样本放行 ✓' % len(good_samples))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--glob', default='.github/workflows/*.yml')
    a = ap.parse_args()
    if not selfcheck():
        return 2
    import glob as _g
    files = sorted(_g.glob(os.path.join(a.root, a.glob)))
    if not files:
        print('  [SKIP] 未找到工作流文件（%s）' % a.glob)
        return 0
    total = 0
    for f in files:
        bad = lint_workflow(f)
        print('  %-44s 问题 %d 处' % (os.path.basename(f), len(bad)))
        for item in bad:
            if len(item) == 4:
                name, ln, line, prev = item
                print('     ★ step=%s 行%d：注释 %r 紧跟在续行链中（上一行以 \\ 结尾：…%s）'
                      % (name[:34], ln, line, prev))
            else:
                ln, line, prev = item
                print('     ★ 行%d：注释 %r 紧跟在续行链中（…%s）' % (ln, line.strip()[:56], prev.strip()[-36:]))
        total += len(bad)
    if total:
        print('  [FAIL] 共 %d 处「注释插进续行链」—— 会让该命令后续行变成独立命令，'
              '环境变量静默丢失（实测曾导致门禁假绿）' % total)
        return 1
    print('  ✓ 未发现「注释插进续行链」')
    return 0


if __name__ == '__main__':
    sys.exit(main())
