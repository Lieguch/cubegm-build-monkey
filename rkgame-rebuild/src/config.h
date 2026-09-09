/* ============================================================
 * config.h — 配置管理系统接口
 * ============================================================ */

#ifndef CONFIG_H
#define CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

/* 初始化配置系统 */
int config_init(void);

/* 从文件加载配置 */
int config_load(const char *path);

/* 保存配置到文件 */
int config_save(const char *path);

/* 查找配置项索引 */
int config_find(const char *name);

/* 获取配置值 */
const char *config_get(const char *name);

/* 设置配置值 */
int config_set(const char *name, const char *value);

/* 获取整数值 */
int config_get_int(const char *name, int default_val);

/* 获取布尔值 */
int config_get_bool(const char *name, int default_val);

/* 同步配置值到全局结构体 */
void config_update_struct(void);

/* 原厂兼容入口：加载 setting.xml 并同步到 g_cfg */
int GetConfig(void);

#ifdef __cplusplus
}
#endif

#endif /* CONFIG_H */