# libretro 接口层权威对照（rkgame frontend × sf2000_multicore retro_core_t）

> **本文件回答的问题**：复刻 rkgame 的 core 加载器时，到底该 `dlsym` 哪些符号？
>
> **上游权威参照**：`madcock/sf2000_multicore` 的 `core_api.c` → `struct retro_core_t core_exports`
> （25 字段，2026-10-18 联网核实，来源 https://github.com/madcock/sf2000_multicore/blob/master/core_api.c）。
> **本机实测**：`golden/factory.rkgame.bin`（ARM32，3,921,108 B）的 `.dynsym` 与字符串。
>
> 定案：PROGRESS R195。

## 1. 本机 rkgame 是 libretro frontend（三项铁证）

| 证据 | 实测值 |
|---|---|
| `dlopen` / `dlsym` / `dlerror` / `dlclose` | **全部在 `.dynsym` UNDEF**（rkgame 共 113 个 UNDEF，含这 4 个） |
| `.dynsym` 里 `retro*` 符号 | **0 个**（说明 frontend 不静态链接 core 接口，而是运行时 dlsym） |
| `.rodata` 内 `retro_*` 字符串 | **19 个**（dlsym 的符号名参数；R197 定稿：必须只扫 `.rodata`，见 §7） |
| rkgame 自己实现的 retro 函数 | `retro_load_state`(0x2b8570, 384 B) / `retro_save_state`(0x2b83e8, 392 B) —— 即时存档 |

## 2. 本机 rkgame 的 dlsym 符号表（19 个，权威 = .rodata 实测）

```
retro_deinit                  retro_load_game              retro_run
retro_get_region              retro_save_state
retro_init                    retro_serialize              retro_serialize_size
retro_is_support              retro_set_audio_sample_batch retro_set_controller_port_device
retro_set_device              retro_set_environment        retro_set_input_poll
retro_set_input_state         retro_set_progress_callback  retro_set_unzip
retro_set_video_refresh       retro_unload_game
retro_unserialize
```

## 3. 上游 sf2000_multicore 的 `core_exports`（25 字段，权威参照）

`struct retro_core_t` 的字段（`core_api.c:63-90`）：

| # | 字段 | # | 字段 |
|---|---|---|---|
| 1 | `retro_init` | 14 | `retro_run` |
| 2 | `retro_deinit` | 15 | `retro_serialize_size` |
| 3 | `retro_api_version` | 16 | `retro_serialize` |
| 4 | `retro_get_system_info` | 17 | `retro_unserialize` |
| 5 | `retro_get_system_av_info` | 18 | `retro_cheat_reset` |
| 6 | `retro_set_environment` | 19 | `retro_cheat_set` |
| 7 | `retro_set_video_refresh` | 20 | `retro_load_game` |
| 8 | `retro_set_audio_sample` | 21 | `retro_load_game_special` |
| 9 | `retro_set_audio_sample_batch` | 22 | `retro_unload_game` |
| 10 | `retro_set_input_poll` | 23 | `retro_get_region` |
| 11 | `retro_set_input_state` | 24 | `retro_get_memory_data` |
| 12 | `retro_set_controller_port_device` | 25 | `retro_get_memory_size` |
| 13 | `retro_reset` | | |

其中 5 个被上游 wrap（加硬件适配）：`retro_init` / `retro_deinit` / `retro_load_game` /
`retro_unload_game` / `retro_set_environment`（`core_api.c:66-92`）。
入口是 `__core_entry__`（返回 `&core_exports`），core 二进制加载基址 **0x87000000**。

## 4. 逐项对照（本机 18 个要求 dlsym × 上游 25 字段）

### 4.1 共有 15 个（标准 libretro 子集，两边一致）

`retro_init` · `retro_deinit` · `retro_get_region` · `retro_load_game` · `retro_run` ·
`retro_serialize` · `retro_serialize_size` · `retro_unserialize` · `retro_set_audio_sample_batch` ·
`retro_set_controller_port_device` · `retro_set_environment` · `retro_set_input_poll` ·
`retro_set_input_state` · `retro_set_video_refresh` · `retro_unload_game`

### 4.2 ★ 本机独有 6 个（上游 sf2000_multicore **没有**）

| 符号 | 性质 | 对复刻的影响 |
|---|---|---|
| `retro_load_state` | **rkgame 自己实现**（0x2b8570） | 即时存档读；复刻侧必须实现同名函数 |
| `retro_save_state` | **rkgame 自己实现**（0x2b83e8） | 即时存档写；复刻侧必须实现同名函数 |
| `retro_is_support` | 厂商扩展（core 能力查询） | core 加载器需 dlsym，缺失要容错 |
| ~~`retro_set_device`~~ | **不是 dlsym 目标**（R197 证伪） | 它只是 `.symtab` 里
  `_retro_set_device` 全局指针的符号名；真正的 dlsym 目标是
  `retro_set_controller_port_device`（已绑定）⇒ **无需为它单独 dlsym** |
| `retro_set_progress_callback` | 厂商扩展（加载进度） | 同上 |
| `retro_set_unzip` | 厂商扩展（zip 内 ROM 直读） | 同上；与真机 `joystick.zip`/`ui_cn.zip` 相关 |

