# 设备端诊断仪（DIAG）—— 工程手册

> 面向：接手本仓的工程侧 agent / 后续维护者。
> 面向**用户**的操作步骤在 `_sdcard_drop/READ-ME-FIRST.txt`（由 `tools/stage_sd_diag.py` 生成）。

---

## 一、为什么必须"编进 rkgame 自己"

设备是**游戏盒子**（HDMI + 内置扬声器，**无命令行**），启动链：

```
U-Boot → kernel → init → rcS → S80icube → exec /sdcard/cubegm/icube → rkgame
```

这一整条链上的文件**全是原厂的**（红线：一律不动）⇒ 我们**没有任何地方**能注入
`LD_PRELOAD`、环境变量、或启动脚本改动。

因此设备上唯一可行的观测手段 = **把诊断能力编进我们自己构建的那个 rkgame**。
两条都是**链接/编译期**开关，**零源码改动**：

| 手段 | 覆盖 | 开关 |
|---|---|---|
| 函数级轨迹 | 每个函数的进入/退出 | `-finstrument-functions` |
| 调用级轨迹 | 文件 / ioctl / mmap / dlopen / 线程 / 时间 / 信号 | `-Wl,-wrap=<sym>` × 65 |

---

## 二、构建

```sh
ZIG="<...>/zig.exe"
CC="$ZIG cc" OPT=-Os PY=<python> sh tools/build_diag.sh build/rkgame.diag
```

5 个阶段：① 编诊断仪自身（**不带**插桩）② 编 213 个专有函数（带插桩）
③ 编 xunzip（带插桩）④ 生成 wrap 列表 + **自检门禁** ⑤ 链接 + 产物自检。

**耗时**：本地约 **2 分钟**（213 个文件重编）。
**产物**：`build/rkgame.diag`（比交付版 `build/rkgame.rebuilt.elf` 大约 8 KB + 768 KB `.bss` 环形缓冲）。

### 2.1 R259：升级观测点在场（both 诊断版）

第十一节的 evdev/sram 观测点依赖 `src/upgrade/` 模块被编进产物，因此：

| CGM_UPGRADE | 诊断版能力 | 用途 |
|---|---|---|
| **both（默认）** | evdev 426 条库装载/匹配 + SRAM 双通道读写全部留痕 | **真机验收用这版** |
| sram / evdev | 单项在场 | 单问题定位 |
| 0 | 纯净 1:1（无观测点） | “交付口径本身出问题”时用 |

规则与交付版共用 `tools/cgm_upgrade_flags.sh`（纪律 69：同一规则禁止写两处）。
升级模块**不插桩**（`cgm_evdev_poll`/`cgm_sram_poll` 每帧/15ms 调，插桩会刷爆环形缓冲）。

### 2.2 R259：CNB 云开发额度耗尽后的构建路径 = GitHub Actions

```sh
# 手动触发（可选 upgrade 参数：both|sram|evdev|0）
gh api -X POST repos/Lieguch/cubegm-build-monkey/actions/workflows/diag-build.yml/dispatches \
  -f ref=main -f 'inputs[upgrade]=both'
# 或：push 触碰 1to1/src/diag|src/upgrade|tools/build_diag.sh|tools/diag_wraps.sh 自动触发
```

产物 = Actions artifact **`rkgame-diag`**（`rkgame.diag` + `.sha256`）。CI 末步做符号终检
（诊断仪 6 关键符号 + `cgm_evdev_poll`/`cgm_evdev_ready`/`cgm_sram_poll`/`controller_db.txt` 在场）。
**合规性**：触发 CI 只为“正式构建产出物”（诊断版二进制），不用于调试/验证。

### 两个硬性纪律（不遵守就会得到"看起来正常"的假日志）

1. **诊断仪自身的文件绝不能带 `-finstrument-functions`**
   ⇒ 否则 `cgm_frame_enter` 自己会被插桩 ⇒ **无限递归**。
   GCC 有 `-finstrument-functions-exclude-file-list`，但 **clang/zig 没有** ⇒
   本脚本改用"诊断仪单独一次编译、不带该标志"，同一份脚本在 GCC 与 zig 下都对。

