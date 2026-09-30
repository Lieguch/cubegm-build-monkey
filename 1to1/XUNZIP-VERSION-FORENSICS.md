# 上游取证：XUnzip 换源的**假设被行为尺证伪**（2026-09-27）

> 结论先行：**换回 Wischik 原版会让产物更差 ⇒ 已回退。**
> 「体积命中 20/25」是**代理指标**，行为上被推翻。本文完整记录证据链与证伪过程。

---

## 〇、结果

| 指标 | 现用变体（回退后） | 换成原版 | 判定 |
|---|---|---|---|
| 共有函数 | 778 | **775** | −3 |
| PASS | **729** | 708 | **−21** |
| **DIVERGE** | **44** | **62** | **+18 ★净回归** |
| TRUNC | 5 | 5 | — |
| 自洽校验 | `729+44+5=778` ✓ | `708+62+5=775` ✓ | 两者都自洽 |

**动作：回退。** 源与对象都已还原，且**回退后的产物逐字节等于换源前**：

```
unzip.cpp   sha256 前缀 9ee99732b8e96f6f   （与换源前一致）
XUnzip.o    39,476 B                        （换源时是 43,748 B）
产物        5,747,156 B
sha256      6737fd22653d17c3fae8715c08e08e0a9e2bd9b518a0dead9b2909810ba59bd9
            └─ 与换源前 16:51 的产物**完全相同** ⇒ 回退是精确的，不留残余
```

---

## 一、被证伪的假设（以及它当时看起来多有说服力）

### 1.1 体积代理指标（`tools/zipver_sweep.py`，已于 2026-09-21 定案，本轮复现）

| 候选 | 在 ±33% 内命中工厂 `st_size` |
|---|---|
| **A. Wischik 原版**（2004-06-25，144,408 B） | **20 / 25** |
| B. 现用变体（tomyqg，151,019 B） | ≈ 0 / 25（几乎每行偏 2×） |

原版 6 个符号**精确到字节**：`unzStringFileNameCompare` 16=16 · `unzClose` 60=60 ·
`unzGetGlobalInfo` 32=32 · `unzGoToFirstFile` 96=96 · `unzlocal_DosDateToTmuDate` 64=64 ·
`unzGetCurrentFileInfo` 64=64。带鉴别力的差异项也全指向原版（`unzOpenCurrentFile` 工厂单参 316
↔ 原版 316 / 变体 440；`Find` 参数形态）。

### 1.2 两个**独立**的符号级旁证（比体积更硬）

| 符号 | 工厂 | 原版 | 现用变体 |
|---|---|---|---|
| `_Z17FormatZipMessageUjPcj` | **有** | **有** | **无** |
| `lasterrorU`（4 B 数据） | **有** | **有**（`ZRESULT lasterrorU=ZR_OK;`） | **无** |

**`lasterrorU` 尤其强**：变体连这个概念都没有，而工厂 symtab 里恰好有它。
当时我认为这已足够下结论。

### 1.3 目录本身处于"混合状态"

`unzip.h` / `zip.cpp` / `zip.h` 是 **2004-06-25 原版**，只有 `unzip.cpp` 是 2018 变体
⇒ 四文件同源看起来是"显然正确的收口"。

---

## 二、换源落地（可复现，`tools/_swap_xunzip.py`）

除换源外必须做的 3 处适配，**每一处都有工厂侧证据**：

| # | 问题 | 证据 | 处置 |
|---|---|---|---|
| 1 | 原版 `const TCHAR *msg=L"unknown zip result code";` 在 ANSI 构建下编不过（该函数其余分支全用 `_T`） | 工厂是 ANSI 构建（`Find` 取 `char`、导入 `FormatZipMessageU(…, char*, …)`） | 改 `_T("…")`（**修上游笔误**） |
| 2 | `duplicate symbol: lasterrorU`（`XUnzip.o` vs `factory_local.o` 工厂数据镜像） | 工厂 symtab 有 `lasterrorU`(4 B) | 定义改 `extern`，**由工厂镜像供给**（与 libiconv `_libiconv_version` 同一手法；`ZR_OK==0` 取值等价） |
| 3 | `undefined symbol: TUnzip::Find(char const*, unsigned char, …)` | 工厂 `Find` 是 `PKch`（unsigned char），原版是 `PKcb`（bool） | 两处参数类型改 `unsigned char`（同 1 字节，ABI 相同） |

