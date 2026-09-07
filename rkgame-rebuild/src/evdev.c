/* ============================================================
 * rkgame-rebuild — evdev 手柄自动识别
 * ============================================================
 *
 * 原版实现（反编译实证）：
 *   ReadUSBJoy(port):
 *     1. access(JOYSTICK_DEVNAME[port]) — 硬编码的设备路径
 *     2. open(JOYSTICK_DEVNAME[port], O_RDONLY)
 *     3. read(fd, buf, 8) — evdev event
 *     4. GetInputInfo("js%d", param) — 读取 /proc/bus/input/devices
 *     5. GetJoystickConfig(USB_Table[port], vid, pid, rev) — 查硬编码映射表
 *
 * 核心问题：
 *   - JOYSTICK_DEVNAME[] 是静态字符数组（如 "/dev/input/js0"）
 *   - USB_Table[] 是静态映射表（按 VID/PID/REV 匹配按键位）
 *   - 不支持即插即用：手柄变化需改代码重新编译
 *
 * 重构方案：
 *   1. 扫描 /dev/input/event* 枚举所有设备
 *   2. ioctl(EVIOCGID) 获取 VID/PID/REV
 *   3. ioctl(EVIOCGBIT) 获取按键/摇杆能力
 *   4. 与内置常见手柄映射表匹配
 *   5. 不支持时输出诊断日志
 *
 * 设备路径优先级：
 *   /dev/input/eventN > /dev/input/jsN（evdev 接口更现代、信息更全）
 *
 * ABI 铁律：
 *   - 需要 linux/input.h、sys/ioctl.h
 *   - ioctl 不需要特殊 .symver（libc 默认版本可用）
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <dirent.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <linux/input.h>
#include <sys/inotify.h>
#include <sys/select.h>

#include "rkgame.h"
#include "ui_zip.h"

/* joy_devs / joy_dev_count 定义在 main.c */

/* ---- inotify 即插即用（P0-A） ----
 *
 * 工厂验证（网络 + 真机）：
 *   - inotify_init1(IN_NONBLOCK) 在 Linux 2.6.13+ 可用
 *   - /dev/input/ 目录监控 IN_CREATE | IN_DELETE | IN_ATTRIB
 *   - 设备节点在 IN_CREATE 后不能立即 open（权限未设置），
 *     需等 IN_ATTRIB 事件再尝试
 *   - 设备拔出时 open 返回 ENOENT，正常忽略
 *
 * 本实现：
 *   - joy_inotify_fd: inotify 文件描述符
 *   - joy_hotplug_check(): 非阻塞检查 inotify 事件
 *   - 触发后调用 joy_autodetect() 重新扫描
 */

static int g_inotify_fd = -1;
static int g_inotify_wd = -1;   /* watch descriptor */

/* 初始化 inotify 监控 /dev/input/ */
static void joy_inotify_init(void)
{
    g_inotify_fd = inotify_init1(IN_NONBLOCK);
    if (g_inotify_fd < 0) {
        ERR("joy_inotify_init: inotify_init1 failed: %s", strerror(errno));
        return;
    }

    g_inotify_wd = inotify_add_watch(g_inotify_fd, "/dev/input",
                                       IN_CREATE | IN_DELETE | IN_ATTRIB);
    if (g_inotify_wd < 0) {
        ERR("joy_inotify_init: inotify_add_watch failed: %s", strerror(errno));
        close(g_inotify_fd);
        g_inotify_fd = -1;
        return;
    }

    LOG("joy_inotify_init: watching /dev/input (wd=%d)", g_inotify_wd);
}

/* 销毁 inotify 监控 */
void joy_inotify_shutdown(void)
{
    if (g_inotify_wd >= 0 && g_inotify_fd >= 0) {
        inotify_rm_watch(g_inotify_fd, g_inotify_wd);
        g_inotify_wd = -1;
    }
    if (g_inotify_fd >= 0) {
        close(g_inotify_fd);
        g_inotify_fd = -1;
    }
}

