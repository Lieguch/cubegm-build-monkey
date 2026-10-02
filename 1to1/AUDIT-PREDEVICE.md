# AUDIT-PREDEVICE —— 「是否已经到达必须上机」的无死角审计

- 日期：**2026-10-01（第 110 轮）**
- 审计标的：`build/rkgame.rebuilt.elf` sha256 `1f09f15b540904724100f8c6407ff59ce04d2ef5557bbab63b98b2a8df297a47`
- 对照物：`golden/factory.rkgame.bin`（原厂，只读红线）· `golden/device_rootfs_min/`（设备真实库）· `golden/sdcard_min/`（SD 内容）
- 触发：用户质询「**目前进度达到必须让我上机才能推进的地步没有？**」
- 纪律：**先写死判据，再看结果**；每条结论后面必须跟可以复算的命令。

---

## 一、结论（先给答案）

> **没有到达。上机不是当前唯一能产生新信息的动作。**
>
> 审计发现：**"设备能否跑起来"这件事被拆成三层，其中前两层本地可判、已全部机械化并通过；
> 第三层（运行期）本地也可判，但装置一直缺一块 —— 而这块现已补上并正在云开发上运行。**
>
> 更严重的是：审计查出**一个把 09-28 之后所有上机尝试全部作废的回归**（`PT_INTERP` = Windows 宿主路径），
> 意味着**此前若你上机，拿到的必然是零信息**。在它修好之前，任何"请上机"都是**把自己的活推给用户**。

---

## 二、把「设备能否跑」拆成可判层

| 层 | 问题 | 本地可判？ | 本轮结论 |
|---|---|---|---|
| **L0 加载层** | 内核 `execve` 会不会拒？ld.so 能不能解析符号/版本？ | ✅ 全可判（静态） | **全 PASS**（下表） |
| **L1 执行安全层** | 代码会不会跳进"不可执行的工厂映像区"？ | ✅ 可判（反汇编+字面池） | **PASS：0 处** |
| **L2 运行期层** | 加载成功后走到哪一步、死在哪 | ✅ **可判**（qemu-user + 设备真 sysroot） | ★ **装置此前缺失，本轮补上并已开跑** |
| **L3 硬件层** | 真 SFC/DRM/ALSA 寄存器与真 SD 时序 | ❌ 只有真机 | 真机 |

---

## 三、L0 加载层：机械判据全过（`tools/pre_device_gate.py`）

复算：`python tools/pre_device_gate.py build/rkgame.rebuilt.elf golden/factory.rkgame.bin golden/device_rootfs_min`

| 判据 | 内容 | 结果 |
|---|---|---|
| P1 | `PT_INTERP` 精确 == `/lib/ld-linux-armhf.so.3` | **PASS**（此前是宿主路径 → 已修，见 §五） |
| P1b | 该文件在**设备 rootfs** 真实存在 | PASS（`ld-linux-armhf.so.3 -> ld-2.29.so`） |
| P2 | 全文件无工具链宿主痕迹 | PASS（0 处） |
| P3 | ELF 身份字段与工厂全同（cls/data/osabi/abiver/type/machine/flags） | PASS |
| P4 | `DT_NEEDED` 7 项全部能从设备 rootfs 找到 | PASS |
| **P5** | **108 个未定义符号 ⊆ 设备库导出符号（12,070 个）** | **PASS：缺 0 个** |
| **P6** | 版本需求（GLIBC_/GLIBCXX_/CXXABI_/GCC_）⊆ 设备提供的 94 个版本 | **PASS：缺 0 个** |
| P7 | 无 `DT_RPATH`/`DT_RUNPATH` | PASS |
| P9 | `DT_INIT`/`DT_INIT_ARRAY` 非空且落在可装载段内 | PASS |
| P4b | `PT_LOAD` 几何（`elf_load_audit` A1–A6） | PASS（9 段 / 最高 vaddr 5.3 MB / 5.2 MB） |

★ **P5/P6 是本次新增的**：在此之前，**没有任何一道门禁问过"设备上这些符号与版本找不找得到"**。
它们全是"设备加载时才炸"的失败模式，而此前 15+ 道门禁一道都没覆盖。

---

