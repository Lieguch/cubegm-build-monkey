# folder→core 映射权威对照（P1-1 对表 · 2026-10-13）

## 目的

把工厂 rkgame 三套并存的 folder→core 决定机制（filelist.xml 配置驱动 / default_core_list 扩展名驱动 /
FBA_Load 10 槽指针表）与生态对照源 TreeFrogUI cores.md（86 folder→core）逐项对表，
为 57-core 移植与本设备 core 命名对齐提供单一权威参考。

## 数据源与证据

| 源 | 内容 | 证据文件 |
|---|---|---|
| A 原厂配置 | filelist.xml 135 条 folder→core（三份一致：sdcard_min / _sd2 / 原厂SD卡根目录结构） | golden/sdcard_min/cores/filelist.xml（sha 一致 8654 B） |
| B1 工厂代码·扩展名驱动 | default_core_list 33 项 @0x3b0254（68B 周期：[32B ext][4B Filetype][32B core 名内联]） | report/_dcl_decoded.txt（本轮从 factory.rkgame.bin 重解码） |
| B2 工厂代码·街机 10 槽 | FBA_Load 指针表 @0x3b012c-0x3b0150（.data 9 槽 + 终止空槽 0x2dbcb4） | report/_fba_load_factory.asm + 本轮逐槽 deref |
| C 生态对照 | TreeFrogUI cores.md 86 folder→core（SF3000 同代硬件） | report/_tf_folders.json / _tf_cores_full.md |

## 源 A：filelist.xml folder→core 实测（原厂只配了 3 个 folder）

| folder | 平台 | 条目数 | core 分布 |
|---|---|---|---|
| 000 | 街机(FBA) | 105 | libemu_fbalpha2012.so ×72 / libemu_extend.so ×18 / libemu_fba.so ×13 / libemu_fbafast.so ×1 / libemu_cps2.so ×1 |
| 002 | SFC | 21 | libemu_snes9x2010.so ×19 / libemu_snes9x.so ×2 |
| 004 | GBA | 9 | libemu_mgba.so ×9 |

**关键事实**：原厂 filelist.xml **没有** 001/003/005-008 的条目 —— 这些 folder 的 ROM 走
default_core_list（扩展名驱动）路径；000/002/004 三个 folder 的 ROM 命中 filelist 条目后直接指定 core。

## 源 B1：default_core_list 33 项（扩展名 → core → Filetype 位）

| # | 扩展名 | Filetype 位值 | core |
|---|---|---|---|
| 1 | SMC | 4 (0x4) | libemu_sfc.so |
| 2 | FIG | 4 (0x4) | libemu_sfc.so |
| 3 | SFC | 4 (0x4) | libemu_sfc.so |
| 4 | GD3 | 4 (0x4) | libemu_sfc.so |
| 5 | GD7 | 4 (0x4) | libemu_sfc.so |
| 6 | DX2 | 4 (0x4) | libemu_sfc.so |
| 7 | BSX | 4 (0x4) | libemu_sfc.so |
| 8 | SWC | 4 (0x4) | libemu_sfc.so |
| 9 | NES | 2 (0x2) | libemu_nes.so |
| 10 | NFC | 2 (0x2) | libemu_nes.so |
| 11 | FDS | 2 (0x2) | libemu_nes.so |
| 12 | UNF | 2 (0x2) | libemu_nes.so |
| 13 | VT3 | 1024 (0x400) | libemu_vrt.so |
| 14 | VT4 | 1024 (0x400) | libemu_vrt.so |
| 15 | GBA | 16 (0x10) | libemu_gpsp.so |
| 16 | AGB | 16 (0x10) | libemu_gpsp.so |
| 17 | GBZ | 16 (0x10) | libemu_gpsp.so |
| 18 | GBC | 32 (0x20) | libemu_tgbdual.so |
| 19 | GB | 32 (0x20) | libemu_tgbdual.so |
| 20 | SGB | 32 (0x20) | libemu_tgbdual.so |
| 21 | BIN | 8 (0x8) | libemu_md.so |
| 22 | MD | 8 (0x8) | libemu_md.so |
| 23 | SMD | 8 (0x8) | libemu_md.so |
| 24 | GEN | 8 (0x8) | libemu_md.so |
| 25 | SMS | 8 (0x8) | libemu_md.so |
| 26 | ISO | 128 (0x80) | libemu_pcsx.so |
| 27 | IMG | 128 (0x80) | libemu_pcsx.so |
| 28 | PBP | 128 (0x80) | libemu_pcsx.so |
| 29 | A26 | 256 (0x100) | libemu_stella.so |
| 30 | A78 | 512 (0x200) | libemu_prosystem.so |
| 31 | CONF | 2048 (0x800) | libemu_dosbox.so |

## 源 B2：FBA_Load 街机 10 槽指针表（0x3b012c 起）

