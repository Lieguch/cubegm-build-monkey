# AUDIT-1TO1 —— 距「1:1 复刻原厂 rkgame」的全量差距评估（含假实现/假代码/假桩专项）

- 审计时间：**2026-09-30（第 95 轮）** ｜ 本版**取代**第 83 轮版本（那份的数字已被 §0.41/§0.42 两轮判据修正作废）
- 审计标的：`build/rkgame.rebuilt.elf` **sha256 `c9aba0eb96e40bf7…`**（5,513,696 B）
- 对照物：`golden/factory.rkgame.bin` **sha256 `8ff3b4b70c253ff7…`**（原厂，只读红线）
- 判据强度：`diff_exec --batch --steps 3000`（触上限者 ×20 放大重试）
- **行为尺权威基线**：`BASE c9aba0eb96e40bf7 782 758 19 5 0 0`
- 全部数字都有实测来源；工具：`pyelftools` + `capstone` + Unicorn(`diff_exec`)

---

## 一、一句话结论

**结构层与"造假"嫌疑已清零；行为层只剩 19 个真发散（+5 个不可判）；真正的缺口在 L3（真机复测）与 L4（项目目的 2）。**
本轮另查出 **1 项从未做过的机械差距**（`.dynsym` 导入表 8+4 项）与 **2 项仓库级隐患**（死代码树、两套数据宇宙）。

---

## 二、差距分四层

| 层 | 判据与实测 | 状态 |
|---|---|---|
| **L1 结构层** 符号落位 / 链接 / 段几何 / 段权限 / ABI / 动态段 | 9 道硬门禁**全 PASS**（见 §三）；`verify_layout` 全局符号命中率 **99.5%（193/194）**、违规 0；`prop_equiv` **FAIL 0 / MISSING 0**；`size_coverage` **SHORT 0** | ✅ **清零** |
| **L2 行为层** 逐函数差分执行 | 782 共有 → **PASS 758 ｜ DIVERGE 19 ｜ TRUNC 5 ｜ REFDEAD 0 ｜ SKIP 0**（另 9 个判「访存内联等价」计入 PASS）。类别见 §五 | ⏳ 有明确清单 |
| **L3 真实功能层** 产物覆盖 SD 卡后**设备** drop-in | 最后一次真机（09-22/23）：A 线成功打开 `driver.so`、初始化 DRM、走到 ALSA 后崩；两处根因已修，**修复后未复测**。`_sdcard_drop8/` 已按当前产物重出（基线按 sha 反查） | ⏳ **唯一终局判据**（★ 纪律 37/40：本地结构性缺口未清完前**不把上机当下一步**） |
| **L4 功能升级层** 项目目的 2 | ① evdev 即插即用手柄 ② `.srm` / `retro_save_state` SRAM 存取 | ⛔ **未动工** |

---

## 三、L1：9 道硬门禁**逐道实测**（本机，判决行）

| 门禁 | 判决 | 关键实测 |
|---|---|---|
| `abi_check` | **PASS** | `e_type/e_machine/e_flags/interp` 逐字段一致；失败 0 |
| `dyn_audit` | **PASS** | `e_entry` ∈ 可执行段；GOT 0 值槽 0；ABS 0 占位 0；GLIBC 版本上限 ≤ 工厂；NEEDED 结构无差异 |
| `verify_layout` | **PASS** | 全局符号命中率 **99.5%（193/194）**；PT_LOAD 9 段；违规 **0** |
| `relro_audit` | **PASS** | RELRO 页取整区间**未**覆盖我们的可写数据 |
| `elf_load_audit` | **PASS** | A1–A6 全过；9 段无重叠、页对齐、最高端 0x548f20 ≤ 32 MB |
| `mmio_width_audit` | **PASS** | 直接访问设备寄存器的函数，访存宽度与工厂一致（0 违规） |
| `dup_sym_gate` | **PASS** | 重名符号主/从绑定正确；0 条缺失 |
| `prop_equiv` | **PASS**（FAIL 0） | 总计 213 ｜ **FAIL 0 ｜ WARN 4 ｜ OK 192 ｜ THIN 15 ｜ MISSING 0** |
| `size_coverage_gate` | **PASS** | **SHORT 0**（无"体量异常小"的疑似桩/缺体） |

`prop_equiv` 仅剩 **WARN 4**，全部已定性（**不是缺陷**）：

| WARN | 我方/工厂 | 定性 |
|---|---|---|
| `ClearBuffer` | 20/32 = 0.625 | 豁免：`memset` 尾调用 |
| `sunxi_gpio_output` / `sunxi_gpio_set_cfgpin` | 140/232 = 0.547 | 豁免：**条件执行融合**（§0.32-E 取证：两侧都从全局重载基址，无可观测差异） |
| `GetZipItemA` | 68/104 = 0.607 | 豁免：我方把 3 个出口**尾合并**成一个（§0.32-F 取证） |

---

## 四、★ 假实现 / 假代码 / 假桩 —— 本轮专项（**六项实测**）