## 四、L1 执行安全层：不会执行到不可执行的工厂映像区（`tools/fimg_ref_audit.py`）

我方产物把工厂机器码的地址镜像放在 `[0x9000, 0x3acffc)`，**权限是 `--R`（不可执行）**（有意为之：
我们不执行工厂代码）。**只要任何一条控制流跳进去，真机就是 SIGSEGV(NX)/SIGILL。**

复算：`python tools/fimg_ref_audit.py build/rkgame.rebuilt.elf golden/factory.rkgame.bin`

| 判据 | 结果 |
|---|---|
| A1 风险区内是否有 `STT_FUNC`（有人把它当函数用） | **0 个**（区内 742 个符号**全是 `STT_OBJECT`**） |
| A2/A3 可执行段字面池指向风险区的 134 个字，是否被用作跳转目标 | **CODE-REF 0 ／ DATA-REF 134** |
| 补充：直接分支（`b/bl/blx #imm`）落入不可执行段 | **0 处**（`pre_device_gate` P8） |

⇒ **"执行到工厂映像区"这一整类失败模式，本地已排除。**

---

## 五、★★★ 审计查出的真问题：一个把 09-28 之后所有上机作废的回归

| 项 | 内容 |
|---|---|
| 症状 | 交付产物 `PT_INTERP` = `C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3` |
| 后果 | 内核 `execve` **只校验该绝对路径是否存在**（连 libc 都不查）⇒ 立即 `ENOENT` ⇒ **进程一行都不跑** ⇒ `_diag/` 零文件 |
| 引入时点 | **2026-09-28**（`link_full.sh` 的 `LINK_DRIVER=lld` 成为默认）；`zig ld.lld` 直驱**硬忽略** `--dynamic-linker`（四种写法全部复现失败，上游同源 ziglang/zig#23813） |
| 反证 | 09-22 那批投放包（`rkgame.t1` = `65118fa2…`）的 `PT_INTERP` **是正确的** `/lib/ld-linux-armhf.so.3` ⇒ **09-22 的观测有效，09-28 之后的全无效** |
| 为何瞒过门禁 | `abi_check.py` 用 `d.find(b'/lib/ld-linux')` **全文件子串搜索**，而宿主路径**本身含这个子串** ⇒ 判 PASS |
| 已修 | 三层：链接后强制对齐（fail-closed）· 门禁改读**真实程序头**并精确比较 · 投放包**拒投闸门** |

★ 这条**否证了"上机是唯一路径"**：在它存在期间，上机是**零信息**动作。它属于**纯本地缺陷**。

---

## 六、设备侧历史事实（有效的两次观测，都在 09-22）

| 轮 | 设备给出的硬事实 | 是否已被本地消费 |
|---|---|---|
| 探针 v1 | 静态产物**能 exec**；`/sdcard/cubegm/` 与 `_diag/` **可写**（`openat rc=3`） | ✅ 已消费（排除了"写不出文件"整类） |
| 探针 v2 | **无任何 EXECVE-FAILED** ⇒ 内核与 ld.so 都放行；A 线 rebuilt `SIGBUS(7)`、diag `SIGSEGV(11)` | ✅ 已消费 ⇒ 结论"加载层无责，崩在程序自身初始化" |
| v2 附带 | 设备环境：`mmap_min_addr=32768`、kernel 4.4.194、根 fs squashfs ro、**SD 挂 `/mnt/sdcard`**（`/sdcard` 亦可写） | ✅ 已消费 |
| 第 4 轮 | **RELRO 修复被证实**（诊断版真的写出 `_diag/` 日志、帧序列正常）；**44100 修复被证实**（`snd_pcm_start -32` 与原厂逐字相同） | ✅ 两个修复都已被真机背书 |
| 第 4 轮 | 剩余阻塞：`t1` 崩在 **`SIGBUS(7) si_addr=<mmap基址>+0x2C PC=sfc_init+0x6c`** | ✅ 已本地定位为 **MMIO 访存宽度被编译器窄化**，已修 + 建 `mmio_width_audit` 门禁 |
| 第 4 轮之后 | —— | ⚠️ **零有效观测**（因为 §五 的回归把此后每一次都变成零日志） |

