# AUDIT-1TO1 —— 距「1:1 复刻原厂 rkgame」的全量差距总账

- 版本：**第 101 轮（2026-10-01）** ｜ 本版**取代**第 95 轮版（那份标的是 `c9aba0eb`，已被 §0.44/§0.45/§0.47 三轮产物变更作废）
- 审计标的：`build/rkgame.rebuilt.elf` **sha256 `4dad7fd13081620f…`**（5,513,232 B）
- 对照物：`golden/factory.rkgame.bin` **sha256 `8ff3b4b70c253ff7…`**（原厂，只读红线）
- 判据强度：`diff_exec --batch --steps 3000`（触上限者 ×20 放大重试）
- **行为尺权威基线**：`BASE 4dad7fd13081620f 782 759 18 5 0 0`
- 部署口径：**CNB 代码托管 + CNB 云开发 + GitHub Actions 构建 CI**
- ★ 全部数字机械复算，复算命令附在第一节末。

---

## 一、四层结论

| 层 | 实测 | 状态 |
|---|---|---|
| **L1 结构层** | 9 道硬门禁**全绿**；全局符号命中率 **99.5%（193/194）**、违规 0；`prop_equiv` **★FAIL 0** / WARN 4 / **MISSING 0**（OK 192 / THIN 15 / CALIB 2，213 全计）；`size_coverage` **SHORT 0**（INFO 6）；副本等价性 **EQUIV 1371 / ★DIFF 0 / NEEDS-REVIEW 5**；`.dynsym`「仅我方多余导入」**0** | ✅ **清零** |
| **L2 行为层** | **PASS 759 ｜ DIVERGE 18 ｜ TRUNC 5 ｜ REFDEAD 0 ｜ SKIP 0**（自洽 759+18+5=782）<br>按输入有效性分层：**语义核心 12 ／ 输入顺序伪影 6** | ⏳ **12 个真嫌疑** |
| **L3 真机层** | 修复后**未复测**；`_sdcard_drop8/` 已按当前产物重出 | ⏳ **唯一终局判据** |
| **L4 目的 2** | evdev 即插即用 / SRAM 存取 | ⛔ **未动工** |

### 复算命令（逐条可核对）
```bash
PY=<venv>/python      # C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe
A=build/rkgame.rebuilt.elf
# --- L1（全 rc=0）---
for t in abi_check dyn_audit relro_audit mmio_width_audit elf_load_audit dup_sym_gate; do $PY tools/$t.py $A; done
$PY tools/verify_layout.py $A ledger/factory_globals.tsv | grep 命中率     # 99.5% (193/194)、违规 0
$PY tools/prop_equiv.py                                                    # rc=0；汇总 213 | ★FAIL 0 | WARN 4 | OK 192 | THIN 15 | CALIB 2 | MISSING 0
$PY tools/size_coverage_gate.py | grep -aE "SHORT|INFO"                     # SHORT 0 ；INFO 6（非我方对象实现，不计入 SHORT）
$PY tools/dup_copy_audit.py | sed -n '6,8p'                                # EQUIV 1371 / ★DIFF 0 / NEEDS-REVIEW 5
# --- L2（默认口径 与 只读语料子集）---
$PY tools/diff_exec.py --batch --steps 3000 --ours $A --out report/a.txt                  # 759/18/5/0/0
$PY tools/diff_exec.py --batch --steps 3000 --groups strs --ours $A --out report/b.txt    # 756/12/14/0/0
```

---

## 二、L2 行为层：18 个发散的**分层**（第 100 轮成果）

| 语料 | PASS | DIVERGE | TRUNC |
|---|---|---|---|
| 全部三组（默认口径） | 759 | **18** | 5 |
| **只有有效指针输入（`strs`）** | 756 | **12** | 14 |

⇒ 反向检查：`strs` 下**没有新增发散** ⇒ 分层一致，不是口径漂移。