/* 非阻塞检查 inotify 事件。
 * 返回 1 = 检测到设备变化（已重新扫描），0 = 无变化。 */
int joy_hotplug_check(void)
{
    if (g_inotify_fd < 0) return 0;

    struct inotify_event *ev;
    char buf[4096] __attribute__((aligned(8)));
    ssize_t n = read(g_inotify_fd, buf, sizeof(buf));
    if (n <= 0) return 0;

    int changed = 0;
    char *ptr = buf;
    while (ptr < buf + n) {
        ev = (struct inotify_event *)ptr;
        if (ev->len > 0) {
            /* 设备增删 */
            const char *name = ev->name;
            if (strncmp(name, "event", 5) == 0) {
                LOG("joy_hotplug: /dev/input/%s event 0x%x",
                    name, ev->mask);
                if (ev->mask & (IN_CREATE | IN_ATTRIB)) {
                    /* 设备插入或权限设置完成 */
                    changed = 1;
                } else if (ev->mask & IN_DELETE) {
                    /* 设备拔出 */
                    changed = 1;
                }
            }
        }
        ptr += sizeof(struct inotify_event) + ev->len;
    }

    if (changed) {
        LOG("joy_hotplug: device change detected, rescan...");
        /* 短暂延迟确保设备节点就绪 */
        usleep(100000);  /* 100ms */
        joy_autodetect();
    }

    return changed;
}

/* 获取 inotify fd（供 main loop select 使用） */
int joy_inotify_fd(void)
{
    return g_inotify_fd;
}

/* ---- 内置手柄映射表（常见设备） ---- */

/* 映射格式：button_id(0-31) -> rkgame key bitmap 位 */
/* 标准 12 键映射（A/B/X/Y/L1/L2/R1/R2/Start/Select/Up/Down/Left/Right/L3/R3） */

typedef struct {
    uint16_t vid;
    uint16_t pid;
    const char *name_pattern;  /* NULL = 匹配任意 name */
    const uint32_t *button_map;  /* 320 元素数组：btn_code -> key_mask */
    uint8_t  axis_left;
    uint8_t  axis_right;
    uint8_t  hat;              /* HAT0 = 0, HAT1 = 1, ... */
} joystick_profile_t;

/* 按键位定义（兼容 rkgame key bitmap） */
#define KEY_UP      (1 << 0)   /* 0x01 */
#define KEY_DOWN    (1 << 1)   /* 0x02 */
#define KEY_LEFT    (1 << 2)   /* 0x04 */
#define KEY_RIGHT   (1 << 3)   /* 0x08 */
#define KEY_A       (1 << 4)   /* 0x10 */
#define KEY_B       (1 << 5)   /* 0x20 */
#define KEY_X       (1 << 6)   /* 0x40 */
#define KEY_Y       (1 << 7)   /* 0x80 */
#define KEY_L1      (1 << 8)
#define KEY_R1      (1 << 9)
#define KEY_L2      (1 << 10)
#define KEY_R2      (1 << 11)
#define KEY_START   (1 << 12)
#define KEY_SELECT  (1 << 13)

/* 原厂 26 动作词表（joystick.zip 内，对齐 GetJoystickConfig @ 0x29d48）
 * 索引 = token 编号 (0-25)，值 = 动作名称字符串
 * 前 17 个 = 按钮，后 3 个 = hat/axis */
static const char *const joystick_actions[26] = {
    "A", "B", "X", "Y", "L1", "R1", "L2", "R2",
    "START", "SELECT", "L3", "R3",
    "UP", "DOWN", "LEFT", "RIGHT",
    "AXIS_X_PLUS", "AXIS_X_MINUS", "AXIS_Y_PLUS", "AXIS_Y_MINUS",
    "HAT_UP", "HAT_DOWN", "HAT_LEFT", "HAT_RIGHT",
    "TRIGGER_LEFT", "TRIGGER_RIGHT",
};

int joystick_action_count(void) { return 26; }
const char *joystick_action_name(int idx)
{
    if (idx < 0 || idx >= 26) return NULL;
    return joystick_actions[idx];
}

