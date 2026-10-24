/* ============================================================
 * evdev_gamepad.c —— 目的 2 升级②：evdev 自适应手柄（**全量库、自动匹配、零手工**）
 *
 * ── 用户要求（2026-10-22）────────────────────────────────────
 * 「把整个全量驱动都放到原厂对应的驱动文件夹中，绝对不能采用每次新增每次新加的模式。
 *   用户水平有限，手柄种类繁多，不可能设计手动添加驱动文件这种反人类操作。」
 * ⇒ 口径：
 *   ① 全量库随卡发布：`/sdcard/cubegm/controller_db.txt`
 *      = RetroArch 官方 `udev/` autoconfig 全量合并表（**426 条**，377 条带 vid/pid），
 *      由 `tools/build_controller_db.py` 从官方 `autoconfig.zip` 生成；
 *   ② 设备端**自动匹配**：(vid,pid) 精确 → device name 子串回退；命中即用，无任何手工步骤；
 *   ③ 匹配不到也不残废：走"兜底映射"（BTN_SOUTH/EAST/NORTH/WEST + hat0/轴 的顺序映射）。
 *
 * ── 为什么不用原厂 `joystick.zip` ─────────────────────────────
 * 原厂表按 `VID_PID` 命名、每设备一个 24 项定长表，**新增设备必须手工加一条**
 * ⇒ 与本条用户要求直接冲突。原厂 zip 保持只读，本模块另读 `controller_db.txt`。
 *
 * ── 上游数据格式（已核实 docs.libretro.com/guides/controller-autoconfiguration）
 *   input_vendor_id / input_product_id 是**十进制**；`input_b_btn="N"` 里的 N 是
 *   **该设备按键的序号**（按 keycode 升序枚举，非 keycode 本身）；
 *   方向键两种：hat（`input_up_btn="h0up"`）或轴（`input_up_axis="-1"`）；轴写 `+N`/`-N`。
 *
 * ── RetroPad → rkgame 位域（**按位置映射**，与 SNES 布局一致）
 *   b(South)→A(0x2000)  a(East)→B(0x4000)  y(West)→X(0x1000)  x(North)→Y(0x8000)
 *   l→TL1(0x400)  r→TR1(0x800)  l2→TL2(0x100)  r2→TR2(0x200)
 *   select→0x1  start→0x8  up→0x10  down→0x40  left→0x80  right→0x20
 *   （rkgame 侧位定义来自 buttontoi.c，逐位核对）
 *
 * ── 与 1:1 的张力 ───────────────────────────────────────────
 * 属"有意偏离"，默认不编入；合入点见 report/L4-evdev-sram-design.md §8.4。
 * ============================================================ */
#include "cgm_upgrade.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <dirent.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/input.h>

/* ★ userspace 的 <linux/input.h> 不提供内核私有宏（R250 首次编译即 5 个 error） */
#ifndef LONG_BITS
#define LONG_BITS (sizeof(long) * 8u)
#endif
#ifndef BITS_TO_LONGS
#define BITS_TO_LONGS(nr) (((nr) + LONG_BITS - 1u) / LONG_BITS)
#endif

#define CGM_DB_PATH   "/sdcard/cubegm/controller_db.txt"
#define CGM_MAX_PROF  640
#define CGM_NAME_MAX  96

/* rkgame 位域（buttontoi.c 逐位核对） */
#define RK_SELECT 0x0001u
#define RK_START  0x0008u
#define RK_UP     0x0010u
#define RK_RIGHT  0x0020u
#define RK_DOWN   0x0040u
#define RK_LEFT   0x0080u
#define RK_TL2    0x0100u
#define RK_TR2    0x0200u
#define RK_TL1    0x0400u
#define RK_TR1    0x0800u
#define RK_X      0x1000u
#define RK_A      0x2000u
#define RK_B      0x4000u
#define RK_Y      0x8000u

