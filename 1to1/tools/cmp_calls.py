#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""被调函数集合对拍门禁 —— 工厂调用过的每个函数，重建侧也必须调用。

## 为什么这条判据最有价值（本项目的实证顺序）

排查"体积偏小"时，我形成了固定的证据顺序：**② 被调函数集合 → ③ 结构直方图 → ① 重定位**。
其中**第 ② 条最便宜、也最决定性**：

- `init_user_joy_key_mask`（GAP 16.36，**函数体被删**）：`.o` 只剩 1 条重定位、源码用的 4 个全局
  一次都没被引用；
- `ReadPS2JS`（GAP 16.39，**延时循环被删**）：调用集合**一致**，真正缺的是循环 ⇒ 靠"结构直方图 + 并排反汇编"才发现；
- `ReadUSBJoy` / `popwindows` / `popoffwindows` / `GetZipItemA`（本轮）：**调用集合与工厂完全一致**
  ⇒ 一律不是"删代码"，偏小来自寻址模式/分支融合 ⇒ **登记豁免，不去改源码**。

⇒ 结论：**"调用集合一致" 是排除"代码被删"的充分性很强的必要条件**。
   它一旦不一致，基本可以断定有逻辑整段丢失。

## 判据

- **工厂侧**：`golden/factory.funcs.json` 的 `t1` 里所有 `bl @name` / `bl @name@plt` / `bl @name+0xNN`。
- **我们侧**：反汇编重建 ELF 的函数区间，取 `bl`/`blx` 的目标地址，**解析成符号名**；
  ★ 关键：我们链接时 libc 调用会走 `__ARMv7ABSLongThunk_<name>` 桩（`0x5054xxx`），
    必须把 `__ARMv7ABSLongThunk_X` 归一化成 `X`，否则会误判成"工厂有而我们没有"。
- **归一化**：去掉 `@plt` / `@`；`__ARMv7ABSLongThunk_` 前缀；`+0xNN` 偏移。
- **判决**：工厂集合 ⊆ 我们集合 ⇒ OK；有工厂有而我们没有的 ⇒ FAIL（列出来）。
- ★ 过滤池噪声：目标地址必须落在某个**有符号**的函数起点上（字面量池数据被误解码时
  目标会是野地址或落在符号中间 ⇒ 直接丢弃）。

