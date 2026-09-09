/* ============================================================
 * data_tables.c — 内嵌数据表实现（P2-3）
 * ============================================================
 *
 * 数据源：CubeGM/RK3036G 原厂实测 + 工作记忆 2026-09-07
 * ============================================================ */

#include "data_tables.h"
#include "debug.h"
#include "rkgame.h"
#include <string.h>
#include <strings.h>

/* ============================================================
 * configitems — 配置项定义（对齐原厂 50 KB 表）
 * ============================================================ */
const config_item_def_t configitems[] = {
    /* ---- 显示 (14 项) ---- */
    { "displayfps",    CFG_TYPE_ENUM,   "60",      "显示刷新率：auto/30/60/120/144" },
    { "displaythread", CFG_TYPE_INT,    "1",       "显示线程标志" },
    { "brightness",    CFG_TYPE_INT,    "70",      "亮度 (0-100)" },
    { "contrast",      CFG_TYPE_INT,    "50",      "对比度 (0-100)" },
    { "gamma",         CFG_TYPE_INT,    "0",       "Gamma 调整 (-100~100)" },
    { "soft_rotation", CFG_TYPE_INT,    "0",       "软旋转角度 (0/90/180/270)" },
    { "screen_type",   CFG_TYPE_ENUM,   "portrait","屏幕方向：portrait/landscape" },
    { "use_rgb_8888",  CFG_TYPE_BOOL,   "0",       "使用 XRGB8888 格式" },
    { "vsync",         CFG_TYPE_BOOL,   "1",       "垂直同步" },
    { "filter",        CFG_TYPE_ENUM,   "nearest", "过滤模式：nearest/bilinear" },
    { "scanline",      CFG_TYPE_BOOL,   "0",       "扫描线滤镜" },
    { "pixel_perfect", CFG_TYPE_BOOL,   "0",       "像素完美模式" },
    { "overscan",      CFG_TYPE_INT,    "0",       "过扫描补偿 (0-50)" },
    { "boot_logo",     CFG_TYPE_BOOL,   "1",       "显示启动 Logo" },

    /* ---- 语言 (6 项) ---- */
    { "language",       CFG_TYPE_ENUM,  "0",       "界面语言索引 (0=cn,1=en,2=jp,3=tw,4=kr)" },
    { "defaultlanguage",CFG_TYPE_ENUM,  "0",       "默认语言" },
    { "font_size",      CFG_TYPE_INT,   "24",      "字体大小 (12-48)" },
    { "font_bold",      CFG_TYPE_BOOL,  "0",       "粗体字体" },
    { "font_smooth",    CFG_TYPE_BOOL,  "1",       "字体平滑" },
    { "font_locale",    CFG_TYPE_STRING,"zh_CN",   "字体 locale" },

    /* ---- 路径 (8 项) ---- */
    { "work_path",      CFG_TYPE_PATH,  "/sdcard/cubegm/", "工作目录" },
    { "save_dir",       CFG_TYPE_PATH,  "saves/",          "存档目录" },
    { "screenshot_dir", CFG_TYPE_PATH,  "shots/",          "截图目录" },
    { "log_dir",        CFG_TYPE_PATH,  "logs/",           "日志目录" },
    { "log_file",       CFG_TYPE_PATH,  "rkgame.log",      "日志文件名" },
    { "core_dir",       CFG_TYPE_PATH,  "cores/",          "核心目录" },
    { "game_dir",       CFG_TYPE_PATH,  "games/",          "游戏目录" },
    { "resource_path",  CFG_TYPE_PATH,  "resource/",       "资源目录" },

    /* ---- 存档 (8 项) ---- */
    { "autorestore",       CFG_TYPE_INT,  "0",       "AutoRestoreKey 位掩码" },
    { "savestatehotkey",   CFG_TYPE_INT,  "-1",      "存档热键 (-1=禁用, 0-31=键位)" },
    { "sram_enabled",      CFG_TYPE_BOOL, "1",       "启用 SRAM 存档持久化" },
    { "sram_interval",     CFG_TYPE_INT,  "10",      "SRAM 自动保存间隔 (秒)" },
    { "sram_dir",          CFG_TYPE_PATH, "saves/",  "SRAM 存档目录" },
    { "sstate_slots",      CFG_TYPE_INT,  "10",      "Save State 槽位数量" },
    { "sstate_dir",        CFG_TYPE_PATH, "sstates/", "Save State 目录" },
    { "sstate_hotkey",     CFG_TYPE_INT,  "-1",      "Save State 热键 (-1=禁用)" },

    /* ---- 核心 (6 项) ---- */
    { "default_core_dir",   CFG_TYPE_PATH, "cores/",   "核心目录" },
    { "prefer_open_core",   CFG_TYPE_BOOL, "0",        "优先开源核心" },
    { "core_config_dir",    CFG_TYPE_PATH, "cores/",   "核心配置目录" },
    { "auto_select_core",   CFG_TYPE_BOOL, "1",        "自动选择核心" },
    { "core_load_timeout",  CFG_TYPE_INT,  "10",       "核心加载超时 (秒)" },
    { "core_verbose",       CFG_TYPE_BOOL, "0",        "核心详细日志" },

    /* ---- 输入 (10 项) ---- */
    { "joy_layout",     CFG_TYPE_ENUM,   "default", "手柄布局" },
    { "deadzone_x",     CFG_TYPE_INT,    "10",      "X 轴死区 (0-255)" },
    { "deadzone_y",     CFG_TYPE_INT,    "10",      "Y 轴死区 (0-255)" },
    { "deadzone_rum",   CFG_TYPE_INT,    "50",      "震动死区" },
    { "joy_auto_detect",CFG_TYPE_BOOL,   "1",       "手柄自动检测" },
    { "joy_hotplug",    CFG_TYPE_BOOL,   "1",       "手柄热插拔" },
    { "gamemenuhotkey", CFG_TYPE_INT,    "9",       "游戏菜单热键 (0-31)" },
    { "key_repeat_delay",CFG_TYPE_INT,   "300",     "按键重复延迟 (ms)" },
    { "key_repeat_rate", CFG_TYPE_INT,   "33",      "按键重复速率 (ms)" },
    { "joy_calibration", CFG_TYPE_STRING,"default", "手柄校准文件" },

    /* ---- 音频 (8 项) ---- */
    { "volume",           CFG_TYPE_INT,  "8",       "音量 (0-100)" },
    { "audio_latency",    CFG_TYPE_INT,  "50",      "音频延迟 (ms)" },
    { "audio_channels",   CFG_TYPE_ENUM, "stereo",  "声道：mono/stereo" },
    { "audio_resample",   CFG_TYPE_BOOL, "1",       "重采样" },
    { "audio_sample_rate",CFG_TYPE_INT,  "44100",   "采样率 (22050/44100/48000)" },
    { "bgm_volume",       CFG_TYPE_INT,  "80",      "背景音乐音量 (0-100)" },
    { "sfx_volume",       CFG_TYPE_INT,  "100",     "音效音量 (0-100)" },
    { "audio_device",     CFG_TYPE_PATH, "default", "音频设备" },

    /* ---- 系统 (8 项) ---- */
    { "boot_delay",     CFG_TYPE_INT,   "3",       "启动延时 (秒)" },
    { "power_off_mode", CFG_TYPE_ENUM,  "suspend", "关机模式：suspend/reboot/off" },
    { "reboot_delay",   CFG_TYPE_INT,   "2",       "重启延时 (秒)" },
    { "heartbeat",      CFG_TYPE_BOOL,  "1",       "启用心跳检测" },
    { "heartbeat_interval", CFG_TYPE_INT, "5",     "心跳间隔 (秒)" },
    { "auto_shutdown",  CFG_TYPE_BOOL,  "0",       "无操作自动关机" },
    { "auto_shutdown_time", CFG_TYPE_INT, "300",   "自动关机时间 (秒)" },
    { "cpu_freq",       CFG_TYPE_INT,   "1000",    "CPU 频率 (MHz)" },

    { NULL, CFG_TYPE_INT, NULL, NULL }
};

