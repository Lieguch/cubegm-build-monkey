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

### G1 ★★★★★ 观测窗口硬天花板：**根因已定位 = `key2` 是 BSS 变量、初值恒 0**（2026-09-17 三次修正，证据链完整）

**事实链（全部可独立复核）**

| # | 证据（命令/位置） | 结论 |
|---|---|---|
| 1 | strace：`openat(AT_FDCWD,"/sdcard/cubegm//ui_cn.zip",O_RDWR) = 3`（两侧同值，出现 3 次） | **文件系统层打开是成功的** ⇒ 游戏打印的 `open … fail` 是**上层 `TUnzip::Open` 返回 0**，不是 fopen 失败 |
| 2 | zip 结构自检：EOCD@4951259、条目数 6、`cd_size=543`、`cd_off=4950716`，且 `4950716+543 = 4951259` ✓ | **`ui_cn.zip` 本身完全合法**，任何标准解析器都能打开 ⇒ 不是文件损坏、不是路径错 |
| 3 | 反编译 `unzlocal_SearchCentralDir`(0x10eb0) 第 66–69 行：倒搜时比对 `key2[0..3]` **或** `key2[4..7]`；机器码 `10fa4: ldrsb r0,[r3,#4]`、`10fb0: ldrsb r0,[r3]`，`r3` ← GOT 槽 `0x3B1E10`，槽内静态值 = `0x3E190C` | 厂商把上游两个字面量搬进了全局：**`PK\x05\x06`(EoCD)** 与 **`PK\x07\x08`(spanned)** ⇒ 比对源就是 `key2` |
| 4 | 程序头：第二个 `PT_LOAD va=0x3AE5C4 filesz=0x3BB0 memsz=0x3350F` ⇒ 文件背衬止于 `0x3B2174`；`key2@0x3E190C` 在其后（`memsz` 延伸至 `0x3E1AD3`） | **`key2` 在 BSS ⇒ 初值恒为 0**，程序自己不给它赋值 |
| 5 | Ghidra 812 函数全量：`key2` **只被读、从未被写**（4 处比较 + 1 处当 XOR 密钥 `key2[0x18]`）；`driver.so` 里**既无** `0x3E190C` 常量**也无** `PK` 字节 | 排除「驱动填的」「某段未反编译代码填的」；也排除「copy relocation」 |
| 6 | 邻居符号：`mainkey`(128B)、`m_crctable`(128B)、`ArchivePath`/`GamePath`/`key2`/`mdtemp1`(各 28B) | `key2` 属于**密钥/缓冲区簇**，不是普通常量表 |

**⇒ 根因**：`key2[0..7]` 全 0 ⇒ `unzlocal_SearchCentralDir` 倒搜的是「**4 个 `0x00`**」而**不是** EoCD 签名 ⇒ 在错误位置命中 ⇒ 算出垃圾偏移 ⇒ `TUnzip::Open` 返回 0 ⇒ 打印 `open … fail` ⇒ 随后 `mui_setting` 拿到 NULL 再 `+4` ⇒ SIGSEGV。
工厂与重建**必然同时失败**（同一份输入 + 同一段逻辑）—— 这正是「门禁全绿、窗口却只有 25%」的完整机制。

**本轮两次自我修正（都写进了技能铁律）**

1. 「`key2` 不是签名表」**是错的** ⇒ 反汇编逐字节核对证明**比对源就是 `key2`**（第 3 行证据）。
2. 场景 B「注入后毫无变化 ⇒ 假设被推翻」**是错的** ⇒ 当时注入的是 `PK\x05\x06 **PK\x06\x06**`，而正确的第二签名是 **`PK\x07\x08`** ⇒ **注入值本身不可能是签名**，那是**假阴性**，不能用于推翻假设。（已修正 `CGM_KEY2_SEED` 的字节。）

**已采取的行动（本轮，单变量两档）**

| 场景 | 开关 | 语义 | 能区分什么 |
|---|---|---|---|
| B | `CGM_KEY2_SEED=1` | constructor 时写入修正后的 8 字节 | 若行为不变 ⇒ **存在写入者**（在我们的注入之后覆写）；若变 ⇒ 无写入者，窗口直接开 |
| E | `CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1` | 在 `open/openat` 命中 **`.zip`** 的瞬间**重新断言** key2（把写入时刻推到 last-moment） | E 有效而 B 无效 ⇒ 写入者被夹在 constructor 与 zip-open 之间；B/E 都无效 ⇒ 写入发生在 zip-open 之后（下轮再往后推）；任一有效 ⇒ **窗口打开，`mui_*`（42 函数 / 70396 B = 重构量 57%）进入观测** |

★ 还有一条**更硬的判据**同时被记录进 CI 输出：`grep -c "ui_cn.zip fail"` 在 A/B/E 三场景的对比（0 = 窗口打开）。

## 二·补、补充实测（2026-09-17 二轮，CI `a5743b67d3c7`）—— 两条**判决性**结论

### 补充 1（★ 已二次修正）：`key2` 探针 —— 实验被「写入者」打断，归因**尚未**被推翻

| 步骤 | 观测 |
|---|---|
| shim 注入（两侧同一值） | `[shim] key2 seeded @0x3E190C = PK…` + **回读 = `50 4b 05 06 50 4b 06 06`** ✓ 写入成功 |
| `-E CGM_KEY2_SEED=1` 是否到 guest | wrapper 里确实有该 `-E`，且 shim 的 evidence 行被打印 ✓ |
| **崩溃现场再读 key2** | **`00 00 00 00 00 7d 1e 47`（两侧二进制完全相同）** |
| 行为是否变化 | **与场景 A 逐字相同**（仍 `open …/ui_cn.zip fail` ×2；覆盖率 48/49 不变）✗ |

⇒ ① **`key2` 有写入者**（我们的注入被它覆盖；覆盖值两侧一致 ⇒ 是确定性代码，不是随机栈残留）；
　 ② 它写进去的**不是 ZIP 签名** ⇒ **`key2` 不是签名表**（很可能与邻居 `ArchivePath`/`GamePath`/`mdtemp1`
　　 一样是个**临时缓冲**）；
　 ③ ★★ **但更进一步的分析推翻了这个结论**：比对点机器码是
　　 `10fa4: ldrsb r0,[r3,#4]` / `10fb0: ldrsb r0,[r3]`，而 `r3` 来自 GOT 槽 **0x3B1E10**，
　　 槽内静态值 = **0x3E190C = `key2`** ⇒ **比对源确实是 `key2`**。
　　 我们的注入之所以"没生效"，是因为**它在搜索之前就被运行期写入者覆写了** ⇒
　　 那次实验**无效**（no-op ≠ 假设被推翻）。**归因回到"key2 是对比源"，但 key2 的初值来源未知**。
　　 ④ 静态定位两次失败：Ghidra 全量反编译 0 写入者；本轮又扫了工厂 `.text` **75 万条指令**里
　　 所有能构造 `0x3E18D0..0x3E1940` 的 `movw/movt` / 字面量池 / `add pc` —— **0 命中**
　　 ⇒ 写入者走 **GOT 间接指针**（`ldr rX,[r6,#off]`），是静态扫描的盲区。
　　 ⑤ 现场值 `00 00 00 00 00 7d 1e 47` 与 shim 现有任何一种 KY 派生载荷都不吻合。
　　 ⇒ 下一步实验（已接入 CI 场景 D）：把**所有 SFC 数据读**载荷统一填 `0xC7`（芯片 ID/UniqueID 保持真实）
　　 并 dump 现场 key2 —— key2 若变 `C7C7…` 则链路成立；否则改用**写陷阱**抓写入者 pc/lr。

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

