# T11–T13 验收台账（rkgame 1:1 复刻）

> 本文件只记**可核对的判据与证据路径**。逐轮推理过程见 `PROGRESS.md`（R2xx 段），
> 长期结论见 `PROJECT-MEMORY.md`。生成时间 2026-10-22。
> 状态口径：**达成** = 有一次真实执行产生的日志/文件/strace 证据，不是静态推断。

## 环境基线（本轮所有验收共用）

| 项 | 值 |
|---|---|
| 被测产物 | `build/rkgame.rebuilt.elf`，sha256 前缀 **`a31fc3de5efed1ee`**，`obj 214/214` |
| 装置 | CNB 云开发 + `qemu-arm-static` + 设备真 sysroot `/arm-root-device` + guest shim + 三桩（libkms/libdrm/libasound） |
| 输入路径 | **菜单路径** `main → main_Menu → mui_run_game`（`setting.xml` 的 autorun 置空） |
| 手柄身份 | shim 合成 `/proc/bus/input/devices` ⇒ `20bc:5500:0111`（`CGM_USB_VID/PID/VER`），命中原厂 `joystick.zip` 的 `20bc_5500` 表 |
| 键位 | A=0x2000(btn0)、TL1=0x400(btn6)、TR1=0x800(btn7)（`buttontoi` 权威表） |
| 一键脚本 | `tools/cnb_t13_autorun.sh`（`UP_SET=full` / `MODE=menu` / `TWOPASS=1`） |

## T11 菜单/按键链路

| 判据 | 实测 |
|---|---|
| `js0` 打开 | `Gamepad 20bc 5500 111 js0 Opened!` |
| 进入菜单主循环 | `mui_menu` 主循环运行（进程 40 s 不崩，`exit=124`） |
| 按键被消费 | 扫键 btn0–11 后出现 `mui_run_game:000/1941.zip` |
| **状态** | ✅ **达成** |

证据：`report/t13/debug.log`

## T12 core 加载链（`use … to run`）

| 判据 | 实测 |
|---|---|
| 遍历到 cps2 | `open …/cores/libemu_neogeo.so fail` → `capcom fail` → `pgm unsupport.` → `fba unsupport.` → **cps2 无 unsupport** |
| `retro_is_support` / `Load_Proc1` / `retro_load_game` 三条件 | 全通过（`use %s to run %s` 是**三条件全过才打印**的那一行） |
| 核心开始读 ROM | `01 41em_30.11f 128KB` … 共 **12** 个 1941 ROM 文件 |
| 进入 `Load_Proc2` 主循环 | `pal_ntsc:0` / `find _SetFrameSkip process` |
| **状态** | ✅ **达成** |

证据：`report/t13/debug.log`（第 7/8/28/29/30 行附近）

## T13 存档落盘 + 读回

| 判据 | 实测 |
|---|---|
| 热键触发 | `SaveDefaultState:/sdcard/cubegm/saves/000/1941.sav`（`savestatehotkey=0xC00` = TL1\|TR1 双键同按） |
| `retro_save_state` 成功 | `retro_save_state:…` ×**59**（该行仅在 `retro_serialize` 成功后打印） |
| 存档文件 | **8496 B**，sha256 `0e2783af8c09ddd343dd2c0882b651b33ab4bd17d2ea8fa86f6afd02025a302a` |
| 格式自洽 | 头 4 B `2c 21 00 00` = **8492 = 8496−4**（原长）；紧随 `78 9c` = **zlib 流头** |
| **读回** | 第二遍：`access(...,F_OK) = 0`、`openat(...,O_RDONLY) = 9` |
| **状态** | ✅ **达成** |

证据：`report/t13/debug.log`、`report/t13/t13_stderr2.txt`

## 目的 2 · SRAM 电池存档（`.srm` 写 + 读回，无白名单）

> 属「有意偏离」，受 `CGM_UPGRADE=sram` 开关控制，默认关（关 = 1:1）。样本 = MD 梦幻模拟战2（用户提供，2,097,664 B，自带 16 KiB SRAM）。

