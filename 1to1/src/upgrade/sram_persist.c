/* ============================================================
 * sram_persist.c —— 目的 2 升级①：SRAM / 记忆卡 / RTC 电池存档（默认不编入 1:1 主链）
 *
 * ── 用户要求（2026-10-22）────────────────────────────────────
 * 「SRAM 需要支持所有"支持无电池存档"或者"记忆卡存档"的游戏，也要支持部分游戏
 *   存档需要电池维持的特殊案例（也是用 SRAM 解决）。」
 * ⇒ 口径落成三条：
 *   ① **不按游戏白名单**：凡 core 报 size>0 就存/读；size==0 静默跳过（＝该 ROM 无存档）
 *   ② **两条通道**：SAVE_RAM(id=0) → `.srm`（PS1 记忆卡也走这条，通常 128KiB）；
 *                   RTC(id=1)      → `.rtc`（"需电池维持时钟"的特殊案例）
 *   ③ **及时落盘**：退出时必写之外，运行中每 ~5s 比对内容指纹，脏才写
 *      —— 真机 SD 直接断电是常态，"只在退出写"等于丢档
 *
 * ── libretro 机制（已核实，非印象）────────────────────────────
 * · `void *retro_get_memory_data(unsigned id)` / `size_t retro_get_memory_size(unsigned id)`
 * · **没有 retro_set_memory**：载入＝frontend 直接 fread 进 get_memory_data 返回的**可写视图**
 * · id: 0=SAVE_RAM  1=RTC  2=SYSTEM_RAM  3=VIDEO_RAM
 * · ★ R251 实测：`get_memory_size` 在 `retro_load_game` **之前恒为 0** ⇒ 必须 load 之后再调
 *
 * ── 与 1:1 的张力 ───────────────────────────────────────────
 * 属"有意偏离"。默认不编入；合入点见 report/L4-evdev-sram-design.md §8.4（各 1 行 ifdef）。
 * ============================================================ */
#include "cgm_upgrade.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <unistd.h>
#include <time.h>

#define RETRO_MEMORY_SAVE_RAM 0u
#define RETRO_MEMORY_RTC      1u

typedef void  *(*get_mem_data_t)(unsigned);
typedef size_t (*get_mem_size_t)(unsigned);

typedef struct {
    unsigned      id;
    const char   *ext;
    const char   *tag;
    size_t        size;
    unsigned char *ptr;
    unsigned long last_sum;
    int           has_sum;
} cgm_channel;

static cgm_channel g_chan[2] = {
    { RETRO_MEMORY_SAVE_RAM, ".srm", "SAVE_RAM", 0, NULL, 0, 0 },
    { RETRO_MEMORY_RTC,      ".rtc", "RTC",      0, NULL, 0, 0 },
};

static void       *g_core;
static get_mem_data_t g_gd;
static get_mem_size_t g_gs;
static time_t      g_last_poll;
static char        g_base[512];   /* 当前存档 base（不含扩展名）*/
static int         g_pending_load;  /* SRAM 延迟建立：load 请求时 size==0 ⇒ 待 poll 每帧补读，直到 size>0 */

/* 256 字节采样的廉价指纹：避免每 5s 全量哈希 128KiB 的成本，同时能发现真实改动 */
static unsigned long cgm_sum(const unsigned char *p, size_t n)
{
    unsigned long s = 2166136261UL;
    size_t i;
    if (p == NULL || n == 0) return 0;
    if (n <= 256) {
        for (i = 0; i < n; i++) s = (s ^ p[i]) * 16777619UL;
    } else {
        size_t step = n / 256;
        for (i = 0; i < n; i += step) s = (s ^ p[i]) * 16777619UL;
        s = (s ^ p[n - 1]) * 16777619UL;
    }
    return s;
}

static void cgm_refresh(void)
{
    int c;
    for (c = 0; c < 2; c++) {
        g_chan[c].size = 0;
        g_chan[c].ptr  = NULL;
        if (g_gs == NULL || g_gd == NULL) continue;
        g_chan[c].size = g_gs(g_chan[c].id);
        if (g_chan[c].size > 0) g_chan[c].ptr = (unsigned char *)g_gd(g_chan[c].id);
        if (g_chan[c].ptr == NULL) g_chan[c].size = 0;
    }
}

int cgm_sram_bind(void *core_handle)
{
    if (core_handle == NULL) return -1;
    if (core_handle == g_core && g_gd != NULL && g_gs != NULL) return 0;  /* 已绑定同句柄 */
    g_core = core_handle;
    g_gd = (get_mem_data_t)dlsym(core_handle, "retro_get_memory_data");
    g_gs = (get_mem_size_t)dlsym(core_handle, "retro_get_memory_size");
    if (g_gd == NULL || g_gs == NULL) {
        g_gd = NULL; g_gs = NULL;
        return -1;
    }
    cgm_refresh();
    g_last_poll = 0;
    return 0;
}

void *cgm_sram_ptr(int idx)
{
    if (idx < 0 || idx > 1) return NULL;
    return g_chan[idx].ptr;
}

size_t cgm_sram_size(int idx)
{
    if (idx < 0 || idx > 1) return 0;
    if (g_chan[idx].size == 0) cgm_refresh();   /* 延迟建立：0 时再查一次 */
    return g_chan[idx].size;
}

void cgm_sram_report(void)
{
    int c;
    cgm_refresh();
    for (c = 0; c < 2; c++)
        printf("[sram] %-8s id=%u size=%zu ptr=%p\n",
               g_chan[c].tag, g_chan[c].id, g_chan[c].size, (void *)g_chan[c].ptr);
}

