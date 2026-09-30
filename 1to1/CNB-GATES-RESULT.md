# CNB 云开发门禁首跑结果（2026-09-28）

> 你要求"去 CNB 的云开发环境调试"。本文是该路的**实测产出**：CNB 云开发工作区里
> **第一次**把 6 道本机跑不了的门禁（依赖 `arm-linux-gnueabihf-objdump`）跑在了**当前交付产物**上。
> 原始日志：`report/cnb_gates/2026-09-28.txt`。

---

## 一、为什么必须去 CNB（而不是"顺手"）

本机是 Windows/Git Bash，**没有** `arm-linux-gnueabihf-objdump` ⇒ 这 6 道门禁从未跑过，
一直只能写在"诚实声明"里。CNB 云开发是 x86_64 Linux（8 核），是 CI 之外唯一能跑它们的平台。

## 二、平台事实（全部实测，两条都会影响选择）

| # | 事实 | 证据 |
|---|---|---|
| 1 | **CNB 的「构建」流水线全部卡在 `Prepare`** —— 不是配置问题 | 平台原文：`Root Group's events CPU core-hours are insufficient for pre-freezing (Freezing time: 5.00 min, equivalent to 0.67 core-hours)`；`rkgame-rebuild`（长期存在的流水线）与 `1to1-linux-gates` 同样失败，我方的 stage 全 `skipped` |
| 2 | **云开发工作区可用**（走另一条配额路径），但**容器会周期性重启**（实测 `up 3 min`）＋约 15 分钟自动关闭 | 曾把"上传"与"执行"拆成两次 SSH ⇒ 重启清空 `/tmp` ⇒ **命令毫无输出**（看似平台问题，实为用法问题） |

⇒ 结论：**构建走 `artifacts-gates` 分支的声明式流水线（已存在，欠配额）**；
   **门禁调试走云开发工作区，且必须"单连接"**。

## 三、落地工具（一条命令）

`tools/cnb_ws_gates.sh` —— 开工作区 → 取 SSH → **单连接**（tar 经 stdin 管道）上传 + 装依赖 + 跑门禁。

调试过程中修掉的**四个自伤缺陷**（都不是平台问题）：

| # | 缺陷 | 现象 | 修法 |
|---|---|---|---|
| 1 | `A=... timeout ssh "$A"` 写在同一行 | 变量为空 ⇒ `connect to host :22` | 赋值独立成句 |
| 2 | 远端 `cd /workspace/1to1 && …` 用 `&&` 串 | 目录不存在 ⇒ 整串短路 ⇒ **零输出** | 探测项目目录 + 逐步 `echo` |
| 3 | `tar xzf - \|\| exit 8` | `tar` 经 ssh 管道返回 **rc=2**（流末尾告警）但文件**已完整解出** ⇒ 被当失败 | 判据改为**后置条件**：文件在 + **sha256 相等** |
| 4 | 门禁参数各写各的 | ① `scan_symbol_delta` 的台账**只在显式传 `--pending` 时才读** ⇒ 已知债务被报成新增违规；② `ci_p2a_stb` 没有参数解析，被传 `--objdump <path>` 后当成 json 文件名 ⇒ `FileNotFoundError` | **逐字照抄 CI**（`.github/workflows/1to1-verify.yml`）；`rc=3` 归入"前置缺失"而非失败 |

★ 另发现一处主链缺陷：`link_full.sh` 的 `PY="${PY:-python}"` 会回退到**无 pyelftools 的系统 python**
⇒ 门禁抛 `ModuleNotFoundError` 被当成"门禁 FAIL"（假失败）。已加**依赖自检 + 已知 venv 兜底 + 指名报错**。

## 四、门禁结果（首跑，对当前交付产物）

