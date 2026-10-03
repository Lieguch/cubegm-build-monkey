# rkgame 1:1 复刻 · 全量差距审计报告

日期：2026-10-02 ｜ 范围：逐模块 / 逐文件 / 逐接口 ｜ 方法：联网核实 + 机械审计 + 源码走查

---

## 零、一句话结论

**假实现 / 假桩 / 假代码层面是「干净」的**（机械审计三项判据全 0 异常，见 §三），
真正挡在「1:1 可替代」前面的是**三处未完成的真实差距**，且全部有明确根因：

1. **架构级**：产物是「重建代码 1.32 MB + 工厂地址镜像 3.90 MB」的混合体，
   `PT_LOAD` 9 段 vs 工厂 2 段；刻度 A（对工厂数据符号的依赖）= **171 符号 / 2543 处**（收敛目标 0）。
2. **真机**：从未成功（零日志）。根因已定位为 ALSA 初始化序列差异（`InitSound` 的采样率常量混淆，**已修，未真机复验**）。
3. **符号级**：`.dynsym` 差异 6 项（`__strdup` / `islower` / `__gmon_start__` / `_ITM_*` / `_Jv_RegisterClasses`），
   另有我方多出 `strdup`（工厂用 glibc 内部符号 `__strdup`）。

**最需要警惕的不是假代码，而是「假验收」**：沙箱 qemu 里的 `M6R✓ M7✓` 是在**假硬件桩**下达成的，
不能替代真机验收（N6）；`prop_equiv` 的 size 比只是探针，不是等价性证据。

---

## 一、rkgame 真实背景（联网核实，非凭印象）

| 项 | 事实 | 来源 |
|---|---|---|
| 身份 | 掌机（R36S / SF3000 系）**主菜单引擎**，`cubegm/rkgame`，1.1 MB 级闭源二进制 | R36S-V2.6_Wiki |
| 文件类型 | ELF 32-bit ARM，EABI5 hard-float（`e_flags=0x5000400`），**未 strip** | 反编译 README |
| 工具链 | `armv7a-libreelec-linux-gnueabi`，glibc 2.24（**ARM，非 MIPS**） | `.file` 路径 |
| 体量 | 3,921,108 B，804 具名函数，2615 符号 | symtab |
| 启动链 | `icube`(启动器) → `rkgame`(菜单) → `driver.so`(显示/硬件) + `cores/*.so`(libretro 核心) | TreeFrogUI |
| 核心机制 | `dlopen` 核心 → `dlsym` libretro 回调 → fork+waitpid 跑游戏 | 反编译 §六 |
| 依赖 | libz / libdl / libm / libstdc++ / libpthread / libgcc_s / libc | NEEDED |
| 文档 | **无官方文档，全部靠逆向** | R36S Wiki 明示 |

**关键澄清**：SF3000 真机 SoC 是 HCSEMI C3100（MIPS），但 `rkgame` 这个二进制本身是 **ARM32**
（工具链 `armv7a-libreelec`，`e_flags` 硬浮点）——两者不矛盾：`rkgame` 属 DataFrog 的 **ARM 系**掌机
（R36S / R36HD / GB350），而非 MIPS 的 SF3000 一代。项目的 ARM32 判断**正确**。

---

## 二、项目现状全景（逐模块）

### 2.1 权威进度口径（PROJECT-MEMORY §7）

| 口径 | 实测 | 工具 |
|---|---|---|
| 工厂函数 | 804 = **581 上游开源**（61.3%）+ **223 专有**（38.7%） | symtab |
| 符号落位 | **741/804 = 92.2%**（0 指向 `.fimg_text`；63 "缺失"几乎全是 `.constprop/.isra/.part` 特化） | §7.1 |
| 专有重建 | **213/223 源文件**（无空壳） | `find src/proprietary` |
| 静态等价 | 213/213，★FAIL 0，p50=1.03 | prop_equiv |
| ABI/链路/PT_LOAD | 链路 PASS；**PT_LOAD 几何未对齐**（9 vs 2） | §6 门禁 |

### 2.2 模块清单（src/proprietary，213 文件）

