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

---

## 十一、第 45 轮：C++ 包装层（XUnzip / TUnzip）对齐 + 一处自我更正

### 11.1 先更正：`TUnzip::Find` **并不缺** `unzCloseCurrentFile`

第 44 轮我据"工厂 0xb4 里有该调用、我们 0x120 里没有"判定"我们少了 `unzCloseCurrentFile`"。
本轮逐指令核实 —— **结论错了**：

| 证据 | 内容 |
|---|---|
| 我们 `unzCloseCurrentFile` 独立符号 | 仍存在（`0x80` = 128 B） |
| 全 ELF 里 `bl unzCloseCurrentFile` 的调用者 | **0 个** |
| 我们 `TUnzip::Find` 尾部机器码 | `ldr r7,[r8,#124]` → `cmp r7,#0` →（非空）`free` → `inflateEnd` → `free` → `str r9,[r8,#124]`，**与独立函数体逐指令同构** |

⇒ clang 把同 TU 的 `unzCloseCurrentFile` **整体内联**进每个调用者（与 `ClearBuffer` 同一物种）。
**"有没有 `bl`"不是判据，机器码/源码语义才是**（技能铁律 112 的第二次应用）。

### 11.2 真差异 1：`TUnzip::Find` 多了一次 264 B 栈拷贝（已修）

| | 工厂 | 我们（改前） |
|---|---|---|
| 机器码 | `128fc: bl unzLocateFile` 之前 **r1 从未被写过**（`param_1` 直接透传） | `mov r0,r7` → `bl strcpy` → `mov r1,r7` |
| 栈 | 无本地缓冲 | `sub sp, sp, #264`（`char name[MAX_PATH]`） |
| 尺寸 | `0xb4`（180 B） | `0x120`（288 B） |

`unzLocateFile` 内部本就会 `memcpy` 进 `s->szCurrentFileName` ⇒ 我们的拷贝**语义多余**；
且是**潜在栈溢出**（名字 >263 会在 `strlen >= UNZ_MAXFILENAMEINZIP` 检查**之前**冲掉本帧）。
已删除 ⇒ 机器码里 `strcpy` 与 `#264` 均消失，尺寸 `0x120 → 0x100`；
余下 `0x100` vs `0xb4` 的差 = **我们内联了 `unzCloseCurrentFile`、工厂是外调**（已解释干净）。

### 11.3 真差异 2：`unzOpenCurrentFile` 参数个数（mangled 名级铁证，已修）

| | mangled 名 | 含义 |
|---|---|---|
| 工厂 | `_Z18unzOpenCurrentFileP5unz_s` | **单参** `(unz_s*)` |
| 我们（改前） | `_Z18unzOpenCurrentFileP5unz_sPKc` | **双参** `(unz_s*, char const*)` |

这条此前只有"印象"（结构体注释里写着"工厂是单参数"）；本轮拿到 **Itanium ABI 级**硬证据。
结构体字段（`malloc(0x6c)` = 108）早在更早轮次就按工厂删过，但**形参一直留着**
（源码注释自陈"仅为暂不改变调用点签名"）⇒ 第 45 轮补完：定义 / 声明 / 两个调用点全部收成单参。
★ 附带收益：C++ 强类型检查现在会在**编译期**拦住"调用点少传参"这一类
（反向验证时实测触发：`too few arguments`）。

### 11.4 新硬门禁：C++ mangled 签名对拍（第 12 道 ★）

`tools/scan_cxx_abi.py`：**参数的个数与类型全部编码在 mangled 名里** ⇒ 按"名字部分"配对、
比较参数编码集合，即可机械抓出这一整类漂移，且**与编译器无关**（clang / gcc 同用 Itanium mangling）。

- 归一化：`.isra.N` / `.part.N` / `.constprop.N` / `.cold` / `.llvm.N` / `.N` 先剥离
  （工厂 `TUnzip::Get` 同时有 `Get` 与 `Get.part.5` ⇒ 归一后必须只剩 1 个 sig）。
- 排除：`_ZL…`（内部链接）/ `_ZZ…`（函数局部）—— 避免"同名 static 帮手签名不同"这类假阳性。
- 判据**刻意收窄**：只判"共有名字的签名不一致"；"仅一侧有"只作规模指标 —— 但**列入棘轮**（只许缩小）。
- 自证：3 条正向锚点（状态感知打印当前判定）+ 1 条归一化锚点；
  **反向验证**：把改前版 `.o` 放进链接 ⇒ 门禁精确报出唯一一条
  `_Z18unzOpenCurrentFile`（工厂 `P5unz_s` / 我们 `P5unz_sPKc`）并 `exit 1`。

**首跑结果**：两侧共有 C++ 函数名 **62 个，签名不一致 = 0** ✓

### 11.5 新发现（入台账，待处理）：我们独有 5 个 C++ 函数

| 符号 | 说明 |
|---|---|
| `_Z12Uupdate_keys` / `_Z13Udecrypt_byte` / `_Z6ucrc32` / `_Z7zdecode` | zip **加密**残留（工厂整块删除） |
| `_Z15EnsureDirectory` | 工厂**没有**该函数 ⇒ 工厂很可能删掉了 `TUnzip::Unzip` 的 **ZIP_FILENAME 分支**（解压到文件 + 建目录） |

⇒ 与"`TUnzip::Unzip` 工厂 `0x1c` + `.part.7` `0x1e8`（合计 516 B）vs 我们 `0x640`（1600 B）"互相印证。
**下一轮入口**：对拍 `TUnzip::Unzip` 的分支集合（ZIP_MEMORY / ZIP_FILENAME / ZIP_HANDLE）。

### 11.6 门禁全景（本轮后）

`1to1-verify` 共 **12 道 ★ 硬门禁**：shim 格式化器自检 / 调用点实参对拍 / 窄指针转型 /
工作流续行链 lint / **C++ mangled 签名对拍（新）** / 数组名转型 / .rodata 字符串当整数 /
P3 链接就绪审计 / P3 完整链接 + ABI 与布局 / 上游库公有 API 集合 / 调用点实参寄存器 / 调用点个数。

本地 8 道全部 PASS；链接自带门禁：全局符号 **193/194 = 99.5%**、越界 **0**、
GLIBC 上限 **2.7 = 工厂**；两侧共有 C++ 签名 **62/62 一致**。

---

## 十二、第 46 轮 ★★ `TUnzip::Unzip`：一个"门禁全绿、功能为零"的真实缺陷

### 12.1 现象：所有资源解压都拿到**空缓冲**，但返回"成功"

15 个专有调用点的写法**完全一致**（例：`mui_LoadUIResource`）：

```c
pvVar3 = malloc((ze_blob)._296_4_);      /* 按**条目大小**分配 */
UnzipItem(iVar1, local_9c, pvVar3, 0, 3);/* len = 0 ; flags = 3 = ZIP_MEMORY */
```

而我们原来的 `TUnzip::Unzip` 是**上游语义**：`unzReadCurrentFile(uf, dst, len)` **只读一次**。
`len == 0` ⇒ **一个字节都不写**、`res == 0` ⇒ 返回 `ZR_OK`（**假成功**）。
⇒ `mui_LoadUIResource` / `get_items_from_zipfile` / `mui_InitFont` / `mui_menu` / `mui_type` /
`mui_search` / `GetJoystickConfig` / `runCase` / `run_game` / `gpsp_unzip` / `FilePreEmu` /
`UpdateROM` / `mui_DisplayThumbnail` / `JoystickTest` —— **全部拿到未填充的缓冲**。

### 12.2 工厂语义（机器码级，0x126f4..0x128d8）

| 环节 | 工厂机器码 | 含义 |
|---|---|---|
| 分派 | `12994: sub ip,r3,#1` / `cmp ip,#2` / `bls` | 只接受 flags ∈ {1,2,3}，否则 `ZR_ARGS`(0x10000) |
| memory 路 | `cmp r3,#3` → `beq 1280c` | **flags==3 才是 memory**（与我们常量表一致：HANDLE1/FILENAME2/MEMORY3） |
| 读循环 | `1285c: mov r2,#16384` / `12868: add r6,r6,r2` | `unzReadCurrentFile(uf, out, **16384**)`，**循环推进 out** |
| 收尾 | `12870: subs r5,r0,#0` / `bge` / `beq 128c0` | `res>0` ⇒ 继续；`res==0` ⇒ 关闭并返回 `ZR_OK`；`res<0` ⇒ 关闭返回 `ZR_WRITE`(0x400) |
| 文件路（flags 1/2） | `bl fopen@plt` / `bl fwrite@plt` / `bl fclose@plt` | 用 **stdio**；**没有** `EnsureDirectory`/`CreateFile`/`WriteFile`，**没有**目录项特判 |

**关键**：工厂**从不读 `len`** —— 其 wrapper 用 `ldr r3,[sp]`（flags）覆盖 r3 后尾跳到 `.part.7`，
而 `.part.7` 里 `len` 再未被使用。→ 调用方传 0 是**故意**的。

### 12.3 为什么判定为"真差异"而不是编译产物（三条独立证据）

1. 工厂 `UnzipItem`(`0x13040`) 把 `len`(r3) **原样转发**（`1309c: ldr ip,[sp,#16]` … `130a8: bl TUnzip::Unzip`），
   而**全部 15 个专有调用点都传 0** ⇒ 若工厂读 len，资源永远解不出来 ⇒ 与"真机能跑"矛盾。
2. 工厂 memory 路用**常量 16384**，不是任何入参。
3. 每个调用点都 `malloc(条目大小)` ⇒ **期待整块填充**（否则 malloc 那么大毫无意义）。

### 12.4 修复

`TUnzip::Unzip` 重写为与工厂逐分支一致：
memory 路 = `for(;;){ res=unzReadCurrentFile(uf,out,16384); out+=16384; if(res==0) break;
if(res<0){关闭;currentfile=-1;return ZR_WRITE;} }` → 关闭 → `ZR_OK`；
文件路改为 `fopen("wb")` + `fwrite` + `fclose`（去掉 Win32 文件 API 与目录创建）。

**顺带清掉 5 个「工厂没有的 C++ 符号」**（第 45 轮台账里的 ORPHAN 项）：

| 符号 | 处置 | 依据 |
|---|---|---|
| `_Z15EnsureDirectory` | 删除 | 工厂无此函数（其文件路不建目录） |
| `_Z12Uupdate_keys` / `_Z13Udecrypt_byte` / `_Z7zdecode` | 删除 | 加密簇，工厂整块删除；`zdecode` 只在注释里被提及 |
| `_Z6ucrc32` | 删除，改绑 C 版 | 工厂只有一个**未 mangle** 的 `ucrc32`（`@0xfff4 size=0x15c`，`callers=1` = `unzReadCurrentFile`）；那份已由专有层 `FUN_0000fff4_ucrc32.c` 1:1 重建 ⇒ 用 `asm("ucrc32")` 绑到 C 符号（与 `zopenerror` 同一手法） |

⇒ C++ ABI 门禁从 **「0 不一致 / 独有 5」** 变为 **「0 不一致 / 独有 0」**（完全干净）。

### 12.5 验证（机器码 + 调用方分配）

| 检查 | 结果 |
|---|---|
| 5 个独有符号 | **全部消失** ✓ |
| 我们 `unzReadCurrentFile` 的调用 | `{ucrc32×2, luf/fseek×1, fread×1, memcpy, uidiv, inflate}` ⇒ **`bl ucrc32` 与工厂一致** ✓ |
| 我们 Unzip 的 memory 路 | `mov r2,#16384` → `bl unzReadCurrentFile` → `add r5,r5,#16384` ✓ |
| 调用方缓冲安全 | 每个调用点都是 `malloc((ze_blob)._296_4_)`（= 条目大小）⇒ 整块填充正是它们期待的 ✓ |
| 尺寸 | 我们 `0x640` → **`0x550`**（工厂 `0x1c+0x1e8 = 0x204`；余差 = 内联 + 文件路栈帧） |
| 门禁 | 本地 8 道全 PASS；链接全局符号 **193/194**、越界 **0** |

### 12.6 教训（→ 技能铁律 121/122）

**参数对拍必须三层：存在性 → 个数/类型 → 语义（是否真的被使用）。**
本例二层全对（签名完全一致），三层却是致命的：工厂**不读** `len`，我们**读**了 ⇒ 静默零拷贝。
**这类缺陷没有任何现有门禁能抓** —— 签名对、尺寸同量级、调用点计数一致、覆盖率甚至还会上升。

### 12.7 ★ 运行期铁证（`CGM_DBGUNZ`，场景 E，env 门控探针）

机器码核对之后，再加一道**运行期**证据 —— 在 `mui_LoadUIResource` 里、`UnzipItem` 之后
统计目标缓冲的前 64 KiB（字节和 / 非零字节数 / 首 8 字节）：

```
DBGUNZ req=setting.raw size=2857048 sum=6830339 nz=65512 head=50 00 00 00 00 05 d0 02
```

| 字段 | 值 | 判读 |
|---|---|---|
| `size` | 2,857,048 | 与 zip 元数据一致（调用方 `malloc` 的大小） |
| `nz` | **65,512 / 65,536** | **99.96% 的字节非零** ⇒ 缓冲区**真的被写满了** |
| `sum` | 6,830,339 | 非零校验和 |
| `head` | `50 00 00 00 00 05 d0 02` | `0x50` = `'P'`，`setting.raw` 的真实头部 |

**对照修复前**：同一探针若在旧构建上跑，必然是 `sum=0 / nz=0`（`unzReadCurrentFile(...,0)` 零拷贝）。
⇒ 这是"零拷贝缺陷已修"的**直接运行期证据**（而不只是机器码推断）。

**行为也随之前进**：场景 E 的重建侧 stdout **21 → 22 行**（工厂 23 行），
四个场景的门禁仍是 A/B/C PASS、E FAIL(1)。

### 12.8 修 CI 时踩到「续行链」的**第二种**破坏形态（已做成 lint 判据）

给场景 E 追加 `CGM_DBGUNZ=1` 时，我把它追加到一行**已经以 `\` 结尾**的行后面：

```yaml
  CGM_KEY2_SEED=1 … CGM_TRACE_ADDRS="…" \ CGM_DBGUNZ=1 \
    sh tools/ci_qemu_behav.sh … report/qemu_e || true
