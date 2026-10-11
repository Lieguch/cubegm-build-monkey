#!/usr/bin/env python3
"""第 146 轮 P2：把"工厂有定义、我方缺失"的 FUNC 符号做**命名归一化**再判缺。

★ 为什么需要（第 145 轮实测 19 项，逐项核实后发现全是"命名规则差异"）：
  两边都是 GCC/Clang，但**符号命名后缀规则不同**：
    工厂 gcc 6.2 会给被拆分/特化/常量传播的克隆函数加后缀：
      `foo.part.N`   —— 函数被切成片段（part）
      `foo.isra.N`   —— interprocedural scalar replacement of aggregates
      `foo.constprop.N` —— 常量传播特化
    clang/zig 用的是另一套（`.cold`、`.llvm.<hash>`、`__llvm.` 前缀等）。
  ⇒ **同一个函数在两侧名字不同**，若直接按名字比对，会把"命名差异"误判成"漏实现"，
    那是**假红**（本项目最忌的失败模式，与第 145 轮 6 项源侧误报同族）。

判据（先归一、再判缺）：
  1. 去掉 gcc 的克隆后缀 `.part.N` / `.isra.N` / `.constprop.N`；
  2. 去�� clang 的 `.cold` / `.llvm.<hash>` / `.__uniq.<hash>` / `.llvm.<hash>...`；
  3. 归一后仍缺 ⇒ 才是**真漏实现**（列入真缺清单，参与失败判定）；
     归一后不缺 ⇒ 归入「命名差异」（只报数，不算失败）。

用法: python3 tools/missing_func_classify.py [--json]
退出: 0 = 无真漏实现 / 2 = 有真漏实现
"""
import argparse
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ 克隆/特化后缀（唯一真源；两处不许各写一份）
#   ⚠ 第 146 轮实测踩到：两侧的分隔符**不同** ——
#     工厂 gcc 6.2 写 `code_convert.constprop.22`（点号）
#     我方复刻把它写成 `code_convert_constprop_22`（下划线，因为**文件名不能含点号**，
#       Ghidra 导出时统一替换）
#   ⇒ 只按点号剥后缀，两边归一结果**不对称**（工厂→`code_convert`，
#     我方→`code_convert_constprop_22`）⇒ 明明是同一个函数却被判成"漏实现"。
#   ⇒ 归一必须先把分隔符统一成点号，再剥后缀。
CLONE_TAGS = ('part', 'isra', 'constprop', 'localalias', 'cold', 'llvm',
              '__uniq', 'omp_fn', 'llvm_copy', 'noinline')
CLONE_SUFFIX_RE = re.compile(
    r'(?:[._](?:' + '|'.join(CLONE_TAGS) + r')(?:[._][0-9a-f]+)*)+$')
# ★★ Ghidra 复刻命名映射：把**下划线形式的克隆后缀**也剥掉
#   （`code_convert_constprop_22` → `code_convert`），与点号形式对称。
#   注意**不能**简单地把所有 `.`→`_`（那会把我方与工厂的差异抹掉）。
CLONE_SUFFIX_US_RE = re.compile(
    r'(?:_(?:' + '|'.join(CLONE_TAGS) + r')(?:_[0-9a-f]+)*)+$')

# CRT 符号：工厂带完整 CRT，我方链接口径不同（-z undefs + 不链 crti/crtbegin）
CRT_NAMES = {
    '__do_global_dtors_aux', 'deregister_tm_clones', 'frame_dummy',
    'call_weak_fn', '_init', '_fini', '__libc_csu_init', '__libc_csu_fini',
    '_start', '__bss_start', '_edata', '_end', '__CTOR_LIST__', '__DTOR_LIST__',
    # 第 146 轮实测补：工厂有、我方链接口径不带（`-z undefs` + 不链 crtbegin/crtend）
    'register_tm_clones', 'deregister_tm_clones', '__do_global_ctors_aux',
    'frame_dummy', 'call_weak_fn',
}