2. **`WRAPS` 列表与 `cgm_wrap.c` 的实现必须一一对应**
   ⇒ 少一个就是 `ld.lld: error: undefined symbol: __wrap_xxx`（本项目实测漏了 6 个）。
   链接器确实会硬失败（这点是对的），但报错在 200 行之后、信息量低 ⇒
   脚本里有自检把它提前成一句人话（exit 11）。

---

## 三、`-wrap` 在 zig 下的写法（**踩过的坑，GAP 16.65**）

**zig 的驱动层只认单横线 `-wrap=`，不认 `--wrap=`。** 实测七种写法：

| 写法 | 结果 |
|---|---|
| `-Wl,--wrap=open` | ✗ `error: unsupported linker arg: --wrap` |
| **`-Wl,-wrap=open`** | **✓ 可用** |
| `-Wl,--wrap open` | ✗ 同 `--wrap` |
| `-Xlinker --wrap=open` | ✗ 同 `--wrap` |
| `-Xlinker --wrap -Xlinker open` | ✗ 同 `--wrap` |
| `-Xlinker=--wrap=open` | ✗ `Unknown Clang option` |
| `-Wl,--defsym=…` | ✗ `unsupported linker arg: --defsym` |

**行为自证**（不是只看参数被接受 —— 这条纪律必须守）：

```
不加 wrap 时 产物未定义符号含 `open`
加 -Wl,-wrap=open 后 `open` 从产物未定义符号里**消失** ⇒ 重定向真的发生了
```

`tools/build_diag.sh` 按编译器分派：zig → `-Wl,-wrap=`，GCC(GNU ld) → `-Wl,--wrap=`。

---

## 四、产物文件与字段含义

| 文件 | 内容 | 拿它回答什么 |
|---|---|---|
| `BEGIN.txt` | 本次运行横幅（pid / 级别 / 构建时间 / 阳性对照说明） | **诊断版到底跑没跑起来** |
| `env.txt` | environ / cmdline / maps / auxv / status / meminfo / cpuinfo / mounts | 运行环境是否如预期 |
| `maps.start.txt` | 启动时 `/proc/self/maps` | **离线把地址变符号名（必需）** |
| `trace.log` | 主事件流 | 文件/ioctl/dlopen/线程/信号/汇总 |
| `frames.bin` | 函数轨迹（崩溃或退出时**全量** dump） | 崩溃前的完整调用历史 |
| `frames.snap.bin` | 每 5 秒一次快照 | **卡死/断电也能拿到最近历史** |
| `crash.txt` | siginfo + 全部寄存器 + fp 链 + 栈扫描 + maps + fd | 崩在哪、什么信号、谁调用的 |
| `heartbeat.txt` | 每 5 秒一行（含调用计数） | **区分"卡死"与"崩溃"** |

日志行格式：

```
E <addr8> <depth> <ms>          函数进入
X <addr8> <ms>                  函数退出
IO  open "path" fl=0x2 ret=4
IO  ioctl fd=7 req=0x0000c008 ret=0      ★ DRM/KMS/ALSA/evdev 全走 ioctl
IO  mmap len=… ret=0x…
DL  dlopen "driver.so" ret=0x…  /  dlsym "…" -> 0x…
TH  pthread_create fn=…
TM  nanosleep 0.100000000
SG  signal sig=11 handler=…
##  SUMMARY …                    每 15 秒汇总
##  EXIT / ABORT / ## BOOT
```

`ms` 是 **`CLOCK_MONOTONIC`**（开机起算），不是墙上时间。
环形缓冲 65536 帧 × 12 B = 768 KB（`.bss`），约 3.2 万次函数调用的历史。

---

## 五、离线符号化

```sh
python tools/diag_symbolize.py build/rkgame.diag <取回的>/frames.bin \
    --maps <取回的>/maps.start.txt --crash <取回的>/crash.txt \
    --out report/diag_symbolized.txt
```

输出：① 摘要（帧数/丢弃数/覆盖函数数）② **崩溃前轨迹**（按深度缩进的调用树）
③ 热点函数 Top 40 ④ **最深调用栈**（最可能指出"卡在哪/崩在哪"）⑤ 无法归属的地址单列。

**纪律**：报告里 `0 帧` 会显式区分两种原因（(a) 插桩前就退出 / (b) 诊断仪没跑起来），
并提示去看 `trace.log` 第一行 —— 不允许把"符号化失败"当成"没走到"。

