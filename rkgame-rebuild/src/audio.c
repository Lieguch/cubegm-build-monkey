/* ============================================================
 * audio.c — 音频子系统（原厂 driver.so 接口复刻）
 * ============================================================
 *
 * 工厂实证（Ghidra FUN_0000db08_InitSound.c）：
 *   InitSound() {
 *     if (handle == 0) return;
 *     sound_driver_init = dlsym(handle, "sound_driver_init");
 *     if (sound_driver_init) {
 *       (*sound_driver_init)(USE_HDMI_OUT, UpdateROM, 2);
 *       sound_driver_playframe = dlsym(handle, "sound_driver_playframe");
 *     }
 *   }
 *   PlaySound() {
 *     if (sound_driver_playframe) (*sound_driver_playframe)();
 *   }
 *
 * 本实现：
 *   - dlsym 从 driver.so 获取 sound_driver_init/playframe
 *   - 与原厂完全一致的调用方式
 *   - 降级为 no-op 当 driver.so 不可用（qemu 环境）
 *   - WAV SFX 解码后通过 sound_driver_playframe 播放
 *   - MP3 BGM 通过 xmp3 解码后播放
 * ============================================================ */

#include "audio.h"
#include "rkgame.h"
#include "debug.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <pthread.h>
#include <dlfcn.h>

/* ---- MP3 解码器（minimp3, CC0 单头实现） ---- */
#define MINIMP3_IMPLEMENTATION
#include "minimp3.h"

/* MP3 解码 chunk 缓冲：一次读 4096 字节 MP3 数据（约 1 帧），输出 PCM 到 g_audio_buf */
#define MP3_READ_CHUNK 4096

/* ---- driver.so 接口 ---- */

/* driver.so 句柄（由 main.c 传入） */
extern void *driver_handle;  /* driver.so dlopen handle */

/* 原厂 sound_driver_init 签名：(int use_hdmi, void *callback, int mode) */
typedef void (*sound_driver_init_t)(int use_hdmi, void *callback, int mode);

/* 原厂 sound_driver_playframe 签名：(void) — 无参数，直接播放 */
typedef void (*sound_driver_playframe_t)(void);

/* 原厂 UpdateROM 回调（用于固件升级，本 rebuild 传 NULL） */
typedef void (*update_rom_t)(void);

static sound_driver_init_t     g_sound_init      = NULL;
static sound_driver_playframe_t g_sound_playframe = NULL;

/* ---- 全局状态 ---- */

static int   g_audio_ready   = 0;
static int   g_volume        = 80;
static int   g_use_hdmi      = 1;  /* USE_HDMI_OUT = 1 */

/* 音频缓冲区（sound_driver_playframe 从这里读取） */
static unsigned char g_audio_buf[64 * 1024];
static size_t        g_audio_buf_size = 0;
static size_t        g_audio_buf_pos = 0;

/* SFX 播放状态 */
static char  g_sfx_path[256] = "";
static bool  g_sfx_pending   = false;

/* BGM 播放状态 */
static char  g_bgm_path[256] = "";
static bool  g_bgm_active    = false;
static pthread_t g_bgm_thread = 0;
static int   g_bgm_stop      = 0;

/* ---- 初始化（复刻原厂 InitSound） ---- */

int audio_init(void)
{
    LOG("audio_init: using driver.so sound_driver_init (factory interface)");

    if (!driver_handle) {
        LOG("audio_init: driver.so handle not available, audio disabled");
        return -1;
    }

    /* 原厂调用：dlsym(handle, "sound_driver_init") */
    g_sound_init = (sound_driver_init_t)dlsym(driver_handle, "sound_driver_init");
    if (!g_sound_init) {
        LOG("audio_init: can't find sound_driver_init proc in driver.so");
        return -1;
    }

    /* 原厂调用：(*sound_driver_init)(USE_HDMI_OUT, UpdateROM, 2) */
    /* 注意：原厂传 UpdateROM 回调，我方传 NULL（无升级需求） */
    g_sound_init(g_use_hdmi, NULL, 2);

    /* 原厂调用：dlsym(handle, "sound_driver_playframe") */
    g_sound_playframe = (sound_driver_playframe_t)dlsym(driver_handle, "sound_driver_playframe");
    if (!g_sound_playframe) {
        LOG("audio_init: can't find sound_driver_playframe proc");
        return -1;
    }

    g_audio_ready = 1;
    LOG("audio_init: sound_driver_init + playframe loaded from driver.so");
    return 0;
}

void audio_shutdown(void)
{
    if (g_bgm_active) {
        audio_stop_bgm();
    }
    g_audio_ready = 0;
    LOG("audio_shutdown: audio subsystem stopped");
}

/* ---- 音量控制 ---- */

void audio_set_volume(int vol)
{
    g_volume = vol;
    LOG("audio_set_volume: %d", vol);
    /* 原厂 sound_driver_init 已配置硬件音量，此处仅记录 */
}

/* ---- SFX 播放（WAV 解码后通过 sound_driver_playframe） ---- */

