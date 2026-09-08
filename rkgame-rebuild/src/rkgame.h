/* ============================================================
 * rkgame-rebuild — rkgame v1.42 重构版
 * ============================================================
 *
 * 目标：完整替换 /sdcard/cubegm/rkgame，增加：
 *   1. SRAM 存档（retro_get_memory_data/size → .srm 落盘）
 *   2. evdev 手柄 VID/PID 自动识别 + 能力协商
 *   3. 保留原版所有功能（libretro 核心加载、视频/音频、菜单）
 *
 * 构建目标：
 *   ARM32 hard-float, glibc 2.29, e_flags=0x5000400
 *   CFLAGS: -march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4
 *           -mfloat-abi=hard -O2
 *   LDFLAGS: -ldl -lpthread -lm -lz
 *
 * ABI 兼容：所有 dlsym/dlopen/pthread_* 函数指针必须通过 .symver
 *           锁定到 GLIBC_2.4（设备 glibc 2.29 只导出 2.4 版本）
 * ============================================================ */

#ifndef RKGAME_H
#define RKGAME_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* libretro 核心所需结构体（不链接 libretro，本地定义） */
typedef struct {
    const char *path;
    const void *data;
    size_t     size;
    const char *metadata;
} retro_game_info_t;

/* ---- 全局状态 ---- */

extern char     work_path[512];    /* /sdcard/cubegm/ */
extern char     resource_path[512]; /* /sdcard/cubegm/resource/ */
extern char     autorunfile[1024]; /* 启动时传入的 ROM 路径 */
extern char     autorundriver[128];
extern char     system_directory[512];
extern char     save_directory[512];

/* 分辨率（原版固定） */
extern uint16_t n_input_width,       n_input_height;
extern uint16_t n_input_visible_width, n_input_visible_height;
extern uint16_t screen_w, screen_x;
extern uint8_t  rotation;
extern bool     use_rgb_8888;

/* libretro core 句柄 */
extern void *core_handle;

/* ---- libretro 函数指针（从 core .so 获取） ---- */

typedef struct {
    /* 核心元数据 */
    void *(*retro_get_system_info)(void);
    void *(*retro_get_system_av_info)(void);

    /* 生命周期 */
    void (*retro_init)(void);
    void (*retro_deinit)(void);
    void (*retro_load_game)(void *);
    void (*retro_unload_game)(void);
    void (*retro_run)(void);
    void (*retro_frame_time)(void);
    int  (*retro_is_support)(const char *);

    /* 序列化（状态快照，非 SRAM） */
    size_t (*retro_serialize_size)(void);
    bool   (*retro_serialize)(void *, size_t);
    bool   (*retro_unserialize)(const void *, size_t);

    /* SRAM 持久化（原版缺失，重构新增） */
    void *(*retro_get_memory_data)(unsigned);
    size_t (*retro_get_memory_size)(unsigned);

    /* 环境变量 */
    bool (*retro_set_environment)(void (*)(unsigned, void *));

    /* 音视频（legacy batch API，与原厂一致） */
    void (*retro_set_audio_sample_batch)(void (*)(const void *, size_t));
    void (*retro_set_audio_callback)(void *);
    void (*retro_set_video_refresh)(void (*)(const void *, unsigned, unsigned, size_t));
    void (*retro_set_input_poll)(void (*)(void));
    /* libretro input_state: int16_t(port, device, index, id) */
    void (*retro_set_input_state)(int16_t (*)(unsigned, unsigned, unsigned, unsigned));

    /* 区域检测（PAL/NTSC） */
    int  (*retro_get_region)(void);

    /* 设备/控制器 */
    void (*retro_set_controller_port_device)(unsigned, unsigned);
    void (*retro_set_led)(void (*)(unsigned, unsigned));

    /* 进度回调 */
    void (*retro_set_progress_callback)(void (*)(unsigned));

    /* 自定义扩展（原版） */
    void (*retro_get_log_callback)(void);
    int  (*retro_set_unzip)(void (*)(void *, unsigned int, void (*)(unsigned int, void *, void *)));

    /* 像素格式协商 */
    int (*retro_set_pixel_format)(unsigned);
} retro_ctx_t;

extern retro_ctx_t ctx;

/* ---- libretro 像素格式常量（libretro 0x13 版本） ----
 * 常用：0x01 = RGB565, 0x07 = XRGB8888, 0x08 = RGBA8888
 */
#define RETRO_PIXEL_FMT_RGB565   0x01u
#define RETRO_PIXEL_FMT_0RGB1555 0x02u
#define RETRO_PIXEL_FMT_XRGB8888 0x07u
#define RETRO_PIXEL_FMT_RGBA8888 0x08u

/* 当前 core 报告的像素格式（retro_set_pixel_format 回调内记录） */
extern unsigned retro_pixel_format;

/* ---- SRAM 存档 ---- */

#define RETRO_MEMORY_SAVE_RAM   0
#define RETRO_MEMORY_RTC        1
#define RETRO_MEMORY_SYSTEM_RAM 2
#define RETRO_MEMORY_VIDEO_RAM  3

