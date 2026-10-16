## R180+R181（2026-10-15）—— UB-DCE 家族第 9–12 条根修 + 块读参数槽死写门禁（`verify_blk12.py`）

### 一、日期

2026-10-15（R180 根修 4 条漏网 + R181 仪器自修与 12 TU 全量复测；全部走 CNB 云开发 SSH 直连 `cnb-nbv-1k4uir0dq`，arm-linux-gnueabihf-gcc 14.2，零 CI 额度）

### 二、完成事项

1. **P0（R179 待办 4「穷举块读调用者」）执行 ⇒ 又抓出 4 条同族漏网并全部根修**：
   全仓 grep 五个块读函数（`blockcopy`/`blockadaptive`/`mui_blockcopy`/`popwindows`/`popoffwindows`）的调用点，
   共 **12 个 TU**；逐一在云机编译 `-O0` vs `-Os` 对比栈存储，发现 R178/R179 判据盲区之外还有 4 条：

   | TU | 槽区间 | -Os 实测（修复前） | 集合级 Δ 为何放行 |
   |---|---|---|---|
   | `mui_DisplayThumbnail` | -0x388..-0x35c（12 槽） | `bl mui_blockcopy` 前仅 **2 条** str（param_1[0]/param_2[0]），其余 10 槽栈垃圾 ⇒ 缩略图 blit 用错 stride/src/dst | af29c/af2a0/af6b8/af6bc/af6c0/af6c4 在本函数 memcpy 循环仍被引用 ⇒ 符号未消失 ⇒ Δ=[] |
   | `SeletEmuCore` | -0x158..-0x12c（12 槽） | 调用#1 前只写 **9 槽**，#3/#4/#5 各 **2 槽**；常量 `0x21c/0x1a4/0x438` 在 -Os 里**完全消失**（只余循环边界 cmp）⇒ 选核界面 blit 错位 | 这些槽写的是**常量**，不引用任何 `DAT_*` ⇒ 永远不进 Δ |
   | `mui_recent` | -0x628..-0x610（6 槽） | `add r0, sp, #44` 后只有 **1 条** `str r3,[sp,#44]` ⇒ popwindows 读的 x/y/w/h/stride 五字段全垃圾 | local_628/624/620/61c/618 都引用 `DAT_003af28c`，该符号在 TU 别处仍被引用 ⇒ Δ=[] |
   | `mui_shoucang` | -0x4a8..-0x490（6 槽） | `add r0, sp, #20` 后只有 **1 条** `str r3,[sp,#20]`，同型 | 槽引用 `DAT_003af28c`/`DAT_003af2a0`，符号在场 ⇒ Δ=[] |

   修法统一为**栈槽数组化**（`int blk[12]` / `int blk[6]`，`&blk[6]`/`&blk[0]` 或 `(gh_u4 *)blk` 传参），
   与 R173 `FBA_Load`、R179 八条完全同构；每处带证据注释（槽区间 / 汇编铁证 / Δ 放行原因 / 回退方法）。

2. **P0（R181）新增 `tools/verify_blk12.py` —— 不依赖符号集合的 -Os 参数槽判据**：
   判据 = 编译 -O0/-Os → 切函数体 → **势精度**跟踪 r0/r1 实参基址 → 要求每个基址起的 6 个 int 槽
   都在「此前累计写过的栈槽集合」里（str/strb/strh/strd/stm 全计，strd 写 2 槽）。
   首版即暴露**自身三处缺陷**并全部根修：
   - 固定 12 行回看窗口太短（`mui_shoucang` 的 `add r0,sp,#24` 距 `bl popwindows` 有 **22 行**）⇒ 改势精度寄存器跟踪（遇标签/分支/调用即失效）；
   - 两组参数槽连数 12 会把 param_2 的 6 槽算到 param_1 头上（**把已修好的文件误报为死写**）⇒ r0/r1 各自起 6 槽分别判；
   - `mov r1, sp`（偏移 0，`DisplayPage_list` 的 param_2 基址）不被识别 ⇒ MOV 正则补 `sp|fp`。

3. **复测通过**：12 个块读调用方 TU 在 `-Os` 下**全部 PASS**（每一处调用的实参基址起的 6 槽均全写，无参数槽死写）。
   覆盖：popwindows / popoffwindows / mui_joystick_setting / mui_video_setting / PauseMenu / mui_load_state /
   mui_save_state / DisplayPage_list / mui_DisplayThumbnail / SeletEmuCore / mui_recent / mui_shoucang。

### 三、新发现与决策

1. **★ R179「8 条 UB-DCE」之后还有 4 条同族 ⇒ 累计 12 条全部根修**（R179 八条 + R180 四条）。
   根因不变：Ghidra 把连续参数槽拆成独立标量 + 块读函数按 `int*` 索引越界读 ⇒ C 标准下是 UB，`-Os` 删死存储。
2. **★★ 集合级 Δ 门禁（`dce_ref_diff.py`）的第二个盲区被量化（GAP 18.01 变体）**：
   死写消除**不改变符号在场性**时 Δ 为空。本轮两种变体都见到：
   ① 符号在 TU 别处仍被引用（DisplayThumbnail / mui_recent / mui_shoucang）；
   ② 槽里写的是**常量**、根本不引用 `DAT_*`（SeletEmuCore）。
   ⇒ **结论：DCE 判定不能只靠符号集合差，必须落到「实参基址起的槽是否真被写」的汇编级判据**（`verify_blk12.py`）。
3. **★ 仪器自身的缺陷比被测缺陷更隐蔽**：`verify_blk12.py` 首版同时有假阴（窗口太短）与假阳（两组连数 / 跨基本块误取实参），
   任一种都会直接产生错误结论。势精度寄存器跟踪 + 分组校验是这类判据的正确形态。
4. **回退面**：每个 TU 的改动仅「12/6 个标量声明 → `int blk[N]`」+ 调用形式 + 证据注释，无语义漂移；`git checkout` 单文件即可回退。

### 四、下一步待办

1. **P0 双远端推送**：R180 四个修复 TU + R181 `verify_blk12.py` + 本段 + `PROJECT-MEMORY.md` 纪律 165，
   推 GitHub（`Lieguch/cubegm-build-monkey`）+ CNB（`lieguch/cubeGM`）。清单 `tools/filelist.py` 已含全部文件。
2. **P1（仪器长期项）**：`factory_fn_stack.py` 增加「取 `&local` 地址 + 被调函数 `ldmib`/`ldr[rn+off]` 间接读」识别，
   把 R178/R179/R180 三轮吃到的判据盲区在门禁自动化里堵死（当前已由 `verify_blk12.py` + 反汇编直接数槽绕过）。
3. **P2**：R36S Wiki 第二参照（R174 已完成，`report/r36s_second_reference.md`）；B6 观测天花板突破（driver.so 私有画布）。