/* ============================================================
 * file_info_list — 文件扩展名/图标/分类
 * ============================================================ */
const file_info_def_t file_info_list[] = {
    /* 000 - Arcade (FBA/MAME) */
    { "zip",  "icon_000", "000" },
    { "7z",   "icon_000", "000" },
    { "tar",  "icon_000", "000" },
    { "gz",   "icon_000", "000" },
    { "cpk",  "icon_000", "000" },

    /* 001 - FC/NES */
    { "nes",  "icon_001", "001" },
    { "fds",  "icon_001", "001" },
    { "nfc",  "icon_001", "001" },
    { "unf",  "icon_001", "001" },
    { "fc",   "icon_001", "001" },
    { "iNES", "icon_001", "001" },

    /* 002 - SFC/SNES */
    { "sfc",  "icon_002", "002" },
    { "smc",  "icon_002", "002" },
    { "fig",  "icon_002", "002" },
    { "gd3",  "icon_002", "002" },
    { "gd7",  "icon_002", "002" },
    { "dx2",  "icon_002", "002" },
    { "bsx",  "icon_002", "002" },
    { "swc",  "icon_002", "002" },
    { "snes", "icon_002", "002" },

    /* 003 - MD/Genesis */
    { "md",   "icon_003", "003" },
    { "smd",  "icon_003", "003" },
    { "bin",  "icon_003", "003" },
    { "gen",  "icon_003", "003" },
    { "sms",  "icon_003", "003" },
    { "sg-1000", "icon_003", "003" },
    { "a16",  "icon_003", "003" },

    /* 004 - GBA */
    { "gba",  "icon_004", "004" },
    { "agb",  "icon_004", "004" },
    { "gbz",  "icon_004", "004" },
    { "srlg", "icon_004", "004" },

    /* 005 - GB/GBC */
    { "gb",   "icon_005", "005" },
    { "gbc",  "icon_005", "005" },
    { "sgb",  "icon_005", "005" },
    { "mb",   "icon_005", "005" },

    /* 007 - PS1 */
    { "iso",  "icon_007", "007" },
    { "img",  "icon_007", "007" },
    { "pbp",  "icon_007", "007" },
    { "chd",  "icon_007", "007" },
    { "cue",  "icon_007", "007" },
    { "mdf",  "icon_007", "007" },

    /* 008 - Atari */
    { "a26",  "icon_008", "008" },
    { "a78",  "icon_008", "008" },

    /* 009 - Virtual Boy */
    { "vt3",  "icon_009", "009" },
    { "vt4",  "icon_009", "009" },

    /* 010 - PSP */
    { "pbp",  "icon_010", "010" },
    { "iso",  "icon_010", "010" },

    /* 011 - N64 */
    { "n64",  "icon_011", "011" },
    { "z64",  "icon_011", "011" },
    { "v64",  "icon_011", "011" },

    /* 012 - DOS */
    { "conf", "icon_misc", "012" },
    { "exe",  "icon_misc", "012" },

    /* 013 - Sega Saturn */
    { "iso",  "icon_013", "013" },
    { "ccd",  "icon_013", "013" },
    { "mds",  "icon_013", "013" },

    /* 014 - Dreamcast */
    { "cdi",  "icon_014", "014" },
    { "iso",  "icon_014", "014" },

    /* 015 - 3DO */
    { "iso",  "icon_015", "015" },
    { "cue",  "icon_015", "015" },

    /* 016 - Jaguar */
    { "jag",  "icon_016", "016" },
    { "zip",  "icon_016", "016" },

    /* ZIP 容器/备份 */
    { "bkp",  "icon_zip",  "000" },
    { "rom",  "icon_misc", "000" },
    { "bin",  "icon_misc", "000" },
    { "dat",  "icon_misc", "000" },

    { NULL, NULL, NULL }
};

