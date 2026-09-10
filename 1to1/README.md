# rkgame 1:1 忠实重构工程

> 目标：用反编译产物忠实重构 rkgame v1.42，编译产物**直接替换** `/sdcard/cubegm/rkgame` 后保留 **100% 原厂功能**。
> 原则：**不猜、不赌运气、不穷举**；每个结论都有可复现的机械验证。

---

## 1. 事实基线（实测，非推测）

| 项目 | 值 |
|---|---|
| 原厂二进制 | 3,921,108 B |
| ELF | ARM32 EABI5 **hard-float**（`e_flags=0x5000400`），**ET_EXEC（非 PIE）** |
| 入口 / 解释器 | `e_entry=0x9d44` / `.interp=/lib/ld-linux-armhf.so.3` |
| 链接 | **动态**（NEEDED: libz, libdl, libm, libstdc++, libpthread, libgcc_s, libc） |
| 符号 | **未 strip**，2615 符号，804 具名函数 |
| 反编译 | **812/812 = 100%**（Ghidra 12.1.3 + JDK 21） |
| 原始单元 | **41 个** `STT_FILE` 编译单元 |
| 构建工具链 | `armv7a-libreelec-linux-gnueabi`（LibreELEC/Lakka 8.0 系，**glibc 2.24**） |

## 2. 真实重构量（确权结果）

| 归属 | 函数 | 代码字节 | 占比 | 处置 |
|---|---:|---:|---:|---|
| **上游开源** | 581 | 194,454 | **61.3%** | 按匹配版本从上游重建 |
| **专有** | 223 | 122,922 | **38.7%** | 逐函数忠实重建 |

**上游组件**：glibc iconv（275f）· stb_truetype（81f）· **XZip/miniunz/内嵌 zlib 1.1.x**（64f）·
Helix MP3（23f）· mini-XML（30f）· libgcc 运行库

**专有模块分布**（`ledger/functions.csv` 全表）：

| 模块 | 函数 | 字节 |
|---|---:|---:|
| mui（菜单 UI 系统） | 42 | 70,396 |
| core（核心加载器 `*_Load`/SeletEmuCore/EmuRun） | 26 | 15,100 |
| misc（待细分） | 92 | 13,086 |
| input（手柄/按键） | 11 | 9,736 |
| flash（sfc/spi/snor/固件升级） | 29 | 6,860 |
| hw（显示/音频/初始化） | 20 | 5,500 |
| config | 2 | 1,752 |
| main | 1 | 492 |

## 3. 验证方法学（★ 本项目核心）

### 3.1 函数级差分门禁（`tools/funcdump.py` + `tools/funcdiff.py`）

原厂二进制 = **oracle**。分级判定：

| 等级 | 含义 | 强度 |
|---|---|---|
| **T1** | 归一化后「助记符 + 操作数（符号化目标）」序列完全一致 | 最强证据 |
| **T2** | 仅助记符序列一致（寄存器分配不同） | 中证据 |
| **T3** | 指令条数一致 | 弱证据，须人工复核 |
| **FAIL** | 以上皆不满足 | 必须定位 |

门禁通过 = T1+T2。归一化消除「地址布局差异」，保留「语义差异」。

```bash
# 1) 生成金标准（原厂反汇编 -> 逐函数归一化）
python tools/funcdump.py <objdump -d 文本> golden/factory.funcs.json

# 2) 生成候选（重建产物同法）
python tools/funcdump.py <rebuild objdump> report/rebuild.funcs.json

# 3) 差分
python tools/funcdiff.py golden/factory.funcs.json report/rebuild.funcs.json \
       --json report/diff.json
# 定位单函数
python tools/funcdiff.py golden/factory.funcs.json report/rebuild.funcs.json --detail mui_menu
```

**自检已通过**：golden vs golden = 835/835 = 100% T1；人为扰动被正确拦截。

### 3.2 上游版本指纹匹配（`tools/vermatch.py` / `tools/stb_range.py`）

组件**函数名集合**是强版本指纹。逐版本拉取上游源码 → 抽取函数名 → 与原厂集合比对。

**已得结论**：
- stb_truetype：v1.19～v1.26 **全部**覆盖原厂 81/81 函数 → **名称指纹不足以定版**，
  须由 CI 用**同工具链**编译后按函数尺寸/指令序列比对落定。
- 内嵌 zlib：由 `huft_build`/`inflate_blocks`/`inflate_codes`/`inflate_trees_*` 判定为 **1.1.x**，
  必须取 XZip 所附旧版源码（**不可**用 1.2.5）。

## 4. 目录结构

```
rkgame-1to1/
├── tools/                     # 验证与方法学工具（可复算）
│   ├── funcdump.py            # objdump -d -> 逐函数归一化序列
│   ├── funcdiff.py            # 函数级差分门禁（T1/T2/T3/FAIL）
│   ├── vermatch.py            # 上游版本指纹匹配
│   ├── stb_range.py           # 版本区间求解
│   ├── extract_factory_funcs.py   # 原厂组件函数名抽取
│   └── build_workspace.py     # 生成重建工作区 + 台账（可复算确权）
├── golden/factory.funcs.json  # ★ 原厂金标准参照集（835 函数 / 715,473 指令）
├── ledger/functions.csv       # 逐函数进度台账（223 专有函数）
└── src/proprietary/<module>/  # 各专有函数的 Ghidra 反编译参考实现
```

## 5. 分阶段门禁

| 阶段 | 动作 | 门禁 |
|---|---|---|
| P1-A | 差分工具链 + 金标准 | ✅ 已完成并自检 |
| P1-B | 源树还原 + 确权 | ✅ 已完成（41 TU / 61.3% 上游） |
| P2-A | 上游组件版本锁定 | 同工具链编译后**符号集 + 函数尺寸**逐项对齐 |
| P2-B | 223 个专有函数重建 | **函数级语义等价差分**逐函数通过 |
| P3 | 链接 + ABI | ELF 头 / `.interp` / `e_flags` / ET_EXEC / NEEDED 与原厂一致 |
| P4 | 行为差分 | oracle 比对（帧缓冲 / 日志 / 文件 / syscall） |
| P5 | 真机验收 | 19088 游戏列表 / 中文 UI / 全菜单 / 存档 / BGM |
| P6 | 替换 + 回滚 | 原子替换，一键回滚 |

## 6. 保命红线（违反 = 变砖）

1. **绝不**改名/删除原厂 `icube`/`rkgame`/`driver.so`/`cores/libemu_*.so`/`root.dat`
2. **绝不**改写 `root.dat` / 校验分区 → 触发 "sdcard is damaged"
3. 每次构建强制 ABI 门禁（目标 ABI 须与原厂一致）

## 7. 环境与访问

- GitHub：`Lieguch/cubegm-build-monkey`，Token 见 `C:/Users/Administrator/cubegm-work/api_push.py`
- **网络通道**：`curl` 因 schannel 证书吊销检查失败（exit 35）不可用；
  须用 **Python `urllib.request` + `ssl._create_unverified_context()`**（HTTPS 仍加密，仅跳过证书链）
  或 `curl --resolve api.github.com:443:20.201.28.148`
- 推送：Git Data API（blob 格式 `{"content": <base64>, "encoding": "base64"}`，**推送后须逐 blob 校验 SHA1**）