---

## 六、级别（`/sdcard/cubegm/_diag/cfg.ini`）

| level | 内容 | 代价 |
|---|---|---|
| 0 | 只留崩溃报告 | 最小 |
| 1 | 生命周期 / 信号 / 文件 open-close / dlopen / 线程 | 小 |
| **2（默认）** | + read/write/lseek 偏移长度 + **每次 ioctl** + mmap | 中 |
| 3 | + 内容 hex + malloc/free 明细 + 每次 clock_gettime | **最全，最慢** |

文件缺失或值非法 ⇒ **退回默认 2**（不报错，避免设备上"配置写错就啥都没有"）。

---

## 七、已知限制（诚实清单）

1. **`.text` 里嵌的工厂镜像（`.fimg_text`）不会被插桩** —— 它是 `.incbin` 进来的**数据**，不是编译产物。
   好在我们 741/804 个工厂函数已由自己的 `.text` 提供，插桩覆盖率就是这部分。
2. **上游库（`build/upstream/*.o`）未插桩** —— 只做了 libc 级的 wrap。
   若要覆盖 mxml/stb/xmp3 的函数级轨迹，需按同样方式重编它们。
3. **fp 链可能不可用** —— 交付口径是 `-Os`（默认 omit frame pointer），
   `crash.txt` 的 `fp chain` 段可能无效；已用 **栈扫描 + 环形缓冲** 兜底。
4. **信号处理器内不可用非 async-signal-safe 函数** —— 所以崩溃报告只写
   siginfo/寄存器/栈扫描/maps/fd，**不写堆内容**。
5. **`cgm_frame_enter` 在 `cgm_diag_boot` 之前被调用会被丢弃** ——
   极早期（`_start` 到 `__libc_start_main` 之间）的调用不在轨迹里。
6. **`stdout` 不走我们的日志** —— 诊断信息全在 SD 卡文件里，与 guest stdout 分开，
   便于与 CI 的行为差分口径对齐（那条纪律：别把即时输出混入事件序列）。

---

## 八、维护：新增一个被拦截的 libc 符号

1. 在 `tools/build_diag.sh` 的 `WRAPS` 列表加名字
2. 在 `src/diag/cgm_wrap.c` 加 `__real_<sym>` 声明 + `__wrap_<sym>` 实现
3. （自检门禁会替你挡第 2 步的遗漏）
4. `sh tools/build_diag.sh` ⇒ 应看到 `✓ 自检：N 个 wrap 符号全部有实现`

---

---

## 九、autorun 劫持（真机 drop-in 前置步骤）

> **红线提醒**：此节改动涉及原厂 `setting.xml`，属"改原厂文件"范畴。
> 执行前必须明确：**改什么 / 怎么改 / 如何回退**。未获用户显式确认不得落地。

### 9.1 目的

原厂 `golden/sdcard_min/setting.xml` 第一行**实测**为 `<autorun file="" driver="" />`
（file 与 driver 均为空 ⇒ 不开机直进游戏）。该字段由 **rkgame 自己的 `main`** 读取：
`autorunfile[0]=='\0'` 走 `main_Menu()`；非空则按前缀分派（`/USBJoystickTest`→TestUSBJoy、
`/JoystickTest`→JoystickTest、其余→`autorun(file,driver)`）。
`autorun()`（60B）语义：`RARCH_LOG("autorun %s %s")` → `InitScr()` → **driver 非空则立即 return**
→ 否则 `run_game(file)`。
⇒ 改变应从**实测空值**出发：目标是让真机拉起**自己构建的** `rkgame`（或 `rkgame.diag`），
  需把该字段从空改为目标文件名（同下 9.2）。

### 9.2 改法（原子替换）

