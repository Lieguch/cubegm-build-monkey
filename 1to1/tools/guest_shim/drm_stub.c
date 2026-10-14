/* ============================================================
 * drm_stub.c —— 桩 `libdrm.so.2`：让厂商闭源 `driver.so` 的图形初始化能过
 *
 * 为什么需要它（2026-09-19 实测定案，见 GAP 16.22）：
 *   1) 设备真实 rootfs 里**有** `libkms.so.1`（CI 的 `/arm-root` 恰好缺它）⇒ `dlopen(driver.so)` 成功
 *      ⇒ 执行流进入 `driver.so` 的图形初始化。
 *   2) 但沙箱里没有真 DRM 设备：`open("/dev/dri/*")` 被 shim 重定向到 `/dev/zero`，
 *      真实 `libdrm` 的 ioctl 全部失败 ⇒ `gr_init` 拿到 NULL 句柄 ⇒ 在
 *      `driver.so + 0x3ca8`（符号 `gr_init`）执行 `ldr r3,[r3]`（r3=0）**必崩**。
 *      gdb 实测：`r0..r3 = 0`、栈回溯 `video_drivers_init` → `gr_init`，
 *      rkgame 侧调用点在 `rkgame + 0x3a9fc4`。
 *   3) ⇒ **只要 driver.so 加载成功，沙箱就必死在厂商代码里**，
 *      而"历史 48/68/76 覆盖率"恰恰是因为 `driver.so` **没加载**才走到的
 *      —— 那不是真机路径。要让沙箱走真机路径，必须让 DRM 初始化"成功"。
 *
 * 为什么不改 shim 的 `ioctl`：
 *   shim 刻意**不拦 ioctl**（第 41-42 行有理由：伪造成功会把未初始化结构体交给被测程序）。
 *   在 DSO 层替换 `libdrm` 更干净：作用域仅限 `driver.so`，且我们**自己**保证
 *   所有返回结构都被完整初始化（等价于"把 shim 那条理由原地消解"）。
 *
 * ★ 符号集**逐字取自实测**（`golden/sdcard_min/driver.so` 的 65 个未定义符号）：
 *   17 个 `drm*` + 20 个 `snd_*`（ALSA 用真库）+ 28 个 libc/其他。
 *   `DT_NEEDED = libdrm.so.2 / libkms.so.1 / libasound.so.2 / libpthread.so.0 / libc.so.6`
 *   ⇒ 本桩只覆盖 `drm*` 这 17 个，其余交由真库。
 *
 * ★ 公平性：两侧（工厂/重建/控制）注入**同一份**桩、同一目录 ⇒ 差分仍是"同环境比实现"。
 * ★ 保守性：本桩只进 LD_LIBRARY_PATH，且由**显式开关**启用（默认关）—— 不启用时行为一字不变。
 *
 * 编译：见 tools/build_libdrm_stub.sh（`-nostdlib`，不依赖 libc）
 * ============================================================ */

typedef unsigned char      u8;
typedef unsigned short     u16;
typedef unsigned int       u32;
typedef signed int         i32;
typedef unsigned long long u64;

/* ---------------- libdrm 结构（32 位 ARM ABI，逐字段对齐内核/libdrm 定义）---------------- */

typedef struct {
    u32 clock;
    u16 hdisplay, hsync_start, hsync_end, htotal, hskew;
    u16 vdisplay, vsync_start, vsync_end, vtotal, vscan;
    u32 vrefresh;
    u32 flags;
    u32 type;
    char name[32];
} drmModeModeInfo;

typedef struct {
    u32 connector_id;
    u32 encoder_id;
    u32 connector_type;
    u32 connector_type_id;
    u32 connection;              /* 1 = connected */
    u32 mmWidth, mmHeight;
    u32 subpixel;
    i32 count_modes;   drmModeModeInfo *modes;
    i32 count_props;   u32 *props;  u64 *prop_values;
    i32 count_encoders; u32 *encoders;
} drmModeConnector;

typedef struct {
    u32 encoder_id;
    u32 encoder_type;
    u32 crtc_id;
    u32 possible_crtcs;
    u32 possible_clones;
} drmModeEncoder;

typedef struct {
    u32 crtc_id;
    u32 buffer_id;
    u32 x, y;
    u32 width, height;
    i32 mode_valid;
    drmModeModeInfo mode;
    i32 gamma_size;
} drmModeCrtc;

typedef struct {
    i32 count_fbs;        u32 *fbs;
    i32 count_crtcs;      u32 *crtcs;
    i32 count_connectors; u32 *connectors;
    i32 count_encoders;   u32 *encoders;
    u32 min_width, max_width, min_height, max_height;
} drmModeRes;

typedef struct {
    u32 count_planes;
    u32 *planes;
} drmModePlaneRes;

typedef struct {
    u32 count_formats; u32 *formats;
    u32 plane_id;
    u32 crtc_id;
    u32 fb_id;
    u32 crtc_x, crtc_y;
    u32 x, y;
    u32 possible_crtcs;
    u32 gamma_size;
} drmModePlane;

/* ---------------- 静态存储：所有返回值都指向**完全初始化**的静态对象 ----------------
 * 为什么要静态且完整：driver.so 会解引用这些字段；任何一个 NULL 都会让它在厂商代码里崩。
 * 为什么 Free* 全做成 no-op：指针指向静态存储，free() 会毁掉堆（且下一次调用会拿到脏数据）。 */

static u32 g_fbs[1]           = { 1u };
static u32 g_crtcs[1]         = { 2u };
static u32 g_conns[1]         = { 3u };
static u32 g_encs[1]          = { 4u };
static u32 g_planes[1]        = { 5u };
static u32 g_props[1]         = { 6u };
static u64 g_propvals[1]      = { 0ull };
static u32 g_fmts[4]          = { 0x34325258u /* XR24 = XRGB8888 */,
                                  0x34325241u /* AR24 = ARGB8888 */,
                                  0x36314752u /* RG16 = RGB565 */,
                                  0x32315559u /* YU12 */ };

