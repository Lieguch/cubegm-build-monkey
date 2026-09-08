/* ============================================================
 * driver_sym.h — driver.so 符号包装层
 * ============================================================
 *
 * 原厂 driver.so 通过 dlsym 暴露的符号：
 *   - InitSound / sound_driver_init / sound_driver_playframe / sound_driver_deinit
 *   - GetDisplay / display_open / display_close
 *   - GetInput / input_init / input_poll
 *   - 等等（原厂 driver.so 40 KB，闭源）
 *
 * 本模块：
 *   - 集中管理所有 driver.so 符号句柄
 *   - 提供带空检查/日志/降级 的包装访问函数
 *   - 支持 fallback（driver.so 不可用时返回 no-op）
 * ============================================================ */

#ifndef DRIVER_SYM_H
#define DRIVER_SYM_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* driver.so dlopen 句柄（由 main.c 设置） */
extern void *driver_handle;

/* 使用 HDMI 输出标志（原厂 USE_HDMI_OUT = 1） */
#define USE_HDMI_OUT 1

/* ---- 已注册符号 ---- */

typedef void (*driver_sound_init_t)(int use_hdmi, void *callback, int mode);
typedef void (*driver_sound_play_t)(void);
typedef void (*driver_sound_deinit_t)(void);
typedef void (*driver_display_open_t)(int mode);
typedef void (*driver_display_close_t)(void);
typedef int  (*driver_display_draw_t)(const void *buf, int w, int h);
typedef void (*driver_input_init_t)(void);
typedef void (*driver_input_poll_t)(unsigned *keys);

/* 全局符号注册表 */
typedef struct {
    driver_sound_init_t     sound_init;
    driver_sound_play_t     sound_playframe;
    driver_sound_deinit_t   sound_deinit;
    driver_display_open_t   display_open;
    driver_display_close_t  display_close;
    driver_display_draw_t   display_draw;
    driver_input_init_t     input_init;
    driver_input_poll_t     input_poll;
} driver_symbols_t;

extern driver_symbols_t g_driver_sym;

/* 初始化：从 driver_handle dlsym 全部符号 */
int  driver_sym_init(void *handle);

/* 释放 */
void driver_sym_free(void);

/* 是否至少有一个符号可用 */
bool driver_sym_is_ready(void);

/* 包装访问（带空检查 + 日志 + 降级） */
void driver_sound_init_safe(int use_hdmi, void *cb, int mode);
void driver_sound_play_safe(void);
void driver_sound_deinit_safe(void);
void driver_display_open_safe(int mode);
void driver_display_close_safe(void);
int  driver_display_draw_safe(const void *buf, int w, int h);
void driver_input_init_safe(void);
void driver_input_poll_safe(unsigned *keys);

/* 诊断 */
void driver_sym_report(void);

#endif /* DRIVER_SYM_H */
