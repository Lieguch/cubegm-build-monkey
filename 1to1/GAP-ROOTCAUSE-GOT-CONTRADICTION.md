# 簇 A 真根因验证判据（先写死）

**目标**：确认 `GetCoreIndex` 的 GOT 条目值 0x003b0134 ≠ `default_core_list` 符号 0x003b0254 的根本原因。

**判据**：
- P1：我方 `GetCoreIndex` 反汇编显示 `ldr r5, [pc, r5]` 加载的地址 → 静态 .got 值
- P2：静态 .got dump 在 `0x4de28c` 处的值 → 0x003b0134（已确认）
- P3：符号表 `default_core_list` 地址 → 0x003b0254（已确认）
- P4：factory_image.S 中 `default_core_list` 定义方式（.set 别名 vs 真实对象）
- P5：工厂 GetCoreIndex 如何获得该地址（GOT 间接还是直接绝对？）
- P6：diff_exec 沙箱中 GOT 区域是否被正确映射且初始化为 0？

**反证条件**：若 P1 与 P2 显示沙箱内 r5=0（读 0），但静态值非 0，则根因可能是沙箱 GOT 未初始化；若静态值本身就是 0x003b0134，则根因是 lld 或符号定义问题。

**修正前提**： visszaáltalános（等待实际证据，不得脑补）。
