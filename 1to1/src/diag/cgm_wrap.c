/* ============================================================
 * cgm_wrap.c —— 链接期 libc 拦截（-Wl,--wrap=<sym>）
 *
 * 为什么用 --wrap 而不是 LD_PRELOAD
 * ---------------------------------------------------------------
 * 设备启动链（U-Boot→…→S80icube→icube→rkgame）全是原厂文件，**红线不可动**
 * ⇒ 没有任何地方能给我们注入 LD_PRELOAD / 环境变量。
 * 而 `--wrap` 是**链接期**重定向：链接器把所有指向 `open` 的引用改指 `__wrap_open`，
 * 我们转发给 `__real_open`（真 libc）。**零源码改动、零环境依赖**。
 *
 * 覆盖范围（按"设备上最可能出问题的地方"排序）
 *   1. 启动     __libc_start_main            ← 最早钩子（早于 main / 构造器）
 *   2. 文件     open/open64/openat/fopen/close/read/write/lseek/fread/fwrite/
 *               fseek/ftell/opendir/readdir/access/stat/fstat/mkdir/unlink/rename/
 *               chdir/readlink/realpath/remove/rmdir/getcwd/statfs/ftruncate
 *   3. 设备     ioctl ★（DRM/KMS、ALSA、evdev 全走 ioctl）
 *               fcntl / mmap / munmap / poll / select
 *   4. 动态库   dlopen/dlsym/dlclose ★（看 driver.so 到底被解析了哪些符号）
 *   5. 进程     fork/vfork/execve/system/popen/exit/_exit/abort
 *   6. 线程     pthread_create/join/mutex_lock/cond_wait/sem_wait
 *   7. 时间     nanosleep/usleep/sleep/clock_gettime/gettimeofday
 *
 * 纪律：转发**必须先调用再记日志**（保证不改变时序语义）；
 *       本文件内部一律经 cgm_putline（其内部只用 syscall）⇒ 无递归。
 * ============================================================ */
#include "cgm_diag.h"

#include <stdarg.h>
#include <stdio.h>
#include <fcntl.h>
#include <dlfcn.h>
#include <pthread.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <dirent.h>
#include <poll.h>
#include <signal.h>
#include <sys/time.h>
#include <sys/vfs.h>
#include <sys/select.h>
#include <time.h>

extern void cgm_putline(const char *tag, const char *fmt, ...);
extern void cgm_tick_public(void);
extern void cgm_bump(const char *nm);

#define LOG(...)  cgm_putline(__VA_ARGS__)
#define TICK()    cgm_tick_public()

/* 日志上限：路径只记前 180 字符（避免超长行把 trace.log 撑爆） */
#define PN(p) ((p) ? (p) : "(null)")

/* ================= 1. 启动钩子（最早） ================= */
typedef int (*main_fn_t)(int, char **, char **);
extern int __real___libc_start_main(main_fn_t, int, char **, void (*)(void),
                                    void (*)(void), void (*)(void), void *);

int __wrap___libc_start_main(main_fn_t main_fn, int argc, char **ubp_av,
                             void (*init)(void), void (*fini)(void),
                             void (*rtld_fini)(void), void *stack_end)
{
    cgm_diag_boot("libc_start_main");
    LOG("BOOT", "enter argc=%d argv0=\"%s\"", argc, (argc > 0 && ubp_av) ? ubp_av[0] : "?");
    TICK();
    int r = __real___libc_start_main(main_fn, argc, ubp_av, init, fini, rtld_fini, stack_end);
    LOG("MAIN", "returned rc=%d", r);
    return r;
}

__attribute__((constructor)) static void cgm_ctor(void)
{
    cgm_diag_boot("ctor");
}

/* ================= 2. 进程退出 ================= */
void __real_exit(int);
void __wrap_exit(int c) { cgm_lifecycle("EXIT", c); __real_exit(c); }
void __real__exit(int);
void __wrap__exit(int c) { cgm_lifecycle("_EXIT", c); __real__exit(c); }
void __real_abort(void);
void __wrap_abort(void) { cgm_lifecycle("ABORT", 0); __real_abort(); }

