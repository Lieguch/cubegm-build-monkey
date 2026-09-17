#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shim 日志格式化器自检（技能铁律 101 的落地）。

为什么需要：
  `tools/guest_shim/fake_mem.c` 里的 `note()` 曾经用 `vsnprintf`，在被拦截的 `fopen`
  内部调用 ⇒ **在 stdio 内部再入 stdio**，实测把 guest 的 FILE 内部结构污染成
  `blx sl, sl=0x3a`（ASCII ':'）的垃圾跳转（场景 E 重建侧崩溃）。
  改成只依赖 `write(2)` 的自包含格式化器之后，**它自己必须被验证**：

  · 直接从 `fake_mem.c` **抽取**格式化器源码（不是复制快照）⇒ 永不腐烂；
  · 在宿主上编译运行，逐用例与 `snprintf` 对拍；
  · `%p` 例外：宿主 printf 约定（Windows：16 位大写无前缀）与 glibc（`0x`+小写）不同，
    故用**显式期望值**，不拿宿主当参照。

用法：
  python tools/shim_fmt_selftest.py [--zig <path>] [--keep]
退出码 0 = 全部用例通过。
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHIM = os.path.join(ROOT, 'tools', 'guest_shim', 'fake_mem.c')
OUT_C = os.path.join(ROOT, 'build', '_fmt_test.c')
OUT_BIN = os.path.join(ROOT, 'build', '_fmt_test.exe')

BEGIN = 'static void raw_write(const char *p, unsigned int n)'
END = 'int munmap(void *addr, size_t len)'

CASES = [
    ('CHK', '"键入 [shim] io #%02d %-8s rc=%-4d %s%s"',
     '1, "fopen", 0, "/sdcard/cubegm//ui_cn.zip", "   x"'),
    ('CHK', '"key2 @0x%08lx = %02x %02x %02x %02x"',
     '(unsigned long)0x3E190C, 0x50, 0x4b, 0x05, 0x06'),
    ('CHK', '"op=0x%04x addr=0x%06x len=%u"', '0x9f, 0x194, 16'),
    ('CHK', '"pc=0x%08lx lr=0x%08lx sp=0x%08lx"',
     '(unsigned long)0x2b3c8, (unsigned long)0x17ec8, (unsigned long)0x40ffe9e0'),
    ('CHK', '"%-11s 0x%08lx %s"', '"lr(caller)", (unsigned long)1, "(none)"'),
    ('CHK', '"[sp+%2d] = 0x%08lx -> %s + 0x%lx"',
     '16, (unsigned long)0x2dd46e, "/sdcard/x", (unsigned long)0x2d546e'),
    ('CHK', '"poison=%u KiB(byte=0x%02x) d=%-4d"', '766, 0xa5, -7'),
    ('CHK', '"neg=%d pct=%% done"', '-12345'),
    ('CHK', '"zero=%02d wide=%04d"', '5, 42'),
    ('CHK', '"%s"', '(const char *)0'),
    ('CHK', '"hex long=%lx u=%lu"',
     '(unsigned long)0xdeadbeefcafeUL, (unsigned long)4294967295UL'),
    # %p：显式期望（宿主约定不同，不能对拍）
    ('EXPLICIT', '"base=%p len=0x%x"', '(void *)0x3fb64000, 0x1000',
     '"base=0x3fb64000 len=0x1000"'),
]

HARNESS_HEAD = '''#include <stdio.h>
#include <stdarg.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <sys/types.h>

static char CAP[8192];
static size_t CAPN;
ssize_t write(int fd, const void *buf, size_t n)
{
    (void)fd;
    memcpy(CAP + CAPN, buf, n);
    CAPN += n;
    return (ssize_t)n;
}
'''

HARNESS_TAIL = '''
static int fail, tot;

#define CHK(fmt, ...) do { \\
        char want[512]; \\
        CAPN = 0; CAP[0] = 0; \\
        snprintf(want, sizeof(want), fmt, ##__VA_ARGS__); \\
        note(fmt, ##__VA_ARGS__); \\
        CAP[CAPN] = 0; tot++; \\
        if (strcmp(want, CAP) != 0) { \\
            fail++; \\
            printf("  FAIL fmt=%-34s\\n       want=[%s]\\n        got=[%s]\\n", #fmt, want, CAP); \\
        } \\
    } while (0)

#define CHK_EXPLICIT(wantstr, fmt, ...) do { \\
        CAPN = 0; CAP[0] = 0; tot++; \\
        note(fmt, ##__VA_ARGS__); \\
        CAP[CAPN] = 0; \\
        if (strcmp(wantstr, CAP) != 0) { \\
            fail++; \\
            printf("  FAIL(显式) fmt=%-34s\\n            want=[%s]\\n             got=[%s]\\n", #fmt, wantstr, CAP); \\
        } \\
    } while (0)

int main(void)
{
    setvbuf(stdout, NULL, _IONBF, 0);
'''


def strip_comments(text):
    """去掉 C 注释后再做符号检查 —— 注释里出现 'printf' 字样是合法的
    （本文件注释大量引用被禁用的旧实现，若不剥注释会误报）。"""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    text = re.sub(r'//[^\n]*', ' ', text)
    return text


def extract_block():
    src = open(SHIM, encoding='utf-8').read()
    i = src.find(BEGIN)
    j = src.find(END)
    if i < 0 or j < 0 or j <= i:
        sys.exit('  [FATAL] 无法从 %s 抽取格式化器块（锚点失配）' % SHIM)
    block = src[i:j]
    # 硬断言：抽取到的块里**不得**出现任何 stdio 调用（这正是本次修复的要害）
    code = strip_comments(block)
    banned = [b for b in ('vsnprintf', 'snprintf', 'printf', 'fputs', 'fwrite',
                          'vprintf', 'asprintf')
              if re.search(r'(?<![A-Za-z0-9_])' + b + r'\s*\(', code)]
    if banned:
        sys.exit('  [FATAL] 格式化器块里仍含 stdio 调用：%s' % banned)
    return block


def build_and_run(zig, keep=False):
    block = extract_block()
    body = [HARNESS_HEAD, block, HARNESS_TAIL]
    for c in CASES:
        if c[0] == 'CHK':
            body.append('    CHK(%s, %s);\n' % (c[1], c[2]))
        else:
            body.append('    CHK_EXPLICIT(%s, %s, %s);\n' % (c[3], c[1], c[2]))
    body.append('    printf("  ---- 自检结果：%d/%d 通过%s\\n", tot - fail, tot,\n'
                '           fail ? "  ★ 有失配" : "  （全绿）");\n')
    body.append('    return fail ? 1 : 0;\n}\n')
    os.makedirs(os.path.dirname(OUT_C), exist_ok=True)
    open(OUT_C, 'w', encoding='utf-8', newline='\n').write(''.join(body))
    print('  抽取格式化器：%d 字节；用例 %d 条' % (len(block), len(CASES)))
    r = subprocess.run([zig, 'cc', '-o', OUT_BIN, OUT_C], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        sys.exit('  [FATAL] 宿主编译失败')
    r = subprocess.run([OUT_BIN], capture_output=True, text=True, timeout=60)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    if not keep:
        for f in (OUT_C, OUT_BIN):
            try:
                os.remove(f)
            except OSError:
                pass
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zig', default=os.environ.get('ZIG_BIN', 'zig'))
    ap.add_argument('--keep', action='store_true')
    a = ap.parse_args()
    rc = build_and_run(a.zig, a.keep)
    print('  shim 日志格式化器自检：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