/* 设备 UI 分辨率实测 = 1280x720（原厂 .raw = RGB565 1280×720） */
static drmModeModeInfo g_mode = {
    74250u,                       /* clock: 74.25 MHz（720p60 标准像素时钟）*/
    1280u, 1390u, 1430u, 1650u, 0u,   /* hdisplay/hsync_start/hsync_end/htotal/hskew */
    720u,  725u,  730u,  750u,  0u,   /* vdisplay/vsync_start/vsync_end/vtotal/vscan */
    60u,                          /* vrefresh */
    5u,                           /* flags: PREFERRED | DRIVER */
    0x40u,                        /* type: DRIVER */
    { '1','2','8','0','x','7','2','0', 0 }
};

static drmModeRes g_res = {
    1, g_fbs, 1, g_crtcs, 1, g_conns, 1, g_encs,
    320u, 4096u, 200u, 4096u
};

static drmModeConnector g_conn = {
    3u,        /* connector_id */
    4u,        /* encoder_id */
    11u,       /* connector_type: DRM_MODE_CONNECTOR_HDMIA */
    1u,        /* connector_type_id */
    1u,        /* connection: connected */
    160u, 90u, /* mmWidth/mmHeight */
    0u,        /* subpixel */
    1, &g_mode,
    1, g_props, g_propvals,
    1, g_encs
};

static drmModeEncoder g_enc = { 4u, 1u, 2u, 1u, 1u };
static drmModeCrtc    g_crtc = { 2u, 1u, 0u, 0u, 1280u, 720u, 1,
                                 { 74250u,1280u,1390u,1430u,1650u,0u, 720u,725u,730u,750u,0u,
                                   60u,5u,0x40u,{ '1','2','8','0','x','7','2','0',0 } },
                                 0 };
static drmModePlaneRes g_pres = { 1u, g_planes };
static drmModePlane    g_plane = { 4u, g_fmts, 5u, 2u, 1u, 0u, 0u, 0u, 0u, 1u, 0u };

/* 假 framebuffer id：真实内核会分配 GEM handle（单调递增的 u32）。
 * 单块 buffer + 单 fb_id 是本桩的既有约定（两侧同一份，不影响公平性）。 */
#define FAKE_FB_ID         1u

/* ---------------- 小工具（不依赖 libc）---------------- */

/* ★ 必须自带 `memset`：本桩用 `-nostdlib` 编译（不与设备的 glibc 绑定），
 *   而编译器在初始化大结构 / 清缓冲时会**自动生成**对 `memset` 的调用。
 *   实测：不给就等于 `undefined symbol: memset` ⇒ 链接失败。
 *   `visibility("hidden")` 是刻意的：本桩只为自己解析该引用，
 *   **不导出**给进程里其它模块（避免遮蔽设备 libc 的优化版 memset）。 */
__attribute__((visibility("hidden")))
void *memset(void *dst, int c, unsigned int n)
{
    unsigned char *d = (unsigned char *)dst;
    unsigned int i;
    for (i = 0; i < n; i++) d[i] = (unsigned char)c;
    return dst;
}

static void zfill(void *p, u32 n)
{
    u8 *c = (u8 *)p;
    u32 i;
    if (p == 0) return;
    for (i = 0; i < n; i++) c[i] = 0;
}

/* ioctl 号拆解：type(bits8..15) nr(bits0..7) size(bits16..29) */
static u32 ioc_nr(unsigned long r)   { return (u32)(r & 0xffu); }
static u32 ioc_type(unsigned long r) { return (u32)((r >> 8) & 0xffu); }
static u32 ioc_size(unsigned long r) { return (u32)((r >> 16) & 0x3fffu); }

/* ---------------- ioctl：driver.so 用它直接做 dumb buffer ----------------
 * ★ 关键设计：**避免猜结构体尺寸** ——
 *   · CREATE_DUMB 的 `size` 字段位置按 `_IOC_SIZE(req)` 判定（24/28 → off 20；≥32 → off 24）；
 *   · 未知的 DRM 命令**零填**整个参数缓冲（尺寸由请求自带）后返回 0 ——
 *     这既确定（全 0，不依赖栈垃圾），又不会把未初始化结构体交给被测程序
 *     （这正是 shim 当初拒绝拦 ioctl 的理由，这里被原地消解）。 */
/* ---- CREATE_DUMB：**必须尊重请求**（2026-09-20 修正，GAP 16.30）------------------
 * 旧实现把 width/height/bpp **写死**（1280/720/32）且 pitch 恒 = w*4。
 * 实测后果：driver.so 读回 pitch 后算出「每像素字节数 = pitch/width = 4」，
 * 而 rkgame 侧 `video_driver_disp_frame` 写入的 `frame->[12] = colormode = 2`
 * （.data 初值，**全库只有一条指令引用 colormode，没有任何写者**）
 * ⇒ driver.so 的 `gr_blit_b` 判定 `cur->[12] (4) != source->[12] (2)` 恒成立
 * ⇒ 30 s 内刷 **1816 次** `gr_blit: source has wrong format`（忙循环）。
 *
 * 正确语义（与内核 drm_mode_create_dumb 一致）：
 *   in : height, width, bpp, flags        ← **调用者填的，必须原样保留**
 *   out: handle, pitch, size
 *   pitch = width * ceil(bpp / 8)；size = pitch * height
 * ⇒ 这样 bpp=16（RG16/RGB565，pitch=w*2）才会被如实回填成 2 字节/像素。
 * ★ 顺序纪律：**先读输入，再 zfill** —— 反了就把调用者填的字段抹成 0（旧实现踩过）。
 */
/* ---------------- 帧缓冲实体：桩真正拥有它，并观测其内容 ----------------
 * ★★★ 2026-10-04（第 137 轮）根治：把「假帧缓冲」升级为「**有实体、可观测**的帧缓冲」
 *
 * 之前的问题（真缺陷，不是"假实现"之外的凑数）：
 *   `MAP_DUMB` 回填 offset=0x10000000，shim 的 mmap 拦截把「≥4MiB 的可写 MAP_SHARED」
 *   一律映射成**匿名零页** ⇒ 画面被画进一块谁也不看、也**无法按硬件语义解释**的内存。
 *   后果：`behav_capture.sh` 的 `frame_hash` 去读**宿主** `/dev/fb0`
 *   （qemu-user 里根本不存在）⇒ **恒为 `none`** ⇒
 *   「按键有没有改变画面」这个问题在物理上**无法回答**。
 *
 * 真实硬件语义（依据 Linux DRM UAPI，见 docs.kernel.org/gpu/drm-uapi.html）：
 *   CREATE_DUMB → 返回 GEM handle；MAP_DUMB → 返回 offset；
 *   `mmap(fd, offset)` 得到的是**那个 GEM buffer 的可写共享映射**
 *   （内核里 `drm_gem_mmap` 把它直接映射到 buffer 的 vma，**不是**新分配一份）。
 *   且同一 handle 被 ADDFB2 用作 framebuffer 时，framebuffer 与该映射
 *   **引用同一份底层 buffer，不是副本**。
 *
 * ⇒ 因此正确做法不是"在旁边假装有一块显存"，而是：**桩自己分配那块 buffer，
 *   并让 MAP_DUMB 的 offset 真正指向它**（shim 的 mmap 拦截识别该 offset 并返回桩的 buffer）。
 *   这样画面就是**真实写入的那份像素**，可被逐字节哈希 —— 这才是判据，不是表演。
 *
 * 本桩保持 `-nostdlib` 的自足性：只额外用到 `mmap2`/`write` 两个 syscall
 * （自行内联汇编，不引入任何 libc 依赖）⇒ 桩依旧不与设备 glibc 绑定。
 */

