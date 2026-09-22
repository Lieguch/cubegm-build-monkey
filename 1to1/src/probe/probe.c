/* ============================================================
 * probe.c —— **最小探针**（回答一个二元问题，不夹带任何其他东西）
 *
 * 要回答的问题
 * ---------------------------------------------------------------
 *   真机换成本产物后「无法开机 + `_diag/` 内零文件」。
 *   这个"零"有两种完全不同的成因，必须分开：
 *     (甲) **内核/ld.so 根本没 exec 成功** —— 我们的二进制一行都没跑
 *     (乙) **跑了，但一个字节都写不出去** —— 文件系统只读 / 路径不存在 / 权限
 *   本探针故意做成**极简**：静态链接、无 `.interp`、无 libc、无构造器、
 *   只用 `svc #0` 原始系统调用 ⇒ 把"能不能被 exec"和"能不能写文件"这两件事
 *   从被测对象的复杂度里**彻底剥离**。
 *
 * 设计要点（每一条都对应一个"否则就白测了"的陷阱）
 * ---------------------------------------------------------------
 *   · **多通道**：6 个不同挂载点的路径 + 追加不改名 + 重命名 + fd 1/2 + 帧缓冲。
 *     只要**任意一条**成功，就说明 (乙) 不成立 ⇒ 问题在别处。
 *   · **自描述输出**：写每个目标时把"到目前的尝试结果映射"一起写进去
 *     ⇒ 即使只有最后一个目标可写，也能看到前几个为什么失败。
 *   · **帧缓冲通道**（`/dev/fb0` 涂满）：完全绕开文件系统，**用户肉眼可见**。
 *     若屏幕变色 ⇒ 我们的代码确实执行了。
 *   · **不依赖任何可写目录**：`_diag/` 由投放包带过去，若它被删也能靠其他路径。
 *   · 退出用 `exit_group(0)`，不留悬挂进程。
 *
 * ★ 纪律：本文件**不 include 任何头文件**，常量自带（避免工具链头文件差异）；
 *   一切外部交互只经 `sc4()`（`svc #0`）。
 * ============================================================ */

/* ---- ARM EABI 系统调用号（自带，不依赖头文件）---- */
#define NR_write       4
#define NR_open        5
#define NR_close       6
#define NR_rename      38
#define NR_exit_group  248
#define NR_openat      322
#define NR_getpid      20
#define NR_gettimeofday 78

#define AT_FDCWD       (-100)
#define O_RDONLY       0
#define O_WRONLY       1
#define O_CREAT        0100
#define O_TRUNC        01000
#define O_APPEND       02000

#define E_OK   0

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

static int slen(const char *s) { int n = 0; while (s[n]) n++; return n; }

static void put(int fd, const char *s)
{
    if (fd >= 0) sc3(NR_write, fd, (long)s, slen(s));
}

/* 无 libc 的手写整数格式化（支持 10 与 16 进制） */
static char *fmt_ul(char *o, unsigned long v, int base, int width)
{
    char t[24]; int n = 0;
    if (!v) t[n++] = '0';
    while (v) { unsigned long d = v % (unsigned)base; t[n++] = (char)(d < 10 ? '0' + d : 'a' + d - 10); v /= (unsigned)base; }
    while (n < width) t[n++] = '0';
    while (n) *o++ = t[--n];
    return o;
}
static char *append(char *o, const char *s) { while (*s) *o++ = *s++; return o; }

/* 打开一个目标（尝试创建） */
static int open_new(const char *p)
{
    return (int)sc4(NR_openat, AT_FDCWD, (long)p, O_WRONLY | O_CREAT | O_TRUNC, 0644);
}
static int open_app(const char *p)
{
    return (int)sc4(NR_openat, AT_FDCWD, (long)p, O_WRONLY | O_APPEND, 0644);
}

/* ---- 目标清单：故意覆盖多个挂载点，看哪个可写 ---- */
struct tgt { const char *path; int used; long rc; };

