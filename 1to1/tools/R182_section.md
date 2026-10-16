## R182（2026-10-16）

### 一、日期

2026-10-16（CNB 云开发 `cnb-fdd-1k515nmtt`，arm 交叉编译环境 + capstone 5.0.7；全程零 CI 额度）

### 二、完成事项

1. **P0（R180+R181 双远端推送闭环，先核验后补推）**：
   推送前逐文件核验发现 **R180 的 4 个修复 TU 与 R181 的 `verify_blk12.py` 在两个远端都不存在**
   （远端只到 R179 的 8 个 TU）⇒ 本轮补齐并落档：
   - PROGRESS.md 原子追加 R180+R181 段（5499 B，`old_intact=True`，555198 → 560697 B）；
   - GitHub `Lieguch/cubegm-build-monkey` commit `2c4ef3d5b43f`（增量上传 9 blob，`VERIFY 928/928 blobs match`）；
   - CNB `lieguch/cubeGM` commit `35d3a94`（9 files changed，灾难性缩水门禁通过）；
   - 推送后复核：4 个 TU 均含 `R180` + `int blk[12]/[6]`，`verify_blk12.py` 与 R180+R181 段均在主线。

2. **P1（R179 待办 3，判据盲区的门禁自动化根修）`tools/factory_fn_stack.py` 增加「被调函数间接读（块读）识别」**：
   - **判据**：扫描本函数 `bl <callee>` 调用点，**势精度**跟踪 r0–r3 是否持帧地址
     （`add rX, sp|fp|r11, #imm` / `mov rX, sp` / `mov rX, rY` 传播 / **`str rX,[sp,#S]`→`ldr rX,[sp,#S]` 栈槽中转** /
     `add rX, rY, #imm` 指针偏移 / APCS 别名 `ip`=`sb`=`fp` 规范化）；再进被调函数用**同一套跟踪**
     （初值 = 参数基址，支持 `mov r6,r0` 后经 r6 索引）找 `ldm{ia,ib,da,db} rn,{list}` 与 `ldr rd,[rn,#imm]` 块读；
     被覆盖的「写了从不读」槽**判定翻转为「不是死槽」**；`ldr rd,[rn,ri]` 寄存器索引读只警告、不给槽位（保守方向）。
   - **自证**：`--self-test` **28 项全过**（旧 6 项 + 新增 3 正例 / 4 反例，全部手算答案的合成 ARM 机器码）。
   - **云机真实 ELF 验证**（`golden/factory.rkgame.bin` + symtab）：10 个 UB-DCE 案例**全部检出**块读调用点与槽位
     （load_state / save_state / SeletEmuCore / DisplayThumbnail / mui_recent / mui_shoucang /
     joystick_setting / video_setting / PauseMenu / DisplayPage_list）。
   - **A/B（`--no-indirect` 旧判据 vs 新判据，死槽数）**：

     | 函数 | 旧判据 | 新判据 | 说明 |
     |---|---|---|---|
     | `mui_load_state` | 13 | **3** | blockcopy@0x2ec64(r0=sp+0x64,r1=sp+0x4c) + blockadaptive@0x2ee3c，12 槽被间接读 |
     | `mui_save_state` | 9 | **2** | 6 个调用点（blockcopy/blockadaptive/popwindows/popoffwindows） |
     | `mui_recent` | 10 | **5** | popwindows/popoffwindows 5 槽 |
     | `mui_shoucang` | 7 | **2** | popwindows/popoffwindows 5 槽 |
     | `mui_menu` / `mui_type` / `mui_search` | 1 / 4 / 7 | **1 / 4 / 7** | ★ **阴性对照：零变化**（b2320 是真·合法 DCE，不滥翻） |

   - 实现期实测踩掉 **5 个自身缺陷**（都靠自证/实跑抓出，非推理）：capstone `op_str` **不含助记符**；
     立即数是 `#0x40` **十六进制**（旧正则只认十进制 ⇒ `add ip,sp,#0x4c` 被漏判）；
     `bl` 目标 capstone **已解析成绝对地址**（勿再 `<<2`）；`ldmia` 被 capstone **归一成 `ldm`**；
     APCS 别名 `ip/sb/fp` 不被 `r\d+` 匹配。

### 三、新发现与决策

1. **★ 工厂取块读实参的真实形态是「地址经栈槽中转」**：`add ip, sp, #0x4c` → `str ip, [sp, #0x18]`
   → （隔 0x130 字节）→ `ldr r1, [sp, #0x18]` → `bl blockcopy`。只做寄存器级跟踪会**整条漏掉** ——
   这是本仪器必须支持栈槽中转的直接原因（`mui_load_state` 的 blockcopy 实参因此一度只抓到 r0、漏了 r1）。
2. **★ 被调函数把参数搬到 r4/r6/r7 再用**（`mov r6, r0` → `ldmib r6, {r0, ip}`）是
   blockcopy / blockadaptive / mui_blockcopy / popwindows 的**一致形态** ⇒ 被调函数侧也必须做指针传播，
   不能只认 r0–r3。
3. **★ 新判据的判别力有阴性对照证明**：`mui_menu`/`mui_type`/`mui_search`（纯 b2320 合法 DCE）
   在新判据下死槽数**一个不变**（1/4/7）⇒ 翻转只发生在真有块读的地方，不是"把一切写成活的"。
4. **★ R178 判据盲区至此在两个方向都堵住**：产物侧 `verify_blk12.py`（我方 -Os 是否真写了槽）+
   工厂侧 `factory_fn_stack.py --indirect`（原厂这些槽是否真被读）。二者互为交叉验证。

### 四、下一步待办

1. **P0 双远端推送**：R182 段 + `factory_fn_stack.py` + `PROJECT-MEMORY.md` 纪律 166，
   推 GitHub + CNB（清单 `tools/filelist.py` 已含全部文件）。
2. **P1（可选）**：把 `factory_fn_stack.py` 的间接读判据接进 `dce_ref_diff.py` 的 Δ 分诊
   （现在 Δ 只是待核清单，可自动附「该文件哪些槽被块读覆盖」）。
3. **P2**：R36S Wiki 第二参照（R174 已完成，`report/r36s_second_reference.md`）；
   B6 观测天花板突破（driver.so 私有画布）。
