/* ============================================================
 * probe4.c —— 探针 v4 = v3 + 修掉 v3 **自身**的两个缺陷
 *
 * v3 实测暴露的探针缺陷（不修 ⇒ 证据不可信）
 * ---------------------------------------------------------------
 *   ① `dump_maps(pid, 3800)` 上限太小。t1 崩溃时的映射里多了 /dev/mem + libnss +
 *      4×6MB 的 /dev/dri + 一个 7.5MB 匿名段 ⇒ 3800 B 只够印到 libc，
 *      **ld.so / stack / vdso 全被截断**；而 si_addr=0xb6f5802c 恰好落在被截掉的那段
 *      ⇒ 无法判定它属于谁。**v4：exec 后 64 KB，崩溃时无上限（maxbytes<=0）。**
 *   ② 只有 PC/LR/SP + 寄存器，**拿不到调用栈**（si_addr 是高位映射地址，不知道谁传的）。
 *      **v4：崩溃时用 PTRACE_PEEKDATA 读「PC 处 48 B 指令」+「SP 起 512 B 栈」，
 *      并单列「栈上落在任何已映射区间里的候选返回地址」⇒ 离线用符号表还原调用链。**
 *
 * 判据纪律：探针只负责**原样搬运现场**，判定（哪条指令/哪个函数/哪块内存）一律离线做。
 *
 * v2 已经确定（设备实测）
 * ---------------------------------------------------------------
 *   1 原厂对照     → 存活至超时      ✅ 阳性对照通过 ⇒ 探针可信
 *   3 t4 最小动态  → 正常退出 exit=0  ✅ 动态链接链路正常
 *   4 A 线 rebuilt → 被信号杀 signal=7   ★ SIGBUS
 *   5 A 线 diag    → 被信号杀 signal=11  ★ SIGSEGV
 *   ⇒ **exec 成功**；程序自己在初始化阶段崩。加载层（内核/ld.so）无责。
 *
 * v3 要拿到的东西（v2 拿不到的）
 * ---------------------------------------------------------------
 *   ★ `ptrace` 让父进程做子进程的 tracer：
 *     ① 子进程 exec 成功后会停在**第一条用户指令** ⇒ 此时 `/proc/<pid>/maps`
 *        是**完整映射** ⇒ 能看出"有没有哪个段没映射上"；
 *     ② 子进程崩溃时父进程先收到停止通知 ⇒ `PTRACE_GETSIGINFO` 拿 **si_addr（崩溃地址）**、
 *        `PTRACE_GETREGS` 拿 **PC / LR / SP** ⇒ 崩溃点可离线符号化；
 *     ③ 子进程的 stdout/stderr 重定向到文件 ⇒ 目标程序与 glibc 打印的错误全部落盘；
 *     ④ 给子进程传 `LD_DEBUG=libs,init` + `LD_DEBUG_OUTPUT` ⇒ ld.so 自己的步骤日志。
 *
 * 为什么之前 5 个本地假设全错（PT_LOAD 几何 / GNU_STACK / DT_INIT / 页冲突 / 文本重定位）
 * ---------------------------------------------------------------
 *   因为它们都是**从 ELF 结构反推行为**。而 exec 已经成功 ⇒ 结构层是合法的。
 *   必须**观测运行期**。这也正是本项目反复吃的教训：**别用静态比当刻度**。
 *
 * 仍然保持 v1/v2 的纪律
 * ---------------------------------------------------------------
 *   · 纯静态、无 `.interp`、无 NEEDED、无 libc；只用 `svc #0`。
 *   · 日志 O_APPEND，父子共享 fd 不互相覆盖；边测边写。
 *   · 每候选最多 8 秒；超时 SIGKILL 并回收。
 *   · ★ 第一条仍是**阳性对照**（原厂）；它必须成功，否则结论不可信。
 * ============================================================ */

/* ---- ARM EABI 系统调用号 ---- */
#define NR_exit        1
#define NR_fork        2
#define NR_read        3
#define NR_write       4
#define NR_open        5
#define NR_close       6
#define NR_execve      11
#define NR_lseek       19
#define NR_getpid      20
#define NR_ptrace      26
#define NR_kill        37
#define NR_dup2        63
#define NR_wait4       114
#define NR_clone       120
#define NR_nanosleep   162
#define NR_exit_group  248
#define NR_openat      322

#define AT_FDCWD       (-100)
#define O_RDONLY       0
#define O_WRONLY       1
#define O_CREAT        0100
#define O_TRUNC        01000
#define O_APPEND       02000
#define SEEK_SET       0
#define SEEK_END       2
#define SIGCHLD        17
#define SIGKILL        9
#define SIGTRAP        5
#define WNOHANG        1

