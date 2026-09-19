/* ============================================================================
 * libretro stub core —— 让菜单"进入游戏"这条路在沙箱里能继续往下走
 *
 * 背景（第 48 轮侦察）：
 *   `golden/sdcard_min/cores/` 里**只有 config.xml 与 filelist.xml，没有任何 .so**
 *   ⇒ 菜单一旦启动游戏，`Core_Load` 的 `dlopen("%s/cores/%s")` 必然失败，路径到此为止。
 *   而 `Core_Load` / `Load_Proc1` / `Load_Proc2` + libretro 回调是**完全未覆盖**的一块。
 *
 * `Core_Load` 的契约（源码 src/proprietary/core/FUN_002b6f58_Core_Load.c，900 B）：
 *   · dlopen(path, RTLD_NOW=2)
 *   · dlsym("retro_is_support")                  —— 可选；返回 <0 则 dlclose 退出
 *   · dlsym("retro_set_controller_port_device")  —— 可选
 *   · dlsym("retro_load_game")  → (*f)(&game)    —— **必需；返回 0 会被 unload+deinit+dlclose**
 *   · run_process("retro_set_progress_callback", progress)
 *   · 之后 Load_Proc2()：dlsym("retro_get_region")（**缺则直接 return**）、
 *     dlsym("retro_run")、dlsym("SetFrameSkip")
 *
 * ⇒ 本 stub 的取舍：
 *   · `retro_load_game` 返回 **1**（让 Core_Load 走"成功"分支 → Load_Proc2 → 主循环）；
 *   · `retro_get_region` 返回 **0**（NTSC；`Load_Proc2` 据此把 `sound_len` 设为 0xb7c）；
 *   · `retro_run` 空实现（主循环每帧调用 ⇒ 这是覆盖 libretro 交互的入口）；
 *   · 其余导出给最小/合理返回值，供上层 `RARCH_LOG` 走"find ... process"分支。
 *
 * ★★ 两条硬约束：
 *   1. **不调用任何 libc 函数** ⇒ 空依赖，绝不可能引入 > GLIBC 2.7 的符号
 *      （设备侧 glibc 天花板 = 2.17，而本工程链接目标是 ≤2.7 —— 见项目 MEMORY 红线）。
 *   2. 用 `zig cc -target arm-linux-gnueabihf` 构建（与主体一致），硬浮点 ABI：
 *      ARM32 + EABI5 + hard-float（`e_flags = 0x05000400`）。
 *
 * 用法（下一轮接 CI 时）：
 *   zig cc -target arm-linux-gnueabihf -shared -fPIC -nostdlib -O1 -o libemu_stub.so stub_core.c
 *   然后按 filelist.xml 里出现的 core 文件名逐个复制成 `cores/<name>`（stage 阶段、两侧共用）。
 * ========================================================================== */

/* ---- 最小 libretro ABI（只声明本 stub 需要的部分；不 include 任何头文件） ---- */
typedef unsigned int   rk_u32;
typedef unsigned long  rk_size;   /* ARM32: 4 字节 */

struct rk_game_info {
    const char  *path;
    const void  *data;
    rk_size      size;
    const char  *meta;
};

/* ---- Core_Load 直接/间接会 dlsym 的导出 ---- */

/* 返回非 0 = 载入成功。Core_Load 在返回 0 时会 unload+deinit+dlclose。 */
int retro_load_game(const struct rk_game_info *game)
{
    (void)game;
    return 1;
}

/* Load_Proc2 的**必需**项：dlsym 不到就直接 return，不进入主循环。
 * 返回值语义（pal_ntsc）：0 = NTSC，非 0 = PAL。返回 0 ⇒ sound_len = 0xb7c。 */
int retro_get_region(void)
{
    return 0;
}

/* 主循环每帧调用 —— 空实现即可（本 stub 的目的是"让路径走通"，不是模拟真实核心）。 */
void retro_run(void)
{
}

/* ---- 可选导出：给了就让上层的 "find ... process" 分支走到，便于观测 ---- */

/* 返回 <0 表示不支持该 ROM ⇒ Core_Load 会 dlclose 退出。返回 0 = 支持。 */
int retro_is_support(const char *rom)
{
    (void)rom;
    return 0;
}

void retro_set_controller_port_device(unsigned port, unsigned device)
{
    (void)port;
    (void)device;
}

void retro_set_progress_callback(void *cb)
{
    (void)cb;
}

void retro_unload_game(void)
{
}

void retro_deinit(void)
{
}

void retro_init(void)
{
}

void SetFrameSkip(int skip)
{
    (void)skip;
}

/* 若上层还会探测分辨率/几何，给一套保守缺省（256x224 = 经典 FC 尺寸）。 */
void retro_get_system_av_info(void *info)
{
    (void)info;
}