⇒ **当前的产物比"最后一次有效观测的产物"多了 5 项修复**（`-Os` 上游档、void 判据双源、
`rotation_buff` 形态、`mbsinit` 对齐、MMIO `volatile`），**且从未在真机上验证过**。
其中 **MMIO `volatile` 正是针对"最后一次真机观测到的崩溃点"** —— 这是"上机确有新信息"的**真实理由**。

---

## 七、L2 运行期层：装置此前缺的一块（本轮已补，正在跑）

### 7.1 缺口（这是本次审计的核心发现）
| 现有云执行器 | 覆盖 | 不覆盖 |
|---|---|---|
| `cnb_ruler.sh` | **函数级**行为尺（Unicorn 逐函数） | **不经过 ld.so / 不经过设备 glibc** |
| `cnb_ws_gates.sh` | 依赖 arm objdump 的静态门禁 | 不做动态执行 |
| `cnb_ca_exp.sh` | 编译器对齐实验 | 同上 |
| `.github/workflows/1to1-qemu-behav.yml` | qemu 行为差分（**含 `SYSROOT=/arm-root-device` 场景**） | 在 **GitHub Actions**（本机推不上去：无 PAT）；且**未断言"我方是否被成功加载"** |

⇒ **"设备真 sysroot 下的启动链"从未在当前产物上跑过。** 而这正是能同时回答
①「加载层通不通」与 ②「走到哪一步」的唯一装置。

### 7.2 本轮补的装置（`tools/cnb_devqemu.sh`，**不需要用户任何动作**）
在 CNB 云开发上：`apt 装 qemu-user-static` → 用 `golden/device_rootfs_min` 建 **`/arm-root-device`**
（含 `lib/ld-linux-armhf.so.3 -> ld-2.29.so` 软链）→ 建 `/sdcard/cubegm` → 三点启动链
（**工厂 / 我方产物 / 负对照（仅差 PT_INTERP 93 字节）**），每点记 `exit` + `strace` 末尾 + 关键字形判定。

预登记判据（先写死）：
- **V1** 工厂侧必须 **RAN**（装置的阳性对照）；工厂都不 RAN ⇒ 装置坏，本轮结论作废。
- **V2** 我方产物必须**至少能被加载**（无 `Could not open '<interp>'`）。
- **V3** 不预设"走到哪一步"的期望值（沙箱无真硬件），只要求**可比**。

### 7.3 结果（CNB 云开发实跑，两轮）

**环境**：`qemu-arm-static 10.0.13` · `-L /arm-root-device`（设备真 rootfs：glibc 2.29 + 设备自带库）·
`-cpu cortex-a7` · 二进制放在 **`/sdcard/cubegm/rkgame`**（真机同款目录，保证 `get_executable_path()` 能定位资产）·
`/sdcard/cubegm/` = `golden/sdcard_min` 全量 · 建了 `/dev/mem`（真机有、沙箱默认没有）。

| 被测 | exit | strace 行数 | 里程碑（grep 命中数） | 末尾现场 | 判定 |
|---|---|---|---|---|---|
| **原厂 factory** | 139 | **228** | `ld.so.cache`×2 ｜ `driver.so`×1 ｜ **`/dev/dri`×16** ｜ `setting.xml`×1 ｜ `rt_sigaction`×2 | `write(2,…)cannot find/open a drm device: No such file or directory` → **SIGSEGV `si_addr=NULL`** | **RAN-AND-DIED** |
| **我方产物** | 139 | **228** | **逐项与工厂完全相同**（`ld.so.cache`×2 ｜ `driver.so`×1 ｜ `/dev/dri`×16 ｜ `setting.xml`×1 ｜ `rt_sigaction`×2） | **与工厂逐字相同**：`cannot find/open a drm device` → **SIGSEGV `si_addr=NULL`** | **RAN-AND-DIED** |
| **负对照**（仅差 `PT_INTERP` 93 字节） | 255 | **1** | 无（**连 strace 都没进**） | `qemu-arm-static: Could not open 'C:/Users/…/ld-linux-armhf.so.3'` | **LOAD-FAILED** |

#### 这一组证据说明了三件事

