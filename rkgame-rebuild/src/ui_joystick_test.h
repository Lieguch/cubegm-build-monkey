/* ============================================================
 * ui_joystick_test.h — 手柄测试（对齐原厂 JoystickTest）
 * ============================================================
 *
 * 原厂 JoystickTest @ 0x2f8c0：
 *   独立模式：读取手柄并显示所有按键/摇杆状态
 *   供 /JoystickTest 和 /USBJoystickTest 两个入口调用
 * ============================================================ */

#ifndef UI_JOYSTICK_TEST_H
#define UI_JOYSTICK_TEST_H

/* 手柄测试模式运行一次（阻塞直到退出）。返回 0 */
int  JoystickTest(void);

/* USB 手柄测试模式运行一次 */
int  TestUSBJoy(void);

#endif /* UI_JOYSTICK_TEST_H */