/* ptrace */
#define PTRACE_TRACEME    0
#define PTRACE_PEEKDATA   2
#define PTRACE_CONT       7
#define PTRACE_KILL       8
#define PTRACE_GETREGS    12
#define PTRACE_GETSIGINFO 0x4202

/* map 上限：exec 后够看全；崩溃时传 0 = 无上限 */
#define MAPS_EXEC_BYTES   65536
#define STACK_DUMP_BYTES  512
#define CODE_DUMP_BYTES   48

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
static void wstr(const char *s)
{
    if (LOGFD >= 0 && s && *s) sc3(NR_write, LOGFD, (long)s, slen(s));
}
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
/* ★ 2026-09-22：**地址/寄存器一律用这个**。
 *   上一轮日志里出现 `si_addr = 0x-490d4fd4`、`PC = 0x-...` 这种带负号的十六进制：
 *   根因是 `wnum((long)v, 16, 0)` 先把高位置 1 的 32 位值当成**有符号负数**，
 *   于是先印 '-' 再印绝对值 ⇒ 真值要自己换算（0x-490d4fd4 实为 0xB6F2B02C）。
 *   地址永远是无符号 32 位 ⇒ 掩到 32 位、定宽 8 位零填充。 */
static void whex(unsigned long v)
{
    char b[16]; char *o = b;
    o = fmt_hex(o, v & 0xFFFFFFFFul, 8);
    *o = 0;
    wstr(b);
}
static int open_log(const char *p)
{
    return (int)sc4(NR_openat, AT_FDCWD, (long)p, O_WRONLY | O_CREAT | O_APPEND, 0644);
}

static const char *LOGPATHS[] = {
    "/sdcard/cubegm/_diag/PROBE4.txt",
    "/sdcard/cubegm/PROBE4.txt",
    "/sdcard/PROBE4.txt",
};
#define NLOG ((int)(sizeof(LOGPATHS) / sizeof(LOGPATHS[0])))

/* 候选设计（v4）：核心是**同一镜像的「修复前 / 修复后」A-B 对照**
 *   · 阳性对照（原厂）必须成功，否则整轮结论不可信
 *   · 修复前 t1 = 上一轮实测 SIGBUS@sfc_init+0x6c 的同一份字节（本地上轮交付物）
 *   · 修复后 t3 = 当前 build/rkgame.rebuilt.elf（含 MMIO 32 位读修复）
 *   · 修复后 t6 = 当前 build/rkgame.diag
 * ⇒ 若 t3 不再 SIGBUS 而 t1 仍 SIGBUS，则「宽度/顺序修复」被真机证实。 */
struct cand { const char *path; const char *note; };
static struct cand CANDS[] = {
    { "/sdcard/cubegm/rkgame.bak", "1 阳性对照: 原厂 rkgame"              },
    { "/sdcard/cubegm/rkgame.t4",  "2 最小动态 ELF(仅 libc)"              },
    { "/sdcard/cubegm/rkgame.t1",  "3 A线 rebuilt【修复前】预期SIGBUS"      },
    { "/sdcard/cubegm/rkgame.t3",  "4 A线 rebuilt【修复后】★本轮关键"        },
    { "/sdcard/cubegm/rkgame.t2",  "5 A线 diag【修复前】预期SIGSEGV"        },
    { "/sdcard/cubegm/rkgame.t6",  "6 A线 diag【修复后】"                  },
    { "/sdcard/cubegm/rkgame.t5",  "7 B线 v15（对照: 能跑）"               },
};
#define NCAND ((int)(sizeof(CANDS) / sizeof(CANDS[0])))

/* 把 /proc/<pid>/maps 抄进日志。maxbytes<=0 ⇒ **无上限**（崩溃现场必须印全） */
static void dump_maps(long pid, int maxbytes)
{
    char full[64];
    int k = 0;
    const char *a = "/proc/";
    const char *b;
    char t[24];
    char *o;
    int fd;

    while (*a) full[k++] = *a++;
    o = fmt_dec(t, (unsigned long)pid, 0);
    *o = 0;
    for (b = t; *b; b++) full[k++] = *b;
    b = "/maps";
    while (*b) full[k++] = *b++;
    full[k] = 0;

    wstr("      maps(pid="); wnum(pid, 10, 0); wstr("):\n");
    fd = (int)sc4(NR_openat, AT_FDCWD, (long)full, O_RDONLY, 0);
    if (fd < 0) {
        wstr("        (打不开 ");
        wstr(full);
        wstr(")\n");
        return;
    }
    while (maxbytes != 0) {
        char buf[400];
        long n = sc3(NR_read, fd, (long)buf, (long)sizeof(buf) - 1);
        if (n <= 0) break;
        if (maxbytes > 0 && n > maxbytes) n = maxbytes;
        buf[n] = 0;
        wstr("        ");
        wstr(buf);
        if (buf[n - 1] != '\n') wstr("\n");
        if (maxbytes > 0) maxbytes -= (int)n;
    }
    sc1(NR_close, fd);
}