```sh
# 备份（必做，回退依据）
cp /sdcard/cubegm/setting.xml /sdcard/cubegm/setting.xml.factory.bak

# 替换 autorun 目标（★ golden 实测格式是**双属性** `<autorun file="" driver="" />`，
#   旧的单属性 sed 模式**匹配不上**，等于没改 —— 必须用整标签替换）
python3 - <<'PYEOF'
p = '/sdcard/cubegm/setting.xml'
d = open(p, 'rb').read()
old_line = b'<autorun file="" driver="" />'
new_line = b'<autorun file="rkgame" driver="" />'
assert old_line in d, 'setting.xml 无预期的 autorun 原值，中止（防误改）'
open(p, 'wb').write(d.replace(old_line, new_line, 1))
print('autorun 已改')
PYEOF

# 校验（必须看到新值）
grep '<autorun' /sdcard/cubegm/setting.xml
# 期望输出：<autorun file="rkgame" driver="" />
```

### 9.3 回退流程

```sh
# 从备份还原
cp /sdcard/cubegm/setting.xml.factory.bak /sdcard/cubegm/setting.xml
grep '<autorun' /sdcard/cubegm/setting.xml
# 期望输出：<autorun file="" driver="" />（golden 原样）
```

### 9.4 BEGIN.txt 判定

诊断版 `rkgame.diag` 启动后会在 `/sdcard/cubegm/_diag/` 下写 `BEGIN.txt`（首行 = 构建 SHA + 时间戳）。
**真机 drop-in 成功的最低判据** = 该文件存在且内容非空。若不存在 ⇒ 启动链在 exec 之前就已失败
（路径错 / 权限错 / setting.xml 未生效 / 内核 panic），**不要继续后续测试**。

### 9.5 日志通道 + core 符号清单 + ROM 匹配判据（R233/R241 定案，权威）

**① `logfile` 必须写绝对路径**（R233 实测定案）
`GetConfig` 读 `setting.xml` 的 `<logfile>`；**相对路径分支有漏参 bug**
（`sprintf(local_1020,"%s%s",work_path)` 少了文件名）⇒ 相对路径等于没配。
```xml
<logfile>/sdcard/cubegm/debug.log</logfile>
```
生效后 `RARCH_LOG` 写 `log_file_fp` 并 `fflush+fsync`（`FUN_00009e6c_RARCH_LOG_V.c`）；
未生效则写 stdout（全缓冲，qemu 下被 `timeout` 杀掉即丢失）⇒ **不配 logfile 的日志不可信**。

**② core 必需符号有两组，别混为一谈**（R240/R241）

| 组 | 符号 | 用途 | cps2/fba 实测 |
|---|---|---|---|
| A. 进游戏主循环（`Load_Proc1` 的 6 个） | `retro_set_video_refresh` / `retro_set_audio_sample_batch` / `retro_set_input_state` / `retro_set_environment` / `retro_set_input_poll` / `retro_init` | `FBA_Load` 的 ② 分支 | **全 DEFINED** |
| B. 存档链路（`Load_Proc2` 之后） | `retro_serialize_size` / `retro_serialize` / `retro_unserialize` / `retro_get_memory_data` / `retro_get_memory_size` | 前端 `retro_save_state`/`retro_load_state` 内部 `dlsym` | **全 DEFINED** |

★ **`retro_save_state` / `retro_load_state` 不是 core 导出的**（两个 core 都 **ABSENT**）；
它们是**前端自有实现**：`FUN_002b83e8_retro_save_state.c`（@0x2b83e8）内部
`dlsym("retro_serialize_size")` → `dlsym("retro_serialize")` → `compress`（zlib）→
`fwrite(4字节原长 + 压缩数据)`。⇒ **判 core 能否存档，查 B 组而不是 `retro_save_state`**。

**③ 存档落盘的两条真实路径**

| 触发器 | 函数 | 落盘路径 | 日志锚 |
|---|---|---|---|
| 游戏主循环按 `savestatehotkey`（`setting.xml` 默认 **3072 = 0xC00**） | `SaveDefaultState` | `<work>saves/<gametype>/<RomName>.sav` | `SaveDefaultState:%s` → `retro_save_state:%s` |
| 游戏内 PauseMenu（`GameMenuHotKey` 默认 9）→ 存档页 → A | `mui_save_state` | `<work>states/<ArchivePath>/<RomName>.sv%d` | 无（只有 `retro_save_state:%s`） |

