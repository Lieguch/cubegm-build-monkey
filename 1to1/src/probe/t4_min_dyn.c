/* ============================================================
 * t4_min_dyn.c —— 「最小动态 ELF」对照样件（probe2 的候选 2）
 *
 * 为什么需要它
 * ---------------------------------------------------------------
 * 已知事实（设备实测）：
 *   · 静态探针（无 .interp / 无 NEEDED）**能跑**
 *   · 5.4MB 动态产物（有 .interp + 5 个 NEEDED，9 个 PT_LOAD）**零日志**
 *
 * 两者之间差了很多变量：**体积 / 段数 / 动态链接 / 依赖库 / 代码量**。
 * 本样件把变量砍到只剩「动态链接」本身：
 *   · 几十行 libc 代码，产物 ~10 KB
 *   · 只依赖 libc.so.6
 *   · 段布局是最朴素的那种
 *
 * 判读（读 probe2 的日志）：
 *   t4 成功 ⇒ 动态链接链路本身没问题 ⇒ 问题在我们的产物的**结构或规模**
 *   t4 失败 ⇒ 连最朴素的动态 ELF 都起不来 ⇒ 聚焦 **loader / glibc / 内核** 这一层
 *
 * 输出写两条路径，只要能写出一条就算跑通。
 * ============================================================ */
#include <stdio.h>

static void try_write(const char *path)
{
    FILE *f = fopen(path, "w");
    if (f) {
        fputs("=== T4 OK: minimal dynamic ELF ran on device ===\n", f);
        fclose(f);
    }
}

int main(void)
{
    try_write("/sdcard/cubegm/_diag/T4-OK.txt");
    try_write("/sdcard/cubegm/T4-OK.txt");
    return 0;
}
