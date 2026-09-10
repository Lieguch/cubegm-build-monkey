# rkgame 1:1 重构 · 状态与交接（2026-09-10 夜）

## 一、本轮已交付（全部经机械验证）

| 交付物 | 状态 | 验证证据 |
|---|---|---|
| **差分验证工具链** `tools/funcdump.py` + `tools/funcdiff.py` | ✅ | 自检 golden-vs-golden = **835/835 = 100% T1**；人为扰动被正确判为非通过 |
| **原厂金标准参照集** `golden/factory.funcs.json.gz` | ✅ | **835 函数 / 715,473 指令**；CI 内断言 835 + 715473 通过 |
| **源树还原 + 确权** | ✅ | 41 个 `STT_FILE` 编译单元；上游 581f/194,454B(61.3%) vs 专有 223f/122,922B(38.7%) |
| **重建工作区 + 逐函数台账** | ✅ | `ledger/functions.csv` 223 专有函数（地址/尺寸/模块/源文件） |
| **上游版本指纹工具** `tools/vermatch.py` / `stb_range.py` | ✅ | 已跑通并得出结论（见下） |
| **P2-A CI 作业** `.github/workflows/1to1-verify.yml` | ✅ | run #2 success，真实数据产出于作业日志 |
| **假绿根除** | ✅ | 加硬门禁（覆盖为 0 → `exit 1`）+ 取证转储；修复后索引 bug（`p[1]`→`p[4]`） |

**GitHub 提交**：`7697e370` → `bd17402d` → `9c993748` → `245eee2d`（均 8~11/11 blob SHA1 校验通过）

## 二、本轮关键发现（推翻旧认知）

| # | 旧认知 | 更正（证据） |
|---|---|---|
| 1 | zlib 1.2.5 | **误判**——`1.2.5` 是 `.rodata` 数据表字节。真相：`XUnzip.cpp` 内嵌 **zlib 1.1.x**（`huft_build`/`inflate_blocks`/`inflate_codes` 为 1.1.x 特征，1.2.0 已删除） |
| 2 | "XUnzip 组件" | 实为 **XZip(`TUnzip`/`LUFILE`) + miniunz(`unzip.c`) + 内嵌 zlib**，因是 C++ 编译单元故符号全被修饰 |
| 3 | 需重建 812 函数 | **实际专有仅 223 函数 / 122,922 B**（上游 61.3% 可从上游重建） |
| 4 | 从零重写可行 | **已被真机证伪**（日志空转 `waiting for Phase 4 UI`；原厂有 19088 游戏 + 中文 UI） |
| 5 | 名称指纹可定版 | **不足以定版**——stb_truetype v1.19~v1.26 全部 81/81 覆盖 |

## 三、当前阻塞（唯一硬前提）

**P2-A 版本锁定受阻于工具链不匹配。**

CI 实测（Ubuntu GCC 11.4）编译 v1.21–v1.26，平均尺寸偏差 **49.6%–49.7%**，全版本不可区分。
→ 必须取得原厂同款工具链才能定版。

**需要的工具链**：`armv7a-libreelec-linux-gnueabi`（LibreELEC/Lakka 8.0 系，glibc 2.24）
- 证据：`.file` 符号含 `/home/vmuser/Lakka/build.Lakka-a10.arm-8.0-devel/glibc-2.24/.armv7a-libreelec-linux-gnueabi/csu/start.o`
- 获取途径（按可行性）：① LibreELEC 8.0 a10 的 SDK/buildroot 产物；② 自行用 crosstool-NG 按 glibc 2.24 + GCC 6.x 复现；③ Lakka 源码树 `build.Lakka-a10.arm-8.0-devel` 的 toolchain 输出

## 四、下一步（按依赖顺序）

| # | 动作 | 门禁 | 阻塞 |
|---|---|---|---|
| **N1** | 取得/复现 `armv7a-libreelec-linux-gnueabi`（glibc 2.24, GCC 6.x） | 能编译并产出 ARM32 hard-float 目标文件 | ★ 当前唯一阻塞 |
| N2 | 复跑 `1to1-verify` 定版 5 个上游组件 | 覆盖 81/81 且尺寸偏差 < 5% 的版本唯一 | 依赖 N1 |
| N3 | 用 N1 工具链复现 `_start`/crt，验证能产出与原厂 `.interp`/`e_flags` 一致的 ELF | ELF 头逐字段一致 | 依赖 N1 |
| N4 | 按 `ledger/functions.csv` 逐函数重建（优先 `mui` 42f/70KB） | 函数级 **T1/T2** 差分通过 | 依赖 N1+N2 |
| N5 | 链接 + 行为差分 | oracle 比对全绿 | 依赖 N4 |
| N6 | 真机验收 | 19088 游戏 / 中文 UI / 全菜单 / 存档 / BGM | 依赖 N5 |

## 五、诚实的工作量评估

- **基础设施已 100% 完成**（工具链、金标准、台账、CI、假绿门禁）——这是后续一切的地基。
- **实际重建尚未开始**：223 个专有函数 / 122,922 B 的忠实重建是主体工作量，
  且必须先解决 N1（工具链）才能进入「编译—差分—修正」闭环。
- 在 N1 解决前强行开始 N4 会重蹈「无验证的从零重写」覆辙，**故本轮到此为止是正确的工程判断**。

## 六、复盘：本轮踩到的坑（已修，勿重复）

1. **GitHub 密钥扫描**：脚本硬编码 Token 会被 422 拦截 → 一律用 `os.environ['GH_TOKEN']`。
2. **CI 日志/制品下载**：`/logs` 与 `/artifacts/{id}/zip` 是 302 到签名 URL，
   带 `Authorization` 头会被 401 → 须**跟随时去掉该头**；`/logs` 返回**纯文本**不是 zip。
3. **`objdump -t` 解析**：行 = `addr bind type section size name`；尺寸在 **p[4]**，
   p[1] 是绑定属性。取错索引会静默提取 0 条。
4. **硬门禁必需**：任何"提取到 0 条"的作业必须 `exit 1`，否则假绿。
