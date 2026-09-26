#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ci_gate_summary —— **逐步骤收齐**：一个 job 里任何一步失败，都在这里一次性全部报出来。

为什么需要它（GAP 17.11 / 与 §0.4「跳出来」同一条纪律）
-------------------------------------------------------
`1to1-verify` 是单 job **顺序**执行 30+ 步；GitHub Actions 的语义是
**第一步失败 ⇒ 后面所有步骤一次都不跑**。后果：

* **一轮 CI 只暴露一个缺陷** ⇒ 判定能力被建在稀缺资源（Actions 分钟 / 真机）上 ⇒ 无法收敛。
  本轮实测：`check_types` 一红，`diff_exec` 两步、`dce_ref_diff`、`regen_contract`、
  `src_transcript_parity` 等 **20+ 步在 CI 里从未执行过**，而它们在本地全是绿的。
* **"CI 绿了"的信息量 = 最弱那一步的信息量** —— 这正是"假绿"的温床。

做法：给每个门禁步骤加 `continue-on-error: true`（**单独看它确实会掩盖失败**），
再在**最后**加一个 `if: always()` 的总账步骤：它读 `toJSON(steps)`，
把**所有**非 success 的步骤一次列全并**硬失败**。
⇒ 净效果：**失败不再被掩盖，而且一轮看完所有失败。**

★ 不变式（自证覆盖）：总账步骤**必须**满足
  ① 任何一步 outcome=failure ⇒ 总账 exit 1；
  ② 全 success ⇒ exit 0；
  ③ **自己不在被检查的集合里**（否则会自我引用）；
  ④ 步骤读不到（env 缺失）⇒ **fail-closed**（exit 2），不许静默当通过。