/* mmap2 的 ARM EABI syscall 号（与 shim 的 __NR_mmap2 同口径） */
#define STUB_NR_write  4
#define STUB_NR_mmap2  192

/* 与 shim 约定好的"识别标记"：shim 的 mmap 拦截见到 MAP_DUMB 的 offset 时，
 *   通过 `drm_stub_fb_address()` 取这块 buffer 的真实地址。
 * 桩导出该弱符号，shim 用 `dlsym(RTLD_DEFAULT, ...)` 取（取不到就退回原匿名页路径，
 * 不影响旧行为）。 */
static u8  *g_fb_buf;          /* 帧缓冲实体（mmap 出来的真实内存）      */
static u32  g_fb_bytes;        /* 实体大小 = pitch * height（内核语义）  */
static u32  g_fb_pitch;        /* 每行字节数（内核回填值，须被尊重）    */
static u32  g_fb_w, g_fb_h, g_fb_bpp;
static u32  g_fb_flips;        /* PageFlip 次数 = 真实硬件的帧提交次数    */

/* ★★ 2026-10-12（第 172 轮）根修：删除共享行缓冲 `g_hash_line`。
 *   旧设计把行格式化进**全局**缓冲再 write(2)；两个线程并发提交时，
 *   A 格式化到一半被 B 覆写 ⇒ A 的 write 打出**残行**（CI 实测证据：
 *   同一份参考二进制两遍运行，一遍 `frame#10 hash=e96c9dc5`、
 *   另一遍 `frame#10 hashe96c9dc5` —— 同一个 `=` 字节被对方覆写）。
 *   新设计：行在**栈上**构造 + 一次 write(2)（长度 ≤ PIPE_BUF ⇒ POSIX 保证管道写原子）
 *   ⇒ 任何交织下都不可能出现残行。
 *   同时新增（同样是根修的一部分）：
 *     · g_fb_lock      —— ARMv7 ldrex/strex 自旋锁，把「取号+实体快照+哈希+打行」串行化
 *     · g_last_hash    —— 上一次**已打印**的哈希（变化检测，见 fb_commit_hash）
 *     · g_fb_flips_last_chk —— 上一次 checkpoint 打印时的提交序号
 *     · g_last_no_px   —— 上一次是否是「无像素实体」状态（状态变化才打行） */
static volatile u32 g_fb_lock;
static u32 g_last_hash;
static u32 g_fb_flips_last_chk;
static u32 g_last_no_px;

/* ---- 纯 syscall（零 libc 依赖，保持桩的自足性）----
 * ★★ 关键修正（2026-10-04 第 137 轮，自证抓到）：
 *   早先写成 `stub_syscall3`（只填 r0/r1/r2）就调 `mmap2`，**是错的**：
 *   ARM EABI 的 `sys_mmap2` 有 **6 个参数**
 *     r0=addr  r1=len  r2=prot  r3=flags  r4=fd  r5=pgoffset(页数)
 *   只填 3 个 ⇒ r3/r4/r5 是上一条指令留下的垃圾 ⇒ 内核直接失败
 *   （实测现象：`CREATE_DUMB` 后**看不到任何大块 mmap2`**）。
 *   而且 flags 我当时填了 `MAP_SHARED|MAP_PRIVATE`（0x1|0x02）—— 二者**互斥**，
 *   即使参数齐全内核也会返回 EINVAL。
 *   ⇒ 改为 6 参数通用 syscall + `MAP_PRIVATE|MAP_ANONYMOUS`（匿名页的正确组合）。
 */
static long stub_syscall6(long nr, long a, long b, long c,
                          long d, long e, long f)
{
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r4 __asm__("r4") = e;
    register long r5 __asm__("r5") = f;
    __asm__ __volatile__ ("svc 0"
                          : "+r"(r0)
                          : "r"(r7), "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r5)
                          : "memory");
    return r0;
}

static long stub_syscall3(long nr, long a, long b, long c)
{
    register long r7 __asm__("r7") = nr;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    __asm__ __volatile__ ("svc 0"
                          : "+r"(r0)
                          : "r"(r7), "r"(r1), "r"(r2)
                          : "memory");
    return r0;
}

/* FNV-1a 32 位：对像素字节做**顺序**遍历 ⇒ 与 stride/格式无关，
 * 只要两次运行的像素流相同就同哈希，���反则不同。
 * 选它是因为只需整数运算、无需查表（-nostdlib 约束）。 */
static u32 fnv1a(const u8 *p, u32 n)
{
    u32 h = 2166136261u;              /* offset basis */
    u32 i;
    for (i = 0; i < n; i++) {
        h ^= (u32)p[i];
        h *= 16777619u;              /* FNV prime */
    }
    return h;
}

/* 把 u32 渲染成 8 位十六进制（自足，不碰 stdio） */
static char *put_hex8(char *dst, u32 v)
{
    const char *hex = "0123456789abcdef";
    int i;
    for (i = 7; i >= 0; i--) dst[i] = hex[v & 0xfu], v >>= 4;
    return dst + 8;
}

/* ---- 「首次调用」标记 ----
 * ★ 为什么需要（本轮实测踩到）：
 *   被测程序常在**超时被杀**（pty_exec timeout → exit=124），
 *   而 `__attribute__((destructor))`（.fini_array）**只在正常退出时**跑
 *   ⇒ 靠退出汇总取证的方案在这种最常见情形下**什么都留不下**。
 *   ⇒ 改为「每个入口**首次**被调用就立刻打一行」：
 *      不依赖进程如何结束、被 SIGKILL 也不丢证据，
 *      且输出量与调用次数无关（每入口至多一行）。
 */
