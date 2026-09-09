/* ============================================================
 * rkgame-rebuild — 入口
 * ============================================================
 *
 * 原版 main() 流程：
 *   puts("rkgame v1.42")
 *   get_executable_path(work_path)
 *   resource_path = work_path + "resource"
 *   GetConfig()        — 读 config.xml
 *   dispmeninfo()      — 输出分辨率信息 + /proc/meminfo 内存诊断
 *   InitDisplay()
 *   InitSound()
 *   InitJoystick()     — GPIO + RF
 *   sfc_init()
 *   spi_driver_init()  — 触摸屏驱动
 *   if autorunfile[0] == '\0':
 *       main_Menu()
 *   elif autorunfile == "/USBJoystickTest":
 *       TestUSBJoy()
 *   elif autorunfile == "/JoystickTest":
 *       JoystickTest()
 *   else:
 *       autorun(autorunfile, autorundriver)
 *
 * 重构后保持同样入口结构。
 * ============================================================ */

#define _GNU_SOURCE
/* rkgame v1.5.0 — SRAM + evdev rebuild, 2026-09-01 */
/* Build trigger */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <dirent.h>
#include <pthread.h>
#include <fcntl.h>
#include <errno.h>
#include <stdarg.h>
#include <dlfcn.h>

/* driver.so dlopen handle（供 audio.c dlsym 使用） */
extern void *driver_handle;
#include <time.h>
#include <sys/time.h>
#include <sys/select.h>

#include "rkgame.h"
#include "debug.h"
#include "heartbeat.h"
#include "font.h"
#include "ui.h"
#include "ui_dispatcher.h"
#include "audio.h"
#include "stubs.h"
#include "cpd.h"

/* ---- 全局变量定义 ---- */

char     work_path[512] = "/sdcard/cubegm/";
char     resource_path[512];
char     autorunfile[1024];
char     autorundriver[128];
char     system_directory[512];
char     save_directory[512];

uint16_t n_input_width       = 0x140;  /* 320 */
uint16_t n_input_height      = 0xe0;   /* 224 */
uint16_t n_input_visible_width  = 0x100;
uint16_t n_input_visible_height = 0xe0;
uint16_t screen_w = 0x100;
uint16_t screen_x = 0;
uint8_t  rotation = 0;
bool     use_rgb_8888 = false;

void *core_handle = NULL;
retro_ctx_t ctx = { 0 };
sram_state_t sram_state = { 0 };
joy_device_t joy_devs[MAX_DEVICES] = { 0 };
int joy_dev_count = 0;
rkgame_config_t g_cfg = { 0 };

/* 游戏列表导航状态（Task #39 — ui.c 通过 extern 读取） */
int menu_gl_selected = 0;
int menu_gl_scroll   = 0;

/* ---- 日志（rklog 实现） ---- */

void rklog(int level, const char *fmt, ...)
{
    va_list ap;
    const char *prefix;
    char buf[512];
    int n;

    switch (level) {
        case RKLOG_ERROR: prefix = "[RK-E]"; break;
        case RKLOG_WARN:  prefix = "[RK-W]"; break;
        case RKLOG_INFO:  prefix = "[RK-I]"; break;
        default:          prefix = "[RK-D]"; break;
    }

    n = snprintf(buf, sizeof(buf), "%s ", prefix);
    va_start(ap, fmt);
    n += vsnprintf(buf + n, sizeof(buf) - n, fmt, ap);
    va_end(ap);
    if (n < 0) n = 0;
    if (n >= (int)sizeof(buf)) n = (int)sizeof(buf) - 1;
    buf[n++] = '\n';

    /*
     * 只通过 dbg_log 写日志。dbg_init() 已把 fd 2 重定向到同一个 g_log_fd；
     * 如果这里再 write(2,...) 会形成双 fd 重复/交错。
     */
    dbg_log(DBG_LEVEL_DEBUG, "%s", buf);
}

/* ---- 显示层（实现见 disp.c） ---- */

/* ---- 音频层：实现在 audio.c（P2.4） ---- */

/* ---- 配置保存（实现在 config.c） ---- */

/* ---- 工具函数 ---- */

/*
 * get_executable_path：读取 /proc/self/exe 链接获取自身路径。
 * 原版用 getcwd 替代，但那样拿到的是当前工作目录而非程序路径。
 *
 * 优先级：
 *   1. RKGAME_WORK_PATH 环境变量（CI 测试 / 运维覆盖用）
 *   2. /proc/self/exe（真实设备路径）
 *   3. qemu 检测：qemu-arm-static 下 readlink 返回 qemu 路径，用默认 /sdcard/cubegm/
 *   4. readlink 失败：回退 /sdcard/cubegm/
 */
static void get_executable_path(char *out, size_t out_size)
{
    /* 1. 环境变量覆盖（CI 测试用） */
    const char *env = getenv("RKGAME_WORK_PATH");
    if (env && *env) {
        strncpy(out, env, out_size - 1);
        out[out_size - 1] = '\0';
        size_t l = strlen(out);
        if (l > 0 && out[l-1] != '/') {
            if (l + 1 < out_size) {
                out[l] = '/';
                out[l+1] = '\0';
            }
        }
        return;
    }

    /* 2. 读 /proc/self/exe */
    ssize_t len = readlink("/proc/self/exe", out, out_size - 1);
    if (len < 0) {
        snprintf(out, out_size, "/sdcard/cubegm/");
        return;
    }
    out[len] = '\0';

    /* 3. qemu 检测：qemu-arm-static 下返回 /usr/bin/qemu-arm-static */
    if (strstr(out, "qemu")) {
        snprintf(out, out_size, "/sdcard/cubegm/");
        return;
    }

    /* 4. 截取到父目录 */
    char *last_slash = strrchr(out, '/');
    if (last_slash) {
        *(last_slash + 1) = '\0';
    }
}

