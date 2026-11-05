/* ============================================================
 * test_evdev_state.c —— R322 evdev 事件状态机离线单元门禁
 * 直接 #include 源文件以访问 static 状态；不开真实设备，纯逻辑注入。
 * 背景：16 号真机 trace 证实旧状态机把"释放/回中"事件丢弃 ⇒ 方向键永久卡死
 *      （tag=K 358/358 恒 0x40）。本门禁保证：任何按键/方向"按下→释放"必须归零。
 * 用法：zig cc tools/test_evdev_state.c -o /tmp/t && /tmp/t   （host linux）
 *      或 zig cc -target arm-linux-gnueabihf -c（语法检查）
 * ============================================================ */
#include <stdio.h>
#include <string.h>
#include "../src/upgrade/evdev_gamepad.c"

static int fails = 0;
#define CK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } \
    else printf("ok  : %s\n", msg); } while (0)

static struct input_event mk(unsigned short t, unsigned short c, int v)
{
    struct input_event e; memset(&e, 0, sizeof e);
    e.type = t; e.code = c; e.value = v; return e;
}

int main(void)
{
    /* ---------- 兜底路径（无 profile）---------- */
    memset(g_match, 0, sizeof g_match);
    memset(g_key, 0, sizeof g_key);
    memset(g_ax_cal, -1, sizeof g_ax_cal);   /* 未校准：绝对轴不参与 */

    { struct input_event e = mk(EV_KEY, BTN_SOUTH, 1); ev_apply(0, &e);
      CK(g_key[0] == RK_A, "KEY 按下置位 A"); }
    { struct input_event e = mk(EV_KEY, BTN_SOUTH, 0); ev_apply(0, &e);
      CK(g_key[0] == 0,     "KEY 释放清位 A（旧代码卡死点）"); }
    { struct input_event e = mk(EV_KEY, BTN_SOUTH, 2); ev_apply(0, &e);
      CK(g_key[0] == RK_A,  "KEY autorepeat(2) 视为按住"); }
    { struct input_event e = mk(EV_KEY, BTN_SOUTH, 0); ev_apply(0, &e); }
    { struct input_event e = mk(EV_KEY, KEY_POWER, 1); ev_apply(0, &e);
      CK(g_key[0] == 0,     "非游戏 KEY 不污染键值"); }

    { struct input_event e = mk(EV_ABS, ABS_HAT0Y, 1); ev_apply(0, &e);
      CK(g_key[0] == RK_DOWN, "hat0Y=+1 → DOWN"); }
    { struct input_event e = mk(EV_ABS, ABS_HAT0Y, 0); ev_apply(0, &e);
      CK(g_key[0] == 0,       "hat0Y=0 回中清 DOWN（旧代码卡死点）"); }
    { struct input_event e = mk(EV_ABS, ABS_HAT0X, -1); ev_apply(0, &e);
      CK(g_key[0] == RK_LEFT, "hat0X=-1 → LEFT"); }
    { struct input_event e = mk(EV_ABS, ABS_HAT0X, 1); ev_apply(0, &e);
      CK(g_key[0] == (RK_LEFT | RK_RIGHT), "hat0X=-1→+1 无中间0：LEFT 保持 + RIGHT 置位（未收到释放者不清）"); }
    { struct input_event e = mk(EV_ABS, ABS_HAT0X, 0); ev_apply(0, &e);
      CK(g_key[0] == 0,       "hat0X=0 回中清两端"); }
    /* 四方向全按再全放，必须归零（第 6 轮 0xf0 累积卡死回归项） */
    { struct input_event e;
      e = mk(EV_ABS, ABS_HAT0Y, -1); ev_apply(0, &e);
      e = mk(EV_ABS, ABS_HAT0X, -1); ev_apply(0, &e);
      CK(g_key[0] == (RK_UP | RK_LEFT), "上+左 同按");
      e = mk(EV_ABS, ABS_HAT0Y, 0);  ev_apply(0, &e);
      e = mk(EV_ABS, ABS_HAT0X, 0);  ev_apply(0, &e);
      CK(g_key[0] == 0, "全放归零（防 0xf0 累积回归）"); }

    /* ---------- profile 路径（摇杆绝对轴）----------
     * 复刻 16 号真机杀伤场景：Xbox360 摇杆 center=128，静止持续上报 128；
     * 旧代码裸 value>0 ⇒ DOWN 恒钉死。 */
    {
        static cgm_prof prof;
        memset(&prof, 0, sizeof prof);
        prof.btn[0] = prof.btn[1] = prof.btn[2] = prof.btn[3] = -1;
        prof.ax_up = -1; prof.ax_dn = 1;    /* Y 轴：负向上 / 正向下 */
        prof.ax_lf = -1; prof.ax_rt = 1;    /* X 轴：负向左 / 正向右 */
        g_match[1] = &prof;
        g_key[1] = 0;
        g_ax_cal[1][1][0] = 128; g_ax_cal[1][1][1] = 8;   /* Y: center/flat */
        g_ax_cal[1][0][0] = 128; g_ax_cal[1][0][1] = 8;   /* X: center/flat */

        { struct input_event e = mk(EV_ABS, ABS_Y, 128); ev_apply(1, &e);
          CK(g_key[1] == 0, "摇杆静止(=center 128)不产生任何方向（16 号钉死场景）"); }
        { struct input_event e = mk(EV_ABS, ABS_Y, 0); ev_apply(1, &e);
          CK(g_key[1] == RK_UP, "上推到底 → UP"); }
        { struct input_event e = mk(EV_ABS, ABS_Y, 128); ev_apply(1, &e);
          CK(g_key[1] == 0, "回中清 UP（旧代码卡死点）"); }
        { struct input_event e = mk(EV_ABS, ABS_Y, 255); ev_apply(1, &e);
          CK(g_key[1] == RK_DOWN, "下推到底 → DOWN"); }
        { struct input_event e = mk(EV_ABS, ABS_Y, 120); ev_apply(1, &e);
          CK(g_key[1] == 0, "死区内微噪 → 清 DOWN（防抖钉）"); }
        { struct input_event e = mk(EV_ABS, ABS_X, 255); ev_apply(1, &e);
          CK(g_key[1] == RK_RIGHT, "X 右推(255) → RIGHT（LEFT 未收到释放，保持？否：从未置位）"); }
        { struct input_event e = mk(EV_ABS, ABS_X, 0); ev_apply(1, &e);
          CK(g_key[1] == (RK_LEFT | RK_RIGHT) - RK_RIGHT, "X 左推(0=左到底) → LEFT（RIGHT 释放清）"); }
        { struct input_event e = mk(EV_ABS, ABS_X, 128); ev_apply(1, &e);
          CK(g_key[1] == 0, "X 回中(128) 清 LEFT（旧代码卡死点）"); }
    }

    /* ---------- profile 路径（hat 优先 + 按键码）---------- */
    {
        static cgm_prof prof2;
        memset(&prof2, 0, sizeof prof2);
        prof2.btn[0] = 6;               /* b 事件码 = 6 (BTN_SOUTH? 自定码) */
        prof2.hat_up = 1; prof2.hat_dn = 1; prof2.hat_lf = 1; prof2.hat_rt = 1;
        g_match[2] = &prof2;
        g_btn_code[2][6] = 30; g_btn_n[2] = 7;   /* profile: b 键用序号 6，序号 6 的 keycode = 30 */
        g_key[2] = 0;
        g_ax_cal[2][0][0] = -1; g_ax_cal[2][1][0] = -1;

        { struct input_event e = mk(EV_KEY, 30, 1); ev_apply(2, &e);
          CK(g_key[2] == RK_A, "profile 按键码 30 → A 置位"); }
        { struct input_event e = mk(EV_KEY, 30, 0); ev_apply(2, &e);
          CK(g_key[2] == 0,   "profile 按键码 30 释放 → 清"); }
        { struct input_event e = mk(EV_ABS, ABS_HAT0Y, 1); ev_apply(2, &e);
          CK(g_key[2] == RK_DOWN, "profile hat 路径 DOWN"); }
        { struct input_event e = mk(EV_ABS, ABS_HAT0Y, 0); ev_apply(2, &e);
          CK(g_key[2] == 0,       "profile hat 回中清"); }
    }

    printf(fails ? "\n*** %d FAIL ***\n" : "\nALL PASS\n", fails);
    return fails ? 1 : 0;
}
