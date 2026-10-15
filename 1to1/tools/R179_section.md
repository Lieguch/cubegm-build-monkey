## R179（2026-10-15）

### 完成事项

1. **P0 DCE 债务从 13 条 → 5 条：8 条 UB-DCE 全部根修 + Δ 归零（云机铁证，全走 CNB 云开发 SSH 直连，零 CI 额度）**：
   - 本轮对 R178「10 条合法 DCE」定性做了**反汇编复核**（这是 R178 判据盲区的必然延伸），发现 R178 的
     `factory_fn_stack.py` 只统计 sp/fp/r7 直接 ldr/str，`ldmib`/`ldr[rn+off]` 块读被跳过 ⇒
     **3 条被误判为「合法 DCE」的实为同族 UB-DCE**（load_state/save_state 在 R178 已列入 13 条债务，
     R178 只定成「低风险」，本轮证明它们与 joystick/video/PauseMenu 走同一个 blockcopy 块读路径）。
   - 云机 `delta_of` 单文件复现 + 全量门禁 + `--self-test` 三项全部通过：
     * **8 条 UB-DCE 真缺陷**（栈槽被 `blockcopy`/`blockadaptive`/`mui_blockcopy` 的 `param_1[5]`/`param_2[5]`
       等 stride 槽块读走，或 `stm`/`ldm` 8 字节块拷被 Ghidra 拆成「4 字常量 + 死指针」）：
       `mui_joystick_setting`(af820/24/28/2c)、`mui_video_setting`(af820/24/28/2c)、`PauseMenu`(af820/24/2c)、
       `mui_load_state`(af820/24)、`mui_save_state`(af820/24)、`DisplayPage_list`(af2a0，本轮新定性)、
       `TestUSBJoy`(af00c/010/014，本轮新定性)、`mui_DisplayGameSum`(0020202d，本轮新定性)；
     * **修法**：与 R173 `FBA_Load` 完全同构的**栈槽数组化**（把 12 个连续 int 槽声明为 `int blk[12]`，
       `&blk[6]`/`&blk[0]` 传参 ⇒ 地址逃逸覆盖整段，-Os 不再消除写入）。`TestUSBJoy` 用 `local_148[8]`
       折叠 3 个 `uStack_*` 标量为 [5..7]，越界读变界内读。
   - `mui_DisplayGameSum` 的 0x20202d 是**伪符号**：工厂反汇编 `ldr r3,[pc,#0x2c0e5c]; ldm r3,{r0,r1}; stm r8,{r0,r1}`
     ⇒ r3=0x2dce44，该处字节 `20 20 2d 2f 2d 20 20 00` = 字符串 `"  -/-  "`。Ghidra 把后 4 字节 `-  \0`
     (小端 0x0020202d) 误读成指针符号（而真正的 0x20202d 处是别处数据 `0e d1 0d 20..`），
     于是拆成「第一字=0x2f2d2020 常量 + 第二字=DAT_0020202d 死指针」的假结构。
     **根修 = `memcpy(uStack_98, "  -/-  ", 8)`**（字节级核对：工厂写入 uStack_98 的正是这 8 字节）。
   - `tools/dce_ref_diff.py` 的 `ALLOW` 债务表**从 13 条缩到 5 条**，全量门禁输出：
     「扫描 214 个文件；编译失败跳过 0 个；★ 表外新增 Δ 的文件 0 个；已登记待核债务 5 条」。

2. **P0 剩余 5 条债务定性为「真·合法 DCE」（反汇编铁证，非猜测）**：
   - `mui_menu`/`mui_type`/`mui_search`/`mui_recent`/`mui_shoucang` 的 `local_32c = (&DAT_003b2320)[i*0x101]`：
     逐个在工厂反汇编里数栈槽（sp#420 / #340 / #340 / #860 / #428）⇒ **每个都只有一条 `str`、全函数无任何 `ldr` 读回**。
     即这些槽确实是「写了从不读」，-Os 消除不影响语义 ⇒ 留在 ALLOW 并改写理由为「合法 DCE（见 R179）」。

