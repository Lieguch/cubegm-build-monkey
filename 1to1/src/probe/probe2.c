/* ============================================================
 * probe2.c —— 探针 v2：**动态加载失败的精确定位器**
 *
 * v1 已用设备实测回答（不再是假设）
 * ---------------------------------------------------------------
 *   · 内核**能** exec 我们的静态产物（`PROBE.txt` 出现，pid=319/322，且 rename 通道也成功）
 *   · `/sdcard/cubegm/` 与 `/sdcard/cubegm/_diag/` **都可写**（openat rc=3）
 *   ⇒ 「写不出文件」被排除。剩下三种成因**必须分开**：
 *       (甲) 内核在 `load_elf_binary` 阶段拒绝   → 子进程 execve 返回 errno
 *       (乙) 内核放行、ld.so 加载/重定位失败     → 子进程 execve 返回 errno
 *       (丙) exec 成功、程序在写第一行日志前自崩 → 子进程被**信号**杀掉
 *
 * v2 的做法（一次上机拿到全部答案）
 * ---------------------------------------------------------------
 *   对每个候选：`fork()` → 子进程 `execve()` → 父进程 `wait4()` 记录结局。
 *   ★ `execve` **只在失败时返回**：
 *       · 失败 ⇒ 子进程立刻把 `execve errno` 写进日志，再 `exit_group(127)`
 *       · 成功 ⇒ 子进程被目标程序取代，永远走不到那一步
 *     ⇒ 父进程看到的 `exit_code==127` 或日志里的 `EXECVE-FAILED` 行 = 加载失败；
 *       其它结局（信号 / 别的退出码 / 超时存活）= **加载成功**，问题在程序内部或已可用。
 *
 * ★★ 必须有**阳性对照**：第一条候选是原厂 `rkgame.bak`（这台设备上确实能跑）。
 *     若连它都失败 ⇒ 说明**本探针的 exec 机制本身有问题**，其余结论一概不可信。
 *     （本项目最贵的教训之一：没有阳性对照的"0 命中"看起来恰等于"分支没走到"。）
 *
 * 设计纪律（沿用 v1，一条不放松）
 * ---------------------------------------------------------------
 *   · 纯静态、无 `.interp`、无 NEEDED、无 libc、无构造器；只用 `svc #0`。
 *   · 日志用 `O_APPEND` 打开 ⇒ 父子进程共享同一 fd 也不会互相覆盖（内核保证原子追加）。
 *   · **边测边写**（每步立刻落盘）⇒ 探针若被候选拖住，已有部分结论。
 *   · 每个候选最多等 6 秒，超时即 `SIGKILL` 并回收（GUI 程序长跑属正常，记为"存活"）。
 *   · 启动时先往多条路径各写一份 alive 标记（保底）。
 *   · 退出用 `exit_group`，不留悬挂进程。
 * ============================================================ */

/* ---- ARM EABI 系统调用号（自带，不依赖任何头文件）---- */
#define NR_exit        1
#define NR_fork        2
#define NR_read        3
#define NR_write       4
#define NR_open        5
#define NR_close       6
#define NR_execve      11
#define NR_lseek       19
#define NR_getpid      20
#define NR_kill        37
#define NR_wait4       114
#define NR_clone       120
#define NR_nanosleep   162
#define NR_exit_group  248
#define NR_openat      322

#define AT_FDCWD       (-100)
#define O_RDONLY       0
#define O_WRONLY       1
#define O_CREAT        0100
#define O_APPEND       02000
#define SEEK_SET       0
#define SEEK_END       2
#define SIGCHLD        17
#define SIGKILL        9
#define WNOHANG        1

static long sc1(long n, long a)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7) : "memory", "cc");
    return r0;
}
static long sc3(long n, long a, long b, long c)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2) : "memory", "cc");
    return r0;
}
static long sc4(long n, long a, long b, long c, long d)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3) : "memory", "cc");
    return r0;
}
static long sc5(long n, long a, long b, long c, long d, long e)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3), "r"(r4)
                     : "memory", "cc");
    return r0;
}

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }

static int LOGFD = -1;

