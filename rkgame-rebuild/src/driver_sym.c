/* ============================================================
 * driver_sym.c — driver.so 符号包装层
 * ============================================================ */

#include "driver_sym.h"
#include "debug.h"
#include "rkgame.h"
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

void *driver_handle = NULL;

driver_symbols_t g_driver_sym = {0};

static void *get_sym(const char *name)
{
    if (!driver_handle) return NULL;
    void *p = dlsym(driver_handle, name);
    if (!p) {
        const char *err = dlerror();
        if (err) {
            LOG("driver_sym: %s not found (%s)", name, err);
        }
    }
    return p;
}

int driver_sym_init(void *handle)
{
    if (!handle) {
        ERR("driver_sym_init: no handle");
        return -1;
    }
    driver_handle = handle;

    memset(&g_driver_sym, 0, sizeof(g_driver_sym));

    g_driver_sym.sound_init      = (driver_sound_init_t)     get_sym("sound_driver_init");
    g_driver_sym.sound_playframe = (driver_sound_play_t)     get_sym("sound_driver_playframe");
    g_driver_sym.sound_deinit    = (driver_sound_deinit_t)   get_sym("sound_driver_deinit");

    g_driver_sym.display_open    = (driver_display_open_t)   get_sym("display_open");
    g_driver_sym.display_close   = (driver_display_close_t)  get_sym("display_close");
    g_driver_sym.display_draw    = (driver_display_draw_t)   get_sym("display_draw");

    g_driver_sym.input_init      = (driver_input_init_t)     get_sym("input_init");
    g_driver_sym.input_poll      = (driver_input_poll_t)     get_sym("input_poll");

    driver_sym_report();
    return 0;
}

void driver_sym_free(void)
{
    memset(&g_driver_sym, 0, sizeof(g_driver_sym));
    driver_handle = NULL;
}

bool driver_sym_is_ready(void)
{
    return g_driver_sym.sound_init ||
           g_driver_sym.sound_playframe ||
           g_driver_sym.display_open ||
           g_driver_sym.input_init;
}

/* ---- 包装访问 ---- */

void driver_sound_init_safe(int use_hdmi, void *cb, int mode)
{
    if (!g_driver_sym.sound_init) {
        LOG("driver_sound_init_safe: no sound_init (qemu/no-op)");
        return;
    }
    g_driver_sym.sound_init(use_hdmi, cb, mode);
}

void driver_sound_play_safe(void)
{
    if (!g_driver_sym.sound_playframe) return;
    g_driver_sym.sound_playframe();
}

void driver_sound_deinit_safe(void)
{
    if (!g_driver_sym.sound_deinit) return;
    g_driver_sym.sound_deinit();
}

void driver_display_open_safe(int mode)
{
    if (!g_driver_sym.display_open) {
        LOG("driver_display_open_safe: no display_open (log-only)");
        return;
    }
    g_driver_sym.display_open(mode);
}

void driver_display_close_safe(void)
{
    if (!g_driver_sym.display_close) return;
    g_driver_sym.display_close();
}

int driver_display_draw_safe(const void *buf, int w, int h)
{
    if (!g_driver_sym.display_draw) return -1;
    return g_driver_sym.display_draw(buf, w, h);
}

void driver_input_init_safe(void)
{
    if (!g_driver_sym.input_init) {
        LOG("driver_input_init_safe: no input_init (evdev fallback)");
        return;
    }
    g_driver_sym.input_init();
}

void driver_input_poll_safe(unsigned *keys)
{
    if (!g_driver_sym.input_poll || !keys) return;
    g_driver_sym.input_poll(keys);
}

void driver_sym_report(void)
{
    LOG("driver_sym_report: handle=%p", driver_handle);
    LOG("  sound_init      = %s", g_driver_sym.sound_init      ? "OK" : "N/A");
    LOG("  sound_playframe = %s", g_driver_sym.sound_playframe ? "OK" : "N/A");
    LOG("  sound_deinit    = %s", g_driver_sym.sound_deinit    ? "OK" : "N/A");
    LOG("  display_open    = %s", g_driver_sym.display_open    ? "OK" : "N/A");
    LOG("  display_close   = %s", g_driver_sym.display_close   ? "OK" : "N/A");
    LOG("  display_draw    = %s", g_driver_sym.display_draw    ? "OK" : "N/A");
    LOG("  input_init      = %s", g_driver_sym.input_init      ? "OK" : "N/A");
    LOG("  input_poll      = %s", g_driver_sym.input_poll      ? "OK" : "N/A");
}
