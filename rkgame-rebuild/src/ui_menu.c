/* ============================================================
 * ui_menu.c — 主菜单 UI 实现（对齐原厂 m_ui + mui_menu）
 * ============================================================
 *
 * 原厂 mui_menu 关键逻辑（Ghidra 0x1b80c）：
 *   1. 显示 menu.raw 背景
 *   2. 显示当前 type.raw 对应的分类
 *   3. 显示当前 game.raw 缩略图 + 游戏名
 *   4. 处理输入：
 *      - A 键：确认 → mui_run_game
 *      - 左/右：切换 category (000-fba ... 008-2600)
 *      - 上/下：切换当前分类内游戏
 *      - 菜单键：跳转 setting.raw
 *      - 搜索键：跳转 search.raw
 * ============================================================ */

#include "ui_menu.h"
#include "ui.h"
#include "ui_zip.h"
#include "game_list.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

/* ---- 全局状态 ---- */
static ui_menu_state_t s_menu = {
    .page = 0,
    .category_index = 0,
    .game_index = 0,
    .active = false,
};

int ui_menu_init(void)
{
    s_menu.category_index = 0;
    s_menu.game_index = 0;
    s_menu.active = true;
    s_menu.page = UI_PAGE_MENU;
    RKLOG_I("ui_menu_init: category=0 game=0");
    return 0;
}

const ui_menu_state_t *ui_menu_state(void) { return &s_menu; }

int ui_menu_selected_game(void)
{
    /* 返回 category 内的 game_index；调用方负责转成全局索引 */
    return s_menu.game_index;
}

int ui_menu_run(void)
{
    /* 主循环由 main.c 的 game_loop 负责调度；
     * 本函数只做一次渲染并返回（供外部轮询调用） */
    if (!ui_is_ready()) {
        return 0;
    }
    ui_draw_menu();
    return 0;
}
