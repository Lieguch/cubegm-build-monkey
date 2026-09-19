/* ============================================================
 * alsa_stub.c —— 桩 `libasound.so.2`：让厂商闭源 `driver.so` 的音频初始化能过
 *
 * 为什么需要它（2026-09-19 实测定案，见 GAP 16.23）：
 *   桩 `libdrm.so.2` 打通图形初始化后，执行流 M0–M7 全通，但两侧都终止于：
 *       rkgame: pcm.c:3009: snd_pcm_avail: Assertion `pcm' failed.
 *   —— 这句**来自真实 libasound**（`pcm.c` 是 alsa-lib 源文件），断言 `pcm != NULL`。
 *   即 driver.so 走到音频初始化时拿到的 `snd_pcm_t*` 是 NULL（沙箱无真实声卡
 *   ⇒ 真 `snd_pcm_open()` 失败 ⇒ 它没检查返回值就继续用）⇒ `abort()`。
 *   ⇒ 与 DRM 完全同型：**只要 driver.so 加载成功，就必须把它的每个硬件后端都"做成成功"**。
 *
 * 实测引用面（逐字取自 `golden/sdcard_min/driver.so` 的 65 个未定义符号）：
 *   20 个 `snd_*`，`DT_NEEDED = libasound.so.2`。
 *   ★ 全仓普查：**只有 driver.so 引用 snd_\***（工厂 rkgame / 重建 elf / icube 均为 0）
 *     ⇒ 用本桩整体替换 `libasound.so.2` 不会影响任何其它模块。
 *
 * 与 `drm_stub.c` 相同的三条纪律：
 *   · 两侧（工厂/重建/控制）注入**同一份**桩 ⇒ 差分仍是"同环境比实现"；
 *   · 只由**显式开关**启用（默认关）⇒ 不启用时行为一字不变；
 *   · `-nostdlib` ⇒ 0 未定义符号、零运行时依赖（自带 hidden `memset`）。
 *
 * ★ 比真 libasound **更健壮的一点**（刻意的）：本桩**永不因入参为 NULL 而崩** ——
 *   `pcm`/`params` 一律不强制解引用。理由：driver.so 正是在"没检查 open 失败"的
 *   路径上把 NULL 传下去的；桩的职责是让流程走下去并留下**可观测的成功语义**，
 *   而不是复刻一个断言。这是"把假硬件做成成功"，不是"放宽判据"。
 *
 * 编译：见 tools/build_libasound_stub.sh（`-nostdlib`）
 * ============================================================ */

typedef unsigned char u8;
typedef unsigned int  u32;
typedef signed int    i32;
typedef long          slong;    /* snd_pcm_sframes_t */
typedef unsigned long ulong;    /* snd_pcm_uframes_t / size_t */

/* driver.so 实测需要的 20 个符号（见 build_libasound_stub.sh 的自证清单）：
 *   sizeof, open, close, prepare, start, drop, recover, avail, writei,
 *   hw_params, hw_params_any, hw_params_sizeof,
 *   hw_params_set_{access,format,channels,rate_near,period_size_near,buffer_size_near},
 *   hw_params_get_{channels,period_size,buffer_size}
 */

/* ---------------- 假 `snd_pcm_t` 句柄 ----------------
 * opaque 类型（driver.so 不可能知道布局）⇒ 给一个非 NULL 的静态对象即可。
 * 大小留足（不做任何假设，纯粹防"下游误读"）。 */
static u32 g_pcm_obj[64] = { 0x50434d43u /* "CMPC" */, 0u };

/* ---------------- `snd_pcm_hw_params_t` 的**私有**布局 ----------------
 * 真实类型是 opaque；driver.so 必然先调 `snd_pcm_hw_params_sizeof()` 再分配缓冲
 * （它拿不到 `sizeof(snd_pcm_hw_params_t)`）。
 * ⇒ 我们只需保证：**只访问自己缓冲的前 32 字节**，绝不越界 —— 无论 driver.so
 *   分配多大都安全；返回的 SIZE 只要 ≥ 32 即可。
 * ★ SIZE 取 256：比真实 alsa-lib 的 sizeof（约 192～208，随版本）**偏大**，
 *   误差方向保守（只会多分配，不会让 driver.so 少分配而越界）。 */