| 判据 | 实测 |
|---|---|
| 真实 SRAM 大小（core 自报） | `retro_load_game -> 1`，`SAVE_RAM id=0 size=16384 ptr=0x64bc0`、`RTC id=1 size=0`（无 RTC，合法跳过） |
| `.srm` 落盘（游戏内） | 第一遍 strace `O_WRONLY` ×55，16384 B（每 ~5s 脏才写 + fsync，断电保护已从菜单链路挪到**游戏主循环** `Load_Proc2`） |
| **`.srm` 读回** | 第二遍 strace `openat(...,"langrisser2.srm",O_RDONLY)=9` ×1 + stdout `[sram] load SAVE_RAM <- ... (16384 B)` |
| 无白名单 | 未做任何游戏登记；md core + ROM 自动识别（size>0 才存/读），覆盖「无电池/记忆卡/需电池维持」三类 |
| 产物 | `build/rkgame.rebuilt.elf` sha256 前缀 `020cc65df129bb6c`，obj 216/216 |
| **状态** | ✅ **达成** |

证据：`report/t13/t13_stderr2.txt`、`report/t13/t13_stdout2.txt`、`report/t13/debug.log2`

> 关键根因（R256）：① poll 曾挂在 `ReadJoystick()`（菜单输入），游戏主循环走 `ReadJoystickProc()` 不经过它 ⇒ 断电保护从未生效，已挪到 `Load_Proc2`；② `.srm` 读回曾用 3s 壁钟超时窗口，qemu 下 guest 慢于 wall clock ⇒ SRAM 延迟建立后窗口早已过期，已改 pending 持久到 size>0。

## 已确认的**装置侧**前提（不是产品缺陷，缺一即失败）

| 前提 | 缺失时的现象 |
|---|---|
| `setting.xml` 的 `<logfile>` 必须是**绝对路径** | `RARCH_LOG` 走 stdout 全缓冲，被 timeout 杀掉即丢日志 |
| `/sdcard/cubegm/saves/<NNN>/` 目录存在 | `retro_save_state` 的 `fopen("wb")` **静默失败**（源码无 else 分支） |
| 手柄身份命中 `joystick.zip` 的某张表 | 键位表为空 ⇒ 任何按键都映射不到 `0x2000` |
| 走**菜单路径**（autorun 置空） | `autorun` 绕过 `main_Menu` ⇒ `DAT_003af29c` 为 NULL ⇒ `progress()` memset 写代码页崩溃 |
| 三桩 + shim + `/dev/dri` | 无桩则在 `InitDisplay`/`gr_init` 就崩，走不到任何菜单 |

## 已知边界（有意不修）

| 项 | 说明 |
|---|---|
| `saves/ARCADE/*.scf` 文件名为空 | `RomName` 只在 `mui_run_game` 赋值；`autorun` 路径必然为空（原厂同理）⇒ **不许修**，修了偏离 1:1 |
| `find font.ttf in ui_cn.zip fail` | 原厂 `ui_cn.zip` 本来就不含 `font.ttf`（独立文件在 `cubegm/font.ttf`），属正常回退信息 |
| `progress()` 不判空 | 原厂行为；我们该做的是**走对入口**，不是给原厂代码打补丁 |

## 本轮修掉的**产品侧**真缺陷

| 缺陷 | 证据 | 修法 |
|---|---|---|
| `code_convert_constprop_22` 6 处调用**缺第 4 参**（`memset(out,0,out_len)` 用栈垃圾 ⇒ 负长度崩溃） | 工厂反汇编 `r3=0x100/0x80/0x80`；`proto.h` 原为 K&R 空括号声明，不校验实参 | 改真原型 + 6 处补参（`mui_run_game` ×3、`shoucang` ×3） |
| （同类隐忧）`build/obj` 曾 23 个 `.o` 旧于源码 | `tools/artifact_freshness_gate.py` 判 STALE rc=2 | 门禁接入 `cnb_gates.sh` + `cnb_env.sh` 自愈清缓存 |
