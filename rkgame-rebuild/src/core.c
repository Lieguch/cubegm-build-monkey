/* ============================================================
 * rkgame-rebuild — libretro core 加载器
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <pthread.h>

/* CI 使用 crosstool-NG glibc-2.29 sysroot。
 * dlopen/dlsym/dlclose 全部为 @GLIBC_2.4，设备 glibc 2.29 完全兼容。
 * 无需 __asm__ 版本锁定或运行时兜底。 */

#include "rkgame.h"
#include "debug.h"

/* 按键 bitmask（与 evdev.c 保持一致） */
#define KEY_A       (1u << 4)
#define KEY_B       (1u << 5)
#define KEY_START   (1u << 12)

/* ---- 配置项表 ---- */
static char corecfg[16000];

static void *retro_get_env_cb(void *cb, unsigned cmd, void *data);
static int  get_cfg_value(const char *key, char *out, size_t out_size, const char *cfg);

static void *get_core_symbol(void *handle, const char *name)
{
    return dlsym(handle, name);
}

/* joy_poll 返回 bool，但 retro_set_input_poll 期望 void(*)(void) — 加包装 */
static void joy_poll_wrapper(void)
{
    (void)joy_poll();
}

/* libretro 像素格式全局（默认 RGB565） */
unsigned retro_pixel_format = RETRO_PIXEL_FMT_RGB565;

/* 前端 pixel format 回调：接受核心请求的格式 */
static int retro_pixel_format_cb(unsigned fmt)
{
    (void)fmt;  /* 接受所有常见格式（RGB565 / XRGB8888 / 0RGB1555） */
    retro_pixel_format = fmt;
    return 1;  /* 1 = 接受 */
}

/* audio_play 已符合 legacy sample_batch 签名 void(*)(const void*, size_t)
 * 这里定义同类型别名以便阅读。 */
static void audio_sample_batch_wrapper(const void *data, size_t frames)
{
    audio_play(data, frames);
}

