/* ============================================================
 * rkgame-rebuild — core.h
 *
 * libretro core 加载器接口声明。
 * 实现见 core.c。
 * ============================================================ */

#ifndef CORE_H
#define CORE_H

#ifdef __cplusplus
extern "C" {
#endif

/* 加载 core 并启动 ROM */
int core_load(const char *rom_path, const char *core_name);

/* 卸载当前 core */
void core_unload(void);

/* 运行一帧 */
int core_run(void);

#ifdef __cplusplus
}
#endif

#endif /* CORE_H */