/* ================= 3. 文件 ================= */
int __real_open(const char *, int, ...);
int __wrap_open(const char *p, int fl, ...)
{
    va_list ap; va_start(ap, fl); int mode = va_arg(ap, int); va_end(ap);
    int r = __real_open(p, fl, mode);
    LOG("IO", "open  \"%s\" fl=0x%x ret=%d", PN(p), fl, r);
    cgm_bump("open"); TICK();
    return r;
}
int __real_open64(const char *, int, ...);
int __wrap_open64(const char *p, int fl, ...)
{
    va_list ap; va_start(ap, fl); int mode = va_arg(ap, int); va_end(ap);
    int r = __real_open64(p, fl, mode);
    LOG("IO", "open64 \"%s\" fl=0x%x ret=%d", PN(p), fl, r);
    cgm_bump("open64"); TICK();
    return r;
}
int __real_openat(int, const char *, int, ...);
int __wrap_openat(int dfd, const char *p, int fl, ...)
{
    va_list ap; va_start(ap, fl); int mode = va_arg(ap, int); va_end(ap);
    int r = __real_openat(dfd, p, fl, mode);
    LOG("IO", "openat dfd=%d \"%s\" fl=0x%x ret=%d", dfd, PN(p), fl, r);
    cgm_bump("openat"); TICK();
    return r;
}
FILE *__real_fopen(const char *, const char *);
FILE *__wrap_fopen(const char *p, const char *m)
{
    FILE *f = __real_fopen(p, m);
    LOG("IO", "fopen \"%s\" mode=\"%s\" ret=%p", PN(p), PN(m), (void *)f);
    cgm_bump("fopen"); TICK();
    return f;
}
FILE *__real_fopen64(const char *, const char *);
FILE *__wrap_fopen64(const char *p, const char *m)
{
    FILE *f = __real_fopen64(p, m);
    LOG("IO", "fopen64 \"%s\" mode=\"%s\" ret=%p", PN(p), PN(m), (void *)f);
    cgm_bump("fopen64"); TICK();
    return f;
}
int __real_fclose(FILE *);
int __wrap_fclose(FILE *f)
{
    int r = __real_fclose(f);
    LOG("IO", "fclose %p ret=%d", (void *)f, r);
    cgm_bump("fclose");
    return r;
}
int __real_close(int);
int __wrap_close(int fd)
{
    int r = __real_close(fd);
    if (cgm_want(CGM_LVL_CORE)) { LOG("IO", "close fd=%d ret=%d", fd, r); cgm_bump("close"); }
    return r;
}
ssize_t __real_read(int, void *, size_t);
ssize_t __wrap_read(int fd, void *b, size_t n)
{
    ssize_t r = __real_read(fd, b, n);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "read  fd=%d req=%u ret=%d", fd, (unsigned)n, (int)r); cgm_bump("read"); }
    TICK();
    return r;
}
ssize_t __real_write(int, const void *, size_t);
ssize_t __wrap_write(int fd, const void *b, size_t n)
{
    ssize_t r = __real_write(fd, b, n);
    if (cgm_want(CGM_LVL_IO) && fd != 1 && fd != 2)
        { LOG("IO", "write fd=%d req=%u ret=%d", fd, (unsigned)n, (int)r); cgm_bump("write"); }
    return r;
}
size_t __real_fread(void *, size_t, size_t, FILE *);
size_t __wrap_fread(void *b, size_t sz, size_t n, FILE *f)
{
    size_t r = __real_fread(b, sz, n, f);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "fread %p sz=%u n=%u ret=%u", (void *)f, (unsigned)sz, (unsigned)n, (unsigned)r); cgm_bump("fread"); }
    TICK();
    return r;
}
size_t __real_fwrite(const void *, size_t, size_t, FILE *);
size_t __wrap_fwrite(const void *b, size_t sz, size_t n, FILE *f)
{
    size_t r = __real_fwrite(b, sz, n, f);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "fwrite %p sz=%u n=%u ret=%u", (void *)f, (unsigned)sz, (unsigned)n, (unsigned)r); cgm_bump("fwrite"); }
    return r;
}
off_t __real_lseek(int, off_t, int);
off_t __wrap_lseek(int fd, off_t o, int w)
{
    off_t r = __real_lseek(fd, o, w);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "lseek fd=%d off=%ld whence=%d ret=%ld", fd, (long)o, w, (long)r); cgm_bump("lseek"); }
    return r;
}
long __real_lseek64(int, long long, int);
long __wrap_lseek64(int fd, long long o, int w)
{
    long r = __real_lseek64(fd, o, w);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "lseek64 fd=%d off=%lld whence=%d ret=%ld", fd, o, w, r); cgm_bump("lseek64"); }
    return r;
}
int __real_fseek(FILE *, long, int);
int __wrap_fseek(FILE *f, long o, int w)
{
    int r = __real_fseek(f, o, w);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "fseek %p off=%ld whence=%d ret=%d", (void *)f, o, w, r); cgm_bump("fseek"); }
    return r;
}
long __real_ftell(FILE *);
long __wrap_ftell(FILE *f)
{
    long r = __real_ftell(f);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "ftell %p ret=%ld", (void *)f, r); cgm_bump("ftell"); }
    return r;
}
int __real_access(const char *, int);
int __wrap_access(const char *p, int m)
{
    int r = __real_access(p, m);
    LOG("IO", "access \"%s\" mode=0x%x ret=%d", PN(p), m, r);
    cgm_bump("access");
    return r;
}
int __real_stat(const char *, struct stat *);
int __wrap_stat(const char *p, struct stat *s)
{
    int r = __real_stat(p, s);
    LOG("IO", "stat \"%s\" ret=%d%s", PN(p), r,
        (r == 0) ? "" : "  <== MISSING");
    cgm_bump("stat");
    return r;
}
int __real_lstat(const char *, struct stat *);
int __wrap_lstat(const char *p, struct stat *s)
{
    int r = __real_lstat(p, s);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "lstat \"%s\" ret=%d", PN(p), r); cgm_bump("lstat"); }
    return r;
}
int __real_fstat(int, struct stat *);
int __wrap_fstat(int fd, struct stat *s)
{
    int r = __real_fstat(fd, s);
    if (cgm_want(CGM_LVL_IO)) { LOG("IO", "fstat fd=%d ret=%d size=%ld", fd, r, (r == 0) ? (long)s->st_size : -1L); cgm_bump("fstat"); }
    return r;
}
int __real_mkdir(const char *, mode_t);
int __wrap_mkdir(const char *p, mode_t m)
{
    int r = __real_mkdir(p, m);
    LOG("IO", "mkdir \"%s\" ret=%d", PN(p), r);
    cgm_bump("mkdir");
    return r;
}
int __real_unlink(const char *);
int __wrap_unlink(const char *p) { int r = __real_unlink(p); LOG("IO", "unlink \"%s\" ret=%d", PN(p), r); cgm_bump("unlink"); return r; }
int __real_remove(const char *);
int __wrap_remove(const char *p) { int r = __real_remove(p); LOG("IO", "remove \"%s\" ret=%d", PN(p), r); cgm_bump("remove"); return r; }
int __real_rename(const char *, const char *);
int __wrap_rename(const char *a, const char *b) { int r = __real_rename(a, b); LOG("IO", "rename \"%s\" -> \"%s\" ret=%d", PN(a), PN(b), r); cgm_bump("rename"); return r; }
int __real_chdir(const char *);
int __wrap_chdir(const char *p) { int r = __real_chdir(p); LOG("IO", "chdir \"%s\" ret=%d", PN(p), r); cgm_bump("chdir"); return r; }
char *__real_getcwd(char *, size_t);
char *__wrap_getcwd(char *b, size_t n) { char *r = __real_getcwd(b, n); LOG("IO", "getcwd \"%s\" ret=%p", PN(r), (void *)r); cgm_bump("getcwd"); return r; }
ssize_t __real_readlink(const char *, char *, size_t);
ssize_t __wrap_readlink(const char *p, char *b, size_t n)
{
    ssize_t r = __real_readlink(p, b, n);
    LOG("IO", "readlink \"%s\" ret=%d", PN(p), (int)r);
    cgm_bump("readlink");
    return r;
}
char *__real_realpath(const char *, char *);
char *__wrap_realpath(const char *p, char *b) { char *r = __real_realpath(p, b); LOG("IO", "realpath \"%s\" -> \"%s\"", PN(p), PN(r)); cgm_bump("realpath"); return r; }
DIR *__real_opendir(const char *);
DIR *__wrap_opendir(const char *p) { DIR *d = __real_opendir(p); LOG("IO", "opendir \"%s\" ret=%p", PN(p), (void *)d); cgm_bump("opendir"); TICK(); return d; }
struct dirent *__real_readdir(DIR *);
struct dirent *__wrap_readdir(DIR *d) { struct dirent *e = __real_readdir(d); if (cgm_want(CGM_LVL_IO) && e) LOG("IO", "readdir \"%s\"", PN(e->d_name)); cgm_bump("readdir"); return e; }
int __real_closedir(DIR *);
int __wrap_closedir(DIR *d) { int r = __real_closedir(d); if (cgm_want(CGM_LVL_CORE)) LOG("IO", "closedir %p ret=%d", (void *)d, r); cgm_bump("closedir"); return r; }
int __real_ftruncate(int, off_t);
int __wrap_ftruncate(int fd, off_t n) { int r = __real_ftruncate(fd, n); LOG("IO", "ftruncate fd=%d n=%ld ret=%d", fd, (long)n, r); cgm_bump("ftruncate"); return r; }

