#!/usr/bin/env python3
"""stale_artifact_gate.py — 中间产物**新鲜度**门禁（防"陈旧 .o 污染判据"）。

★ 为什么需要（第 151 轮血泪，本项目最隐蔽的一类假信号）：
  第 150 轮我用「只替换一个 .o 后重链」做单变量 A/B，得出
  「净账 −1 ⇒ `-fno-builtin-malloc` 不采纳」。
  第 151 轮追查发现**那个结论是假的**：
    · `build/upstream/mp3_buffers.o` 的 mtime = **08:59**，
      而 `src/upstream/mp3/real/buffers.c` = **13:31**（第 144 轮改过）
      ⇒ **上游对象比源码旧 4.5 小时**，里面还是**修复前**的版本；
    · 于是「用陈旧 upstream 链出来的产物」里 `xmp3_AllocateBuffers` 仍指向 memset PLT
      ⇒ batch 报「新增 2 个 DIVERGE」⇒ 被我误读成"flag 造成回退"。
  ★ 真正的元凶是**陈旧中间产物**，不是 flag，也不是链接器
    （实测：同一份 obj 连续重链两次 sha **完全相同** ⇒ 链接可复现）。

判据（纯机械，零猜测）：
  对每个参与构建的 `.o`，比较它与其**源文件**的 mtime；
  若 `.o` 早于源文件 ⇒ **陈旧** ⇒ 判失败。
  `diff_exec.py` 里已有 `tools/check_obj_fresh.py`，本门禁是**补上 upstream 侧**
  （旧脚本只查 `build/obj`，正是漏掉本次元凶的原因）。

★ 2026-10-18（R205）根修「假红」（与假绿同族，都必须根除）：
  旧实现把配对写成「整个 obj 目录 × 单个源目录」，但 `build/upstream/` **混装 4 个库
  25 个 .o**（stb_*/mxml_*/mp3_*/libiconv_*）⇒ 每个库都拿**别的库的 .o** 去比 mtime：
  stb 源(10-04) 最新时其余 24 个 .o(10-01) 全被判"陈旧" ⇒ 门禁**永远 FAIL（假红）**。
  改法：按 .o **文件名前缀**路由到各自源目录，每个 .o 只和它自己的库比。

用法: python3 tools/stale_artifact_gate.py [--fix-hint]
退出: 0 = 全部新鲜 / 2 = 有陈旧对象
"""
import argparse
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ★ 2026-10-18（R205）：obj 目录 → 归属解析规则。
#   三元组 = (obj目录, 前缀→源 映射, 默认源)。前缀映射 None ⇒ 整目录走默认源（单一源）。
#   必须与构建脚本同源：build_upstream.sh 各组件 -o 输出名 / link_audit.sh:19 SRCDIR。
OBJ_SRC_RULES = [
    ('build/obj', None, 'src/proprietary'),
    ('build/upstream', [
        ('stb_',       'src/upstream/stb'),
        ('mxml_',      'src/upstream/mxml'),
        ('mp3_',       'src/upstream/mp3'),
        ('libiconv_',  'src/upstream/libiconv17'),
    ], None),
    ('src/upstream/xunzip', None, 'src/upstream/xunzip'),
]


def newest_src_mtime(src_dir):
    """该目录下**最新的** .c/.h mtime（头文件也影响编译 ⇒ 计入）。"""
    newest = 0.0
    newest_f = None
    for dp, dn, fn in os.walk(os.path.join(ROOT, src_dir)):
        dn[:] = [d for d in dn if d not in ('.git', '__pycache__')]
        for f in fn:
            if f.endswith(('.c', '.h', '.cpp', '.cc', '.s', '.S')):
                p = os.path.join(dp, f)
                try:
                    m = os.path.getmtime(p)
                except OSError:
                    continue
                if m > newest:
                    newest, newest_f = m, os.path.relpath(p, ROOT)
    return newest, newest_f


def check_group(objd, src_dir, obj_files, stale_out):
    """对 obj 目录里一组 .o，与 src_dir 最新源 mtime 比对，报告陈旧。"""
    src_m, src_f = newest_src_mtime(src_dir)
    if not src_m:
        return
    old = []
    for name in obj_files:
        p = os.path.join(ROOT, objd, name)
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if m < src_m:
            old.append((name, m))
    tag = '%-28s ← %-24s' % (objd, src_dir)
    if old:
        print('  ★陈旧 %s : %d/%d 个 .o 早于 %s'
              % (tag, len(old), len(obj_files), src_f))
        for f, m in old[:5]:
            print('        %-44s %s' % (f, time.strftime('%m-%d %H:%M', time.localtime(m))))
        if len(old) > 5:
            print('        ...（另 %d 个）' % (len(old) - 5))
        stale_out.append((objd, src_dir, len(old)))
    else:
        print('  ✓新鲜 %-28s ← %-24s（%d .o）' % (objd, src_dir, len(obj_files)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix-hint', action='store_true', help='打印修复命令')
    a = ap.parse_args()

    print('== stale_artifact_gate（第 151 轮引入 / R205 修假红）==')
    print('  判据：.o 的 mtime 必须**不早于**其归属源目录里最新的源文件')
    stale = []
    for objd, prefix_map, default_src in OBJ_SRC_RULES:
        obj_abs = os.path.join(ROOT, objd)
        if not os.path.isdir(obj_abs):
            print('  [缺目录] %s' % objd)
            continue
        obs = sorted(f for f in os.listdir(obj_abs) if f.endswith('.o'))
        if not obs:
            print('  [无 .o] %s' % objd)
            continue
        if prefix_map is None:
            check_group(objd, default_src, obs, stale)
        else:
            buckets = {}
            unknown = []
            for name in obs:
                src = None
                for prefix, s in prefix_map:
                    if name.startswith(prefix):
                        src = s
                        break
                if src is None:
                    unknown.append(name)
                else:
                    buckets.setdefault(src, []).append(name)
            for src_dir, files in sorted(buckets.items()):
                check_group(objd, src_dir, files, stale)
            for name in unknown:
                print('  !! 未识别前缀：%s（不在构建脚本输出名内，请核对）' % name)
                stale.append((objd, '?' + name, 1))

    print('')
    if stale:
        print('★FAIL：%d 个对象组含陈旧 .o ⇒ 判据会被污染' % len(stale))
        if a.fix_hint:
            print('')
            print('  修复（按依赖顺序，云开发/CI 上执行）：')
            print('    sh tools/cnb_env.sh          # 或下面两条，等价')
            print('    CC="<zig> cc" sh tools/build_upstream.sh build/upstream')
            print('    OPT=-Os sh tools/link_audit.sh /tmp/la.txt')
            print('    sh tools/link_full.sh build/rkgame.rebuilt.elf')
        return 2
    print('OK：全部对象新鲜。')
    return 0


if __name__ == '__main__':
    sys.exit(main())