typedef struct {
    unsigned short vid, pid;      /* 0 = 无 */
    char  name[CGM_NAME_MAX];
    int   btn[16];                /* 索引：0=b 1=a 2=y 3=x 4=l 5=r 6=l2 7=r2 8=l3 9=r3 10=sel 11=st；-1 无 */
    int   hat_up, hat_dn, hat_lf, hat_rt;   /* 0=无；1=hat0 */
    int   ax_up, ax_dn, ax_lf, ax_rt;       /* 带符号：+N/-N；0=无 */
} cgm_prof;

static cgm_prof g_prof[CGM_MAX_PROF];
static int      g_prof_n;
static int      g_db_loaded;

static int g_fd[4] = { -1, -1, -1, -1 };

static unsigned int g_key[4];
static int g_btn_code[4][32];     /* 序号 → keycode */
static int g_btn_n[4];
static const cgm_prof *g_match[4];

/* ---------------- 数据库 ---------------- */

static unsigned short hex4(const char *s)
{
    unsigned v = 0; int i;
    if (s == NULL) return 0;
    for (i = 0; i < 4 && s[i]; i++) {
        char c = s[i];
        v <<= 4;
        if (c >= '0' && c <= '9') v |= (unsigned)(c - '0');
        else if (c >= 'a' && c <= 'f') v |= (unsigned)(c - 'a' + 10);
        else if (c >= 'A' && c <= 'F') v |= (unsigned)(c - 'A' + 10);
        else return 0;
    }
    return (unsigned short)v;
}

/* "%20" → 空格（生成器只编码空格与 tab） */
static void dec_name(const char *src, char *dst, size_t cap)
{
    size_t o = 0;
    while (*src && o + 1 < cap) {
        if (src[0] == '%' && src[1] == '2' && src[2] == '0') { dst[o++] = ' '; src += 3; }
        else if (src[0] == '%' && src[1] == '0' && src[2] == '9') { dst[o++] = '\t'; src += 3; }
        else dst[o++] = *src++;
    }
    dst[o] = 0;
}

static int key_slot(const char *k)
{
    if (!strcmp(k, "b")) return 0;
    if (!strcmp(k, "a")) return 1;
    if (!strcmp(k, "y")) return 2;
    if (!strcmp(k, "x")) return 3;
    if (!strcmp(k, "l")) return 4;
    if (!strcmp(k, "r")) return 5;
    if (!strcmp(k, "l2")) return 6;
    if (!strcmp(k, "r2")) return 7;
    if (!strcmp(k, "l3")) return 8;
    if (!strcmp(k, "r3")) return 9;
    if (!strcmp(k, "sel")) return 10;
    if (!strcmp(k, "st")) return 11;
    return -1;
}

static int load_db(const char *path)
{
    FILE *f;
    char line[512];
    int n = 0;
    if (g_db_loaded) return g_prof_n;
    g_db_loaded = 1;
    f = fopen(path, "r");
    if (f == NULL) {
        printf("[evdev] db 打开失败 %s（将只用兜底映射）\n", path);
        return 0;
    }
    while (fgets(line, sizeof line, f) && n < CGM_MAX_PROF) {
        char *save = NULL, *tok;
        cgm_prof *p = &g_prof[n];
        if (line[0] == '#' || line[0] == '\n' || line[0] == '\r') continue;
        memset(p, 0, sizeof *p);
        p->btn[0] = p->btn[1] = p->btn[2] = p->btn[3] = -1;
        p->btn[4] = p->btn[5] = p->btn[6] = p->btn[7] = -1;
        p->btn[8] = p->btn[9] = p->btn[10] = p->btn[11] = -1;
        tok = strtok_r(line, " \r\n", &save);
        if (tok == NULL) continue;
        p->vid = hex4(tok);
        tok = strtok_r(NULL, " \r\n", &save);
        if (tok == NULL) continue;
        p->pid = hex4(tok);
        tok = strtok_r(NULL, " \r\n", &save);
        if (tok == NULL) continue;
        dec_name(tok, p->name, sizeof p->name);
        while ((tok = strtok_r(NULL, " \r\n", &save)) != NULL) {
            char *eq = strchr(tok, '=');
            int s;
            if (eq == NULL) continue;
            *eq = 0;
            if (!strcmp(tok, "up")) { if (!strcmp(eq + 1, "h0up")) p->hat_up = 1; }
            else if (!strcmp(tok, "dn")) { if (!strcmp(eq + 1, "h0down")) p->hat_dn = 1; }
            else if (!strcmp(tok, "lf")) { if (!strcmp(eq + 1, "h0left")) p->hat_lf = 1; }
            else if (!strcmp(tok, "rt")) { if (!strcmp(eq + 1, "h0right")) p->hat_rt = 1; }
            else if (!strcmp(tok, "up_ax")) p->ax_up = atoi(eq + 1);
            else if (!strcmp(tok, "dn_ax")) p->ax_dn = atoi(eq + 1);
            else if (!strcmp(tok, "lf_ax")) p->ax_lf = atoi(eq + 1);
            else if (!strcmp(tok, "rt_ax")) p->ax_rt = atoi(eq + 1);
            else if ((s = key_slot(tok)) >= 0) p->btn[s] = atoi(eq + 1);
        }
        n++;
    }
    fclose(f);
    g_prof_n = n;
    printf("[evdev] db 载入 %d 条 profile <- %s\n", n, path);
    return n;
}

