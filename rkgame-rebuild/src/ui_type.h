/* ============================================================
 * ui_type.h — 游戏分类界面（对齐原厂 mui_type @ 0x1a3c8）
 * ============================================================
 *
 * 原厂 mui_type @ 0x1a3c8（4.7 KB）：
 *   显示 type.raw 背景，列出所有游戏分类（000-008）
 *   用户按左右键切换分类，按 A 进入该分类游戏列表
 * ============================================================ */

#ifndef UI_TYPE_H
#define UI_TYPE_H

#include <stdbool.h>

typedef struct {
    bool    open;
    int     cursor;           /* 当前分类索引 (0-8 = 000..008) */
    int     type_count;       /* 分类数量 */
    char    type_names[10][64]; /* 分类名 */

    /* P1-3: 桶内子态（A 进桶后浏览桶内游戏） */
    bool    in_bucket;        /* 当前在分类列表 or 桶内列表 */
    int     bucket_sel;       /* 桶内第 N 个（局部索引） */
    int     pending_launch;   /* 桶内 A 确认后写的全局 game_entry_t 索引（-1 = 无） */
} ui_type_state_t;

int  ui_type_init(void);
void ui_type_open(void);
void ui_type_close(void);
void ui_type_tick(int keycode);
void ui_type_draw(void);
bool ui_type_is_open(void);
int  ui_type_selected(void);
bool ui_type_in_bucket(void);          /* P1-3: 当前是否处于桶内态 */
int  ui_type_pending_launch(void);     /* P1-3: 取出待启动的全局索引（-1 无，取出后自动复位） */
void ui_type_clear_pending(void);      /* P1-3: 显式清除 pending */

#endif /* UI_TYPE_H */