/* 通用手柄映射（匹配大多数 USB 手柄） */
static const uint32_t generic_button_map[320] = {
    [BTN_A]       = KEY_A,
    [BTN_B]       = KEY_B,
    [BTN_X]       = KEY_X,
    [BTN_Y]       = KEY_Y,
    [BTN_TL]      = KEY_L1,
    [BTN_TR]      = KEY_R1,
    [BTN_TL2]     = KEY_L2,
    [BTN_TR2]     = KEY_R2,
    [BTN_START]   = KEY_START,
    [BTN_SELECT]  = KEY_SELECT,
    [BTN_THUMBL]  = KEY_L1,    /* L3 */
    [BTN_THUMBR]  = KEY_R1,    /* R3 */
};

/* 8BitDo SN30 Pro */
static const uint32_t sn30_button_map[320] = {
    [BTN_A]       = KEY_A,
    [BTN_B]       = KEY_B,
    [BTN_X]       = KEY_X,
    [BTN_Y]       = KEY_Y,
    [BTN_TL]      = KEY_L1,
    [BTN_TR]      = KEY_R1,
    [BTN_TL2]     = KEY_L2,
    [BTN_TR2]     = KEY_R2,
    [BTN_START]   = KEY_START,
    [BTN_SELECT]  = KEY_SELECT,
};

/* 内置 profiles */
static const joystick_profile_t built_in_profiles[] = {
    /* 8BitDo SN30 Pro+ (D-Pad) */
    { .vid = 0x2dc8, .pid = 0x2000, .name_pattern = "8BitDo",
      .button_map = sn30_button_map, .axis_left = 0, .axis_right = 1, .hat = 0 },

    /* XBox 360 Controller */
    { .vid = 0x045e, .pid = 0x028e, .name_pattern = "XBOX",
      .button_map = generic_button_map, .axis_left = 0, .axis_right = 1, .hat = 0 },

    /* PS3 DualShock 3 (蓝牙) */
    { .vid = 0x054c, .pid = 0x0268, .name_pattern = "PLAYSTATION",
      .button_map = generic_button_map, .axis_left = 0, .axis_right = 1, .hat = 0 },

    /* 通用手柄（匹配所有有 BTN_A+BTN_B 的设备） */
    { .vid = 0, .pid = 0, .name_pattern = NULL,
      .button_map = generic_button_map, .axis_left = 0, .axis_right = 1, .hat = 0 },
};

#define PROFILE_COUNT (sizeof(built_in_profiles) / sizeof(built_in_profiles[0]))

/* ---- joystick.zip 动态加载（P2.5） ----
 *
 * 工厂实证（GetJoystickConfig @ 0x29d48）：
 *   OpenZipU("joystick.zip") → FindZipItemA("VID_PID_REV") → UnzipItem
 *   20 token 映射（16-bit LE 每 token）：
 *     token  0..16 → 17 个 evdev BTN_* 按钮码（值=对应的 evdev BTN_* 号）
 *     token 17      → hat device index (HAT0=0, HAT1=1, ...)
 *     token 18      → axisX axis code (ABS_X=0, ...)
 *     token 19      → axisY axis code (ABS_Y=1, ...)
 *
 * token 顺序（对应 evdev 标准游戏手柄布局）：
 *   0:B, 1:Y, 2:SELECT, 3:START, 4:SHOULDER_L(L1), 5:SHOULDER_R(R1),
 *   6:A, 7:X, 8:UP, 9:DOWN, 10:LEFT, 11:RIGHT,
 *   12:L3(THUMBL), 13:R3(THUMBR), 14:Z(LEFTSTICK), 15:Z2(RIGHTSTICK),
 *   16:Y(shoulder_Y/extra)
 *
 * 本实现：
 *   - joy_load_joystick_zip(): 从 joystick.zip 读取实际 profile
 *   - 将 token 写入 joy_dynamic_profiles[]，替换硬编码 built_in_profiles[]
 *   - joy_match_profile() 优先使用动态 profile（按 VID/PID 匹配）
 */