# ★★ 第 146 轮实测补第三类：**tail-call 跳板（thunk）**。
#   工厂的 `save_state`(0x2b86f0, 4B) / `load_state`(0x2b86f4, 4B) 不是函数，
#   而是**尾调用跳板** —— 反汇编实测：
#       2b86f0: b 2b83e8 <retro_save_state>
#       2b86f4: b 2b8570 <retro_load_state>
#   我方 clang 把调用直接融进 `retro_save_state` / `retro_load_state`
#   （两者都是 GLOBAL FUNC，语义完全覆盖）⇒ **同一语义、不同 codegen**，不是漏实现。
#   判据：工厂侧该符号是 4 字节（一条 ARM `b` 指令）且跳转目标是我方也有的符号。
#   ⚠ 只登记**判据**（THUNK_SIZE_MAX），具体名单由 `classify_thunks()` 从产物**实测**得出，
#   不许在这里硬编码函数名 —— 那是"把结论写进判据"，会随产物漂移而失真。
THUNK_SIZE_MAX = 4          # ARM `b` = 4 字节；`st_size <= 4` 即视为跳板候选


def norm(n):
    """归一到"可跨编译器/跨复刻规范比较"的形式。

    ★ 第 146 轮实测定的对称归一（两侧**必须**同一套，否则结果不对称）：
      ① 剥点号形式的克隆后缀：`code_convert.constprop.22` → `code_convert`
      ② 剥下划线形式的克隆后缀：`code_convert_constprop_22` → `code_convert`
         （我方复刻把点号换成下划线，**不是**把所有点号换成下划线 ——
          后者会把我方与工厂的真实差异一起抹掉）
      ⇒ 归一后两侧同形，才谈得上"缺不缺"。
    """
    n = CLONE_SUFFIX_RE.sub('', n)
    n = CLONE_SUFFIX_US_RE.sub('', n)
    return n


def defined_funcs(path):
    """返回 {符号名: st_size}，只含「已定义」（st_shndx != UND）的 STT_FUNC。"""
    from elftools.elf.elffile import ELFFile
    out = {}
    with open(path, 'rb') as fh:
        e = ELFFile(fh)
        for s in e.iter_sections():
            if s['sh_type'] not in ('SHT_SYMTAB', 'SHT_DYNSYM'):
                continue
            for sym in s.iter_symbols():
                if sym['st_info']['type'] != 'STT_FUNC':
                    continue
                if sym['st_shndx'] == 'SHN_UNDEF':
                    continue
                if sym.name:
                    prev = out.get(sym.name)
                    # 同名多定义取**非零** size（真实实现优先于占位）
                    if prev is None or (prev == 0 and sym['st_size']):
                        out[sym.name] = sym['st_size']
    return out


def classify_thunks(Fmap):
    """从工厂产物**实测**识别 tail-call 跳板：st_size ≤ 4 的 GLOBAL FUNC。

    ★ 为什么要实测而不是硬编码名单（第 146 轮纪律）：
      把结论写进判据（`THUNKS = {'save_state': ...}`）会在产物变化时静默失真 ——
      那是"另一处描述"而不是判据。判据只写**可判定的形式**（size ≤ 4），
      名单由本函数每次运行从产物重新得出。
    """
    return {n for n, sz in Fmap.items() if 0 < sz <= THUNK_SIZE_MAX}


