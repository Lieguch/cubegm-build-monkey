/* ============================================================
 * ui_dispatcher.h — UI 主循环调度器（对齐原厂 m_ui @ 0x2ce6c）
 * ============================================================
 *
 * 原厂 m_ui 调度逻辑：
 *   while (1) {
 *       poll_input();
 *       switch (current_page) {
 *           case MENU:    mui_menu();
 *           case SEARCH:  mui_search();
 *           case TYPE:    mui_type();
 *           case SETTING: mui_setting();
 *           ...
 *       }
 *   }
 *
 * 本实现：在 main_menu 的 while(1) 循环中，根据 gl_* 状态
 * 调度到对应的 mui_* 模块的 open/tick/draw。
 * ============================================================ */

#ifndef UI_DISPATCHER_H
#define UI_DISPATCHER_H

#include <stdbool.h>

/* UI 页面状态（与 gl_* 布尔值对应） */
typedef enum {
    UI_PAGE_MAIN = 0,
    UI_PAGE_LIST,
    UI_PAGE_SEARCH,
    UI_PAGE_TYPE,
    UI_PAGE_SETTING,
    UI_PAGE_BROWSER,
    UI_PAGE_COUNT
} ui_page_state_t;

/* 按键状态结构（供 dispatcher 使用） */
typedef struct {
    int keys[26];       /* 当前帧按键 */
    int prev_keys[26];  /* 上帧按键 */
} ui_keys_t;

/* 边缘检测：本帧按下且上帧未按下 */
#define UI_KEY_EDGE(k, idx) ((k)->keys[idx] && !(k)->prev_keys[idx])

/* 初始化调度器 */
int  m_ui_init(void);

/* 调度一轮 UI 更新：根据状态调用对应 mui_* 的 tick */
void m_ui_dispatch(int keycode, ui_page_state_t page);

/* 调度一轮 UI 绘制：根据状态调用对应 mui_* 的 draw */
void m_ui_draw(ui_page_state_t page);

/* 获取当前页面状态（从 gl_* 布尔值推断） */
ui_page_state_t m_ui_current_page(bool showing, bool searching,
                                   bool setting, bool typing, bool browser);

/* 主 UI 循环入口（替代 main_menu） */
int  m_ui(void);

#endif /* UI_DISPATCHER_H */