/* 不缓冲：每步立刻落盘，防止被候选拖住时丢结论 */
static void wstr(const char *s)
{
    if (LOGFD >= 0 && s && *s) sc3(NR_write, LOGFD, (long)s, slen(s));
}
/* ★ 不要写"运行时 base"的通用格式化：`v % base` 在 base 非常量时会拉
 *   `__aeabi_uidiv`（libgcc 提供），而本探针是 `-nostdlib` ⇒ **链接失败**。
 *   拆成"常量除数的十进制"与"纯移位的十六进制"两个函数 ⇒ 编译器把 /10 优化成
 *   乘法、/16 变成移位 ⇒ 零 libgcc 依赖。 */
static char *fmt_dec(char *o, unsigned long v, int width)
{
    char t[24]; int n = 0;
    if (!v) t[n++] = '0';
    while (v) { t[n++] = (char)('0' + (int)(v % 10u)); v /= 10u; }
    while (n < width) t[n++] = '0';
    while (n) *o++ = t[--n];
    return o;
}
static char *fmt_hex(char *o, unsigned long v, int width)
{
    char t[24]; int n = 0;
    if (!v) t[n++] = '0';
    while (v) {
        unsigned long d = v & 0xfu;
        t[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10);
        v >>= 4;
    }
    while (n < width) t[n++] = '0';
    while (n) *o++ = t[--n];
    return o;
}
static void wnum(long v, int base, int width)
{
    char b[40]; char *o = b;
    if (v < 0) { *o++ = '-'; v = -v; }
    o = (base == 16) ? fmt_hex(o, (unsigned long)v, width)
                     : fmt_dec(o, (unsigned long)v, width);
    *o = 0;
    wstr(b);
}

static int open_log(const char *p)
{
    return (int)sc4(NR_openat, AT_FDCWD, (long)p, O_WRONLY | O_CREAT | O_APPEND, 0644);
}

static const char *LOGPATHS[] = {
    "/sdcard/cubegm/_diag/PROBE2.txt",
    "/sdcard/cubegm/PROBE2.txt",
    "/sdcard/PROBE2.txt",
    "/tmp/PROBE2.txt",
};
#define NLOG ((int)(sizeof(LOGPATHS) / sizeof(LOGPATHS[0])))

/* ============================================================
 * 候选清单
 *   ★ 第 1 条是**阳性对照**（原厂 rkgame，本设备上确实能跑）。
 *     它的存在使"其余候选失败"成为**可解释的差异**，而不是"探针坏了"。
 *   ★ 用户按 README 放置 rkgame.t1..t4；缺哪个就跳过哪个（探针会打印"打不开"）。
 * ============================================================ */
struct cand { const char *path; const char *note; };

static struct cand CANDS[] = {
    { "/sdcard/cubegm/rkgame.bak", "1 阳性对照: 原厂 rkgame"      },
    { "/sdcard/cubegm/rkgame.t4",  "2 最小动态 ELF(仅 NEEDED libc)" },
    { "/sdcard/cubegm/rkgame.t1",  "3 A: rebuilt 5.4MB"           },
    { "/sdcard/cubegm/rkgame.t2",  "4 B: diag 5.7MB"              },
    { "/sdcard/cubegm/rkgame.t3",  "5 C: 2段布局新版"              },
};
#define NCAND ((int)(sizeof(CANDS) / sizeof(CANDS[0])))

static const char *errname(long e)
{
    switch (e) {
    case 0:  return "OK";
    case 1:  return "EPERM";
    case 2:  return "ENOENT(interp或依赖库缺失)";
    case 5:  return "EIO";
    case 7:  return "E2BIG";
    case 8:  return "ENOEXEC(内核拒绝该ELF)";
    case 9:  return "EBADF";
    case 12: return "ENOMEM(段映射内存不足)";
    case 13: return "EACCES(权限)";
    case 14: return "EFAULT";
    case 26: return "ETXTBSY";
    case 40: return "ELOOP";
    case 79: return "ELIBSCN";
    case 80: return "ELIBBAD(动态库不可用)";
    case 88: return "ENOSYS(该系统调用不存在)";
    default: return "?";
    }
}