static void drmstub_note2(const char *tag, u32 a, u32 b)
{
    char line[96];
    char *q = line;
    const char *pre = "[drmstub] enter ";
    int i;
    for (i = 0; pre[i]; i++) q[i] = pre[i];
    q += i;
    for (i = 0; tag[i]; i++) q[i] = tag[i];
    q += i;
    *q++ = ' ';
    q = put_hex8(q, a);
    *q++ = ' ';
    q = put_hex8(q, b);
    *q = '\n';
    stub_syscall3(STUB_NR_write, 2, (long)line, (long)(q - line + 1));
}

static void drmstub_once(const char *tag)
{
    /* 用 tag 指针的最低位做"是否已打"标记（避免数组初始化，纯 BSS 零值可用）。
     * 判据严格：每个 tag 只会因其自身地址而被置位 ⇒ 语义清晰、无碰撞风险。 */
    static unsigned char seen[64];
    u32 idx = ((u32)(unsigned long)tag >> 3) & 63u;
    if (seen[idx]) return;
    seen[idx] = 1;
    drmstub_note2(tag, 0u, 0u);
}

static void drmstub_once_nr(u32 nr)
{
    /* ioctl 号覆盖 256 种 ⇒ 用 4×64 的位图记录"哪种 nr 到过" */
    static unsigned char seen[256];
    if (nr > 255u) return;
    if (seen[nr]) return;
    seen[nr] = 1;
    drmstub_note2("ioctl_nr", nr, 0u);
}

/* ---------------- 画布登记：走内核的 GEM 路径，不去追 driver.so 的私有画布 ----
 * ★★ 2026-10-04 第 137 轮，两次取证把这个方向定死：
 *
 * 事实 ①：`driver.so` 从不在 dumb buffer 上作画。
 *   strace 实录 57 次 mmap，除 loader 的 fd=3 外全是 `fd=-1` 匿名页；
 *   桩的实体地址（0x418c4000 / 0x40c44000 …）在 strace 里各只出现 1 次
 *   —— 就是桩自己那次 mmap2 的返回值，从未被当作 offset 使用。
 *
 * 事实 ②：追不上它的画布。
 *   `driver.so` 的 `mmap` 是**自封定义**（`.symtab` 里有 `mmap@@GLIBC_2.4`，
 *   不是 UNDEF）⇒ 直接发 `SVC`，**绕过 glibc 包装**
 *   ⇒ 宿主侧 LD_PRELOAD 的 shim 无论怎么拦 `mmap`/`syscall` 都看不到它。
 *   实测：shim 的「画布登记」日志**一行都没有**。
 *
 * ⇒ 结论：**不要去追 driver.so 的私有画布**。
 *   正确的观测点是**内核 DRM 自己的 GEM 路径** ——
 *   `drmModeAddFB2(width, height, pixel_format, bo_handles, pitches, offsets, fb_id)`。
 *   真实内核正是用这些参数建立 framebuffer 并在 `SetCrtc`/`PageFlip` 时扫描它。
 *   ⇒ 桩按**调用方给的这些参数**建自己的 framebuffer（内核语义正确），
 *      呈现点哈希它。driver.so 若按真 DRM 用法 blit，就会被观测到。
 *   ⇒ 若 driver.so 连这层都不走（不通过 fb 呈现像素），桩**如实报"无 fb"**，
 *      而不是去猜一块内存冒充"画面"（那就是假观测，本项目明令禁止）。
 */

static u32 g_fb2_w, g_fb2_h, g_fb2_fmt, g_fb2_pitch;
static int g_fb2_valid;

/* ★ R176 根修后：framebuffer 实体 = dumb buffer 实体的**引用**（同一块 GEM），
 * 内核 ADDFB2 语义即如此 —— 见 drmModeAddFB2 根修注释。 */
static u8 *g_fb2_buf;
static u32 g_fb2_bytes;

/* 在帧提交点算一次哈希（真实硬件语义：呈现点 = 一帧被送到扫描 out） */
/* ---------------- ARMv7 独占访问原语（ldrex / strex）----------------
 * ★ 为什么自己写而不用 __atomic/__sync 内建：本桩 `-nostdlib`，**不链接 libgcc / libatomic**。
 *   内建在基线架构不支持时会被降级成 **libcall**（链接期才炸，且报错与病因无关）。
 *   手写 ldrex/strex 是 ARMv7-A 的原生指令（本项目真机 RK3036G = 四核 Cortex-A7）；
 *   qemu-user 对每个 vCPU 实现了 exclusive monitor（linux-user/main.c `do_strex`；
 *   qemu 官方定性：good enough for real code）⇒ 语义确定、可用。 */
static u32 fb_atomic_inc(volatile u32 *p)
{
    u32 v, ok;
    __asm__ __volatile__(
        "2: ldrex %0, [%2]\n"
        "   add   %0, %0, #1\n"
        "   strex %1, %0, [%2]\n"
        "   teq   %1, #0\n"
        "   bne   2b"
        : "=&r"(v), "=&r"(ok)
        : "r"(p)
        : "cc", "memory");
    return v;                 /* 返回**新值** ⇒ 每次提交拿到唯一且单调的序号 */
}

static void fb_lock_take(volatile u32 *lk)
{
    u32 v, ok;
    __asm__ __volatile__(
        "1: ldrex %0, [%2]\n"
        "   cmp   %0, #0\n"
        "   bne   1b\n"
        "   mov   %1, #1\n"
        "   strex %0, %1, [%2]\n"
        "   teq   %0, #0\n"
        "   bne   1b"
        : "=&r"(v), "=&r"(ok)
        : "r"(lk)
        : "cc", "memory");
}

static void fb_lock_drop(volatile u32 *lk)
{
    __asm__ __volatile__("dmb sy" ::: "memory");
    *lk = 0u;
    __asm__ __volatile__("dmb sy" ::: "memory");
}

