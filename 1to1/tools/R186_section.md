## R186（2026-10-16）

### 一、日期

2026-10-16（本机 Windows，纯静态取证：`golden/sdcard_min/driver.so` + `tools/dis_got.py` + 手写 ELF 解析，零 CI 额度、零带宽）

### 二、完成事项

1. **P2/B6 主线推进——静态取证**推翻「B6 观测天花板」的**关键前提**（不是推翻天花板结论本身，是推翻它的论据）：

   **★ 铁证 1（决定性）：`driver.so` 的 `mmap` 是 UNDEF 外部符号，不是「自封定义 SVC」。**
   - `DT_JMPREL` 71 条重定位里，条目 `[40]`：`r_offset(GOT)=0x170ac`, `symbol='mmap'`, `bind=GLOBAL`, `type=FUNC`, **`shndx=UNDEF`**；
   - `.dynsym[76]`：`'mmap'  val=0x0  shndx=UNDEF`（用 `DT_SYMTAB=0x464`/`DT_STRTAB=0xc74` 权威路径解析，绕开被 strip 破坏的节表 `sh_link`）；
   - 权威清单 `report/_undef_all.txt:482` 明确含 `mmap`（该清单 = R174 生成的 65 项 UNDEF 全集：17 drm + 20 snd + 28 libc/其他）。
   - `mmap` 走 **标准 PLT 懒绑定跳板**：`tools/dis_got.py --pltrange` 输出 `PLT 0x1a50 → GOT 0x0170ac → mmap`。
   - ⇒ **纪律 154 的「`.symtab` 有 `mmap@@GLIBC_2.4`，不是 UNDEF ⇒ 直接发 SVC 绕过 glibc」是静态事实错误**：`mmap@@GLIBC_2.4` 是**引用** glibc 2.4 mmap 的版本化符号（UNDEF），不是自封定义。

   **★ 铁证 2：`driver.so` 画面路径在静态层完整闭合（此前只拆到半程）**：
   ```c
   /* rkgame 侧 */  dispFlip(data, w, h, pitch) → video_driver_disp_frame()
                    frame->[16] = data;                     // GAP 16.28 已证
   /* driver 侧 */  gr_blit_b(frame) blit  frame->[16](源) → cur->[16](目标)  → gr_flip() 呈现
   /* cur 来源 */   cur = *0x171cc（"当前帧"描述符），cur->[16] = 像素指针
   ```
   - `gr_blit_b`（@0x34fc）反汇编：`@0x35e8 ldr r2,[r3,#16]`（source->[16] = rkgame 的 data）、
     `@0x362c ldr r0,[r3]`（r3 = *0x171cc = cur）、blit 核心 `@0x335c` 里 `@0x33a4 ldr r2,[r3,#16]`（**dest = cur->[16]**）、
     循环末尾 `@0x3850 strh r2,[r3]`（写 16bpp 像素）。
   - `CREATE_DUMB` 包装（@0x43a4）：`drmIoctl(CREATE_DUMB)` → `drmIoctl(MAP_DUMB)` → **`@0x4624 bl 0x1a50`（mmap@PLT）** →
     `@0x4630 str r2,[r3,#16]`（**把 mmap 返回值写入 dumb buffer 描述符 [16]**，即 cur->[16] = dumb buffer 实体地址）。
   - ⇒ 组合铁证 1+2：`cur->[16]` = driver 经 **glibc mmap**（非 SVC）建立的 dumb buffer 实体地址；
     该 mmap（fd=DRM fd ≥0, MAP_SHARED, offset=桩回填的 g_fb_buf 地址）**必然命中 shim 拦截的分支 1**
     （`fake_mem.c @1785` 的 `fd>=0 && MAP_SHARED && PROT_WRITE` → `shim_drm_fb_lookup`）。

2. **定位「画布登记零行」观测的误读（纪律 154 那条运行时证据的重新解释）**：
   - `fake_mem.c` 的 `mmap` 拦截有**三个分支**：
     * 分支 1（fd≥0, MAP_SHARED, WRITE）→ `shim_drm_fb_lookup` 命中即返回桩实体（**不打画布登记日志**）；
     * 分支 2（fd≥0, MAP_SHARED, off≥4MB）→ 物理寄存器映射 + `shim_canvas_note`；
     * 分支 3（fd<0, MAP_ANONYMOUS, WRITE）→ 匿名页 + `shim_canvas_note`。
   - driver 的 dumb buffer mmap 走**分支 1**，**从不触发分支 2/3 的 `shim_canvas_note`**。
   - ⇒ 纪律 154 的「实测 shim 画布登记日志零行 ⇒ 拦不到」是**观测点错位**：零行只说明「driver 没走分支 2/3」，
     **不说明「分支 1 没拦到 dumb buffer mmap」**。「拦不到」这个结论被误读放大成了「不可观测」。

### 三、新发现与决策