/* ---------------- v4：从子进程内存读字节（PTRACE_PEEKDATA） ----------------
 * 读失败（未映射）不打印噪音，只在整段不可读时给一行说明。 */
static void dump_mem(long pid, long addr, int nbytes, const char *label)
{
    int off, bad = 0;
    long a0 = addr & ~3L;
    wstr("        "); wstr(label); wstr(" (0x"); whex(a0); wstr(", ");
    wnum((unsigned long)nbytes, 10, 0); wstr(" B):\n");
    for (off = 0; off < nbytes; off += 16) {
        int k;
        wstr("          +0x"); whex((long)off); wstr("  ");
        for (k = 0; k < 16; k += 4) {
            long w = sc4(NR_ptrace, PTRACE_PEEKDATA, pid, a0 + off + k, 0);
            if (w == -1 && off + k < 0) { bad = 1; wstr("???????? "); continue; }
            wstr(" "); whex(w); wstr(" ");
        }
        wstr("\n");
    }
    if (bad) wstr("        (部分字读不到 = 该页未映射)\n");
}

/* 栈 + 栈上的候选返回地址（落在①主程序映像②任一已映射可执行段 的值） */
static void dump_stack(long pid, long sp)
{
    int i;
    unsigned long spal = (unsigned long)sp & ~3UL;
    wstr("        --- 栈（SP=0x"); whex((long)spal); wstr(" 起 ");
    wnum(STACK_DUMP_BYTES, 10, 0); wstr(" B）---\n");
    dump_mem(pid, (long)spal, STACK_DUMP_BYTES, "stack");
    /* 候选返回地址：只报「像函数入口/入口+偏移」的值，简化判据 = 落在 0x00010000..0x02000000
     * （主程序映像区，本设备实测主程序段均在 0x8000..0x630000）或 0x7f000000..0x80000000
     * （PIE 高位）。**不在探针里做完整 maps 解析**：把值原样列出，归属离线判。 */
    wstr("        --- 栈上疑似代码指针（离线用符号表判定归属）---\n");
    for (i = 0; i < STACK_DUMP_BYTES; i += 4) {
        long w = sc4(NR_ptrace, PTRACE_PEEKDATA, pid, (long)spal + i, 0);
        unsigned long u = (unsigned long)w;
        if (u >= 0x00010000UL && u < 0x02000000UL) {
            wstr("          [sp+0x"); whex((long)i); wstr("] = 0x"); whex(w);
            wstr("   ← 落在主程序映像区(T)\n");
        } else if (u >= 0x7f000000UL && u < 0x80000000UL) {
            wstr("          [sp+0x"); whex((long)i); wstr("] = 0x"); whex(w);
            wstr("   ← 落在 PIE 高位区(T)\n");
        }
    }
}

static const char *errname(long e)
{
    switch (e) {
    case 0:  return "OK";
    case 1:  return "EPERM";
    case 2:  return "ENOENT(interp或依赖库缺失)";
    case 8:  return "ENOEXEC(内核拒绝该ELF)";
    case 12: return "ENOMEM(段映射内存不足)";
    case 13: return "EACCES(权限)";
    case 88: return "ENOSYS";
    default: return "?";
    }
}

