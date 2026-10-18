# core 选择器规格（真机 rkgame 复刻侧）

> 权威数据源（两个，均来自真机，不得用上游 SF3000 `cores.md` 代替）：
> 1. `tools/device_core_map.tsv` —— 135 条，来自 `golden/sdcard_min/cores/filelist.xml`
>    （逐 **ROM 文件**指定，sha256 `f4c3d9fd…`）
> 2. `tools/device_romid_core_map.tsv` —— 30 条，来自 `golden/factory.rkgame.bin`
>    内嵌表（按 **ROM 标识** 3-4 大写推，sha256 `d491ed8d…`）
>
> 定案依据：PROGRESS R191 / R192。

## 选择算法（唯一权威，不得另写第二份）

```
select_core(rom_path):
    rom_name = basename(rom_path)                    # 例 "002/Batman.zip" → "Batman.zip"
    folder   = dirname(rom_path)                     # 例 "002"

    # ① 先查 filelist.xml 派生表（逐 ROM 覆盖，优先级最高）
    key = folder + "/" + rom_name                    # filelist.xml 的 name 属性格式
    if key in device_core_map:                       # 135 条
        return device_core_map[key]

    # ② 未命中 ⇒ 按 ROM 标识推（内嵌 30 条表）
    rid = rom_id_of(rom_path)                        # 读 ROM 头/内部名，取 3-4 大写标识
    if rid in device_romid_core_map:
        return device_romid_core_map[rid]

    # ③ 仍未知 ⇒ 如实报"无"，**不得**默认猜一个 core
    return NONE
```

## core 加载路径

`<base>/cores/<core>`，其中 `<base>` 对应二进制里的 `%s/cores/libemu_*.so` 格式串
（真机即 SD 卡根）。core 文件必须与 `cores/filelist.xml` 同目录。

## 需支持的 core 集合（10 种，内嵌表全集）

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

> `filelist.xml` 另用到 `libemu_fbalpha2012.so` / `libemu_extend.so` / `libemu_fba.so` /
> `libemu_snes9x2010.so` / `libemu_snes9x.so` / `libemu_fbafast.so` / `libemu_cps2.so`
> 共 7 种（仅出现在逐 ROM 覆盖表，不在内嵌 30 条内）⇒ 复刻侧合计至少 **13 种** core 可用。

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
