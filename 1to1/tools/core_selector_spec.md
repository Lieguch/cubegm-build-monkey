# core 选择器规格（真机 rkgame 复刻侧）

> ★ R202 定案：权威数据源是**三层**，其中第②层已从 config.xml 改为**真机
>   `GetCoreIndex` 静态表**（反汇编 + `.data` 提取证明 config.xml **不是运行时权威**）：
> 1. `tools/device_core_map.tsv` —— 135 条，来自 `golden/sdcard_min/cores/filelist.xml`
>    （逐 **ROM 文件**指定，最高优先）
> 2. `tools/device_getcoreindex_table.tsv` —— **33 条，真机 `GetCoreIndex` 静态表**
>    （`golden/factory.rkgame.bin` 的 `.data` 0x3b0254 起，68 B/项：
>     扩展名在 +0x00、位标志在 +0x20、core 名在 +0x24）
>     ★ **一对一，无歧义**。`device_ext_core_map.tsv`（config.xml 派生）已降级为
>     "非运行时权威，仅供 config.xml 结构参考"。
> 3. `tools/device_romid_core_map.tsv` —— 30 条，来自 `golden/factory.rkgame.bin`
>    内嵌表（按 **ROM 标识** 3-4 大写推，最低优先）
>
> 定案依据：PROGRESS R191 / R192 / R196 / R199 / R202。

## 选择算法（唯一权威，不得另写第二份）

```
select_core(rom_path):
    rom_name = basename(rom_path)
    folder   = dirname(rom_path)
    ext      = upper(suffix(rom_name))               # 例 "ZIP" / "SFC" / "GBA"

    # ① 逐 ROM 覆盖（filelist.xml 135 条，最高优先）
    key = folder + "/" + rom_name
    if key in device_core_map:
        return device_core_map[key]

    # ② 按扩展名查真机 GetCoreIndex 静态表（R202：一对一，无歧义）
    #    真机表在 .data 静态存在，每扩展名唯一一个 core
    #    （BKP/ZIP 两项 core 为空 ⇒ 不经此表，落到③/④）
    core = ext_map.get(ext)                         # 来自 device_getcoreindex_table
    if core:
        return core

    # ③ 按 ROM 标识（二进制内嵌 30 条，最低优先）
    rid = rom_id_of(rom_path)
    if rid in device_romid_core_map:
        return device_romid_core_map[rid]

    # ④ 仍未知 ⇒ 如实报"无"，**不得**默认猜一个 core
    return NONE
```

## core 加载路径

`<base>/cores/<core>`，其中 `<base>` 对应二进制里的 `%s/cores/libemu_*.so` 格式串
（真机即 SD 卡根）。core 文件必须与 `cores/filelist.xml` 同目录。

## 真机两套 core 选择机制（R199 反汇编实证）

复刻侧选择器必须与真机的**两条路径**对齐（`golden/factory.rkgame.bin` 反汇编）：

| 真机函数 | 地址/大小 | 判据 | 对应本规格层 |
|---|---|---|---|
| `GetFileCore` | 0x22334 / 188B | **ROM 全名**（链表遍历 + 按名匹配） | ① `filelist.xml`（135 条逐 ROM） |
| `GetCoreIndex` | 0x2b5624 / 148B | **大写扩展名**（表驱动，一对一） | ② `config.xml`（18 core × 28 ext） |
| 二进制内嵌 ROM 标识表 | `.rodata` 0x3a7914 区 | ROM 内部标识（3-4 大写） | ③（30 条） |

### `GetCoreIndex` 破译结论（R199）

```c
int GetCoreIndex(char *ext)              // ext 已由 strupr() 转大写
{
    table = *(g_base + off);             // 全局表基址（.bss，运行时填）
    for (idx = 0, p = table; p[0] != 0; idx++, p += 0x44) {   // 每项 68B；首字节 0 = 表尾
        if (compare(p, ext) == 0) {      // 命中
            table[idx].field_0x20 |= flag;                   // 置位"已用"标志
            return idx;                                     // ★ 返回**单个**索引
        }
        if (idx == 0x64) break;          // 上限 100 项
    }
    return -1;                           // 未命中
}
```

调用链：`FilePreEmu`(0x16f08) → `GetFilenameExt`(0x2b56b8) → `strupr`(0x16ebc)
→ `GetCoreIndex`(0x2b5624) → `OpenZipU`/`GetZipItemA`/`UnzipItem`/`CloseZipU`。

