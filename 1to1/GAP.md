# rkgame 1:1 重构 —— 「直接替代」差距分析

**日期**：2026-09-17　**基线 commit**：`4f1dc161a641`（场景 A 全绿）+ `d82f065dd818`（场景 B 接入）
**回答的问题**：距离「把 `/sdcard/cubegm/rkgame` 直接换成重建产物、设备正常跑起来」还差什么。

---

## 零、一句话结论

| 层面 | 状态 | 判定依据 |
|---|---|---|
| **结构化替代**（能被内核加载、符号/布局/ABI 自洽、与设备原厂 `rkgame` 同形） | ✅ **已达成** | 静态门禁全绿 + 行为门禁 PASS |
| **功能化替代**（设备上菜单/字库/音频/输入/游戏/core 都能跑） | ❌ **未达成** | 观测窗口天花板 = 专有函数 **21.5%**、字节 **25.1%**；且窗口末尾**两侧都崩溃** |

> ★ 最关键的一条认知：**当前 `1to1-qemu-behav` 的 `PASS` 只证明「到崩溃点为止等价」，不证明「能跑起来」。**
> 两侧 `exit_code` 都是 **139（SIGSEGV）**，崩点同构（`mui_setting` 里 NULL+4 解引用）。
> 也就是说：**替换上去会和原厂二进制表现得一模一样 —— 包括一样打不开 UI 资源包、一样崩在第一屏。**

---

## 一、已达成（可复核的证据）

| 项 | 结果 | 复核命令 |
|---|---|---|
| 编译双轨（宽松/严格） | **213/213**，假绿 0，INFRA 0 | `sh tools/recon_local.sh report/local_recon_build.txt` |
| 符号审计 | 重复定义 **0** / MISSING **0** / upstream 误入 **0** | `sh tools/link_audit.sh` |
| ABI | **PASS**（`e_flags=0x5000400`、interp=`/lib/ld-linux-armhf.so.3`、GLIBC 上限 **2.7**=工厂） | `python tools/abi_check.py build/rkgame.rebuilt.elf` |
| 全局布局 | 全局符号命中 **193/194 = 99.5%** | `python tools/verify_layout.py …` |
| 动态段 | **PASS**（DT_INIT 真实、ABS0=0） | `python tools/dyn_audit.py …` |
| 行为差分（场景 A） | **PASS**，可复现前缀 **38/38 行**，B1–B8b 全绿 | `tools/behav_diff.py` 输出见 `report/qemu/behav_diff.txt` |
| 新工具链门禁 | 数组转型 / 变参函数 / `.rodata` 字符串当整数 / 上游符号指纹 全部接入 | `tools/scan_*.py` |
| 覆盖率度量（本轮新增） | `tools/qemu_coverage.py`（把 `-d exec` 原始轨迹变成进度数字） | 见下 |

---

## 二、本轮首次量化：**观测窗口有多深**（这是"进度"的硬数字）

`tools/qemu_coverage.py` 首跑（CI `4f1dc161a641`，原始 `-d exec` 轨迹 15.1 万 / 20.6 万行）：

| 维度 | 重建侧 | 工厂侧 |
|---|---|---|
| 覆盖函数（本 ELF 全部函数） | **122 / 1671 = 7.30%** | 89 / 804 = 11.07% |
| 覆盖字节（`.text`） | 50592 / 692872 = 7.30% | 44956 / 317376 = 14.16% |
| **覆盖专有函数（223 个重构目标）** | **48 / 223 = 21.52%** | **49 / 223 = 21.97%** |
| **覆盖专有字节（122,922 B）** | **30,804 B = 25.06%** | 30,836 B = 25.09% |

