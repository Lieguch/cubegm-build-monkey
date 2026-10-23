#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core_retro_syms.py —— 零 ARM 执行环境对拍厂商 core .so 的 retro_* 导出。

为什么需要它（R240）：判定 FBA_Load「unsupport.」三条件里，第②条
（Load_Proc1 的 dlsym 清单缺项）是否可能失败，**不需要 qemu**——直接读 .dynsym 即可：
Load_Proc1 需要 core 导出 6 个符号（retro_set_video_refresh / _audio_sample_batch /
_input_state / _environment / _input_poll / retro_init），缺一即 run_process→0→unsupport。

用法：
    python3 tools/core_retro_syms.py <core1.so> [core2.so] ...
输出每个 core 的 defined retro_* 全集 + 对「frontend 必需清单」的缺失项。
"""
import struct
import sys

NEED = [
    'retro_is_support', 'retro_load_game', 'retro_set_progress_callback',
    'retro_set_video_refresh', 'retro_set_audio_sample_batch', 'retro_set_input_state',
    'retro_set_environment', 'retro_set_input_poll', 'retro_init',
    'retro_set_controller_port_device', 'retro_run', 'retro_deinit', 'retro_unload_game',
    'retro_get_memory_data', 'retro_get_memory_size', 'retro_save_state', 'retro_load_state',
]


def defined_syms(path):
    with open(path, 'rb') as f:
        d = f.read()
    if d[:4] != b'\x7fELF' or d[4] != 1:
        raise ValueError('%s: not ELF32' % path)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    secs = [struct.unpack_from('<IIIIIIIIII', d, e_shoff + i * e_shentsize)
            for i in range(e_shnum)]
    shstr_off = secs[e_shstrndx][4]

    def sname(i):
        seg = d[shstr_off + secs[i][0]: shstr_off + secs[i][0] + 256]
        return seg.split(b'\x00')[0].decode('latin1', 'replace')

    names = [sname(i) for i in range(e_shnum)]
    if '.dynsym' not in names or '.dynstr' not in names:
        return set(), set()
    ds = secs[names.index('.dynsym')]
    dstr = secs[names.index('.dynstr')]
    ds_off, ds_size = ds[4], ds[5]
    stro = dstr[4]
    entsz = ds[9] or 16
    defined, undefined = set(), set()
    for i in range(ds_size // entsz):
        o = ds_off + i * entsz
        st_name, _val, _sz, _info, _oth, st_shndx = struct.unpack_from('<IIIBBH', d, o)
        if st_name == 0:
            continue
        s = d[stro + st_name: stro + st_name + 128].split(b'\x00')[0].decode('latin1', 'replace')
        (undefined if st_shndx == 0 else defined).add(s)
    return defined, undefined


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for p in argv:
        defined, undefined = defined_syms(p)
        retro = sorted(x for x in defined if x.startswith('retro_'))
        miss = [k for k in NEED if k not in defined]
        print('== %s ==' % p, flush=True)
        print('   defined retro_* (%d): %s' % (len(retro), ' '.join(retro)), flush=True)
        print('   MISSING (frontend-need %d): %s' % (len(NEED), miss if miss else 'NONE'), flush=True)
        print(flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))