#define SRAMSHIM_MAX_SIZE       (1 * 1024 * 1024)  /* 1 MB 上限 */
#define SRAMSHIM_DEFAULT_DIR    "/sdcard/cubegm/saves"
#define SRAMSHIM_DEFAULT_INTERVAL 10  /* 秒 */

typedef struct {
    char      path[512];          /* 当前 ROM 的 .srm 文件路径 */
    uint8_t  *buf;                /* 内存中的 SRAM 缓冲区（malloc'd） */
    size_t    size;               /* 缓冲区大小 */
    int       interval_sec;       /* 自动落盘间隔 */
    bool      dirty;              /* 是否有未落盘数据 */
    bool      active;             /* 当前 ROM 已加载 */
    int       save_fd;            /* 落盘时用的 fd */
} sram_state_t;

extern sram_state_t sram_state;

/* sram.h API */
void sram_init(void);
void sram_build_path(const char *rom_path);
void sram_load(void);
void sram_save(void);
void sram_save_to_file(void);
void sram_unload(void);
void *sram_get_data(void);
size_t sram_get_size(void);

/* ---- evdev 手柄 ---- */

#define MAX_JOYSTICKS   2
#define MAX_DEVICES     32

typedef struct {
    uint16_t vid;
    uint16_t pid;
    uint16_t revision;
    char     name[64];
    int      fd;
    int      event_fd;
    bool     is_evdev;
    bool     is_js;
    /* 按键映射：下标 = Linux BTN 代码(最高 ~311), 值 = rkgame key bitmap */
    uint32_t button_map[320];
    uint8_t  axis_count;
    uint8_t  button_count;
} joy_device_t;

extern joy_device_t joy_devs[MAX_DEVICES];
extern int          joy_dev_count;

/* evdev.h API */
void joy_init(void);
int  joy_open(const char *path);
bool joy_poll(void);
void joy_close_all(void);
int  joy_get_key(uint8_t player, uint32_t key_id);
int  joy_autodetect(void);   /* 扫描 /dev/input/ 自动识别 */
bool joy_probe_evdev(const char *path, uint16_t *vid, uint16_t *pid);
int16_t joy_input_state(unsigned port, unsigned device, unsigned index, unsigned id);
void joy_state_reset(void);

/* ---- 配置 ---- */

/* rkgame_config_t — 复刻原厂 GetConfig + mui_LoadSetting 的 14 项解析 */
typedef struct {
    /* GetConfig @ 0x9f04 (8 项) */
    int   displayfps;          /* <displayfps> 显示刷新率 */
    int   displaythread;       /* <displaythread> 显示线程标志 */
    int   soft_rotation;       /* <softrotation> 软旋转角度 */
    char  logfile[256];        /* <logfile> 日志文件路径 */
    int   savestatehotkey;     /* <savestatehotkey> 存档热键 (default -1) */
    int   autorestore;         /* <autorestore> 自动恢复 (default 0) */
    int   gamemenuhotkey;      /* <gamemenuhotkey> 游戏菜单热键 (default 9) */
    char  autorun_path[1024];  /* <autorun file="..."> */
    char  autorun_driver[128]; /* <autorun driver="..."> */

    /* mui_LoadSetting @ 0x171f8 (6 项) */
    int   m_ui;                /* <config language="..."> UI 语言索引 */
    int   volume;              /* <config volume="..."> 音量 (default 8) */
    int   defaultlanguage;     /* <defaultlanguage> (default 0) */
    char  music_file[128];     /* <sound><bgm file="..."> 菜单音乐 */
    char  effect0_file[128];   /* <sound><effect0 file="..."> 音效 0 */
    char  effect1_file[128];   /* <sound><effect1 file="..."> 音效 1 */
    char  filebrowser[256];    /* <filebrowser> 文件浏览器根目录 */

    /* 兼容字段（非原厂，rebuild 内部用） */
    char  core_name[128];      /* <core>name</core> 兼容旧格式 */
    char  device0_type[32];    /* <device0_type> */
    char  device1_type[32];    /* <device1_type> */
} rkgame_config_t;

extern rkgame_config_t g_cfg;

void config_load(void);
void config_save(void);

/* ---- 日志 ---- */

#define RKLOG_DEBUG 0
#define RKLOG_INFO  1
#define RKLOG_WARN  2
#define RKLOG_ERROR 3

void rklog(int level, const char *fmt, ...);
#define LOG(fmt, ...) rklog(RKLOG_INFO, fmt, ##__VA_ARGS__)
#define ERR(fmt, ...) rklog(RKLOG_ERROR, fmt, ##__VA_ARGS__)

/* ---- 模块导出 ---- */

/* main.c */
int main(int argc, char **argv);
void autorun(const char *rom, const char *driver);

/* core.c */
int  core_load(const char *rom_path, const char *core_name);
void core_unload(void);
int  core_run(void);

/* core_table.c — 扩展名 → core 映射 */
#include "core_table.h"

/* sram.c */
/* (see above) */

/* evdev.c */
/* (see above) */

