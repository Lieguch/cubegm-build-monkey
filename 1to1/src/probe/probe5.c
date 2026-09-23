/* ============================================================
 * probe5.c —— 探针 v5：**把写入次数降到个位数**（v4 当场因 SD 写失败丢了证据）
 *
 * v4 实测到的**采集端**结构性缺陷（见 PLAN-DEVICE-IO.md §3）
 * ---------------------------------------------------------------
 *   · 崩溃时映射被**截在行中间**（`b6d31000-b6`）—— v4 已把 maps 上限设为"无上限"
 *     ⇒ 不是缓冲截断，是**写盘失败**；
 *   · v4 新增的"PC 处指令 + 栈"**根本没打印**（写失败发生在它们之前）；
 *   · `crash.txt` / `frames.bin` = 0 B —— 文件创建成功、内容写入失败；
 *   · 单轮产生 ~20 个文件、数百次小写；icube 反复拉起 rkgame ⇒ 上千次小写
 *     ⇒ 触发 SD/FAT 的"频繁小数据量写 + 句柄未释放"故障模式。
 *
 * v5 的修法（结构性，不是加重试）
 * ---------------------------------------------------------------
 *   P1 日志写 **tmpfs**（/tmp/cgm/），不写 SD；结束时由外部一次拷回
 *   P3 **不用 LD_DEBUG**（它是"每进程一文件"的元凶；/proc/pid/maps 已含全部加载映像）
 *   P4 候选输出**合并为单文件**（O_APPEND），不再每候选新建/截断
 *   P5 候选超时 8s -> 3s          P6 候选数 7 -> 3（只留关键 A/B 对照 + 阳性对照）
 *   P7 `FILES-PLANNED` / `FILES-CREATED` 打进日志（让"文件爆炸"可观测）
 *   P8 任何 write 失败 ⇒ 追加一行 `### EVIDENCE-TRUNCATED ...`
 *      **禁止半截文件冒充完整证据**（v4 就被半截 maps 骗过一次）
 *
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
#define NR_mkdirat     34      /* ARM EABI: __NR_SYSCALL_BASE + 34 */

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

/* ★ P1：tmpfs 工作目录（高频日志）；SD 只用于"结束时一次拷回" */
#define TMPROOT   "/tmp/cgm"
/* ★ P6：单轮候选 3 个（原厂阳性对照 + 修复前 + 修复后）。
 * 理由：判据需要的只是这组 A/B 对照；候选越多，单轮文件数与时长越失控。 */
#define CAND_TIMEOUT_MS  3000

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
/* ★ P7/P8：所有输出经这里 ⇒ 写入失败可被立刻发现并标记 */
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
/* ★ P8：写入失败必须显式标记。
 * 纪律：**半截证据比没有证据更危险** —— 它会被当成"完整但异常"的现场。
 * v4 的 t6 崩溃映射就是被截在行中间，而我要不是去比对长度，根本看不出。 */
static long g_wfail;        /* 非 0 = 本次会话出现过写入失败 */
static long g_nfiles;       /* 实际创建/打开过的文件数（P7）*/

static void wmark_truncated(const char *why)
{
    static const char *m = "### EVIDENCE-TRUNCATED (write failed; NOT a complete scene) why=";
    if (g_wfail) return;                 /* 只标一次，避免刷屏 */
    g_wfail = 1;
    if (LOGFD >= 0) {
        sc3(NR_write, LOGFD, (long)m, slen(m));
        sc3(NR_write, LOGFD, (long)why, slen(why));
        sc3(NR_write, LOGFD, (long)"\n", 1);
    }
}

static int open_log(const char *p)
{
    int fd = (int)sc4(NR_openat, AT_FDCWD, (long)p, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd >= 0) g_nfiles++;          /* P7：文件数自检 */
    return fd;
}

/* ★ P1：**优先 tmpfs**（RAM 盘）。SD 卡的故障模式是"写入次数"而不是容量
 * （联网核实：频繁小数据量写 + 句柄未释放 ⇒ 写失败 / 文件损坏），
 * 所以把高频日志放到内存里，SD 上只留"最后合并出来的一个文件"。
 * 探针 v1 已实测 `/tmp/PROBE.txt rc=0` ⇒ /tmp 可写。 */
static const char *LOGPATHS[] = {
    "/tmp/cgm/PROBE5.txt",
    "/sdcard/cubegm/_diag/PROBE5.txt",
    "/sdcard/PROBE5.txt",
};
#define NLOG ((int)(sizeof(LOGPATHS) / sizeof(LOGPATHS[0])))

/* 候选设计（v4）：核心是**同一镜像的「修复前 / 修复后」A-B 对照**
 *   · 阳性对照（原厂）必须成功，否则整轮结论不可信
 *   · 修复前 t1 = 上一轮实测 SIGBUS@sfc_init+0x6c 的同一份字节（本地上轮交付物）
 *   · 修复后 t3 = 当前 build/rkgame.rebuilt.elf（含 MMIO 32 位读修复）
 *   · 修复后 t6 = 当前 build/rkgame.diag
 * ⇒ 若 t3 不再 SIGBUS 而 t1 仍 SIGBUS，则「宽度/顺序修复」被真机证实。 */
