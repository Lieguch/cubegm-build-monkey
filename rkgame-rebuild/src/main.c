/* ============================================================
 * rkgame-rebuild — 入口
 * ============================================================
 *
 * 原版 main() 流程：
 *   puts("rkgame v1.42")
 *   get_executable_path(work_path)
 *   resource_path = work_path + "resource"
 *   GetConfig()        — 读 config.xml
 *   dispmeninfo()      — 输出分辨率信息
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
#include <pthread.h>
#include <fcntl.h>
#include <errno.h>
#include <stdarg.h>
#include <time.h>
#include <sys/select.h>

#include "rkgame.h"
#include "debug.h"

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

/* ---- 显示层占位实现（DRM/KMS 待 Phase 4 实现） ---- */

void disp_init(void)         { LOG("disp_init: placeholder"); }
void disp_shutdown(void)     { LOG("disp_shutdown"); }
void disp_set_rotation(uint32_t rot) { LOG("disp_set_rotation: %u", rot); }
void disp_set_colormode(int mode)    { LOG("disp_set_colormode: %d", mode); }
void disp_flip(const void *buf, unsigned w, unsigned h, size_t p)
{
    (void)buf; (void)w; (void)h; (void)p;
}

/* ---- 音频层占位实现（ALSA 待 Phase 4 实现） ---- */

void audio_init(void)         { LOG("audio_init: placeholder"); }
void audio_shutdown(void)     { LOG("audio_shutdown"); }
void audio_play(const void *buf, size_t frames)
{
    (void)buf; (void)frames;
}

/* ---- 配置保存占位 ---- */

void config_save(void) { LOG("config_save: not implemented"); }

/* ---- 工具函数 ---- */

/*
 * get_executable_path：读取 /proc/self/exe 链接获取自身路径。
 * 原版用 getcwd 替代，但那样拿到的是当前工作目录而非程序路径。
 */
static void get_executable_path(char *out, size_t out_size)
{
    ssize_t len = readlink("/proc/self/exe", out, out_size - 1);
    if (len < 0) {
        /* 退路：用 argv[0] */
        snprintf(out, out_size, "/sdcard/cubegm/rkgame");
        return;
    }
    out[len] = '\0';
    /* 截取到父目录 */
    char *last_slash = strrchr(out, '/');
    if (last_slash) {
        *(last_slash + 1) = '\0';
    }
}

/* ---- 配置加载 ---- */