| 模块 | 文件数 | 职责 | 代表函数 |
|---|---|---|---|
| main | 1 | 入口 | `main` |
| core | 26 | 核心加载/存档/游戏启动 | `Core_Load` `run_game` `retro_save_state` `retro_load_state` |
| mui | 42 | 菜单 UI | `mui_LoadSetting` `mui_do_file_list` `mui_run_game` |
| misc | 82 | 杂项/工具 | `GetFileCore` `run_process` `RARCH_LOG` |
| flash | 29 | SPI flash / 固件升级 | `UpdateROM` `spi_memcpy` |
| hw | 20 | 显示/音频/输入/手柄 | `InitDisplay` `InitSound` `DrawFrame` `AudioProcess` |
| input | 11 | 输入 | `joystick_poll` `mui_ReadJoystick` |
| config | 2 | 配置 | `GetConfig` |
| sys | 0 | （空，已并入其它模块） | — |

### 2.3 上游库（src/upstream）

| 库 | 状态 | 说明 |
|---|---|---|
| libiconv17 | ✅ 真源码 | GNU libiconv 1.17（目录名 `17` 是**误标**，`iconv.h:23` `_LIBICONV_VERSION=0x0110` = 1.16，与工厂一致） |
| libcharset | ✅ 真源码 | localcharset.c |
| mxml | ✅ 真源码 | Mini-XML v2.9 |
| stb | ✅ 真源码 | stb_truetype v1.26 |
| mp3 | ✅ 真源码 | Helix MP3 fixpnt |
| xunzip | ✅ 真源码 | XUnzip.cpp POSIX 移植 |
| **libiconv（无 17 后缀）** | ⚠️ **遗留手写桩** | 见 §3.3，**不参与编译**但仍在源码树 |

---

## 三、假实现 / 假桩 / 假验收 专项审计（核心）

### 3.1 机械审计（`tools/fake_impl_audit.py` 实测，可复算）

| 判据 | 结果 | 结论 |
|---|---|---|
| A. 空壳函数（我方 st_size≤4 vs 工厂） | **14 个空壳 = 工厂同样空壳**；工厂更大 = **0** | 无缺体 |
| B. 恒返回常量 | 两侧一致 4 个；不一致 = **0** | 无假常量 |
| C. 桩符号进产物 | compress/uncompress/`_Znwj`/`_ZdlPv`/malloc/free **全 SHN_UNDEF**，异常 **0** | 无假桩进产物 |
| D. 源码占位扫描 | 360 处命中，绝大多数是注释/官方自带 stub | 见 3.3 |

**⇒ 假实现层面「干净」——这是本轮审计最重要的正向结论。**

### 3.2 链接期桩（合法，产物里是 SHN_UNDEF，运行期由设备 DSO 解析）

| 文件 | 符号 | 为什么不是假实现 |
|---|---|---|
| `src/compat/zstub.c` | `compress`/`uncompress` | 函数体 `return -1` **永不执行**；只为让编译器闭嘴。`NEEDED` 只记 `libz.so.1` 不绑版本，运行期由设备 `/usr/lib/libz.so.1` 解析（避免 `ZLIB_1.2.x` 版本绑定） |
| `src/compat/cxx_ops.c` | `_Znwj`/`_ZdlPv` 等 | 仅静态试链用（zig musl 无 libstdc++）；真机部署走动态 libstdc++（与工厂一致） |

### 3.3 遗留假实现（需清理，当前不参与编译）

**`src/upstream/libiconv/`（无 17 后缀）**：STATUS.md 第八轮已记录这是**手写桩**（自称"简化版"，iconv.c 613 行），
1:1 不可用，已改抓 GNU tarball 生成 `libiconv17/`。`tools/build_upstream.sh:204` 用 `LD=$ROOT/src/upstream/libiconv17`，
**旧目录已不参与编译**，但 208 个 `.h` 仍躺在源码树里，是「误导性残留」（若有脚本误 `-I` 到它会静默用桩）。
→ **根治：删除或改名为 `libiconv-legacy-stub/`（带 README 警告）。**

### 3.4 沙箱专用桩（不进产物，仅 LD_LIBRARY_PATH 注入）

| 桩 | 用途 | 是否进产物 |
|---|---|---|
| `build_libkms_stub.sh` → 空 libkms.so.1 | 满足 driver.so 的 DT_NEEDED（`kms_*` 无未定义符号） | ❌ |
| `build_libdrm_stub.sh` → drm_stub.c | 让闭源 driver.so 在无 /dev/dri 的沙箱里"过" DRM 初始化 | ❌ |
| `build_libasound_stub.sh` | ALSA 桩 | ❌ |
| `guest_shim/{drm_stub,alsa_stub,fake_mem,stub_core}.c` | 让沙箱走真机路径（公平注入两侧） | ❌ |

