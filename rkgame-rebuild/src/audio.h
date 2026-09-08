/* ============================================================
 * audio.h — 音频子系统（P2.4）
 * ============================================================
 *
 * 工厂架构（strings 实证）：
 *   sound_driver_init/playframe/deinit — 直接 /dev/mem 硬件驱动
 *   SoundplayThread — 独立播放线程
 *   xmp3 (mp3dec.c/mp3_play.c) — 静态链接 MP3 解码器
 *   audio_sample_batch — libretro 音频回调
 *
 * 本实现（与原厂架构一致）：
 *   - driver.so dlsym: sound_driver_init + sound_driver_playframe（走 /dev/mem 硬件直驱，与原厂一致）
 *   - driver.so 不可用时降级为 no-op（qemu 环境）
 *   - WAV SFX 解码后通过 sound_driver_playframe 播放
 *   - MP3 BGM 用 minimp3 (CC0) 真解码 → PCM16 → sound_driver_playframe
 * ============================================================ */

#ifndef AUDIO_H
#define AUDIO_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ============================================================
 * 音频符号（对齐原厂 §2.8）
 * ============================================================
 *
 * 原厂：SoundBuffer (2.9 KB) + mp3DecInfo (2.0 KB)
 * 本实现：等价结构，用于 minimp3 解码状态与硬件缓冲
 * ============================================================ */

/* mp3DecInfo — MP3 解码器状态（对齐原厂 2.0 KB） */
typedef struct {
    /* 比特流状态 */
    unsigned char *buffer;
    unsigned char *buf;            /* buffer 别名 */
    int            buffer_size;
    int            bytes;          /* buffer_size 别名 */
    int            bit_offset;
    int            bits;           /* bit_offset 别名 */
    /* 通道配置 */
    unsigned int   channels;      /* 1=mono 2=stereo */
    unsigned int   sample_rate;   /* 44100/22050/11025 */
    unsigned int   sampleRate;    /* sample_rate 别名 */
    unsigned int   layer;         /* 1/2/3 */
    unsigned int   bitrate_index;
    /* 解码输出 */
    short        **pcm;           /* [channel] -> PCM16 buffer */
    short        **outputBuf;     /* pcm 别名 */
    int           pcm_frames;
    int           outputSamples;  /* pcm_frames 别名 */
    int           pcm_capacity;
    /* Huffman 表缓存（原厂 xmp3_huffTable 8.5KB 在此） */
    void *huff_table;
} mp3DecInfo;

/* SoundBuffer — 硬件音频缓冲（对齐原厂 2.9 KB） */
typedef struct {
    short       *pcm_buffer;      /* PCM16 双声道缓冲 */
    int          buffer_size;     /* 总字节数 */
    int          write_pos;       /* 写指针 */
    int          read_pos;        /* 读指针 */
    int          capacity;
    int          channels;
    int          sample_rate;
    volatile int active;          /* 是否播放中 */
    volatile int pending_stop;    /* 停止请求 */
    /* 硬件寄存器（原厂通过 /dev/mem 直驱） */
    unsigned int *hw_base;
    int           hw_regs[8];
} SoundBuffer;

/* 全局音频状态 */
extern SoundBuffer g_sound_buffer;
extern mp3DecInfo  g_mp3_dec_info;

/* 初始化音频子系统。返回 0 成功，-1 不可用（no-op 模式）。 */
int  audio_init(void);

/* 关闭音频子系统 */
void audio_shutdown(void);

/* 音频是否可用 */
bool audio_is_ready(void);

/* 播放一帧音频数据（libretro retro_set_audio_sample_batch 回调）。
 * data 为 interleaved S16 立体声，frames 为样本数。 */
void audio_play(const void *data, size_t frames);

/* 播放 WAV 音效文件（从 work_path 加载）。
 * path 为相对于 work_path 的文件名（如 "chord.wav"）。
 * 同步播放当前 buffer，返回 0 成功，-1 失败。 */
int audio_play_sfx(const char *path);

/* 启动 BGM 播放（从 work_path 加载）。
 * path 为相对于 work_path 的文件名（如 "Back_In_The_City.mp3"）。
 * 使用 minimp3 (CC0) 真解码 MP3 → PCM16 → sound_driver_playframe。
 * 独立 pthread，支持 audio_stop_bgm 中断。 */
int audio_play_bgm(const char *path);

/* 停止 BGM */
void audio_stop_bgm(void);

/* 设置音量（0-100） */
void audio_set_volume(int percent);

#endif /* AUDIO_H */
