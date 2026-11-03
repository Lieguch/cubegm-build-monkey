## R305（2026-11-02）—— 真机 SIGSEGV 根因**反转**：诊断仪洗清 ⇒ 元凶 = 重建二进制 ZIPENTRY 尺寸缺陷（3 处 Rule A 已修）

### 1. 根因反转（三条旧假设全部被真机证据证伪）

| 旧假设 | 证伪依据 | 分层 |
|---|---|---|
| R303「诊断仪快照风暴自伤」 | 实验 A（清洁版 + 关 `_diag/`）与实验 B（R303 诊断版）**观感完全一致**（均 0.2-0.4s 闪重启、伴随音乐）⇒ 诊断仪非因 | 已实测（用户目视 + 两组日志目录） |
| 「写爆 SD（ENOSPC）」 | SD 卡剩余 **2.36 GiB**（用户报约 2.3G）⇒ 证伪 | 已实测 |
| 「真机启动链 / 内核侧问题」 | QEMU 侧**原厂二进制**全链路健康（`rkgame v1.42` → `open driver.so sucess` → `open drm!` → DRM 桩 → abiprobe 两侧 3072 帧；B1~B8b 全 PASS）⇒ 责任在**重建二进制** | 已实测（QEMU 侧原厂链逐环节原证） |

⇒ 结论：**真凶是重建二进制自身的 ZIPENTRY 尺寸/取址缺陷**，不是设备、不是内核、不是诊断仪。

### 2. 真机硬证据（`_sdcard_drop/真机验收日志/14/crash.txt`，用户提供）

- `signal=11 (SIGSEGV)  si_code=1(MAPERR)  si_addr=0x10001000  ms=5868  depth=28`
- `si_addr=0x10001000` **不在 `/proc/self/maps` 任何区**（maps 仅 `00009000-003ad000` r-xp / `005c1000-0061a000` r-xp / `00626000-0066c000` rwxp [heap]）⇒ **野指针**
- 调用链：`UnzipItem → TUnzip::Unzip → unzReadCurrentFile → inflate → inflate_blocks → inflate_codes`
  （pc=`0x60d7d4` 落在 `inflate_codes` sym@`0x60d404`+2384 内 ⇒ 崩在 zlib 解压内部）
- 寄存器：`r3=0x10001000`（= si_addr，坏指针）、`r2=0xb2f116d8`（合法映射）⇒ inflate 读到坏指针后解引用
- `000.dat` 时间线：5438ms `fopen /mnt/sdcard/000/000.dat`（240,935,839 B / 230 MB；中央目录 @240,695,719、**1710 条目**）
  → 5486ms ZIPOPEN → idx=1709 命中 `kof97_000.raw`（cmp=0，条目解析正确）→ **3ms 后 inflate 内 SIGSEGV**
  ⇒ 中央目录解析**正确**，崩在**提取（解压）阶段**；早轮 2/3 同族 SIGSEGV（ms≈4315，si_addr `0x0`/`0x4`）= 同一族崩溃的不同面貌。

### 3. 元凶（源码级 + 工厂 1:1 取证）

**元凶函数**：`src/proprietary/mui/FUN_00014f84_mui_DisplayThumbnail.c`

- 我方 ELF **机器码实锤**：`size_t local_30;` **声明后从未赋值** ⇒ `-Os` 下 r0 残留 ⇒ `malloc(local_30)` 实为 **`malloc(0)`**
  （机器码 `0x4e558c bl 0x4015d0`，其前 r0 的最后写入 = `FindZipItemA` 返回值 0）。
- 机制：`UnzipItem(...,__ptr,0,3)` 走 ZIP_MEMORY 路径，工厂 `TUnzip::Unzip` 以 **16KB 为块循环填满 dst**
  （`unzReadCurrentFile(uf,out,16384); out += 16384;`）⇒ dst 尺寸不足 ⇒ **连续越界写** ⇒ 堆破坏 ⇒ inflate 内部野指针 ⇒ SIGSEGV ⇒ 设备重启（0.2-0.4s 闪重启即此因）。
- **工厂真相**（权威源 `tool/factory_t1.txt` 835 函数带符号反汇编 + `src/data/factory_text.bin` 字节指纹校准）：
  - 本函数工厂真实基址 = `0x14f84 - 0xb474 = 0x9B10`
    （校准：`sub sp,sp,#884`（`e24ddfdd`）在 factory_text.bin 全 blob **唯一命中** @`0xb478`，且 +32 处 `mov r2,#128` 恰为 idx9 ⇒ 偏移 `0xb474` ↔ Ghidra `0x14f84`；曾误用 base=`0x10000`/`0x9000` 均被指纹校准推翻）
  - 工厂把 ZIPENTRY 放栈上：`add r9,sp,#576`
  - 工厂 malloc 尺寸 = `LDR r0,[sp,#872]`（原始字 @`0x15080 e59d0368`）= **ZIPENTRY + 296 = `unc_size`**
    （`@0x15084 ebffd1ac` = `BL malloc`；`@0x15090 e59d100c` = `LDR r1,[sp,#12]`；`@0x150ac ebfff7e3` = `BL UnzipItem`）
  - ⇒ 工厂语义 = **`malloc(unc_size)`**，与 `Find → Get` 填充的 `ze->unc_size = ufi.uncompressed_size`（`src/upstream/xunzip/unzip.cpp:3959`）精确对应。
