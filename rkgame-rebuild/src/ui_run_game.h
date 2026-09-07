/* ============================================================
 * ui_run_game.h — 运行游戏（对齐原厂 mui_run_game）
 * ============================================================
 *
 * 原厂 mui_run_game @ 0x2b7510：
 *   根据当前选中游戏，dlopen 对应 libemu_*.so core，
 *   调用 retro_load_game / retro_run 循环
 * ============================================================ */

#ifndef UI_RUN_GAME_H
#define UI_RUN_GAME_H

#include <stdbool.h>

/* 启动参数 */
typedef struct {
    const char *game_path;   /* 游戏 zip 路径 */
    const char *core_path;   /* libemu_*.so 路径 */
    const char *rom_path;    /* ROM 文件（zip 内） */
    bool        pause_menu_enabled;
} ui_run_game_params_t;

int  ui_run_game_init(void);
int  ui_run_game_start(const ui_run_game_params_t *params);
void ui_run_game_stop(void);
bool ui_run_game_is_running(void);

#endif /* UI_RUN_GAME_H */
