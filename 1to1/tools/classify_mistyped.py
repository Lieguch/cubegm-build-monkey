import re, glob

names = ["DAT_003af28c","DAT_003af290","DAT_003af294","DAT_003af298","DAT_003af29c",
"DAT_003af2a8","DAT_003af2ac","DAT_003af2b0","DAT_003af2b4","DAT_003af2b8",
"log_file_fp","scr_data","CRU","GRF","GPIO0","GPIO1","GPIO2","handle","fontbuffer",
"scrbuf","bimapFilebuffer","rotation_buff","g_sfc_reg","ZIP_BUF","romfile","scr_buf"]

# 检查每个 name 的使用形态：下标 / (int)cast / 纯指针
srcs = {}
for f in glob.glob('src/proprietary/*/*.c', recursive=True):
    srcs[f] = open(f, encoding='utf-8', errors='replace').read()

for n in names:
    idx = []; cast = []; pureptr = []
    for f, s in srcs.items():
        for m in re.finditer(re.escape(n) + r'\s*\[', s):
            idx.append(f)
        for m in re.finditer(r'\(\s*(?:int|gh_u4|gh_uint|long)\s*\)\s*' + re.escape(n), s):
            cast.append(f)
        # 纯指针用法： = 结果 / 传参
        if re.search(re.escape(n) + r'\s*=\s*(?:malloc|fopen|mmap|dlopen|calloc|realloc)', s):
            pureptr.append(f)
        if re.search(r'(?:free|munmap|fclose)\s*\(\s*' + re.escape(n), s):
            pureptr.append(f)
    has_idx = bool(idx)
    has_cast = bool(cast)
    # 分类
    if has_idx and not has_cast:
        verdict = 'MIXED: 下标+指针 → 需 blob+字节数组兜底'
    elif has_cast:
        verdict = 'HAS_CAST: 指针+(int)转型 → void* 应可行，但需检下标是否走转型'
    else:
        verdict = 'PURE_PTR: 纯指针 → 直接 void*'
    print(f'{n:20s} idx_files={len(idx)} cast_files={len(cast)} ptr_files={len(pureptr)} → {verdict}')
