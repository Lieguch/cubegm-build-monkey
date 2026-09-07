/* ============================================================
 * ui_menu.h — 主菜单 UI 模块（对齐原厂 m_ui / mui_menu）
 * ============================================================
 *
 * 原厂符号：
 *   m_ui @ 0x2b8c4c    - 主菜单初始化
 *   mui_menu @ 0x1b80c - 主菜单渲染 + 输入分发
 *
 * 功能：
 *   1. 加载 menu.raw / type.raw / search.raw / setting.raw / game.raw
 *   2. 分发页面切换（左/右方向键切换 type, 上/下选择游戏）
 *   3. 输出当前选中的 game_list 索引
 * ============================================================ */

#ifndef UI_MENU_H
#define UI_MENU_H

#include <stdbool.h>

/* 主菜单状态 */
typedef struct {
    int   page;           /* UI_PAGE_* */
    int   category_index; /* 游戏分类索引 (000-fba ... 008-2600) */
    int   game_index;     /* 当前分类内游戏索引 */
    bool  active;         /* 主菜单是否活跃 */
} ui_menu_state_t;

/* 初始化主菜单状态。返回 0 成功 */
int  ui_menu_init(void);

/* 主菜单主循环（每次返回 0 = 需要继续, 1 = 请求退出, -1 = 请求运行游戏） */
int  ui_menu_run(void);

/* 获取当前选中的游戏索引（全表全局索引） */
int  ui_menu_selected_game(void);

/* 获取当前状态 */
const ui_menu_state_t *ui_menu_state(void);

#endif /* UI_MENU_H */
