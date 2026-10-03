# Phase 1 专项取证报告：FilePreEmu / SeletEmuCore

## 0. 取证概况

**目标函数**：`FilePreEmu` (0x00016f08, 676B) / `SeletEmuCore` (0x00021c08, 1712B)  
**数据来源**：工厂二进制 `factory.rkgame.bin` 的 Ghidra 逐函数反导（812 个 `.c` 语料）  
**重现结果**：本地 QEMU 验证 `DIVERGE 18` 中，**簇 A** 为最高优先级真实缺陷嫌疑。

---

## 1. 工厂代码功能重构（从 Ghidra 语料）

### 1.1 FilePreEmu (工厂 Ghidra 输出)

```
int FilePreEmu(char *param_1) {
    char *ext = GetFilenameExt();
    strcpy(&FilenameExt, ext);
    strupr(&FilenameExt);
    GetCoreIndex(&FilenameExt);
    RARCH_LOG("Filetype %d\n", Filetype);

    if (Filetype < 0x10000) {
        // 普通文件路径
        fp = fopen(param_1, "rb");
        fseek(fp, 0, 2); ZIP_BUF_SIZE = ftell(fp);
        fseek(fp, 0, 0);
        ZIP_BUF = malloc(对齐后尺寸);
        fread(ZIP_BUF, 1, ZIP_BUF_SIZE, fp);
        fclose(fp);
        return 1;
    } else {
        // ZIP 包路径
        if (strstr(param_1, "000/") != NULL) {
            // 特殊路径，直接返回 1
            Filetype |= 1;
            return 1;
        }
        else {
            // 解析 zip 包
            zip = OpenZipU(param_1, 0, 2);
            if (zip == 0) return 0;
            // 检查 zip 内容，提取核心信息
            GetZipItemA(zip, ..., &buf);
            RARCH_LOG("zipcount %d\n", buf.count);
            if (buf.count < 2) {
                // 特殊处理单文件 zip
                UnzipItem(...);
            }
            CloseZipU(zip);
            return 1;
        }
    }
}
```

**关键点**：工厂代码在** ZIP 包解析**路径中使用了 `OpenZipU`、`GetZipItemA`、`UnzipItem` 等 API，且对单文件情况有**额外处理**。

### 1.2 SeletEmuCore (工厂 Ghidra 输出)

```
int SeletEmuCore(gh_byte *param_1) {
    int result = FilePreEmu();
    if (result == 0) {
        // 文件 Missing 错误处理
        mui_outputxy_t(..., "The specified file is missing");
        mui_ReadJoystick();
        return 0;
    }

    // 主流程：读取 cores/config.xml
    char path[260]; stpcpy(path, work_path);
    builtin_strncpy(path + ..., "cores/config.xml", 17);
    fp = fopen(path, "r");
    tree = mxmlLoadFile(0, fp, 0); fclose(fp);

    // 遍历 XML，解析支持的后缀和对应的核心
    while (mxmlFindElement(...)) {
        // 关键比较
        while (mxmlFindElement(..., "supported_extensions", ...)) {
            // ★ 工厂有 strcmp
            iVar1 = strcmp(*(char **)(*(int *)(iVar4 + 0x10) + 0x1c), (char *)&FilenameExt);
            if (iVar1 == 0) {
                // 找到匹配，读取 emucore 属性
                pcVar2 = mxmlElementGetAttr(..., DAT_002dcd70);
                strcpy(core_info_list + ..., pcVar2);
                pcVar2 = mxmlElementGetAttr(..., DAT_002dbd74);
                strcpy(core_info_list + ..., pcVar2);
                break;
            }
        }
    }

    EmuCore_list(..., count);
    // 显示选择界面，处理按键...
    // 最终返回核心索引
}
```

**关键点**：
- 工厂代码使用 `strcmp` 比较 **XML 中声明的后缀**与**当前文件后缀**。
- 在**遍历子过程**（`mxmlFindElement` 循环）中，`strcmp` 会被调用多次（报告说 8 次）。
- 工厂还有 6 次表读（stride 0x44）→ 可能是在遍历某个数据结构。