#### G1·补 ★★★ **正向判决达成（2026-09-17 场景 E）** —— 不再是"同样坏"，而是"key2 对了就真能打开"

| # | 观测 | 结论 |
|---|---|---|
| 1 | shim 的 I/O 轨迹（`CGM_IO_TRACE=1`）显示 zip 是经 **`fopen`** 打开的：`io #11/#12/#15 fopen rc=0 /sdcard/cubegm//ui_cn.zip ◀ ZIP` | **此前拦 `open`/`openat` 是拦错了地方** —— glibc 的 `fopen` 内部用隐藏符号调 `open64`，**不走 PLT** ⇒ 拦截点必须覆盖 `fopen` |
| 2 | 在 `.zip` **打开瞬间**重新断言 key2（`CGM_KEY2_HOOK=1`）后，**工厂侧 `M6 UI 资源包打开 = ✓(包已打开(条目缺失))`**；stdout 的报错由 `open …/ui_cn.zip fail` 变成 `find ui.cfg in …/ui_cn.zip fail` / `find font.ttf in … fail` / `find setting.raw fail` | **中央目录搜索成功了** ⇒ **G1 根因（`key2[0..7]` 全 0 导致签名比对失败）被正向实验确证**，而非只是"两侧一致地坏" |
| 3 | **真机证据**：原厂 SD 上设备自写的 `menu.log`（444 B）= 一段结构化记录（`offset 0x11c: 0a 00 00 00`、`0x120: 9d 0a 00 00` = **2717**、多处 `ff ff ff ff` 哨兵、`0x000: 05 00 00 00`） | 设备上**菜单确实运行过并被使用**（有游标/页/最后选择等字段）⇒ **真机上工厂 `rkgame` 能打开 `ui_cn.zip`** ⇒ **`key2` 在真机确有来源**（沙箱缺的正是那一环：SFC 假设备返回的 security 数据）⇒ 也顺带回答了 G4 的分支线索：**不是版本不匹配**（至少在"能不能打开资源包"这一点上） |
| 4 | 新的次级缺口：即便中央目录解析成功，条目查找仍失败（`find ui.cfg in … fail`），而 **`ui.cfg` 确实在包里**（`ui_cn.zip` 6 条目：`ui.cfg` 242 B / `menu.raw` / `search.raw` / `setting.raw` / `type.raw` / `game.raw`；**无 `font.ttf`**） | 该缺口在**工厂侧同样出现** ⇒ 属"包/环境"问题而非我们的实现差异 ⇒ 归入 **G3**（上游 zip 路径未对齐 / 资源包变体不符）继续查 |

#### G1·补二 ★★ 本轮引入并已修复的一个**假分歧**（值得记住的教训）

为打开窗口，我给 shim 加了 `fopen` 拦截 + I/O 轨迹，并在拦截体里调用 `note()` 打日志 ——
而 `note()` 当时内部走 **`vsnprintf`** ⇒ **在被拦截的 stdio 函数里再入 stdio**。

现场（判决性）：重建产物在解析 `setting.xml`（mini-XML）时崩：
`pc=0x0000003a`、`lr=0x0503ec68`（`mxml_load_data+0xdbc`），反汇编 `503ec64: e12fff3a blx sl`，
**`sl = 0x3a`（= ASCII `':'`）、`r3 = 0x3f`（= `'?'`）**，栈上 `[sp+0]` 解析为 libc 的 `_IO_wfile_jumps`
⇒ **FILE 内部结构被半初始化的 stdio 状态污染**。工厂侧恰好没踩到同一窗口 ⇒ 表现为"同一 shim、两侧不同结果"的**假分歧**。

**已修复（根治）**：
1. `note()` 改为**只依赖 `write(2)` 的自包含格式化器**（支持 `%s %d %u %x %p %%` + `l` + `-`/`0` + 宽度）；
   附带收益：`sfc_fault()`（信号处理器）里的日志**从此 async-signal-safe**。
2. 新增 `tools/shim_fmt_selftest.py`：**从 `fake_mem.c` 实时抽取**格式化器（不是快照 ⇒ 永不腐烂），
   ① 硬断言块内**无任何 stdio 调用**（剥注释后检查）；② 12 条用例与 `snprintf` 逐一对拍（`%p` 用显式期望）。
   已接入 `1to1-verify` 作**硬门禁**，并做过**反向验证**（临时塞回 `vsnprintf` ⇒ 门禁立刻 FAIL）。
3. 崩溃报告器**提前到 constructor 装配**（原先只在 SFC 装配时安装 ⇒ 崩在那之前的崩溃现场全丢，
   本轮为此多花了一整轮 CI）。

#### G1·补三 ★★★★★ **窗口已打开（2026-09-17 场景 E，`1ac8c25e`）** —— 重建侧首次走到 M6，覆盖率 4 → 58

| 指标 | 修前（`adb16450` 之前） | 修后（`1ac8c25e`） |
|---|---|---|
| 场景 E 重建侧 `M5 main_Menu` | ✗（崩在 `setting.xml`） | **✓** |
| 场景 E 重建侧 `M6 UI 资源包打开` | ✗（未走到） | **✓（包已打开，条目缺失）** |
| 场景 E 重建侧 stdout 行数 | **3** | **21** |
| 场景 E 重建侧专有函数覆盖 | **4 / 223 = 1.79%** | **58 / 223 = 26.01%**（字节 26.88%）|
| A/B/C 回归门禁 | PASS | **PASS（未受影响）** |

**★ 挡住这一切的真实缺陷（不是环境，是我们的重建错）**：`mxmlLoadFile` 的调用点漏了第 3 个参数。

- 工厂机器码（每处调用都是）：`mov r2,#0` → `mov r1,fp` → `mov r0,#0` → `bl mxmlLoadFile`
  ⇒ 真实形态 `mxmlLoadFile(NULL, fp, NULL)`（3 参，第 3 个是"类型推断回调"）。
- 我们写成了 `mxmlLoadFile(0, fp)`（**2 参**）⇒ ARM 上 r2 是**寄存器垃圾** ⇒
  `mxml_load_data` 内 `(*cb)(parent)` 处 `blx r10`，而 r10 = **0x3a / 0x00（随场景漂移）**
  ⇒ 解释了两个此前说不通的现象：① 同一二进制在某些场景崩、某些场景不崩；② 崩点 pc 会在两轮之间"变值"。
- 同类第二处：`mxmlDelete()`（**一个实参都没传**）⇒ 已改为 `mxmlDelete(tree)`。
- **根因治理**：把 `proto.h` 里三个 K&R 空参声明改成**真原型**（`mxmlLoadFile(gh_u4,void*,gh_u4)` 等）
  ⇒ 漏参在**严格编译门禁**阶段直接报错，不再靠人眼看。