/* ================= 4. 设备（ioctl ★ / mmap / 轮询） ================= */
int __real_ioctl(int, unsigned long, ...);
int __wrap_ioctl(int fd, unsigned long req, ...)
{
    va_list ap; va_start(ap, req); void *a = va_arg(ap, void *); va_end(ap);
    if (cgm_want(CGM_LVL_FULL)) {
        cgm_bump("ioctl");
    }
    int r = __real_ioctl(fd, req, a);
    if (cgm_want(CGM_LVL_CORE)) LOG("IO", "ioctl fd=%d req=0x%08lx ret=%d", fd, req, r);
    TICK();
    return r;
}
int __real_fcntl(int, int, ...);
int __wrap_fcntl(int fd, int cmd, ...)
{
    va_list ap; va_start(ap, cmd); void *a = va_arg(ap, void *); va_end(ap);
    int r = __real_fcntl(fd, cmd, a);
    if (cgm_want(CGM_LVL_CORE)) LOG("IO", "fcntl fd=%d cmd=0x%x ret=0x%x", fd, cmd, r);
    return r;
}
void *__real_mmap(void *, size_t, int, int, int, off_t);
void *__wrap_mmap(void *a, size_t l, int pr, int fl, int fd, off_t o)
{
    void *r = __real_mmap(a, l, pr, fl, fd, o);
    LOG("IO", "mmap len=%u prot=0x%x flags=0x%x fd=%d off=%ld ret=%p%s",
        (unsigned)l, pr, fl, fd, (long)o, r, (r == MAP_FAILED) ? "  <== FAIL" : "");
    cgm_bump("mmap"); TICK();
    return r;
}
int __real_munmap(void *, size_t);
int __wrap_munmap(void *a, size_t l) { int r = __real_munmap(a, l); if (cgm_want(CGM_LVL_IO)) LOG("IO", "munmap %p len=%u ret=%d", a, (unsigned)l, r); return r; }
int __real_poll(struct pollfd *, nfds_t, int);
int __wrap_poll(struct pollfd *f, nfds_t n, int t)
{
    int r = __real_poll(f, n, t);
    if (cgm_want(CGM_LVL_CORE)) LOG("IO", "poll n=%u timeout=%d ret=%d", (unsigned)n, t, r);
    TICK();
    return r;
}