**窗口内实际执行到的专有函数**（两侧一致，48/49 个）：
`main` → `GetConfig`/`dispmeninfo`/`InitDisplay`/`InitSound`/`InitJoystick`/`InitRFJoystick` →
`sfc_init`/`spi_driver_init`/`sfc_request`/`sflash_read_security_data`/`UpdateROM`/`ShareMemCreat`/`xintiao`/`XintiaoThread` →
`main_Menu` → `mui_LoadSetting`/`mui_LoadConfig`/`mui_InitFont`/`mui_DisplayThumbnailThread`/`mui_SoundplayThread` →
`SoundPlay`/`PlaySound`/`AudioProcess`/`LoadMenuLog` → `mui_setting`（**崩**）。

**覆盖率一致性检查（顺手抓到的分歧）**：`ClearBuffer`（misc，32 B）**工厂执行了、重建没执行**。
追因：工厂的 `ClearBuffer` 是被 helix MP3 的 `xmp3_AllocateBuffers` 调用的（`0x2bdf1c`，清解码缓冲），
而我们在 `src/upstream/mp3/real/buffers.c` 里另有一份 `static ClearBuffer`（被内联）⇒ 专有的那份成了**死代码**。
**行为等价（都清零），但结构不等价** ⇒ 属于「看起来绿、实际不保真」的一类，已在下方 G3 登记。

---

## 三、六个差距（按"挡住正常运行"的程度排序）

### G1 ★★★★★ 观测窗口有硬天花板（≈25%）——第一屏就崩，菜单层永远跑不到

**现象（两侧完全一致）**：

```
O|root_path:/sdcard
O|open /sdcard/cubegm//ui_cn.zip fail        ← 出现两次
…然后 mui_setting 里 NULL+4 解引用 ⇒ SIGSEGV（exit 139）
```

**机制（字节级证据链）**：

1. `mui_LoadUIResource(&DAT_003af294,"setting.raw")` → `OpenZipU` → `TUnzip::Open` → `unzOpenInternal`
   → `unzlocal_SearchCentralDir`；
2. 工厂的 `unzlocal_SearchCentralDir`（0x10eb0）**逐字节比对的不是 `PK\x05\x06` 字面量，而是全局 `key2`**
   （`@0x3E190C`，`.bss` 28 B，symtab 有名；全 812 个反编译函数里只有 3 个 zip 函数读它）；
3. **两份二进制全文件都搜不到 `PK\x05\x06`/`PK\x03\x04`/`PK\x01\x02` 字节串** ⇒ 签名只能来自运行期内存；
4. ~~而 **整个 rkgame + driver.so 都没有 key2 的写入者**~~
   **★ 本节已被本日实测推翻，见下方「补充实测（二轮）」** —— 当时的静态取证漏了写入者：
   - rkgame symtab：`key2` 是**局部符号**（不进 `.dynsym`，113 项里只有 `pthread_key_*`）⇒ 外部模块无法写它 ✅（这条仍成立）；
   - `driver.so` 内部**没有** `0x3E190C` 常量、没有 PK 字节 ⇒ 排除"驱动填的" ✅（这条仍成立）；
   - ~~Ghidra 全量反编译：只有 3 个读者、0 个写者~~ ❌ **错**：运行期探针证明**有写入者**
     （它把 key2 覆盖成 `00 00 00 00 00 7d 1e 47`，两侧二进制**完全相同**）。
     静态漏判的原因待查（很可能写入走的是**GOT 相对指针**或 `memcpy` 目标被渲染成别的符号，
     而不是直接写 `key2`/`DAT_003e190c`）。
5. ⇒ 默认环境下 `key2` 全 0 ⇒ 搜索的目标是「**4 个 0x00**」而不是 EoCD 签名 ⇒ 中央目录找不到
   ⇒ `open … fail` ⇒ `mui_setting` 拿到 NULL ⇒ 崩。

**后果**：`mui` 模块（**42 函数 / 70,396 B = 重构量的 57%**）在整个 P5 里**从未被执行过一次**。
这就是覆盖率天花板 25% 的全部原因。

**已采取的行动（本轮）**：新增**场景 B** —— 由 shim 把厂商签名表写进 `key2`（`CGM_KEY2_SEED=1`，
两侧注入完全相同 ⇒ 差分仍然公平），让"资源包可打开"这条路径在两**侧**都变得可观测。
AI 侧代码已接入 CI（`1to1-qemu-behav` 的第 2 个场景步骤），首跑数据待出。