#### G1·补四 ★★★ **更正**：所谓"19 个函数存在漏参"是**错口径产物**，真实存量 = **0**

上一轮我据 `tools/scan_kr_argcount.py`（数工厂机器码 `bl` 前的 `r0..r3` 个数）报告"**19 个函数存在漏参**"。
**这个结论是错的**，必须更正。追查过程（四次口径修正，每次都被工具内置的**自证锚点**拦下）：

| 口径 | 现象 | 为何错 |
|---|---|---|
| ① 取全部调用点的 **max** | `mui_ReadJoystick` 报"工厂 1 参 / 我们 0 参" | 57 处调用里只要有 1 处碰巧设了 r0 就判成 1 参 ⇒ **假阳性** |
| ② 取 **min** | `mxmlDelete` 报 min=0 | `mxmlRelease→mxmlDelete` 是**尾调用**，r0 继承自本函数参数，窗口里本就不该有赋值 ⇒ **假阴性** |
| ③ 取 **前缀 arity**（r0 起连续前缀） | 锚点仍不符 | `mxmlDelete` 调用点前面是 `ldr r0`→`cmp`→`beq`→`bl`，我"遇分支即停"把参数设置丢了 ⇒ **假阴性** |
| ④ 边界收敛为"仅无条件流改变" | 锚点通过，得 20 项 | 但 `len(regs)` 仍被**临时寄存器**污染（`ldr r3,[r4,#204]` 让 `mxmlDelete` 量成 2 参）⇒ **假阳性** |

**最终采用的口径（保守、无假阳性）**：`tools/scan_call_args.py` —— 以**工厂 per-function 反编译 C 的调用表达式**为准，
逐 `(调用者, 被调者)` 比较实参个数。关键性质：Ghidra 推断原型偏小时会**丢参数**
（它把工厂真实的 `mxmlLoadFile(0,fp,0)` 渲染成 `mxmlLoadFile(0,__stream)`），
故该口径**只可能少算、不可能多算** ⇒ 用它判"我们比工厂少传"**不会产生假阳性**（代价是可能漏报，由机器码口径本地兜底）。

**结论（自证通过，1279 对可比对）**：`✓ 无新增漏参` —— **真实漏参数 = 0**，
除已修的两处：`mxmlLoadFile` 6 个调用点（漏第 3 参 `cb`）+ `mxmlDelete` 1 处（零实参）。

**机器码口径的去向**：`tools/scan_kr_argcount.py` 降级为**本地工作清单生成器**（不再进门禁）。

**两处真修复的验证强度**：`mxmlLoadFile` 修好后，场景 E 重建侧**覆盖率 4 → 58 个函数**、
`M5/M6` 首次到达 —— 这是"漏参 ⇒ 寄存器垃圾"这一类缺陷的实证。

#### G1·补五 ★★★★ **M6 之后的第一个真分歧**（窗口打开后才看得见）

场景 E 下两侧`M5/M6`都到达，但 stdout 从第 21 行开始分叉：

| 行 | 工厂 | 重建 |
|---|---|---|
| 21 | `find ui.cfg in /sdcard/cubegm//ui_cn.zip fail` | **缺** |
| 22 | `find font.ttf in /sdcard/cubegm//ui_cn.zip fail` | ✓ |
| 23 | `find setting.raw fail` | **缺** |

**重建侧崩点已定位**：`pc = 0x05047020` ⇒ **`stbtt_GetFontVMetricsOS2 + 0x8`**（就在打印 `font.ttf` 之后）。

三条消息的发出位置（已逐个定位）：
- `find ui.cfg in %s fail` ← `get_items_from_zipfile`（调用链 `mui_LoadConfig → get_items_from_zipfile`）；
- `find font.ttf in %s fail` ← `mui_InitFont`；
- `find setting.raw fail` ← `mui_LoadUIResource(&DAT_003af294,"setting.raw")`。

已排除的方向（都做了逐行核对）：我们的 `get_items_from_zipfile`、`FindZipItemA`、`unzLocateFile`、
`unzStringFileNameCompare` **与工厂语义一致**（函数尺寸差只是编译产物，不是语义差——这条差点让我误判）。

#### G7 ★★★★★ **上游库版本钉错**（机械证据，本轮新增门禁）

新增 `tools/scan_symbol_delta.py`：把两侧的**上游库公有 API 符号集合**摆在一起对拍
（过滤 `isra`/`part` 等内联重命名；自证锚点 `stbtt_FindSVGDoc` 必须被报为"我们多出"）。
首跑结果：**我们比工厂多出 14 个上游公有 API**：

| 库 | 我们多出的 API | 含义 |
|---|---|---|
| stb_truetype | `stbtt_FindSVGDoc` / `stbtt_GetCodepointSVG` / `stbtt_GetGlyphSVG` | **SVG 支持自 v1.22 才引入** ⇒ 工厂的 stb **更旧**（≤1.21）|
| stb_truetype | `stbtt_GetKerningTable` / `stbtt_GetKerningTableLength` | 同上（较新版本才导出）|
| mini-XML | `mxmlElementGetAttrByIndex` / `mxmlElementGetAttrCount` / `mxmlNewOpaquef` / `mxmlSetOpaquef` / `mxml_fd_read` / `mxml_free` / `mxml_parse_element` | 工厂的 mini-XML 是**更旧/被裁剪的变体** |
| Helix MP3 | `MP3ClearBadFrame` / `mp3_unused_GetNextFrameInfo` | Helix 变体不同 |

**"是版本旧，还是被 `--gc-sections` 裁掉"的判别依据**：工厂**保留了同样没被游戏使用的**
`stbtt_PackFontRanges*`、`PackSetOversampling`、`PackSetSkipMissingCodepoints` 等公有 API
⇒ 它**没有做函数级裁剪** ⇒ 缺失的 SVG 函数**确系版本更旧**（这一判别很关键，否则会误判成链接器行为）。

⇒ **影响**：现有"上游定版"里 `stb_truetype v1.26`、以及 mini-XML / Helix 的钉版**都需要重新取证**；
`stbtt_GetFontVMetricsOS2`（我们 0xd4 / 工厂 0xa8）等尺寸差异也提示实现不同。
**门禁已上线**：14 项入 `tools/upstream_api_pending.txt` 台账，**新增"我们多出"即失败**（棘轮）。

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
| 2 | ~~重新定位 `SearchCentralDir` 的比对源~~ **已完成（2026-09-17）**：比对源 = `key2[0..7]`，静态初值恒 0；下一步是**用 B/E 两档单变量实验**判定是否存在运行期写入者 | 解掉 G1 
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

## 五·补、进度的**正确刻度**：功能里程碑（而非覆盖率）

**为什么要换刻度**：覆盖率会随**环境**变动而非单调 —— 场景 C 补 `libkms` 桩让 `driver.so` 加载成功后，
程序随即撞上「假 `/dev/dri` 无法应答 DRM ioctl」而**更早终止** ⇒ 覆盖率 48 → 6。
但**同场景下 工厂 7 / 控制组 7 / 重建 6 三者同步下降** ⇒ 那是**环境属性**，不是实现退步。
若拿覆盖率当进度尺，会得出"越修越远"的错误结论（本报告第一版就是这么写的，已改）。

