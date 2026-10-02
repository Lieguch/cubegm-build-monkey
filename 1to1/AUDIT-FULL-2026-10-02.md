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

**修正后的优先级**：**P3（真机闭环，唯一终局判据）＞ P2（`.dynsym` 符号对齐）＞ P1（架构收敛，大工程、低边际收益）**。

见 `PROJECT-MEMORY.md` §0.59（B 线 wav 装载已根治复验 + 段布局结论）+ GAP 16.102/16.103/16.104。
