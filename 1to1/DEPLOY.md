# DEPLOY.md —— 验收交付说明（交付物 / 怎么验 / 路径）

> 一句话：**从 CI 下载 `rkgame-rebuilt-<sha>` → 校验 sha256 → 覆盖 `/sdcard/cubegm/rkgame`（先备份原厂）
> → 按 `ACCEPTANCE.md` 的 A/B/C 逐项验 → 回填验收记录。**

## 1. 交付物是什么

| 项 | 值 |
|---|---|
| 名称 | `rkgame-rebuilt-<commit-sha>`（GitHub Actions artifact，zip） |
| 内容 | `rkgame.rebuilt.elf`（部署用二进制） + `rkgame.rebuilt.elf.sha256`（校验文件） |
| 生成位置 | 工作流 `1to1-verify` 的步骤「上传可部署产物（真机验收用）★ 交付物」 |
| 保留期 | 30 天 |

**下载方式（二选一）**

- **A. 网页**：GitHub → `Lieguch/cubegm-build-monkey` → Actions → 最近一次 **`1to1-verify`（success）**
  → 页面底部 *Artifacts* → 点 `rkgame-rebuilt-<sha>`。
- **B. 命令行**（`<ARTIFACT_ID>` 从 API 取；`<TOKEN>` 用你自己的）：
  ```bash
  curl -L -H "Authorization: Bearer <TOKEN>" \
    https://api.github.com/repos/Lieguch/cubegm-build-monkey/actions/artifacts/<ARTIFACT_ID>/zip \
    -o rkgame-rebuilt.zip
  unzip rkgame-rebuilt.zip -d rkgame-rebuilt/
  ls -l rkgame-rebuilt/
  ```

**上机前必须校验**（否则"设备上那个二进制是哪次提交"无法证明）：

```bash
cd rkgame-rebuilt/
sha256sum -c rkgame.rebuilt.elf.sha256     # 必须输出 OK
```

## 2. 文件路径（设备侧）

| 用途 | 绝对路径 | 说明 |
|---|---|---|
| **替换目标** | `/sdcard/cubegm/rkgame` | 就是它，覆盖前**必须先备份** |
| **原厂备份** | `/sdcard/cubegm/rkgame.factory.bak` | 红线：原厂文件只备份、不删除 |
| 不要动 | `/sdcard/cubegm/ui_cn.zip`、`/sdcard/cubegm/joystick.zip` | 原厂原样 |
| 不要动 | `/sdcard/cubegm/cores/`（000=fba…008=2600）、`/sdcard/cubegm/saves/` | 游戏与存档 |
| 运行日志（证据） | `/sdcard/cubegm/menu.log` | 验收 A/C 的证据之一 |

**落地步骤**

```bash
# 1) 备份原厂（只做一次；存在就跳过）
[ -f /sdcard/cubegm/rkgame.factory.bak ] || cp -p /sdcard/cubegm/rkgame /sdcard/cubegm/rkgame.factory.bak

# 2) 覆盖（从读卡器/ADB 推入后）
cp rkgame-rebuilt/rkgame.rebuilt.elf /sdcard/cubegm/rkgame
chmod 755 /sdcard/cubegm/rkgame

# 3) 记录（写进验收记录）
sha256sum /sdcard/cubegm/rkgame
ls -l /sdcard/cubegm/rkgame /sdcard/cubegm/rkgame.factory.bak
```

**回滚（任何一项判失败时）**

```bash
cp -p /sdcard/cubegm/rkgame.factory.bak /sdcard/cubegm/rkgame
```

## 3. 怎么验收（照做即可）

判据表在 `ACCEPTANCE.md`：**A 启动/菜单 6 项、B 列表/启动/音频 6 项、C 存档 3 项**。
全部通过 = 可替代；任一项失败 = 该项即唯一根因入口。

### A 类（启动与菜单，5 分钟）

| 步骤 | 动作 | 证据 |
|---|---|---|
| A1 | 上电，等主菜单出现（≤ 30 s） | **拍照 1 张**（要能看清菜单整体） |
| A2 | 放大看菜单文字 | **拍照 1 张**（中文完整、不乱码） |
| A3 | 按 ↑ ↓ 各 5 次 | **拍照 2 张**（高亮位置变化前后） |
| A4 | 按 ← → 切换分页/分组 | **拍照 1 张** |
| A5 | 连续操作 60 s | 计时截图/口述记录（无卡死） |
| A6 | 按返回键回上级 | **拍照 1 张** |

### B 类（列表与游戏启动，15 分钟）—— qemu 未覆盖，首验重点

| 步骤 | 动作 | 证据 |
|---|---|---|
| B1 | 放一个已知 ROM 到对应目录，如 MD 游戏放 `/sdcard/cubegm/cores/003/`（003=MD） | **拍照**（列表出现该文件名） |
| B2 | 选中并启动该 ROM | **拍照**（core 画面出现）+ 记录启动耗时 |
| B3 | 试玩 30 s：方向 + A/B 键 | **录屏 15 s** 或照片 |
| B4 | 退出游戏回菜单 | **拍照**（菜单仍可用） |
| B5 | 游戏内听声音 | **录音 5 s**（有声音、不爆音） |
| B6 | 连续启动/退出 3 次 | 日志：`cat /sdcard/cubegm/menu.log \| tail -50`（无 panic/segv） |

### C 类（存档，10 分钟）—— qemu 未覆盖，首验重点

| 步骤 | 动作 | 证据 |
|---|---|---|
| C1 | 游戏内存档 → 退出 | `ls -l /sdcard/cubegm/saves/` **截图** + `sha256sum /sdcard/cubegm/saves/*.srm` |
| C2 | 断电重启 → 进同一游戏 → 读档 | **拍照**（存档内容可见） |
| C3 | 重复一次相同操作（C1） | 两次 `sha256sum` **逐字节一致**（贴两行输出） |

## 4. 回填验收记录（只增不改）

把结果追加到 `ACCEPTANCE.md` 末尾「验收记录（只增）」：

```
### 2026-10-25 / 产物 rkgame-rebuilt-<sha> / 设备 sha256=<...>
A1 ✓  A2 ✓  A3 ✓  A4 ✓  A5 ✓  A6 ✓
B1 ✓  B2 ✓  B3 ✓  B4 ✓  B5 ✓  B6 ✓
C1 ✓  C2 ✓  C3 ✓
证据：照片 X 张 / 录音 Y 段 / menu.log 尾部 Z 行
```

## 5. 已知偏差（不影响本清单，但要知情）

| 偏差 | 现状 | 处置 |
|---|---|---|
| qemu `B6 frame_hash` 全零基线 | 观测天花板（driver.so 自封私有画布） | 以真机 A1/A2 为准 |
| qemu `B6A frame_hash_abi` 差异 | 中心区逐像素 100% 相同、无平移；差异在 `x≈0..100` 与 `x≈670..1280` | 真机 A1/A2 为最终裁决；对照端确定性判据已在 CI 跑 |

## 6. 当前可直接用的产物

- 最新完整产物（含 `rkgame.rebuilt.elf.sha256`）：**该次 `1to1-verify` 成功后**的
  `rkgame-rebuilt-<sha>`（本文件同批推送后的运行）。
- 若只有旧产物（`04738955ed16…`、`0ce4864a2056…`）：它们**不含** `.sha256` 文件（早于本改动），
  上机前请自行 `sha256sum` 记录，并在验收记录里写明实际值。
