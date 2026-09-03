/* ============================================================
 * rkgame-rebuild — 调试日志模块
 * ============================================================
 *
 * 目标：
 *   1. 每次崩溃自动 dump 寄存器状态到 /sdcard/cubegm/rkgame.crash.log
 *   2. 在每个初始化阶段埋点，崩溃时能精确知道卡在哪一步
 *   3. 运行日志写入 /sdcard/cubegm/rkgame.log，崩溃时拷贝最后 30 条
 *
 * 设计要点：
 *   - 崩溃信号处理函数只能使用 syscall-safe 函数（write/open/close/fstat）
 *   - 不使用 printf/malloc/snprintf（在信号上下文中不安全）
 *   - 所有格式化使用内联 hex 转换 + 固定长度字符串拼接
 *   - 日志 fd 在 main() 之前就打开，确保最早期崩溃也能记录
 *   - 使用 writev() 批量写入减少 IO 次数
 * ============================================================ */

#ifndef RKGAME_DEBUG_H
#define RKGAME_DEBUG_H

#include <stdint.h>
#include <stdbool.h>

/* ---- 日志级别 ---- */
#define DBG_LEVEL_OFF   0
#define DBG_LEVEL_INFO  1
#define DBG_LEVEL_DEBUG 2
#define DBG_LEVEL_TRACE 3

/* ---- 阶段枚举（用于 dbg_probe） ---- */
#define DBGP_STAGE(name)  DBG_ST_##name
enum {
    DBG_ST_ENTRY,           /* _rkgame_start 入口 */
    DBG_ST_MAIN_BEGIN,      /* main() 开始 */
    DBG_ST_GET_PATH,        /* get_executable_path */
    DBG_ST_CONFIG_LOAD,     /* config_load */
    DBG_ST_DISP_INIT,       /* disp_init */
    DBG_ST_AUDIO_INIT,      /* audio_init */
    DBG_ST_SRAM_INIT,       /* sram_init */
    DBG_ST_JOY_INIT,        /* joy_init */
    DBG_ST_CORE_DLOPEN,     /* dlopen(core) */
    DBG_ST_CORE_DLSYM,      /* dlsym 批量解析 */
    DBG_ST_CORE_INIT,       /* retro_init() */
    DBG_ST_CORE_LOADGAME,   /* retro_load_game() */
    DBG_ST_CORE_RUN,        /* 进入核心主循环 */
    DBG_ST_CORE_UNLOAD,     /* core_unload */
    DBG_ST_SHUTDOWN,        /* 清理阶段 */
    DBG_ST_END,             /* main() 正常退出 */
};

/* ---- 初始化 ---- */
/* 在 entry.c _rkgame_start() 中，main() 之前调用。
 * 打开日志文件、安装崩溃信号处理器、记录入口点标记。 */
void dbg_init(void);

/* ---- 阶段探针 ---- */
/* 在每个初始化阶段开始时调用。崩溃后查看 crash.log 中最后一个 DBGP 标记即可定位问题阶段。
 * stage_id 使用 enum 中的 DBG_ST_* 常量。 */
void dbg_probe(int stage_id);

/* ---- 通用日志 ---- */
/* 写入到日志 fd。fmt 使用 printf 格式。
 * 在正常代码路径中调用（不在信号处理函数中）。 */
void dbg_log(int level, const char *fmt, ...);

/* ---- 便捷宏 ---- */
#define DBG_I(fmt, ...) dbg_log(DBG_LEVEL_INFO, fmt, ##__VA_ARGS__)
#define DBG_D(fmt, ...) dbg_log(DBG_LEVEL_DEBUG, fmt, ##__VA_ARGS__)
#define DBG_T(fmt, ...) dbg_log(DBG_LEVEL_TRACE, fmt, ##__VA_ARGS__)
#define DBGP(stage)     dbg_probe(DBG_ST_##stage)

/* ---- 关闭 ---- */
void dbg_close(void);

#endif /* RKGAME_DEBUG_H */