换源后：`XUnzip.o` 39,476 → 43,748 B，含 `_Z17FormatZipMessageUjPcj`（变体缺），
链接成功，PT_LOAD / RELRO / 常量混淆 / MMIO 宽度 / 设备访存 / 体量覆盖 / UB **全部 PASS**。

**——到这里为止，一切指标都指向"换对了"。——**

---

## 三、行为尺判决：**净回归 +18**

| 新增 DIVERGE（12 个，**全是 zip 链路及其调用方**） | 消失的 DIVERGE（11 个，与 zip 无关） |
|---|---|
| `OpenZipU` · `unzOpenInternal` · `unzlocal_getByte` · `unzlocal_SearchCentralDir` · `unzlocal_CheckCurrentFileCoherencyHeader` · `lufseek` · `TUnzip::Find` · `TUnzip::Open` · `get_items_from_zipfile` · `mui_LoadUIResource` · `mui_DisplayThumbnail` · `GetJoystickConfig` | `luferror` · `mui_load_state` · `mui_save_state` · `mui_setting` · `mui_type` · `mui_type_file_list` · `mui_video_setting` · `mxmlEntityGetValue` · `mxml_file_putc` · `myStrrstr` · `outputxy1` |

**关键读法**：新引入的分歧**集中在 zip 内部的读写/寻址链**（`unzlocal_SearchCentralDir`、
`unzlocal_getByte`、`lufseek`、`CheckCurrentFileCoherencyHeader`）——
**这些恰恰是体积最接近工厂的那几个**。⇒ 体积接近 ≠ 语义一致。

⇒ **假设被证伪，按纪律回退。**

---

## 四、为什么这件事比"换源成功"更有价值

1. **它把一条"看起来已经定案、只等执行"的旧结论拆穿了。**
   `zipver_sweep` 09-21 就给出"20/25，原版即工厂版本"，此后 6 天没人验过行为。
   本轮第一次用**行为尺**验收它，结果是**错的**。
2. **它给出了代理指标失效的具体形状**：`st_size` 相近的**同一族函数**内部，
   偏移/寻址/短读语义仍可不同；而 `unzlocal_*` 正是一串**层层嵌套的读写原语**，
   体积几乎只由控制流骨架决定。
3. **它证明了"外加旁证"也可能是巧合**：`FormatZipMessageU` 与 `lasterrorU` 确实只在原版里，
   但那只说明**工厂的 zip 库源自 Wischik 这条血脉**，**不**说明工厂用的是**这一份 2004 快照**
   （工厂可能用的是同一血脉的**中间版本**）。

---

## 五、诚实声明

1. 本轮**只**证伪了"换成这一份 2004 快照"。**没有**证伪"工厂 zip 源自 Wischik 血脉"
   （`FormatZipMessageU` / `lasterrorU` 是硬事实）。
2. 现用变体**不等于**已验证正确；它只是**行为尺下更好**（DIVERGE 44 vs 62）。
3. 回退后需重新确认产物与门禁（已在 `report/_r78_link.txt` 复跑）。
4. **未**上机验证任何一方。

---

## 六、纪律

> **43.** 复现过的旧结论**不等于**已落地，更**不等于**正确：
> `zipver_sweep` 的"20/25"六天没人用行为尺验过 ⇒ 凡"体积/相似度"类结论，
> **必须**有行为尺背书才允许写进交付判断。
> **44.** 链接失败**不得**留下上一轮产物（fail-closed）。"文件存在"不是"本轮成功"。
> **45.** **符号存在性**只能证明"血脉相同"，不能证明"同一快照"。
>   判断上游版本必须用**行为**（或带鉴别力的判据），不能只靠"独有符号 + 体积"。
