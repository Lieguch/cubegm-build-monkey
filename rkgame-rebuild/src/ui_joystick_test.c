/* ============================================================
 * ui_joystick_test.c — 手柄测试（对齐原厂 JoystickTest / TestUSBJoy）
 * ============================================================
 *
 * 原厂 JoystickTest @ 0x2f8c0 (4.8 KB)：
 *   读取所有 evdev 手柄，显示按键/摇杆状态
 *   供 /JoystickTest 和 /USBJoystickTest 入口调用
 * ============================================================ */

#include "ui_joystick_test.h"
#include "rkgame.h"
#include "font.h"
#include "debug.h"

#include <stdio.h>
#include <string.h>

int JoystickTest(void)
{
    RKLOG_I("JoystickTest: started");
    RKLOG_I("JoystickTest: %d devices detected", joy_dev_count);

    if (font_is_ready()) {
        int y = 50;
        font_draw_text("Joystick Test", 20, y, 0x00ff00);
        y += 30;
        for (int d = 0; d < joy_dev_count && d < 8; d++) {
            char line[80];
            snprintf(line, sizeof(line), "Device %d: %s (VID=%04x PID=%04x)",
                     d, joy_devs[d].name[0] ? joy_devs[d].name : "(unknown)",
                     joy_devs[d].vid, joy_devs[d].pid);
            font_draw_text(line, 20, y + d * 28, 0xffffff);
        }
        font_draw_text("Press any button to test...", 20, y + joy_dev_count * 28 + 20, 0x888888);
    }

    RKLOG_I("JoystickTest: finished");
    return 0;
}

int TestUSBJoy(void)
{
    RKLOG_I("TestUSBJoy: started");
    RKLOG_I("TestUSBJoy: %d devices detected", joy_dev_count);
    RKLOG_I("TestUSBJoy: finished");
    return 0;
}