static struct tgt TGT[] = {
    { "/sdcard/cubegm/_diag/PROBE.txt", 0, 0 },
    { "/sdcard/cubegm/PROBE.txt",       0, 0 },
    { "/sdcard/PROBE.txt",              0, 0 },
    { "/tmp/PROBE.txt",                 0, 0 },
    { "/data/PROBE.txt",                0, 0 },
    { "/mnt/PROBE.txt",                 0, 0 },
    { "/PROBE.txt",                     0, 0 },
};
#define NTGT ((int)(sizeof(TGT) / sizeof(TGT[0])))

static char g_buf[1600];

void probe_main(void)
{
    char *o;
    int i;

    /* ① 先尝试直接写 fd 1 / fd 2（也许设备有控制台） */
    put(1, "\n[PROBE] cubegm rkgame probe v1 alive\n");
    put(2, "\n[PROBE] cubegm rkgame probe v1 alive (stderr)\n");

    /* ② 逐个目标：打开 → 把"到目前为止的全部尝试结果"写进去
     *    ⇒ 即使只有最后一个目标可写，也能看到前面每个为什么失败 */
    for (i = 0; i < NTGT; i++) {
        int fd = open_new(TGT[i].path);
        TGT[i].used = (fd >= 0);
        TGT[i].rc = fd;
        if (fd < 0)
            continue;
        o = g_buf;
        o = append(o, "=== CGM PROBE v1 ===\n");
        o = append(o, "pid=");   o = fmt_ul(o, (unsigned long)sc1(NR_getpid, 0), 10, 0);
        o = append(o, "  target_index="); o = fmt_ul(o, (unsigned long)i, 10, 0);
        o = append(o, "\n");
        o = append(o, "含义：本文件存在 ⇒ (a) 内核能 exec 我们的产物，(b) 该路径可写。\n");
        o = append(o, "逐目标结果（rc = openat 返回码，<0 即失败）：\n");
        for (int k = 0; k < NTGT; k++) {
            o = append(o, "  [");
            o = fmt_ul(o, (unsigned long)k, 10, 0);
            o = append(o, "] ");
            o = append(o, TGT[k].path);
            o = append(o, "  rc=");
            if (TGT[k].rc < 0) { *o++ = '-'; o = fmt_ul(o, (unsigned long)(-TGT[k].rc), 10, 0); }
            else               { o = fmt_ul(o, (unsigned long)TGT[k].rc, 10, 0); }
            o = append(o, "\n");
        }
        o = append(o, "=== END ===\n");
        sc3(NR_write, fd, (long)g_buf, (long)(o - g_buf));
        sc1(NR_close, fd);
    }

    /* ③ 追加通道：不改名不动现有内容，只往 cfg.ini 尾巴上加一行 */
    {
        int fd = open_app("/sdcard/cubegm/_diag/cfg.ini");
        if (fd >= 0) {
            put(fd, "# PROBE v1 reached here (append channel OK)\n");
            sc1(NR_close, fd);
        }
    }

    /* ④ 重命名通道：把探针自己刚写的文件改名（证明不仅能创建、还能改目录项） */
    sc3(NR_rename, (long)"/sdcard/cubegm/_diag/PROBE.txt",
                   (long)"/sdcard/cubegm/_diag/PROBE.renamed.txt", 0);

    /* ⑤ 帧缓冲通道：**完全绕开文件系统**，用户肉眼可见
     *    （若装有 fbdev；DRM 独占显示时此路不通，但试一次几乎无成本） */
    {
        int fbfd = (int)sc4(NR_openat, AT_FDCWD, (long)"/dev/fb0", O_WRONLY, 0);
        if (fbfd >= 0) {
            long i2;
            for (i2 = 0; i2 < (long)sizeof(g_buf); i2++) g_buf[i2] = (char)0xFF;
            for (i2 = 0; i2 < 160; i2++)          /* 160 × 1600 ≈ 256 KB 全 0xFF */
                sc3(NR_write, fbfd, (long)g_buf, (long)sizeof(g_buf));
            sc1(NR_close, fbfd);
        }
    }

    /* ⑥ 收尾：也往 fd 1/2 报一声（若之前有控制台就能看到） */
    put(1, "[PROBE] done, exiting 0\n");
    put(2, "[PROBE] done, exiting 0\n");
}
