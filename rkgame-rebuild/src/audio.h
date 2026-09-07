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