/* ============================================================
 * file_info_list_ext — 扩展字段
 * ============================================================ */
const file_info_ext_def_t file_info_list_ext[] = {
    /* ext, supported, default_core_idx */
    { "nes", 1, 0x2 },  { "sfc", 1, 0x4 },  { "md",  1, 0x8 },
    { "gba", 1, 0x10 }, { "gb",  1, 0x20 }, { "iso", 1, 0x80 },
    { "a26", 1, 0x100 }, { "a78", 1, 0x200 }, { "vt3", 1, 0x400 },
    { "conf", 1, 0x800 }, { "zip", 1, 0x10000 }, { "bkp", 1, 0x10000 },
    { "unf", 1, 0x2 },  { "fds", 1, 0x2 },  { "smc", 1, 0x4 },
    { "smd", 1, 0x8 },  { "gbc", 1, 0x20 }, { "pbp", 1, 0x80 },
    { NULL, 0, 0 }
};

/* ============================================================
 * items — UI 菜单项
 * ============================================================ */
const ui_item_def_t items[] = {
    /* 主菜单 (15 项) */
    { "游戏",           "menu.game" },
    { "游戏列表",       "menu.list" },
    { "搜索",           "menu.search" },
    { "最近游戏",       "menu.recent" },
    { "收藏",           "menu.favorite" },
    { "系统设置",       "menu.setting" },
    { "视频设置",       "menu.video" },
    { "音频设置",       "menu.audio" },
    { "手柄设置",       "menu.joystick" },
    { "选择核心",       "menu.core" },
    { "快速保存",       "menu.savestate" },
    { "读取存档",       "menu.loadstate" },
    { "暂停菜单",       "menu.pause" },
    { "手柄测试",       "menu.joytest" },
    { "系统信息",       "menu.system" },

    /* 设置子菜单 (10 项) */
    { "显示刷新率",     "setting.fps" },
    { "亮度",           "setting.brightness" },
    { "音量",           "setting.volume" },
    { "语言",           "setting.language" },
    { "开机启动",       "setting.autorun" },
    { "恢复存档",       "setting.autorestore" },
    { "游戏菜单热键",   "setting.gamemenuhotkey" },
    { "存档热键",       "setting.savestatehotkey" },
    { "日志文件",       "setting.logfile" },
    { "重置设置",       "setting.reset" },

    /* 游戏菜单 (5 项) */
    { "存档",           "game.save" },
    { "读档",           "game.load" },
    { "重置",           "game.reset" },
    { "继续",           "game.resume" },
    { "返回",           "game.back" },

    /* 系统操作 (5 项) */
    { "重启系统",       "system.reboot" },
    { "关机",           "system.poweroff" },
    { "休眠",           "system.suspend" },
    { "更新固件",       "system.update" },
    { "退出",           "system.quit" },

    { NULL, NULL }
};