1. **V1 阳性对照通过**：工厂在装置里 RAN（228 行）；装置可用，本轮结论不作废。
2. **V2 通过且是"强通过"**：我方产物不仅被加载，而是**与工厂走到完全相同的里程碑**
   （228 行、每一项命中计数逐项一致、末尾消息逐字相同、崩在同一个 `si_addr=NULL`）。
   崩溃原因是**沙箱没有 DRM 设备**（`/dev/dri` 开了 16 次都没成），**工厂也崩在同一处**
   ⇒ 这是**环境伪影，不是重建缺陷**。
3. **V3 装置灵敏度被证明**：负对照（与候选只差 93 字节）**连 strace 都没产生**
   ⇒ 第 109 轮那个回归若还在，这个装置**一眼就能抓住**。

#### 为什么这条比"上机"更有价值
在此之前，项目的所有行为证据都来自 **Unicorn 逐函数对拍**（不过 ld.so、不过设备 glibc、不过 `execve`）。
**这是第一次在"设备真 sysroot + 真机目录布局"下证明：我方产物的启动链与原厂逐里程碑一致。**
⇒ 下一步可以在**云上**继续加硬件桩（`CGM_LIBKMS_STUB`、driver.so 桩）把阶梯往上推，
**直到两侧在某个里程碑分叉** —— 那个分叉点才是真机要去验证的东西。
**在阶梯推到"只剩真硬件"之前，上机都不是必要动作。**

#### 现存装置限制（如实写）
- 沙箱无 `/dev/dri`、`/dev/fb0`、SFC 寄存器 ⇒ 阶梯必然在 DRM 初始化处停下（**两侧同停**，所以仍可比）。
- `driver.so` 在 `/sdcard/cubegm/driver.so` 被打开（hit1），但其内部 MMIO 无真硬件 ⇒ 需要桩。
- 尚无 `-strace` 的函数级对齐（下一步：把两侧 strace 归一化后做**逐行 diff**，而不只是计数）。

---

## 7.4 ★★ 新增最细一级判据：`tools/strace_diff.py`（**首个分叉点**）

### 为什么它是"根"而不是"又一个计数"
`behav_diff.py`（事件）/ `milestones.py`（阶段）/ `qemu_coverage.py`（比例）都是**粗粒度**：
两侧「都过 M5、都 exit=139」时，它们**回答不了"第一条不同的系统调用是哪一条"**。
而这份粒度的数据 **`qemu-user -strace` 本来就在采**，只是从来没人做逐行对齐。

### 归一化规则（只抹掉"必然不同"的，保留"应当相同"的）
- 去行首 pid；`0x…` → `0x#`（地址/指针必然不同）
- **保留**：系统调用名、**字符串实参（路径/文件名）**、十进制标量、`PROT_*`/`MAP_*` 符号常量、`= 返回值`、`errno=N` 及文字
- **显式白名单**抹噪声：`set_tid_address/getpid/gettid/...` 的**返回值本身就是 pid** ⇒ 必然不同
  （未抹时实测会产生 **1/2 的假分叉**：`set_tid_address(...) = 523` vs `= 560`）
- **不做"只取公共前缀"的截断**（该判据已被两次证伪）；分别报 **等号前缀 / 分叉段 / 等号后缀**
- 分叉段自动分级：**装载几何类**（段页数、映射大小不同 ⇒ 我方布局与原厂不同，预期会有）
  vs **行为类**（真正要修的）

### 首跑结果（设备真 sysroot，无桩，`report/devqemu/e_{factory,ours}.txt`）
```
归一化后行数： A=228   B=228
等号前缀： 131 行（占短侧 57.5%）
分叉区域共 1 段（装载几何类 1 ／ **行为类 0**）
   [replace-GEOM] A[131] mprotect(0x#,4096,PROT_READ) = 0
                  B[131] mprotect(0x#,8192,PROT_READ) = 0
等号后缀： 96 行（含两侧**逐字相同**的 SIGSEGV si_addr=NULL 与 core dumped）
结论： ALIGNED-EXCEPT-LOADER-GEOMETRY
```

