# rkgame 已实现功能 vs rkgame-load-chain-comparison.md — 诚实审计报告 v4

**审计时间**：2026-09-07 13:27 GMT+8
**审计范围**：`src/` 全部 19 个 .c / 12 个 .h（15,567 行）
**对照文档**：`D:/output/rkgame-load-chain-comparison.md`（v3，声称 100%）
**审计方法**：`grep -n` 逐点核查实际代码，不采信文档声明

---

## 一、总体结论（一句话）

**文档 v3 声称 "P0+P1+P2+P3 = 100% 覆盖" 存在系统性虚标。**
实测：**核心链路（libretro 加载、SRAM、手柄即插即用、setting.xml、WQW、5 UI 页面）已真实现，共 12 项；有 4 项虚标（有 API 但主循环未接/未真解码），有 7 项资源未对接（原厂文件存在但未加载）。**

**实际覆盖率：12/23 ≈ 52%**（含部分实现按 0.5 计），远低于文档声称的 100%。

---

## 二、逐项审计（真实现 vs 虚标 vs 缺失）

### ✅ 真实现（12 项，代码可验证）

| # | 功能 | 证据文件:行 | 备注 |
|---|------|-----------|------|
| 1 | setting.xml 14 字段全解析 | main.c:166-393 | `parse_elem_int/str`, `parse_attr_int/str` |
| 2 | libretro 全 API 绑定 | core.c:85-172 | init/load/unload/deinit/run/video/audio/input/env/region |
| 3 | Core 表 + GetCoreIndex | core_table.c:44-121 | 33 项 + 扩展名查表 |
| 4 | environment() cmd 1/9/0xf/0x1b/0x1f/0x25 | core.c | 含 SAVE_DIRECTORY |
| 5 | SRAM .srm 自动落盘/加载 | sram.c:177-270 | fopen wb/rb 落 saves/<core>/ |
| 6 | Save State 序列化+热键 | sram.c:423-488, core.c:237 | `sstate_check_hotkey` 在游戏循环调用 |
| 7 | 手柄即插即用 (inotify) | evdev.c:72-139 | `inotify_init1(IN_NONBLOCK)` + `/dev/input` |
| 8 | joystick.zip 动态 profile | evdev.c:299-400 | `g_dynamic_profiles` + `joy_apply_tokens` + `joy_match_profile` |
| 9 | WQW\x03 容器完整解析 | wqw.c:146-380 | 412 行，`wqw_parse/extract/list/extract_index` |
| 10 | 游戏列表 fileinfo.txt + filelist.xml | game_list.c:153-343 | CSV 分号分隔 + GB2312→UTF8 iconv + XML |
| 11 | 5 UI 页面渲染 | ui.c:31-42, 464-747 | menu/type/search/setting/game 全接入主循环 |
| 12 | DRM/KMS 显示 + heartbeat shm | disp.c, heartbeat.c | `/dev/dri/card0` + `shmget(0x4d2)` |

### 🟡 虚标（有 API 但未真正生效，4 项）

| # | 文档声称 | 实际状态 | 证据 |
|---|---------|---------|------|
| 13 | **MP3 BGM "minimp3 CC0 解码器 + 独立线程"** | bgm_thread 仅 `fread` 原始 MP3 字节到 buffer 后调 `sound_driver_playframe`——把压缩数据当 PCM 播放，**无实际 minimp3 调用** | audio.c:177-207，grep `mp3_` 在 audio.c 中 **0 匹配** |
| 14 | **音频 "ALSA 条件编译"** | audio.c 走 **driver.so dlsym** (`sound_driver_init`/`sound_driver_playframe`)，**无 `__has_include(alsa/asoundlib.h)`** | audio.c:1-40 头文件说明；grep `alsa` 在 src/ **0 匹配** |
| 15 | **InitScr 双缓冲 "内存从 3.6MB → 260KB，14×"** | `disp_initscr_*` 仅在 main.c:948 **启动画面**调用一次；游戏渲染走 `disp_game_present` 缩放到 1280×720 XRGB8888，**游戏路径未用 320×200 双缓冲** | disp.c:633-670；grep `disp_initscr` 在 main.c 只有 948-950 三行 |
| 16 | **缩略图 "缩略图线程 mui_DisplayThumbnailThread"** | thumbnail.c 278 行完整实现（`thumb_extract/has/count/cache_free`），但 **main.c / game_list.c 里无任何 `thumb_`/`thumbnail` 引用** —— 死代码 | grep 主循环 **0 匹配** |