/* ---- 配置加载 ---- */

/* ---- setting.xml 完整解析 ----
 *
 * 工厂实证（Ghidra 反编译 + 真机 SD 卡 setting.xml）：
 *   GetConfig() @ 0x9f04 解析 8 项：
 *     displayfps, displaythread, softrotation, logfile,
 *     savestatehotkey (default -1), autorestore (default 0),
 *     gamemenuhotkey (default 9), autorun (file, driver attrs)
 *   mui_LoadSetting() @ 0x171f8 解析 6 项：
 *     config (language, volume attrs), defaultlanguage,
 *     sound > bgm (file attr), sound > effect0 (file),
 *     sound > effect1 (file), filebrowser
 *
 * 总计 14 项（含 autorun/config 的 2+2 子属性）。
 */

/* 辅助：从 <tag>...</tag> 提取元素文本为整数 */
static int parse_elem_int(const char *buf, const char *tag, int default_val)
{
    char open_tag[64], close_tag[64];
    snprintf(open_tag, sizeof(open_tag), "<%s>", tag);
    snprintf(close_tag, sizeof(close_tag), "</%s>", tag);
    const char *start = strstr(buf, open_tag);
    if (!start) return default_val;
    start += strlen(open_tag);
    const char *end = strstr(start, close_tag);
    if (!end) return default_val;
    char tmp[64];
    size_t len = (size_t)(end - start);
    if (len >= sizeof(tmp)) len = sizeof(tmp) - 1;
    memcpy(tmp, start, len);
    tmp[len] = '\0';
    return (int)strtol(tmp, NULL, 10);
}