/* ---------------- 设备探测 / 匹配 ---------------- */

static int has_bit(const unsigned long *bits, int b)
{
    return (int)((bits[b / (int)LONG_BITS] >> (b % (int)LONG_BITS)) & 1UL);
}

/* 枚举该设备按键的**序号→keycode**（按 keycode 升序，与 RetroArch udev 语义一致） */
static void build_btn_order(int slot, const unsigned long *keyb)
{
    int c, k = 0;
    g_btn_n[slot] = 0;
    for (c = BTN_MISC; c <= KEY_MAX && k < 32; c++) {
        if (has_bit(keyb, c)) g_btn_code[slot][k++] = c;
    }
    g_btn_n[slot] = k;
}

static int is_gamepad(const unsigned long *keyb, const unsigned long *absb)
{
    if (has_bit(keyb, BTN_SOUTH) || has_bit(keyb, BTN_GAMEPAD)) return 1;
    if (has_bit(absb, ABS_X) && has_bit(keyb, BTN_TRIGGER)) return 1;
    return 0;
}

int cgm_evdev_init(int slot)
{
    if (slot < 0 || slot > 3) return -1;
    load_db(getenv("CGM_CTRL_DB") ? getenv("CGM_CTRL_DB") : CGM_DB_PATH);
    return 0;
}

static const cgm_prof *match_prof(unsigned short vid, unsigned short pid, const char *name)
{
    int i;
    for (i = 0; i < g_prof_n; i++)
        if (g_prof[i].vid == vid && g_prof[i].pid == pid && vid && pid) return &g_prof[i];
    if (name && name[0]) {
        for (i = 0; i < g_prof_n; i++)
            if (g_prof[i].name[0] && strstr(name, g_prof[i].name)) return &g_prof[i];
        for (i = 0; i < g_prof_n; i++)
            if (g_prof[i].name[0] && strstr(g_prof[i].name, name)) return &g_prof[i];
    }
    return NULL;
}

