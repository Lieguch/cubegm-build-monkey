/* ============================================================
 * rkgame-rebuild — 屏幕调试叠加层（实体机无终端时用）
 * ============================================================
 *
 * 背景：
 *   实体机（RK3036G 掌机）没有终端/指令窗口，rkgame 启动后用户
 *   只能看到屏幕画面。当程序崩溃、卡死、内存泄漏时无法通过终端
 *   查看日志。本模块提供一个由按键组合触发的屏幕叠加层，在画面
 *   底部显示关键诊断信息：
 *     - 当前阶段（最后一条 dbg_probe 埋点）
 *     - FPS / 内存 / 运行时间
 *     - 按键状态（16 位掩码 + 可读列表）
 *     - 最近 N 条日志
 *
 * 触发方式：
 *   长按 SELECT + START 2 秒 → 切换叠加层开关
 *   （与原厂 R36S 通用快捷键一致，但本 rebuild 无"退出"功能，
 *     长按 2s 避免误触）
 *
 * 集成方式：
 *   1. main() 启动时调用 dbg_overlay_init()
 *   2. 菜单循环：每帧调用 dbg_overlay_tick()，若返回 true 则
 *      调用 disp_present() 刷新画面
 *   3. 游戏循环：retro_run() 前后分别调用 dbg_overlay_tick_frame()
 *      和 dbg_overlay_tick()
 *
 * 颜色编码：
 *   与 disp.c 保持一致（XRGB8888 格式，A=0xFF 不透明）
 * ============================================================ */

#ifndef RKGAME_DBG_OVERLAY_H
#define RKGAME_DBG_OVERLAY_H

#include <stdbool.h>

/* 初始化（main() 中调用一次） */
void dbg_overlay_init(void);

/*
 * 每帧调用（菜单循环 + 游戏循环）：
 *   1. 检测 SELECT+START 长按 2s → 切换 overlay
 *   2. 若 overlay 开启，渲染到 framebuffer
 * 返回 true 表示已绘制 overlay，调用者需调用 disp_present()。
 */
bool dbg_overlay_tick(void);

/*
 * 游戏循环专用：每帧调用一次以更新 FPS 计数器。
 * 应在 retro_run() 之后调用。
 */
void dbg_overlay_tick_frame(void);

/* 当前 FPS（0 = 尚未计算） */
int dbg_overlay_fps(void);

/* overlay 是否开启 */
bool dbg_overlay_is_on(void);

/* 触发 overlay 切换（供外部调试用） */
void dbg_overlay_force_toggle(void);

#endif /* RKGAME_DBG_OVERLAY_H */