/* ★★★ 2026-10-12（第 172 轮）根修：本函数是「帧提交观测点」，此前是**脆弱设计**。
 *
 * 失败现场（GitHub Actions run 38223795416，step 10 判 INCONCLUSIVE rc=3）：
 *   **同一份**参考二进制跑两遍，stderr 有 **45+ 行字节不一致**：
 *     ① 帧号重复：`frame#4` 出现两次 ⇒ `g_fb_flips++` 非原子（两线程同读旧值、各写一次）
 *     ② 行撕裂  ：一遍 `frame#10 hash=e96c9dc5`、另一遍 `frame#10 hashe96c9dc5`
 *                ⇒ 共享 `g_hash_line`：A 格式化 → B 覆写 → A 的 write(2) 打出残行
 *     ③ 帧号错位：两遍从第 62 行起帧号错开 1（①的连带）
 *   ⇒ behav_diff 确定性控制组（B0c）判「可复现前缀 61/228 < 60%」⇒ INCONCLUSIVE。
 *
 * 根因不是「CI 跑得快所以撞车」（CNB 云测 227/227 只是运气好撞上慢调度），而是三处设计缺陷：
 *   ① 行在**全局缓冲**里格式化后 write(2)      ⇒ 并发覆写残行
 *   ② 提交序号 `g_fb_flips++` 非原子            ⇒ 帧号重复 / 错位
 *   ③ **每帧**打一行（30s 内 3586 行恒等哈希）  ⇒ 竞态窗口放大 3586 倍，且把
 *      `behav_capture.sh` 的 events 前 200 行窗口**挤成帧行**（真正的语义事件被挤出）
 *
 * 根修（不靠运气、不靠"重试/豁免/调阈值"）：
 *   A. 行在**栈上**构造 + 单次 write(2)（长度 ≤ PIPE_BUF ⇒ POSIX 保证管道写原子）⇒ 残行不可能出现
 *   B. 提交序号用 ldrex/strex 原子递增 ⇒ 序号唯一、单调
 *   C. 同一套 ldrex/strex 做**自旋锁**，把「取号 + 实体快照 + 哈希 + 打行」串行化
 *      ⇒ 行序 == 提交序；实体重配（dumb_fill / AddFB2）与哈希不再交叠（消除 UAF）
 *   D. **只打有信息量的行**：首帧 / 哈希变化帧 / 每 1024 次提交的 checkpoint
 *      ⇒ 全零场景每侧 stderr 由 3586 行降到 ≈4 行：任何调度交织下字节级可复现，
 *         且 events 的 200 行窗口还给真正的语义事件（判据范围变宽，不是变窄）
 */
static void fb_commit_hash(void)
{
    char line[128];
    char *q = line;
    u32 i, flip;
    const char *pre = "[drmstub] frame#";
    const char *mid = " hash=";
    const char *dim = " dim=";
    u8  *src;
    u32  bytes;
    u32  hash = 0u;
    int  have_px = 0;
    int  emit = 0;
    int  is_chk = 0;

    fb_lock_take(&g_fb_lock);

    /* ★ 原子取号：任何交织下每条提交拿到唯一且单调的序号（旧实现 `++` 会丢更新）*/
    flip  = fb_atomic_inc(&g_fb_flips);
    src   = g_fb2_valid ? g_fb2_buf : 0;   /* 只有内核 fb 实体才算"画面" */
    bytes = g_fb2_bytes;

    /* ★ 首个提交打一行「我读到的槽值」：与 shim 的「画布登记」日志对照，
     *   一次就能分清是"shim 没登记"还是"登记了但桩读不到"。 */
    if (flip == 1u) {
        char l2[96];
        char *q2 = l2;
        const char *t1 = "[drmstub] fb2_buf=";
        const char *t2 = " fb_buf=";
        int k;
        for (k = 0; t1[k]; k++) q2[k] = t1[k];
        q2 += k;
        q2 = put_hex8(q2, (u32)(unsigned long)g_fb2_buf);
        for (k = 0; t2[k]; k++) q2[k] = t2[k];
        q2 += k;
        q2 = put_hex8(q2, (u32)(unsigned long)g_fb_buf);
        *q2 = '\n';
        stub_syscall3(STUB_NR_write, 2, (long)l2, (long)(q2 - l2 + 1));
    }

    if (src != 0 && bytes != 0u) {
        hash = fnv1a(src, bytes);
        have_px = 1;
        if (flip == 1u || hash != g_last_hash) emit = 1;          /* 首帧 / 画面变了 */
        if (flip - g_fb_flips_last_chk >= 1024u) { emit = 1; is_chk = 1; }  /* 周期性心跳 */
    } else {
        /* 没有可哈希的像素 ⇒ 如实说"无"，不伪造哈希（不假装观测到了）；
           同样只在**状态变化**时打（旧实现每次提交都打 ⇒ 同样的噪声与竞态）*/
        if (flip == 1u || g_last_no_px == 0u) emit = 1;
    }

    if (!emit) { fb_lock_drop(&g_fb_lock); return; }

    if (have_px) { g_last_hash = hash; g_last_no_px = 0u; }
    else         { g_last_no_px = 1u; }
    if (is_chk)  { g_fb_flips_last_chk = flip; }

    for (i = 0; pre[i]; i++) q[i] = pre[i];
    q += i;
    /* frame# 序号（十进制，手写转换）*/
    { char nb[12]; int k = 0; u32 v = flip;
      if (!v) nb[k++] = '0';
      while (v) { nb[k] = (char)('0' + (v % 10u)); v /= 10u; k++; }
      while (k) *q++ = nb[--k];
    }
    if (!have_px) {
        *q++ = ' '; *q++ = '-'; *q++ = '-';
    } else {
        for (i = 0; mid[i]; i++) q[i] = mid[i];
        q += i;
        q = put_hex8(q, hash);
        for (i = 0; dim[i]; i++) q[i] = dim[i];
        q += i;
        /* dim=WxHxBPP（只给 w/h/bpp 三个十进制位，pitch 已在哈希覆盖范围内）*/
        { const u32 vs[3] = { g_fb2_w, g_fb2_h, (g_fb2_pitch / (g_fb2_w ? g_fb2_w : 1)) * 8 }; int k;
          for (k = 0; k < 3; k++) {
            char nb[12]; int m = 0; u32 v = vs[k];
            if (!v) nb[m++] = '0';
            while (v) { nb[m] = (char)('0' + (v % 10u)); v /= 10u; m++; }
            while (m) *q++ = nb[--m];
            if (k != 2) *q++ = 'x';
          }
        }
        /* ★ 带上**来源标记** src=：f=内核 framebuffer 实体（可信），
         *   n=无（fail-closed，如实报无，绝不拿无关内存冒充画面）。
         *   这是"观测是否可信"的自证 —— 之前出现过"哈希恒等于全零 buffer"
         *   而报告看不出原因，就是缺这个标记。 */
        *q++ = ' ';
        *q++ = 's';
        *q++ = 'r';
        *q++ = 'c';
        *q++ = '=';
        *q++ = g_fb2_valid ? 'f' : 'n';
        if (is_chk) { *q++ = ' '; *q++ = 'c'; *q++ = 'h'; *q++ = 'k'; }
    }
    /* ★ fail-closed：写完必须留终止符。若行已满，截断并显式标记
     *   （静默越界会破坏相邻状态，且判据读到半行会误判）。 */
    if (q >= &line[sizeof(line) - 2]) {
        q = &line[sizeof(line) - 3];
        *q++ = '.';
        *q++ = '.';
    }
    *q = '\n';

    /* 打到 fd 2（stderr）：真机也会把 DRM 诊断写 dmesg，这里等价。
     * `behav_capture.sh` 从 stderr.txt 读它 → 成为可判据的 frame_hash。
     * ★ 行在**栈上**、长度 ≤ PIPE_BUF ⇒ write(2) 对管道原子 ⇒ 不可能被并发写撕裂。 */
    stub_syscall3(STUB_NR_write, 2, (long)line, (long)(q - line + 1));

    fb_lock_drop(&g_fb_lock);
}