void config_load(void)
{
    /* 原厂固件用 setting.xml（非 config.xml），格式为 <autorun file="..." driver="..."/> */
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
        return;
    }

    char *buf = malloc(64 * 1024);
    if (!buf) { fclose(fp); return; }
    size_t n = fread(buf, 1, 64 * 1024 - 1, fp);
    buf[n] = '\0';
    fclose(fp);

    /* 1) 解析 <autorun file="..." driver="..."/>（属性语法，原厂 setting.xml 格式） */
    char *tag = strstr(buf, "<autorun");
    if (tag) {
        /* file="..." */
        char *f = strstr(tag, "file=");
        if (f) {
            f += 5;
            if (*f == '"') {
                f++;
                char *end = strchr(f, '"');
                if (end) {
                    size_t len = (size_t)(end - f);
                    if (len < sizeof(g_cfg.autorun_path)) {
                        memcpy(g_cfg.autorun_path, f, len);
                        g_cfg.autorun_path[len] = '\0';
                    }
                }
            }
        }
        /* driver="..." */
        char *d = strstr(tag, "driver=");
        if (d) {
            d += 7;
            if (*d == '"') {
                d++;
                char *end = strchr(d, '"');
                if (end) {
                    size_t len = (size_t)(end - d);
                    if (len < sizeof(g_cfg.autorun_driver)) {
                        memcpy(g_cfg.autorun_driver, d, len);
                        g_cfg.autorun_driver[len] = '\0';
                    }
                }
            }
        }
    }

    /* 2) 回退：<core>name</core>（子元素文本，非原厂格式但保留兼容） */
    tag = strstr(buf, "<core>");
    if (tag && !g_cfg.core_name[0]) {
        tag += 7;
        char *end = strstr(tag, "</core>");
        if (end) {
            size_t len = (size_t)(end - tag);
            if (len < sizeof(g_cfg.core_name)) {
                memcpy(g_cfg.core_name, tag, len);
                g_cfg.core_name[len] = '\0';
            }
        }
    }

    /* 3) device0_type / device1_type */
    tag = strstr(buf, "<device0_type>");
    if (tag) {
        tag += 15;
        char *end = strstr(tag, "</device0_type>");
        if (end) {
            size_t len = (size_t)(end - tag);
            if (len < sizeof(g_cfg.device0_type)) {
                memcpy(g_cfg.device0_type, tag, len);
                g_cfg.device0_type[len] = '\0';
            }
        }
    }
    tag = strstr(buf, "<device1_type>");
    if (tag) {
        tag += 15;
        char *end = strstr(tag, "</device1_type>");
        if (end) {
            size_t len = (size_t)(end - tag);
            if (len < sizeof(g_cfg.device1_type)) {
                memcpy(g_cfg.device1_type, tag, len);
                g_cfg.device1_type[len] = '\0';
            }
        }
    }

    free(buf);
    LOG("config: autorun=%s core=%s driver=%s dev0=%s dev1=%s",
        g_cfg.autorun_path, g_cfg.core_name,
        g_cfg.autorun_driver,
        g_cfg.device0_type, g_cfg.device1_type);
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
    core_load(rom, g_cfg.core_name);
}

/* ---- 菜单占位 ---- */

static void main_menu(void)
{
    LOG("main_menu: placeholder menu active; keeping process alive until UI/ROM autorun");
    ERR("main_menu: 暂不支持完整 UI，需通过 autorun 启动 ROM");

    /*
     * 原厂无 autorun 时会进入菜单并保持前台进程。当前 rebuild 还没有 DRM/KMS
     * 菜单 UI；若这里返回，launcher 会认为 rkgame 已退出并重启进程，形成
     * 7 秒一次的重启循环。因此先进入阻塞事件循环：轮询手柄，但绝不退出。
     * 后续 Phase 4 应把这里替换成真实菜单 UI。
     */
    time_t last_heartbeat = 0;

    while (1) {
        struct timeval tv;
        fd_set rfds;
        int i;
        int maxfd = -1;

        FD_ZERO(&rfds);
        for (i = 0; i < joy_dev_count; i++) {
            if (joy_devs[i].event_fd >= 0) {
                FD_SET(joy_devs[i].event_fd, &rfds);
                if (joy_devs[i].event_fd > maxfd)
                    maxfd = joy_devs[i].event_fd;
            }
        }

        if (maxfd >= 0) {
            tv.tv_sec = 60;
            tv.tv_usec = 0;
            if (select(maxfd + 1, &rfds, NULL, NULL, &tv) > 0) {
                (void)joy_poll();
                continue;
            }
        } else {
            /* 无手柄时也不退出；避免 launcher 重启循环。 */
            struct timespec ts = { 60, 0 };
            nanosleep(&ts, NULL);
        }

        time_t now = time(NULL);
        if (now != last_heartbeat) {
            LOG("main_menu: still active (no autorun configured), waiting for Phase 4 UI");
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

    get_executable_path(work_path, sizeof(work_path));
    DBGP(GET_PATH);
    LOG("work_path = %s", work_path);

    snprintf(resource_path, sizeof(resource_path), "%sresource/", work_path);

    DBGP(CONFIG_LOAD);
    config_load();

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
    disp_init();
    DBGP(AUDIO_INIT);
    audio_init();
    DBGP(SRAM_INIT);
    sram_init();
    DBGP(JOY_INIT);
    joy_init();

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
    sram_unload();
    joy_close_all();
    core_unload();
    audio_shutdown();
    disp_shutdown();

    DBGP(END);
    return 0;
}
