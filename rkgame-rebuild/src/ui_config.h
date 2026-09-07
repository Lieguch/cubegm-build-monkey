/* ============================================================
 * ui_config.h — 配置加载（对齐原厂 mui_LoadConfig + mui_LoadSetting）
 * ============================================================
 *
 * 原厂符号：
 *   mui_LoadConfig   @ 0x17e28 — 读取 cores/config.xml 核心注册表
 *   mui_LoadSetting  @ 0x171f8 — 读取 setting.xml 全局设置（6 项）
 *
 * 本实现使用 mxml（lib/mxml）解析 XML。
 * ============================================================ */

#ifndef UI_CONFIG_H
#define UI_CONFIG_H

/* 加载 setting.xml 到 g_cfg。返回 0 成功 */
int mui_LoadSetting(const char *path);

/* 加载 cores/config.xml 核心注册表。返回 0 成功 */
int mui_LoadConfig(const char *path);

#endif /* UI_CONFIG_H */