/* 辅助：从 <tag>...</tag> 提取元素文本为字符串 */
static void parse_elem_str(const char *buf, const char *tag,
                           char *out, size_t out_size, const char *default_val)
{
    char open_tag[64], close_tag[64];
    snprintf(open_tag, sizeof(open_tag), "<%s>", tag);
    snprintf(close_tag, sizeof(close_tag), "</%s>", tag);
    const char *start = strstr(buf, open_tag);
    if (!start) {
        strncpy(out, default_val, out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    start += strlen(open_tag);
    const char *end = strstr(start, close_tag);
    if (!end) {
        strncpy(out, default_val, out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    size_t len = (size_t)(end - start);
    if (len >= out_size) len = out_size - 1;
    memcpy(out, start, len);
    out[len] = '\0';
}

/* 辅助：从 <tag ... attr="value" .../> 或 <tag ... attr="value" ...> 提取属性值 */
static void parse_attr_str(const char *buf, const char *tag, const char *attr,
                           char *out, size_t out_size, const char *default_val)
{
    const char *tag_start = strstr(buf, tag);
    if (!tag_start) {
        strncpy(out, default_val, out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    char search[64];
    snprintf(search, sizeof(search), "%s=\"", attr);
    const char *f = strstr(tag_start, search);
    if (!f) {
        strncpy(out, default_val, out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    f += strlen(search);
    const char *end = strchr(f, '"');
    if (!end) {
        strncpy(out, default_val, out_size - 1);
        out[out_size - 1] = '\0';
        return;
    }
    size_t len = (size_t)(end - f);
    if (len >= out_size) len = out_size - 1;
    memcpy(out, f, len);
    out[len] = '\0';
}

/* 辅助：从属性提取整数 */
static int parse_attr_int(const char *buf, const char *tag, const char *attr,
                          int default_val)
{
    const char *tag_start = strstr(buf, tag);
    if (!tag_start) return default_val;
    char search[64], tmp[64];
    snprintf(search, sizeof(search), "%s=\"", attr);
    const char *f = strstr(tag_start, search);
    if (!f) return default_val;
    f += strlen(search);
    const char *end = strchr(f, '"');
    if (!end) return default_val;
    size_t len = (size_t)(end - f);
    if (len >= sizeof(tmp)) len = sizeof(tmp) - 1;
    memcpy(tmp, f, len);
    tmp[len] = '\0';
    return (int)strtol(tmp, NULL, 10);
}

void legacy_config_parse(void)
{
    /* 原厂用 setting.xml（非 config.xml），格式为 <autorun file="..." driver="..."/> */
    const char *cfg_files[] = { "setting.xml", "config.xml", NULL };
    FILE *fp = NULL;
    char path[600];

    for (int i = 0; cfg_files[i]; i++) {
        snprintf(path, sizeof(path), "%s%s", work_path, cfg_files[i]);
        fp = fopen(path, "r");
        if (fp) break;
    }

    if (!fp) {
        ERR("config_load: no config file in %s", work_path);
        memset(&g_cfg, 0, sizeof(g_cfg));
        /* 对齐原厂 GetConfig 默认值（反编译 01_main_emurun_joystick.c:180-196）：
         *   SaveDefaultStateKey = -1（禁用）
         *   GameMenuHotKey = 9（L1/MODE2）
         * 真机 setting.xml 实际值可能为 <savestatehotkey>3072</savestatehotkey>（位掩码）。 */
        g_cfg.savestatehotkey = -1;
        g_cfg.gamemenuhotkey = 9;
        g_cfg.volume = 8;
        return;
    }

    char *buf = malloc(64 * 1024);
    if (!buf) { fclose(fp); return; }
    size_t n = fread(buf, 1, 64 * 1024 - 1, fp);
    buf[n] = '\0';
    fclose(fp);

    /* ---- GetConfig() @ 0x9f04: 8 项 ---- */

    /* 1) displayfps */
    g_cfg.displayfps = parse_elem_int(buf, "displayfps", 0);

    /* 2) displaythread */
    g_cfg.displaythread = parse_elem_int(buf, "displaythread", 0);

    /* 3) softrotation */
    g_cfg.soft_rotation = parse_elem_int(buf, "softrotation", 0);

    /* 4) logfile */
    parse_elem_str(buf, "logfile", g_cfg.logfile,
                   sizeof(g_cfg.logfile), "");

    /* 5) savestatehotkey (原厂默认 -1 禁用，实际 setting.xml 值 3072) */
    g_cfg.savestatehotkey = parse_elem_int(buf, "savestatehotkey", -1);

    /* 6) autorestore (default 0) */
    g_cfg.autorestore = parse_elem_int(buf, "autorestore", 0);

    /* 7) gamemenuhotkey (原厂默认 9) */
    g_cfg.gamemenuhotkey = parse_elem_int(buf, "gamemenuhotkey", 9);

    /* 8) autorun (file, driver attrs) */
    parse_attr_str(buf, "<autorun", "file", g_cfg.autorun_path,
                   sizeof(g_cfg.autorun_path), "");
    parse_attr_str(buf, "<autorun", "driver", g_cfg.autorun_driver,
                   sizeof(g_cfg.autorun_driver), "");

    /* ---- mui_LoadSetting() @ 0x171f8: 6 项 ---- */

    /* 9) config (language, volume attrs) — 若 <config> 无 language 属性，
     *    用 <defaultlanguage> 作为 fallback */
    g_cfg.m_ui = parse_attr_int(buf, "<config", "language", -1);
    g_cfg.volume = parse_attr_int(buf, "<config", "volume", 8);

    /* 10) defaultlanguage (default 0) */
    g_cfg.defaultlanguage = parse_elem_int(buf, "defaultlanguage", 0);

    /* 应用 fallback：config language 缺失时用 defaultlanguage */
    if (g_cfg.m_ui < 0) {
        g_cfg.m_ui = g_cfg.defaultlanguage;
    }

    /* 11-13) sound > bgm, effect0, effect1 (file attrs) */
    /* 注意：原厂 setting.xml 用 <bgm file="..."/> 而非 <music file="..."/> */
    parse_attr_str(buf, "<bgm", "file", g_cfg.music_file,
                   sizeof(g_cfg.music_file), "");
    parse_attr_str(buf, "<effect0", "file", g_cfg.effect0_file,
                   sizeof(g_cfg.effect0_file), "");
    parse_attr_str(buf, "<effect1", "file", g_cfg.effect1_file,
                   sizeof(g_cfg.effect1_file), "");

    /* 14) filebrowser (default "/roms") */
    parse_elem_str(buf, "filebrowser", g_cfg.filebrowser,
                   sizeof(g_cfg.filebrowser), "/roms");

    /* 兼容：device0_type / device1_type（非原厂但保留） */
    parse_elem_str(buf, "device0_type", g_cfg.device0_type,
                   sizeof(g_cfg.device0_type), "");
    parse_elem_str(buf, "device1_type", g_cfg.device1_type,
                   sizeof(g_cfg.device1_type), "");

    /* 兼容：<core>name</core>（旧格式） */
    parse_elem_str(buf, "core", g_cfg.core_name,
                   sizeof(g_cfg.core_name), "");

    free(buf);

    LOG("config: autorun=%s core=%s driver=%s",
        g_cfg.autorun_path, g_cfg.core_name,
        g_cfg.autorun_driver);
    LOG("config: displayfps=%d softrotation=%d logfile=%s",
        g_cfg.displayfps, g_cfg.soft_rotation, g_cfg.logfile);
    LOG("config: savestatehotkey=%d autorestore=%d gamemenuhotkey=%d",
        g_cfg.savestatehotkey, g_cfg.autorestore, g_cfg.gamemenuhotkey);
    LOG("config: language=%d volume=%d defaultlang=%d",
        g_cfg.m_ui, g_cfg.volume, g_cfg.defaultlanguage);
    LOG("config: music=%s effect0=%s effect1=%s",
        g_cfg.music_file, g_cfg.effect0_file, g_cfg.effect1_file);
    LOG("config: filebrowser=%s dev0=%s dev1=%s",
        g_cfg.filebrowser, g_cfg.device0_type, g_cfg.device1_type);
}

/* ---- autorun ---- */

void autorun(const char *rom, const char *driver)
{
    LOG("autorun: rom=%s driver=%s", rom, driver ?: "(none)");
    if (driver && *driver) {
        /* 有 driver 参数 — 原版行为：仅 InitScr 后返回 */
        LOG("autorun: driver specified, skipping ROM load");
        return;
    }

    /* 工厂流程（run_game @ 0x2b7510）：
     * 1. GetFilenameExt → 大写
     * 2. GetCoreIndex(ext) → 设置 Filetype, 返回 index
     * 3. 根据 Filetype 分支派发
     *
     * 本 rebuild 简化为：查表得到 core name，传给 core_load。
     * ZIP 容器 (Filetype >= 0x10000) 和特殊 loader (Gpsp_Load,
     * DOSBox game.cfg) 暂用通用 Core_Load 路径。
     */
    char ext[16];
    GetFilenameExt(rom, ext, sizeof(ext));
    int idx = GetCoreIndex(ext);

    if (idx < 0) {
        ERR("autorun: unknown extension '%s' for %s", ext, rom);
        return;
    }

    const char *core_name = core_lookup_by_ext(ext);
    if (!core_name || !*core_name) {
        /* 空 core_name: BKP/ZIP (0x10000) — 需要 OpenZipU 处理，
         * 当前 rebuild 还没有 ZIP 解包路径，尝试直接传给 core_load */
        ERR("autorun: core name empty for ext '%s' (filetype=0x%x) — "
            "ZIP container not yet supported", ext, Filetype);
        return;
    }

    LOG("autorun: ext=%s filetype=0x%x core=%s", ext, Filetype, core_name);
    core_load(rom, core_name);
    /* 标记 menu.log 状态为脏（下次 SaveMenuLog 时写入 UI 状态） */
    menu_log_mark_dirty();
}

/* ---- 菜单占位 ---- */

static void main_menu(void)
{
    LOG("main_menu: entering menu (DRM ready=%d)", disp_is_ready() ? 1 : 0);
    /* 说明：主菜单本身可导航（搜索/设置/文件浏览器/游戏列表），
     * 只有启动 ROM 时才走 core_load → autorun 路径。这里不再输出
     * "full UI not supported yet" 误导性日志（2026-09-08 修复）。 */
    LOG("main_menu: entering interactive menu loop");

    /* 如果 DRM/KMS 可用，渲染启动画面菜单 */
    if (disp_is_ready()) {
        if (ui_is_ready())
            ui_draw_menu();
        else
            disp_draw_menu();
    }

    /*
     * 原厂无 autorun 时会进入菜单并保持前台进程。当前 rebuild 还没有 DRM/KMS
     * 菜单 UI；若这里返回，launcher 会认为 rkgame 已退出并重启进程，形成
     * 7 秒一次的重启循环。因此先进入阻塞事件循环：轮询手柄，但绝不退出。
     * 后续 Phase 4 应把这里替换成真实菜单 UI。
     *
     * 真机观察（2026-09-05）：icube launcher 每 ~7 秒 kill+respawn 一次
     * rkgame，但本循环 while(1) 不会自己退出。icube strings 显示它用
     * shmget/shmat/shmdt/shmctl 做父子通信。可能 icube 用 shm 心跳
     * 看门狗检测子进程是否活着。heartbeat 模块已加信号处理 + shm 探测
     * + 心跳文件写入，用于真机诊断。
     */
    time_t last_heartbeat = 0;
    time_t last_redraw    = 0;
    int    redraw_count   = 0;

    /* ---- 游戏列表导航状态（P2.2 + Task #39） ---- */
    /* int gl_prev_keys[26] 已删除（改用 gl_prev_state bitmask，见下方定义） */
    bool  gl_showing     = false;          /* 是否正在显示游戏列表 */
    bool  gl_searching   = false;          /* 是否正在显示搜索页 */
    bool  gl_setting     = false;          /* 是否正在显示设置页 */
    bool  gl_typing      = false;          /* 是否正在显示游戏分类页（type.raw） */
    bool  gl_browser     = false;          /* 是否正在显示文件浏览器（<filebrowser>） */
    const int GL_PAGE_SIZE = 8;            /* 每页显示的游戏数 */

    /* 文件浏览器状态（<filebrowser> 配置项） */
    char  fb_path[512] = {0};              /* 当前浏览路径 */
    char  fb_files[64][128] = {0};         /* 文件列表（最多 64 项） */
    int   fb_count = 0;                    /* 文件数 */
    int   fb_selected = 0;                 /* 当前选中索引 */
    int   fb_scroll = 0;                   /* 滚动偏移 */

    /* 标准按键位掩码（2026-09-08 修复：改用位掩码，非数字索引）
     * 与 evdev.c 中 KEY_* 定义一致，与 libretro JOYPAD id 对应。
     * 之前用数字 0-25 作为 key_id 导致 joy_get_key 位掩码比较全失败。 */
    #define KEY_UP       (1u << 0)   /* 上    */
    #define KEY_DOWN     (1u << 1)   /* 下    */
    #define KEY_LEFT     (1u << 2)   /* 左    */
    #define KEY_RIGHT    (1u << 3)   /* 右    */
    #define KEY_OK       (1u << 4)   /* A 键 = OK */
    #define KEY_CANCEL   (1u << 5)   /* B 键 = 取消 */
    #define KEY_FAVORITE (1u << 6)   /* X 键 = 收藏（临时用 SELECT 位） */
    #define KEY_START    (1u << 7)   /* START = 菜单切换 */
    #define KEY_SEARCH   (1u << 6)   /* SELECT = 搜索 */
    #define KEY_TYPE     (1u << 8)   /* L1 = 游戏分类 */
    #define KEY_BROWSER  (1u << 9)   /* R1 = 文件浏览器 */

    /* 上帧按键状态 bitmask（用于边缘检测） */
    uint32_t gl_prev_state = 0;

    while (1) {
        struct timeval tv;
        fd_set rfds;
        int i;
        int maxfd = -1;

        /* 周期性更新心跳文件 + 检查是否收到信号 */
        hb_tick();
        hb_shm_heartbeat();  /* 更新 icube shm 计数器，防止被 kill */
        int sig = hb_get_last_signal();
        if (sig != 0) {
            LOG("main_menu: caught signal %d (still alive, "
                "SA_RESTART will resume the wait below)", sig);
        }

        time_t now = time(NULL);

        /* ---- 读取手柄当前按键状态（一次性获取，非阻塞查询） ----
         * joy_key_state_get 从 state bitmap 读取，不消耗 evdev 事件。
         * 事件消费由后面的 joy_poll() 在 select 返回后执行。 */
        uint32_t state   = joy_key_state_get(0);
        uint32_t pressed = state & ~gl_prev_state;   /* 本帧新按下 */
        /* uint32_t released = gl_prev_state & ~state; 本帧新释放（暂未使用） */

        /* ---- 基础菜单导航（无游戏也生效） ---- */
        /* START: 进入游戏列表（需有游戏）或切换视图 */
        if (pressed & KEY_START) {
            if (gl_showing) {
                gl_showing = false;
                LOG("main_menu: returning to main menu");
            } else if (!gl_searching && !gl_setting && !gl_typing && !gl_browser) {
                if (game_list_is_loaded() && game_list_count() > 0) {
                    gl_showing = true;
                    menu_gl_selected = 0;
                    menu_gl_scroll = 0;
                    LOG("main_menu: game list view activated (%d games)",
                        game_list_count());
                }
            }
        }

        /* SELECT: 搜索页 */
        if (pressed & KEY_SEARCH) {
            gl_searching = !gl_searching;
            if (gl_searching) { gl_showing = false; gl_setting = false; gl_typing = false; gl_browser = false; }
            LOG("main_menu: search page %s", gl_searching ? "entered" : "exited");
        }

        /* L1: 设置页 */
        if (pressed & KEY_TYPE) {
            gl_setting = !gl_setting;
            if (gl_setting) { gl_showing = false; gl_searching = false; gl_typing = false; gl_browser = false; }
            LOG("main_menu: setting page %s", gl_setting ? "entered" : "exited");
        }

        /* R1: 文件浏览器 */
        if (pressed & KEY_BROWSER) {
            gl_browser = !gl_browser;
            if (gl_browser) {
                gl_showing = false; gl_searching = false; gl_setting = false; gl_typing = false;
                snprintf(fb_path, sizeof(fb_path), "%s%s", work_path, g_cfg.filebrowser);
                fb_count = 0; fb_selected = 0; fb_scroll = 0;
                LOG("main_menu: file browser opened at %s", fb_path);
            }
        }

        /* B/CANCEL: 退出当前子视图返回主菜单 */
        if ((pressed & KEY_CANCEL) &&
            (gl_showing || gl_searching || gl_setting || gl_typing)) {
            gl_showing = false; gl_searching = false;
            gl_setting = false; gl_typing = false;
            LOG("main_menu: back to main menu");
        }

        /* ---- 游戏列表导航（仅有游戏时生效） ---- */
        if (game_list_is_loaded() && game_list_count() > 0) {
            int count = game_list_count();

            /* 边界检查 */
            if (menu_gl_selected < 0) menu_gl_selected = 0;
            if (menu_gl_selected >= count) menu_gl_selected = count - 1;

            /* 文件浏览器按键处理 */
            if (gl_browser) {
                if (pressed & KEY_CANCEL) {
                    char *slash = strrchr(fb_path, '/');
                    if (slash && slash != fb_path) {
                        *slash = '\0';
                        fb_count = 0; fb_selected = 0; fb_scroll = 0;
                    } else if (slash == fb_path) {
                        gl_browser = false;
                    }
                    LOG("file browser: path=%s", fb_path);
                }
                if ((pressed & KEY_OK) && fb_count > 0) {
                    char full[600];
                    snprintf(full, sizeof(full), "%s/%s", fb_path, fb_files[fb_selected]);
                    struct stat st;
                    if (stat(full, &st) == 0 && S_ISDIR(st.st_mode)) {
                        snprintf(fb_path, sizeof(fb_path), "%s", full);
                        fb_count = 0; fb_selected = 0; fb_scroll = 0;
                        LOG("file browser: entered %s", fb_path);
                    }
                }
                if (pressed & KEY_START) {
                    gl_browser = false;
                    LOG("file browser: closed");
                }
                if (fb_count > 0) {
                    if (pressed & KEY_UP) {
                        fb_selected--;
                        if (fb_selected < 0) fb_selected = fb_count - 1;
                        if (fb_selected < fb_scroll) fb_scroll = fb_selected;
                    }
                    if (pressed & KEY_DOWN) {
                        fb_selected++;
                        if (fb_selected >= fb_count) fb_selected = 0;
                        if (fb_selected >= fb_scroll + GL_PAGE_SIZE)
                            fb_scroll = fb_selected - GL_PAGE_SIZE + 1;
                    }
                }
            }

            /* 上/下选择 + OK 启动（仅游戏列表视图） */
            if (gl_showing) {
                if (pressed & KEY_UP) {
                    menu_gl_selected--;
                    if (menu_gl_selected < 0) menu_gl_selected = count - 1;
                    if (menu_gl_selected < menu_gl_scroll) menu_gl_scroll = menu_gl_selected;
                    LOG("main_menu: selected %d/%d", menu_gl_selected + 1, count);
                }
                if (pressed & KEY_DOWN) {
                    menu_gl_selected++;
                    if (menu_gl_selected >= count) menu_gl_selected = 0;
                    if (menu_gl_selected >= menu_gl_scroll + GL_PAGE_SIZE)
                        menu_gl_scroll = menu_gl_selected - GL_PAGE_SIZE + 1;
                    LOG("main_menu: selected %d/%d", menu_gl_selected + 1, count);
                }

                /* 收藏切换（按 X） */
                if (pressed & KEY_FAVORITE) {
                    const game_entry_t *ge = game_list_get(menu_gl_selected);
                    if (ge) {
                        if (game_list_is_favorite(ge->path)) {
                            game_list_remove_favorite(ge->path);
                            game_list_save_favorites();
                            LOG("main_menu: removed favorite: %s", ge->path);
                        } else {
                            game_list_add_favorite(ge->path);
                            game_list_save_favorites();
                            LOG("main_menu: added favorite: %s", ge->path);
                        }
                    }
                }

                /* 启动游戏（按 A/OK） */
                if (pressed & KEY_OK) {
                    const game_entry_t *ge = game_list_get(menu_gl_selected);
                    if (ge) {
                        LOG("main_menu: launching game %d/%d: %s (%s)",
                            menu_gl_selected + 1, count, ge->path, ge->core);
                        game_list_update_recent(ge->path);
                        game_list_save_recent();
                        game_list_save_favorites();
                        char rom_path[1024];
                        snprintf(rom_path, sizeof(rom_path), "%s%s", work_path, ge->path);
                        const char *core_name = ge->core[0] ? ge->core
                                                 : game_list_find_core(ge->path);
                        if (!core_name) core_name = game_list_core_by_ext(
                               strrchr(ge->path, '.') ? strrchr(ge->path, '.') + 1 : "");
                        LOG("main_menu: launching %s with core %s",
                            rom_path, core_name ? core_name : "(auto)");
                        core_load(rom_path, core_name);
                        menu_log_mark_dirty();
                        return;
                    }
                }
            }
        }

        /* ---- 更新按键状态（边缘检测） ---- */
        gl_prev_state = state;

        /* ---- 调度 UI 模块 tick ---- */
        ui_page_state_t cur_page = m_ui_current_page(
            gl_showing, gl_searching, gl_setting, gl_typing, gl_browser);
        int key_ok_pressed = (pressed & KEY_OK) ? 1 : 0;
        m_ui_dispatch(key_ok_pressed, cur_page);

        /* ---- 重绘当前页面（每次按键或每 5 秒自动重绘） ---- */
        if (disp_is_ready() && ui_is_ready()) {
            if (gl_showing) {
                ui_draw_page(UI_PAGE_GAME);
            } else if (gl_searching) {
                ui_draw_page(UI_PAGE_SEARCH);
            } else if (gl_setting) {
                ui_draw_page(UI_PAGE_SETTING);
            } else if (gl_typing) {
                ui_draw_page(UI_PAGE_TYPE);
            } else if (gl_browser) {
                ui_draw_page(UI_PAGE_GAME);
                if (fb_count == 0) {
                    DIR *d = opendir(fb_path);
                    if (d) {
                        struct dirent *ent;
                        while ((ent = readdir(d)) != NULL && fb_count < 64) {
                            if (ent->d_name[0] == '.') continue;
                            strncpy(fb_files[fb_count++], ent->d_name, 127);
                        }
                        closedir(d);
                        LOG("file browser: scanned %d files at %s", fb_count, fb_path);
                    }
                }
                if (fb_count > 0 && font_is_ready()) {
                    int y = 20;
                    font_draw_text(fb_path, 10, y, 0xffffff);
                    y += 24;
                    for (int k = fb_scroll; k < fb_scroll + GL_PAGE_SIZE && k < fb_count; k++) {
                        const char *prefix = (k == fb_selected) ? " > " : "   ";
                        char line[140];
                        snprintf(line, sizeof(line), "%s%s", prefix, fb_files[k]);
                        font_draw_text(line, 10, y + (k - fb_scroll) * 22,
                                      (k == fb_selected) ? 0x00ff00 : 0xffffff);
                    }
                }
            } else {
                ui_draw_page(UI_PAGE_MENU);
            }
        }

        FD_ZERO(&rfds);
        for (i = 0; i < joy_dev_count; i++) {
            if (joy_devs[i].event_fd >= 0) {
                FD_SET(joy_devs[i].event_fd, &rfds);
                if (joy_devs[i].event_fd > maxfd)
                    maxfd = joy_devs[i].event_fd;
            }
        }

        /* P0-A: 添加 inotify fd 到 select 监听 */
        int inotify_fd = joy_inotify_fd();
        if (inotify_fd >= 0) {
            FD_SET(inotify_fd, &rfds);
            if (inotify_fd > maxfd)
                maxfd = inotify_fd;
        }

        if (maxfd >= 0) {
            /* 缩短超时到 1 秒，确保每 1 秒更新一次 shm[1] 计数器
             * icube 每 7-8 秒检查一次，1 秒间隔足够让 shm[1] 保持"新鲜" */
            tv.tv_sec = 1;
            tv.tv_usec = 0;
            if (select(maxfd + 1, &rfds, NULL, NULL, &tv) > 0) {
                /* P0-A: 检查手柄即插即用 */
                if (inotify_fd >= 0 && FD_ISSET(inotify_fd, &rfds)) {
                    joy_hotplug_check();
                }
                if (joy_poll()) {
                    /* P2.4: 按键触发音效 */
                    if (audio_is_ready() && g_cfg.effect1_file[0])
                        audio_play_sfx(g_cfg.effect1_file);
                }
                continue;
            }
        } else {
            /* 无手柄时也不退出；避免 launcher 重启循环。
             * 用 1 秒粒度，让心跳文件和重绘更及时。 */
            struct timespec ts = { 1, 0 };
            nanosleep(&ts, NULL);
        }

        if (now != last_heartbeat) {
            LOG("main_menu: still active (no autorun configured), "
                "waiting for Phase 4 UI, redraws=%d", redraw_count);
            last_heartbeat = now;
        }
    }
}

/* ---- 入口 ---- */

int main(int argc, char **argv)
{
    dbg_init();
    DBGP(MAIN_BEGIN);
    LOG("rkgame v1.5.0 (rebuild)");

    /* 尽早安装信号处理器，让任何阶段的信号都能被记录 */
    hb_install_signal_handlers();

    get_executable_path(work_path, sizeof(work_path));
    DBGP(GET_PATH);
    LOG("work_path = %s", work_path);

    snprintf(resource_path, sizeof(resource_path), "%sresource/", work_path);

    /* 加载 driver.so（原厂驱动库，供 sound_driver_init/video_driver_init dlsym 使用） */
    {
        char driver_path[512];
        snprintf(driver_path, sizeof(driver_path), "%sdriver.so", work_path);
        driver_handle = dlopen(driver_path, RTLD_NOW);
        if (driver_handle) {
            LOG("driver.so loaded: %s", driver_path);
        } else {
            LOG("driver.so not found at %s (audio/display will use fallback)", driver_path);
        }
    }

    /* 设置 LD_LIBRARY_PATH：加入 cubegm/lib/ 供 core .so 依赖查找
     * 对齐原厂 rkgame 行为：core .so 可能依赖 libgcc_s.so.1 等系统库，
     * 原厂 lib/ 目录包含这些库的本地副本。 */
    {
        char lib_dir[576];
        char ld_path[1200];
        snprintf(lib_dir, sizeof(lib_dir), "%slib/", work_path);
        const char *existing = getenv("LD_LIBRARY_PATH");
        if (existing && existing[0]) {
            snprintf(ld_path, sizeof(ld_path), "%s:%s", lib_dir, existing);
        } else {
            snprintf(ld_path, sizeof(ld_path), "%s", lib_dir);
        }
        setenv("LD_LIBRARY_PATH", ld_path, 1);
        LOG("LD_LIBRARY_PATH = %s", ld_path);
    }

    /* 启动心跳文件（work_path/heartbeat）：真机跑一次后可用 stat 判断
     * 进程是否活着、被 kill 的时刻。 */
    {
        char hb_path[576];
        snprintf(hb_path, sizeof(hb_path), "%sheartbeat", work_path);
        hb_init(hb_path);
    }

    /* 写 PID 文件（work_path/rkgame.pid）：CI 测试 / 运维脚本可以
     * 通过它精确 kill 特定实例，而不是误伤同名的 qemu-arm-static。
     * 真机上也可用于监控/诊断。 */
    {
        char pid_path[576];
        int pid_fd;
        char pid_buf[32];
        int n;
        snprintf(pid_path, sizeof(pid_path), "%srkgame.pid", work_path);
        pid_fd = open(pid_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (pid_fd >= 0) {
            n = snprintf(pid_buf, sizeof(pid_buf), "%d\n", (int)getpid());
            if (n > 0) {
                ssize_t w = write(pid_fd, pid_buf, (size_t)n);
                (void)w;
            }
            close(pid_fd);
        }
    }

    /* 探测 icube launcher 创建的 SysV shm 段（诊断 kill 机制） */
    hb_detect_icube_shm();

    /* 附加到 icube shm 段，启动独立心跳线程（原厂 XintiaoThread 机制） */
    hb_shm_attach();
    hb_start_heartbeat_thread();  /* 每 20ms 更新一次 shm[1]，不受主循环阻塞 */

    DBGP(CONFIG_LOAD);
    RKLOG_D("[main] calling GetConfig()");
    int cfg_rc = GetConfig();
    RKLOG_D("[main] GetConfig returned rc=%d", cfg_rc);
    legacy_config_parse();
    RKLOG_D("[main] legacy_config_parse done");

    /* 加载 cores/config.xml（SeletEmuCore @ 0x3c9aec）
     * 动态扩展 ext→core 映射，作为硬编码 core_table 的补充。
     * 对齐原厂 core_info_list 在 SeletEmuCore() 时从 config.xml 填充。 */
    load_cores_config_xml(work_path);

    /* 加载 menu.log（菜单恢复） */
    LoadMenuLog();

    /* dispmeninfo()：诊断 /proc/meminfo + 显示分辨率（对齐原厂 main() 第 4 阶段） */
    dispmeninfo();

    /* sfc_init() / spi_driver_init() / InitRFJoystick()：原厂 main() 调用，我方桩实现 */
    sfc_init();
    spi_driver_init();
    InitRFJoystick();

    /* 如果有命令行参数，优先用参数指定 autorun */
    if (argc >= 2) {
        strncpy(autorunfile, argv[1], sizeof(autorunfile) - 1);
    } else if (g_cfg.autorun_path[0]) {
        strncpy(autorunfile, g_cfg.autorun_path, sizeof(autorunfile) - 1);
    } else {
        autorunfile[0] = '\0';
    }
    if (argc >= 3) {
        strncpy(autorundriver, argv[2], sizeof(autorundriver) - 1);
    } else if (g_cfg.autorun_driver[0]) {
        strncpy(autorundriver, g_cfg.autorun_driver, sizeof(autorundriver) - 1);
    }

    LOG("autorunfile = %s", autorunfile);

    /* 初始化子系统 */
    DBGP(DISP_INIT);
    int disp_rc = disp_init();
    if (disp_rc == 0)
        LOG("disp_init: DRM/KMS ready");
    else
        LOG("disp_init: DRM/KMS unavailable (rc=%d), log-only mode", disp_rc);

    /* P1.2: 加载 TTF 字体（工厂对齐 stb_truetype） */
    int font_rc = font_init();
    if (font_rc == 0)
        LOG("font_init: TTF font ready");
    else
        LOG("font_init: font unavailable (rc=%d), using 5x7 bitmap fallback", font_rc);

    /* P1.3: 加载 UI 资源（ui_*.zip → menu.raw 背景） */
    int ui_rc = ui_init();
    if (ui_rc == 0)
        LOG("ui_init: UI resources ready");
    else
        LOG("ui_init: UI unavailable (rc=%d), using simple bitmap menu", ui_rc);

    /* P0-1: 初始化 UI 调度器（接线 13 个 mui_* 模块） */
    m_ui_init();

    /* .cpd 资源加载（resource.cpd + UI_Res.cpd）
     * 联网搜索确认（R36S Wiki 2026-09-07）：.cpd = ZIP 格式，可直接用 ui_zip_open() 解压
     * 对齐原厂 mui_menu_ui.c 从 resource.cpd 提取 game.raw/menu.raw/nodata.raw/ui.cfg
     * 及 UI_Res.cpd 提取平台背景。 */
    if (cpd_load_resource(work_path) == 0)
        LOG("cpd_load_resource: resource.cpd ready");
    else
        LOG("cpd_load_resource: resource.cpd unavailable, falling back to ui_*.zip");

    if (cpd_load_ui_res(work_path) == 0)
        LOG("cpd_load_ui_res: UI_Res.cpd ready");
    else
        LOG("cpd_load_ui_res: UI_Res.cpd unavailable");

    cpd_report();

    /* P2.3: 显示启动画面（InitScr RGB565 双缓冲） */
    if (disp_is_ready()) {
        disp_initscr_alloc();  /* 320×200 双缓冲分配 */
        if (disp_initscr_ready()) {
            disp_initscr_present();  /* 将启动画面渲染到帧缓冲 */
            LOG("InitScr: splash screen displayed");
            /* 短暂停留让用户看到启动画面 */
            for (int i = 0; i < 30; i++) {
                struct timespec ts = { .tv_sec = 0, .tv_nsec = 50000000L }; /* 50ms */
                nanosleep(&ts, NULL);
                if (joy_poll()) break;  /* 按键立即跳过 */
            }
        }
    }

    DBGP(AUDIO_INIT);
    audio_init();
    /* P2.4: 设置音量 + 启动 BGM */
    audio_set_volume(g_cfg.volume * 10);  /* g_cfg.volume 0-10 → 0-100% */
    if (g_cfg.music_file[0]) {
        audio_play_bgm(g_cfg.music_file);
    }
    DBGP(SRAM_INIT);
    sram_init();
    DBGP(JOY_INIT);
    joy_init();

    /* P2.2: 加载游戏列表 */
    game_list_init();
    if (game_list_load() == 0)
        LOG("game_list: loaded %d games", game_list_count());
    else
        LOG("game_list: no games found (will scan on demand)");

    /* 菜单 / autorun */
    if (autorunfile[0] == '\0') {
        main_menu();
    } else if (strcmp(autorunfile, "/USBJoystickTest") == 0) {
        /* 手柄测试模式 */
        LOG("entering USB joystick test mode");
    } else if (strcmp(autorunfile, "/JoystickTest") == 0) {
        LOG("entering joystick test mode");
    } else {
        DBGP(CORE_DLOPEN);
        autorun(autorunfile, autorundriver);
    }

    DBGP(SHUTDOWN);
    SaveMenuLog();
    sram_unload();
    joy_inotify_shutdown();
    game_list_free();
    joy_close_all();
    core_unload();
    audio_stop_bgm();
    audio_shutdown();
    ui_shutdown();
    cpd_free_all();
    disp_shutdown();
    font_shutdown();
    hb_stop_heartbeat_thread();  /* 停止心跳线程 */
    hb_shm_detach();
    hb_shutdown();

    DBGP(END);
    return 0;
}