| # | 嫌疑 | 判定 | 证据（本轮机械复算） |
|---|---|---|---|
| 1 | **空壳函数**（我方 `st_size ≤ 4`） | **✔ 忠实** | 我方 9 个；其中**工厂同名函数同样是空壳 9/9**，工厂更大者 **0** |
| 2 | **恒返回常量**（正文只有 `mov r0,#imm [+ bx lr]`） | **✔ 忠实** | 共 1 个，**两侧返回值逐字一致**；不一致 **0** |
| 3 | **桩符号进了产物**（`zstub.c` / `libz.so.1` / `cxx_ops.c`） | **✔ 未进产物** | 产物 `.dynsym` 里 `compress` `uncompress` `_Znwj` `_ZdlPv` `_Znaj` `_ZdaPv` `malloc` `free` **全部 `SHN_UNDEF`**（运行期由**设备自己的** DSO 解析）；异常 **0** |
| 4 | **`.fimg_text`（2.82 MB 原厂机器码逐字节副本）** | **✔ 是地址垫，不是被执行的代码** | 所在 PT_LOAD 权限 `R--`；段内 0 个 `STT_FUNC`；§0.30 删除实验已证**内容可全零**而行为尺零影响 |
| 5 | **★ 死代码树：`src/upstream/libiconv/`** | **⚠ 仓库级陷阱（不在产物内）** | 该目录 **251 个文件，其中 104 个头文件正文只有一行 `/* Empty stub: charset converter not implemented */`**；**grep 全仓库构建/CI：零引用**（构建用 `src/upstream/libiconv17/`）。⇒ 268 个 charset 转换函数**两侧各 268、零缺失零多余**，故**不影响产物**；但它是"看起来像实现、其实是空桩"的诱饵，必须标注或移除 |
| 6 | **我方自有源码的占位** | **✔ 仅 1 处注释 + 1 处不在产物内** | `src/proprietary|compat|data` 命中 **1 处，是注释**；`src/diag/cgm_diag.c:481` 有 `/* 占位 */`，但**产物里没有 `cgm_diag_*` 任何符号**（诊断构建独立） |

### 4.1 ★★ 新查出：`.dynsym` 导入表差异（§0.19-F.3 点名、**一直没做**）
```
工厂 113 项 ｜ 我方 109 项 ｜ 共有 105
仅工厂 8 项：_IO_getc  _IO_putc  __strdup  islower   （+ 4 弱符号 _ITM_*/_Jv_RegisterClasses/__gmon_start__）
仅我方 4 项：getc      putc      strdup     mbsinit
```
| 项 | 定性 | 依据 |
|---|---|---|
| `_IO_getc`↔`getc`、`_IO_putc`↔`putc`、`__strdup`↔`strdup` | **等价别名**（glibc 同一函数的不同入口） | 设备 rootfs 两套都在；不构成功能差异 |
| 4 个弱符号（`__gmon_start__` 等） | **无害** | `STB_WEAK` + `SHN_UNDEF`，缺失即取 0 |
| `islower`（工厂导、我方不导） | **编译器内联差异** | 我方 `src/proprietary/misc/FUN_00016ebc_strupr.c:23` 调用了它，但 clang 经 `__ctype_b_loc` 内联（我方仍导入 `__ctype_b_loc`）⇒ 语义差异不在机器码层 |
| **`mbsinit`（我方多导）** | **★ 待定的真差距** | 工厂导 `mbrtowc`/`wcrtomb` 但**不导 `mbsinit`**；我方 `libiconv17/config.h:16 #define HAVE_MBSINIT 1` ⇒ 走真调用。而 `loop_wchar.h` 的规则是 `#if !HAVE_MBSINIT → #define mbsinit(ps) 1` ⇒ **工厂那版构建的 `HAVE_MBSINIT` 显然为 0**（否则也会导入）。**候选修法**：把该宏对齐（单变量实验，纪律 56） |

---

## 五、L2：19 个 DIVERGE 的类别（数据源 = `diff_exec --dump-rows`，不截断）

| 类别 | 个数 | 判读 |
|---|---|---|
| **ONE-SIDE（真差异第一嫌疑池）** | **13** | 一侧键在对侧**完全找不到落点** ⇒ 真差异第一嫌疑池 |
| INLINE-MOVE-部分（有未解释键） | 3 | 只解释了一部分 ⇒ **不得**当假发散洗白 |
| CALLS-EXT | 3 | 外部调用集合不同 |
| RET | 3 | 返回值不同 |
| MIXED(ca+rd+wr) | 2 | 混合 |
| STOP+MORE | 2 | 停止类别 + 其它维度 |
| MIXED(ca+rd) | 1 | 混合 |

**剩余 19 个函数清单**：
`DisplayPage_list` `DrawFrame` `FilePreEmu` `SeletEmuCore` `TestLibz0` `_Z17FormatZipMessageUjPcj`
`get_item_from_line` `get_value_from_items` `locale_charset` `mui_DisplayInputBuffer`
`mui_DisplayLine_t` `mui_video_setting` `outputxy1` `progress` `stbtt__get_subrs`
`stbtt__tesselate_curve` `strtrim` `wchar_from_loop_reset` `xmp3_FDCT32`