int cgm_evdev_open(int slot)
{
    DIR *d;
    struct dirent *e;
    if (slot < 0 || slot > 3) return -1;
    if (g_fd[slot] >= 0) return g_fd[slot];
    /* ★★★ R272（回退到第 6 轮形态）：这里曾有"失败退避 1 s"的早退。
     *   第 6 轮（无退避、无去重）实测：tag=K=549、用户证实"按键无迟滞"；
     *   第 7/9 轮（有退避+去重）实测：tag=K=0。用户明确要求"在第 6 轮基础上只修间歇重启"，
     *   因此把这段改动整体撤回，恢复第 6 轮行为。 */
    /* ★ R257：懒加载 controller_db.txt（幂等）。此前 load_db 只在 cgm_evdev_init 里被调，
     *   而主链 ReadUSBJoy 只调 cgm_evdev_poll→cgm_evdev_open，从不调 cgm_evdev_init
     *   ⇒ 426 条 profile 从未装载，match_prof 恒返回 NULL，只剩兜底映射（全量库形同虚设）。 */
    load_db(getenv("CGM_CTRL_DB") ? getenv("CGM_CTRL_DB") : CGM_DB_PATH);
    d = opendir("/dev/input");
    if (d == NULL) {
        printf("[evdev] /dev/input 打不开（errno=%d）\n", errno);
        return -1;
    }
    while ((e = readdir(d)) != NULL) {
        char path[128], name[256];
        unsigned long keyb[BITS_TO_LONGS(KEY_MAX + 1)];
        unsigned long absb[BITS_TO_LONGS(ABS_MAX + 1)];
        struct input_id id;
        int fd, got = 0;
        const cgm_prof *pr;
        if (strncmp(e->d_name, "event", 5) != 0) continue;
        snprintf(path, sizeof path, "/dev/input/%s", e->d_name);
        fd = open(path, O_RDONLY | O_NONBLOCK);
        if (fd < 0) continue;
        memset(keyb, 0, sizeof keyb);
        memset(absb, 0, sizeof absb);
        memset(name, 0, sizeof name);
        if (ioctl(fd, EVIOCGBIT(EV_KEY, sizeof keyb), keyb) < 0) got = -1;
        if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof absb), absb) < 0) got = -1;
        if (ioctl(fd, EVIOCGNAME(sizeof name - 1), name) < 0) got = -1;
        memset(&id, 0, sizeof id);
        if (ioctl(fd, EVIOCGID, &id) < 0) got = -1;
        if (got < 0 || !is_gamepad(keyb, absb)) { close(fd); continue; }
        /* ★★★ R272（回退到第 6 轮形态）：这里曾有"同一台设备只分给一个 slot"的去重，
         *   导致 slot1..3 打不开、只能走工厂 jsdev 路径。第 6 轮没有这段，四个 slot 各自
         *   打开同一台设备、各自有条事件队列 —— 实测按键正常。故撤回。
         *   代价（已知）：下拉时四个队列各拿一份事件，可能出现 0x10|0x20 之类的组合值；
         *   但那是第 6 轮"能用"的状态，先恢复可用，再单独评估是否值得改。 */
        pr = match_prof(id.vendor, id.product, name);
        g_match[slot] = pr;
        build_btn_order(slot, keyb);
        g_fd[slot] = fd;
        g_key[slot] = 0;
        printf("[evdev] slot%d 打开 %s  name='%s' vid:pid=%04x:%04x btn_n=%d profile=%s\n",
               slot, path, name, id.vendor, id.product, g_btn_n[slot],
               pr ? pr->name : "(兜底映射)");
        closedir(d);
        return fd;
    }
    closedir(d);
    return -1;   /* ★ R272：不再设退避时间戳（随去重一并撤回） */
}

int cgm_evdev_db_count(void) { return g_prof_n; }

/* ★ R257：供 ReadUSBJoy 判定"evdev 是否就绪"。
 *   真机有 /dev/input/event* ⇒ ready=1 走全量库；qemu/精简内核无 event* ⇒ ready=0
 *   ⇒ 上层回退 joydev 原逻辑，绝不失灵。内部会懒加载 db + 尝试打开（幂等）。 */
int cgm_evdev_ready(int slot)
{
    if (slot < 0 || slot > 3) return 0;
    if (g_fd[slot] < 0) (void)cgm_evdev_open(slot);
    return g_fd[slot] >= 0;
}

const char *cgm_evdev_profile_name(int slot)
{
    if (slot < 0 || slot > 3) return NULL;
    return g_match[slot] ? g_match[slot]->name : NULL;
}

/* ---------------- 事件 → rkgame 位域 ---------------- */