/* 20-token 到 KEY_* 位掩码的映射（顺序与上表一致） */
static const uint32_t token_to_key[17] = {
    [0]  = KEY_B,
    [1]  = KEY_Y,
    [2]  = KEY_SELECT,
    [3]  = KEY_START,
    [4]  = KEY_L1,
    [5]  = KEY_R1,
    [6]  = KEY_A,
    [7]  = KEY_X,
    [8]  = KEY_UP,
    [9]  = KEY_DOWN,
    [10] = KEY_LEFT,
    [11] = KEY_RIGHT,
    [12] = KEY_L1,   /* L3 = L1 slot */
    [13] = KEY_R1,   /* R3 = R1 slot */
    [14] = 0,        /* Z (leftstick) — 未映射 */
    [15] = 0,        /* Z2 (rightstick) — 未映射 */
    [16] = KEY_Y,    /* Y extra */
};

#define JOY_MAX_DYNAMIC 16
static joystick_profile_t g_dynamic_profiles[JOY_MAX_DYNAMIC];
static uint32_t g_dynamic_btn_maps[JOY_MAX_DYNAMIC][320];
static int g_dynamic_count = 0;

/* 将 token 数组应用到 button_map（可写缓冲区） */
static void joy_apply_tokens(uint32_t *btn_map,
                             const unsigned char *tokens, size_t len)
{
    memset(btn_map, 0, sizeof(uint32_t) * 320);
    for (int t = 0; t < 17 && (size_t)(t * 2 + 1) < len; t++) {
        uint16_t btn_code = (uint16_t)(tokens[t * 2] | (tokens[t * 2 + 1] << 8));
        uint32_t key = token_to_key[t];
        if (btn_code == 0 || key == 0) continue;
        if (btn_code < 320) {
            btn_map[btn_code] = key;
        }
    }
}

/* 查找最佳匹配的 profile（优先动态 profile，再 fallback 到内置） */
static const joystick_profile_t *joy_match_profile(uint16_t vid, uint16_t pid)
{
    /* 动态 profile（joystick.zip 加载）优先 */
    for (int i = 0; i < g_dynamic_count; i++) {
        if (g_dynamic_profiles[i].vid == vid &&
            g_dynamic_profiles[i].pid == pid) {
            return &g_dynamic_profiles[i];
        }
    }
    /* 内置 profile */
    for (int i = 0; i < (int)PROFILE_COUNT; i++) {
        if (built_in_profiles[i].vid == vid &&
            built_in_profiles[i].pid == pid) {
            return &built_in_profiles[i];
        }
    }
    /* 通用 fallback（最后一条：vid=0, pid=0, name_pattern=NULL） */
    if (PROFILE_COUNT > 0) return &built_in_profiles[PROFILE_COUNT - 1];
    return NULL;
}

