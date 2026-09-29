#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按**工厂机器行为**对齐 XUnzip 的 `timet2filetime`（1:1 对齐，不是补丁）。

## 证据链（全部可复算）

1. **工厂实现只有 12 字节**（`_Z14timet2filetimel` @0x12284，ARM）：
       str r1, [r0]
       str r1, [r0, #4]
       bx  lr
   即 `out->lo = timer; out->hi = timer;`
2. **调用点证实签名与用法**（`TUnzip::Get` 内 3 处，`tools/xref.py` 扫出）：
       ldr r1, [r8, sl]      ; r1 = timer
       mov r0, r7            ; r0 = &temp（8 字节 sret 缓冲）
       bl  timet2filetime
       ldm r7, {r0, r1}      ; 取回 FILETIME
       stm r3, {r0, r1}      ; 写进 ZIPENTRY 的 mtime/atime/ctime
3. 工厂**没有** `SystemTimeToFileTime`，也**没有** `DosDateTimeToFileTime`
   ⇒ 它的 zip 移植把 Windows 时间转换整套**桩掉**了。
4. 我方（上游 2018 变体）是完整实现：312 B，调 `gmtime` + 完整年月日时分秒转换。
   ⇒ 行为尺判 DIVERGE（`calls_ext F=[] O=['gmtime']`，三组输入全分歧）。

## 处置

把 `timet2filetime` 的实现换成与工厂**逐指令等价**的形式。
★ 这是"按工厂行为对齐"，不是放宽判据；回退见 `--revert`（用 `.bak_t2f` 备份）。
"""
import argparse
import io
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # tools/ 下 ⇒ 上溯两层
SRC = os.path.join(ROOT, "src", "upstream", "xunzip", "unzip.cpp")
BAK = SRC + ".bak_t2f"

OLD = """FILETIME timet2filetime(const time_t timer)
{ struct tm *tm = gmtime(&timer);
  SYSTEMTIME st;
  st.wYear = (WORD)(tm->tm_year+1900);
  st.wMonth = (WORD)(tm->tm_mon+1);
  st.wDay = (WORD)(tm->tm_mday);
  st.wHour = (WORD)(tm->tm_hour);
  st.wMinute = (WORD)(tm->tm_min);
  st.wSecond = (WORD)(tm->tm_sec);
  st.wMilliseconds=0;
  FILETIME ft;
  SystemTimeToFileTime(&st,&ft);
  return ft;
}"""

NEW = """FILETIME timet2filetime(const time_t timer)
/* ★★ 2026-09-28：按**工厂机器行为**对齐（1:1）。
 *
 * 工厂实现只有 12 字节（`_Z14timet2filetimel` @0x12284）：
 *     str r1,[r0] ; str r1,[r0,#4] ; bx lr
 * 调用点（`TUnzip::Get`，`tools/xref.py` 扫出 3 处）：
 *     r0 = &temp(8B sret) ; r1 = timer ; bl ; ldm r7,{r0,r1} ; stm ZIPENTRY+0x10c/0x114/0x11c
 * ⇒ 工厂把 Windows 时间转换整套桩掉了：**没有** SystemTimeToFileTime /
 *   DosDateTimeToFileTime，两个字段直接写 timer。
 *
 * 我方原实现（上游 2018 变体）是完整转换（312 B + 调 gmtime）⇒ 行为尺判
 * DIVERGE（三组输入全分歧，`calls_ext F=[] O=['gmtime']`）。
 * 回退：src/upstream/xunzip/unzip.cpp.bak_t2f
 */
{ FILETIME ft;
  ft.dwLowDateTime = ft.dwHighDateTime = (DWORD)timer;
  return ft;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    if a.revert:
        assert os.path.isfile(BAK), "没有备份，无法回退"
        shutil.copy2(BAK, SRC)
        print("已回退 unzip.cpp")
        return 0
    s = io.open(SRC, encoding="utf-8", errors="replace").read()
    if "dwLowDateTime = ft.dwHighDateTime" in s:
        print("已是工厂对齐版本，跳过")
        return 0
    assert OLD in s, "timet2filetime 原文锚点未命中"
    if not os.path.isfile(BAK):
        shutil.copy2(SRC, BAK)
        print("  备份源 ->", os.path.basename(BAK))
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s.replace(OLD, NEW, 1))
    print("timet2filetime 已按工厂行为对齐（12B 语义）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