### ❌ 缺失功能（资源未对接，7 项）

| # | 原厂资源 | 我方状态 | 说明 |
|---|---------|---------|------|
| 17 | **多语言 UI 包** (`ui_*.zip` × 8：en/cn/ar/fr/ge/ko/po/ru/sp) | 仅硬编码 `ui_en.zip` fallback，**未使用 `<config language=>` / `<defaultlanguage>` 切换** | ui.c:52 `default_zip = "ui_en.zip"` |
| 18 | **`cores/config.xml`** (SeletEmuCore，扩展名→core 映射) | 未读取；仅用 `filelist.xml` 做 ROM→core 覆盖 | grep `config.xml` 在 src/ **0 匹配** |
| 19 | **`resource.cpd` / `UI_Res.cpd`** (UI 资源容器) | 完全未使用 | grep `resource.cpd` **0 匹配** |
| 20 | **`menu.log`** (菜单恢复日志) | 用 `recent.lst` + `favorites.lst` 替代，**格式与原厂 menu.log 不同** | menu_log.c 有实现但语义变化 |
| 21 | **RF 无线手柄** (`InitRFJoystick`) | 无实现，无硬件 | evdev.c 无 RF 相关 |
| 22 | **`dispmeninfo`** (/proc/meminfo 打印) | 无独立函数，日志中有部分诊断输出 | 语义差异 |
| 23 | **`sfc_init` / `spi_driver_init` / `UpdateROM`** | 明确跳过（合理，无 SPI 硬件） | 文档已注明 |

### ⚠️ 行为偏离（非缺失，但需知晓）

| # | 项 | 原厂 | 我方 |
|---|---|------|------|
| A | `<savestatehotkey>` 默认值 | **-1 禁用** | **9 (L1) 启用** |
| B | `<gamemenuhotkey>` 默认值 | **9** | **10 (L2)** |
| C | Core 表项数 | 硬编码 **60 项** | **33 项** |
| D | 手柄 profile 匹配 | joystick.zip 26 动作词表 | 硬编码 4 + 动态 joystick.zip |

---

## 三、资源对接清单（原厂 SD 卡 vs 我方加载）

| 原厂资源 | 路径 | 我方是否加载 | 用途 |
|---------|------|-------------|------|
| `setting.xml` | `cubegm/` | ✅ | 14 字段全解析 |
| `font.ttf` | `cubegm/` | ✅ (font.c 加载) | TTF 渲染 |
| `ui_en.zip` (或 `<config language=>` 指定) | `cubegm/` | ⚠️ 仅 en fallback | 5 UI 页面 |
| `ui_cn/ar/fr/ge/ko/po/ru/sp.zip` | `cubegm/` | ❌ | 多语言 UI（未对接） |
| `root.dat` (725KB, WQW\x03) | SD 根 | ✅ | 提取 fileinfo.txt + bg |
| `joystick.zip` | `cubegm/` | ✅ | 动态 profile |
| `cores/filelist.xml` (135 条) | `cubegm/cores/` | ✅ | ROM→core 映射 |
| `cores/config.xml` | `cubegm/cores/` | ❌ | 扩展名→core 映射（SeletEmuCore） |
| `cores/*.so` (20 个 libretro 核心) | `cubegm/cores/` | ✅ | dlopen 加载 |
| `saves/<core>/` | `cubegm/` | ✅ | SRAM .srm 落盘 |
| `states/<core>/` | `cubegm/` | ✅ | Save State |
| `recent.lst` / `favorites.lst` | `cubegm/` | ✅ | 最近/收藏 |
| `<NNN>.dat` × 9 (缩略图缓存) | SD 根 | ❌ (thumbnail.c 死代码) | 缩略图 |
| `resource.cpd` | `cubegm/` | ❌ | UI 资源容器 |
| `<000>..<008>/*.zip` (单 ROM) | SD 根 | ✅ (目录扫描 fallback) | 游戏 ROM |