/* ============================================================
 * aliases — 别名映射
 * ============================================================ */
const alias_def_t aliases[] = {
    /* 主机别名 */
    { "FC",        "NES" },
    { "Famicom",   "NES" },
    { "SNES",      "SFC" },
    { "Super Nintendo", "SFC" },
    { "Sega",      "MD" },
    { "Genesis",   "MD" },
    { "Mega Drive","MD" },
    { "PSX",       "PS1" },
    { "PlayStation", "PS1" },
    { "GameBoy",   "GB" },
    { "Game Boy",  "GB" },
    { "Game Boy Color", "GBC" },
    { "GameBoy Color", "GBC" },
    { "Game Boy Advance", "GBA" },
    { "GameBoy Advance", "GBA" },
    { "Virtual Boy", "VBoy" },
    { "VBoy",      "VBoy" },
    { "Dreamcast", "DC" },
    { "Nintendo 64", "N64" },
    { "N64",       "N64" },

    /* 文件扩展名别名 */
    { "GBA",       "AGB" },
    { "GB",        "GBC" },
    { "MD",        "SMD" },
    { "SMS",       "MD"  },
    { "GENESIS",   "MD"  },
    { "SMD",       "MD"  },
    { "FC",        "NES" },
    { "FDS",       "NES" },
    { "UNF",       "NES" },
    { "SNES",      "SFC" },
    { "SMC",       "SFC" },
    { "FIG",       "SFC" },
    { "PS1",       "PS1" },
    { "ISO",       "PS1" },
    { "IMG",       "PS1" },
    { "A26",       "A26" },
    { "A78",       "A78" },
    { "VT3",       "VBoy"},
    { "VT4",       "VBoy"},
    { "N64",       "ZIP" },  /* N64 ROM 通过 FBA 走 ZIP */
    { "7Z",        "ZIP" },
    { "TAR",       "ZIP" },
    { "GZ",        "ZIP" },

    { NULL, NULL }
};

/* ============================================================
 * sbi — 保存状态索引
 * ============================================================ */
const sbi_def_t sbi[] = {
    { 0,  "Slot 1" },
    { 1,  "Slot 2" },
    { 2,  "Slot 3" },
    { 3,  "Slot 4" },
    { 4,  "Slot 5" },
    { 5,  "Slot 6" },
    { 6,  "Slot 7" },
    { 7,  "Slot 8" },
    { 8,  "Slot 9" },
    { 9,  "Slot 10" },
    { -1, NULL }
};