/* ================= 5. 动态库（driver.so 到底解析了什么） ================= */
void *__real_dlopen(const char *, int);
void *__wrap_dlopen(const char *p, int m)
{
    void *h = __real_dlopen(p, m);
    LOG("DL", "dlopen \"%s\" flags=0x%x ret=%p%s", PN(p), m, h, h ? "" : "  <== FAIL");
    cgm_bump("dlopen"); TICK();
    return h;
}
void *__real_dlsym(void *, const char *);
void *__wrap_dlsym(void *h, const char *s)
{
    void *r = __real_dlsym(h, s);
    LOG("DL", "dlsym \"%s\" -> %p%s", PN(s), r, r ? "" : "  <== MISSING");
    cgm_bump("dlsym");
    return r;
}
int __real_dlclose(void *);
int __wrap_dlclose(void *h) { int r = __real_dlclose(h); LOG("DL", "dlclose %p ret=%d", h, r); return r; }
char *__real_dlerror(void);
char *__wrap_dlerror(void) { char *e = __real_dlerror(); if (e) LOG("DL", "dlerror \"%s\"", e); return e; }

/* ================= 6. 进程 / 线程 ================= */
pid_t __real_fork(void);
pid_t __wrap_fork(void) { pid_t r = __real_fork(); LOG("TH", "fork ret=%d", (int)r); return r; }
int __real_execve(const char *, char *const[], char *const[]);
int __wrap_execve(const char *p, char *const a[], char *const e[])
{
    LOG("TH", "execve \"%s\"", PN(p));
    int r = __real_execve(p, a, e);
    LOG("TH", "execve ret=%d", r);
    return r;
}
int __real_system(const char *);
int __wrap_system(const char *c) { LOG("TH", "system \"%s\"", PN(c)); int r = __real_system(c); LOG("TH", "system ret=%d", r); return r; }
FILE *__real_popen(const char *, const char *);
FILE *__wrap_popen(const char *c, const char *m) { LOG("TH", "popen \"%s\" \"%s\"", PN(c), PN(m)); FILE *r = __real_popen(c, m); LOG("TH", "popen ret=%p", (void *)r); return r; }
int __real_pthread_create(pthread_t *, const pthread_attr_t *, void *(*)(void *), void *);
int __wrap_pthread_create(pthread_t *t, const pthread_attr_t *a, void *(*fn)(void *), void *arg)
{
    int r = __real_pthread_create(t, a, fn, arg);
    LOG("TH", "pthread_create fn=%p arg=%p ret=%d", (void *)fn, arg, r);
    cgm_bump("pthread_create");
    return r;
}
int __real_pthread_join(pthread_t, void **);
int __wrap_pthread_join(pthread_t t, void **r) { int k = __real_pthread_join(t, r); LOG("TH", "pthread_join ret=%d", k); return k; }
int __real_pthread_mutex_lock(pthread_mutex_t *);
int __wrap_pthread_mutex_lock(pthread_mutex_t *m)
{
    if (cgm_want(CGM_LVL_FULL)) LOG("TH", "mutex_lock %p …", (void *)m);
    int r = __real_pthread_mutex_lock(m);
    if (cgm_want(CGM_LVL_FULL)) LOG("TH", "mutex_lock %p ret=%d", (void *)m, r);
    return r;
}
int __real_pthread_cond_wait(pthread_cond_t *, pthread_mutex_t *);
int __wrap_pthread_cond_wait(pthread_cond_t *c, pthread_mutex_t *m)
{
    if (cgm_want(CGM_LVL_CORE)) LOG("TH", "cond_wait %p …", (void *)c);
    int r = __real_pthread_cond_wait(c, m);
    if (cgm_want(CGM_LVL_CORE)) LOG("TH", "cond_wait %p ret=%d", (void *)c, r);
    return r;
}

