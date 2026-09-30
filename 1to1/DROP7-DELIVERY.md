# drop7 交付报告 —— 关键路径顶到用户面前（2026-09-27）

> 用户口径：「保证初始方向，推进未完成的任务，如果存在绕圈，就必须跳出来。
> 我不要补丁，要根本性的解决方案」+「交给用户实测前先全量审计和补漏」。

---

## 一、直答：本轮之前"没进展"的机制是什么

**主产物是陈的。** 行为尺一直用**新产物**（`build/ab/iconvO0.elf`）测，而投放用的
`build/rkgame.rebuilt.elf` 停在 **09-26 16:05**，比上游源码（09-27 11:40 / 12:21）还旧。
投放包 `_sdcard_drop6/` 更是 **09-23 13:27** 做的、之后**从未上机**。
⇒ 这就是"总交半成品"的机制：**测量在跑、交付没动**，而关键路径卡在"要你上机"这一步
却连续 5 天没顶到你面前。**本轮先修这条。**

---

## 二、本轮对产物的实际改动（全部是构建事实对齐，非补丁）

| # | 改动 | 依据（可复算） | 效果 |
|---|---|---|---|
| 1 | `build/rkgame.rebuilt.elf` **重链**（含 mxml 2.9 / libiconv 1.16 @ -O0） | 对象时间 09-27 14:2x，产物停在 09-26 | 交付产物从"旧"变"当前" |
| 2 | `libiconv17/config.h` 加 `HAVE_LANGINFO_CODESET 1` | 工厂**动态导入表**：导入 `nl_langinfo`、**不导入 `getenv`** | `localcharset.o` 未定义符号由 `getenv` → **`nl_langinfo`**，与工厂一致 |

改动 2 的验证（机械）：

```
改前  build/upstream/libiconv_localcharset.o 未定义符号 : ['getenv']
改后  build/upstream/libiconv_localcharset.o 未定义符号 : ['__aeabi_unwind_cpp_pr0', 'nl_langinfo']
产物  build/rkgame.rebuilt.elf 导入: nl_langinfo=✅  getenv=❌   （工厂同）
```

---

## 三、交付产物的硬数字与门禁（本轮实测）

| 项 | 值 |
|---|---|
| 产物 | `build/rkgame.rebuilt.elf`，**5,745,916 B** @ 09-27 14:45 |
| sha256 | `e5cf44b06e32ebe9…`（完整值见投放包 DEPLOY-MANIFEST） |
| 行为尺 | **PASS 727 ｜ DIVERGE 46 ｜ TRUNC 5 ｜ SKIP 0**；自洽 `727+46+5+0=778` ✓ |
| PT_LOAD 几何 | **PASS**（9 段、无重叠、页对齐、最高端 0x5784d0 ≤ 32 MB） |
| RELRO | **PASS**（`.data`/`.bss` 未落入只读页区间） |
| MMIO 宽度 | **PASS** —— `sfc_init` **窄访问 我们=0 / 工厂=0 ✓**（第 2 次启动失败的根因已修在包内） |
| ABI | PASS |
| 上游 API 台账 | 无新增超集符号 |

---

## 四、★ 新门禁：`tools/size_coverage_gate.py`（补行为尺的盲区）

**为什么必须补**：行为尺只在输入**真的走进那段代码**时才看得见差异。
入口条件不满足（缺文件、缺设备、提前 return）时，两侧都"正常返回"
⇒ **工厂有 976 B 实现、我方只有 112 B 空壳，照样判 PASS**。

判据（机械）：对两侧共有函数比 `st_size`，`ratio = ours/factory < 0.5` ⇒ **SHORT**。
自证 8 条锚点 0 失败。全库扫描 778 个共有函数：

| 比值 | 我方 | 工厂 | 函数 |
|---|---|---|---|
| **0.115** | **112** | **976** | **`UpdateROM`** ← 真缺体 |
| 0.435 | 520 | 1196 | `ReadUSBJoy` |

**`UpdateROM` 实证**：源码 `src/proprietary/flash/FUN_0000ac44_UpdateROM.c` 有完整 139 行
（含 `sync()` / `reboot(0x1234567)`），但编译后**只剩错误分支**：

```asm
fopen(path,"r+b") → 失败则 printf("Load %s fail!") → 返回
fread(buf,1,3) → fclose → printf("%s format error!") → 返回     ← 魔术字校验被消掉
```