| 门禁 | rc | 结论 |
|---|---|---|
| `scan_symbol_delta`（上游 API 集合） | **0** | 工厂 228 / 我方 228，台账生效 ⇒ 无新增 |
| `scan_cxx_abi`（C++ 签名） | **0** | **62 / 62，签名不一致 = 0** —— 含 `TUnzip::Find(char const*, unsigned char, int*, ZIPENTRY*)` |
| `scan_livein_args`（调用点实参寄存器） | **1** | HIGH **6** / LOW 41；台账 1 行已修好（已按棘轮删行） |
| `scan_kr_argcount`（K&R 调用点个数） | **1** | **17 个函数**我方调用点参数个数少于工厂 |
| `scan_dead_loop` | 3 | **前置缺失**：需要 `build/obj`（工作区只有最终 ELF） |
| `ci_p2a_stb` | 1 | 首跑因**我的参数错误**（见上表 #4④） |

### 4.1 `scan_livein_args` — HIGH 6 项（缺的寄存器**确在被调者 live-in 中** ⇒ 会把垃圾当参数用）

| 调用对 | 未设寄存器 | 工厂/我方调用点数 |
|---|---|---|
| `AudioProcess -> PlaySound` | r1 | 1 / 1 |
| `TestRun -> PlaySound` | r1 | 1 / 1 |
| `UpdateROM -> UpdateROMProc` | r1 | 1 / 1 |
| `johab_hangul_decompose -> johab_hangul_wctomb` | r3 | 1 / 1 |
| `PauseMenu -> mui_DispBlock` | r3 | 1 / 1 |
| `mui_setting -> mui_DispBlock` | r3 | **6 / 5** |

### 4.2 `scan_kr_argcount` — 17 个函数（摘录，按"我方少几个"排序）

| 函数 | 工厂 min | 我方 min | 工厂调用点数 | 最少处示例 |
|---|---|---|---|---|
| `strupr` | 1 | **0** | **10** | `mui/shoucang.c` |
| `FilePreEmu` | 1 | **0** | 2 | `mui/SeletEmuCore.c` |
| `GetFilenameExt` | 1 | **0** | 4 | `core/FilePreEmu.c` |
| `SoundClose` | 1 | **0** | 5 | `mui/mui_SoundplayThread.c` |
| `video_driver_set_colormode` | 1 | **0** | 5 | `mui/PauseMenu.c` |
| `spi_read` / `spi_write` | 3 | **2** | 1 | `flash/UpdateROMProc.c` |
| `outputblankxy` | 4 | 3 | 1 | `misc/DisplayLine_list.c` |
| `dir_serial_list` | 2 | 1 | **13** | `misc/dir_serial_list.c` |
| `Mp3DecodeLoop` | 1 | 0 | 2 | `hw/AudioProcess.c` |
| `FBA_Load` / `EmuCore_Blank` / `JoystickTest` / `getticks` / `snor_write_en` / `InitKeyMapping0fEmuType` / `mui_DisplayInputBuffer` | 1–3 | 0–3 | — | 见完整日志 |

⇒ 与 4.1 是**同一主题**：**调用点比被调者少给参数**。在 ARM 上就是"传寄存器垃圾"。

## 五、`scan_dead_loop` rc=3 的正确处置

它需要 `build/obj`（213 个逐函数对象）。云开发工作区只上传最终 ELF ⇒ 前置缺失。
两条正确路径：① 在**声明式流水线**里先构建再跑（该流水线已含 `build-1to1` stage）；
② 工作区里补传 `build/obj`。**不要**把它算成"门禁不通过"。

## 六、★ 本机编译已被沙箱守卫挡住（新阻塞，需你处置）

末次尝试重编 XUnzip 时，zig 报出误导性错误链，逐层追到底：

```
$CC -x c++ ... src/upstream/xunzip/unzip.cpp
warning(compilation): failed to delete 'build\_zigcache_bfa2_C\tmp\e71f23d870e8ad6e-abi-note.o.d': AccessDenied
src/upstream/xunzip/unzip.cpp:1:1: error: FileNotFound
error: sub-compilation of glibc Scrt1.o failed        ← 连 zig 自带的 glibc 都编不动
```
直接用 shell 验证：

| 操作 | 结果 |
|---|---|
| 写文件 | **OK** |
| 读文件 | **OK** |
| `rm -f` | **被拒** —— `[safe-delete][SAFE_DELETE_BULK_GUARD_ERROR] state lock timeout` |

