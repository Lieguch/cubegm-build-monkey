/* ============================================================
 * rkgame-rebuild — stubs.h
 *
 * 原厂 main() 调用但 rebuild 无实质需求的函数桩声明。
 * 全部对齐 Ghidra 反编译，保持调用链完整。
 * ============================================================ */

#ifndef STUBS_H
#define STUBS_H

/* 诊断 /proc/meminfo + 显示分辨率（原厂 main() 第 4 阶段） */
void dispmeninfo(void);

/* SFC 子系统初始化桩（无 SFC 硬件，libretro core 处理） */
int  sfc_init(void);

/* SPI 驱动初始化桩（无触摸屏 SPI） */
int  spi_driver_init(void);

/* 固件升级桩（无升级需求） */
int  UpdateROM(const char *path);

/* RF 无线手柄初始化桩（无 RF 硬件，USB 走 evdev） */
int  InitRFJoystick(void);

/* resource.cpd 加载桩（UI 走 ui_*.zip） */
int  resource_cpd_load(const char *path);

/* 诊断：打印所有 stub 状态 */
void stubs_report(void);

#endif /* STUBS_H */
