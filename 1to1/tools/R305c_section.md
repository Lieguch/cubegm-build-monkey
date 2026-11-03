# R305c — CNB 云开发同口径复现 qemu-behav（2026-11-03）

## 0. 本段要回答的唯一问题

> **本轮 `1to1-qemu-behav` 的失败，是否与 R305 的 ZIPENTRY 修复相关？**

R305b 留档的缺口是：判据行原文因本机 FastGithub 拦截（job logs 401 / artifact 401 / run check-runs 404）取不到，
GitHub connector 授权被 skipped ⇒ **未证明**「判据行与前三轮基线同形」。
本段按用户指令「走 CNB 云开发路径验证」，在 **CNB 云开发工作区**按 workflow step 12 **同口径**复现，
用判据行原文把这个问题**关掉**。

---

## 1. 首轮 CNB 复现：INCONCLUSIVE —— 根因是**环境**（guest shim 的 glibc 版本），不是被测实现

### 1.1 现象（`report/_r305_cnb/round1_behav_diff.txt`）

```
ci_qemu_behav rc=3
[INCONCLUSIVE] B0 参考侧（工厂）**没有真正的行为观测**：
    stdout_lines=0  新增文件=0  变更文件=0   （stderr_lines=2 不计）
```
三侧（factory / rebuild / control）全部 `exit=1`、`stdout=0 行`、`menu.log=2 行`、M0–M7 全 ✗。
对照 CI 基线（factory `exit=124`、stdout 多行、两侧 events≈228）⇒ **CNB 环境未能驱动参考实现**。

### 1.2 真因（直接证据在 `round1_behav_factory.json` 的 events 里）

```
E|/sdcard/cubegm/rkgame: /arm-root-device/lib/libc.so.6: version `GLIBC_2.38' not found (required by report/qemu/guest_shim.so)
E|/sdcard/cubegm/rkgame: /arm-root-device/lib/libc.so.6: version `GLIBC_2.34' not found (required by report/qemu/guest_shim.so)
```

链条（三方互证）：

| 环节 | 事实 | 证据 |
|---|---|---|
| 设备侧 ld.so | `golden/device_rootfs_min` = **glibc 2.29**（Buildroot），13 文件、ld.so OK | 远端日志 `[2/6]`；`build_guest_shim.sh` 注释（实测设备 glibc 2.29） |
| 构建侧编译器 | CNB 镜像是 **Debian 13**（libc 2.41），apt 装的 `gcc-arm-linux-gnueabihf` = **gcc 14.2.0-19cross1** | 远端日志 `libc-bin (2.41-12+deb13u4)` / `gcc-14-arm-linux-gnueabihf (14.2.0-19cross1)` |
| 探测顺序 | `tools/cgm_cc_probe.sh` 探测顺序 ③`arm-linux-gnueabihf-gcc` **早于** ⑦`zig` ⇒ 选中了 gcc-14 | `tools/cgm_cc_probe.sh` 第 20–27 行 |
| 后果 | gcc-14 打的 armhf `.so` 引用 `GLIBC_2.38/2.34` ⇒ guest ld.so 拒绝加载 ⇒ **LD_PRELOAD 失败** ⇒ guest 启动即 `exit=1`、stdout 0 行 | 上述 stderr 两行 |

> ★ 与 CI 的差异：CI workflow 有独立步骤「安装 zig」——
> `pip install ziglang==0.16.0` + `echo "CC=$ZIG cc" >> $GITHUB_ENV`
> ⇒ `cgm_cc_probe` 优先级①命中 zig ⇒ `build_guest_shim.sh` 走 `-target arm-linux-gnueabihf.2.29` 分支
> ⇒ shim 只要求 ≤2.29 ⇒ 设备 2.29 上可加载。**CNB 首轮缺这一步 ⇒ 环境不等价。**

### 1.3 已排除的其他猜测（避免"换个方向继续猜"）

| 猜测 | 证伪依据 |
|---|---|
| `/sdcard/cubegm` 资源未铺设 | 远端实查：`golden/sdcard_min` 在 workspace 内存在；`ci_qemu_behav.sh` 内部 `stage_sdcard_env.sh` 每轮重建 `$WORK` 并铺满（实测 `cores/ driver.so font.ttf joystick.zip …` 齐备） |
| 设备 sysroot 不全 | `[2/6]`：device_rootfs 13 文件、ld.so=OK |
| 三桩编译失败 | `[3/6]`：三桩全部生成，drm 17 符号导出、snd 20 符号导出、自证 0 未定义符号 |

---

## 2. 二轮复现：口径对齐（把「CI 怎么做的」逐条搬过来）

