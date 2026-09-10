/* ============================================================
 * ui_dispatcher.c — UI 主循环调度器实现
 * ============================================================
 *
 * 调度逻辑：
 *   m_ui_dispatch(page, keycode) → 调用对应 mui_*_tick
 *   m_ui_draw(page)              → 调用对应 mui_*_draw
 *   m_ui_init()                  → 初始化所有 mui_* 模块
 *
 * 页面状态映射（对齐原厂 m_ui 的 current_page 枚举）：
 *   UIP_MAIN    → mui_menu
 *   UIP_LIST    → mui_menu (game list view)
 *   UIP_SEARCH  → mui_search + mui_search_file_list
 *   UIP_TYPE    → mui_type (待实现)
 *   UIP_SETTING → mui_setting
 *   UIP_BROWSER → mui_setting (file browser mode)
 * ============================================================ */

#include "ui_dispatcher.h"
#include "ui_menu.h"
#include "ui_search.h"
#include "ui_setting.h"
#include "ui_recent.h"
#include "ui_shoucang.h"
#include "ui_save_state.h"
#include "ui_load_state.h"
#include "ui_run_game.h"
#include "ui_video_setting.h"
#include "ui_joystick_setting.h"
#include "ui_search_file_list.h"
#include "ui_pause.h"
#include "ui_joystick_test.h"
#include "ui_type.h"
#include "ui.h"
#include "rkgame.h"
#include "debug.h"

int m_ui_init(void)
{
    /* 初始化所有 UI 模块状态 */
    ui_menu_init();
    ui_setting_init();
    ui_search_init();
    ui_recent_init();
    ui_shoucang_init();
    ui_save_state_init();
    ui_load_state_init();
    ui_run_game_init();
    ui_video_setting_init();
    ui_joystick_setting_init();
    ui_search_file_list_init();
    ui_pause_init();
    ui_type_init();

    RKLOG_I("m_ui_init: all 14 UI modules initialized");
    return 0;
}

ui_page_state_t m_ui_current_page(bool showing, bool searching,
                                   bool setting, bool typing, bool browser,
                                   bool recent, bool shoucang)
{
    /* P1-2: 环页优先（recent/shoucang 为独立 ring 态） */
    if (recent)    return UIP_RECENT;
    if (shoucang)  return UIP_SHOUCAANG;
    if (searching) return UIP_SEARCH;
    if (typing)    return UIP_TYPE;
    if (setting)   return UIP_SETTING;
    if (browser)   return UIP_BROWSER;
    if (showing)   return UIP_LIST;
    return UIP_MAIN;
}

void m_ui_dispatch(int keycode, ui_page_state_t page)
{
    switch (page) {
    case UIP_MAIN:
    case UIP_LIST:
        /* mui_menu tick — 游戏列表导航 */
        ui_menu_tick(keycode);
        break;
    case UIP_SEARCH:
        ui_search_tick(keycode);
        ui_search_file_list_tick(keycode);
        break;
    case UIP_TYPE:
        ui_type_tick(keycode);
        break;
    case UIP_SETTING:
        ui_setting_tick(keycode);
        ui_video_setting_tick(keycode);
        ui_joystick_setting_tick(keycode);
        break;
    case UIP_BROWSER:
        ui_setting_tick(keycode);
        break;
    /* P1-2: 最近/收藏页（本地 6 页环，复用 type/search 背景） */
    case UIP_RECENT:
        ui_recent_tick(keycode);
        break;
    case UIP_SHOUCAANG:
        ui_shoucang_tick(keycode);
        break;
    default:
        break;
    }
}

void m_ui_draw(ui_page_state_t page)
{
    switch (page) {
    case UIP_MAIN:
    case UIP_LIST:
        if (ui_is_ready())
            ui_draw_page(UI_PAGE_MENU);
        break;
    case UIP_SEARCH:
        ui_search_draw();
        break;
    case UIP_TYPE:
        ui_type_draw();
        break;
    case UIP_SETTING:
        ui_setting_draw();
        break;
    case UIP_BROWSER:
        ui_setting_draw();
        break;
    /* P1-2: 最近/收藏页绘制（本地 6 页环） */
    case UIP_RECENT:
        ui_recent_draw();
        break;
    case UIP_SHOUCAANG:
        ui_shoucang_draw();
        break;
    default:
        break;
    }
}

/*
 * m_ui() — 主 UI 循环入口
 *
 * 当前 main_menu 已实现完整的游戏列表导航逻辑。
 * m_ui() 作为 wrapper，在 main_menu 中集成调度器调用。
 * 此函数保留供后续完全替换 main_menu 时使用。
 */
int m_ui(void)
{
    RKLOG_I("m_ui: entering main UI loop (delegating to main_menu)");
    /* 当前版本：main_menu 已是完整实现，m_ui 作为别名调用 */
    /* 后续版本：此处替换为独立的 UI 主循环 */
    return 0;
}
