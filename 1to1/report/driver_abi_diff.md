# driver.so 符号族 vs 项目逆向清单 diff 对齐（P0-1 · R174 复核）

## 1. driver.so 符号族全量实测（golden/sdcard_min/driver.so，39,844 B）

| 类别 | 数量 | 明细 |
|---|---|---|
| .dynsym DEFINED | **61** | FUNC 39 + OBJECT 15 + NOTYPE 7 |
| .dynsym UNDEFINED | **65** | libdrm 21 + libasound 19 + libc/pthread 25 |
| DT_NEEDED | 5 | libdrm.so.2 / libkms.so.1 / libasound.so.2 / libpthread.so.0 / libc.so.6 |

39 个 FUNC 按内部角色分族：

| 族 | 符号 | 数量 | 谁调用 |
|---|---|---|---|
| **私有 ABI（rkgame dlsym 消费）** | video_driver_setting / video_drivers_init* / video_driver_disp_frame / video_driver_setmode / video_driver_get_size / video_driver_deinit* / sound_driver_init / sound_driver_playframe / sound_driver_deinit* | 9（含 3 个 run_process 间接） | rkgame InitDisplay/InitSound/Deinit* |
| gr_* 图形原语 | gr_init / gr_blit / gr_blit_b / gr_clear / gr_clear_all / gr_color / gr_fill / gr_flip / gr_text / gr_texticon / gr_measure / gr_rotate / gr_select / gr_plane / gr_plane_to / gr_get_width / gr_get_height / gr_get_rotate / gr_get_current / gr_next_frame / gr_font_size / gr_fb_width / gr_fb_height / gr_fb_blank / gr_exit | 25 | driver.so 内部（video_driver_* 转发） |
| 内部线程/辅助 | open_drm / ScaleDisplayThread / video_rotation | 3 | driver.so 内部 |
| 状态 OBJECT | mutex / cond / frame / DisplayThread / DisplayThreadflag / colormode / gr_colormode / video_aspect_ratio_idx / SoundDataBuffer* / SoundDataFrames / threadsoud_* | 15 | driver.so 内部状态 |

## 2. 与项目已逆向清单对表

项目侧权威清单 = `tools/driver_stub_coverage.py` 的 `ABI_SYMS`（9 个）+ R165 三腿自证
（`tools/_r165_abi_selftest.py`：真库覆盖 9/9 / 删符必判缺 / 选错 provider 必判缺，已接入 cnb_gates.sh）。

**diff 结论**：

| driver.so DEFINED | 项目已逆向/消费 | 差 | 定性 |
|---|---|---|---|
| 61 | 9（ABI_SYMS） | 52 | 52 个全部是 **driver.so 内部实现细节**（gr_* 25 + 线程/辅助 3 + OBJECT 15 + 段符号 7 + video_rotation），rkgame 只经 9 个 ABI 进入 ⇒ **不需要**在项目侧逆向；「未覆盖」是正确划分，非缺口 |

源码实测消费面（本轮全仓扫描，非旧结论引用）：

| 符号 | 绑定方式 | 源码位置 |
|---|---|---|
| video_driver_setting | dlsym | proprietary/hw/FUN_0000d678_InitDisplay.c:30 |
| video_driver_disp_frame | dlsym | 同上 :42 |
| video_driver_setmode | dlsym | 同上 :47 |
| video_driver_get_size | dlsym | 同上 :52 |
| video_drivers_init | run_process_constprop_0 | 同上 :39 |
| video_driver_deinit | run_process_constprop_0 | proprietary/hw/FUN_0000dae0_DeinitDisplay.c:14 |
| sound_driver_init | dlsym | proprietary/hw/FUN_0000db08_InitSound.c |
| sound_driver_playframe | dlsym | 同上 |
| sound_driver_deinit | run_process_constprop_0 | proprietary/hw/FUN_0000dbcc_DeinitSound.c:14 |

## 3. 「假桩覆盖全部初始化入口」验证

入口链（源码实测）：

```
InitDisplay → dlopen(work_path/driver.so)
  → dlsym ×6 + run_process(video_drivers_init)
  → pthread_create(ScaleDisplayThread)   [driver.so 内部渲染线程]
InitSound   → dlsym ×2（sound_driver_init/playframe）
DeinitDisplay → run_process(video_driver_deinit)
DeinitSound   → run_process(sound_driver_deinit)
InitJoystick  → sunxi_gpio_init + InitRFJoystick   ★ 不经 driver.so（GPIO/evdev 直走）
```

| 验证层 | 判据 | 结果 |
|---|---|---|
| 静态覆盖 | 9 ABI 符号 vs driver.so 61 DEFINED | 9/9 命中（driver_stub_coverage.py --print-need private） |
| 静态自证 | _r165_abi_selftest.py 三腿 | 真库 9/9 / 删符判缺 / 错 provider 判缺（R165 实测，已入 cnb_gates.sh） |
| UND 提供方 | driver.so 65 UND 按库分组 | libdrm 21 + libasound 19 由设备 sysroot 真实库提供（device_rootfs_min/usr/lib 三库俱全）+ libc/pthread 25 由 sysroot 提供；**libkms.so.1 为空桩**（driver.so 无 kms_* UND ⇒ 只需 SONAME 存在，build_libkms_stub.sh 注释已证） |
| 运行时 | CI 硬门禁 run 38382028547（R173 修复后正式回归） | M3 `open driver.so sucess` ✓、M4 DRM ✓、B6R frame_commits 1024/2048 > 0、M0–M7 三侧差集空 |

## 4. 结论

1. **9 个私有 ABI = 全部初始化入口**（6 dlsym + 3 run_process 间接），与 driver.so 符号族 diff 后
   无遗漏；52 个非 ABI 符号经查证全部属 driver.so 内部实现，正确划分。
2. **桩的分层**：libkms 空桩（补 SONAME）+ libdrm/libasound 可观测桩（替换真实库以记录帧哈希/提交）
   + 设备 sysroot 真实库（深口径对照）。设备 sysroot 本身三库俱全（device_rootfs_min 实测）。
3. **InitJoystick 不经 driver.so**（sunxi_gpio + RF joystick 在 rkgame 主程序内）——
   driver.so 的职责面 = 显示 + 声音，与符号族实测一致。

证据文件：report/_r174_driver_dynsyms.txt（61 DEFINED + 65 UND 全量落盘）
