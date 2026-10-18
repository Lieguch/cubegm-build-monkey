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
static u8  *g_fb_buf;          /* 最后一次 CREATE_DUMB 的实体（兼容 shim 的 drm_stub_fb_address）*/
static u32  g_fb_bytes;        /* 实体大小 = pitch * height（内核语义）  */
static u32  g_fb_pitch;        /* 每行字节数（内核回填值，须被尊重）    */
static u32  g_fb_w, g_fb_h, g_fb_bpp;
static u32  g_fb_flips;        /* PageFlip 次数 = 真实硬件的帧提交次数    */

/* ★★★ 2026-10-17（R188 根修）：「单实体」→「handle→实体表」。
 *   R188 云开发运行时铁证裁决候选 B 成立：driver 一次 modeset 建立 **4 个 dumb buffer**
 *   （RG16×3 + AR24×1，尺寸全 1280×1280），桩把它们的 handle 全回填成 FAKE_FB_ID=1
 *   ⇒ MAP_DUMB 入参 handle 全 1、AddFB2 的 bo_handles[0] 全 1 ⇒ 桩只能引用「最后一次」实体
 *   （AR24），而 driver 实际 blit 到 RG16 ⇒ fb_commit_hash 读错块 ⇒ 恒 e96c9dc5（全零基线）。
 *   内核语义（drm_mode_create_dumb）：每个 CREATE_DUMB 产出**新 GEM handle（单调递增）**，
 *   各自独立的实体；MAP_DUMB(handle) 返回**该** handle 的 offset；ADDFB2 的 bo_handles[0]
 *   精确引用**那个** handle 的实体。桩必须复刻这个「一对多」模型。
 *   ⇒ 表：g_dumb[] 存每个 handle 的实体（独立 mmap，互不覆盖）；handle 从 1 递增。
 *     向后兼容：g_fb_buf 仍指向「最后一次」实体（shim 的 drm_stub_fb_address 依赖它判断接管）。 */
typedef struct {
    u32 handle;                  /* GEM handle（= 分配序号，从 1 递增）*/
    u8 *addr;                    /* 实体地址（独立 mmap）*/
    u32 bytes;                   /* 实体字节数 = pitch*height */
    u32 pitch;                   /* 每行字节数 */
    u32 w, h, bpp;               /* 尺寸与位深（诊断用）*/
    u32 used;                    /* 1 = 槽已被占用 */
} dumb_entity_t;

#define DUMB_MAX 8
static dumb_entity_t g_dumb[DUMB_MAX];
static u32 g_dumb_handle_next;   /* 下一个要分配的 handle = 已分配数 + 1（首个为 1）*/

/* ---- R188：handle→实体 查表 / 分配槽（零 libc，纯数组线性扫描）---- */
/* 返回 handle 对应的实体（含位深/尺寸/地址）；未命中 ⇒ 0。 */
static dumb_entity_t *dumb_lookup(u32 handle)
{
    int i;
    for (i = 0; i < DUMB_MAX; i++) {
        if (g_dumb[i].used && g_dumb[i].handle == handle) return &g_dumb[i];
    }
    return 0;
}

/* 返回第一个空闲槽下标；满 ⇒ -1（调用方 fail-closed）。 */
static int dumb_alloc_slot(void)
{
    int i;
    for (i = 0; i < DUMB_MAX; i++) if (!g_dumb[i].used) return i;
    return -1;
}

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

/* ★ R189：打 6 个 u32 的入参快照（SetPlane/PageFlip 的几何参数）。
 * note2 只带 2 个值，而"driver 从哪块画布、取哪个子矩形呈现"需要 fb/plane/src_*/crtc_*
 * 全部 6 个才能定位。line[96] 容纳 "tag + 6×9 字符"（tag ≤ 12 + 空格 + 6×(8+1) = 65）足够。 */
