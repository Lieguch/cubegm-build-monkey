/* ui_run_game.c — 运行游戏 */

#include "ui_run_game.h"
#include "core.h"
#include "game_list.h"
#include "rkgame.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

static bool s_running = false;
static ui_run_game_params_t s_params;

int ui_run_game_init(void) { return 0; }

int ui_run_game_start(const ui_run_game_params_t *params)
{
    if (!params || !params->rom_path) {
        RKLOG_E("ui_run_game: invalid params");
        return -1;
    }
    s_params = *params;
    s_running = true;
    RKLOG_I("ui_run_game: core=%s rom=%s", s_params.core_path ? s_params.core_path : "(auto)", s_params.rom_path);

    /* 启动 core */
    const char *core = s_params.core_path ? s_params.core_path : NULL;
    int rc = core_load(s_params.rom_path, core);
    if (rc != 0) {
        s_running = false;
        RKLOG_E("ui_run_game: core_load failed rc=%d", rc);
        return rc;
    }
    return 0;
}

void ui_run_game_stop(void) { s_running = false; }
bool ui_run_game_is_running(void) { return s_running; }

void ui_run_game_tick(int keycode) { (void)keycode; }

void ui_run_game_draw(void)
{
    /* 游戏运行时不绘制菜单 */
    (void)s_running;
}