### 里程碑矩阵（`tools/milestones.py`，已接入 CI，每轮自动产出）

| 里程碑 | 场景 A（默认） | 场景 B（key2 注入） | 场景 C（libkms 桩） |
|---|---|---|---|
| M0 进程启动 | ✓ 三侧 | ✓ 三侧 | ✓ 三侧 |
| M1 配置读取 | ✓ | ✓ | ✓ |
| M2 SPI/SFC 初始化 | ✓ | ✓ | **✗**（更早终止，未走到）|
| M3 `driver.so` 加载 | **✗ 加载失败** | ✗ 加载失败 | **✓ 成功** |
| M4 DRM 显示 | ✗ | ✗ | **✓ 到达 `open drm!`**（ioctl ENOSYS ⇒ 随即崩）|
| M5 `main_Menu` 入口 | ✓ | ✓ | ✗ |
| M6 UI 资源包打开 | **✗ 打开失败** | ✗ 打开失败 | 未走到 |
| M7 菜单存活（不崩） | ✗ | ✗ | ✗ |
| 终止 | exit=139 | exit=139 | exit=139 |
| **两侧里程碑差集** | **空** | **空** | **空** |

### 这张表怎么读（对"是否在向 100% 推进"的回答）

1. **等价性维度：在收敛** —— 三个场景下两侧里程碑差集**全为空**、B1–B8b 全 PASS、
   符号/布局/ABI/动态段全绿。也就是"同一环境下我们与原厂行为一致"这件事**从未被破坏**。
2. **环境能力维度：在推进** —— SFC 有状态设备仿真 → stdio I/O 底座 → `libkms` 桩（`driver.so` 成功加载）
   ⇒ **工厂自己**能到达的里程碑也在增加（M3/M4 是场景 C 新拿到的）。
3. ★ **功能可用性维度：尚未证明** —— **没有任何一个场景能让原厂二进制走到 M6/M7**。
   也就是说：当前所有"绿"都建立在"**双方在同一个坑里**"之上 —— 它证明的是"**同样坏**"，
   而不是"能用"。这正是"感觉越修越远"的根源：**环境的坑一个接一个（先 libkms，再 DRM，再 zip）**，
   每个坑都会把窗口截断，于是覆盖率上下起伏，而"能跑起来"始终没被证明。
4. ⇒ 结论：**方向没跑偏（等价性在收敛、环境能力在推进），但"逼近目标"的速度取决于环境缺口**，
   而当前**唯一挡住 57% 重构量**的缺口是 **M6（UI 资源包打开）**。它必须先被解决。

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

---

## 八、★ 新门禁（第 42 轮）：调用点实参寄存器对拍（工厂 = 对照组）

### 为什么这一轮才做出来

前两轮我已经两次被"K&R 空参声明掩盖的调用点差异"打脸：

| 轮次 | 工具 | 口径 | 结果 | 为什么不够 |
|---|---|---|---|---|
| 40 | `tools/scan_kr_argcount.py` | 数每个 `bl` 前写过几个 `r0..r3`，**跨全部调用点取最大** | 报 19 项 | 口径错，噪声 19 项全是假的（临时寄存器被当参数 / 尾调用继承 r0 / 编译器为未用形参清零） |
| 41 | `tools/scan_call_args.py` | 对拍**工厂反编译 C** 的调用表达式 | 报 0 项 | Ghidra 推断原型偏小时会**同时丢两侧**的参数（它把工厂真实的 `mxmlLoadFile(0,fp,0)` 渲染成 2 参）⇒ 结构性看不见 |
| **42** | **`tools/scan_livein_args.py`** | **两侧机器码逐 (调用者,被调者) 对拍** | **HIGH 5 / LOW 70** | 这正是本次要报告的 |

### 口径（`tools/scan_livein_args.py`）

对每一对 `(调用者, 被调者)`：
1. 收集**两侧各自全部调用点**的"已设实参寄存器集合"，
   可用性按回溯终止原因分三档：
   - `entry` —— 一路回到函数入口（未跨调用/跳转）⇒ **入口参数仍可用**，并入本函数 live-in；
   - `call`  —— 跨过了 `bl`/`blx` ⇒ `r0..r3` 已被冲掉，只能用之后的显式写入；
     （★ 例外：`r0` 承接被调者返回值，可被直接转发 ⇒ 仅缺 `r0` 时降级为 LOW，不计 HIGH）
   - `jump`  —— 跨过 `b`/`bx`/`pop {..pc}` ⇒ 该点可由别处到达，**无法直线推理** ⇒ 整条跳过；
2. `被调者 live-in` = 它入口处**读早于写**的 `r0..r3`（取两侧并集）；
3. `miss = 工厂交集 - 我们交集`；`HIGH = miss ∩ live-in`，其余为 LOW。

### 三级自证（铁律 101 的强制要求）

1. **构造性**：同一 ELF 当两边跑，违例必须 0；
2. **锚点**：人工逐字节核对过的 `mui_outputxy_t -> stbtt_GetFontVMetrics`（工厂恒设 `r0,r1,r2,r3`）
   必须被量到；
3. **端到端**：锚点必须出现在**最终违例表**中（验证"反汇编 → 判定"整条链路没有断点）。

三级全绿才出结论；任一级不过即 `FATAL` 退出。

### 本轮结论：这是一类全新的缺陷 —— **依赖寄存器副产物的脆弱性**

`mui_outputxy_t -> stbtt_GetFontVMetrics` 逐字节核对：

| | 工厂 | 我们 |
|---|---|---|
| 调用点 | `mov r3,#0` **＋** `mov r2,r3`（r0..r3 全设） | 直接 `mov r2,#0`，**r3 从未设置** |
| 被调函数体 | `cmp r3,#0` → `strne r0,[r3]`（**会解引用 r3**） | 同（v1.26 源码 `if (lineGap) *lineGap = ...`） |

★ 关键鉴别（**必须诚实**）：**工厂的反编译 C 同样只有 3 个实参**
（Ghidra 渲染 `stbtt_GetFontVMetrics(font,&fontascent,0)`）
⇒ 原厂源码里那句就是 3 参，`mov r3,#0` 是 **GCC 构造 `r2=0` 时顺带的副产物**（恰好安全）。
我们换 clang 后 `mov r2,#0` 不再顺带清 r3 ⇒ **r3 = 上层残留值** ⇒ 一旦非 0 就是**野写**。

⇒ 所以它**不是"漏参"**，而是：**行为在原厂是"偶然确定"，在我们这里变成"不确定"。**
1:1 替代必须把这种偶然性**显式化**。已修：`proto.h` 把该函数从 K&R 空参声明改成真原型
（`extern void stbtt_GetFontVMetrics(void *info,int *ascent,int *descent,int *lineGap);`），
两个调用点显式补 `,0`（= 与工厂 `r3=0` 行为一致且确定）；本地严格门禁配方下 0 error。

### 台账（`tools/livein_args_pending.txt`，棘轮）