**待判定（真机对照才能定）**：工厂二进制在**真机**上是否也打不开 `ui_cn.zip`？
- 若「也打不开」⇒ 用户设备上跑的 `rkgame` 与 `golden/factory.rkgame.bin` **不是同一版本**（或 SD 资源包版本不匹配）
  ⇒ 那么当前 P5 的"参考端"取错了，必须换成设备上真实在跑的那份；
- 若「打得开」⇒ 说明**存在我们尚未发现的 `key2` 初始化路径**（可能只在真机环境里生效，例如某个仅在真机才加载的 .so）
  ⇒ 需要真机侧用探针把 `key2` 的写入者抓出来。

---

## 二·补、补充实测（2026-09-17 二轮，CI `a5743b67d3c7`）—— 两条**判决性**结论

### 补充 1：`key2` 探针 ⇒ **上一轮「必须比对 key2」的归因被推翻**

| 步骤 | 观测 |
|---|---|
| shim 注入（两侧同一值） | `[shim] key2 seeded @0x3E190C = PK…` + **回读 = `50 4b 05 06 50 4b 06 06`** ✓ 写入成功 |
| `-E CGM_KEY2_SEED=1` 是否到 guest | wrapper 里确实有该 `-E`，且 shim 的 evidence 行被打印 ✓ |
| **崩溃现场再读 key2** | **`00 00 00 00 00 7d 1e 47`（两侧二进制完全相同）** |
| 行为是否变化 | **与场景 A 逐字相同**（仍 `open …/ui_cn.zip fail` ×2；覆盖率 48/49 不变）✗ |

⇒ ① **`key2` 有写入者**（我们的注入被它覆盖；覆盖值两侧一致 ⇒ 是确定性代码，不是随机栈残留）；
　 ② 它写进去的**不是 ZIP 签名** ⇒ **`key2` 不是签名表**（很可能与邻居 `ArchivePath`/`GamePath`/`mdtemp1`
　　 一样是个**临时缓冲**）；
　 ③ 因此 `SearchCentralDir` 的比对**另有其源** —— 上一轮把"行为翻转"归因给比对源是错的，
　　 翻转实际来自同一提交里另 3 处改动（`uMaxBack` / `uReadSize` / 短读即 `return 0`）。

### 补充 2：场景 C（`libkms.so.1` 空桩）⇒ **硬件接口层首次被点亮**（重大环境解锁）

```
两侧 stdout 一致：open driver.so sucess
                 video_driver_setting 0 1 1
                 open drm!
两侧 stderr 一致：cannot find/open a drm device: Function not implemented
                 qemu: uncaught target signal 11 → exit 139
场景 C 差分：参考侧 18 行 / 控制侧 18 行；可复现前缀 18/18；门禁 PASS（0 项失败）
```

- ✅ `driver.so` **加载成功**（不再有 `libkms.so.1: cannot open shared object file`）
  ⇒ `InitDisplay`/`InitSound`/`InitJoystick` 里的 `dlsym` 驱动调用**首次真的被执行**，
  且**两侧表现一致**（`video_driver_setting 0 1 1`、`open drm!` 逐字相同）⇒ 这一层的 1:1 保真度**初步可信**。
- ⚠ 但窗口**变浅**（覆盖率 48 → 6~7 个专有函数）：程序现在更早终止 ——
  因为 shim 把 `/dev/dri/*` 重定向到 `/dev/zero`，`ioctl` 返回 `ENOSYS` ⇒
  `cannot find/open a drm device` ⇒ 随后 SIGSEGV。
- ⇒ **下一个环境缺口明确**：需要一个**有状态的假 DRM 设备**（做法与已验证的 SFC 仿真相仿：
  拦 `ioctl`/`mmap` 并应答 `DRM_IOCTL_MODE_*`、dumb buffer），否则显示层永远走不出 `open drm!`。