**④ ROM 是否被 core 接受：查文件名 + CRC 是否在 core 的 `.rodata` 里**
零执行环境判据（`python` 读 ELF + zip，不需要 qemu）：
```python
import zipfile, struct
z = zipfile.ZipFile('000/1941.zip')                      # 待测 ROM
core = open('golden/sdcard_min/cores/libemu_cps2.so','rb').read()
names = [i.filename.encode() for i in z.infolist()]
crcs  = [struct.pack('<I', i.CRC) for i in z.infolist()]  # CRC32 按 LE 4 字节
print('文件名命中', sum(n in core for n in names), '/', len(names))
print('CRC 命中',   sum(c in core for c in crcs),  '/', len(crcs))
```
R241 对 `000/1941.zip`（19 文件）实测：**文件名 19/19、CRC 19/19 全命中 `libemu_cps2.so`**
⇒ core 必然接受该 ROM。同理可对任意 ROM/core 组合先做本机预判，**不必烧核时**。

**⑤ core 资产不入 git，云上必须 tar 上传**
`.gitignore` 第 14-18 行排除 `golden/sdcard_min/cores/*.so`（闭源真机资产）。
⇒ 云上 `git clone` 只得到 `config.xml`/`filelist.xml`；**必须 tar 打包本地 `golden/sdcard_min`**
（`cnb_devqemu.sh` / `cnb_ladder.sh` / `cnb_t13_autorun.sh` 都是这么做的），否则各 core 全 `open ... fail`。

---

## 十、DRM/KMS 显示链 + ALSA 音频链观测点（视频/音频初始化入口权威清单）

> **本节来源**：Ghidra 反编译 `FUN_0000d678_InitDisplay.c` 与 `FUN_0000db08_InitSound.c`，
> 非猜测、非二手文档。每个符号都附源文件行号，可机械复核。

### 10.1 视频初始化入口（4 个 dlsym）

来自 `src/proprietary/hw/FUN_0000d678_InitDisplay.c`：

| 绑定方式 | 符号 | 用途 / 调用点 |
|---|---|---|
| dlsym(^30) | `video_driver_setting` | 设置显示参数（分辨率/帧率/格式） |
| run_process(^39) | `video_drivers_init` | 图形后端整体初始化（`run_process_constprop_0`） |
| dlsym(^42) | `video_driver_disp_frame` | 提交一帧到显示后端（**核心渲染出口**） |
| dlsym(^47) | `video_driver_setmode` | 切换显示模式（分辨率/刷新率变更时调用） |
| dlsym(^52) | `video_driver_get_size` | 查询当前显示尺寸（菜单/UI 布局依赖） |
| run_process（DeinitDisplay ^14） | `video_driver_deinit` | 显示后端整体反初始化 |

**假桩覆盖要求**：上表全部符号（含 `run_process` 携带的 `video_drivers_init` /
`video_driver_deinit`）必须出现在 `driver_stub.so` 的 `.dynsym` 导出表中，
且 `bind ∈ {GLOBAL, WEAK}`、`visibility != hidden`、`st_shndx != 0`。
仅存在于 `.symtab` 或为 LOCAL/hidden ⇒ 外部 UNDEF 无法绑定 ⇒ 计为**未覆盖**。

### 10.2 音频初始化入口（2 个 dlsym）

来自 `src/proprietary/hw/FUN_0000db08_InitSound.c`：

| 绑定方式 | 符号 | 用途 / 调用点 |
|---|---|---|
| dlsym(^17) | `sound_driver_init` | 初始化音频后端（采样率/通道/缓冲） |
| dlsym(^38) | `sound_driver_playframe` | 提交一帧 PCM 数据（**核心音频出口**） |
| run_process（DeinitSound ^14） | `sound_driver_deinit` | 音频后端反初始化 |

**覆盖要求同 10.1**。

### 10.3 DRM_IOCTL 计数作为渲染管线一致性铁证

`video_driver_disp_frame` 的真实现必然触发 `DRM_IOCTL_MODE_ADDFB2` + `DRM_IOCTL_MODE_PAGE_FLIP`。
在 qemu 或真机的 strace/kern.log 中统计这两个 ioctl 的调用次数：

- **> 0 次** ⇒ 渲染管线至少走到提交帧这一步（M6R 里程碑的必要条件）。
- **= 0 次但进程存活** ⇒ dlsym 成功但后端未真正渲染（假绿风险，需查 shim 实现）。
- **dlsym 返回 NULL** ⇒ 进程通常在 InitDisplay 阶段就 abort（exit ≠ 124）。