/* 兜底映射：BTN_SOUTH→A, EAST→B, NORTH→Y, WEST→X；hat0 走方向 */
static unsigned int map_fallback(const struct input_event *ev)
{
    unsigned int bit = 0;
    if (ev->type == EV_KEY && ev->value == 1) {
        switch (ev->code) {
        case BTN_SOUTH: bit = RK_A; break;
        case BTN_EAST:  bit = RK_B; break;
        case BTN_NORTH: bit = RK_Y; break;
        case BTN_WEST:  bit = RK_X; break;
        case BTN_TL:    bit = RK_TL1; break;
        case BTN_TR:    bit = RK_TR1; break;
        case BTN_SELECT:bit = RK_SELECT; break;
        case BTN_START: bit = RK_START; break;
        default: break;
        }
    } else if (ev->type == EV_ABS) {
        if (ev->code == ABS_HAT0Y) bit = (ev->value < 0) ? RK_UP : ((ev->value > 0) ? RK_DOWN : 0);
        else if (ev->code == ABS_HAT0X) bit = (ev->value < 0) ? RK_LEFT : ((ev->value > 0) ? RK_RIGHT : 0);
    }
    return bit;
}

static int code_of_index(int slot, int idx)
{
    if (idx < 0 || idx >= g_btn_n[slot]) return -1;
    return g_btn_code[slot][idx];
}

unsigned int cgm_evdev_poll(int slot)
{
    struct input_event ev;
    ssize_t n;
    if (slot < 0 || slot > 3) return 0;
    if (g_fd[slot] < 0) { (void)cgm_evdev_open(slot); return (int)g_key[slot]; }
    n = read(g_fd[slot], &ev, sizeof ev);
    if (n != (ssize_t)sizeof ev) {
        if (n <= 0 && (errno == ENODEV || errno == EIO)) { close(g_fd[slot]); g_fd[slot] = -1; }
        return (int)g_key[slot];
    }
    {
        const cgm_prof *p = g_match[slot];
        unsigned int hit = 0;
        if (p != NULL) {
            int i;
            for (i = 0; i < 12; i++) {
                int code = code_of_index(slot, p->btn[i]);
                if (code < 0) continue;
                if (ev.type == EV_KEY && ev.code == (unsigned short)code) {
                    switch (i) {
                    case 0: hit = RK_A; break; case 1: hit = RK_B; break;
                    case 2: hit = RK_X; break; case 3: hit = RK_Y; break;
                    case 4: hit = RK_TL1; break; case 5: hit = RK_TR1; break;
                    case 6: hit = RK_TL2; break; case 7: hit = RK_TR2; break;
                    case 10: hit = RK_SELECT; break; case 11: hit = RK_START; break;
                    default: break;
                    }
                }
            }
            if (hit == 0 && ev.type == EV_ABS) {
                if (p->hat_up || p->hat_dn || p->hat_lf || p->hat_rt) {
                    if (ev.code == ABS_HAT0Y) hit = (ev.value < 0) ? RK_UP : ((ev.value > 0) ? RK_DOWN : 0);
                    else if (ev.code == ABS_HAT0X) hit = (ev.value < 0) ? RK_LEFT : ((ev.value > 0) ? RK_RIGHT : 0);
                } else if (p->ax_up || p->ax_dn || p->ax_lf || p->ax_rt) {
                    if (ev.code == (unsigned short)ABS_X || ev.code == 1) {
                        if (p->ax_up && ev.value < 0) hit = RK_UP;
                        if (p->ax_dn && ev.value > 0) hit = RK_DOWN;
                        if (p->ax_lf && ev.value < 0) hit = RK_LEFT;
                        if (p->ax_rt && ev.value > 0) hit = RK_RIGHT;
                    }
                }
            }
        }
        if (hit == 0) hit = map_fallback(&ev);
        if (hit != 0) {
            if (ev.value != 0) g_key[slot] |= hit;
            else g_key[slot] &= ~hit;
        }
    }
    return (int)g_key[slot];
}