/* 把一个文件的内容抄进日志（限长，防日志爆掉）。
 * 用途：把设备环境的硬事实**一次带回来**，省掉一轮轮猜：
 *   /proc/sys/vm/mmap_min_addr —— 若 > 产物最低 vaddr，则内核 EPERM 拒载
 *   /proc/self/maps           —— 我们自己被映射的样子 ⇒ 反推内核**页大小**与加载方式
 *   /proc/mounts              —— /sdcard 的挂载参数（noexec? fmask?）
 *   /proc/version, /proc/cpuinfo —— 内核/CPU 身份 */
static void dump_file(const char *path, int maxbytes)
{
    int fd;
    long n;
    char buf[400];
    wstr("\n--- "); wstr(path); wstr("\n");
    fd = (int)sc4(NR_openat, AT_FDCWD, (long)path, O_RDONLY, 0);
    if (fd < 0) {
        wstr("    (打不开 errno="); wnum(-fd, 10, 0); wstr(")\n");
        return;
    }
    while (maxbytes > 0) {
        n = sc3(NR_read, fd, (long)buf, (long)(sizeof(buf) - 1));
        if (n <= 0) break;
        if (n > maxbytes) n = maxbytes;
        buf[n] = 0;
        wstr("    ");
        wstr(buf);
        if (buf[n - 1] != '\n') wstr("\n");   /* 补换行，保证可读 */
        maxbytes -= (int)n;
    }
    sc1(NR_close, fd);
}

/* 轮询 wait4，最多 max_ms；返回 1=已结束 / -1=超时(已KILL并回收) */
static int wait_pid_limited(long pid, int *status, int max_ms)
{
    int i;
    long ts[2];
    for (i = 0; i < max_ms / 100; i++) {
        long r = sc4(NR_wait4, pid, (long)status, WNOHANG, 0);
        if (r == pid || r < 0) return 1;
        ts[0] = 0; ts[1] = 100000000L;              /* 100 ms */
        sc3(NR_nanosleep, (long)ts, 0, 0);
    }
    sc3(NR_kill, pid, SIGKILL, 0);
    sc4(NR_wait4, pid, (long)status, 0, 0);
    return -1;
}

static void test_cand(struct cand *c)
{
    int fd;
    long size, pid;
    int status = 0;
    unsigned char magic[4];
    long rd;

    wstr("\n--- ");
    wstr(c->note);
    wstr("\n    path ");
    wstr(c->path);
    wstr("\n");

    /* ① 存在性 + 大小 + ELF magic（顺便检出"拷贝损坏"） */
    fd = (int)sc4(NR_openat, AT_FDCWD, (long)c->path, O_RDONLY, 0);
    if (fd < 0) {
        wstr("    文件打不开 errno="); wnum(-fd, 10, 0);
        wstr(" ("); wstr(errname(-fd)); wstr(")  ==> 跳过\n");
        return;
    }
    size = sc3(NR_lseek, fd, 0, SEEK_END);
    sc3(NR_lseek, fd, 0, SEEK_SET);
    magic[0] = magic[1] = magic[2] = magic[3] = 0;
    rd = sc3(NR_read, fd, (long)magic, 4);
    sc1(NR_close, fd);

    wstr("    size="); wnum(size, 10, 0);
    wstr("  magic=");
    wnum(magic[0], 16, 2); wnum(magic[1], 16, 2);
    wnum(magic[2], 16, 2); wnum(magic[3], 16, 2);
    if (!(rd == 4 && magic[0] == 0x7f && magic[1] == 'E' && magic[2] == 'L' && magic[3] == 'F')) {
        wstr("  ==> ★ 不是 ELF（拷贝损坏？）跳过\n");
        return;
    }
    wstr("  (ELF OK)\n");

    /* ② fork + execve */
    pid = sc1(NR_fork, 0);
    if (pid == -38)                                  /* ENOSYS ⇒ 退回 clone */
        pid = sc5(NR_clone, SIGCHLD, 0, 0, 0, 0);
    if (pid < 0) {
        wstr("    fork 失败 errno="); wnum(-pid, 10, 0);
        wstr(" ("); wstr(errname(-pid)); wstr(")\n");
        return;
    }

    if (pid == 0) {
        /* ---------------- 子进程 ---------------- */
        char *argv[2];
        char *envp[1];
        long e;
        argv[0] = (char *)c->path;
        argv[1] = 0;
        envp[0] = 0;                                 /* 空环境：排除环境变量干扰 */
        e = sc3(NR_execve, (long)c->path, (long)argv, (long)envp);
        /* 只有失败才走到这里：立刻把 errno 落盘 */
        wstr("    >>> EXECVE-FAILED errno=");
        wnum(-e, 10, 0);
        wstr(" ("); wstr(errname(-e)); wstr(")  <- 由子进程(pid=");
        wnum(sc1(NR_getpid, 0), 10, 0);
        wstr(")写入\n");
        sc1(NR_exit_group, 127);
        for (;;) { }
    }

    /* ---------------- 父进程 ---------------- */
    if (wait_pid_limited(pid, &status, 6000) < 0) {
        wstr("    >>> 结局: 子进程存活至超时(已KILL)  ==> ★ exec 成功且程序在运行\n");
        return;
    }
    {
        int lo = status & 0x7f;
        if (lo == 0) {
            long code = (status >> 8) & 0xff;
            wstr("    >>> 结局: 正常退出 exit_code="); wnum(code, 10, 0);
            if (code == 127)
                wstr("  ==> ★ execve 失败（详见上面 EXECVE-FAILED 行）\n");
            else
                wstr("  ==> exec 成功，程序自行退出（可能因缺 shm/资源）\n");
        } else {
            wstr("    >>> 结局: 被信号终止 signal="); wnum(lo, 10, 0);
            wstr("  ==> ★ exec 成功，但程序在初始化阶段崩了\n");
        }
    }
}

