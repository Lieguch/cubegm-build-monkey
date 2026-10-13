# R36S Wiki 作为 rkgame 菜单行为第二参照（P2 · R174）

## 1. 参照源（联网核实）

| 项 | 值 |
|---|---|
| 仓库 | `LiamJ74/R36S-V2.6_Wiki`（GitHub）—— R36S 无牌克隆掌机 SD 卡完全指南 |
| 框架 | **iCube/cubegm 菜单系统**（与本机同源：`rkgame` 1.1MB 主菜单 + `icube` launcher + `driver.so`） |
| SoC | RK3326（本机 RK3036G —— **不同 SoC，用户态框架同源**） |
| 原文 | report/_r36s_README_md（21,509 B）/ _r36s_sync_sd_card_py（15,101 B） |

## 2. 匹配性验证（采用前必做，逐项实测）

| R36S Wiki 描述 | 本机 golden 实测 | 匹配性 |
|---|---|---|
| `cubegm/rkgame` 主菜单二进制 | factory.rkgame.bin 3,921,108 B（PROGRESS 审计基准） | ✓ 同框架 |
| `cubegm/cores/filelist.xml` 格式 `<file name="GBA/SomeGame.zip" core="libemu_mgba.so" />` | 本机 filelist.xml 135 条同构（`name="NNN/xxx.zip" core="libemu_X.so"`） | ✓ **格式逐字符同构** |
| `cores/config.xml` 映射扩展名→core | 本机 config.xml 3822 B / 18 core / `<core><emucore name= file=>`+`<supported_extensions>` | ✓ 结构同构 |
| UI 资源 ZIP 格式（.cpd 命名） | 本机 `ui_cn.zip`（M6 key2 re-assert 回读 `50 4b 05 06` = PK ZIP 魔数）；resource 内含 `ui.cfg`+`menu.raw`（M6R ✓ 均读到） | ✓ 同格式不同命名（.zip vs .cpd） |
| `setting.xml` 存语言/音量/亮度/hotkeys | 本机 setting.xml 819 B：`<config language="1" volume="8"/>` + 10 个 `<ui filename="ui_XX.zip" gamelist="0/1"/>` + `<sound>` bgm/effect + `savestatehotkey`/`autorestore` | ✓ 同框架；**本机多了 `autorun` 与 `gamelist` 标记位** |
| `allfiles.lst` 主索引（pipe-delimited） | **本机 golden 无 allfiles.lst**；索引 = filelist.xml（135 条，仅 000/002/004 三 folder）+ favorites.lst/recent.lst | ✗ 部分差异 |
| `states/<PLATFORM>/` 存档 | 本机 retro_save_state = zlib 压缩即时 state（FUN_002b83e8） | ✓ 一致 |
| 屏幕 640x480 | 本机 FBA_Load 输入 320×240（0x140×0xf0）；driver.so gr_* 640×480 待证 | ⚠ 待证（R36S 与本机可能不同面板） |

## 3. 关键语义发现：本机 config.xml 与工厂 DCL 不一致（对表实测）

| 集合 | core |
|---|---|
| config.xml 18 core 独有 **12** | libemu_fbalpha / fbalpha2012 / mame2000 / pgm / fba / cps2 / extend / snes9x / snes9x2010 / mgba / vbam / nestopia |
| 工厂 DCL（default_core_list @0x3b0254）独有 **4** | libemu_gpsp / prosystem / vrt / dosbox |
| 共有 6 | libemu_sfc / md / nes / pcsx / stella / tgbdual |

**运行时角色分层（源码实测，非推测）**：

| 层 | 机制 | 源码证据 |
|---|---|---|
| 默认加载 | DCL 扫表（GetCoreIndex）定 Filetype → 平台 Load 函数 dlsym | FUN_00016f08_FilePreEmu.c:54,103 → FUN_002b5624_GetCoreIndex.c |
| 显式覆盖 | filelist.xml 135 条（NNN/xxx.zip → core） | mui_LoadSetting 链 |
| 交互选择 | config.xml 的 `supported_extensions` 匹配 FilenameExt 的 core 列表 → 用户手选 | FUN_00021c08_SeletEmuCore.c:135-154（mxmlFindElement 遍历）；调用方 = mui_menu/mui_type/mui_search/mui_recent/mui_shoucang/mui_setting 共 7 处 |

（注：`libemu_fbafast.so` 仅在 filelist.xml 出现 1 次（folder 000），不在 config.xml 也不在 DCL ⇒ 纯 filelist 显式条目。）

⇒ **config.xml 不是默认映射表**（与 R36S Wiki 的描述不同）—— 本机它是「手动选 core」的候选池；
12 个 config-only core 只可能经交互选择到达；4 个 DCL-only core（gpsp/prosystem/vrt/dosbox）
走默认扫表路径但**不在**交互候选池中。R36S 把 config.xml 当主映射 = 框架同源、配置分层不同。

## 4. R36S Wiki 对 rkgame 菜单行为的增量解释

1. **启动链**：`icube_start.sh` kill hcprojector → `icube` → `rkgame`（本机 §九 autorun 机制实测：
   autorun 空 → main_Menu；非空 → 分派）。R36S 描述与本机 autorun 分派互补（R36S 无 autorun 描述）。
2. **gamelist 标记位**（本机 setting.xml `<ui ... gamelist="1"/>` 仅 ui_cn 为 1）：
   语言包同时决定「游戏列表数据是否随该语言包提供」—— R36S Wiki 未记载此字段 ⇒ 本机特有。
3. **hotkey 语义**：R36S 记 SELECT+START / FN+A / FN+B；本机 setting.xml 记 `savestatehotkey=3072`(0xC00)
   + `autorestore=03` ⇒ 快速存档/读档键位可配（3072 = 组合键掩码，需与 InitKeyMapping 的 keyMapping 对表）。
4. **封面/占位图**：R36S 320×240 PNG + nodata.raw；本机 M6R 读到 ui.cfg+menu.raw，封面机制
   与 R36S 同代（SF3000 同硬件世代）。

## 5. 未采用/待证项（诚实声明）

- R36S 的 `filelist.csv` per-platform 列表机制本机无对应物（本机 filelist.xml 是 folder→core 映射，
  不是游戏显示名列表）⇒ **不借用**。
- 屏幕分辨率（R36S 640×480 vs 本机 FBA 输入 320×240）未对齐，不引入 R36S 数值。
- R36S 的 26 语言 .cpd 与本机 10 个 ui_*.zip：数量不同，仅借用「语言包=gamelist 提供者」的机制解释。