这些是**验收环境桩**，不是主链假实现。但它们的副作用必须写清楚（见 §四·假验收）。

### 3.5 假验收（★ 最需要警惕的一类）

| 现象 | 为什么是"假验收" | 真实判据 |
|---|---|---|
| 沙箱 qemu `M6R✓ M7✓`（rebuild exit=124 vs factory exit=139） | 工厂侧在沙箱**缺 DRM 真硬件**早死（`driver.so` 里 `gr_init` 崩）；我方 124 是"活到超时"，**不是"更接近原厂"** | 真机 N6 |
| `prop_equiv` size 比 = 探针 | 已有 5+ 编译器习语豁免（GAP §7.4），不能证明语义等价 | 行为差分 + 真机 |
| 符号落位 92.2% | 只证明符号在 `.text`，**不证明功能正确**（§9.4 诚实声明） | 真机 |
| B 线 qemu e2e PASS | 深度只到"进程活着 + 有重绘"，不触碰真实功能 | 已废弃（用户澄清） |

---

## 四、真实差距清单（逐项根因 + 根治方案）

### G1（架构级）刻度 A = 171 工厂数据符号依赖 / 2543 处

- **根因**：产物把工厂 3.90 MB 地址镜像（`.fimg_*`）当作数据嵌入，代码里烧死工厂绝对地址。
- **分布**：`.fimg_data` 144 符号/2381 处 · `.fimg_rodata` 20/82 · `.fimg_bss` 5/78 · `.fimg_text` 2。
- **根治（§0.1 已定路线）**：把 171 个工厂数据符号搬进自有段（`.data`/`.rodata`，保留原厂初值但不钉死绝对地址），
  代码改符号引用 → 依赖归 0 → `.fimg_*` 整体可移除 → `PT_LOAD` 9 段自然收敛到 2 段。
- **真实验收**：`fidelity_source_deps.py` 两个口径都到 0；`elf_load_audit.py` PT_LOAD 几何 2/2。

### G2（真机）ALSA 初始化序列差异（已定位已修，未复验）

- **根因**：`InitSound` 第 2 实参被 Ghidra 误读为 `UpdateROM`（函数地址 0xac44），实为**立即数 44100**（0xAC44）。
  已修（GAP 16.72）：`(*sound_driver_init)(USE_HDMI_OUT, 44100, 2)`。
- **真实验收**：真机日志从 `failed to apply hwparams: -22` 变为与原厂一致的 `snd_pcm_start failed: -32` 且存活。

### G3（符号级）`.dynsym` 差异 6+1 项

| 符号 | 差异 | 根因 |
|---|---|---|
| `__strdup` | 工厂有，我方缺 | 工厂用 glibc 内部符号（`strupr.c` 里 `islower` 也同理）；我方 `mxml`/`libiconv` 用标准 `strdup` |
| `islower` | 工厂有，我方缺 | `strupr.c:23` 调 `islower`，但产物 `.dynsym` 无它（可能被内联/静态化） |
| `__gmon_start__` / `_ITM_*` / `_Jv_RegisterClasses` | 工厂有，我方缺 | GCC 弱符号（-pg / transactional memory / Java 遗留），非功能符号 |
| `strdup` | 我方多 | glibc 版本差异：老 glibc 导出 `__strdup`，新导出 `strdup` |

- **根治**：对齐 `strupr.c` 用 `islower`（真实现，非桩）；`__strdup`/`__gmon_start__`/`_ITM_*`/`_Jv_*` 属**可豁免**
  编译器/glibc 版本习语（不产生行为差异），登记进 GAP 豁免清单即可。

---

## 五、分阶段工作计划

| 阶段 | 内容 | 优先级 | 验收标准 |
|---|---|---|---|
| **P0 收口假实现** | 清理 `src/upstream/libiconv/` 遗留手写桩；给 zstub/cxx_ops 加"链接期桩"显式标记 | 立即 | 全量重编仍 213/213；假实现审计仍 0 异常 |
| **P1 架构收敛** | 刻度 A 171 符号 → 0（搬进自有段），PT_LOAD 9→2 | 最高 | `fidelity_source_deps`=0；`elf_load_audit` 2/2 |
| **P2 符号对齐** | `.dynsym` 差异处置（islower 真实现；其余豁免登记） | 中 | `.dynsym` 对拍只余「已登记豁免」 |
| **P3 真机闭环** | ALSA 序列真机复验（G2 已修） | 最高（依赖真机） | N6 通过：开机进菜单、读 UI 资源 |
| **P4 功能升级** | evdev 即插即用手柄 + SRAM 持久化（`.srm`） | 复刻收敛后 | 见 §0.2 目的 2 |