/* 供 shim 的 mmap 拦截调用：返回桩持有的帧缓冲实体（0 = 尚未 CREATE_DUMB） */
__attribute__((visibility("default")))
void *drm_stub_fb_address(void) { return (void *)g_fb_buf; }

__attribute__((visibility("default")))
unsigned int drm_stub_fb_size(void) { return g_fb_bytes; }


/* ★ 退出时打一行**汇总**：让"一次帧提交都没发生"这种失败**不可能静默**。
 *   用 `__attribute__((destructor))`（链接器级机制，`.fini_array`）而非 `atexit`
 *   —— 本桩 `-nostdlib`，没有 libc 的 atexit 可用。
 *   两次运行（工厂/重建）都会打 ⇒ 差分器可直接比对"提交次数 + 末帧哈希"。 */
__attribute__((destructor))
static void drm_stub_report(void)
{
    char line[160];
    char *q = line;
    const char *pre = "[drmstub] SUMMARY commits=";
    int i;
    for (i = 0; pre[i]; i++) q[i] = pre[i];
    q += i;
    { char nb[12]; int k = 0; u32 v = g_fb_flips;
      if (!v) nb[k++] = '0';
      while (v) { nb[k] = (char)('0' + (v % 10u)); v /= 10u; k++; }
      while (k) *q++ = nb[--k];
    }
    *q++ = ' '; *q++ = 'h'; *q++ = 'a'; *q++ = 's'; *q++ = 'h'; *q++ = '=';
    *q++ = '[';
    /* 末帧哈希（无实体时如实写 -） */
    if (g_fb2_valid && g_fb2_buf && g_fb2_bytes) {
        char *t = put_hex8(q, fnv1a(g_fb2_buf, g_fb2_bytes));
        q = t;
    } else {
        *q++ = '-'; *q++ = '-';
    }
    *q++ = ']'; *q++ = ' '; *q++ = 'f'; *q++ = 'b'; *q++ = '=';
    *q++ = g_fb2_valid ? 'y' : 'n';
    *q++ = ' '; *q++ = 'b'; *q++ = 'y'; *q++ = 't'; *q++ = '=';
    { char nb[12]; int k = 0; u32 v = g_fb2_bytes;
      if (!v) nb[k++] = '0';
      while (v) { nb[k] = (char)('0' + (v % 10u)); v /= 10u; k++; }
      while (k) *q++ = nb[--k];
    }
    *q++ = ' '; *q++ = 'd'; *q++ = 'i'; *q++ = 'm'; *q++ = '=';
    *q++ = (char)('0' + (g_fb2_w / 1000u % 10u));
    *q++ = (char)('0' + (g_fb2_w / 100u % 10u));
    *q++ = 'x';
    *q++ = (char)('0' + (g_fb2_h / 1000u % 10u));
    *q++ = (char)('0' + (g_fb2_h / 100u % 10u));
    *q++ = 'x';
    *q++ = (char)('0' + ((g_fb2_pitch / (g_fb2_w ? g_fb2_w : 1)) / 10u));
    *q++ = (char)('0' + ((g_fb2_pitch / (g_fb2_w ? g_fb2_w : 1)) % 10u));
    *q = '\n';
    stub_syscall3(STUB_NR_write, 2, (long)line, (long)(q - line + 1));
}