/* ============================================================
 * mi — 菜单项信息（原厂 6.9 KB 表，快捷键扫描码）
 * ============================================================ */
const mi_def_t mi[] = {
    { "menu_game",     1, 1 },
    { "menu_list",     2, 1 },
    { "menu_search",   3, 1 },
    { "menu_recent",   4, 1 },
    { "menu_favorite", 5, 1 },
    { "menu_setting",  6, 1 },
    { "menu_video",    7, 1 },
    { "menu_joystick", 8, 1 },
    { "menu_core",     9, 1 },
    { "menu_save",    10, 1 },
    { "menu_load",    11, 1 },
    { "menu_pause",   12, 1 },
    { "menu_joytest", 13, 1 },
    { "menu_reboot",  14, 1 },
    { "menu_power",   15, 1 },
    { "menu_quit",    16, 1 },
    { "menu_up",      17, 1 },
    { "menu_down",    18, 1 },
    { "menu_left",    19, 1 },
    { "menu_right",   20, 1 },
    { "menu_back",    21, 1 },
    { "menu_ok",      22, 1 },
    { "menu_cancel",  23, 1 },
    { "menu_a",       24, 1 },
    { "menu_b",       25, 1 },
    { "menu_x",       26, 1 },
    { "menu_y",       27, 1 },
    { "menu_start",   28, 1 },
    { "menu_select",  29, 1 },
    { "menu_l",       30, 1 },
    { "menu_r",       31, 1 },
    { NULL, 0, 0 }
};

const mi_def_t *mi_find(const char *name)
{
    if (!name) return NULL;
    for (unsigned int i = 0; i < MI_COUNT; i++) {
        if (mi[i].name && strcmp(mi[i].name, name) == 0)
            return &mi[i];
    }
    return NULL;
}

/* ============================================================
 * 访问 API
 * ============================================================ */

const config_item_def_t *configitems_find(const char *key)
{
    if (!key) return NULL;
    for (unsigned int i = 0; i < CONFIGITEMS_COUNT; i++) {
        if (configitems[i].key && strcmp(configitems[i].key, key) == 0)
            return &configitems[i];
    }
    return NULL;
}

const file_info_def_t *file_info_find(const char *ext)
{
    if (!ext) return NULL;
    for (unsigned int i = 0; i < FILE_INFO_COUNT; i++) {
        if (file_info_list[i].ext &&
            strcasecmp(file_info_list[i].ext, ext) == 0)
            return &file_info_list[i];
    }
    return NULL;
}

const file_info_ext_def_t *file_info_ext_find(const char *ext)
{
    if (!ext) return NULL;
    for (unsigned int i = 0; i < FILE_INFO_EXT_COUNT; i++) {
        if (file_info_list_ext[i].ext &&
            strcasecmp(file_info_list_ext[i].ext, ext) == 0)
            return &file_info_list_ext[i];
    }
    return NULL;
}

const alias_def_t *alias_find(const char *alias)
{
    if (!alias) return NULL;
    for (unsigned int i = 0; i < ALIASES_COUNT; i++) {
        if (aliases[i].alias &&
            strcasecmp(aliases[i].alias, alias) == 0)
            return &aliases[i];
    }
    return NULL;
}

int data_tables_init(void)
{
    /* 简单验证：所有表非空 */
    if (CONFIGITEMS_COUNT < 2 || FILE_INFO_COUNT < 2 ||
        ITEMS_COUNT < 2 || ALIASES_COUNT < 2 || SBI_COUNT < 2) {
        ERR("data_tables_init: table too small");
        return -1;
    }
    return 0;
}

void data_tables_report(void)
{
    LOG("data_tables_report: configitems=%u file_info=%u file_info_ext=%u items=%u aliases=%u sbi=%u mi=%u",
        (unsigned)CONFIGITEMS_COUNT, (unsigned)FILE_INFO_COUNT,
        (unsigned)FILE_INFO_EXT_COUNT, (unsigned)ITEMS_COUNT,
        (unsigned)ALIASES_COUNT, (unsigned)SBI_COUNT,
        (unsigned)MI_COUNT);
}