| 分级 | 对数 | 含义 | 代表 |
|---|---|---|---|
| **HIGH** | **5** | 缺失寄存器确在被调者 live-in 中 ⇒ 可能野写/野指针 | `mui_outputxy_t->stbtt_GetFontVMetrics`（已修）、`PauseMenu/mui_setting->mui_DispBlock`（工厂 4 参 `param_4` 是**表索引**，缺了就按垃圾偏移索引）、`xmp3_Subband->xmp3_PolyphaseStereo`、`isoir165_wctomb->gb2312_wctomb` |
| LOW | 70 | 缺失寄存器不在两侧 live-in 中 ⇒ 仅保真度差异 | `run_game->Core_Load`(r3)、`mui_setting->SaveMenuLog`(r2,r3)、`*->SeletEmuCore`(r3) … |

CI 已接入（`1to1-verify` 第 20 步，★ 硬门禁）：**新增差异即失败**；
台账条目消失（= 已修好）打印警告要求删行。

### 下一步（按收益排序）

1. **逐条人工核对 HIGH 剩余 4 项**（`mui_DispBlock` 两处是菜单主路径，优先）—— 每项都要
   回到机器码定实参，**不许照抄 Ghidra 渲染**（它两侧都会丢参数）。
2. **LOW 70 项**：批量核对，确认是纯 codegen 差异后从台账清除，或补显式实参。
3. 复用本工具的口径做 **`b`/`bl` 尾调用版的同类门禁**（当前只覆盖 `bl`）。
4. 继续 G2（假 DRM 设备仿真）、G3（`TUnzip` 语义对齐）、P6（真机对照）。

### 八·补一 第 42 轮的两条实测教训（都来自 CI 与机器码，不是推理）

**① CI 首跑红 = 自证按设计拦住，但我的锚点设计有状态盲区。**
我把正向锚点写死成"必须出现在违例表里"，而**同一轮我又把源码修好了** ⇒ CI 用新构建时
该违例已消失 ⇒ 端到端自证误报 `FATAL`。修法（已生效）：正向锚点改为**状态感知**
（只要求"被检视到"，并**打印当前判定**：违例 / 合规），并新增**负向锚点**
（一个两侧一致的调用对**必须不被误报**，防"全都报"的退化解）。
本地复跑：`selfcheck-1..4` 全过，锚点状态 = **合规（该寄存器已设）**。

**② 判据的不对称会造成凭空违例。**
工厂侧"设了 r3 的点"被保留、"没设的点"被 `jump` 档丢弃 ⇒ `IF` 里出现 r3；我们侧相反
⇒ 造出违例。修法：**任一调用点落在 `jump` 档 ⇒ 整对跳过**（保守方向：宁可漏报）。
修正后 LOW 从 70 → 43。

**③ `mui_DispBlock` 人工裁决结论 = 两侧共有脆弱性（不是我们漏参）。**
- 被调者序言**第一件事**就是 `add r4, r2, r3, lsl #4`（读 `r3`，早于任何写）
  ⇒ `param_4` **是真的第 4 参数**（表项索引）；
- 但工厂**自己的 99 处调用点里有 ≥22 处不设 r3**（例：`JoystickTest@0x2ab0c`：
  `ldr r0/ldr r1/mov r2` 之后直接 `bl`）⇒ **原厂也在用残值**。
⇒ 我们的 3 参写法是**忠实**的；这类差异是"两侧都依赖残值"，**残值不同即分歧源**。
行动 = 若为关键路径则显式化，否则记为已知分歧风险（已在台账标注"待人工裁决"）。

**④ 本地可增量重编 + 重链**（把 CI 往返降为分钟级）：
`zig cc -c` 重编改动对象 → `CC="<zig> cc" sh tools/link_full.sh`
（`build/obj/` 已有 213 个对象）。本轮用它验证：新 ELF 里两处
`bl stbtt_GetFontVMetrics` 之前均出现 `mov r3,#0` ✓；链接门禁全局符号 193/194、越界 0 ✓。

### 八·补二 门禁口径的第 3–6 次修正（全部由"自证 + 人工核对"逼出来）

| # | 假阳性来源 | 现象 | 修正 |
|---|---|---|---|
| 3 | **判据不对称** | 一侧丢弃 `jump` 档样本、另一侧保留 ⇒ 交集凭空多出寄存器 | **任一调用点不可判定 ⇒ 整对跳过**（保守） |
| 4 | **透传形参** | `isoir165_wctomb` 的 `r0`(conv) 只被**透传**给 `gb2312_wctomb`、从不被本函数读 ⇒ `own_live` 不含它 ⇒ 误报"未设 r0" | 引入 `OWNER_ARITY`（形参个数**上界**，两侧取 max）⇒ `entry` 档并入 `r0..r(k-1)`（入口处它们都是有效入参，**与是否被读过无关**） |
| 5 | **指令译码覆盖不全** | `ldmib r2,{r0,r8}` 未处理 ⇒ `r0` 未被记为已写 ⇒ 后续读被判成"进入时活跃"；`xmp3_PolyphaseStereo` 由此误报（人工核对：其序言只读 `r0/r1/r2`，**从不读 r3**，r3 是首个被写的） | 补 `ldm*/stm*/smlal/smull/umlal/umull` 系列译码 |
| 6 | **锚点写死了结论** | 同一个 ELF 对拍是构造性恒等 ⇒ 无意义；锚点又要求"必须违例" ⇒ 修好源码后 CI 误报 FATAL | 正向锚点=**状态感知**（只要求被检视到 + 打印当前判定）；新增**负向锚点**（两侧一致的调用对必须不被误报） |

**收敛过程**：`229 → 75 → 74 → 47 → 40 → 41`（对数），最终 **HIGH = 2 / LOW = 39**。

**剩余 HIGH 2 项 = `PauseMenu`/`mui_setting` → `mui_DispBlock`，已裁决为「两侧共有脆弱性」**：
被调者序言第一件事 `add r4, r2, r3, lsl #4` 读 `r3` ⇒ 第 4 参真实；但**工厂自己 99 处调用点里
≥22 处也不设 r3** ⇒ 原厂同样依赖残值。我们的 3 参写法**忠实**；这类"两侧都靠残值"的差异
是**潜在分歧源**（残值不同即行为不同），标记为已知风险而非"补参数"。

**顺带**：链接门禁在本轮修复后仍全绿（全局符号 **193/194 = 99.5%**、越界 **0**）。

---

## 九、★ 新仪器（第 42 轮）：执行集合差集 —— 比 stdout 前缀门禁更早暴露分歧机制

### 为什么需要它

行为门禁（`behav_diff.py`）比对的是两侧 **stdout 的最长公共前缀**。于是有一类分歧它**看不见**：
**两侧都不打印、但走的代码路径不同**。场景 E 的 stdout 前缀 18/18 PASS，而执行集合一对比就露出：

| 方向 | 函数 |
|---|---|
| **仅我们执行**（工厂没执行）7 个 | `mui_outputxy_t`(904B 字体渲染)、`mui_DispBlock`(124B)、`get_item_from_line`(224B)、`UnzipItem`(132B)、`strtrim`/`strtriml`/`strtrimr` |
| **仅工厂执行** 1 个 | `ClearBuffer`(32B) |

### ★ 机制（这是本轮最有价值的一条定位）

`mui_InitFont` 失败（`find font.ttf in …ui_cn.zip fail`，**两侧都打印**）之后：

