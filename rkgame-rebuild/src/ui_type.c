/* ============================================================
 * ui_type.c — 游戏分类界面实现（对齐原厂 mui_type @ 0x1a3c8）
 * ============================================================
 *
 * 分类定义（对齐原厂 SD 卡 <NNN> 目录）：
 *   000 — 街机 (Arcade/FBA)
 *   001 — FC/NES
 *   002 — SFC/SMC
 *   003 — MD/GG
 *   004 — GBA
 *   005 — NES
 *   006 — GB/GBC
 *   007 — PS1
 *   008 — Atari 2600
 * ============================================================ */

#include "ui_type.h"
#include "rkgame.h"
#include "ui.h"
#include "font.h"
#include "debug.h"
#include "game_list.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

static ui_type_state_t s_type;

/* 分类定义（对齐原厂目录） */
static const char *g_type_names[] = {
    "000 - Arcade/FBA",
    "001 - FC/NES",
    "002 - SFC/SMC",
    "003 - MD/GG",
    "004 - GBA",
    "005 - NES",
    "006 - GB/GBC",
    "007 - PS1",
    "008 - Atari 2600"
};

#define TYPE_COUNT (sizeof(g_type_names) / sizeof(g_type_names[0]))

int ui_type_init(void)
{
    memset(&s_type, 0, sizeof(s_type));
    s_type.type_count = TYPE_COUNT;
    s_type.cursor = 0;
    for (int i = 0; i < TYPE_COUNT && i < 10; i++) {
        snprintf(s_type.type_names[i], 64, "%s", g_type_names[i]);
    }
    RKLOG_I("ui_type_init: %d categories loaded", TYPE_COUNT);
    return 0;
}

void ui_type_open(void)  { s_type.open = true; s_type.cursor = 0; }
void ui_type_close(void) { s_type.open = false; }
bool ui_type_is_open(void) { return s_type.open; }
int  ui_type_selected(void) { return s_type.cursor; }

void ui_type_tick(int keycode)
{
    if (!s_type.open) return;

    /* P1-1/P1-3: keycode 采用**原厂事件码 bitmask**（buttontoi@0x151e4）
     *   A=0x2000 B=0x4000 UP=0x10 DOWN=0x40 LEFT=0x80 RIGHT=0x20
     *   SELECT=0x001 START=0x008
     * 用位掩码 & 判断（多个事件码可 OR 同时出现），main.c 传入
     * joy_factory_key_state_all() 的原始值。 */
    #define FK_UP      0x10
    #define FK_DOWN    0x40
    #define FK_LEFT    0x80
    #define FK_RIGHT   0x20
    #define FK_A       0x2000
    #define FK_B       0x4000
    #define FK_SELECT  0x001

    if (s_type.in_bucket) {
        /* ---- P1-3: 桶内态（浏览当前分类 000-008 的游戏） ---- */
        int dir = s_type.cursor;   /* 0-8 = 000..008 */
        int cnt = game_list_dir_count(dir);
        if (cnt <= 0) {
            s_type.in_bucket = false;
            s_type.pending_launch = -1;
            RKLOG_I("ui_type: bucket %03d empty, back to category", dir);
            return;
        }
        if (keycode & FK_UP) {
            s_type.bucket_sel = (s_type.bucket_sel - 1 + cnt) % cnt;
        } else if (keycode & FK_DOWN) {
            s_type.bucket_sel = (s_type.bucket_sel + 1) % cnt;
        } else if (keycode & FK_A) {
            s_type.pending_launch = s_type.bucket_sel;
            RKLOG_I("ui_type: launch pending in bucket %03d local=%d",
                    dir, s_type.bucket_sel);
        } else if ((keycode & FK_B) || (keycode & FK_SELECT)) {
            s_type.in_bucket = false;
            s_type.pending_launch = -1;
            RKLOG_I("ui_type: back to category from bucket %03d", dir);
        }
        return;
    }

    /* ---- 分类列表态（9 桶 000-008） ---- */
    if ((keycode & FK_UP) || (keycode & FK_LEFT)) {
        s_type.cursor = (s_type.cursor - 1 + s_type.type_count) % s_type.type_count;
        RKLOG_I("ui_type: cursor -> %d", s_type.cursor);
    } else if ((keycode & FK_DOWN) || (keycode & FK_RIGHT)) {
        s_type.cursor = (s_type.cursor + 1) % s_type.type_count;
        RKLOG_I("ui_type: cursor -> %d", s_type.cursor);
    } else if (keycode & FK_A) {
        /* P1-3: A 进桶浏览该分类游戏 */
        if (game_list_dir_count(s_type.cursor) > 0) {
            s_type.in_bucket = true;
            s_type.bucket_sel = 0;
            s_type.pending_launch = -1;
            RKLOG_I("ui_type: enter bucket %03d", s_type.cursor);
        } else {
            RKLOG_I("ui_type: bucket %03d empty, stay in category", s_type.cursor);
        }
    } else if ((keycode & FK_B) || (keycode & FK_SELECT)) {
        s_type.open = false;
        s_type.in_bucket = false;
        s_type.pending_launch = -1;
        RKLOG_I("ui_type: closed");
    }
}