### 10.4 qemu 结构性限制（诚实声明）

qemu-system-arm 无 RK3036 机器模型；`-dtb` 只把设备树交给内核，**不改变 qemu 提供的硬件**。
因此以下事项**只有真机能答**，qemu 结果不能作为最终判据：

- 真 SFC MMIO 语义（地址映射 / 寄存器位宽 / 时序）
- 「sdcard is damaged」校验逻辑（原厂对 SD 卡 CID/CSD 的检查）
- 真面板时序与背光控制
- 真手柄 ADC 采样与按键映射

qemu 的价值在于**启动链连通性 + 软件层行为对齐**；上述硬件相关缺口必须留给真机 drop-in 验证。

**9 符号清单的机械守护**：`tools/driver_stub_coverage.py` 第 165 轮起内置 `ABI_SYMS`
（上面 9 个符号，权威来源 = golden driver.so `.dynsym` 实测 DEFINED + 上述源码调用点），
`--print-need private` 导出该清单；`tools/_r165_abi_selftest.py` 提供判别力自证
（腿A 真库覆盖 / 腿B 删符必判缺 / 腿C 选错 provider 必判缺）。任何代替/桩化 driver.so
的产物都必须全数导出这 9 个符号，缺一即亮红。
但根据 PROGRESS.md §0.0 约束 2/3：**模拟进度达 100% 之前，禁止在任何文档/报告/对话中提及真机验证**；
达到 100% 后由 agent 主动向用户提出。本节仅为技术备忘，不构成"现在就该上真机"的建议。

---

## 十三、R259：both 诊断投放包（真机验收就绪态）

### 13.1 投放包生成与内容

```sh
python tools/stage_sd_diag.py            # 读 build/rkgame.diag + probe + controller_db.txt
```

产出 `_sdcard_drop/`（R259 实测内容）：

| 文件 | 字节 | sha256 前缀 | 作用 |
|---|---|---|---|
| `cubegm/rkgame` | 5,460,216 | `b8e624c2fd80de5a` | both 诊断版（SRAM+evdev+插桩+wrap） |
| `cubegm/controller_db.txt` | 70,652 | `f14edcfd58f3ad6a` | **evdev 全量库 426 条（必须放）** |
| `cubegm/rkgame.probe` | 3,572 | `9bc91b758e4743a9` | 最小探针（启动链失败时二分定位） |
| `cubegm/_diag/cfg.ini` | 393 | `b662fed9fdd69ff7` | 日志级别 level=3 |
| `READ-ME-FIRST.txt` | 8,594 | — | 面向用户的全部步骤（自包含） |

产物来源：GitHub Actions `diag-build.yml` run `39908481619`（conclusion=success，
artifact `rkgame-diag`），本地 sha256 与 CI 自记逐字节一致。

### 13.2 投放与回退（详见 READ-ME-FIRST.txt）

1. **备份**：SD 上 `cubegm/rkgame` → `cubegm/rkgame.factory.orig`（再复制到电脑，双保险）；
2. **部署**：覆盖 `rkgame` + 放 `controller_db.txt` + 放 `probe` + 放 `_diag/`；
3. **回退**：从 `.factory.orig` 还原，删 `controller_db.txt`/`_diag/` 即可恢复原厂现场。

★ **不需要改 `setting.xml`**：启动链（S80icube → icube）写死拉起 `cubegm/rkgame`，
drop-in 只换二进制本身；第九节的 autorun 劫持仅用于"开机直进某游戏"的实验场景，与验收无关。

### 13.3 判据口诀（trace.log / stdout）

| 验什么 | 日志特征 |
|---|---|
| 诊断版跑起来了 | `_diag/BEGIN.txt` 存在且非空；`trace.log` 首行 `## BOOT` |
| evdev 手柄链路接通 | `ioctl` req 高字节 = `0x45`（EVIOC 族）+ `read` 长度 = **16**（evdev 事件；8 = 还在 joydev） |
| 全量库装载 | `[evdev] db 载入 426 条 profile` |
| SRAM 落盘 | `[sram] flush SAVE_RAM -> …xxx.srm (16384 B)` + SD 上 `.srm` 文件出现 |
| SRAM 读回 | 第二遍 `[sram] load SAVE_RAM <- …xxx.srm (16384 B)` |
| core 加载 | `use /sdcard/cubegm//cores/libemu_XXX.so to run …` |
| 渲染管线 | `DRM_IOCTL_MODE_ADDFB2` + `MODE_PAGE_FLIP` 计数 > 0（见 10.3） |

