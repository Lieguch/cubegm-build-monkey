/* ============================================================
 * heartbeat.c — 进程存活诊断与 icube launcher 交互探测
 * ============================================================ */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <signal.h>
#include <errno.h>
#include <time.h>
#include <sys/shm.h>
#include <sys/ipc.h>
#include <sys/types.h>

#include "rkgame.h"
#include "debug.h"
#include "heartbeat.h"

static int  hb_fd = -1;
static char hb_path[512];
static volatile sig_atomic_t last_signal = 0;

/*
 * 信号处理器：SA_RESTART + 只置标志位。
 *
 * 不主动 exit，让主循环继续 —— 这样即便 icube 用 SIGTERM 试探，我们
 * 也不会被中断；SA_RESTART 会自动重启被中断的 select/nanosleep。
 * 如果 icube 之后用 SIGKILL，我们无法捕获，但至少 SIGTERM 被记录
 * 到 hb_get_last_signal()，主循环下次醒来时能写日志。
 */
static void sig_handler(int sig)
{
    last_signal = (int)sig;
}

void hb_install_signal_handlers(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = sig_handler;
    sigemptyset(&sa.sa_mask);
    sa.sa_flags = SA_RESTART;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT,  &sa, NULL);
    sigaction(SIGALRM, &sa, NULL);
    sigaction(SIGCHLD, &sa, NULL);
    LOG("heartbeat: signal handlers installed "
        "(SIGTERM/SIGINT/SIGALRM/SIGCHLD, SA_RESTART)");
}

int hb_get_last_signal(void)
{
    int s = (int)last_signal;
    last_signal = 0;
    return s;
}

void hb_init(const char *path)
{
    if (!path) return;
    strncpy(hb_path, path, sizeof(hb_path) - 1);
    hb_path[sizeof(hb_path) - 1] = '\0';
    hb_fd = open(hb_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (hb_fd >= 0) {
        hb_tick();
        LOG("heartbeat: writing to %s", hb_path);
    } else {
        ERR("heartbeat: cannot open %s: %s", hb_path, strerror(errno));
    }
}

/*
 * 每次主循环醒来时调用，把当前时间戳 + PID 追加到心跳文件。
 * 真机跑一次后 stat 该文件即可判断进程是否真的活着：
 *   mtime 持续更新 -> 进程活着
 *   mtime 停在某一刻 -> 进程被 kill，那一刻就是被 kill 的时间
 */
void hb_tick(void)
{
    if (hb_fd < 0) return;
    time_t now = time(NULL);
    char buf[96];
    int n = snprintf(buf, sizeof(buf), "%lld %d\n",
                     (long long)now, (int)getpid());
    if (n > 0 && n < (int)sizeof(buf)) {
        ssize_t w = write(hb_fd, buf, (size_t)n);
        (void)w;
    }
    /* 每次都不 fsync（I/O 太重）；hb_shutdown 时统一 fsync */
}

void hb_shutdown(void)
{
    if (hb_fd >= 0) {
        hb_tick();
        fsync(hb_fd);
        close(hb_fd);
        hb_fd = -1;
    }
}

/*
 * 探测 icube launcher 创建的 SysV shm 段。
 *
 * 方法：遍历 shmid 0..200，调用 shmctl(shmid, IPC_STAT, &info) 只读
 *       元数据。不做 shmat、不做写入 —— 避免破坏 icube 预期。
 *
 * 目的：确认 icube 是否有活跃的 shm 段（用于判断 kill 机制是否为
 *       shm 心跳超时看门狗）。
 *
 * 限制：shmid 是 per-namespace 索引，如果 icube 用了 IPC_PRIVATE key
 *       创建，shmid 也是可见的（IPC_PRIVATE 只影响 key，不影响 shmid
 *       遍历）。但如果 icube 用 shmctl(IPC_RMID) 在子进程退出后立刻
 *       删段，我们启动稍晚可能看不到 —— 这本身就是有价值的诊断
 *       （"icube 没有活跃 shm 段，重启不是 shm 心跳超时"）。
 */
void hb_detect_icube_shm(void)
{
    struct shmid_ds info;
    int found = 0;
    uid_t me = getuid();

    for (int shmid = 0; shmid < 200 && found < 8; shmid++) {
        if (shmctl(shmid, IPC_STAT, &info) < 0) continue;
        if (info.shm_perm.uid != me && info.shm_perm.cuid != me) continue;
        LOG("heartbeat: found shm shmid=%d size=%zu uid=%d "
            "nattch=%d atime=%lld ctime=%lld",
            shmid, (size_t)info.shm_segsz,
            (int)info.shm_perm.uid, (int)info.shm_nattch,
            (long long)info.shm_atime, (long long)info.shm_ctime);
        found++;
    }

    if (found == 0) {
        LOG("heartbeat: no visible shm segments for uid=%d "
            "(icube may not use shm, or segments were removed)",
            (int)me);
    } else {
        LOG("heartbeat: %d shm segment(s) found — icube likely uses "
            "shm heartbeat; next step is to reverse-engineer its "
            "message format", found);
    }
}