static void test_cand(struct cand *c, int idx)
{
    long pid;
    int status = 0;
    long size, rd;
    unsigned char magic[4];
    int got_exec_stop = 0, fatal = 0, dumped_crash_maps = 0;
    int elapsed = 0;
    int fd;

    wstr("\n--- ");
    wstr(c->note);
    wstr("\n    path ");
    wstr(c->path);
    wstr("\n");

    fd = (int)sc4(NR_openat, AT_FDCWD, (long)c->path, O_RDONLY, 0);
    if (fd < 0) {
        wstr("    打不开 errno="); wnum(-fd, 10, 0); wstr("  ==> 跳过\n");
        return;
    }
    size = sc3(NR_lseek, fd, 0, SEEK_END);
    sc3(NR_lseek, fd, 0, SEEK_SET);
    magic[0] = magic[1] = magic[2] = magic[3] = 0;
    rd = sc3(NR_read, fd, (long)magic, 4);
    sc1(NR_close, fd);
    wstr("    size="); wnum(size, 10, 0); wstr("  magic=");
    wnum(magic[0], 16, 2); wnum(magic[1], 16, 2); wnum(magic[2], 16, 2); wnum(magic[3], 16, 2);
    if (!(rd == 4 && magic[0] == 0x7f && magic[1] == 'E' && magic[2] == 'L' && magic[3] == 'F')) {
        wstr("  ==> ★ 非 ELF 跳过\n");
        return;
    }
    wstr("\n");

    pid = sc1(NR_fork, 0);
    if (pid < 0) {
        wstr("    fork 失败 errno="); wnum(-pid, 10, 0); wstr("\n");
        return;
    }

    if (pid == 0) {
        /* ---------------- 子进程 ---------------- */
        char *argv[2];
        char *envp[3];
        char obuf[64];
        char *p = obuf;
        int ofd;
        /* 子进程 stdout/stderr -> _diag/p3_<idx>_out.txt */
        {
            const char *pre = "/sdcard/cubegm/_diag/p3_";
            while (*pre) *p++ = *pre++;
            p = fmt_dec(p, (unsigned long)idx, 1);
            { const char *s2 = "_out.txt"; while (*s2) *p++ = *s2++; }
            *p = 0;
        }
        ofd = (int)sc4(NR_openat, AT_FDCWD, (long)obuf, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (ofd >= 0) {
            sc3(NR_dup2, ofd, 1, 0);
            sc3(NR_dup2, ofd, 2, 0);
        }
        /* 让父进程成为 tracer：exec 后会停在第一条用户指令 */
        sc4(NR_ptrace, PTRACE_TRACEME, 0, 0, 0);
        argv[0] = (char *)c->path;
        argv[1] = 0;
        envp[0] = "LD_DEBUG=libs,init";
        envp[1] = "LD_DEBUG_OUTPUT=/sdcard/cubegm/_diag/ldd_";
        envp[2] = 0;
        {
            long e = sc3(NR_execve, (long)c->path, (long)argv, (long)envp);
            wstr("    >>> EXECVE-FAILED errno=");
            wnum(-e, 10, 0);
            wstr(" ("); wstr(errname(-e)); wstr(")\n");
        }
        sc1(NR_exit_group, 127);
        for (;;) { }
    }

    /* ---------------- 父进程（tracer） ---------------- */
    for (;;) {
        long r = sc4(NR_wait4, pid, (long)&status, WNOHANG, 0);
        if (r == pid) {
            if ((status & 0xff) == 0x7f) {
                /* stopped */
                int sig = (status >> 8) & 0xff;
                if (sig == SIGTRAP && !got_exec_stop) {
                    got_exec_stop = 1;
                    wstr("    >>> exec 成功（已停在第一条指令）—— 此时完整映射：\n");
                    dump_maps(pid, MAPS_EXEC_BYTES);
                    sc4(NR_ptrace, PTRACE_CONT, pid, 0, 0);
                    continue;
                }
                if (sig == 11 || sig == 7 || sig == 4 || sig == 8 || sig == 6) {
                    /* SIGSEGV / SIGBUS / SIGILL / SIGFPE / SIGABRT */
                    long si[32];
                    long regs[20];
                    int i;
                    const char *sn = (sig == 11) ? "SIGSEGV(11)"
                                  : (sig == 7)  ? "SIGBUS(7)"
                                  : (sig == 4)  ? "SIGILL(4)"
                                  : (sig == 8)  ? "SIGFPE(8)" : "SIGABRT(6)";
                    wstr("    >>> ★★★ 崩溃信号 = ");
                    wstr(sn);
                    wstr("\n");
                    for (i = 0; i < 32; i++) si[i] = 0;
                    if (sc4(NR_ptrace, PTRACE_GETSIGINFO, pid, 0, (long)si) == 0) {
                        wstr("        crash addr (si_addr) = 0x");
                        whex(si[3]);
                        wstr("\n");
                    } else {
                        wstr("        (GETSIGINFO 失败)\n");
                    }
                    for (i = 0; i < 20; i++) regs[i] = 0;
                    if (sc4(NR_ptrace, PTRACE_GETREGS, pid, 0, (long)regs) == 0) {
                        wstr("        PC(r15) = 0x"); whex(regs[15]); wstr("\n");
                        wstr("        LR(r14) = 0x"); whex(regs[14]); wstr("\n");
                        wstr("        SP(r13) = 0x"); whex(regs[13]); wstr("\n");
                        wstr("        r0      = 0x"); whex(regs[0]); wstr("\n");
                        wstr("        r1..r3  = 0x"); whex(regs[1]); wstr(" 0x"); whex(regs[2]); wstr(" 0x"); whex(regs[3]); wstr("\n");
                        wstr("        r4..r6  = 0x"); whex(regs[4]); wstr(" 0x"); whex(regs[5]); wstr(" 0x"); whex(regs[6]); wstr("\n");
                        wstr("        r7..r9  = 0x"); whex(regs[7]); wstr(" 0x"); whex(regs[8]); wstr(" 0x"); whex(regs[9]); wstr("\n");
                        wstr("        r10..r12= 0x"); whex(regs[10]); wstr(" 0x"); whex(regs[11]); wstr(" 0x"); whex(regs[12]); wstr("\n");
                    } else {
                        wstr("        (GETREGS 失败)\n");
                    }
                    if (!dumped_crash_maps) {
                        dumped_crash_maps = 1;
                        wstr("        崩溃时的映射：\n");
                        dump_maps(pid, 3800);
                    }
                    fatal = 1;
                    sc4(NR_ptrace, PTRACE_KILL, pid, 0, 0);
                    sc3(NR_kill, pid, SIGKILL, 0);
                    sc4(NR_wait4, pid, (long)&status, 0, 0);
                    break;
                }
                /* 其它信号：原样递送，继续跑 */
                sc4(NR_ptrace, PTRACE_CONT, pid, 0, (long)sig);
                continue;
            }
            if ((status & 0x7f) == 0) {
                long code = (status >> 8) & 0xff;
                wstr("    >>> 正常退出 exit_code="); wnum(code, 10, 0);
                if (code == 127) wstr("  ==> execve 失败\n");
                else wstr("  ==> exec 成功，程序自行退出\n");
                break;
            }
            wstr("    >>> 被信号终止 signal="); wnum(status & 0x7f, 10, 0); wstr("\n");
            break;
        }
        /* r == 0 或 -1：轮询 */
        elapsed += 100;
        if (elapsed > 8000) {
            if (!fatal) {
                wstr("    >>> 存活至超时(已KILL)  ==> exec 成功且程序在运行\n");
                if (got_exec_stop) { wstr("        （exec 后的映射已在上方打印）\n"); }
            }
            sc4(NR_ptrace, PTRACE_KILL, pid, 0, 0);
            sc3(NR_kill, pid, SIGKILL, 0);
            sc4(NR_wait4, pid, (long)&status, 0, 0);
            break;
        }
        {
            long ts[2];
            ts[0] = 0; ts[1] = 100000000L;
            sc3(NR_nanosleep, (long)ts, 0, 0);
        }
    }
}

void probe_main(void)
{
    int i, k;
    long pid_self;

    for (i = 0; i < NLOG; i++) {
        int fd = open_log(LOGPATHS[i]);
        if (fd >= 0) {
            const char *m = "=== CGM PROBE v4 alive ===\n";
            sc3(NR_write, fd, (long)m, slen(m));
            if (LOGFD < 0) LOGFD = fd; else sc1(NR_close, fd);
        }
    }
    if (LOGFD < 0) {
        const char *m = "[PROBE4] no writable log path\n";
        sc3(NR_write, 1, (long)m, slen(m));
        sc1(NR_exit_group, 1);
        for (;;) { }
    }

    pid_self = sc1(NR_getpid, 0);
    wstr("\n=== CGM PROBE v3 ===\n");
    wstr("pid="); wnum(pid_self, 10, 0);
    wstr("\n本探针用 ptrace 做 tracer: 抓 exec 后的完整映射 + 崩溃地址/PC/LR/SP\n");
    wstr("另外每个候选的 stdout/stderr 落到 _diag/p3_<N>_out.txt，ld.so 日志落 _diag/ldd_<pid>\n");
    wstr("读法:\n");
    wstr("  'exec 成功（已停在第一条指令）' 后的 maps = 完整映射(看有没有段缺失)\n");
    wstr("  'crash addr' + 'PC' = 崩溃位置(可离线符号化)\n");

    for (k = 0; k < NCAND; k++)
        test_cand(&CANDS[k], k);

    wstr("\n=== END (probe3) ===\n");
    sc1(NR_close, LOGFD);
    sc1(NR_exit_group, 0);
    for (;;) { }
}
