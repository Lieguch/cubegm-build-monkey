# retro_core_t 函数表 vs rkgame libretro 接口层对表（P1-2 · R174）

## 1. 权威对照源（联网核实后抓取原文）

| 项 | 值 |
|---|---|
| 仓库 | `madcock/sf2000_multicore`（GitHub，25★ / 337 commits，fork 自 gitlab.com/kobily/sf2000_multicore） |
| 定义文件 | `core_api.h`（31 行）——`struct retro_core_t` **26 个函数指针** + `core_entry_t` |
| 消费方 | `main.c:116-149`：`core_entry()` 取表 → set_* 五连 → `retro_init()` → 缓存 gfn_* 六个 → run 循环 → `retro_deinit()` |
| 加载机制 | `__core_entry__` 放 `.init.core_entry` 节（二进制首地址），loader 直接调它取 `&core_exports` |
| 原文证据 | report/_sf2000_core_api.h（1365 B）/ _sf2000_core_api.c（17,681 B）/ _sf2000_main.c（6,136 B） |

## 2. 机制差异（先定性，再逐项）

| 维度 | SF2000 multicore | rkgame（本机） |
|---|---|---|
| core 接口形态 | **函数表**（core 导出 `__core_entry__` 返回 `retro_core_t*`） | **逐符号 dlsym**（`dlsym(handle_emurun,"retro_*")`，R174 全仓实测 18 个 retro_* + SetFrameSkip） |
| 厂商扩展 | 无（纯 libretro 面） | **4 个**：`retro_is_support` / `retro_set_progress_callback` / `retro_set_unzip` / `SetFrameSkip` |
| 存档 | 表内 `retro_serialize`/`retro_unserialize`/`retro_get_memory_*` | **只** `retro_serialize_size`+`retro_serialize`（zlib 压缩 state 存档，见 FUN_002b83e8：`compress()` 后写 4B 长度+压缩体） |
| 驱动接口 | libretro 回调（video/audio/input/env） | **driver.so 私有 9 ABI**（video_driver_*/sound_driver_*，见 driver_abi_diff.md）—— 两层并存：libretro 回调给 core，driver.so ABI 给硬件 |

## 3. 逐项对表（retro_core_t 26 vs rkgame dlsym 面）

| retro_core_t 成员 | rkgame dlsym | rkgame 调用点（实测） |
|---|---|---|
| `retro_init` | ✓ | run_process("retro_init") Load_Proc1 |
| `retro_deinit` | ✓ | run_process("retro_deinit") Load_Proc2 ×3 |
| `retro_api_version` | — | （未调用） |
| `retro_get_system_info` | — | （未调用） |
| `retro_get_system_av_info` | — | （未调用） |
| `retro_set_environment` | ✓ | Load_Proc1 run_process |
| `retro_set_video_refresh` | ✓ | Load_Proc1 run_process |
| `retro_set_audio_sample` | — | （未调用；只用 batch 变体） |
| `retro_set_audio_sample_batch` | ✓ | Load_Proc1 run_process |
| `retro_set_input_poll` | ✓ | Load_Proc1 run_process |
| `retro_set_input_state` | ✓ | Load_Proc1 run_process |
| `retro_set_controller_port_device` | ✓ | Core_Load.c（Filetype==0x800 时） |
| `retro_reset` | — | （未调用） |
| `retro_run` | ✓ | Load_Proc2 |
| `retro_serialize_size` | ✓ | retro_save_state/retro_load_state |
| `retro_serialize` | ✓ | retro_save_state.c |
| `retro_unserialize` | ✓ | retro_load_state.c |
| `retro_cheat_reset` | — | （未调用） |
| `retro_cheat_set` | — | （未调用） |
| `retro_load_game` | ✓ | 12 处（各平台 Load 函数） |
| `retro_load_game_special` | — | （未调用） |
| `retro_unload_game` | ✓ | Load_Proc2 run_process |
| `retro_get_region` | ✓ | Load_Proc2 |
| `retro_get_memory_data` | — | （未调用 —— .srm RAM 持久化无对应） |
| `retro_get_memory_size` | — | （未调用） |

**统计：26 项中 16 项被 rkgame dlsym 消费；10 项未调用**（api_version / get_system_info /
get_system_av_info / set_audio_sample / reset / cheat_* / load_game_special / get_memory_*）。

**rkgame 独有 4 个（retro_core_t 没有）**：

| 符号 | 用途 | 调用点 |
|---|---|---|
| `retro_is_support` | 加载前探针：core 是否支持该 ROM（返回 ≥0 才继续） | FBA_Load / Core_Load 各平台 Load |
| `retro_set_progress_callback` | ROM 加载进度回调 | FBA_Load / Core_Load |
| `retro_set_unzip` | 注册解压回调（zip 内 ROM） | Gpsp_Load 等 |
| `SetFrameSkip` | 厂商跳帧控制（非 libretro 标准） | Load_Proc2 |

## 4. 结论与 57-core 移植含义（R162 裁决口径）

1. **rkgame 不是标准 libretro frontend**：它用「driver.so 私有 ABI 直驱硬件 + 逐符号 dlsym core」
   的两层结构，retro_core_t 的 26 项只覆盖其 libretro 面的一半（16/26），另有 4 个厂商扩展。
2. **57-core 移植的接口基线**：任何移植进来的 core 必须同时满足
   (a) 16 个标准 retro_* 符号（dlsym 名精确匹配）；(b) 4 个厂商扩展（retro_is_support 是硬门槛——
   加载链第一个探针）；(c) 与 driver.so 9 ABI 解耦（core 只经 libretro 回调出画面，
   不直接碰 drm/alsa）。
3. **存档语义差异**：rkgame 的「存档」= zlib 压缩即时 state（4B 长度头），
   **不用** retro_get_memory_data/size 的 .srm 路径 —— 移植 core 时若依赖
   get_memory_*（如电池存档 SRAM），需另接持久化（P2 待办）。
4. **本表不作主判据**（R162 裁决）：retro_core_t 是**移植期接口清单**，不是行为差分判据；
   行为判据仍以工厂反汇编 + qemu 差分为准。

## 5. 未测项（诚实声明）

- **本机 libemu_*.so 的导出面未测**：golden 只含 driver.so 与 factory.rkgame.bin，
  无 core 样本 ⇒ 「core 侧导出哪些符号」无证据，本表只覆盖 rkgame（frontend）消费面。
- SF2000 multicore 的 core 补丁（cores/ 子模块）与 rkgame libemu 的兼容性未评估。