"""

import json
import os
import sys

# 这些步骤"失败"不构成门禁失败：本身是收尾/上传类，或已有自己的判定
IGNORE_PREFIX = ('门禁总账', '门禁汇总', '上传报告', 'Post ', 'Set up job', 'Complete job',
                 'Checkout', 'Run actions/', '解压金标准', '校验金标准完整性')

BAD = ('failure', 'cancelled', 'timed_out', 'action_required')

# ★ 「检视到多少个步骤」的下界。低于它一律 fail-closed —— 因为"解析出 0 个"与
#   "全部都过"在输出上一模一样，没有这条下界就分不清（本项目实测被此坑了一轮）。
#   加步骤时**必须同步上调**本常量，否则是"覆盖率退化"而不是"通过"。
MIN_STEPS = 30


def verdict(steps_json, min_steps=MIN_STEPS):
    """→ (bad_list, skipped_list, parsed_ok)

    steps_json：GitHub Actions 的 `toJSON(steps)` 文本。
    """
    try:
        steps = json.loads(steps_json)
    except Exception:
        return [], [], False
    if not isinstance(steps, dict):
        return [], [], False
    bad, skipped, seen = [], [], 0
    for name, info in steps.items():
        if not isinstance(info, dict):
            continue
        if name.startswith(IGNORE_PREFIX):
            continue
        seen += 1
        oc = info.get('outcome')
        if oc in BAD:
            bad.append((name, oc, info.get('conclusion')))
        elif oc in ('skipped', None):
            skipped.append(name)
    # ★★★ 第 64 轮实测到的**假绿**（本条被修的原因）：
    #   `toJSON(steps)` 的键是**步骤 id**；工作流里**没有一个步骤带 `id:`** ⇒
    #   它返回空对象 ⇒ 本函数"解析成功、总数 0、失败 0、✓ 全部步骤 success"。
    #   也就是**它一个步骤都没检视，却报全绿** —— 正是 §17.11 要消灭的那种假绿，
    #   而且它让一次真实失败（`audit_vs_factory.py --self-test` 参数写错）静默通过。
    #   ⇒ 两道 fail-closed：① 总数 0 ⇒ 判定不存在；② 少于 MIN_STEPS ⇒ 解析不完整。
    #   （配合：`1to1-verify.yml` 每个步骤都已补 `id: sNN`。）
    return sorted(bad), sorted(skipped), (seen >= min_steps)


def self_test():
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    j_ok = json.dumps({'编译': {'outcome': 'success', 'conclusion': 'success'},
                       '门禁总账': {'outcome': 'failure', 'conclusion': 'failure'},
                       '上传报告': {'outcome': 'success'}})
    b, s, ok = verdict(j_ok, min_steps=0)
    c('正例 全绿（总账自身失败不算）⇒ 无失败项', (b, ok), ([], True))
    c('正例 自身的 failure 被排除', any('门禁总账' in x[0] for x in b), False)

    j_bad = json.dumps({'A门禁': {'outcome': 'failure', 'conclusion': 'failure'},
                        'B门禁': {'outcome': 'success', 'conclusion': 'success'},
                        'C门禁': {'outcome': 'failure', 'conclusion': 'failure'}})
    b, s, ok = verdict(j_bad, min_steps=0)
    c('反例 两个失败都被收齐（不是只报第一个）', [x[0] for x in b], ['A门禁', 'C门禁'])
    c('反例 cancelled 也算失败', verdict(json.dumps(
        {'X': {'outcome': 'cancelled'}}), min_steps=0)[0][0][1], 'cancelled')

    b, s, ok = verdict('{ not json')
    c('缺陷态 解析不了 ⇒ parsed_ok=False（调用方必须 fail-closed）', ok, False)
    b, s, ok = verdict('[]')
    c('缺陷态 形态不对 ⇒ parsed_ok=False', ok, False)
    b, s, ok = verdict('{}')
    # ★ 本锚点**原来的期望是 `([], True)`（"空 dict 解析成功、无失败项"）—— 已更正**：
    #   那正是本轮实测到的假绿（`toJSON(steps)` 返回空 ⇒ 报"✓ 全部步骤 success"）。
    #   正确语义：空 ⇒ **判定不存在** ⇒ parsed_ok=False ⇒ 调用方必须 fail-closed。
    c('★ 边界 空 dict ⇒ parsed_ok=False（不是"无失败项"，而是"没检视到任何步骤"）',
      (b, ok), ([], False))

    b, s, ok = verdict(json.dumps({'D门禁': {'outcome': 'skipped'}}), min_steps=0)
    c('skipped 单列（不当作失败，但要报出来）', s, ['D门禁'])
    # ★ 第 64 轮假绿的回归锚点：**检视到 0 个步骤 ⇒ 判定不存在**（不得报全绿）
    import json as _j
    c('缺陷态 空 steps ⇒ parsed_ok=False（"0 个"与"全过"必须可区分）',
      verdict(_j.dumps({}), min_steps=1)[2], False)
    c('缺陷态 少于下界 ⇒ parsed_ok=False',
      verdict(_j.dumps({'s%02d' % i: {'outcome': 'success'} for i in range(3)}),
              min_steps=30)[2], False)
    c('正例 达到下界且全过 ⇒ parsed_ok=True 且无失败项',
      verdict(_j.dumps({'s%02d' % i: {'outcome': 'success'} for i in range(30)}),
              min_steps=30), ([], [], True))
    return chk


def main():
    if '--self-test' in sys.argv:
        chk = self_test()
        bad = 0
        for tag, got, want, ok in chk:
            print('   %s  %-52s got=%s' % ('✓' if ok else '★FAIL', tag, got))
            bad += 0 if ok else 1
        print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
        return 2 if bad else 0

    raw = os.environ.get('STEPS_JSON')
    if raw is None:
        sys.stderr.write('★ 读不到 STEPS_JSON（workflow 必须传 ${{ toJSON(steps) }}）'
                         ' —— fail-closed，不当通过处理\n')
        return 2
    bad, skipped, ok = verdict(raw)
    if not ok:
        sys.stderr.write('★ STEPS_JSON 解析失败 —— fail-closed\n')
        return 2

    lines = ['## 门禁总账（逐步骤收齐）', '']
    lines.append('* 步骤总数（去掉收尾类）：%d' % (len(json.loads(raw)) - len(bad) - len(skipped)))
    lines.append('* **失败 %d 步**' % len(bad))
    if bad:
        lines.append('')
        lines.append('| 步骤 | outcome |')
        lines.append('|---|---|')
        for n, oc, _ in bad:
            lines.append('| %s | `%s` |' % (n, oc))
    if skipped:
        lines.append('')
        lines.append('* 被跳过（前置步骤已失败 ⇒ **本次没有判过**，不得当作通过）：%s'
                     % ', '.join('`%s`' % x for x in skipped))
    txt = '\n'.join(lines)
    print(txt)
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        with open(summ, 'a', encoding='utf-8') as fh:
            fh.write(txt + '\n')
    if bad:
        for n, oc, _ in bad:
            print('::error title=门禁失败::%s (%s)' % (n, oc))
        return 1
    print('   ✓ 全部步骤 success')
    return 0


if __name__ == '__main__':
    sys.exit(main())