---

## 2. 我方重建代码现状

### 2.1 FilePreEmu 重建

```c
// src/proprietary/core/FUN_00016f08_FilePreEmu.c
int FilePreEmu(char *param_1) {
    char *ext = GetFilenameExt();  // 正确
    strcpy(&FilenameExt, ext);     // 正确
    strupr(&FilenameExt);          // 正确
    GetCoreIndex(&FilenameExt);    // 正确
    RARCH_LOG("Filetype %d\n", Filetype);

    if (Filetype < 0x10000) {
        fp = fopen(param_1, "rb"); // 正确
        if (fp != NULL) {
            fseek(fp, 0, 2);
            ZIP_BUF_SIZE = ftell(fp);
            fseek(fp, 0, 0);
            ZIP_BUF = malloc(对齐后尺寸);
            if (ZIP_BUF != NULL) {
                fread(ZIP_BUF, 1, ZIP_BUF_SIZE, fp);
            }
            fclose(fp);
            return 1;
        }
        RARCH_LOG("%s open fail\r\n", param_1);
        return 0;
    }
    else {
        pcVar1 = strstr(param_1, "000/");
        if (pcVar1 == NULL) {
            memset(&local_158, 0, 0x130);
            iVar3 = OpenZipU(param_1, 0, 2);
            if (iVar3 != 0) {
                GetZipItemA(iVar3, 0xffffffff, &local_158);
                RARCH_LOG("zipcount %d\n", local_158);
                if (local_158 < 2) {
                    iVar4 = GetZipItemA(iVar3, 0, &local_158);
                    if (iVar4 == 0) {
                        // 单文件 zip 处理
                        strupr(auStack_154);
                        pcVar1 = GetFilenameExt(auStack_154);
                        strcpy(&FilenameExt, pcVar1);
                        strupr(&FilenameExt);
                        GetCoreIndex(&FilenameExt);
                        RARCH_LOG("FilenameExt %s\n", &FilenameExt);
                        RARCH_LOG("Filetype %d\n", Filetype);
                        ZIP_BUF_SIZE = local_30;
                        ZIP_BUF = malloc(local_30 + 0x10);
                        if (ZIP_BUF != NULL) {
                            iVar4 = UnzipItem(iVar3, 0, ZIP_BUF, 0, 3);
                            if (iVar4 != 0) {
                                free(ZIP_BUF);
                                ZIP_BUF = NULL;
                                ZIP_BUF_SIZE = 0;
                            }
                        }
                    }
                }
                else {
                    Filetype = Filetype | 1;
                }
                CloseZipU(iVar3);
                return 1;
            }
            RARCH_LOG("open %s fail!\n", param_1);
            return 0;
        }
        else {
            return 1;
        }
    }
    return 0;
}
```

**观察**：
- 逻辑与工厂一致，包括单文件 zip 的特殊处理。
- 但 `UnzipItem` 的调用参数是 `(0, 0, 3)`，这个 `3` 可能不是工厂的等价值。

### 2.2 SeletEmuCore 重建

```c
// src/proprietary/mui/FUN_00021c08_SeletEmuCore.c
int SeletEmuCore(gh_byte *param_1) {
    int result = FilePreEmu();
    if (result == 0) {
        mui_outputxy_t(..., "The specified file is missing");
        // 等待按键...
        return 0;
    }

    // 主流程
    stpcpy(acStack_128, work_path);
    builtin_strncpy(pcVar2, "cores/config.xml", 0x11);
    __stream = fopen(acStack_128, "r");
    if (__stream != NULL) {
        tree = mxmlLoadFile(0, __stream, 0);
        fclose(__stream);
        if (tree != NULL) {
            // 遍历 XML
            while (mxmlFindElement(iVar3, tree, DAT_002dd508, 0, 0, 1)) {
                iVar4 = mxmlFindElement(iVar3, tree, "supported_extensions", 0, 0, 1);
                do {
                    // ★ 有 strcmp
                    iVar1 = strcmp(*(char **)(*(int *)(iVar4 + 0x10) + 0x1c), (char *)&FilenameExt);
                    if (iVar1 == 0) {
                        // 读取核属性
                        pcVar2 = mxmlElementGetAttr(iVar4, DAT_002dcd70);
                        strcpy(core_info_list + iVar1, pcVar2);
                        pcVar2 = mxmlElementGetAttr(iVar4, DAT_002dbd74);
                        strcpy(core_info_list + iVar1 + 0x100, pcVar2);
                        break;
                    }
                    iVar4 = mxmlFindElement(iVar4, tree, "supported_extensions", 0, 0, 0);
                } while (iVar4 != NULL);
            }
            mxmlDelete(tree);
        }
    }

    EmuCore_list(0, 0, count);
    // 主界面循环...
}
```