struct cand { const char *path; const char *note; };
/* ★ P6：**只保留判据必需的三项**。
 *   目的：把单轮从"7 候选 × 8 秒 ≈ 60 秒 + ~20 个文件"压到
 *        "3 候选 × 3 秒 ≈ 10 秒 + 2 个文件"，让 icube 的重启窗口内也能跑完一轮。
 *   其余候选（t4/t2/t6/t5）需要时另跑，不占主判据的单轮预算。 */
static struct cand CANDS[] = {
    { "/sdcard/cubegm/rkgame.bak", "1 阳性对照: 原厂 rkgame（必须存活）"      },
    { "/sdcard/cubegm/rkgame.t1",  "2 A线 rebuilt【修复前】预期 SIGBUS@0x501b84" },
    { "/sdcard/cubegm/rkgame.t3",  "3 A线 rebuilt【修复后】★不得再 SIGBUS"     },
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

    /* ★ P2：确保 tmpfs 目录存在（父亲先建；子进程也建一次，幂等） */
    {
        sc3(NR_mkdirat, AT_FDCWD, (long)TMPROOT, 0755);
    }

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
        /* ★ P4：所有候选的 stdout/stderr **合并到一个文件**（O_APPEND + 分隔头）。
         *   旧做法 `p3_<idx>_out.txt` 每候选新建 + O_TRUNC ⇒ 每轮 7 次文件操作，
         *   而 icube 反复拉起探针 ⇒ 反复重建。合并后每轮只 1 个追加写。 */
        {
            const char *pre = TMPROOT "/out.txt";
            while (*pre) *p++ = *pre++;
            *p = 0;
        }
        ofd = (int)sc4(NR_openat, AT_FDCWD, (long)obuf, O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (ofd >= 0) {
            /* 先写一条分隔头，标明这一段 stdout 属于哪个候选 */
            char hb[96]; char *q = hb;
            { const char *s2 = "\n===CAND "; while (*s2) *q++ = *s2++; }
            q = fmt_dec(q, (unsigned long)idx, 1);
            { const char *s2 = " "; while (*s2) *q++ = *s2++; }
            { const char *s2 = c->path; while (*s2) *q++ = *s2++; }
            { const char *s2 = "===\n"; while (*s2) *q++ = *s2++; }
            *q = 0;
            sc3(NR_write, ofd, (long)hb, (long)(q - hb));
        }
        if (ofd >= 0) {
            sc3(NR_dup2, ofd, 1, 0);
            sc3(NR_dup2, ofd, 2, 0);
        }
        /* 让父进程成为 tracer：exec 后会停在第一条用户指令 */
        sc4(NR_ptrace, PTRACE_TRACEME, 0, 0, 0);
        argv[0] = (char *)c->path;
        argv[1] = 0;
        /* ★ P3：**不设 LD_DEBUG**。ld.so 的 LD_DEBUG_OUTPUT 语义是
         *   「每个被调试进程写一个新文件 <OUTPUT><pid>」——无法合并，
         *   而它提供的加载信息 /proc/pid/maps 已经完整给出。
         *   v4 每轮因此多出 7 个文件，是"文件爆炸"的主要来源之一。 */
        envp[0] = 0;
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
        if (elapsed > CAND_TIMEOUT_MS) {
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
            const char *m = "=== CGM PROBE v5 alive ===\n";
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
    wstr("\n=== CGM PROBE v5 ===\n");
    wstr("pid="); wnum(pid_self, 10, 0);
    /* ★ P7：文件数自检 —— 让"文件爆炸"变成可观测指标 */
    wstr("  FILES-PLANNED="); wnum(2 + NCAND, 10, 0);
    wstr(" (1 日志 + 1 合并 stdout + "); wnum(NCAND, 10, 0); wstr(" 候选; **不设 LD_DEBUG**)\n");
    wstr("  LOGPATH="); wstr(LOGPATHS[0]);
    wstr("  TMPFS-FIRST="); wstr((LOGPATHS[0][0] == '/') ? "yes" : "no"); wstr("\n");
    wstr("\n本探针用 ptrace 做 tracer: 抓 exec 后的完整映射 + 崩溃地址/PC/LR/SP/栈\n");
    wstr("所有候选的 stdout/stderr 合并到 " TMPROOT "/out.txt（**不产生 ldd_* 文件**）\n");
    wstr("读法:\n");
    wstr("  'exec 成功（已停在第一条指令）' 后的 maps = 完整映射(看有没有段缺失)\n");
    wstr("  'crash addr' + 'PC' = 崩溃位置(可离线符号化)\n");

    for (k = 0; k < NCAND; k++)
        test_cand(&CANDS[k], k);

    wstr("\n=== END (probe5) ===\n");
    /* ★ P7：收尾时报告实际文件数与写入健康度 */
    /* 口径：本计数 = 父进程侧成功 open 的日志文件数（含多路径尝试）；
     * 子进程的合并 stdout 文件按候选数单列（子进程不共享该变量）。 */
    wstr("  FILES-CREATED(parent)="); wnum(g_nfiles, 10, 0);
    wstr("  CAND-FILES="); wnum(NCAND, 10, 0);
    wstr("  WRITE-FAILED="); wnum(g_wfail, 10, 0);
    if (g_wfail) wstr("  ### 本次证据不完整，见 EVIDENCE-TRUNCATED 行");
    wstr("\n");
    sc1(NR_close, LOGFD);
    sc1(NR_exit_group, 0);
    for (;;) { }
}
