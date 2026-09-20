#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `proto.h` 里**变参函数**的 K&R 空声明改成真实原型（幂等）。

## 为什么必须改（C 语言层面的硬约束）

`proto.h` 由 `gen_compat.py` 生成，对 Ghidra 无法解析参数的函数一律写成空声明：

    extern void RARCH_LOG();      /* K&R: 参数不可信/不可解析 */

而我们要把定义还原成真正的变参函数：

    void RARCH_LOG(char *param_1, ...) { __builtin_va_start(ap, param_1); ... }

**C11 6.7.6.3p15 明确禁止**这种组合：若一方是「非定义的、参数列表为空」的声明，
另一方的参数列表**不得以省略号结尾**。clang 报：

    error: conflicting types for 'RARCH_LOG'
    note: previous declaration is here: extern void RARCH_LOG();

⇒ 必须把该声明改成原型。Ghidra 会把**所有**变参函数渲染成「单参数 + 空声明」，
   所以这类补丁要能重复执行、并覆盖多个函数。

用法：`python tools/patch_proto_varargs.py`（幂等；已在 gen_compat_all.sh 里自动调用）
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PATH = os.path.join(ROOT, 'src', 'compat', 'proto.h')

# 函数名 -> 真实原型（证据均见对应 .c 文件的头部注释）
VARARGS = {
    'RARCH_LOG': 'char *param_1, ...',
    # ★ 2026-09-20：同一类缺陷的第二个实例（Ghidra 丢 `...`）。证据见
    #   src/proprietary/core/FUN_002b4f14_log_dummy.c 头部（原厂 `push {r1,r2,r3}` +
    #   `add r1, sp, #16` + `bl RARCH_LOG_V` ⇒ 必须传 (fmt, va_list) 两个参数）。
    #   注意它的原声明**不是**空声明而是 `(gh_uint, gh_u4)` —— 因为 Ghidra 解析出了
    #   两个固定参数。所以匹配逻辑也必须容许「带参数的声明行」（旧实现只匹配 `fn()`）。
    'log_dummy': 'gh_uint param_1, char *param_2, ...',
}


def main():
    if not os.path.exists(PATH):
        print('!! proto.h 不存在：%s' % PATH, file=sys.stderr)
        return 1
    s = open(PATH, encoding='utf-8').read()
    changed = []
    for fn, proto in VARARGS.items():
        want = 'extern void %s(%s);\n' % (fn, proto)
        if want in s:
            continue
        # 找到该函数的声明行并替换。
        # ★ 2026-09-20 放宽：旧实现只匹配**空声明** `extern void fn();`，但 Ghidra 对
        #   「有固定参数 + `...`」的函数会渲染成 `(gh_uint, gh_u4)` 这种**带参数**的声明
        #   （实例：`log_dummy`）⇒ 旧匹配找不到、静默 warn 跳过。改为匹配任意
        #   `extern void <fn>(...);` 且要求**参数列表里不含 `...`**（幂等：已改过就不动）。
        import re as _re
        lines = s.split('\n')
        pat = _re.compile(r'^extern\s+void\s+%s\s*\(([^)]*)\)\s*;' % _re.escape(fn))
        for i, ln in enumerate(lines):
            m = pat.match(ln)
            if not m:
                continue
            if '...' in m.group(1):
                break                      # 已是真原型 ⇒ 幂等跳过
            lines[i] = want.rstrip('\n')
            changed.append((fn, ln.strip()))
            break
        else:
            print('   [warn] 未找到 %s 的声明（可能已被改过或名字不同）' % fn)
            continue
        s = '\n'.join(lines)
    if changed:
        open(PATH, 'w', encoding='utf-8', newline='').write(s)
        for fn, old in changed:
            print('   已改 %-14s  %s  ->  真原型（变参）' % (fn, old[:52]))
    else:
        print('   proto.h 无需改动（变参原型已在位）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