/* P1-3: 桶内态查询 */
bool ui_type_in_bucket(void) { return s_type.in_bucket; }

int ui_type_pending_launch(void)
{
    int p = s_type.pending_launch;
    s_type.pending_launch = -1;   /* 取出后自动复位 */
    return p;
}

void ui_type_clear_pending(void)
{
    s_type.pending_launch = -1;
}

void ui_type_draw(void)
{
    if (!s_type.open) return;

    /* 绘制 type.raw 背景（若已加载） */
    if (ui_is_ready()) {
        ui_draw_page(UI_PAGE_TYPE);
    }

    /* ---- P1-3: 桶内态（浏览当前分类 000-008 的游戏） ---- */
    if (s_type.in_bucket) {
        int dir = s_type.cursor;
        int cnt = game_list_dir_count(dir);
        if (font_is_ready()) {
            char dir_label[20];
            snprintf(dir_label, sizeof(dir_label), "%03d - %s",
                     dir, (dir < 9 && g_type_names[dir]) ? g_type_names[dir] : "?");
            int y = 60;
            /* 标题 = 桶目录名 */
            font_draw_text(dir_label, 20, y, 0x00ff00);
            y += 30;
            if (cnt <= 0) {
                font_draw_text("(empty)", 20, y, 0x888888);
                y += 28;
            }
            /* 桶内游戏列表（窗口 8 条，跟随 bucket_sel 滚动） */
            int win = 8;
            int start = (s_type.bucket_sel / win) * win;
            for (int i = start; i < start + win && i < cnt; i++) {
                int gidx = game_list_dir_index(dir, i);
                if (gidx < 0) continue;
                const game_entry_t *ge = game_list_get(gidx);
                if (!ge) continue;
                char line[GL_NAME_LEN + 8];
                const char *prefix = (i == s_type.bucket_sel) ? " > " : "   ";
                snprintf(line, sizeof(line), "%s%s", prefix, ge->name[0] ? ge->name : ge->path);
                font_draw_text(line, 20, y + (i - start) * 24,
                               (i == s_type.bucket_sel) ? 0x00ff00 : 0xffffff);
            }
            font_draw_text("A=Play  B=Back  Up/Down=Browse",
                           20, y + win * 24 + 10, 0x888888);
        }
        return;
    }

    /* ---- 分类列表态（9 桶 000-008） ---- */
    if (font_is_ready()) {
        const char *path = work_path;
        int y = 60;

        /* 标题 */
        font_draw_text("Game Categories", 20, y, 0x00ff00);
        y += 30;

        /* 当前分类目录 */
        char dir[20];
        snprintf(dir, sizeof(dir), "%s%03d", path, s_type.cursor);
        font_draw_text(dir, 20, y, 0xffffff);
        y += 30;

        /* 分类列表 */
        for (int i = 0; i < s_type.type_count; i++) {
            const char *prefix = (i == s_type.cursor) ? " > " : "   ";
            char line[80];
            snprintf(line, sizeof(line), "%s%s", prefix, s_type.type_names[i]);
            font_draw_text(line, 20, y + i * 28,
                           (i == s_type.cursor) ? 0x00ff00 : 0xffffff);
        }

        /* 提示 */
        font_draw_text("A=Enter  B=Back  Up/Down=Browse",
                       20, y + s_type.type_count * 28 + 10, 0x888888);
    }
}
