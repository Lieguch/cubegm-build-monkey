/* ============================================================
 * ui.h — UI 资源加载与渲染（P1.3）
 * ============================================================
 *
 * 工厂实证（Ghidra mui_LoadUIResource @ 0x17dac）：
 *   1. 构造路径: work_path + "/" + selected_ui_zip
 *   2. OpenZipU → FindZipItemA("menu.raw") → UnzipItem → malloc'd buffer
 *   3. .raw 格式: [4B pixel_offset][2B width][2B height][RGB565 data]
 *   4. 工厂用 mui_DispBlock 做精灵渲染（本实现简化为背景+文字）
 *
 * UI 包选择：setting.xml 中 <ui filename="ui_en.zip" ...>
 *            按 gamelist="1" 标记的包为当前使用包
 * ============================================================ */

#ifndef UI_H
#define UI_H

#include <stdint.h>
#include <stdbool.h>

/* 前向声明（完整定义在 ui_zip.h） */
typedef struct ui_zip ui_zip_t;

/* ---- UI 页面枚举 ---- */
enum ui_page {
    UI_PAGE_MENU    = 0,   /* menu.raw — 主菜单背景 */
    UI_PAGE_TYPE    = 1,   /* type.raw — 游戏分类页 */
    UI_PAGE_SEARCH  = 2,   /* search.raw — 搜索页 */
    UI_PAGE_SETTING = 3,   /* setting.raw — 设置页 */
    UI_PAGE_GAME    = 4,   /* game.raw — 游戏详情页 */
    UI_PAGE_COUNT   = 5
};

/* ---- 单个 UI 页面数据 ---- */
typedef struct {
    unsigned char *data;          /* 原始 buffer（含头） */
    int            pixel_offset;  /* 像素数据偏移 */
    int            width;
    int            height;
    bool           loaded;
} ui_page_t;

/* 初始化 UI 系统：加载 selected ui_*.zip + 所有 .raw 页面。
 * 返回 0 成功，-1 失败（调用方应回退到纯色+5x7 菜单）。 */
int  ui_init(void);

/* 关闭 UI，释放资源 */
void ui_shutdown(void);

/* UI 是否可用（至少 menu.raw 已加载） */
bool ui_is_ready(void);

/* 渲染指定页面。page = UI_PAGE_*。 */
void ui_draw_page(int page);

/* 渲染完整菜单（menu.raw 背景 + 文字 + 提示）。
 * 等同于 ui_draw_page(UI_PAGE_MENU)。 */
void ui_draw_menu(void);

/* 获取当前页面的像素缓冲区（RGB565，不含头）。
 * 返回 NULL 表示未加载。 */
const uint8_t *ui_page_pixels(int page);

/* 获取当前页面尺寸。 */
int ui_page_width(int page);
int ui_page_height(int page);

/* 加载指定 .raw 文件到内存。返回 malloc'd 缓冲区（含头），或 NULL。
 * 调用方负责 free。 */
unsigned char *ui_load_raw(const char *name, int *out_w, int *out_h,
                           int *out_pixel_offset);

/* 从指定 zip 加载 .raw（用于 root.dat 背景等外部 zip 源）。
 * 返回 malloc'd 缓冲区（含头），或 NULL。 */
unsigned char *ui_load_raw_from_zip(ui_zip_t *z, const char *name,
                                    int *out_w, int *out_h, int *out_pixel_offset);

#endif /* UI_H */
