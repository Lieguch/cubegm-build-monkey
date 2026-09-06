/* ============================================================
 * heartbeat.h — 进程存活诊断与 icube launcher 交互探测
 * ============================================================
 *
 * 背景：
 *   icube v1.3 launcher 用 fork+execl 拉起 rkgame，然后基于 waitpid
 *   等待子进程。strings 显示 icube 还调用了 shmget/shmat/shmdt/
 *   shmctl(IPC_RMID)，以及 killall rkgame。真机日志显示每 ~7 秒重启
 *   一次 —— 而 main_menu() 的 while(1) 理论上不会自己退出。因此重启
 *   是外部 kill 触发（可能是 launcher 的 shm 心跳超时看门狗）。
 *
 * 本模块提供三项诊断能力（不写入 shm，避免破坏 icube 预期）：
 *   1. hb_install_signal_handlers()  — 记录被 kill 时的信号编号
 *   2. hb_init() / hb_tick()         — 心跳文件（work_path/heartbeat），
 *                                       真机跑一次后可用 stat 判断进程
 *                                       是否真的活着
 *   3. hb_detect_icube_shm()         — 遍历 shmid，只读 IPC_STAT 元
 *                                       数据，确认 icube 是否创建了
 *                                       SysV shm 段（用于判断 kill
 *                                       机制是否为 shm 心跳超时）
 *
 * 注意：不做 shm 写入。写入猜测格式风险大于收益，如果 icube 期望特
 *      定消息内容，写错反而可能触发更多 kill。先拿诊断信息。
 * ============================================================ */

#ifndef HEARTBEAT_H
#define HEARTBEAT_H

void hb_init(const char *path);
void hb_tick(void);
void hb_shutdown(void);

void hb_install_signal_handlers(void);
int  hb_get_last_signal(void);

void hb_detect_icube_shm(void);

/* icube shm 协议 (key=0x4d2, size=8, IPC_CREAT|IPC_EXCL|0666)
 * shm[0] = 1  (存活标志)
 * shm[1] = 计数器/时间戳 (icube 每 7-8 秒检查是否更新)
 */
void hb_shm_attach(void);
void hb_shm_heartbeat(void);
void hb_shm_detach(void);

#endif /* HEARTBEAT_H */