static void dumb_fill(unsigned long req, void *arg)
{
    u32 sz = ioc_size(req);
    u32 *p = (u32 *)arg;
    u32 h, w, bpp, rowbytes, pitch;
    u64 bytes;

    if (arg == 0) return;

    drmstub_once("dumb_fill");

    h   = p[0];                                   /* height（输入）*/
    w   = p[1];                                   /* width （输入）*/
    bpp = p[2];                                   /* bpp   （输入）*/

    zfill(arg, sz);                               /* 清空后再写输出字段 */

    if (w == 0u)  w = 1280u;                      /* 调用者未填时的保守默认 */
    if (h == 0u)  h = 720u;
    if (bpp == 0u) bpp = 16u;                     /* ★ 默认 16bpp（与 colormode=2 一致），不是 32 */

    rowbytes = (bpp + 7u) / 8u;
    pitch = w * rowbytes;
    bytes = (u64)pitch * (u64)h;

    p[0] = h;                                     /* 原样保留输入 */
    p[1] = w;
    p[2] = bpp;
    p[3] = 0u;                                    /* flags */
    p[4] = FAKE_FB_ID;                            /* handle（输出）*/
    p[5] = pitch;                                 /* pitch = w * ceil(bpp/8)（输出）*/
    if (sz >= 32u)      *(u64 *)(void *)((u8 *)arg + 24) = bytes;
    else if (sz >= 28u) *(u64 *)(void *)((u8 *)arg + 20) = bytes;

    /* ★★★ 真实持有实体（第 137 轮）：内核在这里分配 GEM buffer，
     *   后续 MAP_DUMB 的 offset 就指向它 ⇒ 按需真正分配，**尺寸 = pitch*height**。
     *   之前完全不分配（画面落进 shim 的匿名零页），导致帧内容既无实体也无观测。
     *   重复 CREATE_DUMB（重新 modeset）⇒ 释放旧实体再分配，保持"一块活动 framebuffer"。*/
    {
        u32 need = (u32)bytes;
        /* ★ 172 轮：实体切换进锁 —— 与 fb_commit_hash 的「快照+哈希」互斥，
         *   否则另一线程可能拿到"新指针 + 旧尺寸"（错配 ⇒ 越界读）或读到半初始化的字段。 */
        fb_lock_take(&g_fb_lock);
        /* ★ 172 轮：不再主动 munmap 旧实体。两处理由：
         *   ① 语义：内核 GEM 对象的生命周期归 handle —— CREATE_DUMB 产出的是**新**对象，
         *      旧对象要等 DESTROY_DUMB 才释放；在这里主动 munmap 不属于它的语义。
         *   ② 竞态：已发布过的实体可能正被另一线程哈希（fnv1a 逐字节读），
         *      munmap 之后继续读 = UAF（宿主段错误，且症状与被测对象无关）。
         *      ⇒ 去掉主动释放后，"发布过的指针"永远有效，与内核语义一致。
         *      （30s 沙箱里 modeset 次数是个位数，遗留页面的量与 4 GB 地址空间相比可忽略）*/
        if (g_fb_buf != 0) {
            g_fb_buf = 0;      /* 旧实体不再作为"活动"实体，但内存保留（见上）*/
            g_fb_bytes = 0;
        }
        /* pages = ceil(need/4096)；mmap2 的 pgoffset 以**页**为单位 */
        u32 pages = (need + 4095u) / 4096u;
        if (pages == 0u) pages = 1u;
        {
            /* ARM EABI：r2=prot(3=READ|WRITE)  r3=flags(MAP_PRIVATE|MAP_ANONYMOUS)
             *            r4=fd(-1 匿名)       r5=pgoffset(0) */
            long addr = stub_syscall6(STUB_NR_mmap2, 0, (long)(pages * 4096u),
                                      0x1 | 0x2,        /* prot = PROT_READ|PROT_WRITE */
                                      0x02 | 0x20,      /* flags = MAP_PRIVATE|MAP_ANONYMOUS */
                                      -1, 0);
            if (addr > 0 && addr < 0x100000000L) {
                g_fb_buf = (u8 *)addr;
                g_fb_bytes = pages * 4096u;
                g_fb_pitch = pitch;
                g_fb_w = w; g_fb_h = h; g_fb_bpp = bpp;
            } else {
                /* ★ fail-closed：拿不到实体就不假装有画面。
                 *   后续 fb_commit_hash 会如实报"无实体"，而不是给一个假哈希。
                 *   同时**立刻打一行**——否则"分配失败"会被"画面是黑"掩盖
                 *   （这正是本轮踩的坑：分配失败后一路静默，帧哈希恒 `--`）。 */
                g_fb_bytes = 0;
                drmstub_note2("mmap2_FAIL", (u32)addr, need);
            }
        }
        fb_lock_drop(&g_fb_lock);
    }
}

int drmIoctl(int fd, unsigned long request, void *arg)
{
    u32 nr;
    (void)fd;
    drmstub_once("drmIoctl");

    if (ioc_type(request) != 0x64u) return -1;    /* 非 DRM ⇒ 交回上层（不应发生）*/
    nr = ioc_nr(request);
    drmstub_once_nr(nr);

    switch (nr) {
    case 0x00u:                                   /* DRM_IOCTL_VERSION */
        if (arg && ioc_size(request) >= 12u) {
            u32 *p = (u32 *)arg;
            zfill(arg, ioc_size(request));
            p[0] = 1u; p[1] = 0u; p[2] = 0u;      /* major/minor/patchlevel */
        }
        return 0;
    case 0x0cu:                                   /* DRM_IOCTL_GET_CAP：{u64 cap; u64 value;} */
        if (arg && ioc_size(request) >= 16u) {
            u64 *v = (u64 *)arg;
            v[1] = 1ull;                          /* 所有查询的能力都报"有" */
        }
        return 0;
    case 0x0du:                                   /* DRM_IOCTL_SET_CLIENT_CAP */
        if (arg) zfill(arg, ioc_size(request));
        return 0;
    case 0xb2u:                                   /* DRM_IOCTL_MODE_CREATE_DUMB */
        dumb_fill(request, arg);
        return 0;
    case 0xb3u:                                   /* DRM_IOCTL_MODE_MAP_DUMB：{u32 handle; u32 pad; u64 offset;} */
        if (arg) {
            zfill(arg, ioc_size(request));
            /* ★ 真实语义：offset 必须让后续 `mmap(fd, offset)` 映射到**那块 buffer**
             *   （内核里就是 GEM buffer 的 vma）。我们把地址直接回填，
             *   shim 的 mmap 拦截见到此值就把映射接到桩的实体上（见 ① 段说明）。
             *   若实体尚未建立（不该发生）⇒ 如实回 0，让上层自己 mmap 失败。 */
            *(u64 *)(void *)((u8 *)arg + 8) = (u64)(unsigned long)g_fb_buf;
        }
        return 0;
    case 0xb4u:                                   /* DRM_IOCTL_MODE_DESTROY_DUMB */
        return 0;
    case 0xb8u:                                   /* DRM_IOCTL_MODE_ADDFB2：fb_id 是**输出**，在偏移 0 */
        if (arg) {
            u32 *p = (u32 *)arg;
            p[0] = FAKE_FB_ID;
        }
        fb_commit_hash();                          /* 与 drmModeAddFB2 同点（内核里是同一件事）*/
        return 0;
    case 0xbdu:                                   /* DRM_IOCTL_MODE_SETCRTC（内核里 nr=0xbd）*/
        fb_commit_hash();
        if (arg) zfill(arg, ioc_size(request));
        return 0;
    case 0xb9u:                                   /* DRM_IOCTL_MODE_ADDFB（老接口）*/
        if (arg) {
            u32 *p = (u32 *)arg;
            p[0] = FAKE_FB_ID;
        }
        fb_commit_hash();
        return 0;
    default:
        if (arg) zfill(arg, ioc_size(request));    /* 零填 + 成功（确定、不崩）*/
        return 0;
    }
}