int audio_play_sfx(const char *path)
{
    if (!path || !path[0]) return -1;
    if (!g_audio_ready) return -1;

    FILE *fp = fopen(path, "rb");
    if (!fp) {
        LOG("audio_play_sfx: cannot open %s", path);
        return -1;
    }

    /* 读取 WAV 头（简化：RIFF/PCM16） */
    char header[44];
    if (fread(header, 1, 44, fp) < 44) {
        fclose(fp);
        return -1;
    }

    /* 检查 RIFF/WAVE 标记 */
    if (memcmp(header, "RIFF", 4) != 0 || memcmp(header + 8, "WAVE", 4) != 0) {
        LOG("audio_play_sfx: not a valid WAV file: %s", path);
        fclose(fp);
        return -1;
    }

    /* 读取 PCM 数据 */
    fseek(fp, 44, SEEK_SET);
    size_t data_size = fread(g_audio_buf, 1, sizeof(g_audio_buf), fp);
    fclose(fp);

    if (data_size == 0) return -1;

    g_audio_buf_size = data_size;
    g_audio_buf_pos = 0;
    g_sfx_pending = true;

    /* 通过 sound_driver_playframe 播放（原厂方式） */
    if (g_sound_playframe) {
        g_sound_playframe();
    }

    LOG("audio_play_sfx: played %s (%zu bytes)", path, data_size);
    return 0;
}

/* ---- BGM 播放（minimp3 真解码 MP3 → PCM16 → sound_driver_playframe） ---- */

/* 一次解码 MP3 chunk 到 g_audio_buf，返回播放帧数（PCM16 字节数）。
 * 若 g_bgm_stop 置位或文件结束则返回 0。 */
static size_t bgm_decode_one_frame(FILE *fp, mp3dec_t *dec, uint8_t *mp3_chunk)
{
    size_t n = fread(mp3_chunk, 1, sizeof(mp3_chunk), fp);
    if (n == 0) return 0;

    mp3dec_frame_info_t info;
    /* MP3D_SAMPLE 为 int16_t（未定义 MINIMP3_FLOAT_OUTPUT 时） */
    int16_t pcm[MINIMP3_MAX_SAMPLES_PER_FRAME * 2];  /* 最大 1152*2 立体声 */
    int samples = mp3dec_decode_frame(dec, mp3_chunk, (int)n, pcm, &info);

    if (samples <= 0) return 0;

    /* 音量调节（0-100 → 0-1.0 系数） */
    float vol = (float)g_volume / 100.0f;
    size_t bytes_out = 0;
    size_t max_out = sizeof(g_audio_buf);

    for (int i = 0; i < samples; i++) {
        int16_t s = (int16_t)(pcm[i] * vol);
        if (bytes_out + 2 > max_out) break;
        g_audio_buf[bytes_out++] = (unsigned char)(s & 0xFF);
        g_audio_buf[bytes_out++] = (unsigned char)((s >> 8) & 0xFF);
    }

    g_audio_buf_size = bytes_out;
    g_audio_buf_pos = 0;

    /* 通过 sound_driver_playframe 播放当前 buffer */
    if (g_sound_playframe) {
        g_sound_playframe();
    }

    /* 简单限流：MP3 每帧 1152 samples @44100Hz ≈ 26ms，sleep 避免 CPU 100% */
    usleep(15000);  /* 15ms */
    return bytes_out;
}

static void *bgm_thread_func(void *arg)
{
    (void)arg;

    /* 打开 MP3 文件 */
    FILE *fp = fopen(g_bgm_path, "rb");
    if (!fp) {
        ERR("bgm_thread: cannot open %s", g_bgm_path);
        return NULL;
    }

    mp3dec_t dec;
    mp3dec_init(&dec);

    uint8_t mp3_chunk[MP3_READ_CHUNK];
    long total_played = 0;

    LOG("bgm_thread: decoding %s (minimp3 CC0)", g_bgm_path);

    /* 主解码循环：一次读 4096B MP3 数据 → 解码 → 播放 PCM16 */
    while (!g_bgm_stop) {
        size_t played = bgm_decode_one_frame(fp, &dec, mp3_chunk);
        if (played == 0) break;  /* 文件结束或解码失败 */
        total_played += (long)played;
    }

    fclose(fp);
    LOG("bgm_thread: finished (total PCM bytes: %ld)", total_played);
    return NULL;
}

int audio_play_bgm(const char *path)
{
    if (!path || !path[0]) return -1;
    if (!g_audio_ready) return -1;

    if (g_bgm_active) {
        audio_stop_bgm();
    }

    strncpy(g_bgm_path, path, sizeof(g_bgm_path) - 1);
    g_bgm_stop = 0;

    pthread_create(&g_bgm_thread, NULL, bgm_thread_func, NULL);
    g_bgm_active = true;

    LOG("audio_play_bgm: started %s", path);
    return 0;
}

void audio_stop_bgm(void)
{
    if (!g_bgm_active) return;

    g_bgm_stop = 1;
    if (g_bgm_thread) {
        pthread_join(g_bgm_thread, NULL);
    }
    g_bgm_active = false;
    LOG("audio_stop_bgm: stopped");
}