int cgm_sram_load(const char *base)
{
    int c, got = 0;
    char path[512];
    if (base == NULL) return -1;
    cgm_refresh();
    /* ★ R256：md/SFC 等 core 的 SRAM 是**延迟建立**的 —— retro_load_game 之后立刻查仍为 0，
     *   需等首帧 retro_run 后才变 size>0。此时无可写目标 ⇒ 记 pending，交给每帧 poll 补读。 */
    if (g_chan[0].size == 0 && g_chan[1].size == 0) {
        g_pending_load = 1;         /* SRAM 未建立：交 poll 每帧补读（不设壁钟超时——qemu 下不可靠） */
        return 0;
    }
    g_pending_load = 0;
    for (c = 0; c < 2; c++) {
        FILE *f;
        size_t n;
        if (g_chan[c].size == 0 || g_chan[c].ptr == NULL) continue;   /* 该通道无存档 */
        snprintf(path, sizeof path, "%s%s", base, g_chan[c].ext);
        f = fopen(path, "rb");
        if (f == NULL) continue;
        n = fread(g_chan[c].ptr, 1, g_chan[c].size, f);
        fclose(f);
        if (n == g_chan[c].size) {
            got++;
            g_chan[c].last_sum = cgm_sum(g_chan[c].ptr, g_chan[c].size);  /* 读回后记指纹，避免 poll 立即回写 */
            g_chan[c].has_sum = 1;
            printf("[sram] load %s <- %s (%zu B)\n", g_chan[c].tag, path, n);
        } else {
            printf("[sram] load %s 短读 %zu/%zu（文件与当前 ROM 不匹配？忽略）\n",
                   g_chan[c].tag, n, g_chan[c].size);
        }
    }
    return got;
}

int cgm_sram_flush(const char *base)
{
    int c, wrote = 0;
    char path[512];
    if (base == NULL) return -1;
    /* ★★ R255 根因：md core 的 SRAM 是**延迟建立**的 —— retro_load_game 返回后立刻查
     *   get_memory_size 仍是 0，稍后才变 16384（实测）。所以每次操作前必须重查，
     *   绝不能沿用 bind 时缓存的 size（那会是 0 ⇒ 永远不落盘）。 */
    cgm_refresh();
    for (c = 0; c < 2; c++) {
        FILE *f;
        size_t n;
        int fd;
        if (g_chan[c].size == 0 || g_chan[c].ptr == NULL) continue;
        snprintf(path, sizeof path, "%s%s", base, g_chan[c].ext);
        f = fopen(path, "wb");
        if (f == NULL) {
            printf("[sram] flush %s FAIL fopen %s\n", g_chan[c].tag, path);
            continue;
        }
        n = fwrite(g_chan[c].ptr, 1, g_chan[c].size, f);
        fflush(f);
        fd = fileno(f);
        if (fd >= 0) fsync(fd);                 /* 真机断电场景：必须 fsync */
        fclose(f);
        if (n == g_chan[c].size) {
            wrote++;
            g_chan[c].last_sum = cgm_sum(g_chan[c].ptr, g_chan[c].size);
            g_chan[c].has_sum  = 1;
            printf("[sram] flush %s -> %s (%zu B)\n", g_chan[c].tag, path, n);
        }
    }
    return wrote;
}

int cgm_sram_poll(const char *base)
{
    int c, dirty = 0;
    time_t now;
    if (base == NULL) return 0;
    /* ★ R256：SRAM 延迟建立——只要还有 pending load 就每帧 refresh 查 size，size>0 立即补读 .srm。
     *   · cgm_refresh 只是 4 次缓存函数指针间接调用（非 dlsym），每帧成本可忽略；
     *   · 不设壁钟超时：qemu 下 guest 时间远慢于 wall clock，3s 壁钟窗口会在 SRAM 建立前就过期
     *     （正是 R256 首次验证 .srm 读回 O_RDONLY 一直没出现的原因）。 */
    if (g_pending_load) {
        cgm_refresh();
        if (g_chan[0].size > 0 || g_chan[1].size > 0) {
            g_pending_load = 0;
            (void)cgm_sram_load(base);                           /* 内部会 refresh + 记指纹 */
        }
    }
    now = time(NULL);
    if (g_last_poll != 0 && (now - g_last_poll) < 5) return 0;   /* ~5s 节流（只节流脏检查+写） */
    g_last_poll = now;
    cgm_refresh();                                               /* size 可能刚变（延迟建立） */
    for (c = 0; c < 2; c++) {
        unsigned long s;
        if (g_chan[c].size == 0 || g_chan[c].ptr == NULL) continue;
        s = cgm_sum(g_chan[c].ptr, g_chan[c].size);
        if (!g_chan[c].has_sum || s != g_chan[c].last_sum) {
            dirty = 1;
            break;
        }
    }
    if (!dirty) return 0;
    (void)cgm_sram_flush(base);
    return 1;
}

void cgm_sram_set_base(const char *base)
{
    if (base == NULL) { g_base[0] = 0; return; }
    strncpy(g_base, base, sizeof g_base - 1);
    g_base[sizeof g_base - 1] = 0;
}

int cgm_sram_load_base(void)  { return g_base[0] ? cgm_sram_load(g_base)  : 0; }
int cgm_sram_flush_base(void) { return g_base[0] ? cgm_sram_flush(g_base) : 0; }
int cgm_sram_poll_base(void)  { return g_base[0] ? cgm_sram_poll(g_base)  : 0; }