### 那唯一一处装载几何差异的**精确解释**（可复算）
| | `PT_GNU_RELRO` vaddr..end | 页跨度 | ld.so `mprotect` |
|---|---|---|---|
| 原厂 | `0x3ae5c4 … 0x3af000`（filesz 2620=0xA3C） | `0x3ae000-0x3af000` = **1 页** | **4096** ✅ 与实测一致 |
| 我方 | `0x4dcb04 … 0x4de548`（filesz 6724=0x1A44） | `0x4dc000-0x4df000` = **2 页** | **8192** ✅ 与实测一致 |

⇒ 这是**我方 RELRO 内容比原厂大**（6724 B vs 2620 B）的直接后果，
而 RELRO 变大又是**布局碎片化**（§0.1 的架构矛盾）的下游效应 —— **不是可独立修掉的 bug**。
**处置：记为「保真度」项，不追**（追它就是重复"绕圈 DIVERGE"的老路）。

### 这一级判据的价值
它把"两侧 228 行都一样"提升为"**行为类分叉 = 0，仅 1 处装载几何差异，且已定量解释**"。
**这是设备之前能拿到的最细判据**，而它完全跑在云上。

---

## 7.5 ★★★ 阶梯推高：设备真 sysroot + 三桩（C4/C5，云上实跑）

装置：`tools/cnb_ladder.sh`（复用 `ci_qemu_behav.sh`，只**新增** strace 对齐这一级）。
环境：`SYSROOT=/arm-root-device`（glibc 2.29 + 设备自带库）+ 三桩（libkms/libdrm/libasound）+ guest shim + `/sdcard/cubegm` 真机布局。

| 项 | 无桩（§7.3） | **有桩 C4** | **有桩 C5（含 J 口径注入）** |
|---|---|---|---|
| 归一化行数 | 228 / 228 | **360 / 360** | **360 / 360** |
| 等号前缀 | 131 | **271（75.3%）** | **271** |
| 行为类分叉 | 0 | **0** | **0** |
| 装载几何类分叉 | 1 | **1** | **1** |
| 等号后缀 | 96 | **88** | **88** |
| 两侧里程碑差集 | 完全同步 | **空** | **空** |
| 终止码 | 139 / 139 | **139 / 139** | **139 / 139** |

里程碑：`M0✓ M1✓ M2✗ M3✓ M4✓ M5✗ M6✗(未走到) M6R✗(未走到) M7✗`，**两侧逐项相同**。
覆盖率（rebuild，C4）：已执行 **6/223 = 2.69%**（沙箱在 M4 后即同崩，故只到函数入口层）。

### 读法（三条硬结论）
1. **三桩把阶梯推高了**（228 → 360 行、前缀 131 → 271）⇒ 装置有效，且**新增的部分两侧仍然一致**。
2. **行为类分叉 = 0**：在设备真 sysroot 下，我方产物的**运行期系统调用序列与原厂一致**，
   连 `SIGSEGV si_addr=NULL` 与 `core dumped` 都是**逐字相同**（沙箱无真硬件，两侧同崩）。
3. **唯一差异仍只有那一处 RELRO 页跨度**，且已定量解释（§7.4），属保真度项、不追。

### 本轮暴露的装置不足（下一轮入口，已登记）
- **guest shim 是否建成未被取证**：`ci_qemu_behav.sh` 写 `$OUT/shim_build.txt`，本轮**漏取**
  ⇒ 不能排除"降级为不带 shim 跑"。下一轮必须一并取回并加 fail-closed。
- 两侧同停在 M4→M5 之间（NULL 崩）⇒ 要把阶梯再推高，需要**更多"返回值做成成功"的桩**。
- `M6/M6R`（zip 资源包）在两侧都是"未走到" ⇒ 目前**阶梯还区分不了资源包这一段**。

## 7.6 给「以后要不要问上机」的机械规矩（纪律 117 补充）

> 现在有三道本地装置（`pre_device_gate` L0 / `fimg_ref_audit` L1 / `cnb_ladder` L2）。
> **L2 能给到的最细粒度是"逐系统调用"**。因此：
> **只有当 L2 的结论是「行为类分叉 = 0 且里程碑已推到"只剩真硬件"」时，上机才是必要的。**
> 现在 L2 已跑到「行为类分叉 = 0」，但阶梯**卡在 M4→M5 且两侧同卡** ⇒ 还能继续往云上加桩推高，
> **所以此刻仍不是"必须上机"。**

---

