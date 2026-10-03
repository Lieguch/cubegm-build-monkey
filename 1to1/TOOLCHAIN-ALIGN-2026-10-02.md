# 工具链对齐判决实验（第 118 轮 · 2026-10-02）—— 【判据先写死】

> 纪律：「先写死判据再动手」（PROJECT-MEMORY §2.18 / 纪律 61）。本文件在**跑之前**落盘，
> 事后**只许回填实测数字，不许改判据**。

---

## 一、根因（铁证，非推断）

工厂 `rkgame` 的编译口径真值（`report/dwarf_recon.txt:19`，从 DWARF `DW_AT_producer` 恢复）：

```
GCC 6.2.0 -mabi=aapcs-linux -march=armv7-a -mfloat-abi=hard -mfpu=neon \
          -mtune=cortex-a8 -mtls-dialect=gnu -O2 -std=gnu11 -fgnu89-inline \
          -fmerge-all-constants -fno-stack-protector -frounding-math \
          -fomit-frame-pointer -ftls-model=initial-exec
+ glibc 2.24 / binutils 2.27 / GNU gold 1.12
+ .comment = "GCC: (GNU) 6.2.0" + "GCC: (Linaro GCC 4.9-2016.02) 4.9.4"（crt）
```

我方 `tools/link_audit.sh` 当前实际：

| 维度 | 工厂 | 我方 | 差异 |
|---|---|---|---|
| 编译器 | **GCC 6.2.0** | **`zig cc` = clang 21** | ★★★ |
| glibc 头 | 2.24 | **2.7** | ★★★ |
| 优化档 | **`-O2`** | **`-Os`**（当年按**体积比代理指标**选定） | ★★ |
| 影响机器码的开关 | `-fgnu89-inline -fmerge-all-constants -frounding-math -ftls-model=initial-exec -mtls-dialect=gnu -std=gnu11 -mtune=cortex-a8` | **全缺**（只有 `-fno-stack-protector -U_FORTIFY_SOURCE`） | ★★ |

⇒ **所有残余发散（INLINE-MOVE 访存几何 / 体量比 / libiconv 96 个边角 charset / `.dynsym` 习语）
的共同根因 = 编译口径不同**。逐函数追 = 打地鼠；**根治 = 换回工厂同款编译口径**。

## 二、实验设计（单变量，整条编译链一起换）

腿（`AB_LEGS`）：

| 腿 | CC | glibc 头 | OPT | 说明 |
|---|---|---|---|---|
| `zig-Os` | zig cc (clang 21) | 2.7 | `-Os` | **现状基线** |
| `zig-O2` | zig cc | 2.7 | `-O2` | 只变优化档 |
| `gcc63-Os` | **Bootlin GCC 6.3.0** | **2.24** | `-Os` | 只变编译器族 |
| `gcc63-O2` | **Bootlin GCC 6.3.0** | **2.24** | `-O2` | ★ **最接近工厂** |

每条腿：`rm -rf build/obj build/upstream` → `link_audit.sh`（213 对象）→ `build_upstream.sh`
→ `link_full.sh` → **行为尺** `diff_exec.py --batch --steps 3000` 量 `DIVERGE` 数。
唯一变量 = CC / glibc 头 / OPT。

## 三、判据（预登记，跑之前写死）

- **M1（主判据）**：`gcc63-O2` 的 `DIVERGE` **严格小于** `zig-Os`（现状），且 `PASS` 严格大于。
  判读：GCC 6.x + glibc 2.24 + `-O2` 是有效的**整类**根治。
- **M2（单调性）**：`DIVERGE` 应满足 `zig-Os ≥ zig-O2 ≥ gcc63-Os ≥ gcc63-O2`（允许并列）。
  判读：若打破单调 ⇒ 变量互相纠缠，需拆开重做。
- **M3（归因分离）**：`zig-Os → zig-O2` 单独就能降 `DIVERGE` ⇒ 优化档是主因；
  `zig-Os → gcc63-Os` 单独就能降 ⇒ 编译器族是主因。两者都要记录，**不许只报一个**。
- **M4（体积比，次要）**：`gcc63-O2` 的 `prop_equiv` 分布 `p95` 应低于 `zig-Os` 基线（`p95 1.33`）。
- **M5（`.dynsym`，次要假设）**：glibc 2.24 头下 `__strdup` / `islower` 是否出现。
  **未出现也不推翻 M1** —— 只登记为「可豁免 glibc/编译器习语」。
- **反证条件（fail-closed）**：若 `gcc63-O2` 的 `DIVERGE` **≥** `zig-Os`
  ⇒ **编译器不是根因**，本判据作废，必须重新定位（不得改判据迁就结果）。

## 四、验收方法（全部机械、可复算）