### G2 ★★★★ 硬件接口层 **0% 动态验证**（driver.so 在沙箱里根本没加载成功）

| 证据 | 内容 |
|---|---|
| 两侧 stdout 第 11 行 | `open driver.so fail, libkms.so.1: cannot open shared object file` |
| `driver.so` 的 `DT_NEEDED` | `libdrm.so.2` / **`libkms.so.1`** / `libasound.so.2` / `libpthread` / `libc` |
| CI 的 `/arm-root` | 有 `libdrm.so.2`（gdb 日志已证实被加载）、有 `libasound.so.2`，**唯独缺 `libkms.so.1`** |
| 关键发现 | `driver.so` 的**未定义符号里没有任何 `kms_*`**，只用 libc + `drmMode*`/`drmIoctl` + `snd_*` ⇒ **一个空桩 `libkms.so.1` 就能让加载器满足** |

⇒ 后果：`InitDisplay`/`InitSound`/`InitJoystick` 里 **所有 `dlsym` 出来的驱动函数调用都没跑过**
（`video_driver_setting`/`video_driver_disp_frame`/`video_driver_setmode`/`video_driver_get_size`/
`sound_driver_init`/`sound_driver_playframe`）。在真机上这些是**必经之路**。

**低成本解法（下一步）**：在沙箱 sysroot 里放一个只含 `SONAME=libkms.so.1` 的空共享库（两侧同一份 ⇒ 差分公平），
`driver.so` 即可加载，硬件接口层立刻进入观测窗口。

### G3 ★★★ 上游库仍有 6 处已知未对齐（一旦 zip 打开就立即进主路径）

| 符号 | 工厂 | 重建 | 性质 |
|---|---|---|---|
| `TUnzip::Unzip` | **28 B**（+`.part.7` 488 B） | 1600 B | 工厂=薄封装；**从未执行过** |
| `TUnzip::Get` | 152 B（+`.part.5` 888 B） | 1204 B | 同上 |
| `TUnzip::Close` | 68 B | 168 B | 同上 |
| `unzOpenCurrentFile` | `(unz_s*)` **单参数** 316 B | `(unz_s*,const char*)` **双参数** | 工厂删了 zip 加密/密码 |
| `unzLocateFile` | 240 B | 528 B | 待对齐 |
| `unzGetGlobalComment` | 148 B | 308 B | 待对齐 |
| `ClearBuffer` | 被 helix 调用（全局） | 专有份是死代码 | 结构不等价（行为等价） |
| `mxmlSaveFile`/`mxmlSaveString` | 108 / 164 B | 3704 / 3624 B | **已判定为内联差异，非版本问题**，勿据此改上游 |

这些都在 `tools/upstream_fingerprint_baseline.txt` 里**显式登记**（修好一项删一条）。

### G4 ★★★★ 真机验收（P6）完全未开始，且它现在**卡着一个必须回答的问题**

- 缺 SD 部署 + 设备自写日志（`menu.log`）+ **双跑对照**（工厂二进制 vs 克隆、同 SD 同路径同参数）；
- G1 的两个分支（版本不匹配 / 未发现的 key2 写入者）**只能靠真机对照判定**；
- 硬件层（真实 DRM/ALSA/evdev）也只有真机能验。

### G5 ★★ 产物形态差异（不影响加载，但属于"与原厂不同"）

| 项 | 工厂 | 重建 |
|---|---|---|
| 体积 | 3,921,108 B | **17,348,764 B（未 strip）** |
| `DT_NEEDED` | `libz/libdl/libm/libstdc++/libpthread/libgcc_s/libc` | `libz/libm/libc/libpthread/libdl`（**缺 libstdc++/libgcc_s**，zig 用 libc++ 静态链） |

⇒ 需在真机确认：(a) 是否需要 strip / 是否影响加载时间与内存；(b) libc++ 替代 libstdc++ 在异常/类型行为上无差异
（当前代码里 C++ 只用于 XUnzip 且 `-fno-exceptions`）。

### G6 ★★ 场景单一