int core_load(const char *rom_path, const char *core_name)
{
    char path[512];
    int ret;

    memset(corecfg, 0, sizeof(corecfg));
    snprintf(path, sizeof(path), "%s/cores/%s.cfg", work_path, core_name);
    {
        FILE *fp = fopen(path, "r");
        if (fp) {
            size_t n = fread(corecfg, 1, sizeof(corecfg) - 1, fp);
            corecfg[n] = '\0';
            fclose(fp);
            LOG("core config loaded: %s (%zu bytes)", path, n);
        } else {
            LOG("core config not found: %s (OK, using defaults)", path);
        }
    }

    snprintf(path, sizeof(path), "%s/cores/%s", work_path, core_name);
    DBGP(CORE_DLOPEN);
    core_handle = dlopen(path, RTLD_NOW);
    if (!core_handle) {
        ERR("Core_Load: dlopen %s fail", path);
        return -1;
    }
    LOG("Core_Load: dlopen %s OK", path);

    /* 加载该核心的键位映射（InitKeyMapping0fEmuType） */
    InitKeyMapping0fEmuType(core_name);

    memset(&ctx, 0, sizeof(ctx));
    ctx.retro_get_system_info      = get_core_symbol(core_handle, "retro_get_system_info");
    ctx.retro_get_system_av_info   = get_core_symbol(core_handle, "retro_get_system_av_info");
    ctx.retro_init                 = get_core_symbol(core_handle, "retro_init");
    ctx.retro_deinit               = get_core_symbol(core_handle, "retro_deinit");
    ctx.retro_load_game            = get_core_symbol(core_handle, "retro_load_game");
    ctx.retro_unload_game          = get_core_symbol(core_handle, "retro_unload_game");
    ctx.retro_run                  = get_core_symbol(core_handle, "retro_run");
    ctx.retro_is_support           = get_core_symbol(core_handle, "retro_is_support");
    ctx.retro_serialize_size       = get_core_symbol(core_handle, "retro_serialize_size");
    ctx.retro_serialize            = get_core_symbol(core_handle, "retro_serialize");
    ctx.retro_unserialize          = get_core_symbol(core_handle, "retro_unserialize");
    ctx.retro_get_memory_data      = get_core_symbol(core_handle, "retro_get_memory_data");
    ctx.retro_get_memory_size      = get_core_symbol(core_handle, "retro_get_memory_size");
    ctx.retro_set_environment      = get_core_symbol(core_handle, "retro_set_environment");
    ctx.retro_set_video_refresh    = get_core_symbol(core_handle, "retro_set_video_refresh");
    /* legacy batch API — 与原厂一致 */
    ctx.retro_set_audio_sample_batch = get_core_symbol(core_handle,
        "retro_set_audio_sample_batch");
    ctx.retro_set_audio_callback   = get_core_symbol(core_handle, "retro_set_audio_callback");
    ctx.retro_set_input_poll       = get_core_symbol(core_handle, "retro_set_input_poll");
    ctx.retro_set_input_state      = get_core_symbol(core_handle, "retro_set_input_state");
    ctx.retro_get_region           = get_core_symbol(core_handle, "retro_get_region");
    ctx.retro_set_controller_port_device = get_core_symbol(core_handle,
        "retro_set_controller_port_device");
    ctx.retro_set_progress_callback = get_core_symbol(core_handle,
        "retro_set_progress_callback");
    ctx.retro_get_log_callback     = get_core_symbol(core_handle, "retro_get_log_callback");
    ctx.retro_set_unzip            = get_core_symbol(core_handle, "retro_set_unzip");
    ctx.retro_set_pixel_format     = get_core_symbol(core_handle, "retro_set_pixel_format");
    DBGP(CORE_DLSYM);

    if (!ctx.retro_get_memory_data || !ctx.retro_get_memory_size) {
        ERR("Core_Load: core missing retro_get_memory_data/size — SRAM persistence unavailable");
    } else {
        LOG("Core_Load: SRAM support available");
    }

    if (!ctx.retro_set_environment) {
        ERR("Core_Load: retro_set_environment not found");
        dlclose(core_handle);
        core_handle = NULL;
        return -2;
    }

    if (ctx.retro_is_support) {
        int support = ctx.retro_is_support(rom_path);
        if (support < 0) {
            ERR("Core_Load: core rejects ROM %s", rom_path);
            dlclose(core_handle);
            core_handle = NULL;
            return -3;
        }
        LOG("Core_Load: core supports ROM");
    }

    ctx.retro_set_environment(retro_get_env_cb);

    DBGP(CORE_INIT);
    if (ctx.retro_init)
        ctx.retro_init();

    if (ctx.retro_set_controller_port_device) {
        char dev_type[64];
        if (get_cfg_value("device0_type", dev_type, sizeof(dev_type), corecfg)) {
            unsigned dev = (unsigned)strtoul(dev_type, NULL, 10);
            ctx.retro_set_controller_port_device(0, dev);
        }
        if (get_cfg_value("device1_type", dev_type, sizeof(dev_type), corecfg)) {
            unsigned dev = (unsigned)strtoul(dev_type, NULL, 10);
            ctx.retro_set_controller_port_device(1, dev);
        }
    }

    if (ctx.retro_set_progress_callback)
        ctx.retro_set_progress_callback(NULL);

    retro_game_info_t game_info = { 0 };
    game_info.path = rom_path;
    game_info.data = NULL;
    game_info.size = 0;
    game_info.metadata = NULL;

    if (ctx.retro_load_game) {
        DBGP(CORE_LOADGAME);
        ctx.retro_load_game(&game_info);
        LOG("Core_Load: retro_load_game done");
    }

    if (ctx.retro_set_video_refresh)
        ctx.retro_set_video_refresh(disp_flip);
    if (ctx.retro_set_input_poll)
        ctx.retro_set_input_poll(joy_poll_wrapper);
    if (ctx.retro_set_input_state)
        ctx.retro_set_input_state(joy_input_state);
    if (ctx.retro_set_audio_sample_batch)
        ctx.retro_set_audio_sample_batch(audio_sample_batch_wrapper);
    else if (ctx.retro_set_audio_callback)
        LOG("Core_Load: only legacy audio_callback exposed — falling back");

    /* 区域检测（PAL/NTSC） — 记录到日志便于调试 */
    if (ctx.retro_get_region) {
        int region = ctx.retro_get_region();
        LOG("Core_Load: region=%d (0=NTSC, 1=PAL)", region);
    }

    sram_build_path(rom_path);
    sram_load();

    ret = core_run();

    sram_save_to_file();
    sram_unload();
    core_unload();

    return ret;
}

void core_unload(void)
{
    DBGP(CORE_UNLOAD);
    if (!core_handle) return;
    if (ctx.retro_unload_game)
        ctx.retro_unload_game();
    if (ctx.retro_deinit)
        ctx.retro_deinit();
    dlclose(core_handle);
    core_handle = NULL;
    memset(&ctx, 0, sizeof(ctx));
    LOG("core unloaded");
}