**TRUNC 5（不可判，≠ 已收敛）**：`MP3InitDecoder` `TestRun` `TestUSBJoy` `WaitNMI` `xmp3_AllocateBuffers`
（根因 = 沙箱天花板：三侧全在 `mui_setting` 入口 `0x2b3c8` 崩，**factory 也失败** ⇒ 非我方缺陷）

---

## 六、★ 结构性隐患：我方存在**两套数据宇宙**（§0.42 已登记，未做）

| 事实 | 数值 |
|---|---|
| 我方 ELF 里**同一基名有两个 `STT_OBJECT`** | **684 个基名**（例 `aliases` 0x3ab114 **GLOBAL** / 0x410000 **LOCAL**；`cjk_variants_indx` 41984 B 两份） |
| 两套的角色 | ① 工厂 VMA 处的**地址垫**（`src/data/factory_image.S` 的 GLOBAL 别名，**不被读**）；② **我们编译出来的副本**（LOCAL，0x4xxxxx，**我们的代码实际读这一份**） |
| 等价性普查（`tools/dup_copy_audit.py`） | 被检 **1376 个对象**：**EQUIV（逐字节相同）1371 ｜ ★DIFF（真内容差异）0 ｜ NEEDS-REVIEW（含指针，须语义复核）5** |
| NEEDS-REVIEW 5 | `_ZL8z_errmsg` · `_mxml_key_once`（段尾读不满）· `all_encodings` · `entities`（**已判等价**：257/257 名字与值全同）· `types`（**已判等价**：指针指向的串全同） |
| 已修的部分 | §0.42：修掉**命名歧义**导致的误配对（GCC `name.NNNN` / clang `<func>.name`），DIVERGE 27→19 |
| **未做的终局** | 让编译产物**落在工厂 VMA**（= 一套宇宙），才与「段 VMA 必须与工厂一致」完全自洽 |

---

## 七、缺口清单（按优先级，可直接照单推进）

| 优先级 | 缺口 | 性质 | 下一步动作 |
|---|---|---|---|
| **P1** | 19 个 DIVERGE（§五） | 真差异嫌疑池 | 逐个按"工厂有/我方无"取证；优先 `ONE-SIDE` 13 个 |
| **P1** | `mbsinit` / `HAVE_MBSINIT` 不对齐（§4.1） | **真差距（可机械修）** | 单变量实验：对齐该宏后重编 + 行为尺对拍 |
| **P1** | 两套数据宇宙（§六） | 结构（与"段 VMA 一致"冲突） | 生成"对象 → 工厂 VMA"放置表，让编译产物落在工厂 VMA |
| **P2** | `all_encodings` / `_ZL8z_errmsg` 语义复核 | 欠账（`dup_copy_audit` 的 NEEDS-REVIEW） | 指针感知的逐项比对（`entities`/`types` 已用同一方法判等价） |
| **P2** | `src/upstream/libiconv/` 死代码树（251 文件 / 104 空桩头） | 仓库级陷阱 | 标注 `DEAD-TREE` 说明 或 移到 `build/_exp/` |
| **P2** | `TRUNC` 5 个不可判 | 沙箱天花板 | 需能终止的输入或提高 `--steps` |
| **P3** | 项目目的 2 的两项升级 | 未动工 | ① evdev 即插即用 ② `.srm` / `retro_save_state` |
| **终局** | 真机 drop-in 复测 | **唯一终局判据** | `_sdcard_drop8/` 已备；★ 纪律 37/40：先清完设备无关的结构性缺口 |

---

## 八、复现命令（全部本机可跑）

```sh
PY=<含 pyelftools/capstone/unicorn 的 python>

# L1 九道门禁
$PY tools/abi_check.py build/rkgame.rebuilt.elf
$PY tools/dyn_audit.py build/rkgame.rebuilt.elf
$PY tools/verify_layout.py build/rkgame.rebuilt.elf ledger/factory_globals.tsv
$PY tools/relro_audit.py build/rkgame.rebuilt.elf
$PY tools/elf_load_audit.py build/rkgame.rebuilt.elf
$PY tools/mmio_width_audit.py build/rkgame.rebuilt.elf
$PY tools/dup_sym_gate.py build/rkgame.rebuilt.elf
$PY tools/prop_equiv.py
$PY tools/size_coverage_gate.py

# L2 行为尺 + 类别 + 交叉核对
$PY tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf \
    --out report/_diff.txt --dump-rows report/_rows.json --ledger tools/diff_exec_pending.txt
$PY tools/ruler_baseline.py
$PY tools/diverge_cluster.py --rows report/_rows.json
$PY tools/inline_move_audit.py report/_rows.json --verify-meta

# 假实现/假桩 + 两套宇宙
$PY tools/dup_copy_audit.py
$PY tools/fake_impl_audit.py    # 本报告 §四（空壳/恒返回常量/桩落位/源码占位/.dynsym）
```