**观察**：
- 逻辑与工厂基本一致。
- 但 **`mxmlLoadFile` 第三个参数是 `0`**，而工厂语料中似乎是 `0` 或者是其他值？需要确认。

---

## 3. 差距分析：为什么提前崩溃？

### 3.1 崩溃现场（QEMU 轨迹）

根据审计报告：
- 工厂侧：`FilePreEmu` / `SeletEmuCore` 调用链完整，**进入 strcmp 比较**。
- 我方侧：**提前死 in null 解引用** → 可能是 `mxmlFindElement` 返回 NULL 后立即使用。

### 3.2 关键差异点

1. **mxmlLoadFile 调用参数**
   - 工厂 Ghidra 语料中：`tree = mxmlLoadFile(0, __stream, 0);`
   - 但是否有**第三个参数**的差异？工厂可能是 `(0, fp, MXML_NO_CALLBACK)` 或其他。

2. **mxmlFindElement 循环条件**
   - 工厂：`while (mxmlFindElement(...)) { ... }`
   - 我方：同上。
   - **差异**：工厂在遍历 `supported_extensions` 时有 **8 次 strcmp 调用**，而我方在 QEMU 轨迹中**调用次数不同**。

3. **字符串常量地址**
   - 工厂：`strcmp(*(char **)(*(int *)(iVar4 + 0x10) + 0x1c), (char *)&FilenameExt);`
   - 我方：相同。
   - **差异**：`\0` 指针可能被工厂维护得很好，而我方可能某个 `char **` 未经初始化。

### 3.3 真正根因假设

**原因 1：XML 遍历循环提前退出或未进入**
- 如果 `tree` 为 NULL 或 `mxmlFindElement` 第一次就失败 → 直接回到 `mxmlDelete`，跳过 `strcmp` 比较。
- 而 QEMU 中如果此时路径不同，可能触发其他异常。

**原因 2：FilenameExt 初始化不一致**
- 工厂：`FilePreEmu` 先执行，设置好 `FilenameExt`（大写）。
- 我方：也是先调用 `FilePreEmu` → 应该一致。
- **但**：`FilePreEmu` 内部对 Zip 包的处理可能直接影响到 `FilenameExt`。
   - 在 Zip 包单文件情况下，工厂调用 `GetFilenameExt(auStack_154)` 后 **strupr**
   - 我方同样做了，但 `auStack_154` 的初始化可能有误（`memset` 0x130 大小？）。

**原因 3：mxml 节点遍历逻辑差异**
- 工厂语料显示 **8 次 strcmp** → 表示在 `supported_extensions` 列表中有 8 个条目被比较。
- 我方轨迹中可能只比较了 0 次或 1 次 → 表示 XML 结构未正确遍历。
   - 可能原因：`mxmlFindElement` 的根节点不同（`DAT_002dd508` 是什么？）。
   - 可能原因：XML 解析顺序/命名空间处理不同。

---

## 4. 重建方案

### 4.1 立即验证：运行 QEMU 并对比轨迹

**测试脚本**：`tools/test_proto_a.sh`

