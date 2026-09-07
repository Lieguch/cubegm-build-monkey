# Debug 叠加层 — 实体机屏幕调试

## 背景
RK3036G 掌机实体机没有终端/指令窗口，rkgame 启动后用户只能看到屏幕画面。当程序崩溃、卡死、内存泄漏时无法通过终端查看日志。

## 触发方式
**长按 SELECT + START 2 秒** → 切换屏幕底部调试面板

（与原厂 R36S 通用退出快捷键一致，但本 rebuild 无"退出"功能；长按 2s 避免误触）

## 显示内容（屏幕底部 1280×240 半透明黑面板）

```
=== rkgame DEBUG OVERLAY ===              SELECT+START 2s = toggle
PID=1234  up=3m45s  stage=14 [CORE: run loop]
VmRSS=42MB  VmSize=128MB  MemTotal=504MB  Avail=380MB
FPS=59  DRM=OK  game=ON  fb=1280x720  level=2
keys=0x00001440  (hex=16 actions)
pressed: L1+A+UP
--- last 5 logs (newest first) ---
32345678 I: gamemenuhotkey: pause OFF
32345600 I: pause menu: load state slot 0
32345500 D: retro_run: frame 1000
32345400 P: CORE: run loop
32345300 I: retro_load_game: OK
DEBUG: overlay active. Hold SELECT+START 2s to hide.
```

## 技术实现

| 文件 | 作用 |
|------|------|
| `src/dbg_overlay.c` (322 行) | 叠加层实现：切换检测 + 信息收集 + 渲染 |
| `src/dbg_overlay.h` | API 声明 |
| `src/debug.c` | 新增 `dbg_current_stage()` / `dbg_get_last_logs()` 等 |
| `src/main.c` | `dbg_overlay_init()` + 菜单循环集成 |
| `src/core.c` | 游戏循环 + 暂停状态集成 |
| `build.sh` | 源文件列表 |

## 集成架构

```
main()
  ├── dbg_init()
  ├── dbg_overlay_init()          ← 新增
  ├── ...初始化子系统...
  ├── main_menu()                 ← 菜单循环内调用 dbg_overlay_tick()
  │     └── while(1) { ... dbg_overlay_tick() → disp_present() }
  └── autorun()
        └── core_run()            ← 游戏循环内调用 dbg_overlay_tick()
              └── while(1) { retro_run(); dbg_overlay_tick_frame(); dbg_overlay_tick() → disp_present() }
```

## 数据源
- `/proc/self/status` → VmRSS, VmSize
- `/proc/meminfo` → MemTotal, MemAvailable
- `/proc/uptime` → 系统运行时间
- `dbg_current_stage()` → 最后一条 dbg_probe 埋点
- `dbg_get_last_logs()` → 环形缓冲区最近 5 条日志
- `joy_all_keys_state()` → 16 位按键掩码
- `disp_is_ready()` / `disp_is_game_mode()` / `disp_fb_width/height()` → 显示状态