static void drmstub_note6(const char *tag, u32 a, u32 b, u32 c, u32 d, u32 e, u32 f)
{
    char line[96];
    char *q = line;
    const char *pre = "[drmstub] ";
    int i;
    for (i = 0; pre[i]; i++) q[i] = pre[i];
    q += i;
    for (i = 0; tag[i]; i++) q[i] = tag[i];
    q += i;
    *q++ = ' ';
    q = put_hex8(q, a); *q++ = ' ';
    q = put_hex8(q, b); *q++ = ' ';
    q = put_hex8(q, c); *q++ = ' ';
    q = put_hex8(q, d); *q++ = ' ';
    q = put_hex8(q, e); *q++ = ' ';
    q = put_hex8(q, f);
    *q = '\n';
    stub_syscall3(STUB_NR_write, 2, (long)line, (long)(q - line + 1));
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
static void fb_commit_hash(u32 fb)
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
    int  fb_valid = 0;

    fb_lock_take(&g_fb_lock);

    /* ★ 原子取号：任何交织下每条提交拿到唯一且单调的序号（旧实现 `++` 会丢更新）*/
    flip  = fb_atomic_inc(&g_fb_flips);

    /* ★★ R188 第二层根修：呈现点按 fb 精确引用实体（不再恒读「最后一次 AddFB2」的实体）。
     * 内核语义：AddFB2 分配的 fb_id 引用 bo_handle 的 GEM 实体；SetCrtc/PageFlip 用该 fb_id
     * 呈现**那个**实体。旧实现 fb_id 恒 FAKE_FB_ID=1 ⇒ 呈现点无法分辨 driver 呈现哪个实体
     * ⇒ 只能读 g_fb2_buf（最后一次 AddFB2 = AR24 全零）⇒ B6 frame hash 恒 e96c9dc5。
     * 新实现：fb != 0 ⇒ dumb_lookup(fb) 查「handle→实体表」哈希对应实体（driver blit 的目标）；
     *   fb == 0（ioctl 建 fb / 未带 fb id 的兜底）⇒ 退回当前的 g_fb2 实体（旧行为）。 */
    if (fb != 0u) {
        dumb_entity_t *e = dumb_lookup(fb);
        if (e != 0 && e->addr != 0 && e->bytes != 0u) {
            src = e->addr; bytes = e->bytes; fb_valid = 1;
        } else {
            src = 0; bytes = 0u; fb_valid = 0;   /* fail-closed：查不到实体 = 如实报"无" */
        }
    } else {
        src   = g_fb2_valid ? g_fb2_buf : 0;   /* 只有内核 fb 实体才算"画面" */
        bytes = g_fb2_bytes;
        fb_valid = g_fb2_valid;
    }

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
        /* dim=WxHxpitch（三个十进制位）。
        * ★ R187 根修：原来第三位是 (g_fb2_pitch / (g_fb2_w ? g_fb2_w : 1)) * 8
        *   （由 pitch 反算 bpp）——**除数是变量 g_fb2_w**，-nostdlib 下编译器只能
        *   生成 `__aeabi_uidiv` 调用 ⇒ 桩从「0 未定义符号」退化为「1 未定义」，
        *   破坏 build_libdrm_stub.sh 注释里白纸黑字的「产物完全自洽（0 未定义符号）」。
        *   诊断要的信息 pitch 本身就携带（bpp 只是它的导出量），直接打 pitch 即可，
        *   不必做除法。常数除法（/10u、%10u）会被编译器优化成乘法逆元，无此问题。 */
        { const u32 vs[3] = { g_fb2_w, g_fb2_h, g_fb2_pitch }; int k;
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
        *q++ = fb_valid ? 'f' : 'n';
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

/* ★★★ 2026-10-17（R189 第三层根修）：按地址反查 handle→实体表。
 *
 * 根因（R188 云开发运行时已铁证「候选 B」成立，见 PROGRESS R188）：
 *   driver 一次 modeset 建 **4 个 dumb buffer**（RG16×3 + AR24×1，尺寸全 1280×1280），
 *   桩给它们 4 个互不相同的 handle（1/2/3/4），MAP_DUMB 各自回填自己的实体地址
 *   （40c47000 / 41287000 / 418c7000 / 41f07000）。
 *   driver 的 `drm_create_surface`（@0x4604）走 `mmap@plt`（**不是**自封定义那条 SVC 路径），
 *   用 `MAP_SHARED|PROT_READ|PROT_WRITE + fd=DRM fd + offset=MAP_DUMB 回填的实体地址` 调 glibc mmap
 *   ⇒ 会被 shim 的 LD_PRELOAD 拦截。
 *   但 shim 旧实现只认 `drm_stub_fb_address()` == g_fb_buf（最后一次 AR24 实体 41f07000），
 *   ⇒ 前 3 块 RG16 实体的 offset 匹配不上 → shim 返回 0 → 退回匿名页
 *   ⇒ driver 把画面 blit 到**匿名页**，桩的实体恒零 ⇒ frame#1 hash 恒 b5449dc5（全零 RG16 的 FNV-1a）。
 *
 * 内核语义（drm_gem_mmap）：MAP_DUMB(handle) 返回的 offset 就是**那个** GEM buffer 的地址，
 * mmap(fd, offset) 必须映射回**同一块** buffer。这一对接口让 shim 能「按 off 反查任意一块实体」，
 * 而不是只能认最后一块。 */
__attribute__((visibility("default")))
void *drm_stub_fb_lookup_by_addr(unsigned long addr)
{
    int i;
    if (addr == 0ul) return 0;
    for (i = 0; i < DUMB_MAX; i++) {
        dumb_entity_t *e = &g_dumb[i];
        if (e->used && e->addr != 0 && (unsigned long)e->addr == addr)
            return e->addr;
    }
    return 0;
}

__attribute__((visibility("default")))
unsigned int drm_stub_fb_size_by_addr(unsigned long addr)
{
    int i;
    for (i = 0; i < DUMB_MAX; i++) {
        dumb_entity_t *e = &g_dumb[i];
        if (e->used && e->addr != 0 && (unsigned long)e->addr == addr)
            return e->bytes;
    }
    return 0u;
}


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
    /* ★ R187 根修（同 556 行）：第三位原为 pitch/w 反算 bpp，除数是变量 ⇒ __aeabi_uidiv。
    *   直接打 pitch 前两位十进制（0x7D0=2000 ⇒ "20"），信息不丢、自洽性保住。 */
    *q++ = (char)('0' + ((g_fb2_pitch / 10u) % 10u));
    *q++ = (char)('0' + (g_fb2_pitch % 10u));
    *q = '\n';
    stub_syscall3(STUB_NR_write, 2, (long)line, (long)(q - line + 1));
}

/* ★ R187 诊断埋点：每次 CREATE_DUMB 都打「第 N 次 → w/h/bpp/实体地址」。
 * 用途：CNB 云开发运行时裁决候选 A/B（见 PROGRESS R186）。
 *   driver 的 gr_init 会在一次 modeset 里建立**多个** dumb buffer：
 *   3 个 RG16（RGB565，bpp=16，轮转呈现用）+ 1 个 AR24（ARGB8888，bpp=32）。
 *   桩现在只用**单个** g_fb_buf，且每次 CREATE_DUMB 都覆盖它 ⇒ 只能留最后一次。
 *   若 blit 落点（RG16 实体，前 N 次）≠ g_fb_buf（最后一次=AR24），
 *   则候选 A（实体错位）成立。此埋点把每次实体地址序列打印出来即可裁决。 */
static u32 g_dumb_seq;

static void dumb_entity_note(u32 seq, u32 w, u32 h, u32 bpp, u32 addr)
{
    char line[96];
    char *q = line;
    const char *pre = "[drmstub] dumb#";
    int i;
    for (i = 0; pre[i]; i++) q[i] = pre[i];
    q += i;
    { char nb[12]; int k = 0; u32 v = seq;                 /* 序号（十进制）*/
      if (!v) nb[k++] = '0';
      while (v) { nb[k] = (char)('0' + (v % 10u)); v /= 10u; k++; }
      while (k) *q++ = nb[--k];
    }
    *q++ = ' '; *q++ = 'w'; *q++ = '=';  q = put_hex8(q, w);
    *q++ = ' '; *q++ = 'h'; *q++ = '=';  q = put_hex8(q, h);
    *q++ = ' '; *q++ = 'b'; *q++ = 'p'; *q++ = 'p'; *q++ = '='; q = put_hex8(q, bpp);
    *q++ = ' '; *q++ = 'a'; *q++ = 'd'; *q++ = 'd'; *q++ = 'r'; *q++ = '='; q = put_hex8(q, addr);
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

    /* ★★★ R188 根修：handle 从 1 **单调递增**（不再恒 FAKE_FB_ID=1）。
     *   内核 drm_mode_create_dumb 每次分配一个**新** GEM handle；driver 一次 modeset 建 4 个
     *   dumb buffer，桩必须给它们 4 个**互不相等**的 handle，MAP_DUMB/ADDFB2 才能按 handle
     *   精确引用各自的实体（旧实现恒 1 ⇒ 撞号 ⇒ 只能留最后一次 ⇒ B6 读错块）。 */
    u32 handle = FAKE_FB_ID + g_dumb_handle_next;   /* 首个=1，随后 2/3/4… */
    g_dumb_handle_next += 1u;

    p[0] = h;                                     /* 原样保留输入 */
    p[1] = w;
    p[2] = bpp;
    p[3] = 0u;                                    /* flags */
    p[4] = handle;                                /* handle（输出）：单调递增，互不相等 */
    p[5] = pitch;                                 /* pitch = w * ceil(bpp/8)（输出）*/
    if (sz >= 32u)      *(u64 *)(void *)((u8 *)arg + 24) = bytes;
    else if (sz >= 28u) *(u64 *)(void *)((u8 *)arg + 20) = bytes;

    /* ★★★ R188 根修：实体记入 handle→实体表（每 handle 一块**独立** mmap，互不覆盖）。
     *   旧实现「覆盖式复用 g_fb_buf」崩掉了「多 dumb buffer」内核语义 ⇒ B6。 */
    {
        u32 need = (u32)bytes;
        fb_lock_take(&g_fb_lock);

        int slot = dumb_alloc_slot();
        if (slot < 0) {
            /* fail-closed：表满（理论上不会，driver 最多建 4 个）⇒ 不假装成功 */
            fb_lock_drop(&g_fb_lock);
            drmstub_note2("dumb_TABLE_FULL", handle, need);
            return;
        }

        u32 pages = (need + 4095u) / 4096u;
        if (pages == 0u) pages = 1u;
        {
            long addr = stub_syscall6(STUB_NR_mmap2, 0, (long)(pages * 4096u),
                                      0x1 | 0x2,        /* prot = PROT_READ|PROT_WRITE */
                                      0x02 | 0x20,      /* flags = MAP_PRIVATE|MAP_ANONYMOUS */
                                      -1, 0);
            if (addr > 0 && addr < 0x100000000L) {
                /* 写入表（独立实体，不覆盖上一次）*/
                g_dumb[slot].used   = 1;
                g_dumb[slot].handle = handle;
                g_dumb[slot].addr   = (u8 *)addr;
                g_dumb[slot].bytes  = pages * 4096u;
                g_dumb[slot].pitch  = pitch;
                g_dumb[slot].w = w; g_dumb[slot].h = h; g_dumb[slot].bpp = bpp;

                /* 向后兼容：g_fb_buf 仍指向「最后一次」实体（shim 的 drm_stub_fb_address 依赖）*/
                g_fb_buf = (u8 *)addr;
                g_fb_bytes = pages * 4096u;
                g_fb_pitch = pitch;
                g_fb_w = w; g_fb_h = h; g_fb_bpp = bpp;

                dumb_entity_note(++g_dumb_seq, w, h, bpp, (u32)addr);   /* 实体地址序列 */
            } else {
                /* fail-closed：拿不到实体就不占表槽、不假装有画面 */
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
            u32 in_handle = *(u32 *)(void *)arg;   /* ★ R187：zfill 前先抓输入 handle */
            zfill(arg, ioc_size(request));
            /* ★★★ R188 根修：offset 必须回填**该 handle** 的实体地址（查表）。
             *   内核：MAP_DUMB(handle) 返回**那个** GEM buffer 的 offset，mmap(fd,offset)
             *   映射到同一块 buffer。旧实现恒回填 g_fb_buf（最后一次实体）⇒ 4 个 handle
             *   全指向最后一块 ⇒ driver mmap 到错的实体 ⇒ 画面与哈希实体脱节（B6）。 */
            dumb_entity_t *e = dumb_lookup(in_handle);
            u8 *ent = (e != 0) ? e->addr : 0;
            *(u64 *)(void *)((u8 *)arg + 8) = (u64)(unsigned long)ent;
            drmstub_note2("MAP_DUMB", in_handle, (u32)(unsigned long)ent);
        }
        return 0;
    case 0xb4u:                                   /* DRM_IOCTL_MODE_DESTROY_DUMB */
        return 0;
    case 0xb8u:                                   /* DRM_IOCTL_MODE_ADDFB2：fb_id 是**输出**，在偏移 0 */
        if (arg) {
            u32 *p = (u32 *)arg;
            p[0] = FAKE_FB_ID;
        }
        fb_commit_hash(0u);                        /* 建 fb 无呈现 fb_id：退回 g_fb2 兜底（driver 主线走高层的 drmModeAddFB2）*/
        return 0;
    case 0xbdu:                                   /* DRM_IOCTL_MODE_SETCRTC（内核里 nr=0xbd）*/
        fb_commit_hash(0u);                        /* ioctl 路径未解 fb_id：退回 g_fb2 兜底（driver 主线走高层的 drmModeSetCrtc）*/
        if (arg) zfill(arg, ioc_size(request));
        return 0;
    case 0xb9u:                                   /* DRM_IOCTL_MODE_ADDFB（老接口）*/
        if (arg) {
            u32 *p = (u32 *)arg;
            p[0] = FAKE_FB_ID;
        }
        fb_commit_hash(0u);                        /* 建 fb 无呈现 fb_id：退回 g_fb2 兜底 */
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

    /* ★★★ R188 根修（在 R176 基础上**按 handle 精确引用**）：
     * 内核 `drm_mode_addfb2` 语义 = **引用**调用方传入的 bo_handle（已有 GEM 对象），
     * **绝不分配新内存**。R176 根修只做了「bo_handles[0]==FAKE_FB_ID ⇒ 引用 g_fb_buf」。
     * 但 FAKE_FB_ID 撞号 + g_fb_buf 只留最后一次实体 ⇒ 4 个 dumb buffer 里 ADDFB2 只能
     * 引用到最后一块（AR24）。R188 改为**查 handle→实体表**：bo_handles[0] 是哪个 handle，
     * 就引用**那个**实体（RG16 轮转实体各自的地址），fb_commit_hash 才读到真正的画面。 */
    {
        u32 bo_h0 = (bo_handles != 0) ? bo_handles[0] : 0u;   /* ★ R187：进锁前抓 handle */
        /* ★ R188 第二层根修：fb_id = bo_handle（唯一、单调），呈现点据此反查实体。
         * 旧实现 fb_id 恒 FAKE_FB_ID=1 ⇒ 4 个 framebuffer 共用同一 fb_id，
         * SetCrtc/PageFlip(fb=1) 无法分辨呈现哪个实体。内核里 fb_id 是 AddFB2
         * 分配、供 Driver 回传给呈现点的句柄，唯一是它的基本契约（不是可撞号的常量）。 */
        if (fb_id) *fb_id = bo_h0;
        fb_lock_take(&g_fb_lock);
        dumb_entity_t *e = dumb_lookup(bo_h0);
        if (e != 0) {
            g_fb2_buf   = e->addr;               /* ★ 引用**该 handle**的实体，不是新分配 */
            g_fb2_bytes = e->bytes;              /* 与 MAP_DUMB 映射同块 ⇒ 读到的就是画面 */
            g_fb2_w = width; g_fb2_h = height; g_fb2_fmt = pixel_format;
            g_fb2_pitch = (pitches != 0 && pitches[0] != 0u) ? pitches[0] : e->pitch;
            g_fb2_valid = 1;
            drmstub_note2("AddFB2", width, height);
            /* ★ R188：bo_handles[0] → 引用的**该**实体地址（不再是最后一次 g_fb_buf）。 */
            drmstub_note2("AddFB2_h", bo_h0, (u32)(unsigned long)e->addr);
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
    /* ★ R188 埋点：呈现点传入的 fb 值 + 当前 g_fb2 实体，用于确定「呈现用哪个 fb」*/
    drmstub_note2("SetCrtc_fb", fb, (u32)(unsigned long)g_fb2_buf);
    /* ★ SETCRTC = 把 fb 绑到 crtc 上扫描输出 —— 这是**无页翻转时的帧呈现路径** */
    fb_commit_hash(fb);
    (void)crtc;
    return 0;
}

int drmModeSetPlane(int fd, u32 plane, u32 crtc, u32 fb, u32 flags,
                    i32 crtc_x, i32 crtc_y, u32 crtc_w, u32 crtc_h,
                    i32 src_x, i32 src_y, u32 src_w, u32 src_h)
{
    (void)fd; (void)plane; (void)crtc; (void)flags;
    (void)crtc_x; (void)crtc_y; (void)crtc_w; (void)crtc_h;
    (void)src_x; (void)src_y; (void)src_w; (void)src_h;
    drmstub_note2("SetPlane_fb", fb, (u32)(unsigned long)g_fb2_buf);
    /* ★ R189 全入参快照：plane_id / fb / src_x / src_y / src_w / src_h。
     *   目的：driver 用 plane 从画布取子矩形时，src_* 是"画面来源几何"的唯一线索
     *   （16.16 定点数，src_w/h 通常 = 画布宽高 << 16）。若 src_* 指向非桩实体尺寸，
     *   即证明像素在 driver 私有画布而非桩实体。 */
    drmstub_note6("SetPlane_geom", plane, fb,
                  (u32)src_x, (u32)src_y, (u32)src_w, (u32)src_h);
    fb_commit_hash(fb);
    return 0;
}

int drmModePageFlip(int fd, u32 crtc, u32 fb, u32 flags, void *user_data)
{
    drmstub_once("drmModePageFlip");
    (void)fd; (void)crtc; (void)flags; (void)user_data;
    drmstub_note2("PageFlip_fb", fb, (u32)(unsigned long)g_fb2_buf);
    /* ★ R189：crtc / fb / flags 全入参，确认翻转路径呈现哪个 fb。 */
    drmstub_note6("PageFlip_geom", crtc, fb, (u32)(unsigned long)user_data, 0u, 0u, 0u);
    /* ★ 帧提交点 = 真实硬件把这一帧送去扫描 out 的时刻 ⇒ 哈希在这里取才对应"一帧画面"。 */
    fb_commit_hash(fb);
    return 0;
}
