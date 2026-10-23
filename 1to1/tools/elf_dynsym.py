#!/usr/bin/env python3
# elf_dynsym.py —— 解析 ELF 动态符号表，对拍 core .so 的 retro_* 导出（零 ARM 执行环境）
import sys, struct

def parse(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'\x7fELF', "not ELF"
    eiclass = d[4]
    assert eiclass == 1, "only ELF32 here (class=%d)" % eiclass
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 46)
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    sections = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        sections.append(struct.unpack_from('<IIIIIIIIII', d, o))
    shstr_off = sections[e_shstrndx][4]
    def shstr(idx):
        s = d[shstr_off + idx:]
        return s.split(b'\x00')[0].decode('latin1')
    names = [shstr(sections[i][0]) for i in range(e_shnum)]
    if '.dynsym' not in names or '.dynstr' not in names:
        return {}, names
    ds = sections[names.index('.dynsym')]
    dstr = sections[names.index('.dynstr')]
    ds_off, ds_size = ds[4], ds[5]
    str_off = dstr[4]
    entsz = ds[9] or 16
    n = ds_size // entsz
    syms = {}
    for i in range(n):
        o = ds_off + i * entsz
        st_name, st_value, st_size, st_info, _, st_shndx = struct.unpack_from('<IIIBBH', d, o)
        if st_name == 0:
            continue
        nm = d[str_off + st_name:].split(b'\x00')[0].decode('latin1')
        syms[nm] = dict(und=(st_shndx == 0), val=st_value, size=st_size)
    return syms, names

NEED = ['retro_set_video_refresh', 'retro_set_audio_sample_batch', 'retro_set_input_state',
        'retro_set_environment', 'retro_set_input_poll', 'retro_init',
        'retro_is_support', 'retro_load_game', 'retro_set_progress_callback',
        'retro_get_memory_data', 'retro_get_memory_size', 'retro_save_state', 'retro_load_state',
        'retro_run', 'retro_deinit', 'retro_unload_game', 'retro_set_controller_port_device']

if __name__ == '__main__':
    paths = sys.argv[1:]
    if not paths:
        print("usage: elf_dynsym.py <core.so> [...]")
        sys.exit(2)
    for p in paths:
        syms, names = parse(p)
        defined = {k for k, v in syms.items() if not v['und']}
        retro = sorted(k for k in defined if k.startswith('retro_'))
        print("== %s ==" % p)
        print("   defined retro_* (%d): %s" % (len(retro), " ".join(retro)))
        miss = [k for k in NEED if k not in defined]
        print("   MISSING (of frontend-required %d): %s" % (len(NEED), miss if miss else "NONE"))
        print()