### 13.4 已知边界（诚实清单）

- **qemu 无法验证 evdev 完整匹配**：无 `/dev/input/event*`（shim 只合成 `/proc/bus/input/devices`）。真机插入手柄后按 13.3 口诀判读。
- **升级模块不插桩**：`cgm_evdev_poll`/`cgm_sram_poll` 每帧/15ms 调，插桩会刷爆环形缓冲（build_diag.sh [2b/5] 注释）。
- **`CGM_SKIP_MODEL_GATE=1`**：诊断版 wrap 故意重定向 libc 符号，"单侧未建模门禁"（防 diff_exec 假发散）对诊断版不适用，由 build_diag.sh 显式跳过；交付版不受影响。

### 10.5 命名纠错（R174，2026-10-13）—— 本节原名「hcge / fbdev_draw_frame 观测点」

原名沿用自第 161 轮的 `driver_so.h` 符号族，但**第 162 轮实测证伪**（PROJECT-MEMORY.md 纪律 159）：

| 符号族 | 归属 | 本机 driver.so 实测 |
|---|---|---|
| `hcge_*` / `fbdev_*` / `pinmux_*` | **SF3000（MIPS）** 兄弟产品 | **0 个**（`pyelftools` 扫 .dynsym+.symtab 全量，R174 复核仍为 0） |
| `video_driver_*` / `sound_driver_*` | **本机 RK3036G** rkgame 私有 ABI | 9 个（见 10.1/10.2） |
| `drmMode*` / `snd_pcm_*` | 本机 driver.so 的外部依赖 | 21 + 19 个 UND，由设备 sysroot 真实 libdrm/libasound 提供 |

**结论**：本机画面路径 = **标准 DRM/KMS**（AddFB2 + SetPlane + PageFlip，见 10.3 的
DRM_IOCTL 计数判据），不是 hcge 硬件命令队列。R161「画面不走 DRM」的猜测已作废，
本小节保留记录以防旧结论回潮。

---

## 十一、evdev 即插即用手柄 + SRAM 电池存档观测点（L4 目的 2 专用）

> 本节对应 `report/L4-evdev-sram-design.md`（第 207 轮）。**注意**：这两项是目的 2 的
> 「有意偏离」，合入交付版主体前，本节的观测点**先编进诊断版 `rkgame.diag`** 供真机预热。

### 11.1 evdev 观测点（热插拔手柄）

现有 wrap 已覆盖 `open` / `ioctl` / `read` / `close`，无需新符号，只约定 trace.log 判据：

| 观测 | trace.log 留痕 | 判读 |
|---|---|---|
| 枚举节点 | `IO open "/dev/input/eventN"`（可能多次 open+close，扫能力） | 每次 `EVIOCGBIT` 判定前必有对应 open |
| 能力查询 | `IO ioctl fd=N req=0x80184520…` —— **req 高字节 = `'E'`(0x45)**（EVIOC 族 type），`0x20+ev`（EV_KEY=0x21/EV_ABS=0x23） | 手柄判定（BTN_SOUTH+ABS）是否发生 |
| 名字匹配 | `IO ioctl … req=0x80484506`（EVIOCGNAME） | 是否真按名匹配、还是裸按 N 硬编 |
| 读事件 | `IO read fd=N …` 长度 **16**（evdev），对比 joydev 的 8 | **16 = evdev 生效；8 = 仍走旧 joydev** |
| 热插拔 | 拔出后 `access(eventN)` 失败 → close；插入后重新 open | 无 inotify 时靠轮询重扫，周期=读线程 15ms |

★ 判据口诀：**`req 高字节=0x45` + `read len=16` 同时出现 ⇒ evdev 热插拔链路已接通**；
只有 `read len=8` ⇒ 还在 joydev，evdev 未合入。

### 11.2 SRAM 观测点（电池存档）