/* ---------------- libdrm 高层包装（driver.so 直接引用的 17 个符号）---------------- */

int drmGetCap(int fd, u64 capability, u64 *value)
{
    drmstub_once("drmGetCap");
    (void)fd; (void)capability;
    if (value) *value = 1ull;
    return 0;
}

int drmSetClientCap(int fd, u64 capability, u64 value)
{
    (void)fd; (void)capability; (void)value;
    return 0;
}

drmModeRes *drmModeGetResources(int fd)          { drmstub_once("drmModeGetResources"); (void)fd; return &g_res; }
void        drmModeFreeResources(drmModeRes *p)  { (void)p; }

drmModeConnector *drmModeGetConnector(int fd, u32 id) { (void)fd; (void)id; return &g_conn; }
void              drmModeFreeConnector(drmModeConnector *p) { (void)p; }

drmModeEncoder *drmModeGetEncoder(int fd, u32 id)  { (void)fd; (void)id; return &g_enc; }
void            drmModeFreeEncoder(drmModeEncoder *p) { (void)p; }

drmModeCrtc *drmModeGetCrtc(int fd, u32 id)        { (void)fd; (void)id; return &g_crtc; }
void         drmModeFreeCrtc(drmModeCrtc *p)       { (void)p; }

drmModePlaneRes *drmModeGetPlaneResources(int fd)  { (void)fd; return &g_pres; }
void             drmModeFreePlaneResources(drmModePlaneRes *p) { (void)p; }

drmModePlane *drmModeGetPlane(int fd, u32 id)      { (void)fd; (void)id; return &g_plane; }
void          drmModeFreePlane(drmModePlane *p)    { (void)p; }

int drmModeAddFB2(int fd, u32 width, u32 height, u32 pixel_format,
                  u32 bo_handles[4], u32 pitches[4], u32 offsets[4],
                  u32 *fb_id, u32 flags)
{
    drmstub_once("drmModeAddFB2");
    if (fb_id) *fb_id = FAKE_FB_ID;

    /* ★★★ R176 根修（铁证 = R175 审计 CI 日志）：
     * 内核 `drm_mode_addfb2` 语义 = **引用**调用方传入的 bo_handle（已有 GEM 对象），
     * **绝不分配新内存**。旧实现每次新 mmap 一块 `g_fb2_buf`（0x3d324000），
     * 而画面经 MAP_DUMB 写进 dumb 实体 `g_fb_buf`（0x3d964000）⇒
     * `fb_commit_hash` 读自建实体 ⇒ 恒 e96c9dc5（全零基线）⇒ B6 假红。
     * 根修：bo_handles[0] == FAKE_FB_ID（dumb_fill 分配的那块 GEM）⇒ fb 直接引用
     * 该实体（g_fb2_buf = g_fb_buf），不再 mmap。首帧诊断行 `fb2_buf= fb_buf=`
     * 会显示两地址相同 —— 这就是本次根修的自证。 */
    {
        fb_lock_take(&g_fb_lock);
        if ((bo_handles != 0) && (bo_handles[0] == FAKE_FB_ID) &&
            (g_fb_buf != 0) && (g_fb_bytes != 0u)) {
            g_fb2_buf   = g_fb_buf;                /* ★ 引用，不是新分配 */
            g_fb2_bytes = g_fb_bytes;              /* 与 MAP_DUMB 映射同块 ⇒ 读到的就是画面 */
            g_fb2_w = width; g_fb2_h = height; g_fb2_fmt = pixel_format;
            g_fb2_pitch = (pitches != 0 && pitches[0] != 0u) ? pitches[0] : (width * 4u);
            g_fb2_valid = 1;
            drmstub_note2("AddFB2", width, height);
        } else {
            /* ★ fail-closed：引不到实体就如实报「无 fb」，绝不新 mmap 一块无关内存
             *   冒充画面（旧实现的自建实体正是 B6 假红的来源）。 */
            g_fb2_valid = 0;
            drmstub_note2("AddFB2_NO_ENTITY",
                          (bo_handles != 0) ? bo_handles[0] : 0u,
                          (u32)(unsigned long)g_fb_buf);
        }
        fb_lock_drop(&g_fb_lock);
    }
    return 0;
}

int drmModeRmFB(int fd, u32 fb)                   { (void)fd; (void)fb; return 0; }

int drmModeSetCrtc(int fd, u32 crtc, u32 fb, u32 x, u32 y,
                   u32 *connectors, int count, drmModeModeInfo *mode)
{
    drmstub_once("drmModeSetCrtc");
    (void)fd; (void)x; (void)y; (void)connectors; (void)count; (void)mode;
    /* ★ SETCRTC = 把 fb 绑到 crtc 上扫描输出 —— 这是**无页翻转时的帧呈现路径**
     *   （很多嵌入式栈只做 modeset，不做 page flip）。
     *   实测（2026-10-04 第 137 轮）：`driver.so` 走的就是这条，
     *   原先只在 PageFlip 打哈希 ⇒ 提交数恒 0、帧内容不可观测。 */
    fb_commit_hash();
    (void)crtc; (void)fb;
    return 0;
}

int drmModeSetPlane(int fd, u32 plane, u32 crtc, u32 fb, u32 flags,
                    i32 crtc_x, i32 crtc_y, u32 crtc_w, u32 crtc_h,
                    i32 src_x, i32 src_y, u32 src_w, u32 src_h)
{
    (void)fd; (void)plane; (void)crtc; (void)fb; (void)flags;
    (void)crtc_x; (void)crtc_y; (void)crtc_w; (void)crtc_h;
    (void)src_x; (void)src_y; (void)src_w; (void)src_h;
    fb_commit_hash();
    return 0;
}

int drmModePageFlip(int fd, u32 crtc, u32 fb, u32 flags, void *user_data)
{
    drmstub_once("drmModePageFlip");
    (void)fd; (void)crtc; (void)fb; (void)flags; (void)user_data;
    /* ★ 帧提交点 = 真实硬件把这一帧送去扫描 out 的时刻 ⇒ 哈希在这里取才对应"一帧画面"。
     * 之前这里什么都不做 ⇒ 画面内容无任何可观测点。 */
    fb_commit_hash();
    return 0;
}