### 2.1 语义核心（有效输入下仍发散）—— **12 个**
`DisplayPage_list` `DrawFrame` `TestLibz0` `_Z17FormatZipMessageUjPcj` `locale_charset`
`mui_DisplayInputBuffer` `mui_DisplayLine_t` `mui_video_setting` `progress`
`stbtt__get_subrs` `stbtt__tesselate_curve` `xmp3_FDCT32`

### 2.2 输入顺序伪影（只在 NULL/小整数输入下发散）—— **6 个**（**不该改源码**）
`FilePreEmu` `SeletEmuCore` `get_item_from_line` `get_value_from_items` `outputxy1` `strtrim`

证据（两侧静态反汇编：**语义相同、指令排布不同**）：
```
outputxy1  工厂: ldr r5,[pc]; add r5,pc,r5 ; ldr r2,[r5,r2] … ; 0x0a568 ldrb r3,[r6],#1  ← 读 *param 第 16 条
           我方: 0x4e1910 ldrb r7,[r0]                                                    ← 第 3 条
progress   工厂: 先 vldr d16,[r4] / vadd.f64 / vstr（把 d0 累加进全局 double），再 ldrb
```
其中 `strtrim` / `get_item_from_line` 另属 **`UB-PATH`**（空指针解引用路径上的合法加载消除；
`strtriml` 工厂 `0x1f1cc ldrb r3,[r2]` 无条件，我方 `0x4e8ff0 subs/bmi` 把边界判断提到加载之前
⇒ **改 C 修不掉**，见 §0.46-E）。

### 2.3 ⚠️ 对那 12 个的**保留意见**（必须写在报告里，不许含糊）
即使给有效指针输入，这批 UI/状态函数仍因**沙箱里全局状态全为零**而野指针崩溃
（例：`mui_DisplayLine_t` 读 `m_ui+92` 取出的值 `+0x40` → 野地址）。
**观测仍受"崩溃顺序"影响 ⇒ 12 里可能还有伪影。** 在"全局状态播种"（§五 P1-b）完成前，
**不得**把这 12 个都当成真缺陷。

---

## 三、L3 真机层（**唯一终局判据**）—— 未复测

- 现状：`HAVE_MBSINIT` 对齐、陈旧上游对象重编、`strtrim` 参数透传等修复之后，**一次都没上过机**。
- 已备投放包：`_sdcard_drop8/`（t3 = 当前产物 `4dad7fd1`，基线**按产物 sha 反查**，不读固定路径）。
- 项目纪律 37/40 要求"本地装置做完才请用户上机"。本地这一侧还剩 §五 的 P1-a / P1-b 两件；
  **做完即应上机** —— 这是唯一还能产生**新信息**的动作。

---

## 四、L4 目的 2 —— 未动工

| 项 | 状态 |
|---|---|
| evdev 即插即用（手柄热插拔） | ⛔ 未动工 |
| SRAM（`.srm`）存档 RAM 持久化 | ⛔ 未动工 |

---

## 五、未决差距（按优先级，照单可推进）

