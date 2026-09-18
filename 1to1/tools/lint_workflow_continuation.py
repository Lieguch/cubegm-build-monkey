#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI 工作流 `run:` 块的续行链 lint —— 专抓「续行链被破坏」这一类静默失效。

## 为什么需要它（两次真实事故，各代价一整轮 CI）

### 形态 ①（第 44 轮）：注释插进 `\\` 续行链

```yaml
run: |
  cd 1to1
  SYSROOT=/arm-root ... CGM_DBGUI2=1 \\
  # 关键地址普查（……）
  CGM_TRACE_ADDRS="000119f4 …" \\
    sh tools/ci_qemu_behav.sh … || true
```

第 3 行的 `\\` 把第 4 行接上来 ⇒ `CGM_DBGUI2=1 # …` 起注释、且该行**不以 `\\` 结尾**
⇒ 链在此断开 ⇒ `CGM_KEY2_SEED`/`CGM_IO_TRACE`/`CGM_DBGUI2` **全部静默丢失**，
观测现象 = 重建侧退回原症状、探针证据行消失，而**行为门禁反而 PASS（假绿）**。

### 形态 ②（第 46 轮）：在已以 `\\` 结尾的行后面**追加**内容

```yaml
  CGM_KEY2_SEED=1 … CGM_TRACE_ADDRS="…" \\ CGM_DBGUNZ=1 \\
    sh tools/ci_qemu_behav.sh … report/qemu_e || true
```

`\\` 后面跟的是**空格**而不是换行 ⇒ shell 把它当**转义空格**，赋值词被切碎，
实测运行时直接报：

```
_run.sh: line 3:  CGM_DBGUNZ=1: command not found
```

⇒ **真正的 `sh tools/ci_qemu_behav.sh` 根本没执行**：`report/qemu_e` 整目录缺失、
所有探针为空，而该 step 因 `|| true` 仍显示 ✓。

⇒ 两次都是"**门禁假绿 + 实验条件被静默篡改**"，肉眼审 YAML 发现不了。本工具把两者都变硬门禁。

## 判据（刻意保守，只报"确定坏"的）

1. `run:` 块内，**注释行**紧跟在**以 `\\` 结尾**的上一行之后 ⇒ 失败（形态 ①）。
2. `run:` 块内，某行**以 `\\` 结尾**且行内出现「**单**个 `\\` + 空白 + `NAME=`」⇒ 失败（形态 ②）。
   - 单反斜杠用负向后顾排除 `\\\\`（真正的字面反斜杠后跟空格是合法的）；
   - 只认后面接 `NAME=`（即被切碎的赋值词）⇒ 避免把 `echo "a\\ b"` 这类合法写法误报。

自证（铁律 101）：构造性 —— 两种坏样本必须命中，好样本必须放行。
"""
import argparse
import os
import re
import sys

try:
    import yaml
except ImportError:                                    # pragma: no cover
    yaml = None

CONT = re.compile(r'\\[ \t]*$')                        # 行尾续行反斜杠
SPLIT = re.compile(r'(?<!\\)\\[ \t]+[A-Za-z_][A-Za-z0-9_]*=')   # 形态 ②：`\ NAME=`


def continues(line):
    return bool(CONT.search(line))


def is_comment(line):
    return line.lstrip().startswith('#')


def lint_run_block(text):
    """返回 [(行号, 形态, 行内容, 相关行内容)]。"""
    bad = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if is_comment(line) and i > 0 and continues(lines[i - 1]):
            bad.append((i + 1, '注释插进续行链', line, lines[i - 1]))
        if continues(line) and SPLIT.search(line):
            bad.append((i + 1, '续行链被追加内容破坏', line, line))
    return bad


def lint_workflow(path):
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
            for ln, kind, line, ref in lint_run_block(run):
                bad.append((st.get('name', '(unnamed)'), ln, kind, line.strip()[:60],
                            ref.strip()[-44:]))
    return bad


def selfcheck():
    bad_samples = [
        # 形态 ①：注释插进续行链
        ('cmd A=1 \\\n# 注释\nB=2 \\\n  sh run.sh\n', '注释插进续行链'),
        # 形态 ②：在已以 \ 结尾的行后面追加内容
        ('cmd A=1 \\ B=2 \\\n  sh run.sh\n', '续行链被追加内容破坏'),
    ]
    good_samples = [
        '# 注释在最前面\ncmd A=1 \\\nB=2 \\\n  sh run.sh\n',
        'cmd A=1 \\\nB=2 \\\n  sh run.sh\n',
        '# 单独一行注释\nsh run.sh\n',
        'cmd "a \\\\ b"\n# 注释\n',
        # 合法的续行链：内容在反斜杠**之前**
        'cmd A=1 B=2 C=3 \\\n  sh run.sh\n',
        'cmd A=1 \\\n  B=2 C=3 \\\n  sh run.sh\n',
    ]
    ok = True
    for sample, want in bad_samples:
        hits = lint_run_block(sample)
        kinds = [h[1] for h in hits]
        if want not in kinds:
            print('  [selfcheck] ✗ 坏样本（%s）未被命中（量到 %s）' % (want, kinds))
            ok = False
    for s in good_samples:
        if lint_run_block(s):
            print('  [selfcheck] ✗ 好样本被误报：%r' % s[:44])
            ok = False
    if ok:
        print('  [selfcheck] 构造性自证：%d 种坏样本命中 + %d 好样本放行 ✓'
              % (len(bad_samples), len(good_samples)))
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
        for name, ln, kind, line, ref in bad:
            print('     ★ step=%s 行%d【%s】：%r（相关：…%s）'
                  % (name[:32], ln, kind, line, ref))
        total += len(bad)
    if total:
        print('  [FAIL] 共 %d 处「续行链被破坏」—— 会让该命令的实际执行被跳过/环境变量静默丢失'
              '（实测两次：一次门禁假绿、一次整场景未运行）' % total)
        return 1
    print('  ✓ 未发现「续行链被破坏」')
    return 0


if __name__ == '__main__':
    sys.exit(main())
