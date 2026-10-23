/* ============================================================
 * cgm_upgrade.h —— 目的 2 两项升级的统一 API（SRAM 记忆卡 + evdev 自适应手柄）
 *
 * ★ 与 1:1 复刻的关系：这两项是**有意偏离**。默认**不参与**主链：
 *   只在定义 `CGM_ENABLE_SRAM` / `CGM_ENABLE_EVDEV` 时才编进来，
 *   未定义时产物与当前 1:1 逐字节一致（见 report/L4-evdev-sram-design.md §5/§8.4）。
 * ============================================================ */
#ifndef CGM_UPGRADE_H
#define CGM_UPGRADE_H

#include <stddef.h>   /* size_t */

#ifdef __cplusplus
extern "C" {
#endif

/* ---------- ① SRAM / 记忆卡 / RTC（电池存档） ---------- */
/* 语义（libretro Memory Interface，已核实）：
 *   id=0 RETRO_MEMORY_SAVE_RAM  —— 电池存档 SRAM；PS1 的**记忆卡**也走这一路（通常 128KiB）
 *   id=1 RETRO_MEMORY_RTC       —— 需要"电池维持时钟"的特殊案例（如某些卡带 RTC）
 * 设计口径（用户要求）：
 *   · **不按游戏白名单**：凡 core 报 size>0 就走"存/读"，size==0 静默跳过（＝该 ROM 无存档）
 *   · **及时落盘**：除退出时落盘外，运行中每 ~5s 检查一次内容指纹（脏才写），
 *     避免"断电就全丢"（真机 SD 直接断电很常见）
 *   · 文件后缀：`.srm`（save ram）/ `.rtc`（rtc），与 1:1 的 `.sav`（zlib state）严格区分
 */

/* 绑定 core 句柄（dlopen 后的 handle）。可重复调用；返回 0 成功。 */
int cgm_sram_bind(void *core_handle);

/* 从 base（不含扩展名，如 "/sdcard/cubegm/saves/000/1941"）读入 .srm/.rtc。
 * 返回：读入的通道数（0 = 无文件或无 SRAM），负 = 错误。 */
int cgm_sram_load(const char *base);

/* 立即写盘（无条件，供"存档动作刚发生"时调用）。返回写入的通道数。 */
int cgm_sram_flush(const char *base);

/* 记住"当前存档 base"（不含扩展名）；后续 *_base 系列用它，免得上层重复拼路径。 */
void cgm_sram_set_base(const char *base);
int  cgm_sram_load_base(void);
int  cgm_sram_flush_base(void);

/* 帧级轮询：内部按 ~5s 节流 + 脏页指纹比较，脏才写。返回本次是否写了盘。 */
int cgm_sram_poll(const char *base);
int cgm_sram_poll_base(void);

/* 取通道可写视图与大小（idx: 0=SAVE_RAM 1=RTC）。自测/上层落盘用。 */
void  *cgm_sram_ptr(int idx);
size_t cgm_sram_size(int idx);

/* 诊断：打印各通道 size（0 也算有效信息）。 */
void cgm_sram_report(void);

/* ---------- ② evdev 自适应手柄（全量库，自动匹配） ---------- */
/* 设计口径（用户要求）：
 *   · **全量内置**：读 `/sdcard/cubegm/controller_db.txt`（RetroArch 官方 udev
 *     autoconfig 全量合并表，426 条，由 tools/build_controller_db.py 生成）
 *   · **自动匹配**：按 (vid,pid) → 名字子串 两级；新柄无需任何手工步骤
 *   · 输出仍是 rkgame 原有 `joy_key` 位域，故上层（菜单/游戏）无需改动
 */

/* 打开并缓存数据库；slot 为手柄槽位（0..3）。返回 0 成功，负 = 失败。 */
int cgm_evdev_init(int slot);

/* 尝试打开/重开一台手柄（枚举 /dev/input/event*，按能力判定）。
 * 返回 fd（>=0）或负值（-1 无设备）。 */
int cgm_evdev_open(int slot);

/* 读一个事件并返回该槽位最新的 joy_key 位域（与 rkgame 的 bit 定义一致）。
 * 无事件时返回上一次的值（与 ReadUSBJoy 语义对齐）。 */
unsigned int cgm_evdev_poll(int slot);

/* 已载入的 profile 条数（自测/诊断用）。 */
int cgm_evdev_db_count(void);

/* event* 设备是否已就绪（懒加载 db + 尝试打开）；0 = 未就绪（上层应回退 joydev）。 */
int cgm_evdev_ready(int slot);

/* 当前槽位匹配到的 profile 名（用于日志/诊断），无则返回 NULL。 */
const char *cgm_evdev_profile_name(int slot);

#ifdef __cplusplus
}
#endif
#endif /* CGM_UPGRADE_H */