| CI 步骤 | CNB 二轮做法 | 证据 |
|---|---|---|
| workflow step「安装 zig」`ziglang==0.16.0` | `pip install --target /tmp/r305_ziglang ziglang==0.16.0`（**独立目录**，不覆盖镜像预装的 0.17.0）⇒ 版本断言 `= 0.16.0` 不符即 exit 11 | 远端日志 `[1b/6]` |
| `$GITHUB_ENV: CC=$ZIG cc` | `export CC="$ZIG cc"`（`cgm_cc_probe` 优先级①命中，全场 shim/桩同一把 zig） | 同上 |
| shim `-target arm-linux-gnueabihf.2.29` | 同（`build_guest_shim.sh` 的 `*zig*` 分支） | `[1c/6]` |
| workflow step「建立设备真实 sysroot」 | `cp -a golden/device_rootfs_min/. /arm-root-device/` | `[2/6]` |
| workflow step 11 三桩 | 同脚本三桩（zig `-target …2.29`，`-nostdlib`） | `[3/6]` |
| workflow step 12 env | `SYSROOT=/arm-root-device CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=30 CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1 CGM_ALSA_STUB=1 CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1 sh tools/ci_qemu_behav.sh <rebuilt.elf> <factory.bin> report/qemu` | `[4/6]`（逐字对齐） |

### 2.1 新增的机械门禁（把首轮事故固化成预检）

`build_r305_remote.sh` 新增 `[1c/6] shim 预检`：现场建一份 shim，用
`arm-linux-gnueabihf-objdump -T` 取其引用的**最高 `GLIBC_2.x` 次版本号**，
**> 29 ⇒ exit 13**（fail-closed，不靠"应该没事"）。二轮实测：`shim=941604 B`、`ELF 32-bit LSB shared object, ARM`、**最高 GLIBC 次版本 = 4**（≤2.29 ✔）。

---

## 3. 二轮判据结果（`report/_r305_cnb/behav_diff.txt`）

```
  参考端 report/qemu/behav_factory.json
     binary=/sdcard/cubegm/rkgame  sha=8ff3b4b70c253ff7
     workdir=/sdcard/cubegm  exit=124  stdout=26 行  log=menu.log/2 行
  重建端 report/qemu/behav_rebuild.json
     binary=/sdcard/cubegm/rkgame  sha=d34316b1…
     workdir=/sdcard/cubegm  exit=124  stdout=26 行  log=menu.log/2 行
  控制端 …（同一份参考二进制复跑）exit=124  events=227 行
--- 确定性控制（同一份参考二进制跑两遍）--- 参考侧 227 行 / 控制侧 227
  M0 进程启动 ✓✓✓   M1 配置读取 ✓✓✓   M2 SPI/SFC 初始化 ✓✓✓
  M3 driver.so 加载 ✓✓✓   M4 DRM 显示 ✓✓✓   M5 main_Menu 入口 ✓✓✓
  M6 UI 资源包打开 ✓(包已打开(条目缺失)) ×3   M6R 资源条目读取 ✓(ui.cfg+menu.raw 均读到) ×3
  M7 菜单存活 ✓(活着(exit=124)) ×3   MX 终止 exit=124 ×3
  → 两侧里程碑差集：空（完全同步）

  [FAIL] B6 frame_hash      b5449dc5 vs b5449dc5 —— 全零基线 b5449dc5 ⇒ 未观测到像素 / 全零基线 b5449dc5 ⇒ 未观测到像素
  [FAIL] B6A frame_hash_abi dfdaf563(1280x720x2560) vs ffc51130(1280x720x2560)
  [PASS] B6R frame_commits  3072 vs 3072（必须两侧都 > 0，否则"哈希相同"可能是都没画）
  ci_qemu_behav rc=2
```

### 3.1 与前三轮 CI 基线的逐字对照（`tools/_judge_behav_diff.py`）

| 判据行 | e5aef10e 轮 | 288fa2d0 轮 | ad13c99b 轮 | **R305 CNB 复现** | 判定 |
|---|---|---|---|---|---|
| B1 退出码 | 124 vs 124 ✓ | 同 | 同 | 124 vs 124 ✓ | 一致 |
| B2 events 前缀 | 228/228 | 同 | 同 | **227/227** | 行数差 1（见 §4） |
| B6 frame_hash | FAIL b5449dc5 vs b5449dc5 | 同 | 同 | **FAIL b5449dc5 vs b5449dc5** | **逐字一致** |
| B6A frame_hash_abi | FAIL dfdaf563 vs ffc51130 | 同 | 同 | **FAIL dfdaf563 vs ffc51130** | **逐字一致** |
| B6R frame_commits | PASS 3072 vs 3072 | 同 | 同 | **PASS 3072 vs 3072** | **逐字一致** |
| B7 shm | PASS 1 vs 1 | 同 | 同 | PASS 1 vs 1 | 一致 |
| B8a sfc_cmds | PASS 4 vs 4 | 同 | 同 | PASS 4 vs 4 | 一致 |
| B8b sfc_faults | PASS 180 vs 180 | 同 | 同 | PASS 180 vs 180 | 一致 |
| 门禁退出码 | 2 | 2 | 2 | **2**（`ci_qemu_behav rc=2`） | 一致 |

机械判定（脚本输出）：**三方 CI 基线彼此精确一致 = True**；本轮 vs 基线 = **结构同形**，
差异仅两处：B2 行数（228→227）与 `behav_diff 退出码` 行（该行由 **CI step 的 echo** 产生，
不在 `behav_diff.txt` 载体里 ⇒ 载体差异，非判据差异）。