1. **★ B6 的定性从「观测天花板（不可突破）」降级为「可观测、疑似读错/引用错实体（可修复）」**：
   - R171b/R176 把 B6 全零归因到「driver 私有画布（自封 SVC 绕过 glibc，shim 拦不到）」，其**关键前提（自封 mmap）本轮被证伪**。
   - 真实情况：driver 的 dumb buffer mmap 走标准 glibc mmap，blit 目标 `cur->[16]` 就是 dumb buffer 实体；
     而 shim 分支 1 + 桩的 `drm_stub_fb_address()` 理论上能把「桩实体」与会「driver 的 dumb buffer 实体」接上。
   - ⇒ B6 全零**另有根因**，两个候选（都需云开发运行时验证，静态到此为止）：
     * **候选 A（实体错位）**：GAP 16.30 实测 driver 建 **4 个 dumb buffer**（RG16×3 + AR24×1），
       `cur` 在 `tbl[0..2]`（RG16）之间轮转；而桩 `dumb_fill` 的 `g_fb_buf` 只保留**最后一次** CREATE_DUMB 的实体
       （第 4 次 = AR24）。blit 落 RG16 实体（前 3 次），`fb_commit_hash` 读 `g_fb2_buf`（第 4 次）⇒ **读错块**。
     * **候选 B（handle 撞号）**：桩 `dumb_fill` 把每个 dumb buffer 的 `handle` 都回填成 `FAKE_FB_ID=1`
       （@drm_stub.c:679），4 个 dumb buffer 同 handle；AddFB2 根修里 `bo_handles[0]==FAKE_FB_ID` 恒真 ⇒
       `g_fb2_buf = g_fb_buf`（最后一次实体），无法区分「blit 实际落点」是哪个 dumb buffer。
   - **决策**：不靠静态硬猜，下一步用云开发跑一次带三桩的行为门禁，抓「桩每次 CREATE_DUMB 的实体地址序列 +
     首帧诊断行 `fb2_buf=/fb_buf=` + shim 分支 1 命中日志」，用运行时证据在候选 A/B 之间裁决。
2. **★ 纪律 154 「mmap 自封定义」是静态可证伪的错误**（非运行时口径差异）：已用 DT_JMPREL + DT_SYMTAB
   双路径确认 shndx=UNDEF。这类「符号定义属性」的结论**只能信 ELF 动态段/重定位表**，不能信 `.symtab` 的
   版本化名字面（`mmap@@GLIBC_2.4` 是引用形态，不是定义形态）。
3. **✗ 诚实撤回早期一处重复判断**：我在本轮中途先按「.text section header」扫 `svc` 得到 0 条、短暂支持
   「driver 不发 SVC」；随即发现该 DSO 的 `.text` section offset 是坏的（0x1bc4），改按 **PT_LOAD RX 段**
   （program header 权威）扫得 91 条 svc。这 91 条 svc 属 driver 自有代码区（0xc20–0xef0），与「mmap 走 PLT」
   不矛盾（svc 可能用于其它直发 syscall），但**不能**再据 svc 存在与否论断 mmap 的下发方式——唯一权威是
   `mmap` 属于 UNDEF 且走 PLT。
4. **本轮方法论**：对「某符号是否被 LD_PRELOAD 拦得到」这类问题，**先看 ELF 的动态符号绑定
   （UNDEF+DAT_JMPREL ⇒ 走 PLT ⇒ 可被 interpose），再看反汇编调用点**，二者一致才定案。
   纪律 154 正是跳过第一步、直接信了 `.symtab` 的版本化名字面才得出「自封 SVC」的错误前提。

### 四、下一步待办

1. **P0（云开发运行时裁决候选 A/B）**：CNB 云开发跑一次带三桩（`CGM_DRM_STUB=1` + `CGM_KEY2_HOOK=1`）的
   `tools/ci_qemu_behav.sh`，采集：
   - 桩每次 `CREATE_DUMB` 的实体地址序列（现 `dumb_fill` 只打一次 `mmap2_FAIL`，需临时加一行「第 N 次 CREATE_DUMB → addr」诊断）；
   - 首帧诊断行 `fb2_buf= fb_buf=` 与 4 次 dumb buffer 实体地址对比；
   - shim 分支 1 命中日志（需临时给 `shim_drm_fb_lookup` 命中加一行 note）。
   - 裁决：若 blit 落点（tbl[0..2]=RG16 实体）≠ g_fb_buf（第 4 次=AR24）⇒ 候选 A 成立，根修 = 桩按 handle 维护
     「handle→实体」映射表、AddFB2 按 bo_handles[0] 精确引用对应实体，而非只留最后一次。
2. **P0（根修，视裁决结果）**：把桩从「单实体」升级为「handle→实体表」，`MAP_DUMB` 按 handle 回填对应 offset、
   `AddFB2` 按 `bo_handles[0]` 引用对应实体、`fb_commit_hash` 哈希「当前 cur 轮转到的实体」。
3. **P2（降级为可选）**：R36S Wiki 第二参照物（`report/r36s_second_reference.md` 已基本完成，待补充）。
4. **双远端推送**：R186 段（无源码改动，仅 PROGRESS 记录 + 静态取证结论），推 GitHub + CNB。