- **ZIPENTRY 布局定案**（工厂 `TUnzip::Get.part.5` str 偏移 + memset/memcpy 自洽）：`index@0`、`name@4`、`attr@264`、`comp_size@292`、**`unc_size@296`**、额外字段@300 ⇒ **sizeof = 304**
  ⇒ 原声明 `gh_u1 auStack_158[296]` **少 4 字节**，`unc_size` 落在缓冲外。

### 4. 修复（3 处 Rule A + 1 处 Rule B，全部对齐工厂）

| 文件 | 原形态（缺陷） | 新形态 | 工厂依据（`tool/factory_t1.txt`） |
|---|---|---|---|
| `mui/FUN_00014f84_mui_DisplayThumbnail.c` | `malloc(local_30)`（= `malloc(0)`）；缓冲 296B | `ze_t auStack_158;`（304B/对齐 4）+ `malloc(auStack_158._296_4_)` | `LDR r0,[sp,#872]` = ZIPENTRY+296 |
| `core/FUN_00016f08_FilePreEmu.c` | `malloc(local_30 + 0x10)`（栈垃圾尺寸）；`if (local_158 < 2)`（**指针比较 UB**，恒假 ⇒ 解压分支永不可达） | `ZIP_BUF_SIZE = local_158._296_4_;` + `malloc(ZIP_BUF_SIZE + 0x10)`；`if (2 > (int)local_158._0_4_)` | 指令 144 `ldr r2,[sp,#304]`=ZIPENTRY(sp+8)+296；146 `add r0,r2,#16`；147 `str r2,[r4]`；97-98 `cmp r8,#1; ble +0x1d8`（count≤1 ⇒ 解压分支，0x1d8=指令 118 = 第二次 `GetZipItemA(index=0)`） |
| `core/FUN_002b7510_run_game.c` | `malloc(local_30 + 0x10)`（栈垃圾尺寸） | `ZIP_BUF_SIZE = local_158._296_4_;` + `malloc(ZIP_BUF_SIZE + 0x10)` | 指令 277 `ldr r2,[sp,#320]`=ZIPENTRY(sp+24)+296；279 `add r0,r2,#16`；280 `str r2,[r8]` |

- 三处本地 ZIPENTRY 缓冲统一改用 R284 基建 **`ze_t`（`named_array_blobs.h`）**：`unsigned char raw[304]` + 76 组 4 字节 union ⇒ 含 `_296_4_`（@296）、`_0_4_`（@0），`sizeof=304`、`alignof=4` ⇒ **顺带消除原 `gh_u1[296]` 的非对齐 int 访问隐患**。
- 回退点：每处修改均在源码注释中写明「改什么 / 为什么 / 如何回退」。

### 5. 落码自证（`_r305_selfcheck.py`，本机无 ARM 工具链 ⇒ 真实编译门禁在 CI）

| 自证项 | 结果 |
|---|---|
| A 布局 | `ze_t` raw[304]、76 组 × 4B；`_296_4_`@296 ∈ [0,304) ⇒ **unc_size 读取在缓冲内**；`sizeof%4==0` ⇒ 栈上对齐 4 成立；`ZIPENTRY`（ghidra_compat.h，`_raw[300]`+`_pad[296]`）与 `ze_t` **同偏移 296，两通道互证** |
| B 一致性 | 三文件「残留禁用形态 / 目标形态 / 括号配平」三项 **全 PASS**（去注释后判定） |
| C Rule A 收敛 | 全仓 **251 文件**扫描，高置信候选 **3 → 0**；需人工核候选 0；已排除 `DAT_*` 全局实参 2 处（`DAT_003af828` = 屏幕高，`mui_LoadConfig.c:655` 赋 `0x140` 或配置 sscanf ⇒ **非 Rule A**，登记为观察项） |

### 6. 分层标注（结论 / 假设 / 无证据）

- **已实测**：crash.txt 全部字段与 maps/寄存器；实验 A/B 观感同形；SD 剩余 2.36 GiB；工厂指令逐条（`factory_t1.txt` + 原始 blob 字面）；我方 ELF `malloc(0)` 机器码；ZIPENTRY 304B 布局三方互证；全仓 Rule A 扫描。
- **未实测的推断**：新二进制在真机不再 0.2-0.4s 闪重启 —— **必须由用户换卡复测确认**（本轮不安排真机实验，用户手上有卡）。
- **无证据**：崩溃由「哪一次具体的越界写」触发 —— 堆破坏时序未复现，不下根因结论。

### 7. 下一轮待办

- 新二进制入卡复测（用户侧，R274 纪律：不把用户当调试机 —— 交付新构建 + 明确换卡步骤，不追加诊断探针）。
- 是否把 Rule A（malloc 实参来自未初始化局部）固化为 CI 门禁：模板 = `tools/scan_implicit_decl.py`（编译器真值口径 + 正向/负向自证 + 台账棘轮），挂载点 = `1to1-verify.yml`（`continue-on-error: true` + 末尾按 `outcome` 聚合硬失败）。**本轮不做**（避免与崩溃修复同轮混变量、便于失败归因）。
- 清理本会话临时脚本：`_resolve_crash.py` / `_elf_func.py` / `_dis_range.py` / `_arm32.py` / `_qemu_behav_log*.txt` / `_r305_selfcheck.py` / `_r305_push_diff.py`。
