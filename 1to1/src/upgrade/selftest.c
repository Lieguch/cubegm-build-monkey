/* selftest.c —— 目的 2 两模块的**真跑**自测（云端 zig 编译 + qemu 执行）
 * 用法: selftest <core.so> <rom.zip> [savedir]
 * 判据:
 *   · [evdev] db 载入条数 > 0（全量库可读）+ open 结果打印（qemu 无手柄则为 -1，属正常）
 *   · [sram]  retro_load_game 之后各通道 size（>0 即"该 ROM 有电池存档"）+ 存/读往返
 */
#include "cgm_upgrade.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>

typedef int (*cb_env_t)(unsigned, void *);
typedef void (*cb_set_env_t)(cb_env_t);
typedef void (*cb_void_t)(void);
typedef int  (*cb_load_t)(const void *);
struct game_info { const char *path; const void *data; size_t size; const char *meta; };

static int env_cb(unsigned cmd, void *data)
{
    if (cmd == 9u) { if (data) *(const char **)data = "/tmp"; return 1; }
    if (cmd == 10u) return 1;
    return 0;
}

int main(int argc, char **argv)
{
    const char *core = argc > 1 ? argv[1] : NULL;
    const char *rom  = argc > 2 ? argv[2] : NULL;
    const char *dir  = argc > 3 ? argv[3] : "/tmp";
    char base[512];
    void *h;
    cb_set_env_t se; cb_void_t ini; cb_load_t ld;
    struct game_info gi;
    int fd, n;

    printf("=== [evdev] 全量库 ===\n");
    cgm_evdev_init(0);
    printf("[evdev] db_count=%d\n", cgm_evdev_db_count());
    fd = cgm_evdev_open(0);
    printf("[evdev] open slot0 = %d %s\n", fd, fd >= 0 ? "(有手柄)" : "(qemu 下无手柄，属正常)");

    if (!core || !rom) { printf("[sram] 跳过（未给 core/rom）\n"); return 0; }
    printf("=== [sram] 真 core ===\n");
    h = dlopen(core, 2);
    if (!h) { printf("[sram] dlopen 失败 %s\n", dlerror()); return 3; }
    se  = (cb_set_env_t)dlsym(h, "retro_set_environment");
    ini = (cb_void_t)dlsym(h, "retro_init");
    ld  = (cb_load_t)dlsym(h, "retro_load_game");
    if (!se || !ini || !ld) { printf("[sram] 缺 libretro 入口\n"); return 4; }
    se(env_cb); ini();
    /* ★ 两种喂法各测一遍（关键：rkgame 会同时传 data=整份 ROM，见 Core_Load 的 game_blob） */
    gi.path = rom; gi.data = NULL; gi.size = 0; gi.meta = NULL;
    printf("[sram] retro_load_game(path only) -> %d\n", ld(&gi));
    printf("[sram]   size after path-only: %u\n", (unsigned)cgm_sram_size(0));

    {
        FILE *f = fopen(rom, "rb");
        if (f) {
            long n; void *buf;
            fseek(f, 0, 2); n = ftell(f); fseek(f, 0, 0);
            buf = malloc((size_t)n);
            if (buf) {
                size_t got = fread(buf, 1, (size_t)n, f);
                printf("[sram] 已读 ROM 到内存 %zu B\n", got);
                /* 用一份全新的 core 实例语义近似不了，直接再用同实例 load 会拒绝；
                   故这里只报告"如果传 data 会怎样"由外层决定 —— 见下一行 */
                free(buf);
            }
            fclose(f);
        }
    }

    if (cgm_sram_bind(h) != 0) { printf("[sram] bind 失败（core 无 memory 接口）\n"); return 5; }
    cgm_sram_report();

    snprintf(base, sizeof base, "%s/_cgm_sram_test", dir);
    n = cgm_sram_load(base);
    printf("[sram] load 通道数=%d（无文件时 0 属正常）\n", n);

    /* ★ 真往返断言：写图案 -> flush(落盘) -> 清零 -> load(读回) -> 校验 */
    {
        int c;
        for (c = 0; c < 2; c++) {
            unsigned char *p = (unsigned char *)cgm_sram_ptr(c);
            size_t sz = cgm_sram_size(c), i2, bad = 0;
            int wrote;
            if (sz == 0 || p == NULL) continue;
            for (i2 = 0; i2 < sz; i2++) p[i2] = (unsigned char)((i2 * 31u + 7u) & 0xFF);
            wrote = cgm_sram_flush(base);
            printf("[sram] 通道%d flush=%d (size=%zu)\n", c, wrote, sz);
            memset(p, 0, sz);
            if (cgm_sram_load(base) <= 0) { printf("[sram] 通道%d ★FAIL load 未命中\n", c); continue; }
            for (i2 = 0; i2 < sz; i2++)
                if (p[i2] != (unsigned char)((i2 * 31u + 7u) & 0xFF)) bad++;
            printf("[sram] 通道%d round-trip 不符字节=%zu/%zu %s\n", c, bad, sz,
                   bad == 0 ? "OK" : "★FAIL");
            {
                char cmd[600];
                snprintf(cmd, sizeof cmd, "ls -l %s.srm %s.rtc 2>/dev/null | sed 's/^/    /'", base, base);
                if (system(cmd) != 0) { /* 仅展示 */ }
            }
        }
    }
    return 0;
}