#define HW_PARAMS_SIZE 256u

#define HW_MAGIC 0x48574153u   /* "SAWH" */

#define HW_OFF_MAGIC   0u
#define HW_OFF_FORMAT  4u
#define HW_OFF_ACCESS  8u
#define HW_OFF_CHANS   12u
#define HW_OFF_RATE    16u
#define HW_OFF_PERIOD  20u
#define HW_OFF_BUFFER  24u

/* 默认值：44.1 kHz / 立体声 / S16_LE / RW_INTERLEAVED，周期 1024、缓冲 4096 帧。
 * 取常见且自洽的一组（period × 4 = buffer），使 avail/writei 的语义自圆其说。 */
#define DEF_FORMAT  2u        /* SND_PCM_FORMAT_S16_LE */
#define DEF_ACCESS  3u        /* SND_PCM_ACCESS_RW_INTERLEAVED */
#define DEF_CHANS   2u
#define DEF_RATE    44100u
#define DEF_PERIOD  1024u
#define DEF_BUFFER  4096u

/* ---------------- 零依赖小工具 ---------------- */

/* 编译器在初始化大对象时会自动生成 `memset` 调用；`-nostdlib` 下必须自带。
 * `visibility("hidden")`：只为自解析，**不导出**（不遮蔽设备 libc 的优化版）。 */
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

/* 缓冲内取/存 u32（只在前 32 字节内活动） */
static u32 rd(const void *p, u32 off)
{
    const u8 *c = (const u8 *)p;
    return (u32)c[off] | ((u32)c[off + 1] << 8) |
           ((u32)c[off + 2] << 16) | ((u32)c[off + 3] << 24);
}
static void wr(void *p, u32 off, u32 v)
{
    u8 *c = (u8 *)p;
    c[off]     = (u8)(v & 0xffu);
    c[off + 1] = (u8)((v >> 8) & 0xffu);
    c[off + 2] = (u8)((v >> 16) & 0xffu);
    c[off + 3] = (u8)((v >> 24) & 0xffu);
}

/* params 是否为本桩初始化过（magic 命中才读，否则回落到默认值） */
static int hw_ok(const void *params)
{
    return params != 0 && rd(params, HW_OFF_MAGIC) == HW_MAGIC;
}
static u32 hw_get(const void *params, u32 off, u32 dflt)
{
    return hw_ok(params) ? rd(params, off) : dflt;
}
static void hw_put(void *params, u32 off, u32 v)
{
    if (params == 0) return;
    wr(params, off, v);
}

/* ---------------- 设备/句柄生命周期 ---------------- */

/* int snd_pcm_open(snd_pcm_t **pcm, const char *name, snd_pcm_stream_t stream, int mode)
 * ★ 成败关键：真实 libasound 在这里失败 ⇒ 下游拿到 NULL ⇒ 断言崩。
 *   本桩无条件成功，并把**非 NULL** 句柄写回。 */
int snd_pcm_open(void **pcm, const char *name, int stream, int mode)
{
    (void)name; (void)stream; (void)mode;
    if (pcm != 0) *pcm = (void *)g_pcm_obj;
    return 0;
}

int snd_pcm_close(void *pcm)                              { (void)pcm; return 0; }
int snd_pcm_prepare(void *pcm)                            { (void)pcm; return 0; }
int snd_pcm_start(void *pcm)                              { (void)pcm; return 0; }
int snd_pcm_drop(void *pcm)                               { (void)pcm; return 0; }
int snd_pcm_recover(void *pcm, int err, int silent)       { (void)pcm; (void)err; (void)silent; return 0; }

/* snd_pcm_sframes_t snd_pcm_avail(snd_pcm_t *pcm)
 * ★ 崩溃现场就是它（真库的 `pcm.c:3009` 断言）。本桩返回一个**正数**（= 一个周期），
 *   使 driver.so 的"可写帧数"语义自洽，不会死等或走负数分支。 */
slong snd_pcm_avail(void *pcm)
{
    (void)pcm;
    return (slong)DEF_PERIOD;
}