---

## 六、本轮已开始的真推进

### P0 收口假实现 —— 已完成（2026-10-02）

| 动作 | 结果 | 验收 |
|---|---|---|
| 重命名 `src/upstream/libiconv/` → `libiconv-legacy-stub/` + 加 README 警告 | ✅ | `iconv_engine.c` 自述"简化核心引擎"；`iconv.c`(629B 手写) 与真源码 md5 不同；**零脚本引用** |
| zstub.c / cxx_ops.c 标记 | ✅ 已充分（"链接期桩"/"替身"） | 无需改 |
| 清理后假实现审计复跑 | ✅ | 空壳 0 嫌疑、恒返常量 0 嫌疑、桩符号 0 异常 |

### 下一步（P1 架构收敛，最高优先级）

刻度 A 171 工厂数据符号 → 0。见 §五 P1。

### P1 段布局子路径 —— **已实验并放弃**（第 117 轮，2026-10-02）

`PT_LOAD 9→2` 的 4 次尝试**全部失败**（运行期 `SIGSEGV si_addr=0x4`）：① 自有段紧接 0x3f2000；
② ＋R→R-X 切换 ALIGN；③ `PHDRS` 显式段归属（→ `DT_FLAGS` 被覆盖）；④ 全量重编。
根因：`get_executable_path` 对 `work_path[256]` 传 **4096** 给 `readlink`，依赖「`.bss` 后已映射内存」
（工厂 `brk=0x3e2000` 紧邻 .bss 末尾）——段地址改动静默破坏此**运行期不变量**。
回退后产物 sha `07dde6d727439c09`，与第 116 轮**逐字节相同** ⇒ **净产出 0**。

**修正结论**：`PT_LOAD 9 vs 2` 是**忠实度刻度**，非「能否替代」判据；当前 9 段已**合法**（无空洞/重叠/共享页故障）。
段布局**彻底放弃**。纪律 137：段地址"自由"是伪命题。见 GAP 16.104。

**修正后的优先级**（★ 2026-10-02 二次修正：原写"P3 真机最高"**违反纪律 37/40**）：
- ★ **真机不是"下一步"**（纪律 37：「请用户上机」前必须自问**本地装置做完了吗**；
  纪律 40：不得用未证实的负面事实替代对自身进度的诚实评估 —— 那是把责任推给用户）。
- 正路 = **设备无关的本地工作**（PROJECT-MEMORY §0.19-F「待办（全部设备无关）」）：
  ① 抬高沙箱天花板（把阶梯从 M4→M5 推深）；② `UpdateROM`/`ReadUSBJoy` 缺体；
  ③ `.dynsym` 差异；④ 残余分歧（19 mui / 6 XUnzip / 3 mxml / 3 libiconv）。
- ★ 纪律 112：**不要用代理指标（DIVERGE/门禁）的改善去替代终局判据的推进**。
- ★ 纪律 55：报告"CI 绿"**必须给绿的是哪一版 sha**；CI 跑 qemu 沙箱，沙箱里工厂自崩 ⇒ **不是验收场**。

见 `PROJECT-MEMORY.md` §0.19-F / §0.29-F / §0.54 / §0.59（B 线 wav 已根治 + 段布局结论）+ GAP 16.102/16.103/16.104。

---

## 七、第 118 轮（2026-10-02）：根因收敛到「编译口径」—— 跳出「逐函数追发散」的死路

### 7.1 前一轮的弯路（已放弃，承认）

P1 曾被写成「段布局 9→2」。4 次改动全部失败并回退，产物 sha 与上一轮**逐字节相同**（净产出 0）。
⇒ 段布局是**代理几何**，不是根因，已彻底放弃。（GAP 16.104 / 纪律 137）

### 7.2 真正的根因：产物生成口径与工厂**四项全不同**

铁证 = 工厂 DWARF `DW_AT_producer`（`report/dwarf_recon.txt:19`）vs 我方 `tools/link_audit.sh`：