/* ================= 7. 时间（区分"忙等"与"真睡"） ================= */
int __real_nanosleep(const struct timespec *, struct timespec *);
int __wrap_nanosleep(const struct timespec *a, struct timespec *b)
{
    if (cgm_want(CGM_LVL_CORE) && a) LOG("TM", "nanosleep %ld.%09ld", (long)a->tv_sec, (long)a->tv_nsec);
    return __real_nanosleep(a, b);
}
int __real_usleep(useconds_t);
int __wrap_usleep(useconds_t u) { if (cgm_want(CGM_LVL_CORE)) LOG("TM", "usleep %u", (unsigned)u); cgm_bump("usleep"); return __real_usleep(u); }
unsigned int __real_sleep(unsigned int);
unsigned int __wrap_sleep(unsigned int s) { LOG("TM", "sleep %u", s); return __real_sleep(s); }
int __real_gettimeofday(struct timeval *, void *);
int __wrap_gettimeofday(struct timeval *t, void *z) { return __real_gettimeofday(t, z); }

/* ================= 8. 信号（看谁改了处理函数） ================= */
/* zig/clang 的 <signal.h> 里没有 sighandler_t（那是 glibc 扩展）⇒ 展开写 */
void (*__real_signal(int, void (*)(int)))(int);
void (*__wrap_signal(int s, void (*h)(int)))(int)
{
    void (*r)(int) = __real_signal(s, h);
    LOG("SG", "signal sig=%d handler=%p (glibc installs %p)", s, (void *)h, (void *)r);
    return r;
}
int __real_raise(int);
int __wrap_raise(int s) { LOG("SG", "raise sig=%d", s); return __real_raise(s); }
unsigned int __real_alarm(unsigned int);
unsigned int __wrap_alarm(unsigned int s) { LOG("SG", "alarm %u", s); return __real_alarm(s); }

