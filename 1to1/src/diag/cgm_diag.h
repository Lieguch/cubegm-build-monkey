/* ============================================================
 * cgm_diag.h —— 设备端诊断仪（**只编进诊断版 rkgame，不进交付版**）
 *
 * 为什么必须做成"编进自己"而不是 LD_PRELOAD
 * ---------------------------------------------------------------
 * 设备是游戏盒子（HDMI + 扬声器，**无命令行**），启动链
 *   U-Boot → kernel → init → rcS → S80icube → exec /sdcard/cubegm/icube → rkgame
 * 全部是**原厂文件（红线：一律不动）** ⇒ 我们**没有任何地方能注入 LD_PRELOAD / 环境变量**。
 * 因此诊断能力只能：
 *   ① 链接期 `-finstrument-functions`（函数级轨迹，零源码改动）
 *   ② 链接期 `-Wl,--wrap=<libc 符号>`（调用级轨迹，零源码改动）
 *   ③ 本文件提供上面两者的实现 + 崩溃捕获 + 心跳
 * 三条都**不需要设备上有 shell、不需要环境变量**。
 *
 * 输出（全部落在 SD 卡，插卡到 PC 即可取回）
 * ---------------------------------------------------------------
 *   /sdcard/cubegm/_diag/BEGIN.txt        本次运行的启动横幅（唯一标识 + 配置 + 时钟）
 *   /sdcard/cubegm/_diag/env.txt          环境快照（environ/cmdline/uname/auxv/meminfo）
 *   /sdcard/cubegm/_diag/maps.start.txt   启动时 /proc/self/maps（离线符号化的**必需**输入）
 *   /sdcard/cubegm/_diag/trace.log        事件流（生命周期/文件/ioctl/线程/dlopen/信号）
 *   /sdcard/cubegm/_diag/frames.bin       函数轨迹（环形缓冲；崩溃/退出时**全量** dump）
 *   /sdcard/cubegm/_diag/frames.snap.bin  函数轨迹**周期快照**（卡死/断电也能拿到最近历史）
 *   /sdcard/cubegm/_diag/crash.txt        崩溃报告（siginfo + 全寄存器 + 回溯 + 栈扫描 + maps）
 *   /sdcard/cubegm/_diag/heartbeat.txt    心跳（区分"卡死"与"崩溃"；含 utime/stime）
 *   /sdcard/cubegm/_diag/summary.txt      周期汇总（打开文件数 / 读写字节 / 调用计数 Top）
 *   /sdcard/cubegm/_diag/cfg.ini          【可选，我们自己放】级别与开关
 *
 * 纪律（本项目已登记的仪器失效教训，逐条照办）
 * ---------------------------------------------------------------
 *   · 诊断自身**一律走 syscall()**，绝不调用可能被 --wrap 重定向的 libc 函数 ⇒ 不存在递归。
 *   · 关键地址/量一律 **8 位十六进制**（`%08x` 语义），避免"6 位恒 0 命中"那类反向结论。
 *   · 每个"0 命中"都能被阳性对照校验：BEGIN.txt 里写明本轮应出现的 tag。
 *   · 环形缓冲 + 周期快照 = **即使卡死/断电，也不丢最近历史**。
 * ============================================================ */
#ifndef CGM_DIAG_H
#define CGM_DIAG_H

#include <stdint.h>

/* ---------- 配置 ---------- */
#define CGM_DIAG_ROOT        "/sdcard/cubegm/_diag"
#define CGM_RING_FRAMES      (1u << 16)   /* 65536 帧 × 12 B = 768 KB（.bss） */
#define CGM_LOG_MAX_BYTES    (24u << 20)  /* trace.log 超过 24 MB 就轮转一次 */
#define CGM_SNAP_MS          5000u        /* 周期快照 / 心跳间隔（毫秒） */
#define CGM_SUMMARY_MS       15000u       /* 周期汇总间隔 */

/* 级别：cfg.ini 的 `level = N`；文件缺失 ⇒ 默认 2 */
#define CGM_LVL_OFF     0   /* 全关（只留崩溃报告） */
#define CGM_LVL_CORE    1   /* 生命周期 / 信号 / 崩溃 / 文件 open-close / dlopen / 线程 */
#define CGM_LVL_IO      2   /* ★默认：+ read/write/lseek 的偏移与长度 + ioctl 全部 */
#define CGM_LVL_FULL    3   /* + 内容 hex(前 64B) + malloc/free 明细 */

/* 帧：12 字节定长，小端，便于离线用 Python struct 直接解 */
typedef struct {
    uint32_t addr;   /* 被进入/退出的函数地址（产物 VMA，非 PIE ⇒ 固定） */
    uint32_t meta;   /* bit0=1 表示 exit；bit8..23 = 调用深度 */
    uint32_t ms;     /* 进程单调毫秒（粗采样） */
} cgm_frame_t;

/* ---------- 对外接口（被 --wrap / 构造器调用） ---------- */
void cgm_diag_boot(const char *how);                  /* 最早初始化（幂等） */
void cgm_frame_enter(uint32_t addr, uint32_t caller); /* -finstrument-functions */
void cgm_frame_exit(uint32_t addr);
void cgm_lifecycle(const char *ev, int code);         /* 退出/异常等 */
int  cgm_lvl(void);
int  cgm_want(int need);

#endif /* CGM_DIAG_H */