- **工厂**：不再调用 `mui_outputxy_t`（字体渲染），转而执行 `ClearBuffer`；
- **我们**：**照样调用** `mui_outputxy_t` ⇒ 把无效字体传进去 ⇒
  崩在 `stbtt_GetFontVMetricsOS2+0x8`（`ldrd r8,[r0,#4]`，`r0` 无效）——
  这正是此前只看到"崩在这里"却不明原因的那个点。

⇒ 也就是说：**我们的 `mui_InitFont` 失败路径没有把后续渲染拦住**（工厂拦住了）。
这就是场景 E 的第一个**可归因**分歧，优先级高于台账里那 2 项 HIGH（它们是同一路径上的次级疑点）。

### 仪器

`tools/exec_set_diff.py`：读两份 `coverage_*.txt`，输出双向差集 + 读法提示。
已接入 `1to1-qemu-behav`（4 个场景各跑一次，写 `report/<sc>/exec_set_diff.txt`）。
★ 当前为**观测项**（`if: always()`，不判失败）—— 因为场景 E 本就存在真实分歧；
待该分歧修掉、差集归零后，再升级为**硬门禁**（棘轮："仅我们执行"集合只许缩小）。

### 九·补一 第 42 轮续：执行集合差集在 4 场景跑通 + 一处方法学更正 + 一个新缺陷

**① CI（`c1f2a690`）三 workflow 全 success；执行集合差集 4 场景产出：**

| 场景 | 工厂/我们已执行 | 差异 |
|---|---|---|
| A | （报告文件名不同 ⇒ 未产出，已修：兼容 `coverage_*.stdout.txt`） | — |
| B | 49 / 48 | 1（仅工厂 `ClearBuffer`） |
| C | 7 / 6 | 1（仅工厂 `run_process.constprop.0`） |
| **E** | **51 / 58** | **9（仅我们 8 + 仅工厂 1）** |

B/C 的差异都只是"工厂多执行一个收尾函数"，**方向上是工厂走得更远**；只有 E 是**我们多执行 8 个**。

**② ★ 方法学更正（重要）：执行集合列表是「账本域」的，不是全量函数。**

`coverage_*.txt` 的"已执行函数"只覆盖 `ledger/functions.csv` 里的 **223 个专有函数**；
上游 XUnzip 的函数（`unzLocateFile` / `unzGetCurrentFileInfo` / `unzGoToFirstFile`…）
**永远不会出现在该列表里**。⇒ 我此前据"`unzLocateFile` 两侧都未执行"做的推断**无效**，
必须撤回。教训：**任何"列表里没有 X"的结论，先确认该列表的域**（技能铁律 101 的推论）。

**③ 已排除的两项（机器码级核对，不是读源码猜测）：**

| 函数 | 工厂 | 我们 | 结论 |
|---|---|---|---|
| `unzStringFileNameCompare` | 16 B：`cmp r2,#1; beq strcmp; b strcmpcasenosensitive_internal` | 140 B：**内联**同一逻辑，`==1` 时尾调 `strcmp` | **语义等价**（16 B 是尾调 thunk，不是被裁剪） |
| `FindZipItemA` | 132 B | 88 B | **语义等价**：第 5 个栈参数工厂读 `[sp,#16]`、我们读 `[fp,#8]`，**两者都正确** |

**④ ★ 新发现一个真实缺陷：我们的 `TUnzip::Find` 少了 `unzCloseCurrentFile`。**

- 工厂（180 B）在 `unzLocateFile` 成功后：`if (hCurrFile != -1) { unzCloseCurrentFile(unz); hCurrFile = -1; }`
- 我们（288 B）：**没有调用 `unzCloseCurrentFile`**，而是**内联**了一段"`free(z_stream->…)` + `inflateEnd` + `free`"的部分清理。
  ⇒ z_stream 的释放路径、以及 `unzCloseCurrentFile` 内部对 CRC/文件句柄/全局注释的处理**全部缺失**。
- ⚠ 但它执行在 `unzLocateFile` **之后** ⇒ **不能解释**"工厂查 `ui.cfg` 失败、我们成功"这一分歧，
  只能作为一个**独立的保真度缺陷**记录（在"打开过某个条目后再查找"的路径上会导致状态不一致）。

**⑤ 分歧的搜索空间已收窄到**：`unzLocateFile`（工厂 **240 B** / 我们 **528 B**）、
`unzGetCurrentFileInfo`、`unzGoToFirstFile`/`unzGoToNextFile`。
工厂 `unzLocateFile` 的完整语义已逐条读出（240 B，见 STATUS 第四十二轮续）：
`unz==NULL → -101`；`strlen>255 → -101`；`memcpy(buf,name,len+1)`；`unz->[24]==0 → -99`；
保存 `unz->[16]`/`unz->[20]` → `unzGoToFirstFile` → 循环
`{ unzGetCurrentFileInfo(...,buf,256,...); unzStringFileNameCompare(buf,name,caseMode)==0 → 命中 }`
→ 失败则 `unzGoToNextFile`；退出前**恢复** `unz->[16]`/`unz->[20]`。
**下一步**：对拍我们的 `unzLocateFile` 这 240 B 的语义（重点是 `caseMode` 的 1/2 映射、
`unzGetCurrentFileInfo` 的 8 个参数、以及退出前是否恢复 `[16]`/`[20]`），
并用 CI 的 gdb 探针在 `FindZipItemA` 处**打印实参名字与返回值**（这是唯一能定死"查的是哪个名字"的手段）。

### 九·补二 ★ 判决性实测：`ui.cfg` 查找分歧 = **我们正确、工厂失败**（归因转向环境）

在 `get_items_from_zipfile` 里插一段**临时诊断**（已撤销），把查找现场打出来。场景 E 实测：

```
我们 | DBGZIP p=/sdcard/cubegm//ui_cn.zip zr=0 idx=0 tag=1 n=6 cur=0 f24=1 name4='ui.cfg'
工厂 | find ui.cfg in /sdcard/cubegm//ui_cn.zip fail
```

| 字段 | 值 | 含义 |
|---|---|---|
| `zr` | **0** | `FindZipItemA` **成功**（工厂非 0 = 失败） |
| `n` | **6** | 中央目录解析出 **6 个条目**（与 zip 实际条目数一致） |
| `idx` | **0** | 命中索引 0 |
| `name4` | **`ui.cfg`** | 命中条目名**就是 `ui.cfg`** |
| `tag`/`f24` | 1 / 1 | HZIP 类型标签与"已有文件列表"标志正常 |

⇒ **我们的 zip/条目层完全正确**。而两侧源码在第 28 行**逐字相同**
（`zr = FindZipItemA(res_hz,"ui.cfg",1,&local_424,ze);`）⇒
**工厂侧"找不到一个确实存在的条目"无法由源码解释** ⇒ 归因到**环境/运行期状态**
（沙箱里 `key2`/SFC 那条链只能部分复现），**不是**我们的重建缺陷。

★ 结论调整：场景 E 的**第一处**分歧（`ui.cfg` 命中与否）从"我们的嫌疑"**降级为"环境的嫌疑"**；
真正**可归因到我们**的是它后面那一步 ——
`mui_InitFont` 失败后我们**仍进 `mui_outputxy_t` 渲染**（工厂转 `ClearBuffer`）
⇒ 无效字体 ⇒ 崩在 `stbtt_GetFontVMetricsOS2+0x8`。