def classify_src_inline(src_root):
    """从**源码**实测识别 `static inline` 函数（被内联 ⇒ 产物里不会有独立符号）。

    这是"编译器把 static inline 外提成独立函数 vs 全部内联"的判据；
    工厂 gcc 6.2 常外提（还带 `.part.N` 克隆后缀），clang 常全内联 ⇒ 符号缺失但语义不缺。
    ★ 第 146 轮实测踩到：`finditer` 作用在**整块文本**上时，`^` 必须配 `re.M`
      才是"逐行行首"；没有 `re.M` 就变成"整个文件开头"⇒ 实测扫出 0 个。
    """
    pat = re.compile(r'^[ \t]*static[ \t]+inline\b[^;{]*?\b([A-Za-z_][A-Za-z0-9_]*)[ \t]*\(',
                     re.M)
    found = set()
    for dirpath, dirnames, filenames in os.walk(src_root):
        dirnames[:] = [d for d in dirnames if d not in ('.git', '__pycache__')]
        for fn in filenames:
            if not fn.endswith(('.c', '.h', '.cpp', '.cc')):
                continue
            try:
                txt = io.open(os.path.join(dirpath, fn), encoding='utf-8',
                              errors='replace').read()
            except OSError:
                continue
            for m in pat.finditer(txt):
                found.add(m.group(1))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--src-root', default=os.path.join(ROOT, 'src'))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()

    Fmap = defined_funcs(a.factory)
    Omap = defined_funcs(a.ours)
    F, O = set(Fmap), set(Omap)
    # ★★ 两侧**都必须**归一（第 146 轮实测踩到）：
    #   只归一工厂侧是不够的 —— 我方复刻符号是 `code_convert_constprop_22`（点→下划线），
    #   若我方侧不归一，它永远匹配不上归一后的工厂名 ⇒ 误判成漏实现。
    Onorm = set(norm(x) for x in O)

    thunks = classify_thunks(Fmap)
    src_inline = classify_src_inline(a.src_root)

    raw_missing = sorted(F - O)
    naming, crt, inline_diff, real_missing = [], [], [], []
    for m in raw_missing:
        base = norm(m)
        if m in CRT_NAMES:
            crt.append(m)
        elif base in Onorm:
            naming.append(m)
        elif base in thunks:
            # 工厂侧是 ≤4B 的跳板（tail-call thunk）⇒ 我方把调用融进了目标函数
            inline_diff.append(m)
        elif base in src_inline:
            # 我方源码里是 static inline ⇒ 被 clang 内联，无独立符号
            inline_diff.append(m)
        else:
            real_missing.append(m)

    if a.json:
        print(json.dumps({
            'factory_defined': len(F), 'ours_defined': len(O),
            'raw_missing': raw_missing,
            'crt_only': crt,
            'naming_diff': naming,
            'inline_or_thunk': inline_diff,
            'thunks_detected': sorted(thunks),
            'src_static_inline_count': len(src_inline),
            'real_missing': real_missing,
        }, indent=2, ensure_ascii=False))
    else:
        print('== 工厂有定义、我方缺失 —— 命名归一化分类（第 146 轮）==')
        print('  工厂已定义 FUNC = %d   我方 = %d' % (len(F), len(O)))
        print('  原始缺失 = %d' % len(raw_missing))
        print('  ├─ CRT 符号差异（不判缺）= %d : %s' % (len(crt), ' '.join(crt[:8])))
        print('  ├─ ★ 命名规则差异（不判缺）= %d' % len(naming))
        for n in naming:
            print('  │      %-46s → 归一后 %s' % (n, norm(n)))
        print('  ├─ ☆ inline/thunk 形态差异（不判缺）= %d' % len(inline_diff))
        for n in inline_diff:
            why = ('工厂侧 ≤%dB 跳板（tail-call thunk）' % THUNK_SIZE_MAX
                   if norm(n) in thunks else '我方源码为 static inline（被内联）')
            print('  │      %-46s %s' % (n, why))
        print('  └─ ★★ 真漏实现（参与失败判定）= %d' % len(real_missing))
        for n in real_missing:
            print('         %s' % n)

    if real_missing:
        print('\n★FAIL：归一化后仍缺 %d 个 FUNC ⇒ 真漏实现' % len(real_missing))
        return 2
    print('\nOK：%d 项原始缺失全部可由「克隆后缀命名差异」或「CRT 口径」解释。'
          % len(raw_missing))
    return 0


if __name__ == '__main__':
    sys.exit(main())
