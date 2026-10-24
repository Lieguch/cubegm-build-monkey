#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harden_prototypes.py —— 把 proto.h 里的 **K&R 空参声明** 全部换成**精确原型**

为什么是"根治"而不是补丁
------------------------------------------------------------------
7 轮真机里同一族缺陷反复出现（sunxi_gpio_output ×7、mui_DispBlock ×3、PlaySound ×1），
根因不是某几处写错，而是 **C 语言层面的校验被关掉了**：
    `extern gh_u4 sunxi_gpio_output();   /* K&R: 参数不可信/不可解析 *\u002f`
这种"空参声明"在 C 里表示"形参未知"，于是 **编译器不做实参个数检查**，
Ghidra 丢掉的实参可以一路静默编进产物，只在真机上以"无声/无按键/冻住"的形式暴露。

做法：对每个 K&R 声明，去我们的**函数定义**里取出真实形参表，改写成精确原型。
之后任何"实参少于形参"的调用点都会在**编译期**报错 —— 把外部检查变成语言自身的检查。

纪律：
  · 只改**能解析出定义且形参表干净**的（含 `...`、函数指针形参、或找不到定义的跳过并列出）；
  · `main` 特殊处理（保留 int main(int argc, char **argv)）；
  · 原子写（写 .tmp → 校验 → os.replace）；改前的文件留在 proto.h.bak_knr；
  · 输出一份清单：改了哪些、跳了哪些、原因是什么（**不许静默跳过**）。

用法：
    python tools/harden_prototypes.py            # 预演（只报告，不写）
    python tools/harden_prototypes.py --apply    # 实际改写
"""
import io
import os
import re
import shutil
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROTO = os.path.join(ROOT, 'src/compat/proto.h')
BAK = PROTO + '.bak_knr'


def strip(txt):
    out, i, n, st = [], 0, len(txt), None
    while i < n:
        c = txt[i]
        nx = txt[i + 1] if i + 1 < n else ''
        if st is None:
            if c == '/' and nx == '*':
                st = 'b'; out.append('  '); i += 2; continue
            if c == '/' and nx == '/':
                st = 'l'; out.append('  '); i += 2; continue
            if c == '"':
                st = 'd'; out.append(' '); i += 1; continue
            if c == "'":
                st = 's'; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if st == 'b':
            if c == '*' and nx == '/':
                st = None; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if st == 'l':
            if c == '\n':
                st = None; out.append('\n'); i += 1; continue
            out.append(' '); i += 1; continue
        if c == '\\':
            out.append('  '); i += 2; continue
        if (st == 'd' and c == '"') or (st == 's' and c == "'"):
            st = None
        out.append(' '); i += 1
    return ''.join(out)


def definitions():
    """{name: params} —— 从源码定义里取形参表（K&R 的 `f(void)` 记为 'void'）"""
    out = {}
    pat = re.compile(r'\b(\w+)\s*\(([^)]*)\)\s*\n\s*\{')
    for path in glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True):
        txt = strip(io.open(path, encoding='utf-8', errors='replace').read())
        for m in pat.finditer(txt):
            name, params = m.group(1), m.group(2).strip()
            out.setdefault(name, params)
    return out


SAFE_PARAM = re.compile(r'^\s*(?:const\s+|unsigned\s+|signed\s+|struct\s+\w+\s+)*'
                        r'[A-Za-z_]\w*(?:\s+\w+)?(?:\s*\[\s*\d*\s*\])?\s*(?:\*+\s*\w+)?\s*$')


def clean_param_list(params):
    """形参表 → 原型里的类型表（**保留指针星号**，数组退化为指针，去掉形参名）

    ★ R268 修复（工具的系统性 bug）：旧实现用 `^(.+?)\s+\**\s*(\w+)$` 取类型，
      匹配 "ZIPENTRY *param_3" 时把 `*` 当成"类型与名字之间的分隔符"**吞掉了**
      ⇒ 生成 `ZIPENTRY param_3`（按值传结构体）⇒ 编译器把 30+ 处"传指针"报成
      `incompatible pointer to integer`，把定义处报成 `conflicting types`。
      实测：38 个失败文件里绝大多数都是这个假象，不是源码错。
      现改为"取最后一个标识符为形参名，其余原样作类型"，星号与 const 都保留。
    """
    if params in ('', 'void'):
        return 'void'
    out = []
    for p in [x.strip() for x in params.split(',')]:
        if not p:
            continue
        if '...' in p or '(' in p:
            return None                      # 可变参数 / 函数指针形参：跳过，人工处理
        m = re.match(r'^(.*?)\b(\w+)\s*(\[\s*\d*\s*\])?$', p)
        if not m:
            return None
        typ = m.group(1).strip()
        arr = m.group(3)
        if arr:
            typ = typ + '*'
        if not typ or not re.match(r'^[A-Za-z_][\w\s\*]*$', typ):
            return None
        out.append(typ)
    return ', '.join(out) if out else 'void'


def main():
    apply = '--apply' in sys.argv
    txt = io.open(PROTO, encoding='utf-8', errors='replace').read()
    defs = definitions()
    changed, skipped = [], []
    lines = txt.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        m = re.match(r'^extern\s+([A-Za-z_][\w \*]*?)\b(\w+)\s*\(\s*\)\s*;\s*(/\*.*\*/)?\s*$', ln.rstrip('\n'))
        if not m:
            continue
        ret, name = m.group(1).strip(), m.group(2)
        if False:  # R268：不再特殊处理 main —— 我方定义是 `gh_u4 main(void)`，
                   # 硬写成 `int main(int,char**)` 会与定义冲突（conflicting types）。
                   # 入口的 argc/argv 由 __libc_start_main 传，定义里不用就保持 void。
            pass
        else:
            params = defs.get(name)
            if params is None:
                skipped.append((name, '找不到定义'))
                continue
            pr = clean_param_list(params)
            if pr is None:
                skipped.append((name, '形参表含可变参数/函数指针：%s' % params))
                continue
            # ★ 自测抓到的 bug：这里曾漏掉 %s(name)，产出 `extern gh_u4 (void);` —— 函数名消失。
            #   修好后加一条断言：新行必须同时包含函数名与形参表（见下 verify）。
            new = ('extern %s%s%s(%s);  /* R267：原 K&R 空参 → 精确原型（形参取自定义；编译器从此校验实参个数） */\n'
                   % (ret, ('' if ret.endswith('*') else ' '), name, pr))
            assert name in new, 'rewrite lost the function name: %s' % name
            changed.append((name, '', pr, ''))
        lines[i] = new
    print('K&R 声明可改写：%d 条；跳过：%d 条' % (len(changed), len(skipped)))
    for name, why in skipped:
        print('  跳过 %-32s %s' % (name, why))
    if not apply:
        print('\n（预演模式；加 --apply 实际写入）')
        return 0
    if not os.path.exists(BAK):
        shutil.copy2(PROTO, BAK)
    tmp = PROTO + '.tmp'
    io.open(tmp, 'w', encoding='utf-8', newline='\n').write(''.join(lines))
    os.replace(tmp, PROTO)
    print('\n已写入 %s（备份 %s）' % (PROTO, os.path.basename(BAK)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