只有一份 `setting.xml`、一份 SD 布局、一条"走到第一屏就崩"的路径。
设备上的真实使用还有：进入设置各页、搜索、收藏、存/读档、启动游戏 → `dlopen` core（`Load_Proc2`/`run_game`/
`SeletEmuCore` 等 **26 个 core 函数 / 15,100 B** 全未覆盖）、退出等。

---

## 四、推进顺序（按「收益 / 成本」排序，可直接执行）

| # | 动作 | 收益 | 状态/成本 |
|---|---|---|---|
| 1 | **假 DRM 设备仿真**（拦 `ioctl`/`mmap`，应答 `DRM_IOCTL_MODE_*` + dumb buffer） | 场景 C 现在停在 `open drm!`；补上它才能让**显示层**继续往下走（否则窗口比场景 A 还浅） | 待做；做法可复用已验证的 SFC 有状态仿真 |
| 2 | **重新定位 `SearchCentralDir` 的比对源**（`key2` 已被实证排除；候选：GOT 相对指针的真实目标、`mdtemp1`、`unzOpenInternal` 里的 EoCD 校验） | 解掉 G1 的 25% 天花板，让 `mui` 57% 重构量进入观测 | 待做；场景 B 的探针设施可直接复用 |
| 3 | ✅ 场景 B / C 仪器 + 覆盖率度量（本轮已接入，A/B/C 三场景同轮跑） | 进度可量化、环境缺口可定位 | 已完成（CI `4f1dc161a641` / `a5743b67d3c7`） |
| 4 | ✅ `libkms.so.1` 空桩 | `driver.so` 加载成功 ⇒ 硬件接口层首次可观测 | 已完成（场景 C 两侧一致） |
| 5 | ✅ 覆盖率棘轮（`tools/coverage_baseline.txt`，按 **场景/label** 分键） | 覆盖率只升不降，回归可检测 | 已完成（A: 48/49、B: 48/49、C: 6/7） |
| 6 | 对齐 `TUnzip::{Unzip,Get,Close}` + `unzOpenCurrentFile` 单参 | 清除"zip 打开后立刻踩雷"的隐患 | 待做（按反编译逐函数） |
| 7 | **真机对照实验**（工厂 vs 克隆，同 SD） | 判定 G1 的两个分支；拿到硬件层真值 | 需要设备一次 |
| 8 | 场景扩展：进入游戏 → `dlopen` core → 退出 | 覆盖 core 26 函数 / 15 KB + libretro 交互 | 多轮 |

---

## 五、建议的「可以替代」验收标准（建议写进门禁）

1. **覆盖率**：专有函数覆盖率 ≥ 90%（当前 21.5%），且含"进入游戏 → core 加载 → 退出"场景；
2. **行为**：场景 A（工厂默认态）+ 场景 B（资源包可打开）+ ≥1 个游戏启动场景，**全部升级为硬门禁并 PASS**；
3. **真机**：同 SD、同路径下 `stdout`/`menu.log`/文件变更（`saves/`、`states/`、`favorites.lst`…）逐项一致，
   且**不发生崩溃**（当前两侧 exit=139）；
4. **产物**：strip 后体积与 `DT_NEEDED` 集与原厂一致，或显式记录差异理由；
5. **上游**：`tools/upstream_fingerprint_baseline.txt` 为空（KNOWN 归零）。

---

## 六、复现方式

```sh
# 覆盖率（本轮新增；必须在 -d exec 原始日志被删除前运行）
python3 tools/qemu_coverage.py --exec-log report/qemu/exec_rebuild.log \
        --elf build/rkgame.rebuilt.elf --ledger ledger/functions.csv \
        --label rebuild --out report/qemu/coverage_rebuild.txt

# 场景 A（硬门禁）
SYSROOT=/arm-root CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=20 \
  sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu

# 场景 B（key2 注入 ⇒ 资源包可打开；待升级为硬门禁）
SYSROOT=/arm-root CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=25 CGM_KEY2_SEED=1 \
  sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu_b
```
