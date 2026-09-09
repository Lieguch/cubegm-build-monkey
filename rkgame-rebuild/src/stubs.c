/* ============================================================
 * rkgame-rebuild — stubs.c
 *
 * 原厂 rkgame main() 调用但 rebuild 中无实质需求的函数桩。
 * 全部对齐 Ghidra 反编译，保持调用链完整（日志可追溯）。
 *
 * 工厂实证（Ghidra 01_main_emurun_joystick.c:124-160）：
 *   main() {
 *     GetConfig();
 *     dispmeninfo();
 *     video_driver_init();
 *     sound_driver_init(USE_HDMI_OUT, UpdateROM, 2);
 *     InitJoystick();
 *     InitRFJoystick();     /* ← stub: 无 RF 硬件 */
 *     sfc_init();           /* ← stub: 无 SPI 硬件 */
 *     spi_driver_init();    /* ← stub: 无触摸屏 SPI */
 *     UpdateROM("update/firmware.upk");  /* ← stub: 无升级需求 */
 *     ShareMemCreat();
 *     pthread_create(XintiaoThread);
 *     main_Menu() / autorun();
 *   }
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "stubs.h"
#include "rkgame.h"
#include "debug.h"

/* ============================================================
 * dispmeninfo() — 诊断 /proc/meminfo + 显示分辨率
 *
 * 原厂 @ 0x9e7c: 读取 /proc/meminfo 打印内存信息。
 * 我方：从 /proc/meminfo 读取 MemTotal/MemFree/MemAvailable，
 *       同时打印 DRM framebuffer 分辨率（如可用）。
 * ============================================================ */

void dispmeninfo(void)
{
    FILE *fp = fopen("/proc/meminfo", "r");
    if (!fp) {
        LOG("dispmeninfo: /proc/meminfo not accessible");
        return;
    }

    char line[256];
    unsigned long total_kb = 0, free_kb = 0, avail_kb = 0;
    unsigned long buffers_kb = 0, cached_kb = 0;

    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "MemTotal: %lu kB", &total_kb) == 1) continue;
        if (sscanf(line, "MemFree: %lu kB", &free_kb) == 1) continue;
        if (sscanf(line, "MemAvailable: %lu kB", &avail_kb) == 1) continue;
        if (sscanf(line, "Buffers: %lu kB", &buffers_kb) == 1) continue;
        if (sscanf(line, "Cached: %lu kB", &cached_kb) == 1) continue;
    }
    fclose(fp);

    LOG("dispmeninfo: MemTotal=%lu MB, MemFree=%lu MB, MemAvailable=%lu MB, "
        "Buffers=%lu MB, Cached=%lu MB",
        total_kb / 1024, free_kb / 1024, avail_kb / 1024,
        buffers_kb / 1024, cached_kb / 1024);

    /* DRM framebuffer 分辨率（如 disp 已初始化） */
    if (disp_is_ready()) {
        LOG("dispmeninfo: DRM fb %dx%d (pitch=%u, bpp=%u)",
            disp_fb_width(), disp_fb_height(),
            0, 32);
    } else {
        LOG("dispmeninfo: DRM not ready");
    }
}

/* ============================================================
 * sfc_init() — SFC 子系统初始化桩
 *
 * 原厂 @ 0x29b94: 初始化 SFC (SuperFamicom) 子系统。
 * 我方：无 SFC 硬件（走 libretro core），空实现。
 * 保留调用以对齐原厂 main() 顺序。
 * ============================================================ */

int sfc_init(void)
{
    LOG("sfc_init: stub (no SFC hardware; libretro core handles emulation)");
    return 0;
}

/* ============================================================
 * spi_driver_init() — SPI 驱动初始化桩
 *
 * 原厂 @ 0x29c40: 初始化 SPI 驱动（触摸屏/RF 手柄接收器）。
 * 我方：无 SPI 硬件需求，空实现。
 * ============================================================ */

int spi_driver_init(void)
{
    LOG("spi_driver_init: stub (no SPI hardware on RK3036G rebuild path)");
    return 0;
}

/* ============================================================
 * UpdateROM() — 固件升级桩
 *
 * 原厂 @ 0x2b5a4c: 加载 update/firmware.upk 并执行固件升级。
 * 我方：无固件升级需求，空实现。
 * 作为 sound_driver_init 的回调（原厂传 UpdateROM，我方传 NULL）。
 * ============================================================ */

