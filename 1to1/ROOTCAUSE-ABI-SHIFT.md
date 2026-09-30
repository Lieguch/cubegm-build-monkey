

---

## 七、★ 落地实测（2026-09-27 收官）：**根治成立，DIVERGE 57 → 46**

命令链（可复算）：
```
LIBCFLAGS="-c -O0 -fno-sanitize=all -w -fno-strict-aliasing $ARCH $FIDELITY"   # 仅 libiconv + libcharset
sh tools/build_upstream.sh build/upstream   → OK
sh tools/link_full.sh build/ab/iconvO0.elf  → rc=0 size=5,746,056
python tools/diff_exec.py --batch --steps 3000 --ours build/ab/iconvO0.elf --out report/_t20_diff.txt
```

| 阶段 | 共有函数 | PASS | **DIVERGE** | TRUNC |
|---|---|---|---|---|
| 本轮起点（mxml 3.x / libiconv 1.17 @ -Os） | 741 | 661 | **75** | 5 |
| ＋ mxml → 2.9 | 744 | 682 | **57** | 5 |
| ＋ libiconv → 1.16 | 744 | 682 | 57 | 5 |
| ＋ **libiconv → `-O0`（对齐工厂）** | **778** | **727** | **46** | 5 |

* `abi_check.py`：**PASS（0 项失败）**；`diff_exec` 自洽校验 `727+46+5+0=778` ✓
* **iconv 族在 DIVERGE 里的行数：21 → 4** ⇒ ABI 位移假发散被根治（不是靠放宽判据）。
* 共有函数 744→778：-O0 让原被内联掉的一批静态函数重新有了独立符号（与工厂形态更接近）。
* ★ 关掉 UBSan 这件事**有官方依据**（不是试出来的）：
  Zig 0.14.0 Release Notes「UBSan Runtime — Zig now provides a runtime library for UBSan,
  which is **enabled by default when compiling in Debug mode**」；Zig 语言参考的优化档表亦写明
  `Debug(-O0)` = 优化关 + 安全检查开。故 `-O0` 必须显式配 `-fno-sanitize=all`（或 `-fno-sanitize=undefined`）。

## 八、剩余 46 行（36 个函数）的分布 —— 下一靶子

| 族 | 个数 | 性质 |
|---|---|---|
| **mui（我们自写专有 UI）** | **9** | ★ 真实缺陷，不是编译器伪影 —— **下一靶子** |
| zlib / unzip 工具类 | 4 | 待查 |
| libiconv 残余 | 3（`aliases_hash` / `iso2022_jp2_wctomb` / `locale_charset`） | 待查 |
| mxml 残余 | 3（`_mxml_entity_cb` / `mxmlEntityGetValue` / `mxml_file_putc`） | 待查 |
| 应用/驱动 | 15 | ConvertCode / DrawFrame / LoadMenuLog / UpdateROMProc / main_Menu … |
| CRT | 1（`__libc_csu_init`） | 非重建范围 |