## 八、仍未关闭的缺口（不粉饰）

| # | 缺口 | 本地可判？ | 处置 |
|---|---|---|---|
| G1 | **L3 真机**：SFC/DRM/ALSA 真寄存器与真 SD | ❌ | 等 L2 通过后**才**请你上机 |
| G2 | **L2 运行期**（本轮补的装置） | ✅ | 正在跑（§7） |
| G3 | DIVERGE 17（观测受限 12 / codegen 4 / Thumb 1） | ✅ 但**可改源码项 = 0** | 冻结，不再投入 |
| G4 | 工厂 308 个 Thumb 函数（我方 0）：`zig cc` 静默忽略 `-mthumb` | ❌ 需真 GCC(Linux) | ISA 棘轮守着；属"体积不像"而非"跑不起来" |
| G5 | **L4 目的 2**：evdev 热插拔 / `.srm` 存档持久化 | ✅ 部分可判 | **0/2，未动工** |
| G6 | P1-b 沙箱全局播种（12 个"观测受限"发散） | ✅ | 未做；**只影响 DIVERGE，不影响上机** |
| G7 | P1-c `UB-PATH` 类差异 | ✅ | 需一次**显式决策**（接受 / 另找通道） |

---

## 九、给"以后要不要问上机"立一条机械规矩

> **纪律 117（新增）**：**"请上机"必须先过 `pre_device_gate` + `fimg_ref_audit` + `cnb_devqemu`（L2）。**
> 三者任一未过 ⇒ **不许请用户上机**，因为那一趟注定是零信息。
> 判据：**上机必须能回答一个"本地装置回答不了"的问题**，且该问题要**先写下来**。


---

## 7.7 ★★★★★ 第 114 轮：段页共享（GAP 16.100）—— 比 strace 分叉更靠前的一类死因

### 7.7.1 崩溃现场是**程序自己打印出来的**（不是推断）
`probe_stderr_*_strace.txt` 里那些逐字符 `write(2,…,1)` 就是 **guest shim 的 SIGSEGV 处理器**。
把 `write(2,…)` 的载荷按线程重接即可还原原文（本机 20 行 Python）：

| | rebuild（我方） | factory（原厂） |
|---|---|---|
| `si_addr` | `0x005401d8` | `0x00000004` |
| **PC** | **`0x005401d8`（= si_addr）** | `0x0002b3c8` |
| LR | `0x004e4e20` | `0x00017ec8` |
| `[pc]` | `0xe92d4830` = `push {r4,r5,fp,lr}` | `0xe1d300b4` |
| `[pc-4]` | `0xe12fff1e` = **`bx lr`** | `0x0a000264` |

**PC == si_addr ⇒ 取指故障**（不是"写只读页"）；`[pc-4]` 是 `bx lr` ⇒ 某函数返回到 0x5401d8 后该页不可执行。

### 7.7.2 根因：一条页几何（可机械判定）
```
[7] PT_LOAD va=0x004e1000 fl=5(RX) filesz=0x5ffc8  ⇒ 末端 0x540fc8 **未页对齐**
[8] PT_LOAD va=0x00540fc8 fl=4(R)  filesz=0x1840   ⇒ 紧随其后（= .ARM.exidx）
页 0x540000 被两段共享；加载器按段逐页 mmap，**表序最后的 R 段覆盖 ⇒ 该页丢 X**
```
该页内 **24 个 FUNC**（全 XUnzip/Zip 一族）：`TUnzip::Open/Get/Find/Unzip/Close`、`unztell`、
`unzeof`、`unzGetLocalExtrafield`、`unzGetGlobalComment`、`FormatZipMessageU`、`DosDateTimeToFileTime`、`timet2filetime`。
**原厂共享页 0 个**（仅 2 个 PT_LOAD：0x00008000 / 0x003ae000，**都页对齐**、末端也页对齐）。
⇒ 直接解释 M6 里程碑分叉：工厂 `openat("//ui_cn.zip")` ×3，我方 **0 次**。