static int joy_load_joystick_zip(void)
{
    char path[512];
    snprintf(path, sizeof(path), "%sjoystick.zip", work_path);

    ui_zip_t *z = NULL;
    if (ui_zip_open(path, &z) < 0) {
        LOG("joy_load_joystick_zip: %s not found (using built-in profiles)", path);
        return -1;
    }

    char names[256][256];
    int n = ui_zip_list(z, names, 256);
    if (n <= 0) {
        LOG("joy_load_joystick_zip: no entries in %s", path);
        ui_zip_close(z);
        return -1;
    }

    LOG("joy_load_joystick_zip: found %d entries in %s", n, path);

    g_dynamic_count = 0;
    for (int i = 0; i < n; i++) {
        /* VID_PID_REV 格式（如 0810_0001_0100） */
        if (strlen(names[i]) != 14) continue;
        if (names[i][4] != '_' || names[i][9] != '_') continue;

        int is_hex = 1;
        for (int j = 0; j < 14 && is_hex; j++) {
            if (j == 4 || j == 9) continue;
            char c = names[i][j];
            if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                  (c >= 'A' && c <= 'F'))) is_hex = 0;
        }
        if (!is_hex) continue;

        if (g_dynamic_count >= JOY_MAX_DYNAMIC) {
            LOG("joy_load_joystick_zip: dynamic profile table full");
            break;
        }

        unsigned int vid = (unsigned int)strtoul(names[i], NULL, 16);
        unsigned int pid = (unsigned int)strtoul(names[i] + 5, NULL, 16);
        (void)strtoul(names[i] + 10, NULL, 16);

        size_t ps;
        if (ui_zip_find(z, names[i], &ps) < 0 || ps < 40) {
            LOG("joy_load_joystick_zip: profile %s too small (%zu bytes)",
                names[i], ps);
            continue;
        }

        void *pdata = NULL;
        size_t pout;
        if (ui_zip_extract(z, names[i], &pdata, &pout) < 0) continue;

        const unsigned char *tokens = (const unsigned char *)pdata;
        LOG("joy_load_joystick_zip: profile %s (vid=0x%04x pid=0x%04x) "
            "first 4 tokens: %02x %02x %02x %02x",
            names[i], vid, pid,
            tokens[0], tokens[1], tokens[2], tokens[3]);

        joystick_profile_t *p = &g_dynamic_profiles[g_dynamic_count];
        memset(p, 0, sizeof(*p));
        p->vid = (uint16_t)vid;
        p->pid = (uint16_t)pid;
        p->name_pattern = NULL;
        p->button_map = g_dynamic_btn_maps[g_dynamic_count];
        joy_apply_tokens(p->button_map, tokens, pout);

        /* hat/axis（token 17-19） */
        if (17 * 2 < (int)pout) p->hat = tokens[17 * 2];
        if (18 * 2 + 1 < (int)pout) p->axis_left = tokens[18 * 2];
        if (19 * 2 + 1 < (int)pout) p->axis_right = tokens[19 * 2];

        g_dynamic_count++;

        /* 日志：显示映射摘要 */
        int mapped = 0;
        for (int b = 0; b < 320; b++) {
            if (p->button_map[b]) mapped++;
        }
        LOG("joy_load_joystick_zip: profile %s -> %d buttons mapped, "
            "hat=%u axisL=%u axisR=%u",
            names[i], mapped, p->hat, p->axis_left, p->axis_right);

        free(pdata);
    }

    ui_zip_close(z);
    LOG("joy_load_joystick_zip: loaded %d dynamic profiles", g_dynamic_count);
    return g_dynamic_count > 0 ? 0 : -1;
}

/* ---- evdev 探测 ---- */

/*
 * joy_probe_evdev：打开 /dev/input/eventN 并探测设备信息。
 * 返回 0 = 成功，-1 = 失败。
 */
int joy_open(const char *path)
{
    if (joy_dev_count >= MAX_DEVICES) return -1;

    int fd = open(path, O_RDONLY | O_NONBLOCK);
    if (fd < 0) return -1;

    /* EVIOCGID — 获取 VID/PID/REV */
    struct input_id id = { 0 };
    if (ioctl(fd, EVIOCGID, &id) < 0) {
        close(fd);
        return -1;
    }

    /* EVIOCGNAME — 获取设备名 */
    char name[128] = { 0 };
    if (ioctl(fd, EVIOCGNAME(sizeof(name) - 1), name) < 0)
        snprintf(name, sizeof(name), "unknown");

    /* EVIOCGBIT — 获取按键能力位图 */
    unsigned long key_bits[(KEY_MAX + 1) / sizeof(unsigned long)];
    memset(key_bits, 0, sizeof(key_bits));
    if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)), key_bits) < 0) {
        close(fd);
        return -1;
    }

    /* 统计按键数 */
    unsigned int button_count = 0;
    for (unsigned int i = BTN_0; i < KEY_MAX; i++) {
        if (i < (KEY_MAX & ~(sizeof(unsigned long) * 8 - 1)))
            break;
        if (key_bits[i / (sizeof(unsigned long) * 8)] & (1U << (i % (sizeof(unsigned long) * 8))))
            button_count++;
    }

    joy_device_t *dev = &joy_devs[joy_dev_count];
    dev->vid = id.vendor;
    dev->pid = id.product;
    dev->revision = id.version;
    strncpy(dev->name, name, sizeof(dev->name) - 1);
    dev->fd = -1;
    dev->event_fd = fd;
    dev->is_evdev = true;
    dev->is_js = false;
    dev->axis_count = 0;
    dev->button_count = button_count;

    /* 优先使用 joystick.zip 动态 profile，再 fallback 到内置 */
    const joystick_profile_t *prof = joy_match_profile(id.vendor, id.product);
    if (prof) {
        memcpy(dev->button_map, prof->button_map, sizeof(dev->button_map));
        LOG("joy: matched profile for %s", name);
    } else {
        memcpy(dev->button_map, generic_button_map, sizeof(dev->button_map));
    }

    joy_dev_count++;

    LOG("joy: probe %s -> vendor=0x%04x pid=0x%04x rev=0x%04x name=\"%s\" buttons=%u",
        path, dev->vid, dev->pid, dev->revision, dev->name, button_count);

    return 0;
}