| 维度 | 工厂真值 | 我方当前 |
|---|---|---|
| 编译器 | **GCC 6.2.0**（LibreELEC `armv7a-libreelec-linux-gnueabi`） | **`zig cc` = clang 21** |
| glibc 头 | **2.24** | **2.7** |
| 优化档 | **`-O2`** | **`-Os`**（当年按**体积比代理指标**选定） |
| 影响机器码的开关 | `-std=gnu11 -fgnu89-inline -fmerge-all-constants -frounding-math -ftls-model=initial-exec -mtls-dialect=gnu -mtune=cortex-a8` | **全缺** |

⇒ **所有残余发散（INLINE-MOVE 访存几何 / 体量比 / libiconv 96 个边角 charset / `.dynsym` 习语）
共用一个根因**：编译口径不同。逐函数修 = 打地鼠；**根治 = 换回工厂同款口径**。

### 7.3 §0.19-F / §0.29-F 清单的**实时核销**（本轮实测，非记忆）

| 清单项 | 本机 zig 实测 | 结论 |
|---|---|---|
| §0.19-F.2 `UpdateROM` 缺体（976→112B） | **-O1=988(1.012) / -Os=940(0.963)** | ✅ **已闭合**（§0.20 UB 根修生效）⇒ 清单**陈旧** |
| §0.19-F.2 `ReadUSBJoy` | **-O1=1088(0.910) / -Os=1072(0.896)** | ✅ **已闭合** |
| `prop_equiv` 残余 WARN 4 个 | `GetZipItemA .654 / ClearBuffer .625 / sunxi_gpio_output .603 / sunxi_gpio_set_cfgpin .603` | 全为**编译器习语**（基线已定性）；`UpdateROM` 基线行**已按纪律删除** |
| §0.30-F「真嫌疑池」抽查 `ConvertCode` / `outputxy1` | 与工厂 Ghidra 反编译**逐行同构**；尺寸 0.902 / 1.054（OK 带内） | **非缺体**，是访存几何差 |

### 7.4 本轮执行的根治实验（判据先写死）

- 判据：`TOOLCHAIN-ALIGN-2026-10-02.md`（**跑之前**落盘，事后只许回填数字）
- 装置：`tools/cnb_ladder.sh` 新增 `REBUILD=5` → 云上跑 `tools/toolchain_ab.sh`
- 腿：`zig-Os`（现状）/ `zig-O2`（只换优化档）/ `gcc63-O2`（Bootlin GCC 6.3.0 + glibc 2.24 + `-O2`）
- 判决尺：`diff_exec --batch --steps 3000` 的 **DIVERGE 数**（行为尺，**不是**体积比）

**真 GCC 6.2.0 可达性已实测**：`ftp.gnu.org/gnu/gcc/gcc-6.2.0/gcc-6.2.0.tar.bz2` **HTTP 206**、
`binutils-2.27.tar.bz2` **206**、`glibc-2.24.tar.xz` **206**
⇒ 若 `gcc63-O2` 胜出，下一步自建**逐位同款** GCC 6.2.0（= §0.10 登记、**至今未执行**的项）。

### 7.5 上游现成实现（联网核实，如实登记）

| 项目 | 性质 | 对 1:1 的意义 |
|---|---|---|
| `700zx1/mini_rkgame` | SF3000/GB350 的**极简 libretro 前端重写** | **重写**，非 1:1 |
| `tzubertowski/TreeFrogUI` / `vbauer/treefrog-ui` | **前端替换**（hook 原厂 `autorun`） | 走「不碰原厂文件」路线，**绕开 1:1** |
| `goph-R/SF3000-RE` | 逆向工程资料 | 参考 |

⇒ 上游**没有** `rkgame` 的 1:1 复刻源码，本项目路线是唯一的；
`TreeFrogUI` 的 hook 做法正是本文档「目的 2」（evdev 手柄 / SRAM 存档）的功能层形态。

---

## 八、判决结果（2026-10-02）：§7.2 的「编译口径」假设**被实测证伪** —— 更正本文档自身

★ **本节是对 §7.2 的一次公开更正。** 判据在跑之前写死（`TOOLCHAIN-ALIGN-2026-10-02.md` §三），
本节的数字为**回填**，判据一字未改；命中反证条件 ⇒ **照判据执行**。

### 8.1 实测（云上 `REBUILD=5`，3 腿，nonce 校验通过）