⇒ **`safe-delete` 守卫处于"state lock timeout"的坏状态**，删除一律被拒；
zig 需要清理自己刚写的临时文件（`.o.d`）⇒ 被拒 ⇒ 报 `AccessDenied` ⇒ 继而 `FileNotFound`。
**换全新缓存目录也无效**（它需要删自己刚建的文件）。

⇒ **本机任何重建目前都不可能完成**。需要你处置：复位/修复沙箱的 safe-delete 守卫状态。
（已交付的产物是在守卫劣化**之前**构建并验证过的 `build/rkgame.rebuilt.elf`，
sha256 见下，未受影响。）

## 七、这两条阻塞下的正确路径

| 通道 | 状态 | 用途 |
|---|---|---|
| 本机编译 | **被守卫挡住** | 待复位 |
| CNB **构建**流水线 | **CPU 配额耗尽** | 待提升配额（`.cnb.yml` 已就绪） |
| CNB **云开发工作区** | **可用** | 跑门禁（已跑通）／**下一步用它编译** |

**CNB 工作区编译的可行性已核实**：`tools/link_full.sh` 的 `winpath()` 在 Linux 下是**恒等**
（`cygpath` 不存在则原样返回）⇒ 构建脚本本身 Linux 可跑；`cnb_env.sh` 已用
`pip install ziglang` 取 zig（与 CI 同一版本）。所以把
`link_audit.sh + build_upstream.sh + link_full.sh` 放进工作区即可编译 ——
但**必须**在 15 分钟窗口内完成（213 个专有对象 ≈7 min + 上游 ≈2 min + 链接 ≈1.5 min
＋ 门禁），建议改成"分段续跑 + 状态落盘"再用。

## 八、本轮的净结果（可核对）

| 项 | 值 |
|---|---|
| 交付产物 | `build/rkgame.rebuilt.elf` **5,521,740 B** |
| 行为尺 | PASS **733** ｜ **DIVERGE 44** ｜ TRUNC 5 ｜ SKIP 0（自洽 782 ✓） |
| 本地 8 道门禁 | 全 PASS（PT_LOAD / RELRO / MMIO 宽度 / 设备访存类级 / 体量覆盖 SHORT 0 / UB 0 / 单侧未建模 OK） |
| `.dynsym` | 工厂 113 ｜ 我方 110 ｜ 工厂有/我方无 **5** ｜ 我方有/工厂无 **2** |
| CNB 门禁 | 6 道首跑；`symbol_delta`/`cxx_abi` PASS，另 4 道给出真问题清单 |

### 8.1 沙箱降级的第二个证据（同一根因）

Python 连临时目录都建不了：

```
FileNotFoundError: No usable temporary directory found in ['R:\TEMP', ...,
                        'C:\Users\Administrator\AppData\Local\Temp', 'D:\output\rkgame-1to1']
```
⇒ 删除被拒 + 临时目录不可用 ⇒ zig（需要 tmp 与清理）**必然失败**。
这两条一起构成"本机无法重建"的完整解释。

## 九、下一步（按价值排序）

| # | 事项 | 前置 |
|---|---|---|
| 1 | **复位沙箱 safe-delete 守卫 / 临时目录** | **需你处置**（物理动作） |
| 2 | 把 `timet2filetime` 对齐**编进产物**（源已改，`src/upstream/xunzip/unzip.cpp`，1 处） | 依赖 1 |
| 3 | 修 4.1 的 **6 个 HIGH**（缺的寄存器确在被调者 live-in 中） | 依赖 1（需重编） |
| 4 | 修 4.2 的 **17 个漏参** | 依赖 1 |
| 5 | 给 `scan_kr_argcount.py` **接线**（当前 0 个 workflow） | 无 |
| 6 | `scan_dead_loop` 在流水线里跑（需 `build/obj`） | 依赖 1 或 CNB 编译 |
| 7 | CNB **构建配额**提升 | **需你处置**（根组织管理员） |
| 8 | 用 **CNB 云开发工作区编译**（绕开本机守卫与构建配额） | 见 §七；建议分段续跑 |


