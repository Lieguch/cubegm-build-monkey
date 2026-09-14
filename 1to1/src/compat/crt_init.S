/* crt_init.S — 最小 CRT 初始化桩（`_init` / `_fini`）
 *
 * 为什么需要它（2026-09-14 CI 实测回归）
 * ---------------------------------------------------------------
 * zig 工具链**不提供 crti.o**（GCC 会提供）。缺了它 ⇒ `_init` 未定义 ⇒ 链接脚本里那句
 * `PROVIDE_HIDDEN(_init = 0)` 生效 ⇒ `.dynamic` 出现 **`DT_INIT = 0`** ⇒ glibc 的 `call_init`
 * 见到 DT_INIT 就调用 ⇒ `blx` 到地址 0 ⇒ **SIGSEGV，而且是在任何输出之前**
 * （行为差分表现为"重建侧 0 行 stdout、立即 139"）。
 *
 * 工厂的形态（`golden/factory.rkgame.bin` 实测）
 * ---------------------------------------------------------------
 *   .init  12B @0x95fc : e92d4008  eb0001de  e8bd8008
 *                        push {r3,lr} ; bl <__gmon_start__ 的 PLT> ; pop {r3,pc}
 *   .fini   8B @0x2dbc98: e92d4008  e8bd8008      push {r3,lr} ; pop {r3,pc}
 * `__gmon_start__` 是**弱符号**：未用 `-pg` 链接时其值是 NULL，PLT 桩会直接落到下一条指令
 * ⇒ 那记 `bl` 实际是**空操作**。因此我们提供一个等价的空操作 `_init` 即可（行为一致）。
 *
 * ⚠ 位置约束：必须有 `.init` / `.fini` **输出节**（lld 由它决定 DT_INIT/DT_FINI 的目标地址），
 *   且这两个节必须落在**可执行的 PT_LOAD** 里 —— 本项目由 linker/factory.ld 把它们并进
 *   运行时区的 `.text`（`*(.init) *(.fini)`），不要放进只读的元数据区。
 */
    .syntax unified
    .arm

    .section .init,"ax",%progbits
    .global _init
    .type _init, %function
_init:
    push    {r3, lr}
    pop     {r3, pc}
    .size _init, . - _init

    .section .fini,"ax",%progbits
    .global _fini
    .type _fini, %function
_fini:
    push    {r3, lr}
    pop     {r3, pc}
    .size _fini, . - _fini