1. 每腿的 ELF `sha256` + `size` + `abi_check rc` 落 `report/_ab_results.txt`；
2. 行为尺汇总行（`PASS｜DIVERGE｜TRUNC｜REFDEAD｜SKIP`）落 `report/toolchain_ab.txt`；
3. 若 `gcc63-O2` 胜出 ⇒ **把主构建 `CC`/`OPT` 切过去**，并重跑 `prop_equiv` + `.dynsym` 对拍，
   用同一判据复核是否同步收窄。

## 五、回退

`toolchain_ab.sh` 只写 `build/ab/*.elf` 与 `report/_ab_*`，**不动** `build/rkgame.rebuilt.elf`、
**不改** `link_audit.sh` 默认值。故实验本身零风险；
只有判据通过后才改默认值（届时 `git checkout -- tools/link_audit.sh` 可回退）。

## 六、为什么这不是「仪器工作」而是「产物根治」

它改变的是**产物本身的生成口径**（编译器 + 头 + flags），直接决定 `build/rkgame.rebuilt.elf`
的机器码，不是观测装置。且它同时消掉 §0.19-F.3（`.dynsym`）与 §0.29-F 残余分歧**两类**的**共因**。

---

## 七、实测结果（**回填，判据一字未改**）—— 2026-10-02，`REBUILD=5` 云上跑通

取回真实性校验：`ladder.log` 第 3 行含本轮 `RUN-NONCE=1790927846-920`（新增的防陈旧握手），
`ssh 管道 rc=0`，`toolchain_ab rc=0`，**度量成功腿数 = 3 / 3**。⇒ 数字是本轮的，不是残留。

| 腿 | size | abi_rc | PASS | **DIVERGE** | TRUNC | REFDEAD | 构建 |
|---|---|---|---|---|---|---|---|
| `zig-Os`（＝主链口径） | 5,487,288 | 0 | **765** | **18** | 5 | 0 | OK |
| `zig-O2` | 5,503,760 | 0 | 761 | **22** | 5 | 0 | OK |
| `gcc63-O2` | 5,385,444 | 0 | 727 | **26** | 6 | **34** | ★ **rc=17 体量覆盖门禁 FAIL** |

sha256：`zig-Os 6d8a0f85…` / `zig-O2 e0349337…` / `gcc63-O2 c0140936…`

### 判据核销（逐条，不许事后解释）

| 判据 | 预登记 | 实测 | 结论 |
|---|---|---|---|
| **M1** | `gcc63-O2` 的 DIVERGE **严格小于** `zig-Os` | 26 **>** 18 | ❌ **不成立** |
| **M2** 单调性 | `zig-Os ≥ zig-O2 ≥ gcc63-Os ≥ gcc63-O2` | 18 **<** 22（第一步就断） | ❌ **不成立** |
| **M3** 归因 | 记录 `zig-O2` / `gcc63` 各自的单独贡献 | `-O2` 使 DIVERGE **变差**（18→22）；换 GCC 族再变差（22→26） | 两项**都是负贡献** |
| **M4** 体积比 | `gcc63-O2` p95 应低于 `zig-Os` | 未测（gcc63 腿构建即被门禁拦下） | 不可判 |
| **M5** `.dynsym` | 未出现也不推翻 M1 | gcc63 腿的 abi 台账里 `islower` 仍为「已登记」 | 未收窄 |
| **反证条件** | `gcc63-O2` DIVERGE ≥ `zig-Os` ⇒ **编译器不是根因**，判据作废、重新定位 | **命中** | ★ **判据作废（照此执行）** |

### 结论（照判据执行，不迁就结果）

1. **「编译口径不对」不是残余发散的根因。** 换成最接近工厂的 `gcc63-O2`，
   DIVERGE **不降反升**（18→26），且多出 **REFDEAD 34**（参照侧早死 ⇒ 那 34 组不可判）。
   ⇒ 退出该路径。
2. **现状口径（`zig cc` + `-Os`）是三腿中最好的**，不切工具链、不改 `-O2`。
   ⇒ 同时也**推翻**「`-Os` 是当年按体积比选错、应改 `-O2`」这一推断（§16.105.b 的措辞需更正）。
3. `gcc63-O2` 腿**同时**触发 `size_coverage_gate` FAIL（`GetWorkPath 0.429` 12 vs 28、
   `stbtt__cff_get_index 0.476` 160 vs 336）⇒ **GCC 会删掉 clang 留着的代码**（UB 类）。
   ★ 这是一条**新的、可用的方法**：把 GCC 当 **UB 探测器**（不是当产物的编译器）。
4. **与既有结论一致**：§0.40-B（CI `toolchain-ab#13` 四腿表）已测过同样四腿，得
   `zig-Os 36 < gcc63 37/48`，并已写明「gcc63-* 的 REFDEAD=34 是观测性缺口，不能读成生成质量」。
   本轮在**当前源码**上独立复现了同一方向（18 < 26），把该假设**正式证伪**。