void probe_main(void)
{
    int i, k;
    long pid_self;

    /* ① 保底：往所有能打开的路径各写一份 alive 标记 */
    for (i = 0; i < NLOG; i++) {
        int fd = open_log(LOGPATHS[i]);
        if (fd >= 0) {
            const char *m = "=== CGM PROBE v2 alive ===\n";
            sc3(NR_write, fd, (long)m, slen(m));
            if (LOGFD < 0) LOGFD = fd;
            else sc1(NR_close, fd);
        }
    }
    if (LOGFD < 0) {
        const char *m = "[PROBE2] no writable log path\n";
        sc3(NR_write, 1, (long)m, slen(m));
        sc3(NR_write, 2, (long)m, slen(m));
        sc1(NR_exit_group, 1);
        for (;;) { }
    }

    pid_self = sc1(NR_getpid, 0);
    wstr("\n=== CGM PROBE v2 ===\n");
    wstr("pid="); wnum(pid_self, 10, 0);
    wstr("\n用途: 对每个候选 execve() 并记录结局, 判定「内核拒载 / ld.so 失败 / 程序自崩」\n");
    wstr("读法:\n");
    wstr("  EXECVE-FAILED errno=N  => 加载阶段失败(内核或 ld.so), errno 给出原因\n");
    wstr("  被信号终止 signal=N    => exec 成功, 但程序初始化崩\n");
    wstr("  存活至超时 / 自行退出  => exec 成功\n");
    wstr("  ★ 第 1 条(原厂)必须成功; 若它也失败, 则本探针的结论一概不可信\n");

    /* ② 设备环境事实（一次带回来，省掉一轮轮猜） */
    wstr("\n########## 设备环境事实 ##########\n");
    dump_file("/proc/sys/vm/mmap_min_addr", 64);
    dump_file("/proc/version", 200);
    dump_file("/proc/mounts", 900);
    dump_file("/proc/self/maps", 1200);

    /* ③ 逐个候选 exec 测试 */
    wstr("\n########## 候选 exec 测试 ##########\n");
    for (k = 0; k < NCAND; k++)
        test_cand(&CANDS[k]);

    wstr("\n=== END (probe2) ===\n");
    sc1(NR_close, LOGFD);
    sc1(NR_exit_group, 0);
    for (;;) { }
}