int core_run(void)
{
    DBGP(CORE_RUN);
    LOG("core_run: entering main loop");

    /* 切换到游戏模式 480×272 RGB565（原厂 InitScr） */
    disp_set_game_mode(1);
    LOG("core_run: game mode enabled (480x272 RGB565)");

    /* 暂停菜单状态（<gamemenuhotkey> 触发） */
    static int paused = 0;
    static uint32_t last_gamemenu_key = 0;

    while (1) {
        /* P0-B: 检查 Save State 热键 */
        sstate_check_hotkey();

        /* P0-C: 检查暂停菜单热键（<gamemenuhotkey>） */
        {
            uint32_t cur = joy_all_keys_state();
            uint32_t target = (g_cfg.gamemenuhotkey >= 0 && g_cfg.gamemenuhotkey < 32)
                              ? (1u << g_cfg.gamemenuhotkey) : 0;
            if (target && (cur & target) && !(last_gamemenu_key & target)) {
                paused = !paused;
                LOG("gamemenuhotkey: pause %s", paused ? "ON" : "OFF");
            }
            last_gamemenu_key = cur;
        }

        if (paused) {
            /* 暂停菜单：显示存档/读档选项 */
            static uint32_t last_pause_keys = 0;
            uint32_t cur = joy_all_keys_state();
            if (sstate_has_slot(g_sstate_slot)) {
                /* 有存档：A 键读档，B 键存档，START 退出暂停 */
                if ((cur & KEY_A) && !(last_pause_keys & KEY_A)) {
                    if (sstate_load(g_sstate_slot) == 0) {
                        LOG("pause menu: load state slot %d", g_sstate_slot);
                        paused = 0;
                    }
                } else if ((cur & KEY_B) && !(last_pause_keys & KEY_B)) {
                    if (sstate_save(g_sstate_slot) == 0) {
                        LOG("pause menu: save state slot %d", g_sstate_slot);
                    }
                }
            } else {
                /* 无存档：B 键存档，START 退出暂停 */
                if ((cur & KEY_B) && !(last_pause_keys & KEY_B)) {
                    if (sstate_save(g_sstate_slot) == 0) {
                        LOG("pause menu: save state slot %d", g_sstate_slot);
                    }
                }
            }
            /* START 退出暂停 */
            if ((cur & KEY_START) && !(last_pause_keys & KEY_START)) {
                paused = 0;
            }
            last_pause_keys = cur;
            /* 暂停时不运行游戏 */
            continue;
        }

        if (ctx.retro_run) {
            ctx.retro_run();
        }
    }
    return 0;
}

static void *retro_get_env_cb(void *cb, unsigned cmd, void *data)
{
    (void)cb;

    switch (cmd) {
        case 1:  /* SET_ROTATION */
        {
            unsigned *rot = (unsigned *)data;
            rotation = (uint8_t)*rot;
            disp_set_rotation(rotation | 0xff00);
            return (void *)1;
        }
        case 9:  /* GET_SYSTEM_DIRECTORY */
        {
            char **dir = (char **)data;
            snprintf(system_directory, sizeof(system_directory), "%score/", work_path);
            *dir = system_directory;
            return (void *)1;
        }
        case 0x1f:  /* GET_SAVE_DIRECTORY */
        {
            char **dir = (char **)data;
            snprintf(save_directory, sizeof(save_directory), "%ssaves/", work_path);
            *dir = save_directory;
            return (void *)1;
        }
        case 10:  /* GET_CANVAS_FORMAT — 工厂对齐 (use_rgb_8888) */
        {
            unsigned *format = (unsigned *)data;
            if (*format == 1) {
                use_rgb_8888 = true;
                disp_set_colormode(1);
            } else {
                use_rgb_8888 = false;
            }
            return (void *)1;
        }
        case 0xf:  /* GET_VARIABLE */
            return (void *)1;
        case 0x19:  /* SET_PIXEL_FORMAT — 记录核心请求的格式 */
        {
            unsigned *fmt = (unsigned *)data;
            retro_pixel_format = *fmt;
            LOG("retro_set_pixel_format: fmt=0x%02x (RGB565=0x01, XRGB8888=0x07)", *fmt);
            return (void *)1;
        }
        case 0x1b:  /* SET_LOG_INTERFACE */
            return (void *)1;
        case 0x25:
            return (void *)1;
        default:
            return (void *)0;
    }
}

static int get_cfg_value(const char *key, char *out, size_t out_size, const char *cfg)
{
    char tag[128];
    snprintf(tag, sizeof(tag), "<%s>", key);
    char *start = strstr(cfg, tag);
    if (!start) return 0;
    start += strlen(tag);
    char *end = strstr(start, "</");
    if (!end) return 0;
    size_t len = end - start;
    if (len >= out_size) len = out_size - 1;
    memcpy(out, start, len);
    out[len] = '\0';
    return 1;
}
