#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""driver_stub_coverage.py —— driver.so 假桩覆盖门禁（第 162 轮新增；第 163 轮补产物级判据）。

为什么需要（第 162 轮）
  原厂闭源 driver.so（RK3036G，39844 B）在沙箱无真 DRM/声卡时必崩：
  `gr_init` 拿 NULL 后 `ldr r3,[r3]`。解法是 LD_LIBRARY_PATH 前置
  libdrm.so.2 / libasound.so.2 假桩，把硬件初始化"做成成功"。
  本门禁机械守护"桩必须覆盖 driver.so 的全部需桩 UNDEF"，防 core/driver 升级导致桩漂移。

判据（三腿，按 judging-tool-self-test 的自证要求）
  腿1 源级正例：解析 driver.so 的 .dynsym UNDEF（实测 65 = 17 drm* + 20 snd_pcm_* + 28 libc/其他），
      逐项断言对应桩源文本含 `<sym>(`。真实 drm_stub.c / alsa_stub.c ⇒ 必须 PASS。
  腿2 源级反例：把 drm_stub.c 中含 `drmModeAddFB2(` 的行全删 ⇒ 必须 FAIL 且点名 drmModeAddFB2。
      （没有这一腿，腿1 永远只是"真 PASS"，无从证明它有判别力 —— 防"全绿但无效"。）
  腿3 产物级复跑：把桩真正编译成 armhf DSO，解析**产物的** .dynsym 已导出集合
      （bind ∈ {GLOBAL, WEAK}、非 hidden、st_shndx != 0），断言它是需桩集合的超集。
      源级只管"符号名出现在文本里"，产物级才证明"链接器真的把它导出了"。
      反例由 shell 侧 objcopy --localize-symbol 制造（见 driver_stub_elf_gate.sh）。

分类（权威 = golden/sdcard_min/driver.so 实测，不在本文件写死清单）
  drm*       → libdrm.so.2    ← tools/guest_shim/drm_stub.c
  snd_pcm_*  → libasound.so.2 ← tools/guest_shim/alsa_stub.c
  其余        → rootfs 真实 DSO 提供，无需桩

★ 单一权威：build_libdrm_stub.sh / build_libasound_stub.sh 的 NEED 清单由本工具
  `--print-need` 导出，构建脚本不再写第二份（"同一规则禁止写两处"）。

用法:
  python tools/driver_stub_coverage.py                       # 腿1（源级，默认）
  python tools/driver_stub_coverage.py --elf stub/libdrm.so.2 --elf stub/libasound.so.2
  python tools/driver_stub_coverage.py --selftest [--elf ...] # 腿1+2(+3)，门禁用
  python tools/driver_stub_coverage.py --print-need [drm|alsa]  # 导出需桩清单
  python tools/driver_stub_coverage.py --driver <path>        # 换一份 driver.so
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DRIVER = os.path.join(ROOT, 'golden', 'sdcard_min', 'driver.so')
DRM_SRC = os.path.join(HERE, 'guest_shim', 'drm_stub.c')
ALSA_SRC = os.path.join(HERE, 'guest_shim', 'alsa_stub.c')

STB_GLOBAL, STB_WEAK = 1, 2
VIS_HIDDEN = 2

# ============================================================================
# 私有 ABI 覆盖清单 —— rkgame 通过 dlsym 从 driver.so 绑定的"驱动面"符号。
# ★ 权威来源（不是 hardcode 猜测）：
#   ① golden/sdcard_min/driver.so 的 .dynsym **实测 DEFINED**（第 162 轮，61 项里这 9 项
#      属于 rkgame 的驱动契约面；R165 取证脚本逐项核完）；
#   ② Ghidra 源码调用点：`FUN_0000d678_InitDisplay.c`（video_driver_setting /
#      video_driver_disp_frame / video_driver_setmode / video_driver_get_size、
#      经 run_process_constprop_0("video_drivers_init")）、
#      `FUN_0000db08_InitSound.c`（sound_driver_init / sound_driver_playframe）、
#      `FUN_0000dae0_DeinitDisplay.c`（run_process_constprop_0("video_driver_deinit")）、
#      `FUN_0000dbcc_DeinitSound.c`（run_process_constprop_0("sound_driver_deinit")）。
# ★ 为什么"看 DEFINED 而不是 UNDEF"：这 9 个是 driver.so **自导出**、
#   重建方通过 dlsym 消费 —— 重建 ELF 的 UNDEF 里不会出现它们（变量是重建方的已定义全局）。
#   要盯的是「任何代替/桩化 driver.so 的产物必须把这 9 个符号全数导出」。
#   （R164 结论的记法修正：不等于此前记录的 6 个，那是只抓了 dlsym 字面量、
#    漏了 run_process 携带的 video_drivers_init / video_driver_deinit / sound_driver_deinit。）
# ============================================================================
ABI_SYMS = (
    'video_driver_setting',
    'video_drivers_init',
    'video_driver_disp_frame',
    'video_driver_setmode',
    'video_driver_get_size',
    'video_driver_deinit',
    'sound_driver_init',
    'sound_driver_playframe',
    'sound_driver_deinit',
)