### ★ 对第②层的关键影响

- 真机"扩展名 → core"是**一对一**（`GetCoreIndex` 返回单个 int）；
- 而 `config.xml` 里同一扩展名可出现多次（每个 core 各自 `supported_extensions` 声明）
  ⇒ 运行时表是**归一后的一对一表**；
- **归一规则（首个胜出 / 末个覆盖 / 按优先级）尚未证实** —— 填表函数不在
  `mui_LoadConfig`（该函数只调 `get_value_from_items`×50，是读 setting.xml 的），
  且 `supported_extensions` 字符串（.rodata 0x2d5510）**无 `ldr [pc,#imm]` 直接引用**
  ⇒ 填表路径需**动态观测**（qemu 内 dump 该表）才能定案。
- ⇒ 在归一规则证实前，`core_selector.py` 第②层对一对多**报 `AMBIGUOUS` 并带全部候选**
  （不静默取第一个），这是符合项目纪律的中间态，**不是缺陷**。

## 需支持的 core 集合（R196 起 = 18 种，config.xml 全集）

| core | 覆盖 ROM 标识 |
|---|---|
| `libemu_sfc.so` | BSX, DX2, FIG, GD3, GD7, NES, SFC, SMC, SWC |
| `libemu_nes.so` | FDS, NFC, UNF, VT3 |
| `libemu_md.so` | GEN, ISO, MD, SMD, SMS |
| `libemu_gpsp.so` | AGB, GBC, GBZ |
| `libemu_pcsx.so` | A26, IMG, PBP |
| `libemu_tgbdual.so` | BIN, GB, SGB |
| `libemu_vrt.so` | GBA, VT4 |
| `libemu_stella.so` | A78 |
| `libemu_prosystem.so` | CONF |
| `libemu_dosbox.so` | CONF |

> `config.xml` 的 18 种（R196 完整清单，权威）：
> `libemu_fbalpha.so`(ZIP,7Z) · `libemu_fbalpha2012.so`(ZIP) · `libemu_mame2000.so`(ZIP) ·
> `libemu_pgm.so`(ZIP) · `libemu_fba.so`(ZIP) · `libemu_cps2.so`(ZIP) ·
> `libemu_extend.so`(ZIP) · `libemu_snes9x.so`(SMC,SFC,SWC,FIG) ·
> `libemu_sfc.so`(SMC,FIG,SFC,GD3,GD7,DX2,BSX,SWC) · `libemu_snes9x2010.so`(同 sfc 的 8 种) ·
> `libemu_mgba.so`(GBA,GB,GBC) · `libemu_vbam.so`(GBA) · `libemu_md.so`(BIN,GEN,SMD,MD) ·
> `libemu_nes.so`(NES,FDS,UNIF,UNF) · `libemu_nestopia.so`(NES) ·
> `libemu_stella.so`(A26,BIN) · `libemu_tgbdual.so`(GB,GBC,SGB) ·
> `libemu_pcsx.so`(BIN,IMG,MDF,PBP,ISO,TOC)
>
> ★ `libemu_vbam.so` / `libemu_nestopia.so` 是 R196 新发现的（此前两层表里没有）⇒
> 复刻侧 core 集合从 13 种扩到 **18 种**。
> ★ 28 种扩展名里有 6 种**一对多**（ZIP/BIN/SFC/SMC/FIG/BSX/DX2/GD3/GD7/SWC/NES/GB/GBC/GBA），
> 选择器必须消歧，不得静默取第一个（见算法 ②）。

## 待核实疑点（不得静默"修正"）

- `A26 → libemu_pcsx.so`：Atari 2600 惯用 stella，但真机二进制字节邻接唯一指向 pcsx
  （双向核实过）。按原样实现，待真机验证。
- `CONF` 同时出现在 `libemu_prosystem.so` 与 `libemu_dosbox.so` 两条记录中
  （内嵌表本身如此）⇒ 走 ① filelist.xml 优先可消歧；若都未命中，**如实报歧义**，
  不得静默选一个。

## 纪律

- 上游 `tzubertowski/TreeFrogUI` 的 `cores.md`（95 个 folder，语义命名）是**另一款设备**
  （SF3000）的目录级映射，与真机「逐 ROM + 数字 folder + `libemu_` 前缀」不同源，
  **只可作"系统→典型 core"参考，不可用于推断真机映射**（R191 三.1）。
- 任何"按 folder 推断 core"的做法都是越界：真机 `000` 目录同时混用 5 种 core。