| 腿 | PASS | **DIVERGE** | TRUNC | REFDEAD |
|---|---|---|---|---|
| `zig-Os`（＝主链口径） | **765** | **18** | 5 | 0 |
| `zig-O2` | 761 | **22** | 5 | 0 |
| `gcc63-O2`（GCC 6.3.0 + glibc 2.24 + `-O2`） | 727 | **26** | 6 | **34** |

- **M1 不成立**：26 **>** 18 ⇒ 换到最接近工厂的编译口径，发散**不降反升**。
- **M2 单调性**第一步即断（18 < 22）⇒ 变量**不是**单向贡献。
- **反证条件命中** ⇒ **「编译口径不对」不是根因**，该路径退出。

### 8.2 对 §7.2 的更正（逐条）

| §7.2 的原断言 | 实测 | 更正 |
|---|---|---|
| 「所有残余发散共用一个根因 = 编译口径不同」 | 换口径后 DIVERGE 18→26（更差） | ❌ **不成立**。编译口径**不是**共因 |
| 「`-Os` 是按体积比代理指标选定的、应改 `-O2`」 | `-O2` 使 DIVERGE 18→22 | ❌ **不成立**；`-Os` 实测**更优** |
| 「换工具链是有效的整类优化」 | `gcc63-*` 另增 `REFDEAD 34` + 体量门禁 FAIL | ❌ **不成立**；并引入新的不可判区 |

★ 仍**成立**的部分：§7.3 的清单核销（`UpdateROM`/`ReadUSBJoy` 已闭合、基线陈旧行已删）、
§7.5 的上游调研、以及 §16.106 的两处工具缺陷根治。

### 8.3 本轮**新增**的可用结论（不是零产出）

1. **不切工具链**：现状 `zig cc` + `-Os` 是三腿最优 ⇒ 主构建口径**保持不变**（无回退动作）。
2. **残留清单第一次被钉死**：当前源码 `zig-Os` 腿 **DIVERGE 18 / REFDEAD 0 / TRUNC 5**，
   18 个发散聚成 **8 簇**（见 §8.4）。这是「1:1 还剩什么」的**可执行答案**。
3. **GCC 可当 UB 探测器**：`gcc63-O2` 触发 `size_coverage_gate` FAIL
   （`GetWorkPath` 12 vs 28、`stbtt__cff_get_index` 160 vs 336）⇒ GCC **会删掉 clang 留着的代码**
   ⇒ 存在**仍未修的 UB 点**。这是**设备无关**的检出手段（`tools/ub_census.py` 的独立第二意见）。
4. **两条新线索**（待单独取证，本轮**不**下结论）：
   - 簇 A：`FilePreEmu` / `SeletEmuCore` —— 工厂侧有 `strcmp ×8` + 6 处表读（stride 0x44），
     我方只有 `strlen/strcpy` 且**提前死在 null 解引用**（`R!@0x0`）；
     ★ 但工厂 Ghidra 源码里**同样没有 strcmp** ⇒ 那 8 次来自**被内联的遍历子过程**，
     属「我方该循环未进入」的真嫌疑，需单独立案取证。
   - 簇 B：`DrawFrame` 仅**我方**读 `0x003cfa94`（= `rotation_buff`）⇒ 与 §0.103 的
     `rotation_buff` 指针修复直接相关，需核对读的是否为工厂的等价形态。

### 8.4 残余 18 个发散的分类（当前源码，`zig-Os` 腿）

| 簇 | 函数 | 差异实质 | 归类 |
|---|---|---|---|
| A | `FilePreEmu` · `SeletEmuCore` | 仅工厂侧 `strcmp ×8` + 6 表读；我方早死 | ★ **真缺陷嫌疑（最高优先）** |
| B | `DrawFrame`(×2 组) | 仅我方读 `rotation_buff` | 与 §0.103 关联 |
| C | `DisplayPage_list`(×3 组) | 仅我方写 `OutRect+16`、读 `m_ui+1216/+56` | 多访存，待定性 |
| D | `_Z17FormatZipMessageUjPcj` · `get_item_from_line` | 调用次数 / 多一次 `strlen` | 待定性 |
| E | `TestLibz0`(×3 组) | 仅「原始名不同」 | 命名，可豁免 |
| F | TRUNC 5 个 | `MP3InitDecoder` `TestRun` `TestUSBJoy` `WaitNMI` `xmp3_AllocateBuffers` | **不可判**（≠ 收敛，纪律不变量） |