---

## 4. 结论（分层标注）

### 4.1 已实测（证据充分）

1. **本轮 qemu-behav 的 FAIL 与 R305 ZIPENTRY 修复无关 —— R305 零回归。**
   判据行（B6/B6A/B6R/B1/B2/B7/B8a/B8b + 里程碑矩阵 M0–M7/M6R）与前三轮 CI 基线**同形**，
   其中 B6/B6A/B6R 三条**逐字一致**（含哈希值 `b5449dc5` / `dfdaf563` / `ffc51130` / `3072`），
   门禁退出码同为 2 ⇒ **该 FAIL 是继承态（R305 之前既有），非本轮引入。**
2. R305 重建侧与工厂侧在 CNB 里**行为完全同步**：M0–M7+M6R 全 ✓、里程碑差集为空、
   参考/重建/控制三侧均 `exit=124`、stdout 26 行、确定性控制前缀 227/227 自洽。
3. 首轮 INCONCLUSIVE 的根因已定位并修复：**guest shim 必须按设备 glibc（2.29）钉版本构建**，
   CI 靠 `CC=$ZIG cc` + ziglang 0.16.0；CNB 缺这一步时 gcc-14 产物引用 GLIBC_2.38 ⇒ 侧载失败。
   新增 `objdump -T` 预检门禁（>29 即 exit 13）已固化。

### 4.2 未取证 / 不下结论

- **B2 行数差 1（CI 228 vs CNB 227）**：差的 1 行是 **guest stdout**（CI `stdout=27 行` vs CNB `26 行`），
  且它**同时出现在参考侧与重建侧**、CNB 内两侧逐行一致 ⇒ 属**环境口径差异**，与实现无关。
  具体是哪一行**未取证**（CI 的 `behav_*.json` artifact 因 FastGithub 401/502 不可得；CI 日志只打印 stdout 头部 3 行）。
  ⇒ 不影响 §4.1 结论（三条判据行逐字一致 + 里程碑差集空）。
- **B6A 像素哈希差异（dfdaf563 vs ffc51130）的成因**：R171b/R224 起长期跟踪的既有观测项，
  本段**只证明"与 R305 无关"**，**不解释**其成因。

### 4.3 用户侧（仍未实测）

- 新 ELF（`d34316b1…`，5,404,120 B）入卡复测「是否还闪重启」= **未实测推断**（R305 真机侧结论待用户复测）。

---

## 5. 本段新增纪律（不要再踩）

1. **凡要在 guest 内加载的 .so（LD_PRELOAD 的 shim、dlopen 的桩），构建工具链必须按设备 glibc 钉版本**；
   用发行版交叉 gcc（尤其 Debian 13 / gcc-14）会引入 GLIBC_2.3x/2.38 需求 ⇒ 设备 2.29 侧载失败，
   表现为「guest 立刻 exit=1、stdout 0 行」，**极易被误读成"被测实现坏了"**。
   ⇒ 预检：`arm-linux-gnueabihf-objdump -T <so> | grep GLIBC_2.` 取最高次版本，> 设备版本即失败。
2. **"参考侧没有任何观测" ⇒ 先怀疑环境，不要先怀疑实现**（本段首轮即栽在这里）。
   判据顺序：stdout 行数 → stderr 原文 → 动态链接器版本需求 → 资源铺设 → 最后才谈实现。
3. **CNB 云开发 ≠ CI 等价**：镜像自带 **ziglang 0.17.0**（uv site-packages，可执行文件不在 PATH），
   且 `cgm_cc_probe` 会优先命中 apt 装的 `arm-linux-gnueabihf-gcc` ⇒ 复现前必须**显式钉 CC 与 zig 版本**
   （本段用 `--target` 独立目录 + 版本断言实现）。
4. **CI 判据行取不到时，用同口径云复现补证**（本段范式：逐条对齐 workflow 步骤与 env，
   先用 `objdump`/stderr 证据确认环境等价，再读判据行）。

---

## 6. 产物索引

| 文件 | 内容 |
|---|---|
| `report/_r305_cnb/behav_diff.txt` | 二轮判据原文（B1–B8b + 里程碑矩阵） |
| `report/_r305_cnb/behav_factory.json` / `behav_rebuild.json` | 二轮两侧行为观测（events 227 行 / frame_commits 3072） |
| `report/_r305_cnb/round1_*` | 首轮 INCONCLUSIVE 证据（含 glibc 版本报错原文） |
| `report/_r305_cnb/remote_run2.log` | 二轮远端全量日志（[1b]~[6/6] + 判据摘要 + b64 回传） |
| `tools/_cnb_r305_repro.sh` | 远端复现段（workspace 内执行） |
| `tools/_cnb_r305_driver.sh` | 本机驱动（起/复用 workspace → 上传 → 远端跑 → b64 取回 → 解包） |
| `tools/_judge_behav_diff.py` | 判据行四方对照（按 outdir 定位主门禁段、保留哈希原文、双口径判定） |
| CNB workspace | `sn=cnb-l6s-1k6fl7dmi`（**已 stop**，省钱纪律） |