```

`\` 后面跟的是**空格**而不是换行 ⇒ shell 当**转义空格**处理 ⇒ 赋值词被切碎。
CI 运行时直接给出判决性一行：

```
_run.sh: line 3:  CGM_DBGUNZ=1: command not found
```

⇒ **真正的 `sh tools/ci_qemu_behav.sh` 根本没执行**（`report/qemu_e` 整目录缺失、
所有探针为空、制品从 256 文件掉到 192），而该 step 因 `|| true` **仍显示 ✓**。

**修法**：环境变量必须加在**最后一个 `\` 之前**，不是行尾之后。
**门禁加固**：`tools/lint_workflow_continuation.py` 增加判据 ② ——
`(?<!\\)\\[ \t]+[A-Za-z_]\w*=` 且该行**以 `\` 结尾** ⇒ 判失败（负向后顾排除字面反斜杠）。
自证从「1 坏 + 4 好」扩到「**2 坏 + 6 好**」；**修之前该判据命中了这一行（exit 1）**，修完 0 问题。

⇒ 两种形态现在都被硬门禁覆盖：① 注释插进链中（第 44 轮）；② 链尾被追加内容（第 46 轮）。

---

## 十三、第 47 轮：**「调用点缺原型」= ABI 级错位**（阻塞 M7 的那一个）+ `fontscale` 类型错

### 13.1 缺陷 D1：调用点缺原型 ⇒ 实参按默认提升传 ⇒ `r0` 根本没被设置

**修复前现场（场景 E，我们侧）**：
```
pc = stbtt_FindGlyphIndex+0x8     指令 5045ae0: ldr r4,[r0,#4]   ← info->data
lr = stbtt_GetCodepointBitmapBoxSubpixel+0x2C   （= 50477a8，紧随 bl stbtt_FindGlyphIndex）
故障地址 = 0x4     r0 = 0x00000000
```

**根因链（全部有机器码对照）**：

| # | 事实 | 证据 |
|---|---|---|
| 1 | `proto.h` 里**没有** `stbtt_GetCodepointBitmapBoxSubpixel` / `stbtt_MakeCodepointBitmapSubpixel` / `stbtt_GetCodepointHMetrics` 的原型 | `grep stbtt_ src/compat/proto.h` 只有 3 条 |
| 2 | 于是走 **隐式声明** ⇒ 默认实参提升：`float` → **double** | 我们机器码 `vcvt.f64.f32 d0,s0` |
| 3 | double 落进 d0/d1/d2，而真函数按 `s0..s3` 读 float ⇒ **整组错位** | 工厂同一调用点：`vmov.f32 s0,s1` / `s2` / `s3` |
| 4 | 指针实参 `font` 被排到第 5 个位置 ⇒ **`r0` 从未被赋值** | 我们：`mov r0,r8` 之前 r0 无人设置；工厂：`1bc2c: mov r0,r5`(=&font) |
| 5 | 被调者入口 r0 = 0 ⇒ `ldr r4,[r0,#4]` 故障地址恰为 **0x4** | 崩溃现场 `r0=0x0`、故障地址 `0x00000004` |

★ 关键教训：`GetCodepointBitmapBoxSubpixel` 内部 `bl stbtt_FindGlyphIndex` 之前**没有重新加载 r0**
（`5047794: mov r6,r0` 之后一路沿用）⇒ **"崩溃点的 r0"就等于"调用者传的 font"**。
所以"故障地址 0x4"不能只解释成"上层指针为空"，而应优先怀疑**调用点 ABI 错位**。

**同一轮还发现一个错原型**：`extern float stbtt_ScaleForPixelHeight(float param_1, void *param_2);`
—— 真签名是 `(const stbtt_fontinfo *info, float height)`，**顺序与类型都是反的**。
本例因"一浮点一指针"的寄存器位置恰好互补而侥幸无害，但同类声明一旦有两个同类型参数就会致命。

### 13.2 缺陷 D2：`fontscale` 应是 `float`，我们写成了 `unsigned int`

| | 工厂 | 我们（修复前） |
|---|---|---|
| 写 | `1b288: vstr s0,[r5,#672]`（**按 float 存** scale） | `vcvt.u32.f32 s0,s0` → `vstr`（**截断成整数**再存）|
| 读 | `1b29c: vldr s14,[r5,#672]` → `vmul.f32` | 按 float 读，但里面已是整数 |
| 后果 | 正确的缩放系数 | scale 恒 <1 ⇒ 截断为 **0** ⇒ 字形缩放与 baseline 全丢 |

⇒ 判定方法：**看工厂对该地址的取存指令**（`vldr/vstr/vmov` ⇒ float；`ldr/str`+`vcvt` ⇒ int）。
Ghidra 标的 `undefined4` **不代表类型**，必须回到指令。

### 13.3 顺手补一处漏声明

`proto.h` 有 `shmget`/`shmdt` 却**漏了 `shmat`**（调用点 `(gh_u4 *)shmat(shmid,(void*)0,0)`）。
两侧 ELF 都导入 `shmget/shmat/shmdt` ⇒ 调用是**忠实**的，只是原型漏了（返回类型被假定 `int`）。
ARM32 上 int/pointer 同为 32 位而侥幸无害，但同类漏声明一旦涉及 float 或 64 位返回值就是 ABI 级错误。

### 13.4 新门禁（第 13 道 ★）：`tools/scan_implicit_decl.py` —— **编译器真值**口径

为什么不用源码启发式：要维护 libc/上游/宏的巨型白名单，必然假阳性。
而**编译器的判断就是真值**：逐文件 `-fsyntax-only`，缺原型会以 **error** 形式出现。

- 措辞兼容：clang ≥16 是 `call to undeclared function`（默认 error），旧版是 `implicit declaration of function`。
- 自证（正负双向）：临时 TU 里未声明调用**必须被检出**；已声明调用**必须不被检出**。
- 台账棘轮：新增即失败；台账项消失只告警（防"源码已修、账未删"造成假红）。
- 首跑结果：**213 个文件 → 检出 1 个（`shmat`）** ⇒ 补掉后 **0 项**。
- 性能：串行 70s → 并行（`--jobs 4`）**20.5s**。
  ★ `--jobs 8` 在本机直接 `OSError [WinError 1455] 页面文件太小`（zig cc 单进程内存不低）⇒ 默认取 4。
- ★ **派生失败必须 FATAL**：绝不允许把"编译失败"当成"该文件无缺原型"（仪器静默降级的老坑）。

### 13.5 对既有结论的两处修正

1. **「`key2` 被覆写」的归因撤回**：场景 E 里工厂侧 `key2` 在**崩溃时仍是注入值**
   `50 4b 05 06 50 4b 07 08`（3 次 `key2 re-assert` 回读也都正确）。
   即"某处覆写了 key2"这个机制**在注入+重断言之后已不复现**。
2. **工厂 zip 查找失败的归因理由要换**：分支普查显示 `unzStringFileNameCompare` /
   `unzGetCurrentFileInfo` 命中 **0** ⇒ **遍历循环体零执行** ⇒ `unzGoToFirstFile` 返回非零。
   仍归因沙箱，但不再用"key2 是 0"作理由（key2 当时是正确的）。

### 13.6 修复后的验证（机器码形状与工厂对齐）

| 调用点 | 修复后我们 | 工厂 |
|---|---|---|
| `stbtt_ScaleForPixelHeight` | `mov r0,&font` → `bl` → **`vstr s0,[r9]`（float 直存）** | `mov r0,&font` → `bl` → `vstr s0,[r5,#672]` |
| `GetCodepointBitmapBoxSubpixel` | `r0=&font`、`r1=codepoint`、两个栈槽 ix0/iy0、r2/r3 传 ix1/iy1 指针 | 同形 |
| `MakeCodepointBitmapSubpixel` | `r0=&font`、`r1=output`、`r2=out_w`、`r3=out_h`、`[sp]=stride`、`[sp+4]=codepoint`、`s0=s1=scale`、`s2=s3=0` | 同形 |
| 全 ELF | 这些调用点前的 **`vcvt.f64.f32` 全部消失**；`fontscale` 存的 **`vcvt.u32.f32` 截断消失** | — |

严格配方复编：两个文件 **0 error**，`implicit-declaration` 告警 **0 条**；
本地 8 道门禁复跑全绿（链接 193/194、越界 0）。

---

## 十四、第 47 轮实证：**M7「菜单存活」首次达成**（只有我们）

### 14.1 里程碑矩阵（场景 E，同一份 SD、同一 shim、同一 qemu）

| ID | 里程碑 | 工厂 | **我们** | 控制组 |
|---|---|---|---|---|
| M5 | `main_Menu` 入口 | ✓ | ✓ | ✓ |
| M6 | UI 资源包打开 | ✓ | ✓ | ✓ |
| **M7** | **菜单存活** | ✗ | **✓（首次）** | ✗ |
| — | 崩溃 | **SIGSEGV (139)** | **0 次崩溃** | SIGSEGV |
| — | `exit_code` | 139 | **124（= 超时被杀 ⇒ 一直活着）** | 139 |
| — | 专有函数覆盖 | 51 / 223 | **68 / 223** | 51 / 223 |
| — | A/B/C 场景 | — | **无回归**（48、48、6） | — |

### 14.2 我们是"活着"还是"死循环"？—— 三条否定证据

1. stdout **23 行，无重复自旋**（唯一重复是 `====...` 分隔线，本就出现两次）。
2. 末行停在 `Microsoft Vmbus HID-compliant Mouse 045e 0621 1 js0 Opened!` ⇒ **输入设备初始化完成**。
3. io 轨迹显示 `open /dev/input/js0`（rc=3）、`fopen /proc/bus/input/devices`（rc=0）、
   `fopen joystick.zip`（rc=0）⇒ 正常走到**等待输入**（沙箱里没有输入事件，菜单停在这里是预期行为）。

### 14.3 缺陷 D1/D2 修复的**实证效果**（修复前后同场景对比）

| | 修复前 | 修复后 |
|---|---|---|
| 崩点 | `stbtt_FindGlyphIndex+0x8`（故障地址 0x4） | **无崩溃** |
| stdout | 22 行 | **23 行（与工厂持平）** |
| 专有函数覆盖 | 58 / 223 | **68 / 223** |
| 新增覆盖（我们独有执行） | — | `ReadJoystick` / `ReadJoystickProc` / `ReadUSBJoy` / `GetInputInfo` /
| | | `GetJoystickConfig` / `mui_ReadJoystick` / `mui_WaitNMI` / `dispFlip` / `Mp3DecodeLoop` 等 18 个 |

⇒ 一个"缺原型"就让整条**字形渲染 → 菜单绘制 → 输入初始化**链路全断；补齐后一次性贯通。

### 14.4 场景 E 门禁现在的失败**方向**（必须标注，否则会被误读）

```
[FAIL] B1 exit_code       139 vs 124
[FAIL] B2 events          可判定前缀 46/59 行一致；重建侧共 55 行
[PASS] B3 new_files / B4 changed_files / B5 log_sha / B6 frame_hash / B7 shm / B8a sfc_cmds / B8b sfc_faults
```

★ **方向**：参照侧 `exit=139`（崩溃）、重建侧 `exit=124`（存活到超时）⇒ B1/B2 的失败**不是我们的缺陷**，
而是**参照侧**在沙箱里因环境缺口提前死亡。B5 `menu.log` 哈希两侧**完全相同**、B8a/B8b 的 SFC 命令数与
寄存器访问次数**逐项相同**，说明沙箱内的确定性部分仍然一致。
（仪器已升级：`behav_diff.py` 在"参照侧崩、重建侧存活"时输出 `方向：重建侧更健康` 并给结论加 `△ 疑似参照侧环境缺口` 标记。）

### 14.5 剩余差异（执行集合差集：仅我们 18 / 仅工厂 1）

- 仅我们 18 个：输入子系统（`ReadJoystick`/`ReadUSBJoy`/`GetInputInfo`/`GetJoystickConfig` 等）、
  `dispFlip`、`Mp3DecodeLoop`、`mui_WaitNMI`、`mui_outputxy_t`/`mui_DispBlock`、`UnzipItem`…
  —— 全部是**工厂因崩溃而没走到的路径**。
- 仅工厂 1 个：`ClearBuffer`（已定案 = **内联 vs 外联**，尺寸多重集逐项相同）。
⇒ **E 场景的差集现在全部可由"参照侧提前崩溃"解释**，不再有指向我们的可疑项。

### 14.6 下一轮入口

1. E 场景已"我们更健康"，需要**更深的场景**才能继续找真分歧：`F 场景`＝让菜单真正响应输入
   （shim 造 evdev 事件）→ 触发菜单切换/进入游戏（`dlopen` core）。
2. `TUnzip::Unzip` 余下尺寸差（我们 0x550 / 工厂 0x204）继续分解。
3. 真机对照（P6）：工厂在真机上是否也崩在 `mui_setting+0x114`？这决定"参照侧沙箱缺口"的最终定性。

---

## 十五、第 48 轮：**打开输入子系统**（场景 F）—— 这是 `mui` 57% 重构量的唯一入口

### 15.1 问题：场景 E 虽已"活着"，但卡在输入上

场景 E 达成 M7（菜单存活、exit=124 = 超时被杀、0 次崩溃）之后，stdout 停在
`... js0 Opened!` 再无动作。原因逐层查到最底：

| 层 | 事实 |
|---|---|
| shim | `redirect_dev()` 把 `/dev/input/*` 统一重定向到 `/dev/zero`（白名单见 `DEV_PREFIX`） |
| guest | `ReadUSBJoy()` 走 legacy joystick API：`access()` → `open(path, O_NONBLOCK)` → `read(fd,buf,8)` |
| 结果 | 从 `/dev/zero` 读回 **8 个零字节** ⇒ `type=0`（既非 `JS_EVENT_BUTTON(1)` 也非 `JS_EVENT_INIT(2)`）⇒ 函数直接 `return` 旧值 ⇒ **菜单永远收不到输入** |
| 代价 | `mui` 模块 **42 函数 / 70,396 B = 重构量 57%** 一次都没被驱动 |

### 15.2 做法：只改 `open` 一条路径（刻意不碰 `read`/`write`）

命中 `/dev/input/js<N>` 且启用注入时，不再重定向到 `/dev/zero`，而是造一个**内存 fd**
（`memfd_create`，退化路径 `/tmp/.cgi_js_events`），把事件字节流写进去、`lseek` 回 0 再返回。

⇒ **guest 侧读语义 100% 原生**（读到 EOF 返回 0），**不需要拦 `read`**，也就不会牵扯
stdio 内部（本项目已踩过"在被拦截的 stdio 函数里调用 stdio"的坑）。

**事件格式**（`struct js_event`，8 字节小端）：

| 偏移 | 字段 | 说明 |
|---|---|---|
| 0..3 | `time` (u32) | 时间戳（本注入填 0） |
| 4..5 | `value` (i16) | 按钮：1=按下 / 0=松开；轴：±32767 |
| 6 | `type` (u8) | 1 = `JS_EVENT_BUTTON`，2 = `JS_EVENT_INIT` |
| 7 | `number` (u8) | 按钮/轴编号 |

| 场景 F 注入 | 含义 |
|---|---|
| `0000000001000100` | value=1, type=1, number=0 ⇒ **按下 button 0** |
| 重复 4 次 | 读尽后 EOF ⇒ `ReadUSBJoy` 返回旧值 ⇒ 等价"**持续按住**"，配合 `ReadJoystick` 的 Delay 连发逻辑（`0x27` 次阈值）周期性产生按键 ⇒ 覆盖整个运行窗口 |

**顺带接管 `access()`**（guest 的 `.dynsym` 里确实导入了它，GLIBC_2.4）：
把"`/dev/input/jsN` 是否存在"从**宿主文件系统状态**变成**显式可控**，消除隐藏变量。

### 15.3 公平性与纪律（四条）

1. 两侧**共用同一份 shim** + **同一注入脚本** ⇒ 差分公平。
2. 只在 `CGM_INPUT_HEX` 非空时生效（**默认关**）—— 与其它探针同规矩；探针只出现在一侧就会污染行为门禁。
3. 场景 F 用 `|| true` 作**观测项**（工厂侧在沙箱里已崩，硬门禁会恒红无信息量）。
4. 导出符号已核对：`access` / `open` / `open64` / `openat` / `fopen` / `fopen64` / `mmap` /
   `munmap` **均已导出**；`read` **不在导出表内**（正是本方案的安全点）。

### 15.4 附带修掉两处（都属于"仪器可信度"）

| # | 问题 | 危害 | 处置 |
|---|---|---|---|
| ① | `behav_diff.py` 只打印 `门禁结果: FAIL`，读者无法看出**失败方向** | 场景 E 的 FAIL 是"参照侧崩、重建侧存活"，极易被读成"重建侧退步" | 新增**方向标注**：`方向：**重建侧更健康**：参照侧 exit=139 疑似异常终止，重建侧 exit=124（超时被杀 ⇒ 一直运行）` + `△ 疑似参照侧环境缺口` |
| ② | shim 的 key2 探针文案写着**旧的**注入值（`PK\x05\x06 PK\x06\x06`，第 42 轮修正前） | 现场读到 `50 4b 05 06 50 4b 07 08` 时，读者会误判"注入没生效/被覆写"，而实际是**完全一致 ⇒ 未被覆写** ⇒ **误导性证据** | 文案改为动态口径并写明两种世界的期望值 |

⇒ 方向标注已用**真实制品**本地验证：E 场景出标注、A 场景（PASS）不出标注。

### 15.5 下一轮入口

1. **读场景 F 的首跑数据**：注入是否生效（两侧各一行 `js 输入注入已启用`）、
   是否出现 `open(js-inject)` 轨迹、`mui` 模块覆盖率是否从 0 起来、里程碑是否有新动作。
2. `print_info`（我们的实现里 `spi_printf("%s %04x %04x %x js%d Closed/Opened!")` 的 `%s`
   被 Ghidra 渲染成地址 `0x3e16a4`）—— 顺手核对两侧该字符串常量是否同址同文。
3. `cores/` 目录里**没有 `.so`**（只有 `config.xml`/`filelist.xml`）⇒ "进入游戏 → `dlopen` core"
   在沙箱走不通；若要走通需给 `golden/sdcard_min/cores/` 补一个 stub `.so`（新议题）。

### 15.6 下一轮入口已侦察：**stub core**（把观测窗口从"菜单"推进到"进游戏 + libretro 交互"）

**为什么需要**：场景 F 让菜单能接收输入，但 `golden/sdcard_min/cores/` 里**只有 `config.xml` 与
`filelist.xml`，没有任何 `.so`** ⇒ 一旦菜单选中游戏并启动，`dlopen` 必然失败，路径到此为止。
而 `libemu_*` 的加载与交互（`Core_Load` / `Load_Proc1` / `Load_Proc2` + libretro 回调）
是**完全未覆盖**的一块。

**`Core_Load` 的完整契约**（源码 `src/proprietary/core/FUN_002b6f58_Core_Load.c`，900 B）：

| 步骤 | 内容 | 必需性 |
|---|---|---|
| 配置 | `sprintf(cfg, "%s/cores/%s.cfg", work_path, param_2)` → `get_items_from_file()` | 缺文件应可容忍（`corecfg` 先 `memset` 0） |
| 加载 | `sprintf(path, "%s/cores/%s", work_path, param_2)` → `dlopen(path, RTLD_NOW=2)` | **必需** |
| 支持性 | `dlsym("retro_is_support")` → `(*f)(rom)`；返回 <0 则 `dlclose` 并退出 | 可选（不存在则跳过） |
| 手柄类型 | `dlsym("retro_set_controller_port_device")`，从 cfg 读 `device0_type`/`device1_type` | 可选 |
| 载入 | `dlsym("retro_load_game")` → `(*f)(&game_blob)`；**返回值 0 ⇒ unload+deinit+dlclose** | **必需** |
| 后续 | `run_process("retro_set_progress_callback", progress)`；返回非 0 时 `Load_Proc2()` + `video_driver_set_rotation(0xFF00)` | — |
| `Load_Proc2` | `dlsym("retro_get_region")`（**必需**，缺则 return）、`dlsym("retro_run")`、`dlsym("SetFrameSkip")` | 部分必需 |

**⇒ stub core 的最小导出集**（交叉编译成 armhf `.so`，几百行 C 即可）：

```
retro_load_game(void *game) -> int      /* 必须返回非 0，否则被 dlclose */
retro_get_region(void)      -> int      /* Load_Proc2 里缺它就直接 return */
retro_run(void)             -> void     /* 主循环每帧调用 ⇒ 这是覆盖 libretro 交互的入口 */
retro_unload_game / retro_deinit / retro_set_progress_callback /
retro_set_controller_port_device / retro_is_support / SetFrameSkip   /* 可选，用于探测分辨率 */
```

**★ 红线与做法**（必须先定，否则会污染对照环境）：

1. `golden/sdcard_min/` 是**带 `MANIFEST.sha256` 的原厂只读拷贝** ⇒ **绝不能**往里面加文件
   （会破坏"原厂完整性"这一前提，也会让 `B3 new_files` 判据失去意义）。
2. 正确做法：在 CI 的 **stage 阶段动态生成** stub core 并放进 `/sdcard/cubegm/cores/`，
   且**两侧使用同一份**（差分公平）。
3. **`new_files` 口径已核实（第 48 轮查证）**：`behav_capture.sh` 的 `new_files` = 
   "`CGM_WORK`(= `/sdcard/cubegm`) 下相对**前置快照**新增的文件"，而前置快照是在
   **stage 之后、guest 运行之前**拍的（`ci_qemu_behav.sh` 的 `run_side()` 先铺环境再采集）。
   ⇒ 只要 stub core 在 **stage 阶段**放入且两侧一致，它就**不会**进 `new_files`。
   ⚠ 反向注意：探针本身若改动 work 目录，必须跑在**独立一遍**里（否则前置快照被污染，
   该维度静默失效 —— 这一条已在 `ci_qemu_behav.sh` 的注释里记为实测事故）。
4. `retro_run` 是空实现的话，`Load_Proc2` 之后会进入 `ReadJoystickThread` 的主循环 ⇒
   与场景 F 的输入注入**天然衔接**，可看到"按键 → 切菜单 → 进游戏 → 核心运行"的完整链路。

**编译配方（已本地验证）**：

```
zig cc -target arm-linux-gnueabihf -shared -fPIC -nostdlib -O1 -fno-unwind-tables \
       -o libemu_stub.so tools/guest_shim/stub_core.c
```

| 校验项 | 结果 |
|---|---|
| `e_machine` / `e_flags` | `0x28`(EM_ARM) / **`0x05000400`**（与工厂、设备基准逐位一致） |
| 导出符号 | 11 个（含 `retro_load_game` / `retro_get_region` / `retro_run` 等全部必需项） |
| **未定义符号** | **0 个（完全自洽）** —— `-fno-unwind-tables` 消掉了唯一的 `__aeabi_unwind_cpp_pr0` |
| `.gnu.version_r` | 不存在 ⇒ **零版本化依赖**（不触碰 GLIBC ≤2.7 红线） |

★ 附带观察：`factory.rkgame.bin` 的 `DT_NEEDED` **含 `libgcc_s.so.1`**（其 `__aeabi_unwind_cpp_pr0/pr1`
为 UND），而我们的 `rkgame.rebuilt.elf` **一个 `aeabi` 符号都没有** —— 编译器差异（GCC 走 libgcc_s
unwind，clang/zig 静态化）；功能上无影响（两侧都不做 C++ 异常传播），但值得记一笔：
**`DT_NEEDED` 集合也是保真度的一个维度，目前没有任何门禁覆盖它**（候选：新门禁）。

**预估价值**：覆盖 `Core_Load`/`Load_Proc1`/`Load_Proc2`/`run_process` +
`processvblank`/`dispFlip` 主循环 + libretro 交互 ≈ 26 函数 / 15 KB，且是**唯一**能验证
"核心加载 ABI"（`retro_is_support`/`save_state`/`load_state`/`set_unzip`/`set_progress_callback`
这套定制 ABI）的场景。

### 15.7 ★ 场景 F 首跑结论 + **一次我自己引入的事故**（诚实记录）

#### (a) 注入生效了 —— 但它只改变了"设备枚举"，还没驱动菜单逻辑

| 观测项 | 场景 E | **场景 F** | 判读 |
|---|---|---|---|
| `[shim] js 输入注入已启用` | — | **两侧各一行**（32 字节 / 4 个 js_event） | 注入装配成功 |
| `open(js-inject)` 轨迹 | — | 我们侧 **js0/js1/js2/js3 各一次**（fd=3/5/8/11） | ★ 行为确实被改变 |
| 工厂侧 `open(js-inject)` | — | **无** | 工厂在 E 就已经崩了，走不到输入初始化 |
| 我们侧 stdout 行数 | 23 | **25**（多出 `js1/js2/js3 Opened!`） | 前进 2 行 |
| 专有函数覆盖率 | 68 / 223 | **68 / 223（未变）** | ⚠ 没带来新代码覆盖 |
| 里程碑 M0–M7 | M7 ✓ | **同样是 M7 ✓（无新增）** | ⚠ 未进入新阶段 |

**读法**：E 场景下我们只打开 **1 个** js 设备（`access("/dev/input/jsN")` 只有 js0 通过）；
F 场景接管 `access` 后 **4 个全部返回可读** ⇒ `ReadUSBJoy(0..3)` 依次打开 4 个设备。
**这是注入生效的直接证据**，但也暴露一个设计副作用：

> ★ **`access` 接管过宽** —— 我让它对所有 `/dev/input/jsN` 都返回 0，
> 于是 guest 认为 4 个手柄都在线。真实设备上没插的手柄应当 `access` 失败。
> **下一轮应把注入限定到指定编号**（例如只让 `js0` 可读，或由 `CGM_INPUT_HEX` 带 N 位掩码），
> 否则"4 个设备都在线"本身就是一处与真机不符的偏差。

**为什么覆盖率没涨**（诚实说：不知道，需要下一轮查）：
候选解释 —— ① 注入的按键被 `ReadJoystick` 消费了，但菜单主循环尚未运行到处理按键的位置
（我们的 stdout 在 4 行 `Opened!` 之后就结束了）；② 按键位掩码未命中菜单使用的键码；
③ 按键只在启动瞬间注入一次，而菜单进入主循环更晚。
**下一步的判定实验**：让注入**周期性重复**（而非 4 次后 EOF）+ 延长 `CGM_TIMEOUT`，
看 stdout 是否出现菜单动作（如 `mui_setting`/`mui_DispBlock` 相关打印）与覆盖率跃迁。

#### (b) ★ 事故：**我引入了一个让三个场景静默失效的缺陷**

| 项 | 内容 |
|---|---|
| **症状** | CI 三 workflow 全 **success**，但 `qemu_b` / `qemu_e` / `qemu_f` 的 `behav_diff.txt` **末行全是** `json.decoder.JSONDecodeError: Invalid control character at: line 72 column 73` |
| **本质** | 这三个场景**判定根本不存在**，却看不出失败 —— "看起来在跑，其实没判" |
| **根因** | 我在第 48 轮改 key2 探针文案时写了 `PK\x05\x06`（**真转义**，C 里是 ENQ/ACK 字节）。`behav_capture.sh` 把 guest stderr 逐行收进 `behav_*.json`，而 **JSON 不允许裸控制字符**（除 `\t \n \r`）⇒ 采集的 JSON 非法 ⇒ `behav_diff.py` 抛异常 |
| **为什么 B 也中** | 场景 B 开了 `CGM_KEY2_SEED=1` ⇒ 必然打印该探针行 |
| **为什么没被立刻发现** | `ci_qemu_behav.sh` 里只 `echo "behav_diff 退出码 = $rc"`，**没有据此报错**；而场景 B/E 又是观测项（workflow 层 `|| true`） |

**修复（三件，都已落盘）**：

1. **文案改纯可打印**：`PK\x05\x06` → 十六进制文本 `50 4b 05 06`（同一信息，零控制字符）。
2. **新硬门禁（第 15 道 ★）**：`tools/check_shim_charset.py` —— 扫 shim 源码的**字符串字面量**，
   报出其中的真控制字符转义。**判据必须区分反斜杠奇偶**：
   `"PK\x05\x06"`（1 个反斜杠）= 真转义（危险）；`"PK\\x05\\x06"`（2 个）= 字面文本（安全）。
   构造性自证 1 坏 + 1 好，并做了**反向验证**（还原成真转义 ⇒ 精确命中那 2 处并 exit 1）。
   已接进 `1to1-verify`。
3. **仪器故障显式化**：`ci_qemu_behav.sh` 里 `behav_diff.py` 的约定退出码是
   `0=PASS / 2=FAIL / 3=INCONCLUSIVE`；**其它值一律 `::error::` + `exit 1`**。
   ⇒ 从此"仪器自己崩了"不会再被当成"场景通过"。

**这是本轮最有价值的一条教训**（已写进技能铁律 129）：

> **探针/日志的输出必须可安全序列化；且"仪器的崩溃"必须与"被测对象失败"分开显式化。**
> 否则最危险的假绿就出现了 —— 门禁报 success，而它**什么都没判**。

### 15.8 注入设施的两次改进（针对 15.7 暴露的两个问题）

#### (a) `access` 接管过宽 ⇒ 新增 `CGM_INPUT_JS` 限定在线编号

**问题**：第一版让 `access("/dev/input/jsN")` 对**所有** N 返回 0 ⇒ guest 认为 4 个手柄全在线
（实测 `open(js-inject)` 出现 js0/js1/js2/js3），而**真机只插 1 个手柄**
⇒ 这本身就是一处"与真机不符的假象"，会以"两侧一致"的形式混进差分。

**改法**：新增 `CGM_INPUT_JS`（默认 `"0"`，可写 `"01"` / `"0,1"`）⇒
只有列出的编号 `access` 成功，其余照常失败（等价于"该手柄没插"，guest 走它自己的分支）。
`open` 特判也同步按编号，避免两条路径口径不一致。

#### (b) 注入只覆盖"启动瞬间" ⇒ 新增 `CGM_INPUT_FILL` 循环填充

**问题**：第一版只给 4 个 `js_event`（32 B），而 `ReadUSBJoy` 每 15 ms 读 8 B
⇒ **32 字节在几毫秒内读尽**，之后 EOF、`joy_key_tmp` 保持最后值。
而菜单进入主循环通常要几秒 ⇒ **按键注入的时机过窗** ——
这很可能是"注入生效（设备都被打开）但覆盖率没涨"的原因之一。

**改法**：新增 `CGM_INPUT_FILL=<字节数>`，把事件流**循环填充**到该长度后再交给 guest。
场景 F 现用：一个"按下 + 松开"周期（16 B）+ `FILL=4096` ⇒ 256 个周期
⇒ 约 **7.7 秒**的按键活动（按 15 ms/次读算）⇒ 覆盖菜单初始化之后的窗口。

#### (c) 场景 F 现在的完整注入参数

```
CGM_INPUT_JS=0                 # 只 js0 在线（真机 = 插一个手柄）
CGM_INPUT_HEX=0000000001000100 0000000000000100   # 按下 button0 + 松开（一个周期）
CGM_INPUT_FILL=4096            # 循环填充到 4 KiB ⇒ 256 周期 ⇒ ~7.7 秒
```

**下一轮要看的三件事**：
1. 我们侧 stdout 是否出现**菜单动作**（不再是停在 4 行 `Opened!`）；
2. 专有函数覆盖率是否**从 68/223 起涨**（尤其 `mui` 模块）；
3. 里程碑是否出现 M7 之后的新阶段。

## 十六、第 49 轮 ★★★ 根因定案：**起始屏幕由 `menu.log` 头 4 字节决定** —— E/F「活着但不推进」的真因

### 16.1 现场三件套（互相印证）

| # | 观测 | 数据 |
|---|---|---|
| 1 | 我们侧**活着**（超时被杀） | `exit=124`；工厂 `exit=139`（确定性控制组复现） |
| 2 | 但覆盖率**恒定** | 专有函数 **68/223 = 30.49%**（字节 36,600/122,922 = 29.77%）；场景 E 与 F **完全相同** |
| 3 | 到底在跑什么 | exec 尾部：`mui_SoundplayThread` / `AudioProcess` / `PlaySound` / `GetTicks` / `usleep`；strace：`read(3,buf,8) = 8` + `clock_nanosleep` 循环 |

### 16.2 真因（源码级，单点）

`main_Menu`（`src/proprietary/mui/FUN_0002ce6c_main_Menu.c`）：

```c
DAT_003af26c = (m_menulog_blob)._0_4_;      /* ★ 起始屏幕 = menu.log 头 4 字节 */
uVar2 = (m_menulog_blob)._0_4_;
do { switch(uVar2) {
       case 0: mui_menu();     case 1: mui_type();   case 2: mui_recent();
       case 3: mui_shoucang(); case 4: mui_search(); case 5: mui_setting();
     } uVar2 = DAT_003af26c; } while(1);
```

`golden/sdcard_min/menu.log`（444 B）头 4 字节 = **`05 00 00 00` = 5** ⇒ 开机即进 `mui_setting()`；
而 `mui_setting` 只有把 `DAT_003af26c` 改写成别的值才返回顶层 ⇒ **整轮运行都驻留在「设置页」**。

**与覆盖率清单逐项吻合**：`mui_setting`(7096 B) **已执行 ✓**，而
`mui_menu`(3084) / `mui_search`(5712) / `mui_recent`(4792) / `mui_type`(4740) / `mui_shoucang`(3888)
**全部未执行**（五个屏幕函数合计 **26,216 B ≈ 21% 重构量**）。

⇒ **这不是缺陷，是"停在设置页轮询"**。把 `main_Menu` 的 `switch` 找出来，比盲注入按键有效得多。

### 16.3 输入注入**已端到端验证**，但注入的按键**语义无效**（假阴性）

| 验证项 | 证据 |
|---|---|
| 事件被真读到 | strace：`read(3,0x40ffed0c,8) = 8` |
| 只开 js0（掩码生效） | strace：`access("/dev/input/js1",R_OK) = -1 errno=2`（js2/js3 同） |
| 填充生效 | shim：`js 事件流填充：16 B -> 4096 B（256 个周期）` |
| 在线掩码 | shim：`js 在线掩码 = 0x1（CGM_INPUT_JS='0'）` |
| 确实打开了设备 | shim：`io #16 open(js-inject) rc=3 /dev/input/js0`；stdout `... js0 Opened!` |

**但**：注入的是 `number=0`，而 `joystick.zip/ui.cfg` 的扫描码矩阵（**真值源**）显示 **0 = SELECT**：

| 按键号 | 0 | 1 | 2 | 4 | 8 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|
| 动作 | SELECT | DOWN | UP | LEFT | START | RIGHT | A | B |

SELECT 几乎不改变菜单状态 ⇒ **输入生效、语义无效**。这类"注入了却什么也没驱动"的假阴性，
**只能靠"键位映射真值源"排除** —— 否则会误判成"注入设施没做好"而去乱改设施。

### 16.4 本轮新查证的资源事实（全部带字节数）

| 资源 | 大小 | 条目 / 结论 |
|---|---|---|
| `ui_cn.zip` | 4,951,281 B | `ui.cfg`(242) / `menu.raw` / `search.raw` / **`setting.raw`(2,857,048)** / `type.raw` / `game.raw` —— ★ **没有 `font.ttf`**（`font.ttf` 是顶层文件 1,840,376 B）⇒ 两侧那句 `find font.ttf in ui_cn.zip fail` 是**正常回退**，不是缺陷 |
| `joystick.zip` | 332,110 B | `0000_0000`(107 B = 26 动作词表) / `joystick.raw` / `ui.cfg`(215 B = 2×27 扫描码矩阵) / 4 个 USB 手柄 profile |
| `cores/filelist.xml` | 8,654 B | **真实游戏列表（非空）**，如 `002/Targa (Europe) (Proto).zip` → `libemu_snes9x.so` |
| `cores/config.xml` | 3,822 B | 核心注册表（`.so` 本体不在沙箱 ⇒ 仍需 stub core，见 15.6） |
| `font.ttf` | 1,840,376 B | 顶层真实字体（**不是缺失**） |
| `menu.log` | 444 B | 头 u32 = 起始屏幕 = `5` |

### 16.5 我们侧严格优于工厂的两处（运行期证据）

| 侧 | stdout 关键行 |
|---|---|
| 工厂 | `find ui.cfg in /sdcard/cubegm//ui_cn.zip fail` ＋ `find setting.raw fail` ← **zip 里明明有这两项** |
| 我们 | `DBGUNZ req=setting.raw size=2857048 sum=6830339 nz=65512 head=50 00 00 00 00 05 d0 02` ← 尺寸与 zip 元数据**逐字节一致** |

⇒ 我们的 zip 查找 / 解压路径**正确**；工厂在沙箱里失败（控制组复现 `exit=139` ⇒ 环境归因，非我们的缺陷）。

### 16.6 本轮新增两个场景（G / H）+ 修掉一处差分公平缺陷

| 场景 | 唯一变量 | 与谁严格单变量 | 目的 |
|---|---|---|---|
| **G** | `CGM_MENULOG_SCREEN=0`（**只改 `menu.log` 头 4 字节**，其余 440 B 原厂原样） | vs **E**（探针集完全相同） | 归因「起始屏幕」⇒ 打开 `mui_menu` 分支 |
| **H** | G ＋ `CGM_INPUT_HEX`（DOWN 按下/松开 ＋ A 按下/松开，32 B 周期）＋ `CGM_INPUT_FILL=4096` | vs **G** | 归因「输入」⇒ 驱动菜单交互 |

实现：`tools/stage_sdcard_env.sh` 新增 `CGM_MENULOG_SCREEN=<0..5>`（**默认关**；两侧共用同一份；**宿主侧**铺环境，不需要 `-E` 转发）。
本地干跑三情形已验证：未设 → 保持 `05 00 00 00`；设 0 → 头 4 字节变 0 且**其余 440 B 与原厂逐字节一致**；设 9 → `FATAL` 且 `rc=1`。

★ **修正的缺陷（我自己引入）**：场景 E 开了 `CGM_DBGUNZ=1`、F 没开 ⇒ E vs F 的 stdout 差异里混进了
**"探针行有无"**这个非行为变量，使一次注入副作用被误读成需要两轮排查。已给 F 补上 `CGM_DBGUNZ=1`。
**教训**：跨场景对比的前提是「除目标变量外完全一致」——**探针集本身也是变量**。

### 16.7 下一轮要看的三件事（按信息量排序）

1. **G**：`mui_menu` / `mui_do_file_list` 是否被覆盖（破 5 个屏幕函数的第一道）；
2. **H**：是否出现**屏幕切换**（`mui_type`/`mui_recent`/`mui_shoucang`/`mui_search` 任一）；
3. **覆盖率是否从 68/223 起涨**（且**必须与 E 同口径**比较，勿拿波动当进度）。

### 16.8 ★★★ 场景 G/H 首跑结果（回答 16.7 的三问）

| 16.7 的问题 | 结果 |
|---|---|
| G：`mui_menu` / `mui_do_file_list` 是否被覆盖 | **✓ 是，两者首次执行**（见下表"新增 2"） |
| H：是否出现屏幕切换 | ✗ 否（H 相对 G 新增 **0** 个） |
| 覆盖率是否起涨 | ✗ **68 → 59**（净 -9）—— 原因见下，**不是退步** |

| 场景 | 专有函数覆盖 | M7 菜单存活 | 我们侧 exit | 门禁 |
|---|---|---|---|---|
| E / F | 68/223 = 30.49% | ✓ | **124**（活着） | FAIL(2) ＋ 方向=重建侧更健康 |
| **G** | **59/223 = 26.46%** | ✗ | **139（崩）** | FAIL(1) |
| **H** | 59/223 = 26.46% | ✗ | 139（崩） | FAIL(1) |
| 工厂（G/H） | — | ✗ | 139（崩） | — |

`menu.log` 注入证据：`MENULOG_INJECT screen=0 file=/sdcard/cubegm/menu.log size=444` × **6 次**（3 侧 × 探针+采集）✓

**E → G 的集合变化（精确）**

- 新增 2：`mui_do_file_list`、`mui_menu`
- 消失 11：`mui_setting`、`ReadUSBJoy`、`ReadJoystick`、`ReadJoystickProc`、`GetJoystickConfig`、
  `GetInputInfo`、`mui_ReadJoystick`、`mui_WaitNMI`、`mui_outputxy_t`、`dispFlip`、`get_from_line`

⇒ **68→59 是"换了一条更早就崩的路径"，不是退步**：`mui_setting` 那条链里含**整个摇杆轮询循环**
（`ReadJoystickProc→ReadJoystick→ReadUSBJoy` ＋ `mui_ReadJoystick` ＋ `mui_WaitNMI`）与字体渲染
`mui_outputxy_t`；换成 `mui_menu` 后链在 `mui_do_file_list` 里**立刻崩**，轮询根本没机会跑。

★ **重要副产品（修正了场景 F/H 的设计前提）**：**摇杆轮询循环位于 `mui_setting` 内，不在 `main_Menu` 顶层**
—— `main_Menu` 只是 `switch(menulog[0])` 的分派器。这就是 H（在 `mui_menu` 上注入方向/确认键）新增 0 个函数的机制解释。

### 16.9 ★★★ 新崩溃的根因：`/sdcard/root.dat` 缺失（**环境缺口，非缺陷**）

- 崩溃现场（我们侧 stderr）：`io #16 fopen rc=-1 /sdcard/root.dat` →
  `真崩溃 pc=0x05006430 lr=0x003b24a4 r0=0x00000000`，故障指令 `0xe5d50000` = **`ldrb r0,[r0]`**
- pc 归属（读重建 ELF 的 `.symtab`；**链接基址 `0x05000000`**）：
  **`mui_do_file_list + 0xf0`**（起始 `0x05006340`，大小 1500 B）
- 工厂反编译 `decompiled/02-ghidra-c/00_rkgame_ALL.c:19268-19285`：

```c
if (DAT_003af2ac == (void *)0x0) {
    sprintf(acStack_490,"%s/root.dat",root_path);              /* root.dat 是 ZIP 包 */
    hz = OpenZipU(acStack_490,0,2);
    if ((hz==0) || (zr=FindZipItemA(hz,"fileinfo.txt",1,&local_498,ze), zr!=0)) {
        RARCH_LOG("find %s fail!\n",acStack_490);             /* ← 失败：DAT_003af2ac 保持 NULL */
    } else { DAT_003af2ac = malloc(ze._296_4_ + 1); UnzipItem(...); }   /* ← 只有成功才赋值 */
}
...
iVar2 = mui_do_file_list(iVar11, DAT_003af2ac);                /* ← 把 NULL 当第 2 实参传进去 ⇒ 崩 */
```

- **我们侧 `mui_menu` 与工厂逐行同构**（含 `DAT_003af2ac = (void *)0x0;` 与失败分支不赋值）
  ⇒ **两侧同一故障形态**（工厂 G/H 亦 `exit=139`）
- `golden/sdcard_min/fileinfo`（49 B）= `"0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"`（25 个 `0,`）
  = **`root.dat` 内 `fileinfo.txt` 的来源**
- ⇒ **判定：沙箱缺 `/sdcard/root.dat` 这一外部输入所导致，不是我们的实现缺陷。**
  判据：① 两侧同一故障形态（同一条 `ldrb r0,[r0]`、r0=0）；② 崩溃发生在"依赖外部文件的失败分支之后"。

### 16.10 本轮新增场景 I（补 `/sdcard/root.dat`）

| 场景 | 唯一变量 | 与谁严格单变量 |
|---|---|---|
| **I** | G ＋ `CGM_ROOTDAT=1`（合成 `/sdcard/root.dat` = `ZIP{fileinfo.txt ← golden/sdcard_min/fileinfo}`） | vs **G** |

实现要点（`tools/stage_sdcard_env.sh`）：

1. 目标路径 `$(dirname "$WORK")/root.dat` = **`/sdcard/root.dat`** —— 在 `CGM_WORK` **之外**
   ⇒ 不进 `new_files` / `changed_files` 维度（不会污染 B3/B4）；
2. ★★ **开关缺省时显式 `rm -f`**：`/sdcard` 是跨场景共享的，残留会让"缺文件"的场景**静默变成"有文件"**
   —— 与场景 C 的 `stublib` 残留属同一类事故（"每个场景的输入必须完全由该场景自己的开关决定"）；
3. 内容取**原厂 49 B `fileinfo`**，不自行编造；
4. 本地干跑三情形已验证：未设 → 无残留；设 1 → 合法 ZIP（129 B）且 `fileinfo.txt` 与原厂**逐字节一致**；
   再未设 → **显式移除残留**（两分支都打明确提示）。

### 16.11 本轮修掉的三处**仪器/流程缺陷**（都是我自己引入或踩到的）

| # | 现象 | 根因 | 处置 |
|---|---|---|---|
| 1 | CI 监控连续 11 次打印「（无）」却不报错，差点误判"推送没触发 CI" | `actions/runs?head_sha=<12 位短 sha>` **静默返回空集** | 短 sha 先解析为全长；并把"空结果"与"查询失败"分开 |
| 2 | 场景 E 开 `CGM_DBGUNZ=1`、F 没开 ⇒ E vs F 差异 **不可归因** | 跨场景对比时**探针集也是变量** | 给 F 补 `CGM_DBGUNZ=1` |
| 3 | `cp` 出来的"改动前"备份，内容却等于"改动后"；幂等断言在自身刚改过的文件上误报"已存在" | **提权重试会让整条命令"从头再执行一遍"** ⇒ 副作用执行两次 | 补丁脚本一律写**幂等**；`cp`/`mv` 这类破坏性前置步骤尤其注意 |

### 16.12 ★★★ 场景 I 首跑：补上 `root.dat` 使覆盖 **59 → 76**（历史最高），并暴露下一缺口

| 指标 | E/F（此前最好） | G/H | **I（补 root.dat）** |
|---|---|---|---|
| 我们侧**专有函数**覆盖 | 68/223 = 30.49% | 59/223 = 26.46% | **76/223 = 34.08%** |
| 我们侧覆盖函数（全 ELF） | 216/1661 | 189/1661 | **225/1661** |
| 我们侧覆盖字节（.text） | 121,344 / 692,288 | 102,592 | 120,704 |
| M7 菜单存活 | ✓ | ✗ | **✓ 恢复** |
| 我们侧 exit | 124（活着） | 139（崩） | **124（活着）** |
| 工厂侧专有函数覆盖 | 52/223 | — | 52/223 |

**I 相对 G：新增 17 个 / 消失 0 个**；且 `exec_set_diff` 报 **"仅工厂执行 = 0 个"**
⇒ **我们的执行集合已是工厂的超集**（这是目前最强的保真度信号）。

新增的 17 个：输入链全套（`ReadUSBJoy` / `ReadJoystick` / `ReadJoystickProc` / `GetJoystickConfig` /
`GetInputInfo` / `mui_ReadJoystick` / `mui_WaitNMI`）＋ 渲染链（`mui_outputxy_t` / `dispFlip` /
`get_from_line`）＋ 7 个 mui 函数（`mui_DisplayGameSum` / `mui_DisplayLine_t` / `mui_DisplayThumbnail` /
`mui_UnDispBlock` / `mui_Undisplay` / `mui_extract_basename` / `mui_extract_basepath`）。

★ **新缺口（已定位到行）**：stdout 反复出现 `open /sdcard//.dat fail`。来源
`src/proprietary/mui/FUN_00014f84_mui_DisplayThumbnail.c:40-42`：

```c
mui_extract_basepath(puVar4, &file_info_list + DAT_003af27c * 0x404, 0x80);
mui_extract_basename(auStack_2d8, &file_info_list + DAT_003af27c * 0x404, 0x80);
sprintf(acStack_258, "%s/%s/%s.dat", root_path, puVar4, puVar4);
```

`mui_extract_basepath` = 取 `strrchr(0x2f)` **之前**的部分；没有 `/` ⇒ **空串** ⇒ `/sdcard//.dat`。

### 16.13 `fileinfo.txt` 的**真实格式**（真值源，逐条读出）

`mui_do_file_list`（`FUN_000186a4`）的解析循环：

| 环节 | 事实 |
|---|---|
| 分隔符 | `,`(0x2c) / `;`(0x3b) / `\n`(10) / `\r`(13) |
| 每项处理 | `libiconv`(GB2312→utf-8) → `mui_extract_basepath` → **`strtol(local_8c, NULL, 10)`** |
| ⇒ 约束 | 首段（目录名）必须是**十进制数字**，即每项形如 `NNN/<文件名>` |
| 可得真值源 | `golden/sdcard_min/cores/filelist.xml` 的 `name="002/xxx.zip"` —— 正是该形态 |

⇒ 场景 I 用的 `golden/fileinfo`（49 B = 25 个 `0`）**不成立**（无 `/` ⇒ basepath 空 ⇒ `/sdcard//.dat`）。
新工具 `tools/make_rootdat.py --mode filelist` 从 `cores/filelist.xml` 提取 **135 个 `name=`**，
首项 `002/Targa (Europe) (Proto).zip`、末项 `000/bayroute.zip`（含 `/` 且首段为数字 ✓）。

### 16.14 新增场景 J + `CGM_ROOTDAT` 两口径

| 取值 | 含义 |
|---|---|
| `CGM_ROOTDAT=1` | 旧口径：`fileinfo.txt` ← `golden/fileinfo`（**已实测不成立**，保留作对照） |
| `CGM_ROOTDAT=2` | **真值源**：`fileinfo.txt` ← `cores/filelist.xml` 的 `name=` 列表（`,` 连接） |

新场景 **J** = 场景 I 的 `CGM_ROOTDAT` 由 1 改 2，其余（`CGM_MENULOG_SCREEN=0` / 探针集 / 超时）完全一致
⇒ **I vs J 严格单变量**，可直接归因到 `fileinfo.txt` 的内容。

### 16.15 又一处仪器可移植性缺陷（已修）

`_TOOLS="$(cd "$(dirname "$0")" && pwd)"` 在 Git Bash 下给出 `/d/...` 形式，交给 **Windows 版
`python.exe`** 会被解释成 `D:\d\...` ⇒ `No such file or directory`（本地实测；CI 上是 Linux 不受影响）。
⇒ 改用**相对路径** `_TOOLS="$(dirname "$0")"`；并加 `python3 → python` **解释器回退**
（本机只有 `python`、CI 只有 `python3`），找不到两者则 `FATAL`（不让它静默不产出）。

本地端到端干跑（走 stage 脚本本身）已全绿：`=1` → 129 B / 25 项；`=2` → 1156 B / **135 项**；
`=7` → `FATAL` + `rc=1`；未设 → 无残留；与 `CGM_MENULOG_SCREEN=0` 组合时 `menu.log` 头 4 字节仍为 0。

### 16.16 ★★ 场景 J 的**否证**：`fileinfo.txt` 的内容对当前路径**零影响**

| 场景 | `root.dat` 大小 | `fileinfo.txt` 内容 | `/.dat fail` 行数 | 专有函数覆盖 | M7 | exit |
|---|---|---|---|---|---|---|
| I | 129 B | 25 个 `0`（旧口径） | 29 | 76/223 | ✓ | 124 |
| **J** | **1156 B** | **135 个 `filelist` 路径**（真值源） | **29（未变）** | **76/223（未变）** | ✓ | 124 |

严格核对：**I 与 J 的覆盖函数集合逐项完全相同**（76 ≡ 76，双向差集为空）；两侧 stdout 仅内存行不同。
⇒ **`fileinfo.txt` 的内容不被当前路径消费** —— `root.dat` 的作用只是"**让 `DAT_003af2ac` 非 NULL**（不崩）"，
与内容无关。这是本轮最有价值的**否证**：它排除了一个看似合理的假设，把下一步钉到真正的填充路径上。

**真因在另一条填充路径**：`src/proprietary/misc/FUN_0002142c_dir_serial_list.c:69`（readdir 扫目录）：

```c
pcVar4 = strcpy(&file_info_list + iVar3, pdVar8->d_name);          /* 直接拷目录项名字 */
*(gh_uint *)(pcVar4 + 0x100) = (gh_uint)(*ppdVar7)->d_type;        /* 并记录 d_type */
```

而沙箱 `/sdcard/cubegm/` 顶层**没有 `000/`–`008/` 游戏目录**（只有 `cores/` 一个子目录）
⇒ `dir_serial_list` 扫不到游戏目录 ⇒ `file_info_list[i]` 里没有 `NNN/xxx.zip` 这类项
⇒ `mui_extract_basepath` 取不到 `/` ⇒ basepath 空 ⇒ **`/sdcard//.dat`**。

**`cores/filelist.xml` 的目录分布（= 下一轮的合成目标，已精确到项数）**

| 目录 | 项数 | 例 | 对应核心（filelist 内） |
|---|---|---|---|
| `000` | **105** | `kof96.zip`、`1944.zip` | fba / fbafast / cps2 / fbalpha2012 / extend |
| `002` | **21** | `Targa (Europe) (Proto).zip` | `libemu_snes9x` / `libemu_snes9x2010` |
| `004` | **9** | `Rockman Zero4.zip` | `libemu_mgba` |

共 **135 项 / 3 个目录**。★ 附带发现：`libemu_fbafast.so` 被 `filelist.xml` 引用，但 `cores/config.xml`
**未注册**（config 注册 18 个核心、filelist 只用到 8 个）。

⇒ **下一轮的可执行目标（已量化）**：新增 stage 开关 `CGM_GAMEDIRS=1`，按上面 3 个目录名合成
`/sdcard/cubegm/000|002|004/` ＋ 按 `filelist.xml` 的 `name=` 造占位游戏文件（135 个，零内容即可）
⇒ 让 `dir_serial_list` 能列出它们 ⇒ basepath 非空 ⇒ `NNN/NNN.dat` 缩略图包路径成立。
两侧共用同一份、且在 pre 快照之后不含它 ⇒ 不影响 B3/B4。

### 16.17 场景 K：合成 `NNN/` 游戏目录 + 占位游戏文件（针对 `dir_serial_list`）

| 项 | 内容 |
|---|---|
| 开关 | `CGM_GAMEDIRS=1`（新）；缺省时**显式 `rm -rf` 清理**残留 |
| 工具 | `tools/make_gamedirs.py`（读 `cores/filelist.xml` 的 `name=`） |
| 产出 | **3 个目录 / 135 个占位文件**：`000/` 105 项、`002/` 21 项、`004/` 9 项 |
| 占位文件内容 | **22 B 合法空 ZIP**（不是 0 字节）—— 它们是 `.zip`，被 `OpenZipU` 打开时"找不到条目"比"不是压缩包"噪声更小 |
| 自证 | 工具自身 `os.listdir` 断言 readdir 能看到 135 个条目（否则 FATAL） |

本地端到端干跑（走 stage 脚本）：未设 → 无 `NNN/`；设 1 → 3 目录/135 文件 + 自证通过；
与 `CGM_MENULOG_SCREEN=0` + `CGM_ROOTDAT=2` 组合 → 三者同时生效；再未设 → 分支执行并报"清理 3 个残留"。
（本机 `rm -rf` 被 safe-delete shim 拦，故目录删除未真正生效；分支与计数均正确，CI 无此 shim。）

**场景 K 的判据（关键）**：不看"覆盖率涨没涨"，而看**同一句日志的路径内容是否改变** ——
`open /sdcard//.dat fail` ⇒ 应变成 `open /sdcard/000/000.dat fail`。
理由：覆盖率会被别的因素抵消（G/H 就出现过"打开新函数但总数下降"），而"路径里的 basepath 是否非空"
是**单点可判定**的，不受其他因素干扰。

### 16.18 本轮（第 49 轮）净产出汇总

| 类别 | 数量 | 明细 |
|---|---|---|
| 新场景 | +4 | G（起始屏幕）/ H（+输入）/ I（+root.dat）/ J（fileinfo 真值源）/ K（+游戏目录） |
| 新设施 | +4 | `CGM_MENULOG_SCREEN` / `CGM_ROOTDAT=1|2` / `CGM_GAMEDIRS` / `_PY` 解释器回退 |
| 新工具 | +2 | `tools/make_rootdat.py` / `tools/make_gamedirs.py` |
| 定案根因 | 3 | 起始屏幕 / `root.dat` 缺失 / `dir_serial_list` 为空 |
| 否证 | 1 | `root.dat` 的内容零影响（I ≡ J） |
| 修的缺陷 | 6 | 见上表（短 sha 静默空集 / 探针集不一致 / 重试双执行 / 路径形式 / 语法 / 残留） |
| 技能铁律 | 129 → 136 | 新增 134/135/136/137 |

### 16.19 ★★★ 闸门定案：`DAT_003af394`（每屏列表项数）—— 场景 I/J/K 三次「零变化」的统一解释

**证据链（逐条可复核）**

| # | 证据 | 来源 |
|---|---|---|
| 1 | 场景 K 注入生效（`GAMEDIRS_BUILT dirs=3 files=135` × 6），但 `.dat` 仍 `/sdcard//.dat`、覆盖仍 76/223、**K vs J 差集 = 0（双向）** | `qemu_art73/qemu_k/*` |
| 2 | **strace 里没有任何目录扫描**（无 `opendir`/`getdents`），只有文件 open | `probe_stderr_rebuild_strace.txt` |
| 3 | `dir_serial_list`（唯一的 readdir 填充者）**只被 `mui_setting` 调用**（`callers=1`）；而 G/H/I/J/K 起始屏幕都是 0（`mui_menu`）⇒ **扫描从未发生** | `grep dir_serial_list` |
| 4 | 所有列表循环的统一上界 = `DAT_003af394`，只在 `mui_LoadConfig` 赋值 | 见下 |

```c
get_value_from_items("GameList_count",local_128,configitems,uVar2);
if (local_128[0] == ' ') { DAT_003af394 = 0xb; }             /* 缺字段 ⇒ 默认 11 */
else { __isoc99_sscanf(local_128,"%d",&DAT_003af394); }       /* 格式串 DAT_002dcf4c = "%d" */
```

| 5 | `golden/ui_cn.zip/ui.cfg`（242 B）只有 `[Setting]` / `Recover*` ⇒ **`GameList_count` 缺字段** | `unzip -l` + 全文 |
| 6 | **场景 J 已证 `fileinfo.txt` 内容零影响** ⇒ 解析循环体被跳过 ⇒ 只可能是 `DAT_003af394 == 0` | 场景 J |

⇒ **`DAT_003af394 == 0` 是 I/J/K 全部「零变化」的统一机制**：它是 `mui_do_file_list` / `dir_serial_list` /
`mui_menu` / `mui_type` / `DisplayPage_list` 里**每一个**列表循环的上界；为 0 时 `file_info_list`
与 root.dat 的 `fileinfo.txt` 都不会被消费 ⇒ 缩略图路径退化成 `/sdcard//.dat`（实测 29 行）。

**理论到此无法再推 ⇒ 上探针**（本项目纪律：推不动就上仪器）：
新增 `CGM_DBGCFG=1`（env 门控、只在重建侧 stdout、只在场景 L 启用），
在 `mui_LoadConfig` 的 `GameList_count` 之后打印 `DAT_003af394` / `local_128` / `root_path`。

**场景增删**：新增 **L**（= J + 探针，严格单变量）；**删除 K 步骤**（结论已定案，保留每轮白烧 ~3 min CI）。

### 16.20 ★ 本轮被「排除」的输入（负面清单，避免以后重复试）

| 已排除的输入 | 证据 | 结论 |
|---|---|---|
| `root.dat` 是否存在 | I vs G：59 → 76（+17） | ✅ **有效**（唯一有效的） |
| `root.dat` 的 `fileinfo.txt` 内容 | I vs J：逐项相同 | ❌ 零影响 |
| `NNN/` 游戏目录是否存在 | K vs J：差集 0、无目录扫描 | ❌ 零影响（因闸门为 0，扫描根本没发生） |
| 起始屏幕 = 0（`mui_menu`） | G vs E：打开 `mui_menu`+`mui_do_file_list` | ⚠️ 有效但会让 `dir_serial_list` 无法被调用（它只在 `mui_setting`） |


### 16.21 ★★★★ sysroot 差异的**单一根因** = `libkms.so.1`（且历史覆盖率是"缺件口径"）

**证据链**
1. `tools/build_libkms_stub.sh` 头部自述：*"CI 沙箱里 `/arm-root` 有 libdrm.so.2 / libasound.so.2，
   **唯独缺 libkms.so.1** ⇒ `dlopen(/sdcard/cubegm/driver.so)` 失败"*；
   而 `tools/ci_qemu_env.sh` 的运行时元件校验清单（`ld-linux / libc / libm / libz / libstdc++ /
   libgcc_s / libdl / libpthread / libdrm / libasound`）**恰好没有 `libkms`** —— 校验通过 ≠ 元件齐全。
2. 本轮新建的 `golden/device_rootfs_min/`（设备真实 rootfs 最小集）**包含 `libkms.so.1`**
   （`usr/lib/libkms.so.1.0.0`，实测设备 rootfs 里存在）。
3. 三种口径的实测对照：

| 口径 | `libkms.so.1` | `driver.so` | 深度 | 我们侧覆盖率 | 里程碑 |
|---|---|---|---|---|---|
| `/arm-root`（Ubuntu jammy） | **缺** | `dlopen` 失败 | 跳过 DRM | **48/223**(A) / **76/223**(J) | M5 ✓ |
| **CI 场景 C**（jammy + 桩） | 有（桩） | 加载成功 | 进 DRM 后崩 | **6/223** | M3/M4 ✓ M5 ✗ |
| **`/arm-root-device`**（设备真实） | **有（原生）** | 加载成功 | 进 DRM 后崩 | **6/223** | M3/M4 ✓ M5 ✗ |

⇒ **设备 sysroot ≡ jammy+桩 ≡ CI 场景 C**：三者逐项一致（7/6/223、`exit=139`、同一崩溃点）。

**结论（影响此前的全部结论）**
- 历史所有「48/223、68/223、76/223」都是 **`driver.so` 根本没加载**这个缺件口径下的数字
  ⇒ 它们不是"设备上会发生的事"，**不能当作交付判据**。
- 设备真实路径是"**加载 `driver.so` → 走 DRM/KMS → 在 DRM 处止步**"。
- 因此"提高覆盖率"的正确方向不是继续在 jammy 缺件口径下加场景，而是
  **让 shim 把 `/dev/dri/card0` 的 DRM/KMS 交互仿真出来**，使执行流越过 DRM 到 `main_Menu`。

**下一轮唯一入口（已定，可执行）**
在 `tools/guest_shim/fake_mem.c` 里新增 **DRM/KMS 设备仿真**（env 门控开关，默认关、两侧共用）：
- `open("/dev/dri/card0" | "/dev/dri/renderD128")` → 内存 fd（不落 `/dev/zero`）
- 新增 `ioctl` 拦截（shim 目前**没有**导出 `ioctl`），应答 `DRM_IOCTL_VERSION` /
  `DRM_IOCTL_GET_CAP` / `DRM_IOCTL_SET_CLIENT_CAP` / `DRM_IOCTL_MODE_GETRESOURCES` /
  `DRM_IOCTL_MODE_CREATE_DUMB`（返回假 handle/stride/size）/ `DRM_IOCTL_MODE_MAP_DUMB`（返回假 offset）
- `mmap` 该 offset → 匿名零页（复用 `fake_mem.c` 已有的 mmap 拦截路径）
- 判据：设备 sysroot 下 `M4 DRM 显示` 不再是"打印失败即算到达"，而是**真的越过 DRM**
  ⇒ `M5 main_Menu 入口 ✓`，覆盖率从 6/223 明显上升，且两侧仍同步。
- 前置：`sh tools/build_libkms_stub.sh report/stublib`（**必须给 outdir 参数**，
  否则脚本只打印 usage 就退出 ⇒ 开关空转，本轮就是这样白跑一次）。


### 16.22 ★★★★★ 突破：桩 `libdrm.so.2` 让厂商 driver.so 的图形初始化通过 ⇒ **全里程碑贯通**

**问题（gdb 实测的崩溃现场）**
```
[shim] pc = driver.so + 0x3ca8   符号 = gr_init
[shim] lr = libc.so.6 + 0x41e44
栈回溯: driver.so + 0x6378 video_drivers_init / +0x6360 video_drivers_init / rkgame + 0x3a9fc4
故障指令 = ldr r3,[r3]   (r0..r3 = 0 ⇒ NULL 解引用)
```
⇒ 设备真实 rootfs **有** `libkms.so.1` ⇒ `dlopen(driver.so)` 成功 ⇒ 进 `gr_init`，
而沙箱无真 DRM 设备 ⇒ 真 libdrm 的 ioctl 全失败 ⇒ `gr_init` 拿 NULL ⇒ **必崩在厂商代码里**。
⇒ 历史 48/68/76 覆盖率是 `driver.so` **没加载**才走到的 —— 不是真机路径。

**做法**：`tools/build_libdrm_stub.sh` 造桩 `libdrm.so.2`（`tools/guest_shim/drm_stub.c`），
覆盖 `driver.so` **实测引用的全部 17 个 `drm*` 符号**（符号集逐字取自其 65 个未定义符号），
并把 `driver.so` 实际用到的 `snd_*`（20 个）留给真 `libasound`。
- 所有返回结构**完整初始化**的静态对象；`Free*` 全部 no-op（指针指向静态存储，free 会毁堆）
- `drmIoctl` 按 `_IOC_NR` 分派，**不猜结构体尺寸**（CREATE_DUMB 的 `size` 位置按 `_IOC_SIZE` 判定）；
  未知 DRM 命令**零填**整个参数缓冲后返回 0 —— 既确定，也不把未初始化结构体交给被测程序
- 假 dumb 偏移 = `0x10000000`（≥4 MiB）⇒ 命中 shim 既有"共享+可写+偏移≥4MiB ⇒ 匿名零页"规则，**不引入新机制**
- `-nostdlib` + 自带 `memset`（`visibility("hidden")`，不导出）+ `-fno-unwind-tables`
  ⇒ **0 未定义符号**、`e_flags=0x05000400`、`SONAME=libdrm.so.2`

**实测（SYSROOT=`/arm-root-device` 设备真实 glibc 2.29 + `CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1`）**

| 里程碑 | factory | rebuild | control |
|---|---|---|---|
| M0 进程启动 / M1 配置 / **M2 SPI-SFC** / **M3 driver.so** / **M4 DRM** / **M5 main_Menu** / **M6 UI 资源包** / **M7 菜单存活** | 全部 ✓ | **全部 ✓** | 全部 ✓ |
| 覆盖率 | 47/223 = 21.08% | **52/223 = 23.32%** | — |
| 终止 | exit=134 (SIGABRT) | exit=134 | exit=134 |

- 对照（不加 drm 桩）：7/6/223、崩在 `gr_init` ⇒ **单变量可归因**
- ★★ **本项目第一次在设备真实路径上 M0–M7 全通，且我们侧覆盖率（52）> 工厂侧（47）**
- 两侧终止码一致（exit=134）⇒ 差分公平

**下一个瓶颈（已抓到实证，下一轮唯一入口）**
```
rkgame: pcm.c:3009: snd_pcm_avail: Assertion `pcm' failed.
```
⇒ vendor `driver.so` 调 `snd_pcm_avail` 时 pcm 为 NULL（假硬件没有声卡）⇒ `abort()`。
**下一轮**：镜像本轮的机制造桩 `libasound.so.2`，覆盖实测的 **20 个 `snd_pcm_*`**
（`open/hw_params_*/prepare/start/writei/avail/drop/close/recover/sizeof` 等），
把 ALSA 初始化也做成"成功"，让执行流越过这次 `abort`。

**操作坑（本轮踩到两次，已记）**
- `CC_ARM="<zig> cc"` **必须带 `-target`**，否则 zig 按**宿主**编译 ⇒
  `lld-link: undefined symbol: _DllMainCRTStartup`（症状与病因完全无关，易误读成"缺 memset"）
- 传给 native Windows 版 `zig.exe` 的路径必须 `cygpath -w`，否则报
  **`error: CacheCheckFailed`**（同样是误导性症状）
- `build_libkms_stub.sh` / `build_libdrm_stub.sh` **必须给 outdir**，否则只打 usage 就退出 ⇒ 开关空转


### 16.23 ★★★★★ 桩 `libasound.so.2`：rebuild 覆盖率 52 → 73（+40%），且**不再崩溃**（超时存活）

**问题（实证）**
```
rkgame: pcm.c:3009: snd_pcm_avail: Assertion `pcm' failed.
```
`pcm.c` 是 **alsa-lib 的源文件** ⇒ 这句来自**真实 libasound**，断言 `pcm != NULL`：
假硬件上 `snd_pcm_open()` 失败 ⇒ driver.so 未检查返回值就继续用 NULL 句柄 ⇒ `abort()`。
**与 DRM 完全同型** —— driver.so 的每个硬件后端都必须"做成成功"。

**做法**：`tools/guest_shim/alsa_stub.c` + `tools/build_libasound_stub.sh`，
覆盖 `driver.so` 实测引用的**全部 20 个 `snd_*`**（符号集逐字取自其 65 个未定义符号）。

| 设计点 | 取值 | 为什么 |
|---|---|---|
| 引用面普查 | **只有 driver.so 引用 `snd_*`**（工厂 rkgame / 重建 elf / icube 均 0）| 整体替换 `libasound.so.2` 不影响任何其它模块 |
| `snd_pcm_hw_params_sizeof` | 返回 **256**（真实约 192~208）| 类型是 opaque ⇒ driver.so 必须运行时调它来分配缓冲；偏大 ⇒ 误差方向保守 |
| `hw_params` 私有布局 | 只用缓冲**前 32 字节** | 无论 driver.so 分配多大都不越界 |
| 入参为 NULL | **一律不解引用** | driver.so 正是在"没检查 open 失败"的路径上传 NULL；桩的职责是让流程走下去，不是复刻断言 |
| 产物自证 | SONAME=`libasound.so.2`、**UND=0**、`e_flags=0x05000400`、**20/20 覆盖** | 零运行时依赖（自带 hidden memset）|

**严格单变量实测**（同容器 / 同 sysroot=`/arm-root-device` / **同开关集 J**，唯一变量 = `CGM_ALSA_STUB`）

| 组 | ALSA 桩 | factory | **rebuild** | 终止 f/r/c | M7 菜单存活 f/r/c |
|---|---|---|---|---|---|
| `dv_x` | 关 | 47/223 | **52/223** | 134 / **139**(SIGSEGV) / 134 | ✓ / **✗** / ✓ |
| `dv_y` | **开** | 52/223 | **73/223 = 32.74%** | 139 / **124**(超时) / 139 | ✗ / **✓** / ✗ |
| Δ | | +5 | **+21（+40%）** | 崩溃 → **存活** | ✗ → **✓** |

- ★★ **rebuild：52 → 73 专有函数（+21），终止码 139(SIGSEGV) → 124(超时存活)**
  ⇒ **不再崩溃，菜单活着跑满 30 s 超时**（124 是"活着"的判据，与场景 E/F 的 `exit=124` 同型）
- ★ **设备真实 sysroot 口径下覆盖率新纪录（73/223 = 32.74%）**，且首次 **rebuild(73) > factory(52)**
- ★ M6 两侧一致（`✓(包已打开(条目缺失))`）⇒ 桩**未破坏** UI 资源包路径

**★ 必须同时记录的两件事（否则是自欺）**
1. **factory 侧在 ALSA 桩下反而退步**（M7 ✓→✗、`134`→`139`）⇒ 桩对两侧影响**不对称**，
   这是**新的分歧点**，下一轮必须诊断（怀疑 driver.so 的音频线程在工厂侧走了不同的同步路径；
   driver.so 确实引用 `pthread_create/cond_signal/mutex_lock`）。
2. **差分门禁仍 FAIL(2 项)** —— 两侧终止码不同（124 vs 139）。
   "终止码不同"本身可能是"我们活着、工厂崩了"，**不等于我们错**；但必须看清是哪 2 项、失败方向是什么。

**★ 本轮实验的设计缺陷（已修正，记账）**
第一次跑 `dv_alsa` 时**漏了 `CGM_KEY2_SEED`** ⇒ M6 必然 ✗、与历史 52/47 不可比 —— 当时误判为"ALSA 桩帮倒忙"。
补回**完整同一开关集**后才得到可归因的单变量结论。
⇒ **纪律：任何"与历史数字对比"的实验，必须先逐字复刻历史那一组的完整开关集（含旁路注入），否则不是单变量。**

---

**★ CI 侧交叉验证（`f2bed039`，20 steps 全 ✓；job `105906364634`）**

| 口径 | sysroot | 桩 | 旁路注入 | factory | rebuild | M6/M7 | 终止 |
|---|---|---|---|---|---|---|---|
| CI 场景 C（既存） | jammy | libkms | — | 7 | 6 | ✗/✗ | 139 |
| CNB `dv_alsa`（**漏 KEY2**） | device | 三桩 | — | 50 | 48 | ✗/✗ | 139 |
| **CI 场景 C4**（本轮新增） | **device** | 三桩 | — | **50** | **48** | ✗/✗ | 139 两侧一致 |
| CNB `dv_y` | device | 三桩 | **J 口径** | 52 | **73** | ✓/✓ | 124(f) / 139(f) |
| **CI 场景 C5**（本轮新增） | device | 三桩 | J 口径 | 待首跑验证 | 待首跑验证 | — | — |

- ★★ **CI/C4 与 CNB `dv_alsa` 逐位一致（50/48、M6 ✗、exit=139）** ⇒ 差分结论**跨平台可复现**
  （Ubuntu runner + `arm-linux-gnueabihf-gcc` vs Debian 13 容器 + zig）
- ★ 三桩在 CI 侧同样自证通过（`SONAME` 正确、`UND=0`），且**换了编译器**（gcc 而非 zig）
  ⇒ 桩的**编译器无关性**得到独立验证
- ★ CI 侧设备 sysroot 建立成功：`文件数=25`、`ld.so OK`、`libc OK`、`GNU C Library (Buildroot) 2.29`
- ★ 场景 C5（与本地 `dv_y` **逐字同口径**）的职责 = 给出 **73/223 的跨平台可复现证据**

**★ 本轮实验设计缺陷之二（已修，记账）**
- C4 最初**漏了 `CGM_KEY2_SEED`** ⇒ `ui_cn.zip` 打不开 ⇒ M6 必然 ✗、**测不到"桩把执行流推了多深"**；
- C4 的"终止码"输出为空 —— `grep exit=` 打到了不含该字段的 `coverage_*.txt`（应打 `milestones.txt`）。

**★★ CI 场景 C5 的裁决（`3a652872` / run `35447258006`）—— 核心结论跨平台复现**

| 项 | CNB `dv_y`（Debian13 + zig） | **CI 场景 C5**（Ubuntu + gcc） | 一致性 |
|---|---|---|---|
| factory 覆盖率 | 52/223 | **52/223** | ✓ 逐位一致 |
| rebuild 覆盖率 | 73/223 = 32.74% | **76/223 = 34.08%** | +3（抖动 2.6%，方向保守） |
| M6（f/r/c） | ✓/✓/✓ | ✓/✓/✓ | ✓ |
| M7（f/r/c） | ✗/✓/✗ | ✗/✓/✗ | ✓ |
| 终止码（f/r/c） | 139/**124**/139 | 139/**124**/139 | ✓ |
| stdout 行数（f/r） | 29 / 1871 | **29 / 1874** | ✓ |
| 差分方向自判 | 重建侧更健康 | 重建侧更健康 | ✓ |
| 唯一里程碑差集 | M7 | M7 | ✓ |

- ⇒ **除 rebuild 覆盖率有 ±3 个函数的抖动（2.6%）外，其余全部逐位一致**
  （含 M7 差集、终止码三元组、两侧 stdout 行数量级、差分工具的自判方向）
- ⇒ ★★ **设备真实路径下的覆盖率（76/223 = 34.08%）追平了此前 jammy 口径的历史最高 76/223**
  —— 而那个数是 `driver.so` **没加载**的假路径得到的。**现在这个 76 是在真机路径上拿到的。**
- ⇒ ★ 「rebuild `exit=124`（超时存活）vs factory `exit=139`（崩）」这一**判决性差异在两种环境下完全一致**

### 16.24 ★★★ 仪器口径缺陷修正：M7「菜单存活」的旧判据产生过**假绿**

**缺陷（一行代码）**
```python
marks["M7"] = bool(marks["M5"]) and ex not in (None, 139)   # 旧（tools/milestones.py:81）
```
只排除 `139`(SIGSEGV) ⇒ **把 `134`(SIGABRT) 也判成"菜单存活"**。

**实测后果（本轮亲历）**

| 场景 | factory exit | 旧判 M7 | 真相 |
|---|---|---|---|
| `dv_x`（无 ALSA 桩） | **134**（`pcm.c:3009: snd_pcm_avail: Assertion `pcm' failed.`） | **✓ 假绿** | 死于 ALSA 断言，根本没活着 |
| `dv_y`（有 ALSA 桩） | 139 | ✗ | 崩 |

⇒ 加桩后 factory 的 M7 从 ✓ 变 ✗，表面像"M7 在两侧之间来回交换"，
**实际是判据太宽**，把"被 abort 打死"误当"活着"。
（★ 我上一轮曾据此写"M7 判据不稳 / 待查" —— **那个判断是错的**，在此更正。）

**修正**
```python
marks["M7"] = bool(marks["M5"]) and ex is not None and ex < 128
```
依据 GNU `timeout` 语义：命令自身退出 → 原样返回其退出码；超时被杀 → **124**；被信号 N 杀死 → **128+N**。
⇒ `0` 与 `124` 算"活着"；`134/137/139` 等一律算"死"。
- 误差方向：任何 `128+N` 判 ✗（保守）；代价 = "进程用 exit(200+) 自行退出"会误判（罕见，可接受）
- `ex is None`（`behav_*.json` 缺失）判 ✗ —— **"本该产出的产物缺席"必须显式失败**，不得静默放行

**自证：新增 `python3 tools/milestones.py --selftest`（8 个锚点，全部人工核对，全绿）**

| exit | 到达 M5 | 期望 M7 | 锚点含义 |
|---|---|---|---|
| 124 | True | True | 超时被杀 ⇒ 一直在跑 ⇒ 活着 |
| 0 | True | True | 自行正常退出 |
| 1 | True | True | 自行以 1 退出（仍属"未被信号终止"）|
| **134** | True | **False** | **SIGABRT(ALSA 断言) —— 旧判据正是在此假绿** |
| 139 | True | False | SIGSEGV |
| 137 | True | False | SIGKILL |
| 124 | False | False | 没到菜单入口 ⇒ 不算存活 |
| None | True | False | behav json 缺失 ⇒ 仪器缺失必须失败 |

⇒ 加自证的理由：**这次缺陷是"人工肉眼看出来"的；仪器缺陷必须由锚点自证拦住，而不是靠人看。**

**连带修正**：M7 现在会带出**判定依据**（`✓(活着(exit=124))` / `✗(被信号终止(exit=134))`），
否则 "M7 ✗" 无法区分"被信号打死"与"压根没到菜单入口"——两者是完全不同的结论。

**⇒ 修正后的结论比修正前更强**：`dv_x` 两侧 M7 **全 ✗**；`dv_y` 只有 **rebuild ✓（唯一"活着"的一侧）**。

**★ 另一处已修的登记缺陷**：workflow 的 `upload-artifact` paths 漏了 `qemu_c4/` / `qemu_c5/`
⇒ 判决性场景跑完了却**拿不到 rundir 产物**（首跑只能靠 CI 日志里 echo 出来的摘要）。已补登记。

### 16.25 ★★★★★ 定位 rebuild「跑满超时」的真相 + 两侧第一个分歧点（精确到行）

**观测方法**：CI artifact（`run 35447258006`）+ CNB 同口径复跑 ⇒ 分析 `rundir_*/stdout.txt` 的**唯一行**结构。
（只比"最长公共前缀"看不见这类信息 —— 这是"执行集合差集"之外的第三种观测粒度。）

**① rebuild 的 1871 行 = 一个忙循环**

| 出现次数 | 行 |
|---|---|
| **1816** | `gr_blit: source has wrong format` |
| 29 | `open /sdcard//.dat fail` |
| 其余 25 行 | 各 1 次（初始化 / 内存 / 驱动 / ROM 打印） |

⇒ **`exit=124`（超时存活）不是"闲着"，而是 driver.so 的 `gr_blit` 因"source 格式错误"反复失败 ⇒ 忙循环 30 s。**
⇒ 归属已证：`gr_blit` 与 `Unknown format` 两句**只存在于 `driver.so`**（@0x69d8 / @0x6ac0），rkgame 里没有。

**② 两侧第一个分歧点 = 第 25 行**

唯一行清单**前 24 行完全相同**（含 `video_driver_setting 0 1 1` / `open drm!` / `Unknown format 875713089`）：

| 行 | factory | rebuild |
|---|---|---|
| 25 | `find ui.cfg in /sdcard/cubegm//ui_cn.zip fail` | *(无 —— **找到了** ui.cfg)* |
| 26 | `find font.ttf in … fail` | `find font.ttf in … fail` |
| 27+ | `find menu.raw fail` / `find /sdcard/root.dat fail!` ⇒ 崩 | **`gr_blit` ×1816** + `open /sdcard//.dat fail` ×29 |

- ★ **`Unknown format 875713089`(=0x34325241=AR24) 是两侧共有的**（driver.so 在 M4 的一次性警告）⇒ **不是分歧点**
- 真分歧仍是 `ui.cfg` 查找（GAP 583–605 已定案：我们正确、工厂失败）
- ⇒ rebuild 因拿到 ui.cfg 而**第一次走到菜单渲染**（`gr_blit`），工厂**从未走到**

**③ 下一瓶颈（明确、可执行）**

`gr_blit` 是 driver.so **内部**调用的（两个 rkgame 都不含该字符串）；
rkgame 的入口是 `video_driver_disp_frame` —— 通过 `dlsym` 取到后存入 BSS 全局：
```c
/* src/proprietary/hw/FUN_0000d678_InitDisplay.c:42 */
video_driver_frame = dlsym(handle,"video_driver_disp_frame");
/* 调用点 src/proprietary/hw/FUN_0000d8e4_dispFlip.c:43 */
gh_u4 ret = (*video_driver_frame)(param_1,param_2,param_3,param_4);
```
⇒ **下一步 = 对比 `dispFlip` 的 4 个实参**（尤其"帧数据指针 + 格式"那两个）与工厂在同一位置的传参。

**★ 我在本轮犯的一个仪器错误（记账，必须写）**

用正则 `[A-Za-z_][A-Za-z0-9_]{3,60}` 扫"两个 rkgame 里出现了哪些 driver.so 导出符号"，
得出"factory 多一个 `frame`、rebuilt 缺失" —— **假阳性**：`frame` 来自 factory 的
`-fomit-frame-pointer` 编译标志串（前后是 `-`，被分词切开）。
⇒ **教训：把"字符串包含"当"API 引用"必须精确分词（要求前后为非标识符字符），否则编译标志/注释串会污染结论。**
⇒ 用精确分词复核后：**两侧对 driver.so 的 API 字符串集完全一致（14 个）**，无保真度差异。

### 16.26 ★★★★★ 新 M7 判据下的**全场景矩阵**：跨两套 sysroot 口径的一致结论

CI `1e864b09`（run `35449551215`，21 steps 全 ✓）跑出新判据下的矩阵（每格都带**判定依据**）：

| 场景 | sysroot | 桩 | 旁路 | M3 driver.so | M5 | M6 | M7 factory | M7 rebuild | 差集 |
|---|---|---|---|---|---|---|---|---|---|
| `qemu` | jammy | — | — | ✗ | ✓ | ✗ | ✗(139) | ✗(139) | 空 |
| `qemu_c` | jammy | libkms | — | ✓ | ✗ | ✗ | ✗ | ✗ | 空 |
| `qemu_c4` | **device** | 三桩 | — | ✓ | ✓ | ✗ | ✗(139) | ✗(139) | 空 |
| **`qemu_c5`** | **device** | 三桩 | **J** | ✓ | ✓ | **✓** | **✗(139)** | **✓(124 活着)** | **M7** |
| **`qemu_j`** | jammy | — | **J** | ✗ | ✓ | **✓** | **✗(139)** | **✓(124 活着)** | **M7** |
| `qemu_m/n/o/p` | jammy | — | 各变体 | ✗ | ✓ | ✗ | ✗(139) | ✗(139) | 空 |

**⇒ 三条硬结论**

1. ★★ **两个"活着"的场景跨 sysroot 口径一致**：`c5`（device + 三桩 + J）与 `j`（jammy + J，driver.so 甚至**没加载**）
   都得到「**rebuild `124`(活着) / factory `139`(被信号终止)**」。
   ⇒ 这**不是环境偶然**，而是 **J 环境下的稳定现象**。
2. ★ **共同前提是 M6 ✓（UI 资源包打开）** ⇒ 能不能"活着"取决于 M6 是否成功；
   而 M6 之后 factory 因 `ui.cfg` 查找失败走了别的分支（**GAP 583–605 已定案：我们正确、工厂失败**）⇒ 被信号终止。
   ⇒ 与 16.25 的"第一个分歧点在第 25 行 = `ui.cfg`"**逐字吻合**。
3. ★ **新判据的信息增益**：旧判据会把 `qemu_j` 的 factory(`139`) 误判成 `M7 ✓`（制造"两侧都活着"的假象）；
   新判据直接印出 `✗(被信号终止(exit=139))` vs `✓(活着(exit=124))` ⇒
   **"谁活着、为什么"从"要靠人推断"变成"矩阵里直接可读"**。

### 16.27 ★★★★★ 逐层剥到 driver.so 内部：`gr_blit` 的"格式不匹配"判定与运行期实测值

**方法：三种观测粒度，全部零源码改动**
1. `rundir_*/stdout.txt` 的**唯一行**结构（见 16.25）
2. `arm-linux-gnueabihf-objdump -d --disassemble=<符号>`（driver.so **有符号**，导出 61 个）
3. gdb（`gdb-multiarch` + `dispFlip` **符号断点** + gdb-Python `stop()` 回调）读**运行期**实参与全局

**① 实参实测（断 `dispFlip`，采样第 1/3/50/200/1000/3000 次…）**
```
DF#1     w=1280 h=720 pitch=2560 data=0x45758008
DF#2000  w=1280 h=720 pitch=2560 data=0x45758008
全局      scrbuf=0x45758008  w=1280  h=720      ← 与实参完全一致
```
- `pitch / w = 2` ⇒ **16bpp（RGB565）**，与所有调用点的 `width << 1` 约定一致 ⇒ **参数没有错**
- 220 s 内命中 **13000+ 次**（≈59/s）⇒ **60fps 每帧渲染**，菜单确实在持续跑

**② `video_driver_disp_frame(data,w,h,pitch)` 的机制（反汇编）**
```asm
; 仅当 (w,h,pitch) 与内部结构 S 的 [0],[4],[8] 不一致时才【重建】：
  S->[0]  = w
  S->[4]  = h
  S->[12] = <某全局的值>        ← ★ 格式字段（懒初始化）
  S->[8]  = pitch
; 之后统一：
  S->[16] = data
  bl gr_next_frame@plt           ; 双缓冲切换
  bl gr_blit_b@plt(...)          ; ★ 实际被调用的是 gr_blit_b，不是 gr_blit
```

**③ `gr_blit_b` 的判定（反汇编）**
```asm
gr_blit_b(r0 = source):
  if (source == 0) return;
  r2 = (<全局指针 P>)->[12];
  r3 = source->[12];
  if (r2 != r3) { puts("gr_blit: source has wrong format"); return; }   ← 就是这一行
```
- `gr_blit`（无 `_b`）内有**逐字相同**的一段，但全库**没有对 `gr_blit` 的直接 `bl`**
  ⇒ **打印该消息的是 `gr_blit_b`**（第一次探针断在 `gr_blit` 上命中 0 次，正是因此）

**④ 运行期实测（在 `dispFlip` 断点内反推 driver.so 基址后读）**
```
vdf = video_driver_frame = 0x40a89590   ⇒ driver.so base = 0x40a83000
frame 全局(.bss@0x17220) = 0x5086ef0
frame->[12] :  第 1 次 = 12388（★ 脏值）  →  第 3 次起 = 2（稳定）
colormode    = 2   (.data@0x171a4)
gr_colormode = 0   (.bss @0x171b4)          ← ★ 两个"颜色模式"本身就不一致
rkgame 侧 Frame_data / Frame_width = 0      ← 另一套帧描述符（DrawFrame/core 回调用），未启用
```
⇒ **`frame->[12]` 存在"初始化窗口"**（12388 → 2）；且 `colormode=2` 与 `gr_colormode=0` **不一致本身就是线索**。

**⑤ 当前状态与下一步（明确）**
- **已排除**：`dispFlip` 的实参、rkgame 侧全局（scrbuf/w/h 三者一致、16bpp）
- **已确认**：不匹配发生在 **driver.so 内部**的 `gr_blit_b`（`P->[12]` vs `source->[12]`）
- **下一步**：解析 `gr_blit_b` 里 `P`（GOT@3964）与 `disp_frame` 里 `S->[12]`（GOT@67c8）**各自对应哪个符号**
  （候选只有 `frame` / `colormode` / `gr_colormode`），并确认**双缓冲**（`gr_next_frame`）
  是否使 `frame` 指向的 `[12]` 与 `source` 的 `[12]` 来自**不同缓冲**。

**★ 方法论增量（可复用，已写进记忆）**
- **gdb-Python 回调断点 + 符号反推 DSO 基址**：`base = video_driver_frame - 0x6590`
  （`video_driver_frame` 是 rkgame 的 BSS **函数指针**，由 `dlsym("video_driver_disp_frame")` 填入
  ⇒ 其值就是 driver.so 内该函数的运行地址）⇒ **无需 `stop-on-solib-events`**
  （实测该法在 `batch` + Python 循环下不可靠：会卡在首次 solib 事件并报
  `Cannot execute this command while the target is running`）。
- **`objdump -d --disassemble=<sym>`** 对付**有符号**的厂商 DSO 极有效；无符号时才需绝对地址。
- **绝对地址断点必须区分"文件 vaddr"与"运行时地址"**：`break *0xd8e4` 命中 0 次，
  而符号断点 `dispFlip` 命中 13000+ 次（该 ELF 的 `dispFlip` 实际在 `0x500387c`）。

### 16.28 ★★★★★ GOT 全解算：`S` = `frame`、`S->[12]` = `colormode` —— 并暴露一个必须解决的矛盾

**方法**：**纯静态**（Python 按 `PT_DYNAMIC` → `DT_REL` 解 `R_ARM_GLOB_DAT`，不依赖任何 ARM 工具链）
—— 因为容器被回收，反而发现"GOT 解算根本不需要设备/容器"。

**driver.so 的完整 GOT 表（0x17000–0x17200，26 项）**

| GOT 项 | 符号 | GOT 项 | 符号 |
|---|---|---|---|
| 0x17128 | `__cxa_finalize` | 0x17144 | **`frame`** ★ |
| 0x17130 | `mutex` | 0x17148 | `DisplayThreadflag` |
| 0x17134 | **`colormode`** ★ | 0x17150 | `gr_colormode` |
| 0x17138 | `ScaleDisplayThread` | 0x17154 | `stdout` |
| 0x1713c | `cond` | 0x17158 | `DisplayThread` |
| 0x17140 | `stderr` | 0x1715c | `video_aspect_ratio_idx` |

**解算结果**
```c
/* video_driver_disp_frame() —— GOT 0x17144 = frame, 0x17134 = colormode */
S = &frame;                                  /* 注意：GOT 内容 = 符号地址 ⇒ r3 = &frame */
if (S->[0] != w || S->[4] != h || S->[8] != pitch) {
    S->[0]  = w;
    S->[4]  = h;
    S->[12] = colormode;                     /* ★ 直接取 colormode 全局的值 */
    S->[8]  = pitch;
}
S->[16] = data;
gr_next_frame();
gr_blit_b(S, ...);
```
⇒ 结合 16.27 的实测（`colormode = 2`、`frame` 指向结构体的 `[12] = 2`）：
**`source->[12] = colormode = 2`，且 `frame->[12] = 2` ⇒ 两侧应当相等。**

**★ 必须解决的矛盾（下一轮唯一入口）**
`gr_blit: source has wrong format` 却出现 **1816 次** ⇒ 上述"应当相等"与实测冲突。三种候选解释（必须用实验排除）：
1. **`gr_blit_b` 的 `P` 不是 `frame`** —— 我按 `add r3,pc,r3` 算出的 GOT 地址是 `0x171cc`，
   但 `0x171cc` **不在**已解析的 GOT 区间（0x17128–0x17168）⇒ 该处要么是 `.data` 里的
   **指针变量**（不是 GOT 项），要么我的 pc 基准取错（`ldr` 的 pc = 该指令 +8）。
2. **双缓冲**：`gr_next_frame` 切换后，`frame` 全局指向的缓冲与 blit 用的 source 不是同一个。
3. **报错的 source 不是 `S`**：`gr_blit_b` 可能还有 other 调用点（本模块内**经 PLT** 调用）。

**⇒ 排除方法（唯一决定性）**：**把断点直接设在 `gr_blit_b` 入口**（而不是像 16.27 那样在 `dispFlip` 里采样），
在同一时刻读 **`r0`（source）的 `[0]/[4]/[8]/[12]/[16]`** 与 **`P->[12]`** ⇒ 一次就能分辨三种解释。

**★ 方法论增量**
- **GOT 解算可以完全脱离 ARM 工具链**：按 `PT_DYNAMIC` 找 `DT_REL/DT_RELSZ/DT_RELENT`，
  对 `R_ARM_GLOB_DAT`(21) 的 `r_offset` 与 `r_info>>8` 取 `.dynsym` 名即可。
- **`VaddrToOffset` 必须遍历 `PT_LOAD`**（节表在某些 `.so` 上不含 `.dynamic`；实测该 DSO 的
  `.dynamic` **只能**从 program header 拿到，用节表解析会 `IndexError`）。


### 16.29 ★★★★★ 用自研反汇编器把 driver.so 的**图形链路**整体解开（含 71 条 PLT↔符号表）

**新仪器 `tools/dis_got.py`**（纯 Python，**不需要任何 ARM 工具链**）：
最小 ARM32 反汇编 + GOT/PLT 解算 + 地址 xref。用法：
```
python3 tools/dis_got.py <elf> --func gr_blit_b          # 反汇编并自动解「字面量池 → 绝对地址 → 符号名」
python3 tools/dis_got.py <elf> --pltrange 1870:1c00      # 全 PLT ↔ 符号表
python3 tools/dis_got.py <elf> --rel                     # 全部重定位
python3 tools/dis_got.py <elf> --xref 0x171cc            # 谁引用了这个地址（3 种模式）
```

**① driver.so 的结构（program header 权威）**
```
PT_LOAD1 vaddr=0x0      filesz=0x6d88  RX   ← 代码 + 只读（含 "gr_blit: source has wrong format" @0x69d8）
PT_LOAD2 vaddr=0x16ef4  filesz=0x2b8   RW   ← .data（colormode@0x171a4 初值 = 2）
BSS：gr_colormode@0x171b4 / 0x171bc / 0x171c4 / 0x171c8 / 0x171cc / frame@0x17220
GOT 基址 = 0x17000（`PLTGOT`）; DT_REL 28 条 + **DT_JMPREL 71 条**（★ 只读 DT_REL 会漏掉整个 PLT）
```

**② 完整 PLT↔符号表（71 条，节选与图形/音频相关的）**
```
0x1a08 puts        0x1a14 malloc    0x1a2c open       0x1a50 mmap       0x1a98 memset
0x1aa4 snd_pcm_hw_params_set_format   0x1ad4 gr_rotate    0x1aec gr_flip
0x1b04 open_drm ★  0x1b28 drmGetCap   0x1b40 pthread_cond_wait
0x1a5c gr_blit_b ★ 0x1a8c gr_next_frame ★ 0x199c gr_init   0x1b4c gr_exit
（另有 drmModeSetCrtc/GetResources/AddFB2/SetPlane/PageFlip/…、snd_pcm_* 20 个、pthread_*）
```

**③ `video_driver_disp_frame(data, w, h, pitch)` —— 判定式的来源（@0x6590）**
```c
if (w & 15)  w = ((w > 0 ? w : w + 15) >> 4 << 4) + 16;   /* 16 对齐；h 同理 */
S = &frame;                                   /* ★ GOT 0x17144（.dynsym 里 frame@0x17220）*/
if (S->[0] != h || S->[4] != w' || S->[8] != pitch) {
    S->[0] = ...; S->[4] = ...; S->[8] = ...;
    S->[12] = *(GOT 0x17134) = **colormode**;  /* ★★ 池@0x67c8 = 0x134 —— 判定用的就是它 */
}
S->[16] = data;
if (gr_next_frame() != 0) gr_blit_b(S, ...);  /* 0x1a8c / 0x1a5c 均经 PLT */
```

**④ `gr_blit_b(r0 = source)` 的判定式（@0x34fc）**
```asm
352c  r3 = 0x171cc ; r3 = *r3          ; cur = 「当前帧」
3538  r2 = [r3 + 12]                   ; r2 = cur->[12]
3540  r3 = [source + 12]               ; r3 = source->[12]
3544  cmp r2, r3 ; beq 3560            ; 相等 ⇒ 继续
354c  puts("gr_blit: source has wrong format")   ; ★ 1816 次的就是这里
```

**⑤ `P` 的来历：driver.so 内部有一个**图形后端 vtable**（这是本轮最重要的结构发现）**
```c
/* open_drm() @0x58b4 —— 只有 36 字节，就是 `return (void*)0x1717c;` */
void *open_drm(void) { return (void *)0x1717c; }

/* 0x1717c 起的 9 槽函数表（全部由 R_ARM_RELATIVE 在加载期绑定 ⇒ 局部函数）*/
0x1717c → 0x4b68    0x17180 → 0x52fc   0x17184 → 0x5208
0x17188 → 0x40bc    0x1718c → 0x543c   0x17190 → 0x5710
0x17194 → 0x546c    0x17198 → 0x55c8   0x1719c → 0x57b0

/* gr_init() @0x3c24 */
if (*0x171cc == 0) {
    puts("open drm!");                       /* ← 实测 stdout 两侧共有的那一行 */
    *0x171bc = open_drm();                   /* DRM 上下文 */
    *0x171cc = (*(void**)0x171bc)->[0](ctx); /* ★★★ cur = ctx->slot0(ctx) */
}
/* gr_next_frame() @0x3a90 : *0x171cc = ctx->[0x14](ctx); return *0x171cc; */
/* gr_select(mode) @0x3bc4 : *0x171cc = ctx->[8](ctx, mode);                  */
```

**⑥ `colormode` 与 `gr_colormode` 是**两个不同东西**（此前混用过）**
```c
/* video_driver_setting(struct{u32 m,a,b;}*) @0x67d8 */
printf("video_driver_setting %d %d %d", p->[0], p->[4], p->[8]);
*(&gr_colormode) = p->[0];        /* ★ 写的是 gr_colormode（GOT 0x17150），不是 colormode */
return 1;
```
- 实测：`gr_colormode = 0`（由 rkgame 的 `video_driver_set_colormode(0)` 写入，见 `Core_Load.c:92`）
- `colormode = 2` 是 **.data 编译期初值，运行期没有任何代码写它** ⇒ `S->[12]` 恒为 **2**

**⑦ fourcc → bpp 映射 `0x42a4`（"Unknown format" 就出自这里）**
```c
int fmt_bpp(u32 fourcc) {
    if (fourcc == "RG24") return 24;
    if (fourcc ∈ {"AB24","XB24","BA24","BX24","XR24","RX24"}) return 32;
    if (fourcc == "RG16") return 16;
    printf("Unknown format %d", fourcc);      /* ← 实测 `Unknown format 875713089` */
    return 32;                                /* 875713089 = 0x34325241 = "AR24" ⇒ 不在支持表里 */
}
```

**⑧ 格式探测 @0x4ee0..0x5068：逐个 fourcc 试建 dumb buffer**
```c
/* 0x43a4(w,h,fourcc)：calloc(1,28) + memset + drmIoctl(fd, 0xC02064B2, &req) */
/*   0xC02064B2 ⇒ _IOC_NR = 0xB2 = DRM_IOCTL_MODE_CREATE_DUMB（_IOC_SIZE = 0x20 = 32 字节私有结构）*/
/* 探测序列与落点（BSS 表 0x171d4 + 0/4/8/12）*/
t[0] = probe("RG16");   t[1] = probe("RG16");   t[2] = probe("RG16");   t[3] = probe("AR24");
if (!(t[0] && t[1] && t[2] && t[3])) {  释放各槽（0x4164）; 0x171e4/0x171e8/0x171ec = 0; }
```
⇒ **`Unknown format 875713089` 正是 driver.so 在探测 `AR24` 时打的**，
与 16.25 的"两侧 stdout 前 24 行**逐字相同**"完全吻合 ⇒ **它不是分歧点**。

**⑨ 判定式两侧的语义（本轮结论）**

| 侧 | 值 | 来源 |
|---|---|---|
| `source->[12]` | **2** | `colormode`（.data 初值，无人改写） |
| `cur->[12]` | **待实测** | `open_drm()->slot0()` 返回的「当前帧」——由 DRM 层按探测到的格式填 |

⇒ **`gr_blit: source has wrong format` 的充要条件 = DRM 层选的格式码 ≠ 2。**

**⑩ 新增探针（本轮的仪器交付）**

`tools/ci_qemu_behav.sh` 新增 `gblit_probe()`，`CGM_GBLIT_PROBE=1` 显式启用（默认关、常规轮次行为一字不变）：
- **复用 `mk_wrap`**（wrapper 里已含 shim + 三桩 `LD_LIBRARY_PATH` + `CGM_*` 转发）—— 外部自行拼环境实测会 `rc=139` 零输出；
- 先在 `dispFlip`（rkgame 自己的符号）命中时反推 `driver_base = video_driver_frame - 0x6590`，
  再挂 `*<base+0x34fc>`（`gr_blit_b`）断点 ⇒ **绕开 `stop-on-solib-events` 的坑**；
- 在 `gr_blit_b` 入口**同一时刻**读：`source`/`cur` 的 `[0][4][8][12][16]`、
  `colormode`/`gr_colormode`、DRM 上下文指针、格式表 4 槽（及其对象的字段）
  ⇒ **一次分辨"谁填了什么"**。

**★ 本轮工具踩的 4 个坑（都会产生"看似合理但错误"的结果）**
1. **数据处理的旋转立即数**：`imm12 = (rotate<<8)|imm8`，值 = `ror(imm8, 2*rotate)`。
   忘了它，`add ip, pc, #0x600`（rotate=6,imm8=0）会被读成"加 0x600"（实为 **0**），
   `add ip, ip, #0xA15` 会被读成"加 0xA15"（实为 **0x15000**）⇒ PLT 目标算成 0x30A9（未对齐、落在 .text）
   而误判"这不是 PLT"。
2. **`DT_JMPREL` 必须单独读**：该 DSO 的 `DT_REL` 只有 28 条（全是数据符号的 GLOB_DAT），
   PLT 重定位全在 `DT_JMPREL`（71 条）⇒ 只读 DT_REL 会得到"PLT 目标全部未知"的假象。
3. **PLT 桩长 12 字节**（`add ip,pc,#imm` / `add ip,ip,#imm` / `ldr pc,[ip,#N]!`），
   按 16 字节步进会**漏掉一半**桩。
4. **判"指令类"的掩码必须含寄存器字段位**：ARM 的 Rd 在 bits15:12、Rn 在 bits19:16，
   用 `0xFFFFF000` 判 `ldr Rd,[pc,#imm]` 只匹配 Rd=0 ⇒ 静默漏掉绝大多数指令。

### 16.30 ★★★★★ 根因锁定：`gr_blit` 忙循环 = **我们桩里 `CREATE_DUMB` 的硬编码**（不是 rkgame 的问题）

**① 探针实测（`CGM_GBLIT_PROBE=1`，新探针第一次运行即到位，J 口径）**
```
>>> driver.so base = 0x40a83000（由 video_driver_frame=0x40a89590 - 0x6590 反推）
>>> gr_blit_b @0x40a864fc   frame(0x17220)=0x5086ef0   cur_slot(0x171cc)=0x5086e88

GB#1 source=0x5086ef0 [0]=1280 [4]=720  [8]=2560 [12]=2 [16]=0x45758008   ← rkgame 的帧
GB#1 cur   =0x5086ea8 [0]=1280 [4]=1280 [8]=5120 [12]=4 [16]=0x41130000   ★不等 ⇒ 报 wrong format
GB#1 colormode=2  gr_colormode=0  ctx=0x40a9a17c
GB#1 frame_tbl = [0x5086e88, 0x5086ea8, 0x5086ec8, 0x5086f08]   ← 4 个「格式探测」缓冲，全部 [12]=4
```
- **`[12]` 就是"每像素字节数"**：`[8] (pitch) = [0] (宽) × [12]` 精确成立（1280×4=5120、1280×2=2560）
- `cur` 在 `tbl[0..2]` 之间轮转（`gr_next_frame` 逐个轮换 dumb buffer）

**② 两个决定性静态证据（`tools/dis_got.py`）**
```c
/* 证据 A：S->[12] 取的就是 colormode，且 colormode 全库【只有一条指令引用】*/
0x66bc  ldr r2,[r4,r3]  ; r3=0x134 ⇒ GOT[0x17134] = colormode
0x66c4  ldr r2,[r2]     ; r2 = colormode 的值
0x66c8  str r2,[r3,#12] ; S->[12] = colormode
/* 扫全 .text：池值 == 0x134 的引用 ⇒ 【仅 1 处】= video_driver_disp_frame+0x12c
   ⇒ 没有任何代码写 colormode ⇒ 它在任何设备上恒为 .data 初值 2（16bpp）*/

/* 证据 B：CREATE_DUMB 的输入字段被我们覆盖 */
```

**③ 根因：桩 `libdrm.so.2` 的 `dumb_fill()` 把 width/height/bpp **写死**（旧实现）**
```c
u32 pitch = 1280u * 4u;      /* ★ 恒定 4 字节/像素 */
zfill(arg, sz);              /* ★ 先清空 ⇒ 把调用者填的 height/width/bpp 全抹成 0 */
p[0] = 720u; p[1] = 1280u; p[2] = 32u;   /* ★ 写死 */
p[5] = pitch;                /* ★ 输出 pitch 恒 = 1280*4 = 5120 */
```
driver.so 读回 `pitch` 后算出 **每像素 4 字节** ⇒ 它的 4 个 dumb buffer 描述符全是 `[12]=4`；
而 rkgame 经 `disp_frame` 写入的 `frame->[12] = colormode = 2` ⇒
`gr_blit_b` 判定恒不等 ⇒ **30 s 内 1816 次 `gr_blit: source has wrong format`（忙循环）**。

⇒ **⇒ 这一条推翻了我此前"rkgame 侧参数/保真度有问题"的所有怀疑：rkgame 侧完全正确（1280×720、pitch=2560=w×2、16bpp）。**

**④ 修正（提交 `38d1c9b8`，**单变量：只改 `dumb_fill`**）**
```c
h = p[0]; w = p[1]; bpp = p[2];      /* ★ 先读输入 */
zfill(arg, sz);                       /* 再清空 */
if (w==0) w=1280; if (h==0) h=720; if (bpp==0) bpp=16;   /* ★ 缺省 16bpp，与 colormode=2 一致 */
rowbytes = (bpp + 7) / 8;
pitch = w * rowbytes;                 /* ★ 尊重请求 */
bytes = (u64)pitch * h;
p[0]=h; p[1]=w; p[2]=bpp; p[3]=0; p[4]=FAKE_FB_ID; p[5]=pitch;
```
- 与内核 `drm_mode_create_dumb` 语义一致：`height/width/bpp/flags` 是**输入**（原样保留），`handle/pitch/size` 是**输出**
- **顺序纪律**：必须"先读输入，再 zfill"—— 反了就把输入抹成 0（旧实现踩过）

**⑤ 新增仪器（本轮交付）**
- `tools/dis_got.py`：纯 Python 最小 ARM32 反汇编 + GOT/PLT 解算 + xref（不需 ARM 工具链）
- `tools/ci_qemu_behav.sh` 的 `gblit_probe()`：`CGM_GBLIT_PROBE=1` 启用，复用 `mk_wrap` 的完整环境，
  一次读出 `source`/`cur` 两侧字段 + 格式表 4 槽

**★ 方法论增量（本轮最值钱的一条）**
> **"厂商代码报错"未必是厂商代码错，也未必是被测程序错 —— 先看**桩回填了什么**。**
> 本例中 `gr_blit: source has wrong format` 出现在 driver.so 里、由 rkgame 触发，
> 但真正的输入（dumb buffer 的 pitch）是**我们桩伪造的** ⇒ 桩的伪造必须**尊重调用者的请求**，
> 否则桩就从"假硬件"变成了"假语义"。**判据：桩的每个输出字段都应能追溯到请求字段或明确的硬件常量，
> 不能是无条件的硬编码。**

**⑥ 修正后的实测（`38d1c9b8`，J 口径逐字复刻 `dv_y` 的开关集）**

| 观测 | 修正前 | **修正后** |
|---|---|---|
| `tbl[0]/[1]/[2]`（driver 的 RG16 探测缓冲） | `[8]=5120  [12]=4`（32bpp） | **`[8]=2560  [12]=2`（16bpp）** |
| `tbl[3]`（AR24 探测） | `[8]=5120 [12]=4` | `[8]=5120 [12]=4`（符合 `fmt_bpp("AR24")==32`） |
| `gr_blit_b` 的判定（探针逐次打印） | 恒 `★不等(将报 wrong format)` | **`==> 相等(应继续)`** |
| rebuild stdout | 1871 行，其中 **1816 × `gr_blit: source has wrong format`** | **55 行，`wrong format` 归零** |
| rebuild stdout 最多的行 | `gr_blit: source has wrong format` ×1816 | `open /sdcard//.dat fail` ×29（已知 CGM_GAMEDIRS） |
| 覆盖率（device 口径） | 73/223 = 32.74% | 73/223 = 32.74%（同 —— 见下） |
| M7 / 终止 | rebuild ✓(124) · factory ✗(139) | rebuild ✓(124) · factory ✗(139) |

- ★★ **`gr_blit: source has wrong format` 从 1816 次降到 0 次 ⇒ 唯一的忙循环被消除。**
- ★ 覆盖率仍为 73：**符合预期** —— `gr_blit_b` 本来就已经在执行（只是每次都提前 `return`），
  修正是让它**把函数体走完**（基本块级差异），而覆盖率是按**函数**计数（`qemu_coverage.py`）⇒ 不涨。
  ⇒ **这正说明"覆盖率"这个刻度对"同函数内的行为差异"不敏感**；本轮的判据必须是
  **`wrong format` 计数 = 0** 这种**语义判据**，不能只看覆盖率。
- 仍存的 M7 差异（rebuild 124 vs factory 139）是既有的、跨口径稳定的现象（GAP 16.26）。

**⑦ 下一步（唯一入口，已量化）**
`rebuild` 现在稳定在 60fps 渲染 + 跑到超时（124），下一个可见的异常是
```
29 × open /sdcard//.dat fail          ← 路径里"目录名"是空的（`/sdcard//.dat`）
```
⇒ 下一步 = 定位这个 `.dat` 路径由哪个变量拼出（与 `CGM_GAMEDIRS` / `GameList` 相关），
确认是"沙箱缺目录"还是"rkgame 侧路径拼装差异"。

**⑧ CI 侧独立验证（`33de02d7`，run `35497188365`，22 steps 全 ✓）**

| 项 | 修正前（`550de4ab` 的 C5） | **修正后** |
|---|---|---|
| 重建侧 `gr_blit wrong-format` 计数 | 1816 | **0**（新硬断言 pass） |
| 重建侧 stdout 总行数 | 1874 | **56** |
| rebuild 覆盖率（device 口径） | 76/223 = 34.08% | 76/223 = 34.08% |
| 终止码 | rebuild 124 · factory 139 | rebuild 124 · factory 139 |

- ★ **单元件差异 + 跨平台（Ubuntu runner + gcc）独立复现** ⇒ 根因与修正都成立。
- ★ 新增工作流硬门禁（第 12 步，**无 `continue-on-error`**）：
  「★ 格式一致性硬断言（C5 的 wrong-format 计数必须为 0）」——
  它专门拦"覆盖率抓不到"的这一类回归（同函数内行为差异）。
  **且已确认它不是空断言**：同一轮 CI 里 C5 的 rebuild 仍 `M7 ✓(124)`、覆盖率 `76/223` ⇒ 断言是在"真跑到渲染"的前提下判 0。

**⑨ 本轮同时暴露的一个 CI 设计缺陷（下一轮修）**

CI 里 `J / M / N / O / P` 五个场景跑的是**默认口径**（jammy sysroot + **不带三桩**）⇒
在那些场景里 `driver.so` 根本没加载（M3 ✗）⇒ 它们**从来没有真正走到菜单渲染**，
所以"列表是否被填充""菜单是否被驱动"这些**它们本来要回答的问题，一条也没被回答过**。
⇒ 下一轮：把这五个场景**重挂到「设备真机 sysroot + 三桩」的深口径**（并把历史数字标注为"浅口径基线"，不可与深口径直接比较）。

### 16.31 ★★★★ 下一个瓶颈的因果链（`.dat` 路径）+ 一个**仪器级缺陷**：CI 的 J/M/N/O/P 一直在浅口径上空转

**① `open /sdcard//.dat fail` ×29 的完整因果链（全部有源码/机器码证据）**

```c
/* 症状来源：mui_DisplayThumbnail()（缩略图线程体，由 filelist_run_game 起的 pthread） */
mui_extract_basepath(basepath, &file_info_list[DAT_003af27c * 0x404], 0x80);
sprintf(path, "%s/%s/%s.dat", root_path, basepath, basepath);   /* ← 拼出 /sdcard//.dat */
iVar1 = OpenZipU(path, 0, 2);
if (iVar1 == 0) RARCH_LOG("open %s fail\n", path);              /* ← ×29 */

/* 列表填充者：dir_serial_list(param_1) —— 结构 0x404 B：name[0x100] + d_type(在 +0x100) */
iVar2 = scandir(path, &list, NULL, alphasort);
两个回环：① 先收「目录」(d_type & 4) ② 再收「文件」
硬闸门： if (DAT_003af394 <= iVar11) 跳过;      /* ★ DAT_003af394 = GameList_count（ui.cfg 里的键）*/
         strcpy(&file_info_list + iVar11*0x404, pdVar8->d_name);

/* 索引来源：mui_menu() */
DAT_003af27c = (m_menulog_blob)._284_4_;        /* 当前选中项，来自 menu.log 的 blob */
```

⇒ **因果链**：`GameList_count == 0`（或 `scandir` 看不到任何目录）
⇒ `file_info_list` **一个条目都不写** ⇒ `DAT_003af27c = 0` 指向**全 0 的空条目**
⇒ `basepath = ""` ⇒ 路径退化成 `/sdcard//.dat` ⇒ 缩略图线程每轮打一行失败。
- ★ 这条链在项目里**早有记录**（`tools/patch_uicfg.py` 的文件头就写了"它为 0 时缩略图路径退化成 `/sdcard//.dat`"）
  ⇒ 所以 **29 行不是新缺陷**，而是 **J 口径（未补 `GameList_count`）的预期症状**；
  真正的下一步不是修 `.dat`，而是**让列表被填起来**（`CGM_UICFG=1` + `CGM_GAMEDIRS=2`）。
- `[8] = [0] × [12]`、`d_type & 4` 先收目录 ⇒ **菜单第一层是"平台目录"列表**，
  与项目已知的 folder-to-core 映射（000=fba / 001=FC / …）一致。

**② 仪器级缺陷：CI 里的 J/M/N/O/P 一直在**默认口径**上跑（= 观测一个不存在的路径）**

| 场景 | 原口径 | 后果 |
|---|---|---|
| A（基线） | jammy，无桩 | 预期（浅） |
| C | jammy + libkms | 观测 driver.so 解锁 |
| C4 / C5 | **device + 三桩** | 真机路径 |
| **J / M / N / O / P** | **jammy，无桩** | ★ `dlopen(driver.so)` 失败 ⇒ **M3 ✗ ⇒ 从来没走到菜单渲染** |

⇒ 这五个场景**本来要回答的问题**（"列表是否被填充""菜单是否被驱动""缩略图是否加载"）
**一条也没被回答过** —— 它们在观测一条根本不经过菜单的路径。
（`dir_serial_list` / `mui_DisplayThumbnail` / `mui_menu` 全都在 `driver.so` 加载之后才可能执行。）

**③ 修正（提交 `1ef9bd56`，纯 CI 口径修改，不动被测代码）**
- 这五个场景统一改为 `SYSROOT=/arm-root-device` + `CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1 CGM_ALSA_STUB=1`；
- 场景 J 的 step 里补**桩构建 + 硬校验**（`[ -f ... ] || exit 1`）⇒
  **深口径不成立就显式失败**，不允许静默退化成浅口径（这正是这一轮暴露出来的失败模式）；
- ★ 在 step 注释里明确标注：**历史数字属"浅口径基线"，与深口径不可直接比较**（口径变了 ⇒ 不是单变量）。

**④ ★★★★ 深组合实验的**负面结果**（实测）：三个开关**全部无效**

| 组 | 新开开关 | factory / rebuild 覆盖率 | stdout | `.dat` 行 | M6/M7 |
|---|---|---|---|---|---|
| `fx_j` | （基线） | 52 / 73 | 51 行 | 25 | ✓ / rebuild ✓124 |
| `fx_n` | +`CGM_GAMEDIRS=2` +`CGM_UICFG=1` | 52 / 73 | 51 行 | 25 | 同 |
| `fx_p` | +`CGM_ALLFILES=1` | 52 / 73 | 51 行 | 25 | 同 |

**三组逐位完全相同**（覆盖率、stdout 每一行、里程碑、终止码）
⇒ **`CGM_UICFG=1`（补 `GameList_count`）/ `CGM_GAMEDIRS=2`（游戏目录）/ `CGM_ALLFILES=1`（游戏索引）
目前一个都没有产生可观测量差异。**

**⑤ 为什么无效：`dir_serial_list` 的调用点根本不在 `mui_menu` 里（新结构洞察）**

```
grep 全仓调用点：
  dir_serial_list     ← **只被 mui_setting 调用**（4 处：fW 302 / 319 / 336 / 340），**不在 mui_menu**
  mui_do_file_list    ← 被 mui_menu 调用（80 / 114 / 119 / 197）—— 它只**显示**已填好的 file_info_list
  mui_type_file_list  ← 被 mui_type 调用
```
⇒ `file_info_list` 由 **`mui_setting`（"设置/类型"屏）**填充；`mui_menu` 只负责**显示**。
⇒ **要让列表被填起来，必须让流程进入 `mui_setting`**（`CGM_MENULOG_SCREEN=5`），
否则补 `ui.cfg` / 造游戏目录**都只是在给一个不会被执行的循环准备数据**。

**⑥ ★ 我的实验设计缺陷（记账，与"漏 KEY2"同类）**

我在 `fx_n` / `fx_p` 里写了
```
run fx_n $J CGM_GAMEDIRS=2 CGM_UICFG=1        # $J 里已经含 CGM_MENULOG_SCREEN=0
```
`env` 的语义是**后写覆盖先写** ⇒ `CGM_MENULOG_SCREEN` 仍是 **0**，
**这三组从头到尾都没进过 `mui_setting`** ⇒ 当然三组相同。
⇒ **纪律：给基础开关集"追加"变量时，必须显式检查是否有重名，并把覆盖项放在最后；
否则你以为在改一个变量，其实什么都没改（而结果看起来像"该变量无效"）。**

**⑦ 顺带完成的一项保真度核对（工厂侧 `dir_serial_list` 的真身，`0x2142c`）**

```asm
0x21440  mov  sb, r0           ; param_1 → sb(r9)（用于后续索引）
0x21450  add  r1, sp, #20      ; &namelist
0x21430  mov  r2, #0           ; 第 3 参数 = NULL
0x2145c  sub  r0, r0, #2000 / sub r0, r0, #4   ; r0 = 0x3c99ec = **全局 path[256]**（不是参数！）
0x21464  ldr  r3, [ip, r3]     ; 第 4 参数 = *(0x3b1e3c)
0x21468  bl   0x99e8           ; scandir(path, &namelist, NULL, compar)
```
- `dis_got.py --rel` 解出：**`0x3b1e3c` = `alphasort` 的 GOT 槽（`R_ARM_GLOB_DAT`）**
  ⇒ 工厂侧 = `scandir(path, &list, NULL, alphasort)`；**与我们重建的写法逐字一致** ✅
  **⇒ `dir_serial_list` 无保真度差异**；路径确实取全局 `path`（0x3c99ec，与 `gdb_globals.sh` 的 `A_PATH` 同一个）。
- ★ 附带能力：**`dis_got.py` 对工厂二进制同样有效**（它是带 113 个 dynsym 的 ELF；`--rel` 能把工厂侧的
  GOT 项翻成符号名，`--addr` 可按绝对地址反汇编）⇒ **工厂侧也进入了"可定点提问"的状态**。


### 16.32 ★★★★★ 方法论纠偏：换判据 —— 从「能跑到哪」到「写得对不对」（覆盖 34% → 100%）

**背景：为什么必须换（自我诊断）**

P5 阶段长期把「QEMU 跑整体 + 函数级覆盖率」当作唯一进度刻度。它的三个硬伤在本轮集中暴露：

| 硬伤 | 实证 |
|---|---|
| ① 只回答"能跑到哪"，不回答"写得对不对" | 修掉 1816 次 `gr_blit: source has wrong format` 忙循环后，覆盖率**一动不动**（同函数内差异不敏感） |
| ② 覆盖面只有 34% | 最好成绩 76/223 ⇒ **147 个函数从未被任何判据检验过** |
| ③ 单轮成本 8~12 分钟且靠猜 | 每轮要"重启容器 → bootstrap → 改 workflow → 等 CI"；驱动靠"环境变量组合"⇒ 三次同类失误（漏 `CGM_KEY2_SEED` / 漏 `CGM_MENULOG_SCREEN` 覆盖 / CI 跑了"半个深口径"），代价是"三组逐位相同"的零信息实验 |

**换判据：逐函数机器码等价性差分（`tools/prop_equiv.py`）**

两侧数据本就都在仓库里，**不需要任何运行时**：
- 工厂侧 `golden/factory.funcs.json`（`extract_factory_funcs.py` 产出）：**835 个函数**，每项含
  `addr` / `n`(指令条数) / `t1`(逐条反汇编文本) / `t2`(助记符序列) / `b`(基本块数)
- 重建侧 `build/rkgame.rebuilt.elf` 的 **SHT_SYMTAB**：**1661 个 FUNC 符号 + size**
  （★ 不能用 `dis_got.Elf.syms` —— 它读的是 dynsym，只有 85 个）

专有函数清单直接取自 `src/proprietary/**/*.c` 的文件名（`FUN_<addr>_<name>.c` ⇒ `<name>`），
⇒ 清单 = "我们实际动手重写了什么"，与源码同步、不会漂移。

**判据与三处**当场修正的失真**（首跑就把它们抓出来了，这是判据可信的关键）**

| 失真 | 首跑症状 | 修正 |
|---|---|---|
| **薄函数**被误判 | 10 个 `4B → 12B`（ratio 3.0）全是 `InitDecode/joystick_poll/spi_memcpy…` —— 工厂侧 4 B = **单条 `bx lr` 空桩**，我们侧编译器保留序言 ⇒ 3 倍差异是**工具链样板**，不是实现不同 | 新增 `THIN` 档（工厂 ≤16B），**单列不计入 FAIL/WARN**，但仍列出供抽查 |
| **判据整体失真**未被察觉 | `__libc_csu_fini`（4B→12B）也在 FAIL 里 —— 它**我们从未写过**，两侧都来自各自 libc | 引入**内置校准锚点** `__libc_csu_*`；锚点若落 FAIL 则工具以 **exit 3** 报"判据失真" ⇒ 失真变成**机器可判**，不靠人看 |
| `mnem_sim` 无信息量 | 连 OK 的大函数也普遍 0.005~0.1（`mui_search` 0.009、`JoystickTest` 0.005） | 保留数值但**显式自证**：体量≥64B 的样本中位数 0.382 ⇒ 工具自动打印"本判据在当前工具链组合下无信息量，结论不得引用" |
| GCC 克隆后缀造成假 MISSING | `code_convert.constprop.22` / `mui_outputxy_length.isra.19` | 新增 `norm_name()` 剥离 `.constprop./.isra./.part./.cold` 等后缀后再匹配 |

**首跑结果（本地，几秒钟）**

```
工厂模型 835 个；专有清单 213 个；重建 FUNC 符号 1661 个
总计 213 | ★FAIL 7 | WARN 4 | OK 184 | THIN 14 | CALIB 2 | MISSING 2
实测分布（仅体量≥64B 的非校准函数，n=178）：min 0.12 | p50 1.00 | p75 1.09 | p90 1.29 | p95 1.64 | max 4.17
校准锚点裁决：✓ 校准锚点全部落在 THIN/CALIB（工具链样板差异已被正确隔离）
```

**★ 两个改变项目图景的发现**

1. **`p50 = 1.00`** ⇒ **一半以上的专有函数，重建产物与原厂的字节数完全一致**。
   ⇒ 项目真实完成度**远高于**"覆盖率 76/223 = 34%"给人的印象：**184/213 = 86% 的函数落在健康水位（<1.6）内**。
   ⇒ 那个 34% 只是"QEMU 能跑到的比例"，**不是"写对了的比例"** —— 长期被当成进度刻度是刻度选错了。
2. **7 个真 FAIL 就是下一轮的精确工作清单**（数据决定，不再需要猜开关驱动）：
   `Convert_Stereo` 56→412(7.36x) · `gameType` 60→276(4.60x) · `SPI_RR` 92→384(4.17x) ·
   `outputblankxy` 220→644(2.93x) · `DrawSelectBar` 168→488(2.91x) · `SPI_WW` 104→296(2.85x) ·
   `mui_LoadUIResource` 324→876(2.70x)

**上线（CI 门禁 + 棘轮）**

- `tools/prop_equiv.py --selftest`：**9 个锚点**（ratio 分档边界 + THIN 上界 + 空桩特例），全绿
- **CI 新增 step 8**「★ 专有函数等价性差分（静态；零 QEMU；213/213 覆盖）」——
  在"构建重建产物"之后、"行为采集"之前，**无 `continue-on-error`**（新 FAIL 直接红）
- `tools/prop_equiv_baseline.txt`：7 个已知 FAIL 登记为 `KNOWN`（沿用 `upstream_fingerprint_baseline.txt` 的棘轮纪律），
  工具会**主动列出"已不再 FAIL、必须删行"的陈旧项**（纪律 1 由机器执行）
- 退出码约定：`0` 无真 FAIL / `2` 有真 FAIL / `3` 判据失真（校准锚点被误判）
- artifact 带上 `report/prop_equiv.json`（机器可读，供后续趋势跟踪）

**★ 方法论增量（写进记忆与技能）**

> **进度刻度必须选在"目标本身"上。** 本项目的目标是"1:1 重建"，所以刻度必须是
> "逐函数的实现等价性"，而不是"某次跑动能覆盖多少函数"。后者把
> **"没跑到"与"写错了"混为一谈**，导致 66% 的函数既没被检验、也不计入工作量。
> 判据上线时**必须自带校准锚点**（用"已知等价但来源不同"的对象，如工具链样板），
> 否则"工具链差异"会被系统性误判成"实现不符"——本次 `__libc_csu_fini` 正是这一条抓出来的。

### 16.33 ★★★★★ 根源性修复：**编译口径** —— 工厂是 `-Os`，我们用 `-O1`

**起点**：GAP 16.32 建立的逐函数等价性判据给出 7 个真 FAIL。第一反应是"这些函数写错了"，
但把两侧反汇编并排打出来（`golden/factory.funcs.json` 的 `t1` vs 我们产物的 symtab）看到的是**同一种模式**：

| 函数 | 工厂形态 | 我们形态 |
|---|---|---|
| `SPI_RR` | 23 条，`mov r5,#8` + `lsl r4,r4,#1` + `orrne` + `bne`（**保留 8 次循环**） | 96 条 = **8 × 11 + 序言**（循环被**完全展开**） |
| `Convert_Stereo` | 14 条双循环 | 103 条 ≈ 32 × 3 + 序言（内层 32 次被展开） |

而**源码**是我们 1:1 从 Ghidra 反编译搬过来的：
```c
/* SPI_RR：次数是编译期常量 8 */
cVar2 = '\b';  uVar3 = 0;
do { sunxi_gpio_output(1,0); sunxi_gpio_output(1);
     iVar1 = sunxi_gpio_input(2);
     uVar3 = (uVar3 & 0x7f) << 1;  cVar2 = cVar2 + -1;
     if (iVar1 != 0) uVar3 = uVar3 | 1;
} while (cVar2 != '\0');
```
⇒ **这就是"常量次数小循环被编译器完全展开"**，不是实现差异。

**单变量实验（本地即可做，不需要容器/设备）**
用 `zig cc -target arm-linux-gnueabihf.2.29` **逐个编译同一份 `src/proprietary/*.c`**，
只改优化选项，再解 `.o` 的 `SHT_SYMTAB` 取函数体大小：

| 函数 | 工厂 | `-O1`（当前） | `-O1 -fno-unroll-loops` | **`-Os`** |
|---|---|---|---|---|
| `SPI_RR` | **92 B** | 384 B (4.17x) | 96 B (1.04x) | **92 B (1.00x ★精确到字节)** |
| `gameType` | 60 B | 276 B (4.60x) | — | **52 B (0.87x)** |
| `Convert_Stereo` | 56 B | 412 B (7.36x) | — | **76 B (1.36x)** |
| `outputblankxy` | 220 B | 644 B (2.93x) | — | **272 B (1.24x)** |
| `DrawSelectBar` | 168 B | 488 B (2.90x) | — | **196 B (1.17x)** |
| `SPI_WW` | 104 B | 296 B (2.85x) | — | **96 B (0.92x)** |
| `DrawFrame` | 552 B | 644 B (1.17x) | — | **508 B (0.92x)** |
| `mui_LoadUIResource` | 324 B | 312 B (0.96x) | — | 308 B (0.95x) |

- ★ **`-O1` 的 384 B 与 `prop_equiv` 实测的 `SPI_RR` 尺寸逐字相同** ⇒ 实验口径与判据口径一致，实验可信。
- ★ **`-Os` 让 `SPI_RR` 精确命中工厂的 92 B** ⇒ **工厂 rkgame 是 `-Os` 编译的**。
- ★ 抽样 8 个函数中 **7 个 `-Os` 更接近工厂**（唯一例外 `mui_LoadUIResource` 两者几乎相同：0.96 vs 0.95）。

**修复（提交 `b0193a6b` 等）**
- 编译入口是 **`tools/link_audit.sh`**（`cnb_env.sh` [6/7] 调它，"唯一把 `src/proprietary/*.c` 编成
  `build/obj/*.o` 的脚本"）—— **不是** `link_full.sh`（那只做链接）。
  ⇒ 第一次改错了 `recon_build.sh`/`recon_local.sh`（顺带一起改了，保持一致），
    真正的入口在 `link_audit.sh:36`。
- 把 `-c -O1` 改为 `-c $OPT`，`OPT="${OPT:--Os}"` ⇒ **默认对齐工厂，且可用 `OPT=-O1` 单变量回退对照**。
- 脚本头部写清依据与纪律（避免以后有人"顺手改回去"）。

**★ 方法论（可复用，值得写进技能）**

> **在"二进制 1:1 重建"里，编译口径必须从原厂产物反推 —— 它是与"实现正确性"同等量级的变量。**
> 反推方法极简单：**同一份源码 × 不同 FLAGS → 逐个比对函数体大小**，命中者即为原厂口径。
> 本项目的证据强度：`-Os` 下 `SPI_RR` 与工厂**同尺寸到字节**（92 = 92）。
>
> 不这么做的代价：把"纯编译差异"（循环展开 4~7x）误判成"实现不符"，
> 于是**花时间去改本来正确的代码**。本轮的 7 个 FAIL 里至少 5 个属于这一类。

**顺带**：本轮还修掉了判据的地基 —— `tools/arm_dis.py`（完整 ARMv7-A 解码器）。
`dis_got.py` 原自带解码器**未识别率 32%**（漏掉 `cmp r0,#0`(1596) / `ldr r0,[pc,r0]`(932) /
`mvn r0,#0`(408) / `bx lr`(164) / `lsl r1,r1,#1`(152) 等最基本指令），
直接把"助记符相似度"判据污染成"无信息量"。修为 40 锚点自证 + **真未识别率 0.00%** 后，
该指标中位数从 0.382 → 0.443（工具不再宣告不可用）。

### 16.34 ★★★★ 判据的第五个校准点：**双侧对称** —— 并因此暴露两个此前被掩盖的真问题

**反证先记**：把编译口径改成 `-Os` 后，如果只按"逐函数 `|ratio-1|` 更小"计数，
`-O1` 反而"赢"（103 vs 68）。**这说明"取绝对值最小"是错的判据**：

| 函数 | 工厂B | `-Os` | `-O1` | 谁"更接近" | 真实性质 |
|---|---|---|---|---|---|
| `SPI_RR` | 92 | 1.00 | 4.17 | -Os | 工厂更大（循环展开，**纯噪声**）|
| `init_user_joy_key_mask` | 340 | 0.32 | 0.51 | **-O1** | **我们明显更小（真信号）** |
| `popwindows` | 556 | 0.53 | 0.86 | **-O1** | **我们明显更小（真信号）** |

⇒ **偏大（循环展开/内联，编译器）与偏小（少实现，真差异）的成因完全不同**，
却都"偏离 1" ⇒ **必须两侧分别设阈值**。改为 `skew = max(ratio, 1/ratio)`（WARN≥1.6 / FAIL≥2.5）。

**改完立刻抓到两个此前躺在 `OK` 里的真问题**：

| 函数 | 工厂B | 我们B | ratio | 旧判据 |
|---|---|---|---|---|
| `ReadPS2JS` | 384 | 148 | **0.385** | OK（被掩盖）|
| `UpdateROM` | 976 | 116 | **0.119** | OK（被掩盖）|

**`UpdateROM` 的定位（决定性）**
```asm
0x5001108  UpdateROM 段1（116 B）：fopen / fread / fclose / magic 校验 / printf
0x5001174  ← 字面量池（两个 32 位常量）
0x500117c  ← 紧接着：push {9 regs} / vfp / sub sp,#296 / ldr r0,[pc,#664] / mov r1,#480
                                                                    ↑ 480 = 0x1e0 = scr_h_size
```
⇒ **编译器把 `UpdateROM` 拆成了两段**（热路径 + 主体），**符号表的 `st_size` 只覆盖第一段**。
源码是完整的（139 行，含 `OpenZipU`/`UnzipItem`/`sflash_*`/`reboot`），
且 `UpdateROMProc` 侧 884 B vs 工厂 852 B = 1.04x **正常** ⇒ 排除"函数拆分/缺失"。
⇒ 这是**纯工具链行为**，不是实现差异。

**已做的两件事**
1. **判据双侧对称**（`skew`），并在输出层给"偏小"项加显式提示
   `←★偏小：疑编译器分段（查紧随地址）或真的少实现`（提醒先反汇编紧随地址再判定性质）。
2. **基线棘轮**：`-Os` 口径下原 7 项 FAIL 全部关闭 ⇒ **按纪律 1 清空**；
   新登记 2 项偏小项（`UpdateROM` 已定位=分段 / `ReadPS2JS` 待按地址核对）。

**★ 方法论**：判据的"对称性"不是审美问题。只要两侧偏差的**成因不同**，
就必须用**两个方向的阈值**，否则一定会有一侧的真问题被系统性掩盖 ——
本项目这两项已经躺在 `OK` 里很久了。

### 16.35 ★★★★ 编译口径切换（`-O1`→`-Os`）连带暴露的**两个真问题** + 判据的第六个校准点

改口径是"消除噪声"，但**噪声被消除后，原先被掩盖的东西就露出来了**。CI 立刻给出两处：

**① `1to1-verify` 的「调用点实参寄存器对拍」硬门禁失败**
```
★★ 新增差异 1 对（不在台账内 ⇒ 判失败）：
   mui_do_file_list -> IsShoucang   未设 r2   LOW
```
- 台账里**已有** `mui_type_file_list IsShoucang LOW` —— 这是**同族的另一对**。
- 机制：`-O1` 下 `mui_do_file_list` 里对 `IsShoucang` 的调用**被内联** ⇒ 扫描器看不到；
  `-Os` 不内联 ⇒ **调用点显形** ⇒ 才发现"这个调用点没设 r2"。
- 定级 `LOW`（缺失寄存器不在两侧 live-in 中 ⇒ 保真度差异，暂无行为后果），
  已按台账纪律登记（同族项已在表中）。

**② `1to1-qemu-behav` 的「行为采集 + 差分 ★ 硬门禁」失败 —— 而这是判据问题，不是行为问题**
```
[FAIL] B2 events   可判定前缀 34/38 行一致；重建侧共 39 行
@@ -32,7 +32,7 @@
 E|[shim] 栈回溯（sp+0..sp+40；仅列可解析项）:
+E|[shim] [sp+ 4] = ADDR -> /arm-root/lib/.../libc.so.6 + __fstatat64_time64
```
- 差异行是**崩溃现场的栈内容转储**：记录"崩溃时栈上恰好残留什么地址"。
- ★ **控制组（同一份二进制跑两遍）是 38/38 完全一致** ⇒ 确定性没问题，
  变的只是**跨二进制的偶然栈内容**（栈布局随编译产物变）。
- ⇒ 这是判据的**第六个校准点**：**崩溃诊断里的"栈转储"不携带可比信息，
  不应参与行为等价性判定**（崩溃位置由 `pc(出错点)`/`lr(调用者)`/`故障指令` 另有独立行记录，
  语义判决能力不受影响）。
- 修法（`tools/behav_diff.py`）：新增 `_drop_volatile()`，**整体丢弃** `E|[shim] [sp+ N] = ...`
  这类行，并在丢弃时打印 `[note] 已折叠「栈内容转储」行…`（透明，不静默）。
  控制组 `ec` 同样折叠，保证前缀与两侧比较在同一口径下进行。

**★ 本轮的连带收益（一句话）**
> 把编译口径对齐工厂（`-Os`）不只是"让数字好看" —— 它把**四个此前被掩盖的真问题**
> 一并掀出来了：`UpdateROM`/`ReadPS2JS` 的 size 偏小（分段）·
> `mui_do_file_list -> IsShoucang` 未设 r2（调用约定）· 以及判据自身对"栈转储"过敏。
> **口径不对齐时，判据会同时产生"假阳性"（循环展开）和"假阴性"（内联掩盖调用点）** ——
> 两个方向的错误同时存在，这才是它最危险的地方。

### 16.36 ★★★★★ 判据第二次换刻度后的**第一个真缺陷**：Ghidra 把「栈槽地址」当循环边界

**入口**：`prop_equiv` 在 `-Os` 口径下只剩 2 个真 FAIL，其中 `init_user_joy_key_mask`
的 size 比只有 **0.342**（工厂 316 B / 我们 108 B）。最初归为"疑编译器分段"。

**第一步：读我们的源码 —— 它是完整、忠实的 1:1 转写**（83 行，两段循环 + `turbo_delay = param_2`
逐条对得上工厂反汇编 79 条）。所以"少实现"不成立，必须查产物。

**第二步：查产物的原始机器码与重定位（决定性）**

| | `.text` | `.rel.text`（被引用的外部符号） |
|---|---|---|
| 修复前 | **108 B（27 槽）** | **1 条：只有 `STD_index`** |
| **源码声明的全局** | — | `STD_index` / `user_joy_key_mask` / `user_joy_key_trubo` / `joy_key_mask` / `turbo_delay`（**5 个**）|

⇒ **源码引用的另外 4 个全局，在目标文件里一次也没被引用**。反汇编也显示：
代码在**第一段循环的背边**处 `b <loop_head>` 结束，**没有终止测试、没有函数尾声**，
`.text` 末尾两条是字面量池。

**第三步：根因 —— 一个 Ghidra 保真度陷阱**

```c
gh_uint local_88 [24];
gh_uint uStack_28;                 /* ← Ghidra 把「数组末尾那个栈槽的地址」单独渲染成一个对象 */
...
}} while (puVar6 != &uStack_28);    /* ← 用它的地址当循环边界 */
```
`uStack_28` 作为**独立 C 对象**，地址由编译器自行摆放。放在 `local_88` 之下时，
`puVar6 != &uStack_28` **恒真** ⇒ 循环后续全部是**不可达代码** ⇒ 编译器
**合法地整段删除**（第二段循环 + 尾声），第一段循环还失去终止测试变成**死循环**。

**第四步：修复 + 单变量验证（本地即可，几秒）**

```c
}} while (puVar6 != local_88 + 24);   /* 边界与数组同源 ⇒ 不依赖局部变量布局 */
```

| | `.text` | 重定位 | vs 工厂 |
|---|---|---|---|
| 修复前 | 108 B（27 槽） | 1 条 | 0.342x → FAIL |
| **修复后** | **348 B（87 槽）** | **6 条** | **1.101x → OK** |

⇒ 这**不是**体积问题，是**函数体被删 + 变成死循环**。判据（size 比）只是把它"顶出来"，
真正定性靠的是"**源码声明的全局 vs 目标文件重定位**"这条硬证据。

**第五步：把这一类固化成门禁 `tools/scan_dead_loop.py`**

- 判据：**产物里出现「无出口的强连通块（SCC >= 2 块 + 无出边 + 从入口可达）」**，
  且**源码里没有** `for(;;)`/`while(1)`/`while(true)` ⇒ 判 FAIL。
- 为什么这样设计：源码里本来就是死循环的函数（`XintiaoThread`/`JoystickThread`/
  `main_Menu` 等 **6 个**，全部含 `while(true)`）命中是**预期**的；门禁**自动去查同名源文件**，
  自维护、不需要人工白名单。
- 口径收敛过程（**锚点自证 + 实跑双向校验**）：
  1. 只认"≥2 块" ⇒ 6 命中（全在源码里有 `while(true)`，合理）；
  2. 放宽到"单块自环 `b .`" ⇒ **假阳性从 6 暴涨到 32**（函数里的字面量池数据字被解成 `b .`，
     加"可达性"也拦不住 —— 条件分支的 fall-through 会落进池里）⇒ **收敛回"≥2 块"**。
  ⇒ 教训：**判据放宽必须同时看"锚点"和"实跑命中数"**，只看锚点会过拟合。
- 形态：`--selftest` **5 个锚点**（含"条件分支的目标必须落在指令序列内"这条设计纪律，
  否则"有出口的循环"会被误判）；退出码 `0 / 2 / 3`。已接入 CI（第 20 步，硬门禁）。
- ★ 顺带发现：`Ghidra 用「另一个局部对象的地址」当循环/比较边界` 这个**精确形式**
  在全仓只出现 **2 处**（另 1 处是 `mui_menu.c` 传参，非边界）⇒ 不是主要成因，
  但**一旦命中就是"函数体被删"级**的后果。

### 16.37 ★★★ 判据的第九、十个校准点（本轮新增，均带实证）

**⑨ 工厂体积必须扣除字面量池。** `factory.funcs.json` 的 `t1` 把函数尾部的字面量池
也列成 `.word` 条目（1 条 = 4 B），而 `n` 把它们算进指令数 ⇒ `fac_b = n*4` 把池当代码。
实证：`GetWorkPath` 工厂 `n=7`（含 **2** 个 `.word`）⇒ 按 `n*4` 是 0.571，
按**纯指令 5×4=20 B** 是 **0.800**。修法：主判据改用"纯指令字节数"，原始值写入 JSON 备查。

**⑩ 逐指令比（`n_ratio`）需要最小样本量。** 小函数"差 1 条指令"就能把比值推到 1.75+。
实证：`GetWorkPath` 工厂 5 条 / 我们 4 条 ⇒ 读作"偏离 1.751"（WARN），
而两道都只是"取一个全局指针"，差别仅在字面量池取址方式。
修法：仅当工厂**纯指令数 >= 12** 时让 `n_ratio` 参与判决。

### 16.38 ★★★★ 变参门禁的**判据盲区**（本轮第二个真缺陷 + 门禁自纠）

**① 工厂侧判据太窄 ⇒ 整族漏掉。** 原判据只认 `push {r0,r1,r2,r3}`（`0xE92D000F`）。
但 GCC 只保存**真正需要**的变参寄存器：`log_dummy(int lvl, const char *fmt, ...)`
的 `lvl` 是已消费的固定参数 ⇒ 序言是 **`push {r1,r2,r3}`（`0xE92D000E`）** ⇒ 旧判据漏掉。
放宽后立刻多抓出 **1 个真缺陷**（`log_dummy` 丢了 `...`，与 `RARCH_LOG` 同类）。

**② `patch_proto_varargs.py` 也只匹配空声明** ⇒ 对"有固定参数 + `...`"的函数
（Ghidra 渲染成 `(gh_uint, gh_u4)`）静默 warn 跳过。已放宽为匹配任意
`extern void <fn>(...)` 且要求参数列表不含 `...`（幂等）。

**③ 自己判据的第二次盲区：我们侧也不该只认 `push/stm`。** 修复后 clang 的产物是
`str r2,[sp,#16] / str r3,[sp,#20] / add r2,sp,#16 / mov r0,r1 / mov r1,r2 / bl RARCH_LOG_V`
—— **用两条独立 `str`** 保存变参区。判据改为**语义式**："必须构造 va_list 基址
（`add rX,sp,#imm`）并在其后 8 条指令内出现 `bl`"。因为变参转发**必须把 va_list 的地址交出去**，
而尾调用 `b` 构造不了（这正是原缺陷形态）⇒ "取址 + 真调用"是必要特征。

**④ 顺带定位：为 `log_dummy` 写的位置判据。** 放宽掩码后立刻出现假阳性
`PauseMenu`（真序言 `push {r4..fp,lr}`）—— 命中来自**函数体内部**（入口 +2128 B 处）
恰好有一条 `push {r1,r2,r3}`。⇒ 补"变参序言必须落在函数入口 +32 B 内"。
**不做位置约束，判据就没有意义。**

**收口（本地 -Os 口径，三道门禁全绿）**

| 门禁 | 结果 |
|---|---|
| 专有函数等价性差分 | **★FAIL 0** / WARN 8 / OK 184；分布 `p50 1.03 / p95 1.33 / max 1.72` |
| 变参函数保真度 | **PASS 5/5** |
| 死循环门禁（新） | **PASS**（6 个命中全为"源码有 `while(true)`"）|

**已定性的"编译器习语"（登记入基线，**不修源码** —— 修了反而破坏语义等价）**

| 函数 | 比值 | 机制（反汇编证据） |
|---|---|---|
| `ClearBuffer` | 0.625 | 编译器把手工清零循环换成 **`memset` 尾调用**（`cmp/bxlt/mov/mov/b memset`），工厂保留逐字节循环 |
| `sunxi_gpio_output` | 0.603 | 编译器用**条件执行**把 6 个分支块融合成 3 个（`orrne`/`biceq`），工厂是 6 个独立块 |
| `sunxi_gpio_set_cfgpin` | 0.603 | 同上（逐条指令同形） |

**★ 方法论（本轮最值钱的一条）**

> **"体积偏小"可能是三件完全不同的事**，必须用**机器码级证据**区分，不能靠体积猜：
> 1. **编译器习语**（memset 尾调用 / 条件执行融合 / 寻址模式）—— 语义等价，登记即可；
> 2. **编译器分段**（`st_size` 只覆盖第一段）—— 查"紧随地址"即可确认；
> 3. **函数体被删**（本轮）—— **查"源码声明的全局 vs 目标文件重定位"**，一次性定性。
>
> 而**第 3 类只有靠"语义判据"才能与第 1、2 类区分开**：体积比只是"把它顶出来"的探针，
> 定性的硬证据是**重定位/被引用符号集合**。这也是为什么值得为它单独建一条门禁
> （`scan_dead_loop.py`）—— 体积比会漏（本例 0.342 与"习语"的 0.603 只差一倍），
> 而无出口循环是**非此即彼**的结构特征。

### 16.39 ★★★★★ 第二个「函数被编译器删除」的真缺陷：**延时循环被当死代码删掉**

**入口**：`ReadPS2JS` 的 size 比 0.375（工厂 384 B / 我们 144 B）。按上一轮建立的**结构对拍**顺序检查：

| 证据链 | 结果 |
|---|---|
| 被调函数集合 | **与工厂完全一致**（`sunxi_gpio_input` / `sunxi_gpio_output`，2/2）⇒ 不是"少调用" |
| 比较/条件分支直方图 | `cmp` 8→2，**条件分支 10→1** ← 唯一异常 |
| 并排反汇编 | **★ 工厂有 3 段忙等延时循环，我们一条都没有** |

**工厂侧（96 条）**的三段延时循环（每段外层 5 次、内层 **39 = 0x27** 次）：

```asm
str r8, [sp, #8]      ; i = 0
mov r3, #39
str r3, [sp, #12]     ; limit = 39
loop: ldr r2,[sp,#8] / ldr r3,[sp,#12] / cmp r2,r3 / bge out
      ldr r3,[sp,#8] / add r3,#1 / str r3,[sp,#8]
      ldr r2,[sp,#8] / ldr r3,[sp,#12] / cmp r2,r3 / blt loop
```

**这是 GPIO 位敲（bit-bang）的时序延时** —— 少了它，PS/2 的读时序就变了。

**我们侧（36 条）**：三段全无。而源码里**明明有**：

```c
do { local_30 = 0; do { local_30 = local_30 + 1; } while (local_30 < 0x27); iVar4--; } while (iVar4);
```

⇒ **现代编译器把它判定为死代码整体删除**：计数器是普通局部变量 ⇒ 被提升到寄存器 ⇒
循环无任何可观察副作用 ⇒ 删。**换编译器也一样**（同一份源码实测）：

| 编译口径 | `ReadPS2JS` | vs 工厂 384 B |
|---|---|---|
| 工厂 GCC 6.2.0（基准） | 384 B | 1.00x |
| clang（zig cc `-Os`） | 144 B | 0.375x |
| **GCC 14.2 `-Os`（本轮新做的对照组）** | **88 B** | 0.23x（**删得更彻底**） |

**修法（语义修复，不是为了让数字好看）**：延时计数器改 `volatile` ⇒ 每轮迭代强制真实存取，
与工厂"每轮写栈"的行为一致。
**结果：144 B → 276 B（0.719x，从 FAIL/KNOWN 进 OK 区）**。

### 16.40 ★★★★ 顺带证伪了两条假设（都做成了单变量实验）

**① `.ARM.attributes` 能给 ISA/ABI 的权威口径，但给不出优化级别。**
按官方 tag 编号解析工厂的 `.ARM.attributes`（55 B）：

| 属性 | 值 | 含义 |
|---|---|---|
| `CPU_arch` | 10 | **ARMv7** |
| `CPU_arch_profile` | 0x41 = 字符 A | Application profile |
| `ARM_ISA_use` / `THUMB_ISA_use` | 1 / 2 | 用 ARM 指令 + **Thumb-2** |
| `FP_arch` / `Advanced_SIMD_arch` | 3 / 1 | VFPv3 + **NEON** |
| `ABI_VFP_args` | 1 | **硬浮点（VFP registers）** |
| `ABI_PCS_wchar_t` / `ABI_enum_size` | 4 / 2 | wchar_t=4B、enum=int |
| `ABI_align_needed` | 1 | 8 字节对齐 |
| **`ABI_optimization_goals`** | **缺失** | ⇒ **不能**用它独立确认 `-Os` |

⇒ 结论要说清楚：**`-Os` 仍只由"尺寸逐字节命中"这条证据支撑**（`SPI_RR` 92 = 92 B），
`.ARM.attributes` 只权威确认了 ISA/ABI 部分。**不要把"没有反证"当成"有正面证据"。**

**② 「工厂用 GOT 式寻址、我们直接寻址」不是可切换的口径差异。**
动机：工厂有 `.got`（1144 B）而我们的产物**没有** `.got`；我们侧 `ldr` 数只有工厂一半
（`ReadUSBJoy` 79→42、`ReadPS2JS` 15→0）。假设是"工厂编了 PIC"。
**单变量实验（容器里做，4 种口径 × 9 个函数）**：

| 口径 | gcc `-Os` | gcc `-Os -fPIC` | zig(clang) `-Os` | zig `-Os -fPIC` |
|---|---|---|---|---|
| `-fPIC` 是否改变尺寸 | — | **无变化** | — | **无变化** |
| 最接近工厂的次数 | 1 | 0 | **8** | 0 |

- **`-fPIC` 在两种编译器上都完全不改变这些函数的尺寸/寻址形态** ⇒ 不是开关问题；
- **换 GCC 反而更小**（`ReadUSBJoy` 332 vs clang 520；`popwindows` 220 vs 296）⇒
  现代 GCC 的 DCE/合并比 clang 更激进。

⇒ **我们现用的 clang（zig cc）已是可得的最优选择**；"寻址模式"不是待修的偏差，而是
**GCC 6 时代代码生成与当代编译器的固有差异**（登记豁免）。

### 16.41 ★★★ 新门禁 `tools/scan_delay_loops.py`（判据与体积无关）

- **判据**：源码里存在"纯计数循环"（循环体只有 `X = X ± 1;`，条件是 `X <op> 常量`）时，
  该**常量必须作为立即数出现在产物的函数区间内**（`cmp rX,#C` / `mov rX,#C` / `ldr` 的 imm12）
  ⇒ 说明循环还在；找不到 ⇒ **循环被编译器删掉**。
- **为什么不用体积**：体积比只能"顶出来"，而且本例 0.375 与"正常习语"的 0.60 只差一倍；
  而"常量还在不在"是**非此即彼**的。
- 实测：修复前 `ReadPS2JS` 的 `0x27` 不在产物里 ⇒ FAIL；修复后 `0x27` 在位 ⇒ PASS。
  当前全仓 **5 处**这类循环（`ReadPS2JS`×3 · `TestUSBJoy` · `gameType`）**全部在位**。
- 已接入 CI（第 20 步，硬门禁）；`1to1-qemu-behav` 现有 **3 道静态门禁**（等价性 / 延时循环 / 死循环）。

**★ 补进方法论的"删除类"缺陷清单（现在有两条）**

> 编译器"删代码"有两种完全不同的形态，**都必须用源码→产物的结构对拍才能发现**：
> 1. **不可达尾被删**（GAP 16.36）：循环边界取了另一个局部对象的地址 ⇒ 条件恒真 ⇒ 后面全删；
>    症状 = **无出口循环** + **重定位数骤减**。
> 2. **死代码循环被删**（本轮）：循环体无副作用 ⇒ 整段删；
>    症状 = **源码有该常量、产物没有** + **条件分支数骤减**。
>
> 共同点：**体积比只能"顶出来"，定性必须靠结构证据**（重定位集合 / 循环常量在不在）。

### 16.42 ★★★★ 仪器化：`tools/cmp_calls.py`（被调函数集合对拍）+ 一个**开放项**

**动机**：本轮排查 5 个"偏小"项时，我发现最便宜、最决定性的第一步是
**"工厂调用过的函数，我们是否也调用了"**。把它做成工具后，一次跑完 213 个函数。

**判据**：工厂 `t1` 的所有 `bl @name` 归一化后，必须是重建侧该函数 `bl`/`blx` 目标集合的子集。

**开发中踩到的三类假阳性（都已在工具里消掉，并写进注释）**

| 类别 | 现象 | 处理 |
|---|---|---|
| **thunk 包装** | 我们侧 libc 调用走 `__ARMv7ABSLongThunk_sprintf` 桩 | `norm()` 剥前缀 |
| **GCC 克隆后缀** | 工厂叫 `run_process.constprop.0` / `mui_outputxy_length.isra.19` | 剥 `.constprop/.isra/.part.N` |
| **可内联内建** | `memcpy`/`strlen`/`malloc`/`__aeabi_*idiv`/ctype 族（glibc 里是宏） | 白名单（实测：不设白名单时 36 个函数被误报，设后降到 9，再剥后缀+分段修正后降到 8）|

**残留 8 项的逐条归类（这就是本工具的真正价值：把噪声压到能逐条看）**

| 函数 | 缺的符号 | 归类 |
|---|---|---|
| `DeinitDisplay` / `InitDisplay` | `run_process` | 疑似**内联**（工厂调 `.constprop.0` 克隆体） |
| `DisplayLine_list` / `EmuCore_Line` | `mui_outputxy_length` | 同上 |
| `mui_run_game` / `shoucang` | `code_convert` | 同上 |
| `UpdateROM` | `OpenZipU`/`UnzipItem`/`GetZipItemA`/`CloseZipU`/`DateToTmuDate` | **编译器分段**（GAP 16.34 已定性：`st_size` 只覆盖第一段，第二段被链接器放到别处） |
| `mui_setting` | `UnDrawSelectBar` | **★ 开放项**（见下） |

**★ 开放项：`mui_setting` 少了一次 `UnDrawSelectBar` 调用**

源码 `src/proprietary/mui/FUN_0002b2b4_mui_setting.c:143` 是**活代码**：
```c
if (-1 < DAT_003af27c) {
    UnDrawSelectBar(local_56c + DAT_003af27c * 4,(int)DAT_003af294,0);   /* ← 擦掉上一个选中项 */
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294);
    ...
}
iVar9 = iVar11;
if (-1 < iVar11) { DrawSelectBar(local_56c + iVar11 * 4); ... }           /* ← 画新的选中项：我们侧在 */
```

**已排除的解释（都有实测）**
1. **不是命名问题**：`UnDrawSelectBar` 在我们产物里就叫这个名字（160 B），`prop_equiv` 也认它；
2. **不是内联**：拿 `UnDrawSelectBar` 的指令签名（去寄存器、留助记符+立即数）在 `mui_setting` 体内
   做子序列匹配 ⇒ **最长连续匹配 1/30 条** ⇒ 没有被内联；
3. **不是分段**：全可执行段搜"目标 = `UnDrawSelectBar` 地址"的 `bl` ⇒ 命中 8 处，**全部落在
   `mui_joystick_setting`(×5)/`mui_video_setting`(×3) 的 `st_size` 之内**，没有任何一处来自
   `mui_setting` 区域；
4. **不是尾部合并**：同一函数里确实能看到尾部合并的痕迹（`mui_outputxy_t` 13→8、`mui_DispBlock` 6→5、
   `dir_serial_list` 13→10），但尾部合并**只能让调用点共用，不可能把 1 次降到 0 次**。

**旁证**：我们 `mui_setting` 是 **7700 B vs 工厂 6500 B（1.185×，属 OK 区，不是偏小）** ⇒
"少一次调用却更大"本身说明代码膨胀/重排也在发生，两件事并不互斥。

**★ 这个开放项**：**不宣称是真缺陷，也不排除**。下一步的判据（已想清楚，成本低）：
> 在 `mui_setting` 里定位"`-1 < DAT_003af27c` 检查 + 紧随其后的 `mui_DispBlock`"这一对，
> 与工厂同位置逐条对比 —— 若那一块整体在、只少一条 `bl`，就是**真缺陷**（
> 少了"擦除上一个选中条"⇒ 菜单残影）；若那一块整体不在、且另一块已被复用，则是**控制流合并**。

**工具定位（重要）**：`tools/cmp_calls.py` 目前**是报告级，不接 CI 门禁** ——
残留项的"内联 vs 分段 vs 缺失"还需要人工判一次。等开放项结论出来后，
把残留项登记成基线（带理由）即可升级为门禁。
**不接门禁的理由要写清**：判据的**假阳性率**当前无法降到可接受水平（36 → 8 已尽力），
而门禁一旦长期带假阳性就会被人忽略 —— 这比没有门禁更糟。

### 16.43 ★★★★★ 换刻度：从**静态体积比** → **可观测窗口内的执行集合差集**

**（一）先记账：我确实绕圈了**

前几轮我把"`prop_equiv` 的 size 比"当成了推进刻度，于是每轮的工作变成
**逐个人工分类"体积偏小"的项**（习语 / 分段 / 删代码 / 内联）。这条路不是无效 ——
它抓出了两个真缺陷（`init_user_joy_key_mask` 函数体被删、`ReadPS2JS` 延时循环被删）——
但它的**边际收益在快速下降**，而且**和本主线的目标不是同一个东西**：

> `USER.md` 里这条主线的目标 = **重建产物可直接替代原厂二进制跑起来**。
> 它的刻度只能是**运行时**：设备口径下**我们跑到哪、工厂跑到哪、差在哪**。
> 体积比是"静态近似"，而且它对"哪条分支判反了""哪条路径多走了"这类**运行期分歧完全无感**。

**（二）联网查到的标准做法（与项目已有工具完全对上）**

- 固件/嵌入式领域的通行做法：用 QEMU 的 **`-d exec,nochain`** 导出**翻译块执行轨迹**，
  再做两侧轨迹对比；量化指标用 **Jaccard 指数**（共同执行指令 / 并集），
  并做**对齐后找首个分歧**（Laelaps, ACM 10.1145/3427228.3427280）。
- ★ 项目**早就有**这条链路：`tools/qemu_coverage.py`（轨迹→逐函数覆盖，明确写着
  "未覆盖的重量级函数清单 ← 直接驱动下一轮该测什么"）+ `tools/exec_set_diff.py`
  （两侧执行集合差集）。
  ⇒ **不是缺仪器，是我一直在用错刻度。** 这一条要写进"不要重复"。

**（三）把刻度真正读出来（用 CI artifact，不重跑容器）**

下载最近一次全绿运行（`577e5f6b`，run 35512144253）的 artifact（3.1 MB，552 个条目，
含 9 个场景 × 三份 coverage），在本地解析两侧"已执行函数明细"求差：

| 场景 | 工厂已执行 | 我们已执行 | **仅工厂** | 仅我们 |
|---|---|---|---|---|
| A(qemu) | 49 | 48 | 1 | 0 |
| C | 7 | 6 | 1 | 0 |
| C4 / M / N / O / P | 50 | 48 | 2 | 0 |
| **C5（设备真机口径）** | 53 | **75** | 2 | **24** |
| **J（起始屏幕=0 + 合成 root.dat）** | 53 | **75** | 2 | **24** |

**结论 1（最重要，而且是"好消息"）**：**全部 9 个场景里，"工厂执行了我们没执行"的只有 2 个函数**，
且都极小、都已有解释：

    run_process.constprop.0    80 B   ← 我们侧**内联**了它（cmp_calls.py 同侧证据）
    ClearBuffer                32 B   ← 我们侧编译成 `b memset`（尾调用），调用点被换成内联 memset

⇒ **在已观测窗口内，重建产物没有缺失的函数。** 这比"体积比 FAIL 0"硬得多 ——
前者是**运行期**断言，后者只是静态近似。

**结论 2**："仅我们执行" 24 个（C5/J 完全同一批）：
`mui_do_file_list`(1380B) · `ReadUSBJoy`(1196B) · `mui_outputxy_t`(904B) · `GetJoystickConfig`(708B) ·
`mui_DisplayLine_t` · `mui_DisplayThumbnail` · `dispFlip` · `ucrc32` · `get_from_line` ·
`mui_DisplayGameSum` · `ReadJoystick` · `get_item_from_line` · `GetInputInfo` · `mui_WaitNMI` …
按 `exec_set_diff.py` 自己的读法（本文件里既有场景 E 的案例）：**分歧机制就在这一侧**。

**结论 3（红旗，且是新的量化）**：轨迹长度

| 场景 | 工厂轨迹行 | 我们轨迹行 | 比值 |
|---|---|---|---|
| A / C / C4 / M / N / O / P | 10万–21万 | 4万–16万 | **0.39–0.79×（我们更短）** |
| **C5** | 201,256 | **2,229,644** | **11.08×** |
| **J** | 201,109 | **2,201,006** | **10.94×** |

⇒ 只有 C5/J 上我们比工厂多跑 11 倍，且恰好就是"仅我们执行 24 个"的那两个场景。
**读法**：我们进入了一条工厂不走的路径（文件列表 / 手柄配置 / 缩略图 / 字型渲染），
并在这条路径上**长时间自旋**。其余场景我们比工厂短（更收敛）⇒ 不是普遍性膨胀，是**局部**问题。

**结论 4**：工厂自身在 C5 只覆盖 **53/223 = 23.77%**（22.42% 字节）——
未执行的重量级函数里 `mui_setting`/`mui_search`/`PauseMenu`/`SeletEmuCore` 等
**工厂自己也没跑到**。⇒ **覆盖率的绝对数不是我们的短板；观测窗口的深度才是。**
（此前把"我们 33%"当进度、把"没跑到"当"写得不对"，是同一个错误的两面。）

**（四）已做的根源性修复：这一步的自动化**

CI 里"执行集合差集"原先
1. 排在第 17 步 ⇒ **在所有场景之后？不，它在 J/M/N/O/P 之前**；
2. 场景清单**漏了 `qemu_c4` / `qemu_c5`**；
⇒ 设备真机口径与 J/M/N/O/P 的差集**从来没被产出过**（artifact 里只有 `qemu/` 与 `qemu_c/` 两份）。

已修：把它**移到所有场景之后**（第 18 步，门禁之前）、**清单补全为
`qemu qemu_c qemu_c4 qemu_c5 qemu_j qemu_m qemu_n qemu_o qemu_p`**。
⇒ 此后每轮自动产出上面那张表，不需要我再去下载 artifact 手工算。

**（五）下一轮的精确入口（已量化，不需要猜）**

从"仅我们执行"的 24 个里，按字节取下一位：**`mui_do_file_list`(1380 B)**、`ReadUSBJoy`(1196 B)。
> 但**不要**先去读这两个函数本身 —— 按 `exec_set_diff` 的读法，**分歧在"谁在什么条件下调用它"**：
> 取这两个函数的**调用者**，把两侧"到达调用点的那条分支条件"逐条并排对比 ⇒ 目标是定位
> **"哪个条件判反了 / 哪个返回值不同"**，它同时解释"多走 24 个函数"与"轨迹长 11 倍"。

### 16.44 ★★★★★ 换上运行时刻度后的第一个结论：**分歧在"工厂早死"，不在我们**

**背景（16.43）**：我在前几轮把"静态体积比"当进度刻度，边际收益越来越低。换刻度为
**可观测窗口内的两侧执行集合差集**（`tools/qemu_coverage.py` + `tools/exec_set_diff.py`；
CI 已每轮自动产出 9 场景 —— 原先这一步**排在场景 J/M/N/O/P 之前**且清单**漏了 `qemu_c4/qemu_c5`**，
深口径差集从未产出过，已修）。

**结果一（好消息，且是**运行期**断言）**：全部 9 场景里「工厂执行了我们没执行」**只有 2 个**：

| 函数 | 工厂字节 | 解释 |
|---|---|---|
| `ClearBuffer` | 32 | 我们侧编译成 `b memset`（尾调用），调用点本身被替换 ⇒ 不再产生对它的 `bl` |
| `run_process.constprop.0` | 80 | 我们侧内联了它（工厂调的是克隆体）|

⇒ **已观测窗口内，重建产物没有缺失的函数。** 这比任何静态判据都硬（它是执行证据，不是形状证据）。

**结果二（红旗）**：只有 **C5 / J** 两个场景出现「仅我们执行 24 个」+ 轨迹 **11.08×/10.94×** 工厂
（222 万 vs 20 万行）；其余 7 个场景 0.39–0.79×（我们**更短**）。

**归因（本轮的决定性一步）：不是我们的分支判反了，而是工厂在该环境里早死。**

1. **里程碑矩阵**（`tools/milestones.py`）：7/9 场景两侧**完全同步**；只有 C5/J 差集 = `{M6R, M7}`。
2. **C5 的 `behav_diff` + `milestones`**：
   ```
   M6R  资源条目读取   factory ✗(缺:ui.cfg,menu.raw)   rebuild ✓(均读到)   control ✗(缺:…)
   M7   菜单存活       factory ✗(139)                  rebuild ✓(124)      control ✗(139)
   ```
   **控制组（同一份参照二进制复跑）与工厂同判 ✗** ⇒ 可复现、非偶然。
3. **纯 `O|`（guest stdout）序列对齐**（★ 必须只比 `O|`，`E|`（shim stderr）是即时输出、
   `O|` 是缓冲输出，混在一起比会被交织污染）：
   ```
   equal   [0:24] 两侧逐行相同（到 root_path:/sdcard）
   del     factory[24] = "find ui.cfg in .../ui_cn.zip fail"   ← 我们**没打**（即我们读到了 ui.cfg）
   equal   "find font.ttf in .../ui_cn.zip fail"  两侧都有
   repl    factory = "find menu.raw fail" + "find /sdcard/root.dat fail!"
           rebuild = "open /sdcard//.dat fail" ×27 + HID mouse
   ```
4. **崩溃链**：`mui_LoadUIResource(&DAT_003af28c,"menu.raw")` 失败时**不给 `*param_1` 赋值**
   （源码：`else { uVar2 = 0; RARCH_LOG("find %s fail\n",param_2); }`）⇒ `DAT_003af28c` 留 NULL
   ⇒ `mui_menu:75` 的 `memcpy(..., (void*)((int)DAT_003af28c + *DAT_003af28c), ...)` **空指针解引用**
   ⇒ 工厂 **全部 9 个场景 exit=139**。我们读得到条目 ⇒ 活到超时（exit=124）。
5. **我们侧"多跑"的可见症状**：`mui_DisplayThumbnail` 在**空 `file_info_list`** 上循环，
   `sprintf("%s/%s/%s.dat", root_path, puVar4, puVar4)` 里 `puVar4=""` ⇒ **`/sdcard//.dat` 刷屏 27 次**
   （该函数因此进入"仅我们执行"名单 —— 它是**后果**不是原因）。

**⇒ 结论：C5/J 的「24 个多执行函数 + 11× 轨迹」不是重建缺陷，而是
"工厂侧环境坏 → 工厂早死 → 之后只有我们还在跑"的影子。**

### 16.45 ★★★★ 顺带查清：`ui_cn.zip` **是标准 ZIP**，瓶颈在 zip I/O 层而不是文件本身

**动机**：`M6` 在三侧（含工厂）都判 `✓(包已打开(条目缺失))`，看着像"资源包读不出来"。
先把文件本身查清（本地 5 秒）：

```
golden/sdcard_min/ui_cn.zip   4,951,281 B   与原厂 cubegm/ui_cn.zip **逐字节同尺寸**
头 32B  : 50 4b 03 04 ...               ← 标准本地文件头
EOCD    : PK\x05\x06 出现 1 次           ← 标准
zipfile : ★ 打开成功，6 个条目 = ui.cfg / menu.raw / search.raw / setting.raw / type.raw / game.raw
```

⇒ **资源包是好的、是标准的、6 个条目齐全**。而且 `font.ttf` **不在包内**（它是独立文件）
—— 这一点后面变成了判据修复的关键（16.46）。

**那为什么读不出来？** 因为厂商把 EOCD 的签名**换成了运行期全局** `key2`（防篡改）：
`src/upstream/xunzip/unzip.cpp:2903` 的 `unzlocal_SearchCentralDir` 逐个字节比对
`key2[0..3]`／`key2[4..7]`（工厂 rodata 里**没有** `PK` 字面量）。`key2` 在 `.bss`，
别名 `factory_image.S:2085` = `__f_bss_base + 0x2f794` = **0x3E190C（与工厂逐字节一致）**。
`CGM_KEY2_SEED` 把 `50 4b 05 06 50 4b 07 08` 写进去 ⇒ 搜索**能命中** ⇒ `M6` ✓。
⇒ **打开成功、但随后的条目枚举在工厂侧仍失败** —— 这就是 `TUnzip::Unzip`(28 B vs 我们 1608 B) /
`Get` / `Close` 三项**仍在** `tools/upstream_fingerprint_baseline.txt` 台账里的后果
（"第七/第八个真实分歧：上游 XUnzip 版本不符"）。
★ 注意方向：**这一路我们反而更"成功"**，但"更成功"在这里是**保真度差异**，不是优点 ——
判据要求的是**与工厂逐字对齐**（"打开成功/失败"的判定必须同构），而不是"能读出来"。

### 16.46 ★★★★ 仪器修复：新增 **M6R** 里程碑（旧 M6 不具区分度）

- **旧 M6 的硬伤**：判据是"出现过 `find <item> in <path>.zip fail`"。而 `font.ttf`
  **本就不在 `ui_cn.zip` 内** ⇒ **三侧都命中** ⇒ 一律 ✓，把唯一真实的条目读取分歧**完全抹平**。
- **新 M6R（资源条目读取）**：只查**包内应当存在**的条目 —— `ui.cfg`（`get_items_from_zipfile` 取，
  `mui_LoadConfig` 调）与 `menu.raw`（`mui_LoadUIResource` 取，`mui_menu` 调）：
  两者都没报缺 ⇒ ✓；任一报缺 ⇒ ✗ 并列出缺哪个；包没打开 ⇒ ✗(未走到)。
- **为什么这样设计**：探针必须是**该环境里确实应当存在的对象**。用"包内根本没有的文件"当探针，
  判据恒真（本轮就是这样）；反过来用"环境里不可能有的东西"当探针则会恒假。
- **锚点自证**：`tools/milestones.py --selftest` 从 8 → **13 锚点**（新增 5 条 M6R 正负锚点，
  全部取自本轮 CI 实测，含"只缺 font.ttf 不得判缺"这条**正是旧 M6 出错的地方**）。
- **实测生效**（C5 artifact）：
  ```
  M6   UI 资源包打开   ✓(包已打开(条目缺失))   ✓(包已打开(条目缺失))   ✓(包已打开(条目缺失))
  M6R  资源条目读取    ✗(缺:ui.cfg,menu.raw)   ✓(ui.cfg+menu.raw 均读到) ✗(缺:ui.cfg,menu.raw)
  ```
  ⇒ **真信号第一次变得可见**，且控制组与工厂同判（可复现）。

### 16.47 ★★★★ 方法论：**先把"时钟"对准，再谈"写错没写错"**

本轮的通用教训（值得写进技能）：

> **"我们多执行了 N 个函数"是一个极易被误读的信号。**
> 执行集合是**集合**，不含顺序、不含"谁先退出"。参照侧一旦提前退出（崩溃/被信号杀掉/
> 环境缺件），另一侧就会"凭空中多出"一整套它**本该也执行**的函数。
> ⇒ 看到这个信号时的**固定动作**：
> 1. 先看两侧的**终止状态**（`MX`/`M7`）与控制组结论；
> 2. 再做**纯 `O|` 的事件序列对齐**（★ 别把即时输出的 `E|` 混进来），找**首个分歧点**；
> 3. 最后才回到源码看那个分歧点的分支条件。
> 顺序反了，就会把"工厂早死的影子"当成"我们的分支判反了"去改代码。
>
> 配套：**控制组（同一份参照二进制复跑）是唯一能区分"环境缺陷"与"行为分歧"的仪器** ——
> 它判 ✗ 的东西，参照侧的失败就与"重建"无关。

### 16.48 ★★★★★ 新仪器 `tools/exec_align.py`：**首个分歧点**（Laelaps 法落地）

**为什么 `exec_set_diff` 还不够**（它有两个天然盲区）：

1. **执行集合是无序的**："两边都执行了 A 和 B"但顺序相反（A→B vs B→A），集合差集看不出来；
2. **集合不含"谁先退出"**：参照侧提前崩溃时，另一侧会"凭空中多出"一整套函数
   —— 这正是 16.44 里 C5 的误读来源（差集显示"重建侧多跑 24 个"，实际是工厂侧空指针早逝）。

**新工具做三件事**：

| 视图 | 归一方式 | 用途 |
|---|---|---|
| ① 逐次执行 | `函数名+0x偏移` | 最细：同一函数内走了不同路径 |
| ② 按函数名 | `函数名`（丢偏移） | 中等：偏移差异不算分歧 |
| ③ 按函数转移 | 折叠连续重复 → `A→B→C` | 最可读：高层路径是否走偏 |

**关键设计：只对齐"主程序自身代码段"内的执行，并按各自 symtab 归一。**
两侧是**两个不同的二进制**（地址不同、链的 libc/ld.so 也不同）⇒ 地址序列**天然不可直接比**。
所以先按 ELF 的 `PT_LOAD PF_X` / `SHF_EXECINSTR` **过滤掉 libc/ld.so 的帧**，
再用各自的 `SHT_SYMTAB` 归一成 `函数名+偏移` ⇒ 变成可比序列。

★ **字段映射已逐条校验**（建工具前必做）：qemu `-d exec` 行 `Trace N: 0x… [a/PC/c/d] <sym>`
的第 2 个 16 进制字段**就是 PC**，且 qemu 追加的符号名与本仓 symtab **逐条一致**（实测 8/8：

```
pc=0x5080c58  符号=compiler_rt.int.__aeabi_idiv  区间=[0x5080c34,0x5080c64)  ✓
pc=0x500ff84  符号=AudioProcess                   区间=[0x500fe08,0x50100ec)  ✓
```
）。

★ **自证**：`--selftest` **7 个锚点**（对齐原语 5 条正负锚点 + 归一化 + 转移折叠）。
为什么必须有：本工具最容易悄悄失效的一环是"过滤 + 归一"——
过滤区间写错 ⇒ 全部帧被丢（序列为空，**看起来"无分歧"**）；归一写错 ⇒ 序列恒不同。
两者都会产出**看起来正常**的输出 ⇒ 必须由锚点拦。

**★ 为什么必须在"完整日志"上对齐，而不能用现有的 `exec_tail_*`（尾部 800 行）**

C5 实测（同一 artifact）：

| 侧 | 尾部 800 行里落在 libc/ld.so(>=0x3f000000) | 落在自身代码段 | 带符号名 |
|---|---|---|---|
| factory | **652 / 746** | 94 | **0 条** |
| rebuild | 416 / 799 | **383**（`AudioProcess` 274 / `__aeabi_idiv` 109）| 383 |

⇒ 工厂侧的尾部**几乎全是崩溃后的 ld/libc 解体路径**（`bt_factory.txt` 也停在 `_start () from ld-linux-armhf.so.3`）
⇒ 在尾部上对齐只会得到"两侧都已在 libc 里"这种**无意义**结论。**必须用完整日志。**

**CI 接线（`CGM_EXEC_ALIGN=1`，默认关 ⇒ 行为与从前逐字一致）**
- 完整轨迹**不进制品**（rebuild 侧可达 ~160 MB）：开关打开时把它从 `$OUT` 移到 `$OUT` **之外**的
  `$EXEC_KEEP`（默认 `/tmp/cgm_exec_keep`），对齐完**立即 `rm -rf`** ⇒ 磁盘占用被限制在"一个场景"内。
- 调用点在**所有 `run_side` 之后**（两侧日志都还在）、`milestones.py` 之前；小结（几 KB）写进
  `$OUT/exec_align.txt`，随场景目录自动进制品。
- 已对 **C5 与 J**（唯二分歧场景）打开；其余场景是一词之改。

### 16.49 ★★★ exec_set_diff 的**解读护栏** —— 把纪律写进仪器，而不是留在文档里

教训（16.44）：差集显示"重建侧多跑 24 个函数"，我第一反应是"我们的分支判反了"。
**但执行集合是无序集合、不含"谁先退出"** —— 参照侧一崩，另一侧就会凭空中多出一整套函数。
把这条纪律写在 GAP 里没用（下轮照样会误读），所以直接写进工具的输出：

```
  ★★ 解读前置条件（**先读这一块，再看上面的清单**）：
     执行集合是**无序集合**，不含"谁先退出" —— 参照侧一旦提前退出（崩溃/被杀/环境缺件），
     重建侧就会"凭空中多出"一整套它**本该也执行**的函数，看着像"我们走错了分支"。
     本场景终止：factory=139(被信号终止)  rebuild=124(活着)  control=139(被信号终止)
     ⚠️ 两侧终止形态不同，且**控制组与 factory 同判 139 ⇒ 参照侧失败可复现** ——
        本场景的「仅我们执行」清单**不能当作重建侧的分支分歧证据**，
        它更可能是"参照侧环境缺陷导致其早逝"的影子。
```

它读同场景的 `behav_{factory,rebuild,control}.json` 取 `exit_code`，并按三种情形给不同结论：
两侧同形态 / 形态不同但控制组与 factory 同判（可复现 ⇒ 环境缺陷）/ 控制组与 factory 不同判（⇒ 参照侧不确定，一切结论不可信）。
⇒ **"控制组"是唯一能区分"环境缺陷"与"行为分歧"的仪器**，现在它被强制出现在每一份差集报告里。

### 16.50 ★★★★ `exec_align` 首跑暴露的**仪器缺陷**：两个二进制**不能从下标 0 对齐**

**首跑结果**（CI `20ba70e4`，C5）：三个视图**全部**报"首个分歧点 = 第 1 次（0 基）"：

| 视图 | factory | rebuild |
|---|---|---|
| ① 逐次执行 | `main+0x1ec` | `_init+0x8` |
| ② 按函数名 | `main` | `_init` |
| ③ 按函数转移 | `main` | `_init` |

**这是仪器缺陷，不是发现**：两个**不同的二进制**的 **CRT / loader 前导天然不同**
（链的 crt 版本、ld.so、`_init`/`__libc_csu_init` 布局都不一样）⇒
从下标 0 比**必然**立刻分歧，于是整份报告退化成"两侧入口不同"这种废话，
**真正的分歧点被前导噪声顶掉**。

**修法：锚点对齐**（`--anchor`，默认 `main`）
- 取两侧**共有的那一个"实质"符号**（默认 `main`；定不到时退化为"factory 侧首个非 CRT 且 rebuild 也有的符号"），
  从它各自**首次出现**的位置开始比；
- 锚点**之前**的差异只作**信息性**记录（"前导执行数 factory N / rebuild M"），**不参与判决**；
- **定不到锚 ⇒ `INCONCLUSIVE`（exit 3）**，绝不输出"无分歧"这种假绿。
- `CRT_RE` 排除：`_init/_fini/_start/__libc_csu_*/__libc_start_main/__ARMv7ABSLongThunk_*/_dl_*/`
  `frame_dummy/*_tm_clones/__do_global_dtors_aux/__gnu_*/@nosym/@0x*`。
- `--selftest` 从 7 → **11 个锚点**（新增：CRT 识别 10 项、定锚（默认 main）、
  **"锚点之后应无分歧（前导差异不得算进判决）"**、**"两侧只有 CRT 符号 ⇒ 必须 INCONCLUSIVE"**）。
  ★ 第 3 条正是首跑错的那个地方；第 4 条防的是"定不到锚却报绿"。

### 16.51 ★★★★★ C5 的 **zip 路径关键地址普查**：18 个判决点，一次跑完钉死工厂走了哪条分支

**为什么不再继续推理**：已知链是硬的 ——
`OpenZipU` 成功 ⇔ `unzOpenInternal` 返回非 NULL ⇔ **EOCD 搜索 + 中央目录解析都成功**；
而工厂**仍然"找不到"包内确实存在的条目**（打了 `find ui.cfg … fail`），我们找到了。
⇒ 失败点**只能**在「逐条读中央目录项的**文件名**并比对」这一段。
再往下推理就是猜，所以改用项目**已有**的仪器：`CGM_TRACE_ADDRS`（关键地址命中普查，
`ci_qemu_behav.sh` 在**删完整日志之前**逐地址 `grep -c`）。

**地址清单**（工厂侧绝对地址，取自 `factory.rkgame.bin` 的 `SHT_SYMTAB`）：

| 地址 | 含义 |
|---|---|
| `00010fec` | SearchCentralDir：**命中**（算出了 EOCD 位置）|
| `00011064` | SearchCentralDir：**短读 ⇒ 返回 0**（`lufread != 1`）|
| `00010ff8` | SearchCentralDir：循环结束仍未找到 / malloc 失败 ⇒ 返回 0 |
| `00010ed8` | SearchCentralDir：入口 seek 失败 ⇒ 返回 0 |
| `0001168c` | `unzOpenInternal` 入口 |
| `00011074` | `unzGetGlobalInfo` 入口（`unzLocateFile` 循环前先取 `number_entry`）|
| `0001162c` | `unzGoToFirstFile` 入口 |
| `00011868` | `unzGoToNextFile` 入口（**命中次数 = 循环迭代了几次**）|
| `000110d4` | `unzlocal_GetCurrentFileInfoInternal` 入口（每次读一条中央目录项）|
| `0001190c` | `unzLocateFile` 入口 |
| `00010ea0` | `unzStringFileNameCompare` 入口（大小写不敏感比对，仅 16 B）|
| `00012608` / `000128dc` | `TUnzip::Open` / `TUnzip::Find` 入口 |
| `00012cd0` / `00012ebc` | `OpenZipU` / `FindZipItemA` 入口 |
| `00017e9c` | `mui_LoadUIResource`：`FindZipItemA != 0` ⇒ **"找不到条目"** |
| `00017eb4` | `mui_LoadUIResource`：`OpenZipU == 0` ⇒ "打不开" |
| `00017e48` | `mui_LoadUIResource`：**成功**路径 |

**读法（已写进 workflow 注释）**：先看 `00010fec` 与 `00011064` 哪个非零 —— 直接区分
"EOCD 没搜到"与"搜到了但条目比对失败"；再看 `000110d4` / `00011868` 的次数：
若各约 6~7 次 ⇒ 循环确实遍历了全部 6 个条目而名字没匹配上（问题在**文件名字段读取**或**比对函数**），
而不是"没进循环"。

### 16.52 ★★★★★ 本轮最值钱的产出：**四个"仪器自身的静默失效"**（全部当场踩到并修掉）

| # | 失效 | 症状 | 修法 / 纪律 |
|---|---|---|---|
| 1 | **连续两次 `write` 用同一个原始字符串** | 第二次把第一次的替换**覆盖**掉；而脚本**照样打印了 ✓** ⇒ 地址清单被静默丢弃 | 累积到 `s`、**最后只写一次**；★ **写完必须独立校验**（读回文件 grep 一遍），不信脚本自己的 ✓ |
| 2 | **shell heredoc 把 `\\` 变成 `\`** | Python 三引号串里 `\<换行>` 是**行接续**（吞掉换行）⇒ 锚点**永远**匹配不上 | 带反斜杠的补丁脚本**一律写成文件再执行**（`"$PY" patch.py`），不经 shell 转义层 |
| 3 | **地址必须 8 位十六进制** | 写成 6 位 `010fec` ⇒ `grep "/010fec/"` 与轨迹里的 `/00010fec/` 不相等 ⇒ **恒 0 命中**；而"0 命中"**看起来恰好等于**"这条分支没走到" ⇒ **会把结论带向完全相反的方向** | 一律 `'%08x' % addr`；并在 workflow 注释里写明这条 |
| 4 | **0 命中缺少"阳性对照"** | `grep` 的 0 命中有两种含义：① 该分支真没走到；② **普查链路本身坏了**。没有阳性对照就**分不清** | 普查清单里**必须放一个已知必然命中的地址**。本项目的天然阳性对照：`00017dac`(`mui_LoadUIResource` 入口) 与 `00012ebc`(`FindZipItemA` 入口) —— 工厂打了 `find ui.cfg … fail`，这两条链**一定**都进过 |

**共性（一句话）**：
> **"看起来正常"的输出是最危险的输出。** 这四条都不是"程序报错"，而是"程序给了我一个
> **读起来合理、但方向相反**的结论"。⇒ 纪律：任何新仪器/新判据上线，必须
> ①带**正负双向锚点**自证；②**产物与写入分离校验**（写完读回来 grep）；
> ③**关键量必须有阳性对照**。三者缺一，就要靠人肉发现错误 —— 而这次是靠人肉发现的三次。

### 16.53 状态与下一步

- 提交：`ed628ede`（exec_align 首上线）→ `20ba70e4` → `0a7c9e27`（锚点对齐修复）→
  `a422859f` → **`37748097`**（8 位地址普查，CI 运行中，已挂监控）。
- 另一条并行的确认：**"仅工厂执行/仅我们执行"在两个场景之外全为 0** 的结论在
  `exec_align` 上线后仍成立（C5/J 的 24 个多执行函数 = 工厂早逝的影子）。
- **下一步（唯一入口）**：读 `37748097` 的普查表 ⇒ 工厂侧 zip 枚举失败的**精确分支**；
  若 `00010fec > 0`（EOCD 搜到了）而 `000110d4`/`00011868` 约为 6~7 次
  ⇒ 问题在**中央目录项的文件名字段读取**或 `unzStringFileNameCompare`，
  那正好落在 `TUnzip::Get`(152 B + `.part.5` 888 B) / `unzlocal_GetCurrentFileInfoInternal`(1304 B)
  这两个"上游版本不符"的台账项上 —— 与 `tools/upstream_fingerprint_baseline.txt` 的剩余三项汇合。

### 16.54 ★★★★★ **根因定位：我们 vendor 了错的 `unzip.cpp` 变体**（一次机械对拍解决，而不是继续逐符号手工对齐）

**先承认绕圈的模式**：过去几轮我在**逐符号手工对齐** `src/upstream/xunzip/unzip.cpp`
（第 45 轮修 `TUnzip::Open`、第 46 轮改 `TUnzip::Unzip`、…），每轮还要再配一件新仪器。
而项目**已经有一条被证明有效的机械方法**：编译口径 `-Os` 是怎么定的？
——「**同一份源码 × 逐个候选配置 → 编译 → 解 `SHT_SYMTAB` 逐函数比 size**」，一次命中到字节。
我把这条方法只用在了编译选项上，**没想到可以用在"库版本"上**。

**★ 决定性线索（在我自己文件的头部注释里）**：

```
src/upstream/xunzip/unzip.cpp:3   原始来源：Wischik zip_utils 的 **tomyqg/helix_mp3 变体** unzip.cpp
                            :10   新增：ZIPENTRYW + GetZipItemW/FindZipItemW（**工厂有，本变体缺失**，按…重建）
```

⇒ **工厂用的不是 helix_mp3 变体，而是 Wischik 原版** —— 而**原版就在仓里**
（`src/upstream/zip_utils.zip!unzip.cpp`，144,408 B，2004-06-25）。

**实验（`tools/zipver_sweep.py`，本地 ~1 分钟）**
口径：`zig c++ -std=gnu++14 -Os -target arm-linux-gnueabihf.2.29`（与原厂 GCC 6.2 的默认方言一致；
★ 原版含 `register`，`-std` 不对连编译都过不去 —— 方言也是"口径"的一部分）。

| 符号 | 工厂 | **原版 Wischik** | 现用(helix_mp3) |
|---|---|---|---|
| `unzStringFileNameCompare` | 16 | **16 (1.00)** ✅ | 140 (8.75×) |
| `unzClose` | 60 | **60 (1.00)** ✅ | 144 |
| `unzGetGlobalInfo` | 32 | **32 (1.00)** ✅ | 44 |
| `unzGoToFirstFile` | 96 | **96 (1.00)** ✅ | 100 |
| `unzlocal_DosDateToTmuDate` | 64 | **64 (1.00)** ✅ | 72 |
| `unzGetCurrentFileInfo` | 64 | **64 (1.00)** ✅ | 68 |
| `unzlocal_getByte` | 92 | **100 (1.09)** | 212 (2.30×) |
| `unzlocal_getShort` | 96 | **92 (0.96)** | 376 (3.92×) |
| `unzlocal_getLong` | 156 | **152 (0.97)** | 720 (4.62×) |
| `unzGoToNextFile` | 164 | **160 (0.98)** | 172 |
| `SearchCentralDir` | 452 | **416 (0.92)** | 844 (1.87×) |
| `unzOpenInternal` | 476 | **500 (1.05)** | 524 |
| `GetCurrentFileInfoInternal` | 1304 | **1100 (0.84)** | 1428 |
| `unzLocateFile` | 240 | **292 (1.22)** | 528 (2.20×) |
| `unzeof` / `unztell` | 44 / 36 | **36 (0.82) / 28 (0.78)** | 56 / 48 |
| `TUnzip::Close` | 68 | **56 (0.82)** | 168 (2.47×) |

**⇒ 原版在 ±33% 内命中工厂 `20 / 25`（80%），其中 6 个精确到字节；
   而现用的 helix_mp3 变体几乎每一行都偏 2×** —— 这就是那串"系统性 2× 偏差"的来源。

**★ 但工厂 ≠ 纯原版**：5 处方向明确的改动（原版 → 工厂）
1. `unzOpenCurrentFile`：原版 **双参** `_Z18unzOpenCurrentFileP5unz_sPKc`(440 B) → 工厂 **单参**
   `_Z18unzOpenCurrentFileP5unz_s`(316 B) ⇒ **砍掉了 password 参数**（内嵌加密能力被裁）；
2. `TUnzip::Find`：原版 `...PKcb...`（**bool**）→ 工厂 `...PKch...`（**unsigned char**）
   （★ 现用变体**这一点已经改对了**，文件头注释有记）；
3. `TUnzip::Unzip`：原版 848 B 单一大函数 → 工厂 **28 B + `.part.7`(488 B)**
   ⇒ "薄封装 + GCC 冷热分割"；
4. `TUnzip::Get`：原版 920 B → 工厂 **152 B + `.part.5`(888 B)**，同上；
5. `TUnzip::Open`：原版 192 B → 工厂 **84 B**。

**⇒ 最优解（下一步的唯一入口）**：把 vendored 源从 helix_mp3 变体换成
**「Wischik 原版 + 上述 5 处工厂改动」**，并保留项目已用机器码核实过的三处增量
（POSIX 垫片 / `key2` 全局 + 改写的 `unzlocal_SearchCentralDir` / `zopenerror` 别名）。
**验收标准已量化**：`python3 tools/zipver_sweep.py` 的命中率要从 **~0/25 → ≥23/25**。
这是一次**结构性替换**，能一次性消掉整族偏差，而不是像现在这样逐符号手工对齐。

### 16.55 ★★★★★ 关键地址普查**正面证实**了同一处根因（两条独立证据链汇合）

第一轮不接 `CGM_TRACE_ADDRS` 时地址写成了 6 位（见 16.52 #3）⇒ 全部恒 0 命中；
改成 8 位后重跑（CI `37748097`），**工厂侧**结果（control 侧逐字相同 ⇒ 可复现）：

| 地址 | 含义 | factory | control |
|---|---|---|---|
| `00012ebc` | **阳性对照** FindZipItemA 入口 | **4** | 4 |
| `00017e9c` | **阳性对照** mui_LoadUIResource「找不到条目」分支 | **1** | 1 |
| `00010fec` | SearchCentralDir **命中（算出 EOCD 位置）** | **1** | 1 |
| `00011064` | SearchCentralDir 短读 ⇒ 返回 0 | **0** | 0 |
| `000110d4` | `GetCurrentFileInfoInternal` 入口 | **1** | 1 |
| **`00011868`** | **`unzGoToNextFile` 入口** | **0** ← **循环一次都没迭代** | 0 |
| **`00010ea0`** | **`unzStringFileNameCompare` 入口** | **0** ← **从未比对过** | 0 |
| `0001190c` | `unzLocateFile` 入口 | 4 | 4 |
| `00017eb4` / `00017e48` | OpenZipU==0 分支 / 成功分支 | 0 / 0 | 0 / 0 |

**读法（先看阳性对照 ⇒ 普查链路是通的，0 才可信）**：
- **EOCD 搜到了、包打开了**（`00010fec`=1，`00011064`=0）—— 与"没打 `open ... fail`"一致；
- **`GetCurrentFileInfoInternal` 只被调 1 次、`unzGoToNextFile` 0 次、`unzStringFileNameCompare` 0 次**
  ⇒ **工厂的 `unzLocateFile` 在"读第一条中央目录项"这一步就失败返回
  「列表结束」**，于是 `Find` 报 NOTFOUND → 打 `find menu.raw fail`
  → `mui_LoadUIResource` 失败**不给 `*param_1` 赋值** ⇒ `DAT_003af28c` 留 NULL
  ⇒ `mui_menu:75` 空指针 ⇒ **工厂 exit=139**（16.44 的链）。
- ⇒ **失败点正是"中央目录项的文件名字段读取"** —— 而这一族的实现
  （`unzlocal_getByte/getShort/getLong`、`GetCurrentFileInfoInternal`、`unzLocateFile`）
  **恰好全部在那张 2× 偏差表里**。**两条独立证据链（版本对拍 + 地址普查）汇合到同一处根因。**

**★ `exec_align`（锚点对齐后）给出的第三个独立视角**（C5，锚点 = `main`）：
- 锚点之后 factory 84077 次执行 / 73785 次转移；rebuild 1353162 / 463844（我们活得久）；
- **符号集合差集（排除 CRT）**：
  · 仅 factory：`unzGoToFirstFile`、`unzlocal_getByte`、`lufopen/lufseek/luftell/lufclose`、`ClearBuffer`、`mxml*`
  · 仅 rebuild：**`UnzipItem` + `inflateInit2/inflate_fast/inflate_codes/huft_build`**、`ReadUSBJoy`、`GetJoystickConfig` …
  ⇒ **我们真的解压了（跑了 inflate），工厂连第一条目录项都没读出来**。
- ⚠️ 已知残留：视图 ①/②/③ 的首个分歧点仍在锚点后第 1~2 次（factory `@nosym` vs rebuild
  `__ARMv7ABSLongThunk_puts`）—— 那是 **crt/PLT 垫片层的差异**，锚点取 `main` 还不够深。
  ⇒ 改进方向：锚点改用**业务函数**（如 `main_Menu`），或锚点后跳过前 K 帧。

### 16.56 ★★★★★ 真根因：**`XUnzip.o` 从未被重新编译过** —— 并且**更正 16.54 的错误结论**

#### 一、先更正：上一轮（16.54）的结论**是错的**

16.54 写的根因是「我们 vendor 了错的 `unzip.cpp` 变体（helix_mp3 而非 Wischuk 原版）」。
**这个结论建立在错误的数据上**：当时的"我们"一列读的是 `build/rkgame.rebuilt.elf`，
而它链接的是一个**陈旧的 `XUnzip.o`**，并非当前 `unzip.cpp` 的产物。

⇒ 实测（同一份源码、项目口径、0.96 秒）：

| 来源 | zip 符号命中工厂 ±15% | 精确到字节 |
|---|---|---|
| **仓库里那个 `XUnzip.o`（一直被链接）** | **11 / 30** | 0 |
| **同一份源码用项目 CFLAGS 现编** | **21 / 30** | **7** |

**⇒ 源码本来是对的。**"整族偏 2×"不是变体的错，是**对象陈旧**。
（16.54 的实验本身没错——原版确实也接近工厂 20/25——但由此推出的"我们的源不对"是错的。）

#### 二、真根因（三层，逐层都有机器码级证据）

**层 1：对象与源码不符。** 仓库里的 `XUnzip.o` = **147,896 B**，带 **7 个 `.debug_*` 节**。

**层 2：它是 `-O1` 时代的产物（决定性证据）。**

| 编译口径（同一份 `unzip.cpp`） | 对象大小 |
|---|---|
| `-O1` | **147,896 B** ← **与那个陈旧对象逐字节同尺寸** |
| `-Os` | 39,476 B ← 与工厂命中 27/41 |

**层 3：为什么 `-Os` 修改没修到它 —— 哈希钉永久失效。**

```
unzip.cpp 当前哈希 : 9ee99732b8e96f6fed0ba67eded0118feac1fe97ad7f75275159c4731df78a69
.sha256 里记录的  : 9ee99732b8e96f6fed0ba67eded0118feac1fe97ad7f75275159c4731df78a69
★ 相同 ⇒ 每轮都判定「无需重编」
```

⇒ GAP 16.33 把编译口径从 `-O1` 改成 `-Os` 时，**`XUnzip.o` 被哈希缓存豁免**，
于是 `-Os` 修复在整个 XUnzip 库里**从未生效**。这不是"又发现一个新 bug"，
而是**16.33 那次修复漏掉的一个洞**。

**层 3 的放大器：失败只打印不中止。**
旧逻辑 `... && { echo "已编译"; } || echo "编译失败"` —— 编译失败**只打印一行**就继续；
而 `link_full.sh` 见 `.o` 存在照样链接；`push_1to1.py` 又专门为它开了"**必须入库**"的例外
⇒ 陈旧对象被**永久钉死在仓库里**。这就是同一根因**三次复发**的完整链条：
① 只在 `.o` 缺失时编 → ② 改成 `-nt` 比时间戳（checkout 后两边 mtime 相同，判定不可靠）
→ ③ 改成源码哈希缓存 + 为 `.o` 开入库例外。

#### 三、修复（三处，都很小）

| 文件 | 改动 | 理由 |
|---|---|---|
| `tools/link_audit.sh` | **去掉哈希缓存，每次必重编**；编译失败 ⇒ 删目标 + `exit 1` | 编译 **0.96 秒**，任何缓存的收益都远小于"静默陈旧"的风险；失败必须硬失败（否则链接到旧对象） |
| `tools/push_1to1.py` | 删掉 `XUnzip.o` 的"必须入库"例外 | 构建产物一律不入库 —— 入库就等于把陈旧对象钉死 |
| `.gitignore` | 登记 `src/upstream/xunzip/*.o` | 同上（本仓库走 API 推送，此项仅为声明） |
| **`tools/check_obj_fresh.py`（新门禁）** | 现编一份 → 与磁盘对象/链接产物逐符号对拍；并检查 push 脚本未开例外 | 同一根因已复发三次，必须机械拦截 |

#### 四、效果（链接产物，端到端）

| | zip 层符号命中工厂 ±15% | 精确到字节 |
|---|---|---|
| 修复前 | **11 / 41** | 0 |
| **修复后** | **27 / 41** | **7** |

7 个精确到字节：`unzStringFileNameCompare` 16=16 · `unzClose` 60=60 ·
`unzGetGlobalInfo` 32=32 · `unzGoToFirstFile` 96=96 · `unzGetCurrentFileInfo` 64=64 ·
`unzlocal_DosDateToTmuDate` 64=64 · `IsZipHandleU` 28=28。

其余偏差已定性（不再需要逐个手工猜）：

| 符号 | 工厂 | 我们 | 性质 |
|---|---|---|---|
| `TUnzip::Unzip` | 28 + `.part.7` **488** = **516** | 472 | **GCC 冷热分割**（clang 不分段）⇒ 总量 0.91×，语义一致 |
| `TUnzip::Get` | 152 + `.part.5` **888** = **1040** | 852 | 同上（0.82×） |
| `unzlocal_SearchCentralDir` | 452 | 668 (1.48×) | 我们的 key2 实现比工厂多做事（**下一轮入口**）|
| `GetCurrentFileInfoInternal` | 1304 | 956 (0.73×) | 疑同类分段，待核 |
| `inflate_fast` | 1140 | 776 (0.68×) | 内嵌 zlib 版本差异 |
| `CloseZipU/FindZipItemA/GetZipItemA/UnzipItem` | 140/132/112/132 | 112/84/68/84 | **我们自研的 C 包装**（0.61~0.80），待核 |

#### 五、★ 方法论（比这次修复本身更值钱）

> **"缓存 + 静默失效"是这类项目最贵的一类 bug。**
> 判据全部建立在"产物"之上（symbol size / 反汇编 / 重定位），
> 而一个**陈旧的对象**会让所有判据**不报错、只给出方向相反的结论** ——
> 本项目因此把"源码不对"当成根因，做了一件完全没必要的大改（16.54）。
>
> 三条纪律：
> 1. **构建产物一律不入库。** 入库 = 给它一个"永远可用"的假象。
> 2. **缓存必须在"源 × 工具链 × flags"三元组上失效**，而不仅是源哈希；
>    更稳的做法是：**只要编译够便宜（<2 秒），就不要缓存**。
> 3. **任何"会跳过一段构建"的开关，都必须配一条能证明"产物与输入一致"的门禁。**
>    本项目的门禁 = `tools/check_obj_fresh.py`（现编一份逐符号对拍）。

### 16.57 ★★★★ 新门禁首跑连挂两轮 —— **门禁自身的两条脆弱性**（比它防的风险更贵）

`tools/check_obj_fresh.py` 上线后，`1to1-qemu-behav` **连续两轮失败**，而它要防的那个风险
（陈旧对象）**从未发生**（判据 1 两次都 PASS）。两次失败都出在**辅助判据 2**：

| 轮次 | 判据 2 的写法 | 失败原因 |
|---|---|---|
| `635fcc29` | 查 `ROOT/.gitignore` 是否排除 `*.o` | **CI 里 `.gitignore` 在仓库根**，而脚本的 `ROOT` 是 `1to1/` ⇒ 文件不存在 ⇒ 恒 FAIL |
| `39b6b98e` | 查 `tools/push_1to1.py` 里有没有 `.o` 跳过规则 | **`push_1to1.py` 因含 token 本来就不推送** ⇒ **CI 里这个文件根本不存在** ⇒ 恒 FAIL |

**两次的共同点：判据依赖了一个"在 CI 里不存在（或位置不同）的文件"，于是恒假。**
第二次我甚至先入为主地归因为"字符串匹配写错"（`.o"` vs `".o",`），实际是**文件不存在**。

**代价（这次比风险本身贵得多）**：
- 两轮 CI 全废（每轮 8~12 分钟）；**每轮还把后面 10 个运行时观测场景全部 `skipped`**
  —— 正是项目在 GAP 16.32/16.35 已登记过的同一个教训：**静态门禁不该阻塞运行时观测**。
  已把它从"构建之后（fail-fast）"挪回**静态门禁组**（所有观测之后）。

**修法（两条纪律）**：
1. **门禁不得依赖"可能不在 CI 里的文件"** —— 尤其：含 token 的脚本（`push_1to1.py`）、
   `.gitignore`（位置随仓库布局变）、本地才有的路径。**要依赖就先判存在性并降级为提示。**
2. **一条门禁只留一条硬判据。** 判据 1（"现编对象 vs 磁盘对象/链接产物 逐符号对拍"）
   已**双向自证**（喂 `-O1` 对象 ⇒ `exit 2`；喂正确对象 ⇒ `exit 0`；模拟 CI 环境 ⇒ `exit 0`），
   其余检查**全部降为提示**。
   > 理由很直白：**一条脆弱的辅助判据把整轮 CI 烧掉，代价远大于它想防的风险。**

**新纪律（已写进技能）**：
> 门禁上线前必须做**三态自证**：① **正常态**（应 PASS）② **缺陷态**（应 FAIL）
> ③ **CI 近似态**（把"CI 里不存在的文件"临时挪走，仍必须 PASS）。
> 只做前两条会漏掉"依赖缺席文件导致恒假"这一类 —— 本次就是②通过、③没做。

### 16.58 ★★★ 顺带确证：CI 侧已真的开始重编 `XUnzip.o`

`39b6b98e` 的门禁日志（失败轮，但**判据 1 的输出有效**）：

```
[编译器] /home/runner/.local/lib/python3.10/site-packages/ziglang/zig  （来源：env CC）
[现编] XUnzip.fresh.o  (39476 B)
[仓库/构建对象] src/upstream/xunzip/XUnzip.o  (39476 B)
[判据1] 现编对象 vs 磁盘对象：比对 31 个 zip 符号，**不一致 0 个**   ✓
[判据1b] 现编 vs **链接产物**：比对 31 个，不一致 0 个              ✓
```

⇒ ① `link_audit.sh` 的"每次必重编"在 CI 上生效（`39476 B` = `-Os` 新对象，不再是 `147896 B` 的 `-O1` 旧物）；
   ② 判据 1 的**编译器多级解析**在 CI 上命中 `env CC`（不必依赖本地 Windows 路径）。

### 16.59 ★★★ CI 构建步骤**吞掉了 link_audit.sh 的返回码** —— 新加的硬失败形同虚设

`link_audit.sh` 改成交付"编译失败 ⇒ `exit 1`"之后，发现 CI 里那一行是：

```sh
PY=python3 sh tools/link_audit.sh report/link_audit.txt || \
  echo "[warn] link_audit 非零（对象已产出，继续）: rc=$?"
```

⇒ **返回码被 `||` 吞掉**（注释还写着"它自身的门禁结论由 1to1-verify 负责，这里只为拿对象，故 rc 不强判"）。
于是本步里新加的硬失败**不生效**。

**修法**：加一条**基于文件存在性**的直接断言（不看 rc，因为 rc 被吞了）：

```sh
[ -s src/upstream/xunzip/XUnzip.o ] || { echo "::error::XUnzip.o 未产出（源码编译失败）—— 禁止继续（否则会链接到陈旧对象）"; exit 1; }
echo "XUnzip.o 就绪：$(wc -c < src/upstream/xunzip/XUnzip.o) B"
```

（`1to1-verify` 侧另有 `[ "$rc" = "0" ] || exit "$rc"` 的强判，两处互补。）

★ 教训：**给某个脚本加了硬失败之后，必须去它的每个调用点确认返回码没有被吞** ——
否则"我加了门禁"只是心理安慰。

### 16.60 ★★★★★ 第二轮关键地址普查：**把 zip 解析失败断在 `GetCurrentFileInfoInternal` 内部**

**第一轮（19 个地址）已经把链条收到一个函数**，且四个数字互相印证：

| 地址 | 符号 | 命中 |
|---|---|---|
| `00010fec` / `00010ff8` | SearchCentralDir **命中** / **成功返回** | **1 / 1** |
| `0001168c` | `unzOpenInternal` | **4** |
| `0001162c` | `unzGoToFirstFile` | **1** |
| `000110d4` | `unzlocal_GetCurrentFileInfoInternal` | **1** |
| **`00011074`** | **`unzGetGlobalInfo`** | **0** |
| **`00011868`** | **`unzGoToNextFile`** | **0** |
| **`00010ea0`** | **`unzStringFileNameCompare`** | **0** |
| `0001190c` | `unzLocateFile` | **4** |

**这四个数字精确吻合原版源码的一条 early-return**（`_pristine/unzip.cpp:3247`）：

```c
int unzLocateFile (unzFile file, const char *szFileName, int iCaseSensitivity)
{ ...
  s=(unz_s*)file;
  if (!s->current_file_ok)                              // ← 3246-3247
      return UNZ_END_OF_LIST_OF_FILE;
  ...
  err = unzGoToFirstFile(file);                         // ← 3252
  while (err == UNZ_OK) { ... unzStringFileNameCompare ... }
```

推断（唯一能同时解释 4:1:0:0 的序列）：
1. `unzOpenInternal` 打开 `ui_cn.zip` 成功（SearchCentralDir 命中 ⇒ EOCD 找到、EOCD 字段读完）；
2. `unzOpenInternal:2954` 末尾调 `unzGoToFirstFile`（**那 1 次**）→ 它调
   `unzlocal_GetCurrentFileInfoInternal`（**1 次**）**失败** ⇒ `current_file_ok=false`；
3. 之后 **4 次** `unzLocateFile` 全部在第 3247 行**直接 return** ⇒ 于是 `GoToNextFile`=0、`Compare`=0。
4. `unzGetGlobalInfo`=0 也吻合（`unzOpenInternal` 是直接赋值 `s->gi.number_entry`，不调该函数）。

**⇒ 唯一失败点 = `unzlocal_GetCurrentFileInfoInternal` 的首次调用。**
**⇒ 第二轮普查（新增 7 个地址，共 26 个）把这个函数内部切开**（工厂侧地址）：

| 地址 | 含义 |
|---|---|
| `00010b74` | `lufseek` 入口 |
| **`0001111c`** | **`lufseek` 失败标记**（`mvn r4,#0`）—— 命中 >0 ⇒ **seek 就失败** |
| `00011144` / `00011158` | 第 1 / 第 2 个字段读取失败标记（`mvnne r4,#0`） |
| `00010d24` / `00010d84` | `unzlocal_getShort` / `unzlocal_getLong` 入口 |
| `00010cc8` | `unzlocal_getByte` 入口（底层读字节；命中次数直接反映"读了几次就断"） |

**两条互斥结论由 `0001111c` 一票区分**：
- `>0` ⇒ seek 失败 ⇒ 问题在 `pos_in_central_dir` / `byte_before_the_zipfile` 的**计算**
  （`unzOpenInternal` 里 `byte_before_the_zipfile = central_pos + fin->initial_offset - (offset_central_dir + size_central_dir)`）；
- `=0` 且 `00011144/00011158 > 0` ⇒ seek 成功但**字段读短** ⇒ 问题在 `fread`/短读。

### 16.61 ★★★ 已定性的一处**保真度差异**：`lufread` 内存分支少了厂商的 `spi_memcpy` 钩子

并排反汇编（工厂 `lufread` 168 B / 40 条 vs 我们）发现工厂的内存分支付多一层**运行期开关**：

```asm
17| ldr r2,[pc,#92]      ; GOT 槽
18| ldr r3,[r3,r2]       ; r3 = 指向某全局的指针
20| ldr r3,[r3]          ; r3 = 该全局的值
21| cmp r3,#0
24| bne L_spi
25| bl  @memcpy@plt
33| L_spi: bl @spi_memcpy      ; ← 工厂多这一支
```

而工厂的 `spi_memcpy` @ `0x29ce4` **只有 4 字节 = 空函数**（`bx lr`）。
我们的移植（`unzip.cpp:2696-2701`）**硬编码 `memcpy`，没有这个开关**。

**★ 但它不是本次失败的原因**（已排除，避免错误归因）：
该分支在 `flags==1`（内存缓冲）时才走，而 `ui_cn.zip` 是
`OpenZipU(path,0,2)` ⇒ `flags==2` ⇒ `lopen` 里走 `fopen("r+b")` 的 **FILE\*** 分支。
⇒ 登记为**待收口的保真度差异**（若将来有调用点传 `flags==1`，行为会不同），
本轮**不去改它**（改了也无法由当前观测窗口验证）。

★ 同时记一条**纪律**：发现"看起来能解释一切的机制"（SPI 钩子+空函数）时，
**必须先确认它所处的分支是否真的会被走到** —— 我差点把它当成结论写进 GAP。
本次靠"`ui_cn.zip` 走 FILE\* 分支"这条硬事实当场否掉。

### 16.62 ★★★ 工厂 `GetCurrentFileInfoInternal` **被厂商删掉了 magic 比对**（反汇编逐条证实）

`_Z35unzlocal_GetCurrentFileInfoInternal…` @ `0x110d4` 前 9 条调用序列：

| 序 | 工厂指令 | 对应原版源码 |
|---|---|---|
| 1 | `bl @unzlocal_getShort` @0x11134 | `version` |
| 2 | `bl @unzlocal_getShort` @0x11148 | `version_needed` |
| 3 | `bl @unzlocal_getShort` @0x1115c | `flag` |
| 4 | `bl @unzlocal_getShort` @0x11170 | `compression_method` |
| 5 | `bl @unzlocal_getLong`  @0x11184 | `dosDate` |
| 6 | `bl @DosDateToTmuDate`  @0x11198 | 同名 |
| 7 | `bl @unzlocal_getLong`  @0x111a4 | `crc` |

而原版 `unzip.cpp:3040-3044` 在 `version` **之前**还有一段
`getLong(&uMagic)` + `else if (uMagic!=0x02014b50) err=UNZ_BADZIPFILE;`。
**工厂反汇编里完全没有这一段** ⇒ 厂商删除了中央目录 magic 校验。
⇒ **推论**：上一轮把"magic 比对失败"列为头号嫌疑**不成立**（静态反汇编即能否掉，比内核证据更早）。

### 16.63 ★★★★★ 仪器缺陷：「入口命中数 = 调用次数」**这个前提从未自证**

本轮用 `CGM_TRACE_ADDRS` 得到 `unzOpenInternal`=4 而 `unzGoToFirstFile`=1。
上一轮据此推断"4 次 open 中 3 次在到达 GoToFirstFile 前就失败"——**该推断不可靠**。

理由：`unzOpenInternal` 末尾的 `unzGoToFirstFile(...)` 是**可被 GCC 内联**的
（函数体仅 `push {r4,lr}` + 约 10 条指令）。一旦内联，**out-of-line 入口的命中数就不再等于调用次数**。
同类风险同样适用于 `GetCurrentFileInfoInternal`（9 寄存器入栈、体量适中）。

⇒ **纪律（与 16.52 的四条并列）**：
① **"入口命中数"只能证明"至少走到过"，不能证明"调用了几次"**；
② 要论"次数"必须配一条**不可内联的旁证**（如 strace 的 syscall 计数、或 `bl` 现场的唯一调用点）；
③ 任何用来推"次数/顺序"的仪器，上线前必须用一个**已知内联情形**做反向自证。

### 16.64 ★★★★ 内核 strace 给出的模型无关硬事实（本轮唯一站得住的证据）

对照基准（真实 `golden/sdcard_min/ui_cn.zip`）：`filesize=4,951,281`、`EOCD@4,951,259`、
`offset_central_dir=4,950,716`、`size_central_dir=543`、`entries=6`、`comment=0`。

| 观测 | factory | rebuild |
|---|---|---|
| 对 zip 的 `_llseek` 目标种类 | **6 种** | **82 种** |
| `seek(4951281)`(=EOF) | ×9 | ×29 |
| `seek(4947968)`(=filesize−3313) | ×3 | ×3 |
| **是否 seek 到真实中央目录偏移 4,950,716** | **✗ 从未** | **✗ 从未** |
| `read` 4096 / 12288（顺序读资源数据） | **✗ 无** | **✓ 有**（`seek(4096)|(20480)|(36864)… → read(12288)`，步长 16384） |
| IO 序列前 12 步 | — | **与 factory 逐条相同** |

⇒ 两条硬结论：
1. **两侧都不按"中央目录偏移"直读**（都只 seek 到 `filesize−3313`）⇒ zip 访问**很可能是内存模式**
   （`TUnzip::Open(void*, unsigned, unsigned)` 这一签名本身就是"传缓冲区"的内存模式 API，命中 1 次）
   —— 这**重新激活**了 16.61 里那个被否掉的 `lufread` 内存分支 / `spi_memcpy` 空函数假设，**必须重查**。
2. **分歧实锤在"读到中央目录之后"**：rebuild 有 12,288 字节步长的顺序读（读 `menu.raw` 等资源本体），
   工厂**完全没有**。⇒ **工厂确实没有走通"定位并读出条目内容"**，与 9 场景 exit=139 一致。

**下一步（唯一入口，且不再依赖命中计数）**：用 strace 的**读字节数**判定内存模式的长度参数
（`TUnzip::Open` 的 `len`）是否为 0 —— 若为 0，则内存模式读 0 字节 ⇒ 全 0 ⇒ 与厂商删掉 magic 校验后
"err 仍非 OK" 的另一个置错点吻合。

### 16.65 ★★★★ `-wrap` 在 zig 下必须写**单横线**（`-Wl,-wrap=` 可用，`-Wl,--wrap=` 被拒）

为给设备做诊断，需要链接期重定向 libc 调用（设备启动链全是原厂文件 ⇒ **无任何地方能注入
`LD_PRELOAD`/环境变量** ⇒ 只能用链接期手段）。实测七种写法：

| 写法 | 结果 |
|---|---|
| `-Wl,--wrap=open` | ✗ `error: unsupported linker arg: --wrap` |
| **`-Wl,-wrap=open`** | **✓ 可用** |
| `-Wl,--wrap open` | ✗ 同 `--wrap` |
| `-Xlinker --wrap=open` | ✗ 同 `--wrap` |
| `-Xlinker --wrap -Xlinker open` | ✗ 同 `--wrap` |
| `-Xlinker=--wrap=open` | ✗ `Unknown Clang option` |
| `-Wl,--defsym=…` | ✗ `unsupported linker arg: --defsym` |

⇒ 结论：**zig 的驱动层只放行单横线形式**（lld 本身两者都认）。`tools/diag_wraps.sh` 按编译器分派：
zig → `-wrap=`，GCC(GNU ld) → `--wrap=`。

**行为自证**（不能只看参数被接受）：不加 wrap 时产物未定义符号含 `open`；加 `-Wl,-wrap=open` 后
`open` 从产物未定义符号里**消失** ⇒ 重定向真的发生了。

### 16.66 ★★★★★ 设计门禁的"缺陷态"时：**必须用"被引用"的符号**

同一件事我做了两次反证，第一次**假绿**：

- 第一次：往 `WRAPS` 塞一个无人引用的假符号 `__no_such_symbol_at_all`
  ⇒ 门禁不响、**链接也不报错**、照常出产物（exit 0）。我一度以为"门禁没生效"。
  **真因**：`-wrap=X` **只在有东西引用 `X` 时**才把引用重定向到 `__wrap_X` ⇒
  无人引用的符号**根本不会产生未定义符号**，`-z undefs` 下更是无声通过。
- 第二次：用**被引用**的符号 `fflush`（真链接时第一个报的就是 `undefined symbol: __wrap_fflush`）
  ⇒ 门禁 exit 11、链接器也如期报错。✓

⇒ **纪律**：造缺陷态要问的不是"这个符号不存在吗"，而是"**这个缺陷本来会以什么方式显现**"。
    若缺陷的正常显现方式是"某处引用解析不到"，缺陷态就必须放一个**会被引用的**东西。

### 16.67 ★★★ 门禁自身踩了"原生程序只认 Windows 形式路径"这个老坑 —— 幸好留了守卫

`diag_wraps.sh` 里用 `$PY`（**原生 Windows python.exe**）去读 `src/diag/cgm_wrap.c`。
而 `ROOT` 由 `pwd` 得到，是 **MSYS 形式 `/d/output/...`** ⇒ 原生 python **打不开** ⇒
判据恒假（`MISS` 为空 ⇒ 门禁永远 PASS）。

**唯一没让它变成假绿的原因** = 门禁里写了"读不到文件也必须 exit 11"这条守卫：

```
try:    t = io.open(sys.argv[1], ...).read()
except: print('__READ_ERROR__'); sys.exit(0)
...
[ "$GATE_MISS" = "__READ_ERROR__" ] && exit 11
```

修法：门禁内部自己对路径做 `winpath()`（`cygpath -m`），并保留 `command -v winpath` 的回退定义。

⇒ 通则（与 16.52④ 同源）：**任何门禁都必须能区分"判据不成立"与"判据压根没跑起来"**；
    前者 PASS、后者也必须 **FAIL**。这一条在这次真的救了场。

### 16.68 ★★ `-wrap=X` 的清单与实现必须一一对应（且失败必须响亮）

`WRAPS` 列表里 65 个符号，`cgm_wrap.c` 里必须有 65 个 `__wrap_<sym>`。
本项目实测**漏了 6 个**（`fflush`/`statfs`/`select`/`vfork`/`clock_gettime`/`sigaction`）
⇒ `ld.lld: error: undefined symbol: __wrap_fflush`。链接器**硬失败是对的**，
但报错在 200 行之后、信息量低 ⇒ 加了 `diag_wraps.sh` 自检，把它提前成一句人话，
并**移到编译之前**（旧版本放在 [4/5]，一个列表错误要先白编 213 个文件 ≈ 2 分钟）。

三态自证（`tools/_diag_gate_selftest.py`）：正常态 exit 0 / 缺陷态（去 `__wrap_fflush`）exit 11 /
近似态（挪走 `cgm_wrap.c`）exit 11。**1 秒内跑完**，因为它不依赖编译。

### 16.69 ★★★★★ **PT_LOAD 几何畸形** —— 真机"无法开机 + 零日志"的真根因（15 道门禁才拦住）

**现象**（2026-09-21 用户实测，两次复现，中间换回原厂即正常）：
把 `build/rkgame.diag` 覆盖到 `/sdcard/cubegm/rkgame` 后，**设备无法开机**，
且 `/sdcard/cubegm/_diag/` 内**一个文件都没生成**（目录是我们投放包带过去的）。

**这个"零"本身是关键证据**：我们的代码第一件事就是 `mkdirat(_diag)` + 写 `BEGIN.txt`，
**全是原始 syscall** ⇒ 一条都没有 ⇒ **代码根本没执行**（或执行前就被挡掉）。

**根因（本地静态取证，不需要设备）**：产物的**程序头表是畸形的**。

`linker/factory.ld` 第 34–36 行把自有节钉死在任意高地址：
```ld
.data 0x01000000 : { ... }
.bss  0x02000000 : { ... }
.text 0x05000000 : { ... }
```
而**写属性**的 `.fini_array` 落在 `.rodata` 末尾（VMA ≈ `0x004e00e0`）。
lld 按"属性分组"建段 ⇒ `.fini_array` 与 `.data` 进了**同一个 RW 段**，
于是该段的 `p_filesz` 必须跨过两者之间的 **11,665,696 B VMA 空洞**：

| 量 | 工厂 | 缺陷产物 | 修复后 |
|---|---|---|---|
| PT_LOAD 段数 | **2** | **9** | 9 |
| 文件大小 | 3,921,108 | **17,331,448 B（11 MB 纯填充）** | **5,663,812 B** |
| 最高 vaddr 端 | `0x3e1ad3`（3.9 MB） | **`0x1001b9c`（268 MB）** | `0x564f10`（5.4 MB） |
| 段重叠 | 0 | **11 MB 段吞掉 `.text` 段** | 0 |
| 文件空洞 | 83 KB | **11.1 MB** | 172 KB |

**为什么能一路全绿** —— 原有 14 道门禁**没有一道看"段本身是否畸形"**：
* `abi_check` 只看 ELF 头 4 个字段；
* `dyn_audit` 只看动态段；
* `verify_layout` 只看"符号是否落在 PT_LOAD 内" —— **畸形段也是 PT_LOAD，符号照样"在里面"**；
* qemu-user / PC 内核对重叠段与超大 brk 都容忍 ⇒ 行为差分、里程碑、差集**全部照常 PASS**。

**为什么真机死**：Kernel 的 `load_elf_binary` 用 `elf_bss = max(p_vaddr + p_filesz)` 决定
`set_brk` 的起点 —— 被推到 **268 MB**；再叠加"11 MB 段与 `.text` 段在地址上重叠"
（后续段以 `MAP_FIXED` 覆盖前一段的映射），在 2×Cortex-A7 的小内存盒子上直接 `exec` 失败。
**失败发生在 `_start` 之前 ⇒ 零日志。**

**修法**：不再钉死这三个地址，让自有节紧接 `.rodata` 连续排布（与工厂的 2 段形态同向）。
自有节地址本来就无契约（工厂的 `.data`/`.bss` 在 `0x3af000`/`0x3b2178`，由 `.fimg_*` 复刻）；
钉死它们是历史遗留 ⇒ 移动**不影响任何"烧死的绝对地址"**。

**新增第 15 道硬门禁 `tools/elf_load_audit.py`**（6 条判据，各自有独立缺陷态）：
| 判据 | 内容 |
|---|---|
| A1 | 段 `p_filesz` 不得超过其 **PROGBITS 内容的最外 vaddr 跨度**（+8 KB 容差） |
| A2 | **任一段起点不得落在另一段区间内部**（真重叠） |
| A3 | `p_vaddr % p_align == p_offset % p_align` |
| A4 | 最高 `vaddr+max(filesz,memsz)` ≤ 32 MB（工厂 3.9 MB / 修后 5.4 MB / 缺陷 268 MB） |
| A5 | PT_LOAD 段数 ≤ 12（工厂 2 / 修后 9） |
| A6 | 文件 ≤ 8 MB（工厂 3.9 MB / 修后 5.4 MB / 缺陷 16.6 MB） |

**插入位置**：直接钉进 `tools/link_full.sh` 末尾（本地与 CI 都绕不过，`exit 12`）。

**★ 本轮门禁自身也踩了两个坑（都已修，都值得记）**：
1. **A1 第一版判据写错了** —— 我用"段内各节字节之和"当基准，结果把**合法的 NOBITS 跳段**
   （`.fimg_data` → **NOBITS `.fimg_bss`** → `.fimg_bss_pad`）判成跨洞，**正常态直接 FAIL**。
   正确基准是「段**必须覆盖的最外 vaddr 跨度**」（NOBITS 不占文件字节但必须被段覆盖）。
   ⇒ 纪律：门禁上线前**必须先在正常态跑通**；「看起来像缺陷」和「是缺陷」是两件事。
2. **一次缺陷态只验证一条判据是不够的** —— 我第一版只注入"段吞掉 `.text`"，
   结果只有 A2 命中、A1 不命中（该形态下空洞与内容跨度一起变），我却按"A1 也必须命中"断言，
   于是误判"门禁未生效"。改成**每条判据各有自己的缺陷态**（A2 注入重叠 / A1 注入尾部填充 /
   A3 注入 offset 偏移）后 4/4 命中。
   ⇒ 纪律：**N 条判据就要 N 个缺陷态**，不能用一个缺陷态代表全部。

**并行产物**：`build/rkgame.probe` —— **3,572 B 的最小探针**（`-nostdlib -static`，
**无 `.interp`、无 `DT_NEEDED`**、入口手写 `_start`、只经 `svc #0`），
用原始系统调用往 7 个路径写文件 + 往 `/dev/fb0` 涂满 + 追加 + 重命名，
用来把"内核不肯 exec 我们的产物"与"跑了但写不出文件"这两件事**彻底分开**。
它也过同一道几何门禁。

### 16.70 ★★ 工具缺陷（我自己的仪器报假缺陷）：arm_dis 把 `strd` 解成 `strh`

**经过**：真机 t1 崩在 `sfc_init+0x6c`（SIGBUS，`si_addr` 落在库区）。我用 `tools/arm_dis.py`
反汇编我们产物里的 `sfc_init`，看到 `0x501b5c: strh r6, [sp, #0]` 且**全文没有把偏移常量
（0x10208000）入栈**的指令 ⇒ 我据此断定「`mmap` 的第 6 实参是垃圾值」——**这是假的**。

**真值**：`0xE1CD60F0` 是 `strd r6, r7, [sp, #0]`（64 位存储：r6→[sp]，r7→[sp+4]）。
解码依据（ARM ARM A8.8.73/74）：立即数形式下 bits[7:4] 的语义是
`1011=LDRH/STRH`、`1101=LDRSB/LDRSH`、**`1111=LDRD/STRD`**；旧代码把 `1111` 归进半字分支。

**影响**：`sfc_init` 与工厂**逐条等价**（同样的 `mmap(NULL,1024,3,1,fd,0x10208000)`、
同样的 `ldrh [base+0x2C]` / `str [base]` / `str [base+0x88]`）。已修 `tools/arm_dis.py`
并加了 4 条编码回归自证（`0xE1CD60F0` / `0xE1D012BC` / `0xE1C000B0` / `0xE5900000`）。

⇒ **纪律（与 16.52 并列）**：**工具产出的"缺陷"必须先验证工具本身**再写进结论。
  判据：拿一条**已知编码**做回归；解码器的每个分支都要有正例。

### 16.71 ★★★★★ `PT_GNU_RELRO` 把 `.data` 圈成只读 ⇒ 写自己的全局变量即 SIGSEGV（真机实证）

**现象**（探针 v3，t2 = 诊断版）：`SIGSEGV`，`si_addr = 0x4e1010`，`PC = cgm_diag_boot+0x184`
—— 崩在**写自己的全局变量 `g_lvl`**（该地址在 `RW` 段里，设计上就该可写），
连 `-finstrument-functions` 的插桩都没跑起来（所以 `_diag/` 里一个文件都没有）。

**根因**：`ld.lld` 的 `PT_GNU_RELRO` = 「本 RW 段内**第一个 relro 节**的起点 → **最后一个
relro 节**的终点」。此前链接脚本把 `.data.rel.ro`/`.got` 混在 `.data` 输出段里，而 lld
又把 `.dynamic` 自动排到 `.data` **之后** ⇒ RELRO = 0x4e00e0 .. 0x4e2b9c
⇒ **`.data`（0x4e1000）整段在 RELRO 内** ⇒ 内核按页取整把 0x4e0000-0x4e3000 设只读
⇒ **第一次写 `.data` 全局变量即 SIGSEGV**。

**对照原厂（正确范例）**：`PT_GNU_RELRO = 0x3ae5c4 + 2620`，终点 `0x3aefe0`
**恰好停在页对齐的 `.data`(0x3af000) 之前** ⇒ 原厂 `.data` 完全可写。

**修法**（`linker/factory.ld`）：`.data.rel.ro` / `.got` / `.dynamic` 各自成段并**排在
`.data` 之前**，`.data` 页对齐。修后实测：
`PT_GNU_RELRO = 0x4e00e0 + 7060`（页区间 0x4e0000-0x4e2000），`.data` @ **0x4e2000**（页对齐、可写）。

**为何此前 15 道门禁全绿**：所有判据都在看"地址对不对/符号在不在段里"，**没有一条看
「可写节是否落在 RELRO 页里」** —— 而这正是"运行期第一秒就死"的直接原因。
新增 `tools/relro_audit.py`（R1 页面级判据 + 三态自证），已钉进 `tools/link_full.sh`（失败 exit 13）。

### 16.72 ★★★★★ 工厂是「立即数」，重建写成了「符号名」⇒ 采样率变成 5,128,288

**真机证据**：原厂自己打印 `snd_pcm_start failed: -32`（EPIPE，无害，它继续活着）；
我们打印 `failed to apply hwparams: -22`（EINVAL，致命）。两边都走到了音频初始化。

**机器码级对照**（工厂 `InitSound` @0xdb4c）：

| | 工厂机器码 | 我们（修复前） |
|---|---|---|
| 第 3 参 | `mov r2, #2` | `mov r2, #2` ✅ |
| **第 2 参** | **`movw r1, #44100`** | `ldr r1,[pc,..]` + `ldr r1,[pc,r1]`（**从 GOT 取符号地址**）❌ |
| 第 1 参 | `ldr r0,[=USE_HDMI_OUT]` | 同 ✅ |

`44100 == 0xAC44`，**恰好等于**工厂里 `UpdateROM` 的函数地址 `0x0000ac44`
⇒ **Ghidra 把"立即数 44100"反编译成了符号 `UpdateROM`**，重建原样抄下。
工厂布局下两者数值相同（"碰巧无害"），但我们的产物把 `UpdateROM` 链接到 `0x4e4060` 附近
⇒ 传给 `driver.so` 的采样率 ≈ **5,128,288 Hz**。

`driver.so` 的 `sound_driver_init` 用它算缓冲区（`[fp,#-24] = (40*(arg2+1))/100` 再取 2 的幂）
⇒ `SoundDataBufferLen/period` 变成天文数字 ⇒ `snd_pcm_hw_params()` 返回 **-22(EINVAL)**
⇒ 音频初始化失败（原厂同一处只是无害的 -32）。

**修法**：`(*sound_driver_init)(USE_HDMI_OUT,44100,2)`；修后产物机器码 = `movw r1, #0xac44`
（**与工厂逐条一致**）。

**新增门禁** `tools/lint_const_args.py`：对 213 个重建函数，把「工厂函数体里的立即数 V」
与「V 对应的工厂符号名在我们源码里被当值使用」做对拍；三态自证（正常 PASS / 把 44100
还原成 `UpdateROM` 必被抓到 / 缺 golden 必 exit 11）。

**同类风险已排查**：全源码扫描后**仅此一处**（`InitDisplay` 的 `video_driver_setting`
传的是 `&{0,1,1}` 三整型，经机器码核对与工厂等价）。

### 16.73 ★ 对上一轮结论的更正：`sfc_init` **不是**缺陷

我在 16.70 之前一度写下「`sfc_init` 的第 6 实参 fmmap 偏移没入栈、是垃圾值」。
**该结论作废**：真值是 `strd r6, r7, [sp, #0]`（工具误报，见 16.70）。
`sfc_init` 与工厂逐条等价 —— t1 的 `SIGBUS` **另有原因**（未定；下一轮用修好的探针 v3
（已修十六进制符号打印 + maps 上限 3800 + 补印 r1-r12）重新采集现场）。

### 16.74 本轮门禁总表（新增 3 道，共 18 道）

| # | 门禁 | 抓手 | 钉在哪 | 失败码 |
|---|---|---|---|---|
| 16 | `elf_load_audit.py` | PT_LOAD 几何（重叠/跨洞/最高地址/体积） | `link_full.sh` | 12 |
| 17 | **`relro_audit.py`** | **RELRO 页区间 ∩ 可写数据节** | `link_full.sh` | 13 |
| 18 | **`lint_const_args.py`** | **工厂立即数 vs 源码符号名** | `link_full.sh` | 14 |

修后本地全绿：`link_audit`（未定义 0 / 重复定义 0）· `elf_load_audit` PASS ·
`relro_audit` PASS · `abi_check` PASS · `dyn_audit` PASS(WARN 1) · `check_obj_fresh` PASS ·
`lint_const_args` PASS（213 函数对拍）。