def _sections(d):
    shoff = struct.unpack_from('<I', d, 0x20)[0]
    shentsize = struct.unpack_from('<H', d, 0x2E)[0]
    shnum = struct.unpack_from('<H', d, 0x30)[0]
    return [struct.unpack_from('<10I', d, shoff + i * shentsize)
            for i in range(shnum) if shoff + (i + 1) * shentsize <= len(d)]


def parse_dynsym(path, want):
    """ELF32 .dynsym 解析（零依赖，纯 struct）。

    want='undef'   → 未定义导入（st_shndx == SHN_UNDEF）
    want='defined' → 可对外满足的导出：st_shndx != 0 且 bind ∈ {GLOBAL, WEAK} 且非 hidden
                     ★ 后两个条件是关键：LOCAL/hidden 的"已定义"符号**不能**满足
                       driver.so 的外部 UNDEF 引用，计它为覆盖就是假绿。
    """
    d = open(path, 'rb').read()
    assert d[:4] == b'\x7fELF' and d[4] == 1, '%s 不是 ELF32' % path
    assert d[18:20] == b'\x28\x00', '%s e_machine != EM_ARM(40) —— 桩可能编成了别的架构' % path
    shs = _sections(d)
    ds = next(s for s in shs if s[1] == 11)          # SHT_DYNSYM
    stroff = shs[ds[6]][4]                            # 关联 .dynstr 的 sh_offset
    out = []
    for i in range(ds[5] // 16):                      # sh_size / sizeof(Elf32_Sym)
        st_name, _v, _sz, st_info, st_other, st_shndx = \
            struct.unpack_from('<IIIBBH', d, ds[4] + i * 16)
        if not st_name:
            continue
        end = d.index(b'\x00', stroff + st_name)
        nm = d[stroff + st_name:end].decode('utf-8', 'replace')
        if want == 'undef':
            if st_shndx == 0:
                out.append(nm)
        else:
            bind = st_info >> 4
            if st_shndx != 0 and bind in (STB_GLOBAL, STB_WEAK) \
                    and (st_other & 3) != VIS_HIDDEN:
                out.append(nm)
    return out


def need_stubs(driver_path):
    """返回 (drm, alsa, rest)：driver.so 的需桩符号分类。"""
    undef = sorted(set(parse_dynsym(driver_path, 'undef')))
    drm = [s for s in undef if s.startswith('drm')]
    alsa = [s for s in undef if s.startswith('snd_pcm_')]
    rest = [s for s in undef if s not in set(drm) and s not in set(alsa)]
    return drm, alsa, rest


def load_src(p):
    with open(p, encoding='utf-8', errors='replace') as f:
        return f.read()


def src_has_fn(src, sym):
    """源文本里 `<sym>(` 出现 ⇒ 有该符号的定义/声明形态。"""
    return (sym + '(') in src


def src_check(driver_path):
    """腿1：返回 (rows, missing)，rows = [(sym, 桩源名, ok)]。"""
    drm, alsa, _ = need_stubs(driver_path)
    dsrc, asrc = load_src(DRM_SRC), load_src(ALSA_SRC)
    rows = [(s, 'drm_stub.c', src_has_fn(dsrc, s)) for s in drm] + \
           [(s, 'alsa_stub.c', src_has_fn(asrc, s)) for s in alsa]
    missing = [s for _, _, ok in rows if not ok]
    return rows, missing


def elf_check(driver_path, elves):
    """腿3：返回 (rows, missing)，rows = [(sym, 提供该符号的桩文件名)]。"""
    drm, alsa, _ = need_stubs(driver_path)
    need = drm + alsa
    defs = {}
    for p in elves:
        for s in set(parse_dynsym(p, 'defined')):
            defs.setdefault(s, []).append(os.path.basename(p))
    missing = [s for s in need if s not in defs]
    rows = [(s, ' '.join(defs.get(s, [])) or '--', s not in missing) for s in need]
    return rows, missing


def print_table(rows, missing, label):
    """rows 元素：(sym, 来源说明, ok) —— ok 为真/假，或用 '--' 表示"无人提供"。"""
    print('--- %s：逐项判据 ---' % label)
    for sym, who, ok in rows:
        print('  %s %-40s -> %s' % ('OK ' if ok else 'MISS', sym, who))
    print('需桩 %d 项：已覆盖 %d，缺失 %d' %
          (len(rows), len(rows) - len(missing), len(missing)))
    if missing:
        print('缺失: %s' % ' '.join(missing))


def main():
    argv = sys.argv[1:]

    def has(name):
        return name in argv

    def vals(name):
        return [argv[i + 1] for i, a in enumerate(argv)
                if a == name and i + 1 < len(argv)]

    driver = vals('--driver')[:1] or [DRIVER]
    driver = driver[0]
    elves = vals('--elf')

    # ---- 导出需桩清单（构建脚本的单一权威）----
    for i, a in enumerate(argv):
        if a == '--print-need':
            sub = argv[i + 1] if i + 1 < len(argv) and argv[i + 1] in ('drm', 'alsa', 'private') else ''
            drm, alsa, _ = need_stubs(driver)
            pick = {'drm': drm, 'alsa': alsa, 'private': list(ABI_SYMS),
                    '': drm + alsa}[sub]
            print(' '.join(pick))
            return 0

    # ---- selftest：腿1+2(+3) ----
    if has('--selftest'):
        print('== 腿1：源级正例（真实桩源）==')
        rows, missing = src_check(driver)
        print_table(rows, missing, '源级')
        if missing:
            print('★ 腿1 FAIL：%d 项需桩符号在桩源中找不到' % len(missing))
            return 1
        print('  腿1 PASS')

        print('== 腿2：源级反例（删掉含 drmModeAddFB2( 的行）==')
        bad = '\n'.join(l for l in load_src(DRM_SRC).split('\n') if 'drmModeAddFB2(' not in l)
        drm, _alsa, _r = need_stubs(driver)
        miss2 = [s for s in drm if not src_has_fn(bad, s)]
        if 'drmModeAddFB2' not in miss2:
            print('★ 腿2 假绿：截断源竟没让 drmModeAddFB2 判为缺失（miss=%s）' % miss2)
            return 1
        print('  腿2 PASS（反例正确 FAIL，点名：%s）' % ' '.join(miss2))

        if elves:
            print('== 腿3：产物级复跑（%d 个桩 DSO）==' % len(elves))
            rows, missing = elf_check(driver, elves)
            print_table(rows, missing, '产物级 .dynsym')
            if missing:
                print('★ 腿3 FAIL：%d 项需桩符号未在产物 .dynsym 中导出' % len(missing))
                return 1
            print('  腿3 PASS')
            print('门禁 selftest PASS：三腿齐（源级正/反例 + 产物级）')
        else:
            print('  腿3 跳过（未给 --elf；产物级判据由 driver_stub_elf_gate.sh 在云端执行）')
            print('门禁 selftest PASS：两腿（源级正/反例）')
        return 0

    # ---- 默认：腿1（+ 可选腿3）----
    print('== driver.so = %s ==' % driver)
    drm, alsa, rest = need_stubs(driver)
    print('UNDEF 全集 %d = DRM %d + ALSA %d + libc/pthread/运行时 %d' %
          (len(drm) + len(alsa) + len(rest), len(drm), len(alsa), len(rest)))
    print('libc/pthread/运行时（rootfs 提供，无需桩）: %s' % ' '.join(rest))
    rows, missing = src_check(driver)
    print_table(rows, missing, '源级')
    if missing:
        print('★ 门禁 FAIL：%d 项需桩符号在桩实现中找不到' % len(missing))
        return 1
    if elves:
        rows, missing = elf_check(driver, elves)
        print_table(rows, missing, '产物级 .dynsym')
        if missing:
            print('★ 门禁 FAIL（产物级）：%d 项需桩符号未导出' % len(missing))
            return 1
        print('门禁 PASS：源级 + 产物级（%d 个桩 DSO）均覆盖 driver.so 全部需桩 UNDEF。' % len(elves))
    else:
        print('门禁 PASS：假桩覆盖 driver.so 全部需桩 UNDEF。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