int UpdateROM(const char *path)
{
    (void)path;
    LOG("UpdateROM: stub (no firmware upgrade needed)");
    return 0;
}

/* ============================================================
 * InitRFJoystick() — RF 无线手柄初始化桩
 *
 * 原厂 @ 0x29e1c: 初始化 RF 无线手柄接收器。
 * 我方：无 RF 硬件，空实现。
 * USB 手柄通过 evdev + inotify 热插拔处理（evdev.c）。
 * ============================================================ */

int InitRFJoystick(void)
{
    LOG("InitRFJoystick: stub (no RF hardware; USB via evdev + inotify)");
    return 0;
}

/* ============================================================
 * resource_cpd_load() — resource.cpd / UI_Res.cpd 加载桩
 *
 * 原厂：加载 resource.cpd / UI_Res.cpd 中的 UI 资源。
 *
 * ★ 联网搜索修正（2026-09-07，R36S Wiki）：
 *   .cpd 实际是 ZIP 格式（非自定义容器），可直接用 unzip 解压。
 *   资源结构：
 *     - UI_Res.cpd: 平台背景（640x480 BGRA raw）、图标精灵表、设置屏幕
 *     - resource.cpd: 游戏列表布局（game.raw）、菜单布局（menu.raw）、
 *                     无数据占位图（nodata.raw, 320x240 RGB565）、ui.cfg
 *     - ui_*.cpd: 语言特定覆盖（26 种语言）
 *     - joystick.cpd: 控制器映射图像
 *
 * 我方：当前 UI 走 ui_*.zip 包（ui_en/cn/sp/ru/ar/po/ko/ge/fr），
 *       .cpd 格式与 .zip 兼容（都是 ZIP），但文件名和内容结构不同。
 * 保留桩函数以备后续接入 .cpd 解压。
 * ============================================================ */

int resource_cpd_load(const char *path)
{
    (void)path;
    /* 已由 cpd.c 实现 .cpd 加载（.cpd = ZIP 格式） */
    LOG("resource_cpd_load: superseded by cpd_load_resource / cpd_load_ui_res");
    LOG("resource_cpd_load: factory resources:");
    LOG("resource_cpd_load:   UI_Res.cpd  = backgrounds + icon sprites");
    LOG("resource_cpd_load:   resource.cpd = game.raw/menu.raw/nodata.raw/ui.cfg");
    LOG("resource_cpd_load:   ui_*.cpd    = 26 language overlays");
    LOG("resource_cpd_load:   joystick.cpd = controller mapping images");
    return 0;
}

/* ============================================================
 * 音频就绪检查 / 音频播放 — 由 audio.c 实现，此处提供 fallback 桩
 * 若 audio.c 被裁剪，主循环仍可继续（不崩溃）
 * ============================================================ */

bool audio_is_ready(void)
{
    return false;
}

void audio_play(const void *buf, size_t frames)
{
    (void)buf; (void)frames;
}

/* ============================================================
 * build_sstate_path() — 构造 Save State 文件路径
 * 实际实现由 sram.c 提供，此处为 fallback 桩
 * ============================================================ */

void build_sstate_path(char *out, size_t out_sz, int slot)
{
    if (!out || out_sz == 0) return;
    snprintf(out, out_sz, "/sdcard/cubegm/saves/sstate_%02d.sstate", slot);
}

/* ============================================================
 * g_initscr_ready() — 检查初始化屏幕是否就绪
 * 实际实现由 disp.c 提供，此处为 fallback 桩
 * ============================================================ */

int g_initscr_ready(void)
{
    return 1;
}

/* ============================================================
 * 诊断输出
 * ============================================================ */

void stubs_report(void)
{
    LOG("stubs: dispmeninfo/sfc_init/spi_driver_init/UpdateROM/");
    LOG("stubs:       InitRFJoystick/resource_cpd_load — all stubbed");
    LOG("stubs: real implementations needed for:");
    LOG("stubs:   - SFC hardware (libretro core handles)");
    LOG("stubs:   - SPI touchscreen/RF (not on RK3036G)");
    LOG("stubs:   - firmware upgrade (no update/ dir)");
    LOG("stubs:   - RF wireless joystick (USB via evdev)");
    LOG("stubs:   - resource.cpd (.cpd format not reverse-engineered)");
}
