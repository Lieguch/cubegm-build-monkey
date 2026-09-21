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