| 观测 | 留痕 | 判读 |
|---|---|---|
| memory 接口解析 | `DL dlsym "retro_get_memory_data" -> 0x…` / `retro_get_memory_size` | dlsym 非 NULL ⇒ core 已提供 SRAM（第 207 轮实测 20/20 枚 core 都导出） |
| `.srm` 落盘 | `IO fopen "…/saves/000/xxx.srm" mode=wb` + `IO fwrite` | 存档动作是否触发 |
| `.srm` 回读 | `IO fopen "…/xxx.srm" mode=rb` + `IO fread` | 载档动作是否触发、读进 SRAM 视图 |
| 无电池存档 | 仅 dlsym 成功 + 无 fopen/fwrite（size=0 跳过） | **不误报**：dlsym 成功但无落盘 = 该 ROM 无 SRAM，属正常 |

★ 建议：`sram_save`/`sram_load` 内主动 `RARCH_LOG("SRAM save %s size=%u", path, n)`，
裸数据半径（SRAM 大小）据此可见 —— 这是"新增代码"，可安全加观测（不碰原厂逻辑）。

### 11.3 已知限制

1. evdev 端**依赖**设备内核是否带 evdev/joydev 两个驱动（kernel 4.4 通常都有）；万一某手柄
   只出现在 `/dev/input/jsN`（joydev）而 eventN 缺失，evdev 路径会退回"扫不到" ——
   trace.log 里 `open eventN` 全失败可定位。
2. `EVIOCGBIT` 的手柄判定（BTN_SOUTH+ABS）是跨手柄通用测试（libmanette/SDL 同款），
   但罗技/8bitdo 等的**轴范围标识**各不相同，最终映射仍须走 `joystick.zip` 的 VID:PID 校准
   （`GetJoystickConfig.c`），evdev 只替换"发现/读事件"这一层。

---

## 十二、产物新鲜度 + autorun 语义（R242/R243 定案）

### 12.1 产物新鲜度门禁（**任何行为结论之前先过这一关**）

```sh
python tools/artifact_freshness_gate.py --selftest         # 先证门禁有判别力（双向锚点）
python tools/artifact_freshness_gate.py                    # 再查当前仓库
```

| rc | 语义 | 处置 |
|---|---|---|
| 0 | FRESH | 可继续 |
| 2 | STALE（有 `.o` 旧于 `.c` / 缺 `.o` / ELF 落后） | **产物不可信**：`rm -rf build/obj build/upstream` 重编 |
| 3 | NOT-APPLICABLE（干净树，未构建） | 不计失败 |
| 11 | `src` 目录不存在（配置错） | fail-closed |

**真实事故（R242）**：`build/obj` 23 个 `.o` 比源码旧（最大 20.5 天），ELF 由旧对象重链 ⇒
`FBA_Load` 的 `sprintf(buf,"%s/cores/%s",work_path,*ppcVar4)` **只传 3 参**（无 r3）⇒
glibc 打 `(null)` ⇒ 10 槽 core 遍历全废（日志 `open …/cores/(null) fail` ×9）⇒
连续多轮围绕 `unsupport.` 的归因**前提不成立**。

已接入：`tools/cnb_gates.sh`（门禁清单）+ `tools/cnb_env.sh`（检测到 STALE 自动清缓存重编）。

### 12.2 `autorun` 路径**不会**给 `RomName` 赋值（原厂同样如此，不是缺陷）

`RomName` 的唯一赋值点是 `mui_run_game`（`FUN_000229f8:35` `mui_extract_basename(RomName,…)`）。
`main → autorun() → run_game()` **跳过 `mui_run_game`** ⇒ `RomName` 保持空串 ⇒
`InitKeyMapping0fEmuType` / `SaveDefaultState` 拼出的路径变成
`/sdcard/cubegm/saves/ARCADE/.scf`、`/sdcard/cubegm/saves/000/.sav`（**文件名为空**）。

⚠ **不许"修"这一条**：原厂二进制走同一路径得到同样结果，属**原厂行为**；
修了就偏离 1:1。要 `RomName` 有值必须走菜单路径（经 `mui_run_game`）。

⇒ 用 `autorun` 做实验时，**任何依赖 `RomName` 的功能（按键映射存档 `.scf`、默认存档 `.sav`）
都不可用于判据**；需要它们时改用 `menu.log` 选中项 + 按键路径。