/*
 * joy_autodetect：扫描 /dev/input/ 自动枚举所有手柄设备。
 */
int joy_autodetect(void)
{
    LOG("joy_autodetect: scanning /dev/input/");

    /* 重置已打开设备 */
    joy_close_all();

    DIR *dir = opendir("/dev/input");
    if (!dir) {
        ERR("joy_autodetect: cannot open /dev/input: %s", strerror(errno));
        return -1;
    }

    struct dirent *ent;
    while ((ent = readdir(dir)) != NULL) {
        const char *name = ent->d_name;
        if (strncmp(name, "event", 5) == 0) {
            char path[64];
            snprintf(path, sizeof(path), "/dev/input/%s", name);
            joy_open(path);
        }
    }
    closedir(dir);

    LOG("joy_autodetect: found %d devices", joy_dev_count);
    return joy_dev_count;
}

bool joy_probe_evdev(const char *path, uint16_t *out_vid, uint16_t *out_pid)
{
    int fd = open(path, O_RDONLY | O_NONBLOCK);
    if (fd < 0) return false;

    struct input_id id = { 0 };
    if (ioctl(fd, EVIOCGID, &id) < 0) {
        close(fd);
        return false;
    }

    if (out_vid) *out_vid = id.vendor;
    if (out_pid) *out_pid = id.product;
    close(fd);
    return true;
}

void joy_close_all(void)
{
    for (int i = 0; i < joy_dev_count; i++) {
        if (joy_devs[i].event_fd >= 0) {
            close(joy_devs[i].event_fd);
            joy_devs[i].event_fd = -1;
        }
        if (joy_devs[i].fd >= 0) {
            close(joy_devs[i].fd);
            joy_devs[i].fd = -1;
        }
    }
    joy_dev_count = 0;
}

/*
 * joy_poll：读取所有已连接手柄的事件。
 * 返回 true 如果至少有一个手柄有输入。
 */
static void joy_update_state(joy_device_t *dev, int dev_idx,
                             const struct input_event *ev, size_t count);  /* fwd */
bool joy_poll(void)
{
    bool any = false;
    for (int i = 0; i < joy_dev_count; i++) {
        if (joy_devs[i].event_fd < 0) continue;

        struct input_event ev[16];
        ssize_t n = read(joy_devs[i].event_fd, ev, sizeof(ev));
        if (n <= 0) continue;

        size_t count = n / sizeof(struct input_event);
        for (size_t j = 0; j < count; j++) {
            struct input_event *e = &ev[j];
            if (e->type == EV_KEY && e->value > 0) {
                unsigned int code = (unsigned int)e->code;
                if (code < 320 && joy_devs[i].button_map[code]) {
                    any = true;
                }
            } else if (e->type == EV_ABS) {
                /* 摇杆/按键释放 */
                any = true;
            }
        }
        /* 更新状态 bitmap（供 joy_input_state 查询） */
        joy_update_state(&joy_devs[i], i, ev, count);
    }
    return any;
}