### 九·补三 又一个「仪器静默降级」（这次是我自己引入的）

CI 里场景 A 的覆盖率**从来没产出过**：`--tag ${CGM_COV_TAG:-}` 在 tag 为空时拼出**裸 `--tag`**
⇒ `qemu_coverage.py` argparse 直接 `error: argument --tag: expected one argument` 退出；
而脚本只打一句 `[note]` 就继续 ⇒ **静默**（`coverage_*.txt` 在 A 缺席，B/C/E 却在）。
修法：① 仅当 tag 非空才追加；② 覆盖率非 0 退出改为 **`::error::` 注解 + 打印工具输出前 12 行**。
⇒ 铁律强化：**"本该产出的仪器产物"缺席必须显式报错**，不能只留一句 note。

### 九·补四 ★ 判决性修复：`mui_setting` 的「窄指针转型」缺陷（场景 E 第一个**我们自己的**可修分歧）

**取证路径（全部机器码级，不靠推理）**

1. 用新的**执行集合差集**定位到 E 场景「仅我们执行」7 项，其中 `mui_outputxy_t`（904 B 字体渲染）
   与 `mui_DispBlock` 属渲染路径 ⇒ 指向"`mui_InitFont` 失败后我们仍渲染"。
2. 取崩溃现场（shim 提前装配的崩溃报告器）：
   `pc=0x05007570`（故障指令 `0xe5d2a000` = `ldrb sl,[r2]`）、**故障地址 `0x80`**、
   `r2 = arg6 = 0x80`。⇒ 是 `mui_outputxy_t` 读**第 6 实参（字符串指针）**时崩，指针值是 `0x80`。
3. 反查 `mui_setting` 的 8 个调用点，唯一用 `ldrb` 取 arg6 的是 `0x5015d10`：
   `ldrb r1,[r1,#4]` → `str r1,[sp,#4]`。工厂对应点是 `2b490: ldr r2,[r6,#4]!`（**取字**）。
4. 源码对照（**决定性**）：

   | | 源码 |
   |---|---|
   | 工厂 | `mui_outputxy_t(..., DAT_003af704, *puVar15);` |
   | 我们（修前） | `mui_outputxy_t(..., DAT_003af704, (gh_byte *)*(gh_byte *)puVar15);` |

   `puVar15` 是**指针表游标**（`gh_u4 **`，步长 4）。多写的一层 `(gh_byte *)` 让编译器发射
   **字节读** ⇒ 取到**指针的低字节**（该槽指针低字节恰为 `0x80`）⇒ 当指针用 ⇒ `ldrb [0x80]` 崩。
   **崩溃值与本案逐位吻合。**

**修复**（2 处，`FUN_0002b2b4_mui_setting.c:78/210` → 修后 86/218）：

```c
- (gh_byte *)*(gh_byte *)puVar15
+ (gh_byte *)*puVar15
```

本地增量重编 + 重链后机器码验证：`ldrb r1,[r1,#4]` → **`ldr r1,[r1,#4]`** ✓（arg6 恢复为字=指针）。

### 九·补五 ★ 方法学定案：`ClearBuffer` 的"分歧"是 **codegen artifact**，不是缺陷

执行集合差集显示 `ClearBuffer` 在 **A/B/C/E 全部 4 个场景**都"仅工厂执行"，看着像稳定差异。核查：

| 层 | 结论 |
|---|---|
| 工厂 | `xmp3_AllocateBuffers` 里 **8 处 `bl ClearBuffer`**，尺寸 `[2032, 56, 328, 284, 4624, 840, 6944, 8708]` |
| 我们 | 同函数把 `ClearBuffer` **内联**成 `memset`/`vst1.32`，尺寸 `[2004(+28), 56, 328, 284, 4624, 840, 6944, 8708]` |
| **判定** | **尺寸多重集完全一致**（2032 = 28 + 2004）⇒ **语义等价**，差异仅"是否保持外联调用" |

### 九·补六 ★★ `mui_setting -> mui_outputxy_t` 的 `bl` 数 13 vs 8 —— 也是 codegen artifact

源码级（Ghidra per-function C）**两侧都是 13 处**；二进制 `bl` 数我们只有 8，因为 clang 把
工厂那两处（`sub r2,#10` / `sub r2,#6`）用 `mvn r7,#9` + `mvneq r7,#5` **合并成一处调用点**
（cross-jumping），函数体积反而更大。

**⇒ 方法学铁律（已写成技能 112）**：
**二进制层的「调用点计数」「某函数是否被执行」都不是保真度指标** ——
编译器有权合并（cross-jumping）、复制（unrolling）、内联、外提。
对拍必须回到**源码级调用表达式计数**，或用**机器码语义等价性**（尺寸/参数/边界）判定。

### 九·补七 两道新硬门禁（本轮新增，`1to1-verify` 现共 10 道 ★）

| 门禁 | 工具 | 自证 | 首跑 |
|---|---|---|---|
| **逐函数「调用点个数」对拍**（源码级，与 codegen 无关） | `tools/scan_call_counts.py` | 正向 2 条 + **负向 4 条**（证明 mangled 名归一化生效） | **0 项**（台账空） |
| **窄指针转型 + 解引用扫描** | `tools/scan_narrow_deref.py` | 构造性 **3 危险 + 6 安全**；反向验证命中恰好那 2 行 | **0 项** |

`scan_call_counts.py` 的口径：以 **Ghidra per-function C 的调用表达式**为权威，按文件名 stem
（`FUN_<addr>_<name>`）配对，只报"工厂有、我们没有"（保守方向）。带 `canon()` 归一化：
`_Znwj→operator_new`、`_ZN6TUnzip4OpenE…→Open`（首版因 `CALL_RE` 把前导 `_` 吃掉而失效，已修）。

`scan_narrow_deref.py` 的判据**刻意收窄**到 `(窄类型 *)*(窄类型 *)`（内外都窄）：
第一版只匹配 `(窄类型 *) *`，误报 13/15（合法的 `(char *)*m_search`、libiconv 的
`(unsigned char*)*outbuf`、`(gh_byte *)*(gh_u4 *)(p+4)` 全被误报）⇒ 收紧后 0 误报。

### 九·补八 ★ 修复后实测：崩溃点**前移一大步**（从"参数垃圾"进到"真实字形渲染"）

修复 `(gh_byte *)*(gh_byte *)puVar15` 后同一场景（E）的崩溃现场：

| | 修前 | **修后** | 工厂（对照） |
|---|---|---|---|
| 崩点函数 | `mui_outputxy_t+0x84` | **`stbtt_FindGlyphIndex+0x8`** | `mui_setting+0x114` |
| 调用者 | — | `stbtt_GetCodepointBitmapBoxSubpixel+0x2C` | — |
| 故障指令 | `ldrb sl,[r2]`（读字符串首字节） | 解引用 `[r3+4]`（字形表查找） | `ldrh r0,[r3,#4]`（图像描述符） |
| 故障地址 | **0x80**（= arg6 低字节） | **0x4**（= NULL + 4） | **0x4** |