⇒ 闪写 / CRC 校验 / 安全区写 / `reboot` 整段（约 864 B）**没进二进制**。
这解释了另一处机械事实：**工厂导入 `reboot`、`sync`，我方两个都没有**。
（属于**功能缺口**，不影响启动 ⇒ 不阻塞本轮投放，列为下一靶子。）

---

## 五、★ `.dynsym` 保真审计（新视角，机械可复算）

工厂动态导入 **113** 个，我方 **90** 个，交集 85。

| 方向 | 数量 | 代表 |
|---|---|---|
| 工厂有 · 我方无 | **28** | `_IO_putc`/`_IO_getc`、`__strdup`、`memcpy`/`memset`/`strlen`、`sqrt`/`cos`/`floorf`/`fmod`/`sqrtf`、`_Znwj`/`_Znaj`/`_ZdlPv`/`_ZdaPv`、`reboot`/`sync`/`raise` |
| 我方有 · 工厂无 | 5 | `putc`、`getc`、`strdup`、`mbsinit`、`gmtime` |

**性质**：我方把 `memcpy/memset/strlen/sqrt` 等**静态链进来**（zig 的 compiler_rt / 静态 libm），
工厂则是**动态导入**。这不只是符号表差异 —— 它会让行为尺产生**假发散**：
工厂调 `memset` 走模型（模拟），我方内联的 `memset` **真执行** ⇒ 访存指纹必然不同
（实证：`LoadMenuLog` F 有 `memset`、O 无；`mui_LoadConfig` 同）。⇒ 下一靶子。

---

## 六、drop7 投放包

目录：**`_sdcard_drop7/`**（`tools/stage_sd_round7.py` 生成）

| 目标路径 | 字节 | sha256 |
|---|---|---|
| `cubegm/rkgame`（探针 v5） | — | 见 MANIFEST |
| `cubegm/rkgame.t1`（修复前对照） | 5,663,896 | 见 MANIFEST |
| `cubegm/rkgame.t3`（★ 本轮候选） | 5,745,916 | `e5cf44b0…` |
| `cubegm/_diag/` | — | — |

**你要做的 4 步**（细节见包内 `READ-ME-FIRST.txt`）：
1. 确认卡上 `cubegm/rkgame.bak` 存在（原厂备份，3,921,108 B）
2. 把包内 `cubegm/` 的 4 个东西拷到 SD 卡（`rkgame` 必须覆盖）
3. 插卡开机，**等满 90 秒**
4. 关机拔卡，把 `cubegm/_diag/PROBE5.txt` 发我

**预登记判据**：`t1` 预期仍 SIGBUS；`t3` 三态各有含义（存活 / 崩在新 PC / 仍崩 sfc_init）。

---

## 七、诚实声明（没有验证的）

> ★ **2026-09-27 15:45 更正**：本文件初稿写的"重建产物从未在真机上成功启动过"是**错的**，
> 属于我凭印象下结论。真机事实如下（全部来自你提供的 `PROBE3.txt`，87 KB / 1619 行）：

| 候选 | 真机实测结果 |
|---|---|
| 原厂对照 | **存活至超时** ✅ 阳性对照通过 |
| **B 线 v15** | **存活至超时**（205 s）—— **我们自己的代码在真机上真的跑起来了** |
| t4 最小动态 ELF | 正常退出 `exit=0` ✅ |
| A 线 rebuilt | exec 成功，**SIGBUS(7) @ `sfc_init+0x6c`**（机器码级确认 = `ldrh r1,[r0,#0x2c]`） |
| A 线 diag | SIGSEGV(11) @ `cgm_diag_boot+0x184` |

⇒ 正确的表述是：**产品已经上机多次、并且已经在真机上执行过我们的代码**；
未完成的只是"修完第三个根因之后的复测"。

1. **宽度修复之后的复测没有做过**（这是唯一缺的一次，不是"从未上机"）。
2. DIVERGE 不为 0（46 个，36 个函数），最大一族是我们自写的 `mui`（19 个）。
3. `UpdateROM` 缺体、`.dynsym` 28 项差异 —— 已知、已定位、**未修**。
4. 本机跑不了的门禁（依赖 `objdump`/`readelf`）仍需一轮 CI 才有结论。