/* snd_pcm_sframes_t snd_pcm_writei(snd_pcm_t *, const void *, snd_pcm_uframes_t)
 * 返回**已消费的帧数** = 请求值 ⇒ "全部接受"（假硬件丢弃数据）。 */
slong snd_pcm_writei(void *pcm, const void *buf, ulong size)
{
    (void)pcm; (void)buf;
    return (slong)size;
}

/* ---------------- hw_params 协商 ---------------- */

ulong snd_pcm_hw_params_sizeof(void)
{
    return (ulong)HW_PARAMS_SIZE;
}

int snd_pcm_hw_params_any(void *pcm, void *params)
{
    (void)pcm;
    if (params != 0) {
        zfill(params, 32u);                 /* 只清我们自己用的那 32 字节 */
        wr(params, HW_OFF_MAGIC,  HW_MAGIC);
        wr(params, HW_OFF_FORMAT, DEF_FORMAT);
        wr(params, HW_OFF_ACCESS, DEF_ACCESS);
        wr(params, HW_OFF_CHANS,  DEF_CHANS);
        wr(params, HW_OFF_RATE,   DEF_RATE);
        wr(params, HW_OFF_PERIOD, DEF_PERIOD);
        wr(params, HW_OFF_BUFFER, DEF_BUFFER);
    }
    return 0;
}

/* int snd_pcm_hw_params(snd_pcm_t *, snd_pcm_hw_params_t *)
 * 真实库在此把协商结果落到设备；假硬件一律接受。 */
int snd_pcm_hw_params(void *pcm, void *params)            { (void)pcm; (void)params; return 0; }

int snd_pcm_hw_params_set_format(void *pcm, void *params, int val)
{
    (void)pcm; hw_put(params, HW_OFF_FORMAT, (u32)val); return 0;
}

int snd_pcm_hw_params_set_access(void *pcm, void *params, int access)
{
    (void)pcm; hw_put(params, HW_OFF_ACCESS, (u32)access); return 0;
}

int snd_pcm_hw_params_set_channels(void *pcm, void *params, unsigned int val)
{
    (void)pcm;
    if (val == 0u) val = DEF_CHANS;         /* 0 声道不合法 ⇒ 回落到默认，避免下游除零 */
    hw_put(params, HW_OFF_CHANS, (u32)val);
    return 0;
}

/* set_*_near：把**实际采纳的值**写回 `*val`（ALSA 语义），并清 `*dir`。 */
int snd_pcm_hw_params_set_rate_near(void *pcm, void *params, unsigned int *val, int *dir)
{
    (void)pcm;
    if (val != 0) { hw_put(params, HW_OFF_RATE, (u32)*val); }
    if (dir != 0) *dir = 0;
    return 0;
}

int snd_pcm_hw_params_set_period_size_near(void *pcm, void *params, ulong *val, int *dir)
{
    (void)pcm;
    if (val != 0) {
        ulong v = *val ? *val : (ulong)DEF_PERIOD;
        hw_put(params, HW_OFF_PERIOD, (u32)v);
        *val = v;
    }
    if (dir != 0) *dir = 0;
    return 0;
}

int snd_pcm_hw_params_set_buffer_size_near(void *pcm, void *params, ulong *val)
{
    (void)pcm;
    if (val != 0) {
        ulong v = *val ? *val : (ulong)DEF_BUFFER;
        hw_put(params, HW_OFF_BUFFER, (u32)v);
        *val = v;
    }
    return 0;
}

/* ---------------- hw_params 回读（与 set_* 写入的值一致）---------------- */

int snd_pcm_hw_params_get_channels(const void *params, unsigned int *val)
{
    if (val != 0) *val = hw_get(params, HW_OFF_CHANS, DEF_CHANS);
    return 0;
}

int snd_pcm_hw_params_get_period_size(const void *params, ulong *frames, int *dir)
{
    if (frames != 0) *frames = (ulong)hw_get(params, HW_OFF_PERIOD, DEF_PERIOD);
    if (dir != 0) *dir = 0;
    return 0;
}

int snd_pcm_hw_params_get_buffer_size(const void *params, ulong *val)
{
    if (val != 0) *val = (ulong)hw_get(params, HW_OFF_BUFFER, DEF_BUFFER);
    return 0;
}