**读法**：修前我们崩在"**传进来的参数本身是垃圾**"（`0x80`）；修后已进到
**真正的字形渲染**（`stbtt_FindGlyphIndex` 里访问 font 表），崩因是
`mui_InitFont` 失败（`find font.ttf in …ui_cn.zip fail`，**两侧都打印**）导致 font 指针无效。
⇒ **这一处是我们自己的缺陷，已修死**；剩下的分歧属"环境缺 `font.ttf`/SFC 安全数据"那一类
（工厂同样在此区域崩溃，只是崩点函数不同）。

**仍存的真实分歧**（E 场景门禁 FAIL 的具体项）：
`[FAIL] B2 events 可判定前缀 20/59 行一致；重建侧共 58 行 ★ 未到达参考侧的确定性前缀（提前终止）`
—— 我方 stdout 21 行 vs 工厂 23 行，差的正是两条 find-fail
（`find ui.cfg … fail` 我们**没有**，因为查找成功；`find setting.raw fail` 我们**没走到**）。

### 九·补九 门禁首跑在 CI 上红（本地绿）—— 缺"目录不存在即跳过"守卫

`tools/scan_call_counts.py` 依赖本机 Ghidra 反编译目录（本机产物、不进仓库）。
首跑 CI 时该步骤直接 `[FATAL] 索引为空` 退出 ⇒ 打红。已按 `tools/scan_call_args.py` 的既有做法
加 `[SKIP]` 优雅跳过（本地模拟 CI：`--ghidra D:/no_such_dir` ⇒ SKIP、退出 0 ✓；
正常路径仍 213 对可比对、PASS）。
**纪律**：任何依赖**本机产物**的门禁，都必须显式处理"产物缺席"，并**打印 SKIP 原因**而不是静默/报错。

---

## 十、第 44 轮 ★ `setting.raw` 判决 + 用「关键地址命中普查」把工厂侧失败钉到具体分支

### 10.1 `setting.raw` 其实**在包里**，而且我们读对了

在 `mui_LoadUIResource` 入口加 env 门控探针（已撤）后拿到：

```
我们| DBGUI2 req=setting.raw zip=/sdcard/cubegm//ui_cn.zip
我们| DBGUI2 req=setting.raw zr=0 HIT size=2857048
```

对照 `ui_cn.zip` 的真实条目：

| 条目 | 大小 |
|---|---|
| `ui.cfg` | 242 B |
| `menu.raw` | 3,282,288 B |
| `search.raw` | 2,234,144 B |
| **`setting.raw`** | **2,857,048 B** ← 与我们的 `HIT size` **逐字节一致** |
| `type.raw` | 2,274,136 B |
| `game.raw` | 2,911,744 B |

⇒ 我们不仅**找到**了 `setting.raw`，还**正确解压**了 2,857,048 B。
而工厂对**同一个 zip 里确实存在的条目**报 `find … fail`。

### 10.2 ★★ 关键地址命中普查：工厂失败被钉到具体分支

新增 CI 设施 `CGM_TRACE_ADDRS`（在 `-d exec` 原始日志被删**之前**统计指定地址的出现次数；
**制品只留尾部 800 行，覆盖不到这些位置**）。场景 E 实测（工厂与 control **完全一致**）：

| 地址 | 含义 | 命中 |
|---|---|---|
| `000119f4` | `unzLocateFile` 的 **-99 早退**（`unz->[24]==0`，`mvn r3,#99`） | **1** |
| `000119e4` | `unzLocateFile` 的 -101（`unz==NULL` / `strlen>255`） | 0 |
| `0001162c` | `unzGoToFirstFile` 入口 | **1** |
| `00010ea0` | `unzStringFileNameCompare`（遍历中真的比过名字） | **0** |
| `000115ec` | `unzGetCurrentFileInfo`（遍历中取过条目信息） | **0** |
| `00011948` | `ldr r3,[r5,#24]` 所在块 | 3 |
| `00011950` | `cmp r3,#0` / `beq` 所在块 | 0 |

**读法**：
1. 工厂有 **1 次**调用在 `unz->[24]==0` 处**直接返回 -99**（连遍历都不进）；
2. 另一次**通过了** `[24]` 检查并进入 `unzGoToFirstFile`，但
   **`unzStringFileNameCompare` 与 `unzGetCurrentFileInfo` 命中均为 0**
   ⇒ **循环体零执行** ⇒ `unzGoToFirstFile` **返回了非 0**，直接跳到返回路径。

⇒ **工厂侧的 zip 条目查找在沙箱里不可用**，且失败发生在"中央目录遍历"这一层
（要么 `[24]==0` 早退，要么 `unzGoToFirstFile` 失败），**从未走到"逐个比名字"**。
我们的实现（`unzLocateFile` 已逐指令核对：同样有 `[24]==0 → -99` 的检查）在同一 zip、
同一 shim、同一 key2 注入下**全部成功**。

**归因**：这是**沙箱环境缺一环**（`unzOpenInternal` 填 `[24]` / 建立遍历所需的某个状态），
而真机上工厂经 `menu.log` 证明**能打开资源包** ⇒ 该缺口在真机不存在。
**不影响"1:1 替代"**（真机上两侧都会成功），但**必须保留为待真机对照项**。

### 10.3 本轮的三处「仪器/脚本层静默失效」（都花掉了真实轮次）

| # | 现象 | 根因 | 修法 |
|---|---|---|---|
| ① | `trace_hits_factory.txt` 被创建但**空**；`exec_factory.log` 没删；场景 E 的 rebuild 侧与差分**完全没跑**，而 workflow 仍报 success | `_n=$(grep -ac …)` 在**无匹配**时返回 1，脚本是 `set -e` ⇒ **整体退出**（退出发生在 `rm` 之前） | `grep … \|\| true` |
| ② | 重建侧退回 `open … ui_cn.zip fail`（key2 未注入的原症状）、探针证据行全消失，而**行为门禁反而报 PASS（假绿）** | YAML `run:` 里把**注释插进了 `\` 续行链中间** ⇒ shell 把注释行与上一行合并、注释吃掉其后内容、且该行不以 `\` 结尾 ⇒ **续行链断裂**，后面变成独立命令 ⇒ `CGM_KEY2_SEED`/`KEY2_HOOK`/`IO_TRACE`/`DBGUI2` **全部静默丢失** | 注释移到链外；新增硬门禁 `tools/lint_workflow_continuation.py` |
| ③ | Python heredoc 里含反斜杠的锚点**永远不匹配** | Bash 工具会把命令里的 `\\` 折叠成 `\`，于是 Python 里的 `\\n` 变成**真换行** | 一律用 `chr(92)` 构造反斜杠 |

**③ 的连带发现**：本仓库有 **181 个 CRLF 文件**（vs 928 个纯 LF）——
凡是对这些文件做多行文本替换，必须先做换行归一（`replace(CRLF, LF)`），否则多行锚点失配。

### 10.4 新增硬门禁

`tools/lint_workflow_continuation.py`：检查所有 workflow 的 `run:` 块中
**"注释行紧跟在以 `\` 结尾的行之后"**。构造性自证 1 坏样本 + 4 好样本；
已接入 `1to1-verify`（现共 **11 道 ★ 硬门禁**）。
