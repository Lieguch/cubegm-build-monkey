#!/usr/bin/env python3
"""
link_audit.py — P3 链接就绪审计（符号层面）。

输入：`tools/elf_syms.py` 对全部 .o 输出的 TSV（DEFINED/COMMON/UNDEF）。
输出（stdout，同时写报告）：
  1. 重复定义（同一符号被 >1 个对象定义）—— 链接硬阻断
  2. 本地总定义/引用数
  3. 未解析引用（本体重无定义）按来源分类：
       - upstream : 命中 `upstream/factory_component_funcs.json` 的组件函数
       - libc     : 已知 glibc/编译器运行时/硬件库符号（由链接期 -lc/-ldl/-lm/-lpthread 提供）
       - eabi     : ARM EABI / libgcc 运行时（__aeabi_*、__gnu_*、_Unwind_*）
       - MISSING  : 既非 upstream 也非已知运行时 —— 真正的缺口
退出码：0 = 无重复定义且无 MISSING；2 = 存在阻断项
"""
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, 'upstream', 'factory_component_funcs.json')

# 已知由 glibc / libgcc / 硬件库在链接期提供的符号前缀与精确名
LIBC_EXACT = {
    'malloc', 'calloc', 'realloc', 'free', 'memcpy', 'memset', 'memmove', 'memcmp',
    'strlen', 'strcpy', 'strncpy', 'strcat', 'strcmp', 'strncmp', 'strstr', 'strchr',
    'strrchr', 'strtok', 'strdup', 'strerror', 'strspn', 'strcspn', 'strpbrk',
    'sprintf', 'snprintf', 'vsnprintf', 'sscanf', 'printf', 'fprintf', 'vfprintf',
    'puts', 'putchar', 'fputs', 'fputc', 'fwrite', 'fread', 'fopen', 'fclose',
    'fseek', 'ftell', 'fflush', 'feof', 'ferror', 'fileno', 'fsync', 'fgets', 'fgetc',
    'gettimeofday', 'time', 'localtime', 'gmtime', 'mktime', 'clock_gettime', 'usleep',
    'nanosleep', 'sleep', 'access', 'open', 'close', 'read', 'write', 'lseek', 'ioctl',
    'stat', 'fstat', 'lstat', 'mkdir', 'unlink', 'rename', 'remove', 'rmdir', 'opendir',
    'readdir', 'closedir', 'chdir', 'getcwd', 'realpath', 'system', 'exit', 'abort',
    'atexit', 'getenv', 'setenv', 'putenv', 'atoi', 'atol', 'strtol', 'strtoul',
    'strtod', 'rand', 'srand', 'abs', 'labs', 'qsort', 'bsearch', 'div',
    'pthread_create', 'pthread_join', 'pthread_mutex_init', 'pthread_mutex_lock',
    'pthread_mutex_unlock', 'pthread_mutex_destroy', 'pthread_cond_init',
    'pthread_cond_wait', 'pthread_cond_signal', 'pthread_cond_broadcast',
    'pthread_attr_init', 'pthread_attr_setstacksize', 'pthread_detach',
    'pthread_self', 'pthread_exit', 'sem_init', 'sem_wait', 'sem_post', 'sem_destroy',
    'dlopen', 'dlclose', 'dlsym', 'dlerror',
    'shmget', 'shmat', 'shmdt', 'shmctl',
    'mmap', 'munmap', 'msync', 'mprotect',
    'sin', 'cos', 'tan', 'sqrt', 'pow', 'floor', 'ceil', 'fabs', 'atan2', 'fmod',
    'log', 'log10', 'exp', 'round', 'trunc',
    'iconv', 'iconv_open', 'iconv_close',
    'gmtime_r', 'localtime_r', 'difftime', 'setlocale',
    'tolower', 'toupper', 'isdigit', 'isalpha', 'isspace', 'isupper', 'islower',
    # P3 二期补充（实测 UNDEF 中出现，均为 libc/POSIX）
    'dup', 'readlink', 'rewind', 'scandir', 'alphasort', 'stpcpy', 'bcmp',
    'futimens', 'utimensat', 'strcasecmp', 'strncasecmp', '__errno_location',
    'putc', 'getc', 'ungetc', 'setvbuf', 'setbuf', 'compress', 'uncompress', 'inflateInit',
    'acos', 'asin', 'atan', 'ceilf', 'floorf', 'sqrtf', 'fabsf', 'powf', 'logf',
    'pthread_getspecific', 'pthread_setspecific', 'pthread_key_create', 'pthread_key_delete',
    'pthread_once', 'locale_charset', 'nl_langinfo', 'getc_unlocked', 'putc_unlocked',
    '__isoc99_sscanf', '__isoc99_scanf', 'isgraph', 'ispunct', 'iscntrl',
    'memchr', 'strcasestr', 'asprintf', 'vasprintf', 'fdopen', 'fileno',
}
# libstdc++ 供应（工厂 UNDEF 同款：operator new/delete 及数组变体）
LIBSTDCXX = {'_Znwj', '_ZdlPv', '_Znaj', '_ZdaPv', '_ZnwjRKSt9nothrow_t', '_ZdlPvm'}
# CRT 供应（crt1.o / crtbegin.o）
# GCC -D_FORTIFY_SOURCE / -fstack-protector 引入的 glibc 符号（CI 用 GCC 会大量出现）
FORTIFY = {'__assert_fail', '__stack_chk_fail', '__stack_chk_guard', '__stack_chk_fail_local',
           '__memcpy_chk', '__memset_chk', '__memmove_chk', '__strcpy_chk', '__strncpy_chk',
           '__strcat_chk', '__stpcpy_chk', '__sprintf_chk', '__snprintf_chk', '__vsnprintf_chk',
           '__printf_chk', '__fprintf_chk', '__vfprintf_chk', '__fread_chk', '__read_chk',
           '__fgets_chk', '__gets_chk', '__fwrite_chk', '__syslog_chk'}