### 7.7.3 联网核实（与实测逐字吻合，非推断）
| 来源 | 结论 |
|---|---|
| LLVM **D21801**（lld + 链接脚本，场景与本案一致） | "…map size of 0x1000 (page rounded) and different protection attributes. Finally one will have region … mapped with RW attributes. Jumping to entry point … will immediately cause protection fault (SIGSEGV). **Not a single user instruction will be executed**." |
| **MaskRay**（lld 维护者） | "A page serves as the granularity at which memory exhibits different permissions, and within a page, we cannot have varying permissions … Subsequent PT_LOAD segments then overwrite the previous memory regions." |
| 内核 **`b212921b13bd`**（Linus, 5.4） | "elf: dont use MAP_FIXED_NOREPLACE for elf executable mappings" —— 因旧二进制存在重叠段，内核回退 **`MAP_FIXED`（覆盖而非拒绝）** |

⇒ 真机后果与 qemu 实测**同向**（该页被后段权限覆盖）；4.17–5.4 之间的内核可能直接 `EEXIST` 让 `execve` 失败。
**两条路都是致命的**，所以这条不是"沙箱伪影"。

### 7.7.4 根修与门禁（规则只写一份，其余只转发）
- **根修**：`linker/factory.ld` 的 `.ARM.exidx` 加 `ALIGN(0x1000)`。**同时改生成器 `tools/gen_data_module.py`**
  （否则下一次 regen 静默回退 —— 这正是 `check_regen_contract.py` 存在的理由，已加不变量 ⑥）。
- **新门禁**：`tools/seg_page_audit.py`（**唯一实现**）。
  不变量：*任一被 >1 个 PT_LOAD 覆盖的页，其**最终权限**（表序最后一段）必须 ⊇ 覆盖它的所有段权限并集*。
  钉进 `link_full.sh`（fail-closed `exit 20`）；`pre_device_gate` 的 **P10 只转发调用它**；`cnb_gates.sh` 已收录。
- **判据必须写"后果"而不是"是否重叠"**：本产物有 **3 个共享页**，其中 **2 个是良性的**
  （RX 覆盖 R、RW 覆盖 R），只有 1 个致命（R 覆盖 RX）。"重叠即报"会产生假阳性。
- **本机 30 秒复现实验**：`zig ld.lld` 认 `ALIGN(0x1000)`（`.ARM.exidx` 0x1024 → 0x2000）；
  不带 ALIGN 的形态**逐字复现**出同样的共享页 ⇒ 修法与判据自洽。

### 7.7.5 这一轮同时暴露并修掉的**执行器/仪器缺陷**（4 个）
| # | 缺陷 | 症状 | 根修 |
|---|---|---|---|
| 1 | `REBUILD=2` 上传清单漏 `src/upstream/xunzip/XUnzip.o` | 云上 `link_full.sh` fail-closed 报 `XUnzip 对象不存在` | `UP` 补该文件 |
| 2 | 改了 `linker/factory.ld` 却**没上传 `linker/`** | 云上链接 **rc=0** 但布局是旧的 ⇒ 新门禁 SEGPAGE-FAIL | `UP` 固定含 `linker src/data` |
| 3 | 云上产物**从不取回** | 本地一直是旧版，静态分析对着过期产物做结论 | 自动取回并替换；旧版存 `build/_exp/rkgame.rebuilt.pre-cloudfetch.elf` |
| 4 | `REMOTE-DONE` 只写 stderr，而该通道实测不可靠 | 每轮都报"无有效结论" | 同时写 `/tmp/ladder.log`，本地**任一处见到即算完成**并打印通道名 |

再加两条"防自己"的：
- **陈旧产物冒充新观测**：`SCEN=4` ⇒ C5 没跑，而目录里还有上一轮的 c5 strace ⇒ 解码出"仍崩在 0x5401d8"的**错误结论**。
  现：取回前先清本地产物目录；阶梯在每进场景前打印**被测产物 sha**。
- **反引号第三次咬人**：新注释里的反引号（本地双引号字面量）⇒ 本地命令替换 ⇒ `line 110: 场景: command not found`，整轮静默死掉；
  而"检查反引号"的临时 grep **自己锚点取错**（先匹配注释里的 `REMOTE-DONE`）⇒ 报 0 的**假绿**。
  根修 = `tools/ssh_literal_guard.py`（成对锚点、锚点缺失报 11、打印判据覆盖行数、反例自证），已进 `cnb_gates.sh`。