/*
 * joy_get_key：查询手柄按键状态。
 * player: 0-1 (对应 rkgame 的两个 player 槽位)
 * key_id: 按键位掩码（如 KEY_A = 0x10）
 * 返回 1 = 按下，0 = 未按下
 */
int joy_get_key(uint8_t player, uint32_t key_id)
{
    if (player >= (uint8_t)joy_dev_count) return 0;

    joy_device_t *dev = &joy_devs[player];
    if (dev->event_fd < 0) return 0;

    /* 读取所有待处理事件（非阻塞） */
    struct input_event ev[32];
    ssize_t n = read(dev->event_fd, ev, sizeof(ev));
    if (n <= 0) return 0;

    size_t count = n / sizeof(struct input_event);
    for (size_t j = 0; j < count; j++) {
        struct input_event *e = &ev[j];
        if (e->type == EV_KEY && e->value > 0) {
            unsigned int code = (unsigned int)e->code;
            if (code < 320 && dev->button_map[code] == key_id)
                return 1;
        }
    }
    return 0;
}

/*
 * joy_init：初始化手柄子系统，调用自动探测。
 */
void joy_init(void)
{
    LOG("joy_init: initializing");
    joy_dev_count = 0;

    /* P0-A: 初始化 inotify 即插即用 */
    joy_inotify_init();

    /* P2.5: 尝试从 joystick.zip 加载动态 profile */
    joy_load_joystick_zip();

    /* 自动探测 */
    int count = joy_autodetect();
    if (count < 0) {
        ERR("joy_init: autodetect failed, falling back to static devices");
        /* 回退到静态设备路径（兼容原版） */
        static const char *fallback_devices[] = {
            "/dev/input/event0", "/dev/input/event1",
            "/dev/input/js0", "/dev/input/js1",
            NULL
        };
        for (int i = 0; fallback_devices[i] != NULL; i++) {
            if (access(fallback_devices[i], F_OK) == 0) {
                joy_open(fallback_devices[i]);
            }
        }
    }

    LOG("joy_init: %d device(s) ready", joy_dev_count);
}

/*
 * joy_print_diag：打印所有已连接手柄的诊断信息。
 * 用于调试 /sdcard/cubegm/ 下的 sramshim.log。
 */
void joy_print_diag(void)
{
    LOG("joy_diag: ===");
    for (int i = 0; i < joy_dev_count; i++) {
        joy_device_t *d = &joy_devs[i];
        LOG("  [%d] %s vid=0x%04x pid=0x%04x rev=0x%04x evdev=%s fd=%d buttons=%u",
            i, d->name, d->vid, d->pid, d->revision,
            d->is_evdev ? "yes" : "no", d->event_fd, d->button_count);
    }
    LOG("joy_diag: ===");
}

/* ============================================================
 * libretro input_state 回调（原厂 retro_set_input_state 绑定目标）
 *
 * 签名：int16_t f(unsigned port, unsigned device, unsigned index, unsigned id)
 *   - port: 0 或 1（对应 joy_devs[0] / joy_devs[1]）
 *   - device: RETRO_DEVICE_JOYPAD = 1
 *   - index: 未用（JOYPAD 无 index）
 *   - id: RETRO_DEVICE_ID_JOYPAD_* (0..17)
 *
 * 返回：0 = 未按下，非 0 = 按下（通常返回 1）
 *
 * RETRO_DEVICE_ID_JOYPAD_* 常量（libretro.h）：
 *   0=UP, 1=DOWN, 2=LEFT, 3=RIGHT, 4=A(BUTTON_A), 5=B(BUTTON_B),
 *   6=SELECT, 7=START, 8=shoulder_left, 9=shoulder_right,
 *   10=UP_DOWN, 11=LEFT_RIGHT, 12=A_DOWN, 13=B_DOWN,
 *   14=L3, 15=R3, 16=button_z, 17=button_y
 * ============================================================ */