---

## 四、文档 v3 声称 vs 实际（关键差异）

| 文档 v3 章节 | 声称 | 实测 | 差异 |
|-------------|------|------|------|
| §11 TL;DR "P0+P1+P2+P3 全部 100% 覆盖" | 100% | **52%** | 严重虚标 |
| §十 "P2.16 MP3 BGM minimp3 解码器" | ✅ | ❌ 无 mp3_ 调用 | 虚标 |
| §15.1 "InitScr 死代码修复，320×200 双缓冲" | ✅ 已接入 | 🟡 仅启动画面 | 部分虚标 |
| §15.4 "缩略图可运行" | ✅ | ❌ 主循环无调用 | 虚标 |
| §4 "ALSA 条件编译降级" | ALSA | driver.so dlsym | 描述错误 |
| §9 "Save State UI" | ✅ | ✅ 热键触发 | 一致 |
| §7 "手柄即插即用" | ✅ | ✅ inotify | 一致 |
| §六 "libretro 加载链 P0 已全绿" | ✅ | ✅ | 一致 |
| §二 "setting.xml 14/14 100%" | ✅ | ✅ | 一致 |
| §十 "P2.15 游戏列表 fileinfo+filelist" | ✅ | ✅ | 一致 |

---

## 五、真实覆盖率（修正版）

| 模块 | 完成度 | 说明 |
|------|-------|------|
| 启动链路 (main+heartbeat) | 100% | 全绿 |
| setting.xml 解析 | 100% | 14/14 |
| libretro 核心加载 | 100% | API 齐 |
| SRAM 存档 | 100% | .srm 落盘 |
| Save State | 90% | 缺游戏内 UI 菜单（仅热键） |
| 手柄即插即用 | 100% | inotify |
| 游戏列表 (fileinfo+filelist) | 100% | CSV+XML |
| UI 5 页面 | 90% | 页面齐但无缩略图 overlay |
| WQW\x03 容器 | 100% | 完整逆向 |
| **音频 BGM (MP3)** | **0%** | **虚标，未解码** |
| 多语言 UI | 15% | 仅 en fallback |
| 缩略图 | 0% | 死代码 |
| 资源 cpd | 0% | 未使用 |
| **综合** | **~55%** | **非文档声称的 100%** |

---

## 六、下一步修复优先级

**P0（阻塞真实出声）**
1. audio.c 集成 minimp3.h：`#include "minimp3.h"` + `mp3dec_init/hydra/hydra2/...` 解码 MP3 → PCM16 → sound_driver_playframe

**P1（阻塞 UI 完整性）**
2. ui.c 按 `<config language=>` / `<defaultlanguage>` 切换 ui_*.zip
3. main.c 主循环接入 thumbnail.c（`thumb_extract` 按当前选中 game 加载 `<NNN>.dat` 缩略图）
4. game_list.c 读 `cores/config.xml` 补齐 SeletEmuCore 映射

**P2（阻塞行为对齐）**
5. InitScr 双缓冲真正用于游戏渲染（`disp_flip` 游戏模式分支调 `disp_initscr_present` 而非 `disp_game_present` 缩放）
6. 恢复 `<savestatehotkey>` 默认 -1 禁用（与原厂一致）
7. Core 表补齐到 60 项（对齐 DAT_003b0278）

---

**审计人**：SenseNova 6.8 Flash Lite
**审计方法**：`grep -n` 逐函数、逐字符串、逐调用点核查
**证据链**：本报告所有 ✅/❌ 判定均基于 `grep` 实测输出，非文档声明
