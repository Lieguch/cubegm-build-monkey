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

/* 假 dumb buffer 的 mmap 偏移：刻意选 ≥ 4 MiB，以命中 shim 既有的
 * "MAP_SHARED + 可写 + 偏移 ≥ 4 MiB ⇒ 匿名零页" 规则（不引入新机制）。 */
#define FAKE_DUMB_MMAP_OFF 0x10000000u
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
static void dumb_fill(unsigned long req, void *arg)
{
    u32 sz = ioc_size(req);
    u32 *p = (u32 *)arg;
    u32 h, w, bpp, rowbytes, pitch;
    u64 bytes;

    if (arg == 0) return;

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
}

int drmIoctl(int fd, unsigned long request, void *arg)
{
    u32 nr;
    (void)fd;

    if (ioc_type(request) != 0x64u) return -1;    /* 非 DRM ⇒ 交回上层（不应发生）*/
    nr = ioc_nr(request);

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
            *(u64 *)(void *)((u8 *)arg + 8) = (u64)FAKE_DUMB_MMAP_OFF;
        }
        return 0;
    case 0xb4u:                                   /* DRM_IOCTL_MODE_DESTROY_DUMB */
        return 0;
    case 0xb8u:                                   /* DRM_IOCTL_MODE_ADDFB2：fb_id 是**输出**，在偏移 0 */
        if (arg) {
            u32 *p = (u32 *)arg;
            p[0] = FAKE_FB_ID;
        }
        return 0;
    default:
        if (arg) zfill(arg, ioc_size(request));    /* 零填 + 成功（确定、不崩）*/
        return 0;
    }
}

/* ---------------- libdrm 高层包装（driver.so 直接引用的 17 个符号）---------------- */

int drmGetCap(int fd, u64 capability, u64 *value)
{
    (void)fd; (void)capability;
    if (value) *value = 1ull;
    return 0;
}

int drmSetClientCap(int fd, u64 capability, u64 value)
{
    (void)fd; (void)capability; (void)value;
    return 0;
}

drmModeRes *drmModeGetResources(int fd)          { (void)fd; return &g_res; }
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
    (void)fd; (void)width; (void)height; (void)pixel_format;
    (void)bo_handles; (void)pitches; (void)offsets; (void)flags;
    if (fb_id) *fb_id = FAKE_FB_ID;
    return 0;
}

int drmModeRmFB(int fd, u32 fb)                   { (void)fd; (void)fb; return 0; }

int drmModeSetCrtc(int fd, u32 crtc, u32 fb, u32 x, u32 y,
                   u32 *connectors, int count, drmModeModeInfo *mode)
{
    (void)fd; (void)crtc; (void)fb; (void)x; (void)y;
    (void)connectors; (void)count; (void)mode;
    return 0;
}

int drmModeSetPlane(int fd, u32 plane, u32 crtc, u32 fb, u32 flags,
                    i32 crtc_x, i32 crtc_y, u32 crtc_w, u32 crtc_h,
                    i32 src_x, i32 src_y, u32 src_w, u32 src_h)
{
    (void)fd; (void)plane; (void)crtc; (void)fb; (void)flags;
    (void)crtc_x; (void)crtc_y; (void)crtc_w; (void)crtc_h;
    (void)src_x; (void)src_y; (void)src_w; (void)src_h;
    return 0;
}

int drmModePageFlip(int fd, u32 crtc, u32 fb, u32 flags, void *user_data)
{
    (void)fd; (void)crtc; (void)fb; (void)flags; (void)user_data;
    return 0;
}
