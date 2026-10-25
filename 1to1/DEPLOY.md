# DEPLOY.md —— 真机验收（你是 3 步，其余我做）

> 这次我把角色搞反了，已改回你惯用的方式：
> **你负责拿文件 → 上机 → 回传日志目录；判读、归因、回填记录全由我做。**
> 你不需要按清单拍照/录音/跑校验命令。

## 你只做三步

### 第 1 步：下载两个产物（GitHub Actions → Artifacts）

| 产物 | 用途 | 什么时候用 |
|---|---|---|
| `rkgame-diag`（内含 `rkgame.diag` + `.sha256`） | **取证版**：把设备上的运行过程写成 `trace.log` | **先跑这个** |
| `rkgame-rebuilt-<sha>`（内含 `rkgame.rebuilt.elf` + `.sha256`） | **交付版**：最终替代原厂的那个二进制 | 取证版日志判过 A 类后再换 |

下载位置：`Lieguch/cubegm-build-monkey` → Actions → `diag-build`（最新 success）/ `1to1-verify`（最新 success）→ Artifacts。

### 第 2 步：上机跑一次（约 1 分钟）

```bash
# 备份原厂（只做一次）
[ -f /sdcard/cubegm/rkgame.factory.bak ] || cp -p /sdcard/cubegm/rkgame /sdcard/cubegm/rkgame.factory.bak
# 用取证版替换（文件名改成 rkgame）
cp rkgame.diag /sdcard/cubegm/rkgame && chmod 755 /sdcard/cubegm/rkgame
```

开机 → 等主菜单出来 → 上下键按几下 → 等 30~60 秒 → 关机。

### 第 3 步：把日志目录回传给我（4 个文件）

设备上生成在 **`/sdcard/cubegm/_diag/`**：

| 文件 | 内容 |
|---|---|
| `trace.log` | 主证据：`jiffies + 标记 + 明细`（BOOT / DL / IO / VARCHK …） |
| `env.txt` | pid / cmdline / 系统环境 |
| `maps.start.txt` | 启动时的内存映射（含 driver.so、libz 等） |
| `frames.bin` | 帧快照（可能为 0 字节，视配置） |

把整个 `_diag/` 目录打包发我即可（跟以前 `真机验收日志/11/` 一样的四个文件）。

**如果方便，额外给一张主菜单的全屏照片** —— 只有"画面外观/中文是否正常"这一项日志判不了，其它全归我。

## 我拿到日志后做什么（不需要你参与）

| 判据 | 我从日志里怎么判 |
|---|---|
| A1 启动到菜单 | `BOOT enter` 出现 + 后续 IO 到 `ui_cn.zip`/`menu.raw` + 末条 jiffies 与起始差值（存活时长） |
| A3/A4 按键生效 | trace 里输入观测点（evdev/joy 读数）与 jiffies 序列 |
| A5 不卡死 | jiffies 是否持续推进；有无长空档 |
| A6 返回可用 | 菜单状态切换的 IO/调用序列 |
| A2 文字/画面 | **照片**（唯一需要你眼睛的项） |
| B2 core 启动 | trace 里 `DL dlopen ".../cores/00X/xxx.so"` 与随后的大量 IO |
| B5 声音 | 日志判不了 → 需你一句"有声音/无声/爆音"（不用录音） |
| C1 存档落盘 | trace 里 `IO fopen ".../saves/*.srm"` 写模式 + 写入字节数 |
| C2/C3 存档可读、稳定 | 第二次运行 trace 里读同一 `.srm` + 我比对两次内容哈希 |

判完我直接回填 `ACCEPTANCE.md` 的「验收记录」，并把失败项定位到具体函数/源码（这才是我的活）。

## 回滚（任何异常时你自己一条命令）

```bash
cp -p /sdcard/cubegm/rkgame.factory.bak /sdcard/cubegm/rkgame
```

## 路径速查

| 项 | 路径 |
|---|---|
| 被测二进制 | `/sdcard/cubegm/rkgame` |
| 原厂备份 | `/sdcard/cubegm/rkgame.factory.bak` |
| 诊断日志（回传这个） | `/sdcard/cubegm/_diag/` |
| 运行日志 | `/sdcard/cubegm/menu.log` |
| 不要动 | `/sdcard/cubegm/ui_cn.zip`、`joystick.zip`、`cores/`、`saves/` |
| ROM 放置（B 类时） | `/sdcard/cubegm/cores/003/`（003=MD，000=fba…008=2600） |

## 与以前流程的对应

| 以前（第 1–11 轮） | 现在 |
|---|---|
| 你拿 `rkgame.diag` 上机 | 同 |
| 你回传 `真机验收日志/N/`（env.txt / maps.start.txt / trace.log / frames.bin） | 同（设备上是 `/sdcard/cubegm/_diag/`） |
| 我解析日志给结论 | 同 |
| 我写"下一步改哪里" | 同 |

**唯一的变化**：交付物带 `.sha256`（可核对），产物名带 commit sha（可追溯）—— 这两点不增加你的操作。