/* disp.c */
int  disp_init(void);
void disp_shutdown(void);
bool disp_is_ready(void);
void disp_set_rotation(uint32_t rot);
void disp_set_colormode(int mode);
void disp_flip(const void *buf, unsigned width, unsigned height, size_t pitch);
void disp_clear(uint32_t color);
void disp_draw_rect(int x, int y, int w, int h, uint32_t color);
void disp_draw_text(int x, int y, const char *text, uint32_t color);
void disp_draw_menu(void);
/* UI 辅助（P1.3） */
int  disp_fb_width(void);
int  disp_fb_height(void);
void disp_blit_rgb565(const uint8_t *buf, int width, int height, int pitch);
/* 带偏移的 blit：将 RGB565 图像 blit 到 (x,y) 位置，支持缩略图 overlay。
 * 图像超出 fb 边界时自动裁剪。 */
void disp_blit_rgb565_at(const uint8_t *buf, int x, int y,
                         int width, int height, int pitch);
void disp_present(void);

/* 背景缓存（P2.3 — InitScr RGB565 双缓冲优化） */
int  disp_cache_bg(const uint8_t *rgb565, int width, int height, int pitch);
void disp_draw_cached_bg(void);
void disp_clear_cached_bg(void);
bool disp_bg_cached(void);

/* InitScr RGB565 双缓冲（320×200） */
int  disp_initscr_alloc(void);
void disp_initscr_free(void);
uint16_t *disp_initscr_get_buf(void);
void disp_initscr_flip(void);
void disp_initscr_present(void);
bool disp_initscr_ready(void);

/* audio.c */
int audio_init(void);
void audio_shutdown(void);
void audio_play(const void *buf, size_t frames);
int audio_play_sfx(const char *path);
int audio_play_bgm(const char *path);
void audio_stop_bgm(void);
void audio_set_volume(int percent);
bool audio_is_ready(void);

/* sram.c — Save State（P0-B） */
int  sstate_save(int slot);
int  sstate_load(int slot);
int  sstate_check_hotkey(void);
int  sstate_has_slot(int slot);
extern int g_sstate_slot;

/* menu_log.c — LoadMenuLog / SaveMenuLog（二进制 444B 格式，对齐原厂 0x211f8/0x21388） */
int     LoadMenuLog(void);
int     SaveMenuLog(void);
void    menu_log_set_selected(int idx);
int     menu_log_get_selected(void);
void    menu_log_set_scroll(int offset);
int     menu_log_get_scroll(void);
void    menu_log_set_page(int page);
int     menu_log_get_page(void);
void    menu_log_mark_dirty(void);
int     menu_log_is_dirty(void);
void    menu_log_reset(void);

/* wqw.c — WQW\x03 容器解析（ZIP 变体，filename XOR 0xE5） */
#define WQW_MAX_FILES   256
#define WQW_MAX_NAME    256
typedef struct {
    uint16_t  method;
    uint16_t  time;
    uint16_t  date;
    uint32_t  crc;
    uint32_t  csize;
    uint32_t  usize;
    uint16_t  namelen;
    char      name[WQW_MAX_NAME];
    uint32_t  lfh_offset;
    uint32_t  data_offset;
} wqw_entry_t;
typedef struct {
    wqw_entry_t entries[WQW_MAX_FILES];
    int         count;
} wqw_container_t;

bool    wqw_is_container(const char *path);
int     wqw_parse(const char *path, wqw_container_t *out);
int     wqw_extract(const char *path, const char *filename,
                    unsigned char **out_data, size_t *out_size);
int     wqw_list(const char *path);
int     wqw_extract_index(const char *path, int index,
                          unsigned char **out_data, size_t *out_size,
                          char *out_name, size_t name_size);
void sstate_set_slot(int slot);
int  sstate_get_slot(void);

/* evdev.c — 即插即用（P0-A） */
int  joy_hotplug_check(void);
int  joy_inotify_fd(void);
void joy_inotify_shutdown(void);
uint32_t joy_key_state_get(int dev_idx);
uint32_t joy_all_keys_state(void);
int joystick_action_count(void);
const char *joystick_action_name(int idx);

/* keymap.c — 每核心键位映射 */
int   InitKeyMapping0fEmuType(const char *core_name);
int   SaveKeyMappingConfigFile(void);
int   keymap_lookup(uint32_t key_mask);
int   keymap_set(uint32_t from_key, int to_slot);
const char *keymap_current_core(void);
int   keymap_count(void);

/* driver.so handle (dlopen handle for factory driver) */
extern void *driver_handle;

/* disp.c — 游戏模式切换 */
void disp_set_game_mode(int enabled);
int  disp_is_game_mode(void);
void disp_game_present(void);

/* game_list.c — 游戏列表（P2.2） */
#include "game_list.h"

/* thumbnail.c — 缩略图提取（WQW .dat 容器） */
#include "thumbnail.h"

/* 游戏列表导航状态（main.c 定义，ui.c 读取） */
extern int menu_gl_selected;   /* 当前选中索引 */
extern int menu_gl_scroll;     /* 滚动偏移 */

#endif /* RKGAME_H */
