/* ============================================================
 * ui_run_game.c — 运行游戏（对齐原厂 mui_run_game @ 0x2b7510）
 * ============================================================ */

#include "ui_run_game.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

static bool s_running = false;

int ui_run_game_init(void) { return 0; }

int ui_run_game_start(const ui_run_game_params_t *params)
{
    if (!params || !params->core_path || !params->rom_path) {
        RKLOG_E("ui_run_game: invalid params");
        return -1;
    }
    /* 简化：交由 core.c 的 game_loop 接管；这里只置位 */
    s_running = true;
    RKLOG_I("ui_run_game: core=%s rom=%s", params->core_path, params->rom_path);
    return 0;
}

void ui_run_game_stop(void) { s_running = false; }
bool ui_run_game_is_running(void) { return s_running; }
