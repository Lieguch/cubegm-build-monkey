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
        # 找到该函数的空声明行（允许行尾带注释）
        lines = s.split('\n')
        for i, ln in enumerate(lines):
            if ln.startswith('extern void %s();' % fn):
                lines[i] = want.rstrip('\n')
                changed.append((fn, ln.strip()))
                break
        else:
            print('   [warn] 未找到 %s 的空声明（可能已被改过或名字不同）' % fn)
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