/* ================= 9. 补齐项 =================
 * ★ 教训（2026-09-21）：`tools/build_diag.sh` 的 WRAPS 列表与本文件的实现**必须一一对应**，
 *   少一个就是 `ld.lld: error: undefined symbol: __wrap_xxx` 的**硬失败**。
 *   这次它就是这么逮住我的（fflush/statfs/select/vfork/clock_gettime/sigaction 六个漏了）。
 *   硬失败是对的 —— 若这里静默降级，设备上就会出现"以为在拦、其实没拦"的假日志。
 */
int __real_fflush(FILE *);
int __wrap_fflush(FILE *f)
{
    int r = __real_fflush(f);
    if (cgm_want(CGM_LVL_IO)) LOG("IO", "fflush %p ret=%d", (void *)f, r);
    return r;
}
int __real_statfs(const char *, struct statfs *);
int __wrap_statfs(const char *p, struct statfs *s)
{
    int r = __real_statfs(p, s);
    if (r == 0 && cgm_want(CGM_LVL_CORE))
        LOG("IO", "statfs \"%s\" bsize=%ld blocks=%ld bfree=%ld bavail=%ld",
            PN(p), (long)s->f_bsize, (long)s->f_blocks, (long)s->f_bfree, (long)s->f_bavail);
    else if (r != 0)
        LOG("IO", "statfs \"%s\" ret=%d  <== FAIL", PN(p), r);
    return r;
}
int __real_select(int, fd_set *, fd_set *, fd_set *, struct timeval *);
int __wrap_select(int n, fd_set *r, fd_set *w, fd_set *e, struct timeval *t)
{
    int k = __real_select(n, r, w, e, t);
    if (cgm_want(CGM_LVL_CORE)) LOG("IO", "select nfds=%d ret=%d", n, k);
    TICK();
    return k;
}
pid_t __real_vfork(void);
pid_t __wrap_vfork(void) { pid_t r = __real_vfork(); LOG("TH", "vfork ret=%d", (int)r); return r; }
int __real_clock_gettime(int, struct timespec *);
int __wrap_clock_gettime(int clk, struct timespec *ts)
{
    /* ★ 极高频率：只在 level=3 记每一次，否则只计数（避免把 trace.log 撑爆） */
    if (cgm_want(CGM_LVL_FULL))
        LOG("TM", "clock_gettime clk=%d", clk);
    cgm_bump("cgettime");
    return __real_clock_gettime(clk, ts);
}
int __real_sigaction(int, const struct sigaction *, struct sigaction *);
int __wrap_sigaction(int s, const struct sigaction *n, struct sigaction *o)
{
    int r = __real_sigaction(s, n, o);
    LOG("SG", "sigaction sig=%d handler=%p flags=0x%x ret=%d", s,
        n ? (void *)n->sa_handler : 0, n ? (unsigned)n->sa_flags : 0, r);
    return r;
}