/* joy_state 内部使用的键位 bitmap（由 joy_poll 维护） */
static uint32_t joy_key_state[MAX_DEVICES];  /* per-device key mask */

/* 公开访问函数：返回指定设备的当前按键 bitmask。
 * 供 sstate_check_hotkey() 等外部模块使用，避免重复 read() evdev fd。 */
uint32_t joy_key_state_get(int dev_idx)
{
    if (dev_idx < 0 || dev_idx >= joy_dev_count) return 0;
    return joy_key_state[dev_idx];
}

/* 便捷封装：返回所有设备的按键 bitmask 聚合（供 sstate_check_hotkey 使用） */
uint32_t joy_all_keys_state(void)
{
    uint32_t agg = 0;
    for (int i = 0; i < joy_dev_count; i++) {
        agg |= joy_key_state[i];
    }
    return agg;
}

/* 更新单个设备的键位状态（由 joy_poll 调用） */
static void joy_update_state(joy_device_t *dev, int dev_idx,
                             const struct input_event *ev, size_t count)
{
    for (size_t j = 0; j < count; j++) {
        const struct input_event *e = &ev[j];
        if (e->type != EV_KEY || (unsigned int)e->code >= 320) continue;
        uint32_t key = dev->button_map[(unsigned int)e->code];
        if (!key) continue;
        if (e->value > 0) {
            joy_key_state[dev_idx] |= key;  /* 按下 */
        } else if (e->value == 0) {
            joy_key_state[dev_idx] &= ~key; /* 释放 */
        }
    }
}

/* RETRO_DEVICE_ID_JOYPAD_* → rkgame KEY 位掩码映射 */
#define RJPAD_UP      (1 << 0)
#define RJPAD_DOWN    (1 << 1)
#define RJPAD_LEFT    (1 << 2)
#define RJPAD_RIGHT   (1 << 3)
#define RJPAD_A       (1 << 4)
#define RJPAD_B       (1 << 5)
#define RJPAD_SELECT  (1 << 6)
#define RJPAD_START   (1 << 7)
#define RJPAD_L       (1 << 8)
#define RJPAD_R       (1 << 9)
#define RJPAD_L3      (1 << 10)
#define RJPAD_R3      (1 << 11)

int16_t joy_input_state(unsigned port, unsigned device, unsigned index, unsigned id)
{
    (void)index;
    if (device != 1 /* RETRO_DEVICE_JOYPAD */) return 0;
    if (port >= (unsigned)joy_dev_count) return 0;

    /* 将 libretro JOYPAD id 映射到我们的 KEY 位掩码 */
    uint32_t mask = 0;
    switch (id) {
        case 0:  mask = RJPAD_UP;      break;  /* UP */
        case 1:  mask = RJPAD_DOWN;    break;  /* DOWN */
        case 2:  mask = RJPAD_LEFT;    break;  /* LEFT */
        case 3:  mask = RJPAD_RIGHT;   break;  /* RIGHT */
        case 4:  mask = RJPAD_A;       break;  /* BUTTON_A */
        case 5:  mask = RJPAD_B;       break;  /* BUTTON_B */
        case 6:  mask = RJPAD_SELECT;  break;  /* SELECT */
        case 7:  mask = RJPAD_START;   break;  /* START */
        case 8:  mask = RJPAD_L;       break;  /* SHOULDER_L */
        case 9:  mask = RJPAD_R;       break;  /* SHOULDER_R */
        case 14: mask = RJPAD_L3;      break;  /* BUTTON_L3 */
        case 15: mask = RJPAD_R3;      break;  /* BUTTON_R3 */
        default: return 0;
    }
    return (joy_key_state[port] & mask) ? 1 : 0;
}

/* 重置所有设备的键位状态（卸载 core 时调用） */
void joy_state_reset(void)
{
    for (int i = 0; i < MAX_DEVICES; i++) joy_key_state[i] = 0;
}