CRT_SYMS = {'_init', '_fini', '__frame_dummy_init_array_entry',
            '__do_global_dtors_aux_fini_array_entry', '__libc_csu_init',
            '__libc_csu_fini', '_IO_stdin_used', '__data_start', '_edata',
            '__bss_start', '_end', '__dso_handle'}
LIBC_PREFIX = (
    '__ctype_', 'stdout', 'stderr', 'stdin',
    'snd_',        # ALSA
    'drm', 'DRM',  # DRM/KMS
    'EGL', 'gl', 'gl3', 'gles',  # GLES
    'SDL_',
)
# ARM EABI / libgcc 运行时
EABI_PREFIX = ('__aeabi_', '__gnu_', '_Unwind_', '__div', '__udiv', '__mod',
               '__mul', '__cmp', '__float', '__fix', '__add', '__sub', '__neg')


def load_manifest():
    names = set()
    try:
        d = json.load(open(MANIFEST, encoding='utf-8'))
    except Exception:
        return names
    for comp, lst in d.items():
        for it in lst or []:
            if isinstance(it, dict) and it.get('name'):
                names.add(it['name'])
    return names


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    tsv = sys.argv[1]
    report = sys.argv[2] if len(sys.argv) > 2 else None

    defined = defaultdict(set)   # sym -> {obj}   仅 GLOBAL/WEAK（LOCAL 不参与重复判定）
    local = defaultdict(set)     # sym -> {obj}   LOCAL 符号（.L.str / $a / $d ...）
    common = defaultdict(set)
    undef = defaultdict(set)

    for line in open(tsv, encoding='utf-8', errors='replace'):
        parts = line.rstrip('\n').split('\t')
        if len(parts) != 3:
            continue
        kind, sym, obj = parts
        if kind == 'DEFINED':
            defined[sym].add(obj)
        elif kind == 'LOCAL':
            local[sym].add(obj)
        elif kind == 'COMMON':
            common[sym].add(obj)
        elif kind == 'UNDEF':
            undef[sym].add(obj)

    upstream = load_manifest()
    local_all = set(defined) | set(common)

    dups = {s: sorted(o) for s, o in defined.items() if len(o) > 1}
    unresolved = {}
    for s in undef:
        if s in local_all:
            continue
        if s in upstream:
            unresolved[s] = 'upstream'
        elif s in LIBSTDCXX:
            unresolved[s] = 'libstdc++'
        elif s in FORTIFY:
            unresolved[s] = 'libc'
        elif s in CRT_SYMS:
            unresolved[s] = 'crt'
        elif s in LIBC_EXACT or s.startswith(LIBC_PREFIX):
            unresolved[s] = 'libc'
        elif s.startswith(EABI_PREFIX):
            unresolved[s] = 'eabi'
        else:
            unresolved[s] = 'MISSING'

    L = []
    A = L.append
    A('=' * 70)
    A('P3 链接就绪审计（符号层）')
    A('=' * 70)
    A('对象数            : %d' % len({o for os_ in defined.values() for o in os_} |
                                     {o for os_ in undef.values() for o in os_}))
    A('本体重定义符号数  : %d   （仅 GLOBAL/WEAK，含 OBJECT/FUNC/ABS）' % len(defined))
    A('本体 LOCAL 符号数  : %d   （文件作用域，重名合法，不参与重复判定）' % len(local))
    A('本体暂定定义数    : %d   （SHN_COMMON，链接期合并）' % len(common))
    A('本体引用符号数    : %d' % len(undef))
    A('')
    A('【1】重复定义（链接硬阻断）: %d' % len(dups))
    for s, objs in sorted(dups.items())[:60]:
        A('   %-44s %s' % (s[:44], ', '.join(os.path.basename(x) for x in objs)[:120]))
    A('')
    cats = defaultdict(list)
    for s, c in unresolved.items():
        cats[c].append(s)
    A('【2】未解析引用（本体重无定义）: %d' % len(unresolved))
    for c in ('MISSING', 'upstream', 'libstdc++', 'libc', 'eabi'):
        v = sorted(cats.get(c, []))
        A('   %-9s : %d' % (c, len(v)))
    A('')
    A('【3】MISSING 明细（既非上游组件、也非已知运行时库）')
    miss = sorted(cats.get('MISSING', []))
    if not miss:
        A('   （无）')
    for s in miss[:200]:
        A('   %s' % s)
    if len(miss) > 200:
        A('   ... 共 %d 个（完整清单见 report/_link_missing.txt）' % len(miss))
    A('')
    A('【4】upstream 明细（需从 GitHub 拉取组件源码后即可解析）')
    for s in sorted(cats.get('upstream', []))[:80]:
        A('   %s' % s)
    A('')
    A('【5】libc/eabi 样本（链接期由 -lc/-ldl/-lm/-lpthread/-lgcc 提供）')
    for s in sorted(cats.get('libc', []))[:30]:
        A('   %s' % s)
    A('   ... eabi: %s' % ', '.join(sorted(cats.get('eabi', []))[:12]))
    A('')
    blockers = len(dups) + len(miss)
    A('===== 结论：重复定义 %d，MISSING %d ⇒ %s =====' %
      (len(dups), len(miss), '链接前置条件已满足' if blockers == 0 else '仍有阻断项'))

    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    if report:
        os.makedirs(os.path.dirname(report), exist_ok=True)
        open(report, 'w', encoding='utf-8').write(txt)
        # 机器可读清单（供 data_provision_plan.py 消费）
        mp = os.path.join(os.path.dirname(report), '_link_missing.txt')
        with open(mp, 'w', encoding='utf-8') as f:
            for c in ('MISSING', 'upstream'):
                for s in sorted(cats.get(c, [])):
                    f.write('%s\t%s\n' % (c, s))
    return 0 if blockers == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
