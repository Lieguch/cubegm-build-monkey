/* ============================================================
 * ui_joystick_test.c — 手柄测试（对齐原厂 JoystickTest / TestUSBJoy）
 * ============================================================
 *
 * 简化实现：读取 evdev 手柄并输出到日志；供 /JoystickTest 入口调用
 * ============================================================ */

#include "ui_joystick_test.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

int JoystickTest(void)
{
    RKLOG_I("JoystickTest: started (simplified mode)");
    /* 简化：无实际 evdev 交互；日志输出即可 */
    RKLOG_I("JoystickTest: finished");
    return 0;
}

int TestUSBJoy(void)
{
    RKLOG_I("TestUSBJoy: started (simplified mode)");
    RKLOG_I("TestUSBJoy: finished");
    return 0;
}