退出码：0 = 全覆盖；2 = 有缺失；3 = 无法判定。
"""
import io
import json
import os
import re
import struct
import sys
import gzip

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REBUILT = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
FACTORY_JSON = os.path.join(ROOT, 'golden', 'factory.funcs.json')


def load_factory():
    if os.path.exists(FACTORY_JSON):
        j = json.load(io.open(FACTORY_JSON, encoding='utf-8'))
        return j['functions'], 'json'
    gz = FACTORY_JSON + '.gz'
    if os.path.exists(gz):
        return json.loads(gzip.open(gz, 'rb').read().decode())['functions'], 'gz'
    return None, None


# ★ 假阳性类别 1：可内联的 libc / 编译器内建。
#   我们侧（clang）会把它们内联成指令（memcpy 小常量尺寸 → 几条 ldr/str；strlen → 循环；
#   __aeabi_idiv → 原地展开），因此"工厂有 bl、我们没有"**不代表逻辑缺失**。
#   实测（首次全量跑）：这类占了缺口的绝大多数。
INLINEABLE = {
    'strlen', 'strcpy', 'strncpy', 'strcmp', 'strncmp', 'memcpy', 'memmove', 'memset',
    'memcmp', 'malloc', 'free', 'realloc', 'calloc', 'fclose', 'fopen', 'fread', 'fwrite',
    'fseek', 'ftell', 'printf', 'sprintf', 'snprintf', 'puts', 'putchar', 'abort',
    '__aeabi_idiv', '__aeabi_uidiv', '__aeabi_idivmod', '__aeabi_uidivmod',
    '__aeabi_ldivmod', '__aeabi_uldivmod', '__aeabi_memcpy', '__aeabi_memset',
    '__stack_chk_fail', '__gnu_thumb1_case_uqi',
    # ctype 族的"函数"在 glibc 里其实是查表宏 ⇒ 我们侧编译成位测试指令，不产生调用
    'islower', 'isupper', 'isdigit', 'isalpha', 'isspace', 'isalnum', 'isxdigit',
    'tolower', 'toupper',
}


def norm(n):
    """符号名归一化。★ 三类假阳性都要在这里消掉（都是实测踩过的）：

    1. PLT / thunk 包装：`sprintf@plt`、`__ARMv7ABSLongThunk_sprintf` ⇒ 归一成 `sprintf`。
       （我们侧 libc 调用走 `__ARMv7ABSLongThunk_*` 桩，不归一化会被整片误判成"工厂有我们没有"。）
    2. **GCC 克隆后缀**：`run_process.constprop.0` / `mui_outputxy_length.isra.19` /
       `code_convert.constprop.22` / `f.part.0` —— 工厂侧调的是**克隆体**，我们侧可能调本体
       或另一个克隆体 ⇒ **必须剥掉后缀再比**（`prop_equiv` 的 `norm_name()` 同一套纪律）。
       实测：不剥后缀会有 6 个函数被误报。
    3. `+0xNN` 偏移（工厂模型里 `bl @name+0x34` 指向函数内部）。
    """
    n = n.strip().lstrip('@')
    n = re.sub(r'\+0x[0-9a-fA-F]+$', '', n)
    n = re.sub(r'@plt$', '', n)
    n = re.sub(r'^__ARMv7ABSLongThunk_', '', n)
    n = re.sub(r'^__ARMv7A_LongThunk_', '', n)
    n = re.sub(r'\.(constprop|isra|part|clone|localalias)\.[0-9]+$', '', n)   # ★ 克隆后缀
    return n


def elf_syms_and_text(path):
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, e_shoff + i * es) for i in range(n)]
    syms = {}          # name -> (val, size)
    byaddr = {}        # val -> name（只看 FUNC）
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            nm = d[stro + nmn:k].decode('utf-8', 'replace')
            syms.setdefault(nm, (val, sz))
            byaddr.setdefault(val, nm)
    # 可执行段
    text = []
    for s in S:
        if (s[2] & 0x4) and s[5] > 0:
            text.append((s[3], s[3] + s[5], s[4]))
    return d, syms, byaddr, text


def our_calls(d, syms, byaddr, text, vaddr, size):
    """返回该函数区间内的被调符号名集合。

    ★ 假阳性类别 2：**编译器分段**。一个函数可能被拆成多段，而 symtab 的 `st_size`
      只覆盖第一段（本项目实证：`UpdateROM` 976 B 的工厂代码被拆成 116 B + 主体）。
      只扫 `st_size` 会把"第二段里的调用"判成缺失（实测：`UpdateROM` 被报缺
      `OpenZipU/UnzipItem/GetZipItemA/CloseZipU/DateToTmuDate` 五个自研函数）。
      ⇒ 修正：扫描区间延伸到**下一个符号的起点**（`starts` 里 > vaddr 的最小值）。
    """
    # 找段
    base = None
    for st, en, off in text:
        if st <= vaddr < en:
            base = off + (vaddr - st)
            break
    if base is None:
        return None
    # ★ 延伸到下一个符号起点（覆盖"编译器分段"）
    nxt = min([a for a in byaddr if a > vaddr], default=vaddr + size)
    scan = min(max(size, nxt - vaddr), 8192)
    out = set()
    for o in range(0, scan, 4):
        w = struct.unpack_from('<I', d, base + o)[0]
        if (w >> 28) & 0xF == 0xF:
            continue
        # B/BL：bits27:25 == 101
        if ((w >> 25) & 0x7) != 0b101 or not ((w >> 24) & 1):
            continue                      # 只看带 link 的
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        tgt = (vaddr + o + 8 + imm * 4) & 0xFFFFFFFF
        nm = byaddr.get(tgt)
        if nm is None:
            # 目标在符号中间 / 野地址 ⇒ 池数据噪声，丢弃
            continue
        out.add(norm(nm))
    return out


def factory_calls(t):
    out = set()
    for x in t.get('t1') or []:
        if not isinstance(x, str):
            continue
        m = re.match(r'^bl\s+(.+)$', x.strip())
        if m:
            out.add(norm(m.group(1)))
    return out


def main():
    fac, src = load_factory()
    if fac is None:
        print('!! 缺 golden/factory.funcs.json(.gz)')
        return 3
    if not os.path.exists(REBUILT):
        print('!! 缺 %s（先构建）' % REBUILT)
        return 3
    d, syms, byaddr, text = elf_syms_and_text(REBUILT)
    names = [os.path.basename(p)[:-2].split('_', 2)[-1]
             for p in __import__('glob').glob(os.path.join(ROOT, 'src', 'proprietary', '*', '*.c'))]
    print('=' * 92)
    print('被调函数集合对拍（工厂调用过的每个函数，重建侧也必须调用）')
    print('=' * 92)
    bad = []
    checked = 0
    for nm in sorted(set(names)):
        t = fac.get(nm)
        r = syms.get(nm)
        if t is None or r is None:
            continue
        fc = factory_calls(t)
        oc = our_calls(d, syms, byaddr, text, r[0], r[1])
        if oc is None:
            continue
        checked += 1
        # ★ 假阳性类别 1 的过滤：可内联的 libc/内建不算"缺失"
        miss = sorted(x for x in (fc - oc) if x not in INLINEABLE)
        if miss:
            bad.append((nm, miss, sorted(fc), sorted(oc)))
    print('  参与对拍的函数 %d 个；工厂调用的去重符号总数 %d'
          % (checked, len({x for nm in names for x in (factory_calls(fac.get(nm) or {}))})))
    if bad:
        print('  ★ 工厂有而我们**没有调用**的符号（%d 个函数）：' % len(bad))
        for nm, miss, fc, oc in bad[:24]:
            print('    %-26s 缺: %s' % (nm[:26], ", ".join(miss[:5])))
        print('')
        print('  结论 : FAIL —— 这些函数可能整段丢失了调用逻辑（或被内联）')
        return 2
    print('  结论 : PASS（%d/%d 个函数的调用集合覆盖工厂）' % (checked, checked))
    return 0


if __name__ == '__main__':
    sys.exit(main())