```bash
#!/bin/bash
# 1. 编译当前版本
./tools/cnb_ladder.sh REBUILD=5 SCEN=45

# 2. 在 QEMU 中分别运行工厂和我方，捕获轨迹
QEMUARCH=arm QEMU_SYSROOT=... qemu-system-arm -kernel build/rkgame.rebuilt.elf -d exec 2> factory.trace &
pid1=$!
# 工厂...
wait $pid1

QEMUARCH=arm QEMU_SYSROOT=... qemu-system-arm -kernel build/rkgame.rebuilt.elf -d exec 2> rebuild.trace &
pid2=$!
# 重建...
wait $pid2

# 3. 对比 trace 中的关键调用
grep -E "strcmp|FilePreEmu|SeletEmuCore" factory.trace | wc -l
grep -E "strcmp|FilePreEmu|SeletEmuCore" rebuild.trace | wc -l

# 4. 对比 mxmlLoadFile 参数
grep "mxmlLoadFile" factory.trace
grep "mxmlLoadFile" rebuild.trace
```

### 4.2 如果差异确认为「mxml 遍历未进入」

**重建步骤**：

1. **检查 `mxmlLoadFile` 调用**
   - 工厂语料中：`tree = mxmlLoadFile(0, __stream, 0);`
   - 我方需要确认 `mxml` 库版本是否一致？
   - 可能工厂用的是 `mxmlLoadFile(file, stream, mxmlXML}` 等）。

2. **检查 `DAT_002dd508`**
   - 这个字符串常量可能是 XML 根标签名称。
   - 通过 `tools/factory_globals.py` 查看 `DAT_*` 地址映射。

3. **修复单文件 Zip 处理**
   - 确保 `auStack_154` 的 `memset`  correctly。
   - 确保 `GetFilenameExt` 返回的指针正确处理。

### 4.3 如果差异确认为「字符串比较提前崩溃」

**关键**：工厂有 **8 次 strcmp**，而我方可能是 0 次。
- **检查 `FilenameExt` 在比较时的值**：
   - 工厂：`strcmp(..., (char *)&FilenameExt)`
   - 我方：相同。
   - **差异**：工厂的 `FilenameExt` 地址可能正确初始化，而我方在某些路径下 `FilenameExt` 可能未定义或为 NULL。

**修复**：
- 在 `FilePreEmu` 开头确保 `FilenameExt` 已初始化：
   ```c
   char FilenameExt[32] = {0}; // 确保静态或全局变量有初始值
   ```

### 4.4 如果差异确认为「mxml 解析器行为不同」

**验证**：
- 上游 `mxml` 版本：`src/upstream/mxml` 是否为 2.9？
- 工厂是否使用了**定制版** mxml（例如增加了空指针检查）？

**修复**：
- 检查 mxml 代码中的空指针保护。
- 对比 `mxmlLoadFile` 和 `mxmlFindElement` 的实现差异。

---

## 5. 执行计划

| 步骤 | 时间 | 产出 |
|------|------|------|
| **1. 轨迹对比脚本** | 立即 | `tools/test_proto_a.sh` |
| **2. 运行 QEMU 取证** | 1 小时 | `factory.trace`, `rebuild.trace` |
| **3. 差异分析** | 1 小时 | 确认具体根因 |
| **4. 代码修复** | 2 小时 | 修复后的 `FilePreEmu.c` / `SeletEmuCore.c` |
| **5. 本地验证** | 1 小时 | QEMU 轨迹对比 ⇒ 发散减少 |
| **6. 云部署** | 1 小时 | 推送 CI 触发 `diff_exec` 验证 |
| **7. 报告更新** | 1 小时 | `PHASE1-FILEPREEMU-SELETEMUCORE.md` 更新 |

**总计**：约 7 小时（本地）+ 云 CI 时间。

---

## 6. 后续收尾

- 如果簇 A 修复成功，`DIVERGE` 应减少 **8-12**（假设 8 次 strcmp 是主要来源）。
- 剩余发散追溯到其他簇（B/C/D）。
- 推进刻度 A 符号依赖清理（L1/L2/L3）。

---

**下一步行动**：立即运行 `tools/test_proto_a.sh`。