3. **P0 门禁自证复跑通过**（云机 `--self-test`）：正例/反例/回归/非法输入四项全 ✓，确认仪器可信后才引用其结论。

4. **P0 回退确认（残留 struct 检查）**：对 R178 曾误改的 5 个 TU grep `struct {` / `pm.a820` 等 ⇒ 无残留 struct 块；
   R178 的「struct 合并」误改本轮已全部被数组化根修取代（diff 只含数组化/块拷/注释，无 R178 残留）。

### 新发现与决策

1. **★ R178 判据盲区的实际杀伤范围被量化**：13 条债务里 **8 条是真缺陷、仅 5 条合法**。R178 判「10 合法 + 3 UB」，
   实际是「5 合法 + 8 UB」。根因不变：`factory_fn_stack.py` 不认块读。本轮**用工厂反汇编直接数栈槽读写**
   （`ldm/stm/ldr[sp,#disp]`）替代该仪器做定性 ⇒ 这是比仪器更强的判据，因为「写后是否有读回」是汇编事实、无推断成分。
2. **★ 块读函数族的 stride 槽是 UB-DCE 高发区**：`blockcopy`/`blockadaptive`/`mui_blockcopy` 都读
   `param_1[0,1,2,5]` + `param_2[0..5]`。凡 Ghidra 把传入的连续 12-int 栈槽拆成独立标量的 TU，param_1[5]/param_2[5]
   （stride，常见为 `xxx << 1`）就会成为「地址逃逸不到的假死写」。本轮 6 条（joystick/video/PauseMenu/load/save/DisplayPage）
   全属此族。
3. **★「写了不读」必须逐槽在反汇编里数，不能靠 C 源码形态**：C 源码里 `local_32c` 只赋值不读，看着像死写，
   但若它是某个 12-int 块读槽数组的一员，就可能是活的（load_state/save_state 正是如此）。
   反过来 `b2320` 组在 C 里也只赋值不读，反汇编证明其槽无读回，才是真死写。**两种形态在 C 层无法区分，必须落到汇编。**
4. **★ 伪符号（misread constant as pointer）是独立于 UB-DCE 的第三种 Δ 来源**：`mui_DisplayGameSum` 的 0x20202d
   既非真缺陷也非死写，而是 Ghidra 把字符串字节流误解为指针。修法不是数组化而是还原真实字面量。
   同类风险：任何「8 字节块拷」被拆成「常量 + 指针」的地方都可能有。
5. **CNB 云开发免密 SSH 直连通道本轮全程可用**（`cnb-nbv-1k4uir0dq`），编译/扫描/自证/字节核对全部零 CI 额度。

### 下一步待办

1. **P0 双远端推送**：R179 段 + 8 个修复 TU + `dce_ref_diff.py` ALLOW，推 GitHub（`Lieguch/cubegm-build-monkey`）+
   CNB（`lieguch/cubeGM`）。
2. **P1（联网，云机代查）**：`tzubertowski/TreeFrogUI` cores.md ↔ folder→core 映射对表；
   `madcock/sf2000_multicore` retro_core_t 函数表作 libretro 接口层权威对照。
3. **P1（仪器）**：`factory_fn_stack.py` 增加「取 &local 地址 + 被调函数 ldmib/ldr[rn+off] 间接读」识别，
   补掉 R178/R179 两轮都吃到的判据盲区（长期项；当前已用「反汇编直接数槽」绕过，但门禁自动化仍需要它）。
4. **P1（可选）**：对 `blockcopy`/`blockadaptive`/`mui_blockcopy` 三个块读函数本身做一次
   「调用点栈槽布局」全量核对，确认没有第 9 条漏网（本轮 6 条来自静态分析已知调用点，未穷举所有调用者）。
5. **P2**：R36S Wiki（RK3326）菜单行为第二参照物；B6 观测天花板突破（driver.so 私有画布）。