⇒ **这些是"照标准 libretro 写 frontend 会漏"的符号**。若复刻的 core 加载器只 dlsym
标准 25 个，厂商扩展全部拿不到 ⇒ 即时存档/能力查询/zip 直读静默失效。

### 4.4 机械门禁（`tools/core_dlsym_gate.py`，R195 建 / R197 定稿）

**最终结果：✅ 18/18 全部已绑定，exit=0**。

★ 建设过程中门禁自身有 **3 个 bug**，全部已修。注意：这 3 个都是
  **"我误报复刻侧缺口"**，不是复刻侧真缺：

| # | bug | 误报后果 | 修法 |
|---|---|---|---|
| ① | 只认 `dlsym(h,"sym")` 一种形式 | 漏了 `run_process("sym",arg)`
  （其实现内部就是 `pf = dlsym(handle_emurun, name)`，
  见 `src/proprietary/misc/FUN_002b59bc_run_process.c:14`）
  ⇒ 误报 `retro_deinit`/`retro_unload_game`/`retro_set_progress_callback` 缺失 |
  正则同时匹配两种形式 |
| ② | 扫**全二进制**而非 `.rodata` | 把 `.symtab` 里的**变量符号名**
  `_retro_set_device`（@0x3bc350）当成 dlsym 目标 ⇒ 误报 `retro_set_device` 缺失
  （真正目标 `retro_set_controller_port_device` @0x2d5cec 在 `.rodata` 且已绑定） |
  只扫 `SHT_PROGBITS + SHF_ALLOC + 非 SHF_WRITE` 且排除符号表段 |
| ③ | 自证腿A 依赖"当前恰好有 missing" | 门禁全绿时永远证不出真阳性 |
  改为"临时从已绑定集合删一个，必须翻红" |

三腿判别力自证已过（真阳性 / 可恢复 / 清单敏感）；常规模式与自证模式口径一致（18/18）。

### 4.3 上游有、本机无 11 个

`retro_api_version` · `retro_get_system_info` · `retro_get_system_av_info` ·
`retro_set_audio_sample` · `retro_reset` · `retro_unserialize` · `retro_cheat_reset` ·
`retro_cheat_set` · `retro_load_game_special` · `retro_get_memory_data` ·
`retro_get_memory_size`

⇒ 本机 rkgame **不用**这些（或从别处获取）。复刻侧**不应**因"标准 libretro 有"就额外 dlsym
它们；但若被加载的 core 是标准 libretro core，这些符号在 core 侧存在、frontend 不调用即可。

## 5. 对复刻的结论（动作项）

1. **core 加载器的 dlsym 清单 = 本机 18 个**（§2 的 19 减去 rkgame 自实现 1 个），不是标准 25 个。
2. **`retro_load_state` / `retro_save_state` 必须由复刻侧自己实现**（不是从 core dlsym），
   且符号地址须对齐真机（0x2b83e8 / 0x2b8570，`.symtab` 已给）。
3. 厂商扩展 4 个（`retro_is_support` / `retro_set_device` / `retro_set_progress_callback` /
   `retro_set_unzip`）dlsym 时**取不到要容错**（不是所有 core 都导出）。
4. 上游 sf2000_multicore 的价值 = **"多 core 统一接口层"的设计参照**（`__core_entry__` +
   `core_exports` + 5 个 wrap 回调），适用于本项目"一个 frontend 加载多个 `libemu_*.so`"的场景
   （见 `tools/core_selector_spec.md` 的 18 种 core）；**但其 25 字段表不能直接当本机清单用**
   （见 §4.2/4.3 的 6+11 差异）。

## 6. 纪律

- 本文件的"本机 20 个"权威来源 = `golden/factory.rkgame.bin` 二进制实测，**不写死**在代码里；
  可用 `python3 tools/_r195_symdiff.py` 同法复现（`retro_` 前缀扫字符串 + `.dynsym` 判 dl* 导入）。
- 上游 25 字段表来源 = `madcock/sf2000_multicore` `core_api.c`（2026-10-18 联网核实）；
  上游若变更，以变更后的 `core_api.c` 为准，不沿用本文快照。

## 7. R197 定案：dlsym 目标字符串必须只扫 `.rodata`

| 区域 | 内容 | 是否 dlsym 目标 |
|---|---|---|
| `.rodata`（0x2d5cec 一带） | `retro_set_controller_port_device` 与 `device0_type`/`find ... process fail` 等日志串相邻 | ✅ 是 |
| `.symtab`（0x3bc350 一带） | `_retro_set_device` 等**全局指针变量**的符号名（上下文是 `Load.prosystem_Load.stella_Load...`） | ❌ 否 |

⇒ 权威清单提取规则：`SHT_PROGBITS` + `SHF_ALLOC` + **非** `SHF_WRITE` + 排除符号表/注释/note 段。
（实现见 `tools/core_dlsym_gate.py: device_retro_strings()`）

## 8. 绑定形式必须认全（两种）

| 形式 | 例 | 等价性 |
|---|---|---|
| 直接 dlsym | `_retro_run = dlsym(h,"retro_run")` | — |
| 按名调用 | `run_process("retro_deinit", 0)` | `run_process` 内部即 `pf=dlsym(handle_emurun,name); (*pf)()` |

⇒ 门禁正则必须同时匹配两者（实现见 `rebuild_dlsym_literals()`）。