| 槽 | .data 地址 | rodata 指针 | core 名 |
|---|---|---|---|
| [0] | 0x003b012c | 0x002ddf6c | libemu_neogeo.so |
| [1] | 0x003b0130 | 0x002ddf80 | libemu_capcom.so |
| [2] | 0x003b0134 | 0x002ddf94 | libemu_pgm.so |
| [3] | 0x003b0138 | 0x002ddfa4 | libemu_fba.so |
| [4] | 0x003b013c | 0x002ddfb4 | libemu_cps2.so |
| [5] | 0x003b0140 | 0x002ddfc4 | libemu_extend.so |
| [6] | 0x003b0144 | 0x002ddfd8 | libemu_fbalpha.so |
| [7] | 0x003b0148 | 0x002ddfec | libemu_fbalpha2012.so |
| [8] | 0x003b014c | 0x002de004 | libemu_mame2000.so |
| [9] | 0x003b0150 | 0x002dbcb4 | （空串=终止哨兵） |

遍历语义（工厂反汇编定案）：`sprintf(buf,"%s/cores/%s",work_path,core_path[i])` 后 dlopen；
dlopen/retro_is_support 失败则 i++ 重试，至空槽终止。**第 4 参 core 名由 r3 跨块携带**
（0x2b6cc0 首载 / 0x2b6d5c、0x2b6db0 pre-index 自增），本轮已根修入 src（R173）。

## 源 C：TreeFrogUI cores.md 86 folder→core（生态对照，非本机判据）

TreeFrogUI 用 libretro 命名（*_libretro.so），与本机 libemu_*.so 命名不同但平台对应关系可映射。
完整 86 条见 report/_tf_folders.json。与本机 folder 对应的代表性条目：

| TF folder | 平台 | TF core | 本机 folder | 本机对应 core（filelist/DCL） |
|---|---|---|---|---|
| nes | NES | fceumm_libretro.so | 005/001 | libemu_nes.so（DCL） |
| fds | Famicom Disk System (needs `disksys.rom`) | fceumm_libretro.so | 001 | libemu_nes.so（DCL） |
| nest | NES (accurate) | nestopia_libretro.so | 005/001 | libemu_nes.so（DCL） |
| snes02 | SNES (2002) | snes9x2002_libretro.so | 002 | libemu_snes9x2010.so（filelist 002 主力）/ libemu_snes9x.so ×2 |
| gb | Game Boy | gambatte_libretro.so | 006 | libemu_tgbdual.so（DCL GB/GBC/SGB） |
| gbb | GB link | tgbdual_libretro.so | 006 | libemu_tgbdual.so（DCL） |
| gbac | GBA (multicore) | gpsp_multicore_libretro.so | 004 | libemu_mgba.so（filelist 004 ×9）/ libemu_gpsp.so（DCL GBA/AGB/GBZ） |
| gbav | GBA | vba_next_libretro.so | 004 | libemu_gpsp.so（DCL） |
| gpgx | Mega Drive (accurate) | genesis_plus_gx_libretro.so | 003 | libemu_md.so（DCL BIN/MD/SMD/GEN/SMS） |
| 32x | Sega 32X (may run slow) | picodrive_libretro.so | 003 | libemu_md.so（DCL） |
| a26 | Atari 2600 | stella2014_libretro.so | 008 | libemu_stella.so（DCL A26） |
| a78 | Atari 7800 | prosystem_libretro.so | —（无 folder，A78 扩展名→DCL prosystem） | libemu_prosystem.so（DCL A78） |
| pce | PC Engine / TurboGrafx-16 | mednafen_pce_fast_libretro.so | —（无对应） | （本机无 PCE core） |

## 对表结论

1. **本机命名体系独立于 libretro**：工厂 19 个 libemu_*.so 中，与 TreeFrogUI 同名直击的只有
   stella（A26→stella2014）、prosystem（A78）两个 libretro 出身的核心；其余为本厂命名。
2. **folder 与 core 的绑定是三层结构**：filelist.xml（000/002/004 显式绑定）→
   default_core_list（扩展名位掩码 Filetype 驱动，覆盖全部 folder 的兜底路径）→
   FBA_Load 10 槽（仅街机 000 的 dlopen 遍历顺序）。
3. **BKP/ZIP 两项 cnt=65536(0x10000) 无 core 名**：它们只置 Filetype 位，不指定 core ——
   与 filelist.xml 中 zip 条目显式指定 core 的行为互补（zip 内 ROM 由 filelist 精确指定）。
4. **57-core 移植的对齐基点**：本机 9 个街机候选 core 的 dlopen 顺序
   （neogeo→capcom→pgm→fba→cps2→extend→fbalpha→fbalpha2012→mame2000）
   是 1:1 复刻必须保持的语义；TreeFrogUI 侧无此遍历（单 core 直载）。
5. **VT3/VT4（小霸王学习机）→ libemu_vrt.so**：config.xml/filelist 均无 vrt 条目，
   vrt core 仅由 DCL 扩展名驱动 —— 佐证 config.xml 缺失的 core（capcom/neogeo/dosbox/gpsp/prosystem/vrt）
   走 DCL/dlopen 路径。

## 本轮修复记录（R173）

FBA_Load.c sprintf 漏参（重建 bug）：工厂 4 参 `sprintf(buf,"%s/cores/%s",work_path,core_path[i])`，
此前重建版只传 work_path ⇒ dlopen 路径缺 core 名段。已修（含证据注释），
云端 zig cc -Os 冒烟 rc=0、.o 4024 B、UNDEF 表 10/10 DAT_003b01xx + work_path + DAT_002dbcb4 全保留（无 DCE 复发）。