| 优先级 | 差距 | 为什么是它 / 下一步 |
|---|---|---|
| **P1-a** | **「我方第二份拷贝落在 0x4xxxxx」**（**待验证的假设**） | 受害样本 `mui_DisplayLine_t`：工厂读 `0x3af278`，我方轨迹是 `0x4e8ad8 / 0x4de160`（我方自己的字面池/GOT），且**在读该全局前就死**（13 条 vs 22 条）。地址垫已 `.set DAT_003af278, __f_data_base+0x278`（名义地址 0x3af278 正确）⇒ 须查**是否存在第二份定义/拷贝**、GOT 槽实际指向。**若成立，统一到工厂 VMA 可一次消掉一整类** |
| **P1-b** | **沙箱未播种全局初值** | 见 §2.3：这批函数因状态全零而野指针崩溃 ⇒ 观测窗口不可比 ⇒ 12 个里几个是真缺陷**无法定论**。做法：把工厂映像里具名对象的初值写进沙箱映射区 |
| **P1-c** | `UB-PATH` 类（`strtrim`/`get_item_from_line`…） | 已证"改 C 修不掉"（纪律 93）；而**换编译器杠杆已被数据否决**（§0.47-B）⇒ 需要**显式决策**：接受该类差异，或另找通道。**不要再花轮次试换工具链** |
| P2 | `inline_move.dims_are_mem_only()` **靠解析文本**反推维度 | 判据字段被非判据文本污染会让判据**静默失效**（§0.46-C 实测 18→23）。应改为结构化字段 |
| P2 | **上游对象新鲜度门禁**（现只覆盖 `XUnzip.o`） | "构建产物 ≠ 当前脚本的产物"是**静默**的（§0.44 实测：陈旧对象让 `.dynsym` 多出 3 项） |
| P2 | `dup_copy_audit` 的 **NEEDS-REVIEW 5 项** | `_ZL8z_errmsg` `_mxml_key_once` `all_encodings` `entities` `types`（后两者已判语义等价）⇒ 须人工按语义复核 |
| P2 | 死代码树 `src/upstream/libiconv/`（251 文件 / 104 个空桩头） | 不在产物内、全仓库零引用，但是"像实现、实为空桩"的诱饵 ⇒ 标注 `DEAD-TREE` 或移出 |
| P3 | TRUNC 5：`MP3InitDecoder` `TestRun` `TestUSBJoy` `WaitNMI` `xmp3_AllocateBuffers` | 沙箱天花板（工厂侧同样失败） |
| P3 | L4 目的 2 两项 | evdev / SRAM |
| 终局 | **真机 drop-in** | `_sdcard_drop8/` 已备 |

---

## 六、已关闭的杠杆（**写在这里防重走**）

| 曾经的方向 | 结论 | 证据 |
|---|---|---|
| 换编译器（clang → GCC 6.2/6.3） | **判负，关闭** | 213 TU 单变量：clang ±15% **75.7%** / 中位体积比 0.993 / L1 **0.455**；GCC6.3 74.3% / 0.929 / 0.490；GCC5.4 ≈ GCC6.3（§0.47-B） |
| 优化档（`-O`）对齐 | **已对齐，不是杠杆** | `UPOPT=-O2`；`LIBOPT=-O0` 有普查依据（工厂 304 个 `-O0` 形态函数全属 libiconv） |
| 「两侧早死 ⇒ 不可比」（按 `min(insns)` 截断） | **证伪，已撤销** | DIVERGE 18 → **81**（指令密度跨产物不可对齐；§0.46-A） |
| 「死亡现场地址不同 ⇒ 差异」 | **证伪，已撤销** | 18 → **91**（绝对地址不可比；§0.46-B） |
| 假实现/假代码/假桩 6 项专项 | **4 项清白、2 项属仓库/构建配置问题** | §0.43-B |
| `mbsinit` 配置不对齐 | **已修，收敛 1 个** | §0.44 |
| 陈旧上游对象 | **已对齐**（`.dynsym` 仅我方 3→0） | §0.45-A |
| 16 个根级 `.md` 静默漏推 | **已修**（根级 `.md` 自动纳入，30/30） | §0.43 |
| 一个坏臂删光两个好臂 + `tee` 吞退出码 | **已修 + fail-loud** | §0.47-A |

---

## 七、可核对的进度度量（**不编百分比**）

| 维度 | 度量 |
|---|---|
| L1 结构层 | **9/9 门禁绿**；符号命中率 99.5%；违规 0；副本 ★DIFF **0** |
| L2 行为层 | **759 / 782 = 97.06%** 通过；18 未收敛，其中 **6 已定性为输入顺序伪影** ⇒ **12 待定** |
| 侧信道 | `.dynsym` 仅我方 **0** ／ 仅工厂 **5**（4 个无害弱符号 + `islower`） |
| L3 真机 | **0 次复测** |
| L4 目的 2 | **0 / 2** |
| 仪器 | 12 道门禁；`diff_exec --self-test` **102/102**；`ruler_baseline --self-test` 6/6；口径指纹 `e4f3695f…` 与台账一致 |
