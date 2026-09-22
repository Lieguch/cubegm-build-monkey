/* ============================================================
 * start.S —— 探针的最小入口（**无 libc、无 CRT、无 .interp**）
 *
 * 为什么手写：探针的全部意义是"把被测对象的复杂度剥干净"。
 * 用 zig/clang 的默认 CRT 会引入 crt1.o / `__libc_start_main` / PT_INTERP，
 * 那正是我们要排除的变量之一（真机上"内核 exec 失败"与"ld.so 加载失败"
 * 必须能被区分开）。
 *
 * 说明：
 *   · `-nostdlib -static` ⇒ 无 `.interp`、无 NEEDED、无 DT_INIT。
 *   · bss 清零由内核按 PT_LOAD 的 memsz 完成（`.bss` 在 PT_LOAD 的 memsz 里）。
 *   · exit_group(248) 直接结束整个线程组，不留悬挂进程。
 * ============================================================ */
    .syntax unified
    .arm

    .text
    .global _start
    .type _start, %function
    .align 2
_start:
    bl      probe_main
    mov     r7, #248          /* __NR_exit_group (ARM EABI) */
    mov     r0, #0
    svc     #0
1:  b       1b
    .size _start, . - _start
