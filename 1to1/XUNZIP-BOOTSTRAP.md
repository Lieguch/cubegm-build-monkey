# 判据：`build_upstream.sh` 自举 `XUnzip.o`（新克隆不再报废）

**预登记**：动手改之前（2026-10-03，第 121 轮）。
**反证条件**：若自举编出的 `XUnzip.o` 与本机既有那份**符号集不一致**，
或云端构建仍报 `XUnzip 对象不存在` ⇒ flag 或路径不对，**不得**靠上传掩盖。

## 病灶（云端 `cnb-a2n-1k40p84gg` 实测）

```
① link_audit    rc=4  产出对象 0（期望 213）
★★ XUnzip 对象不存在：/workspace/1to1/src/upstream/xunzip/XUnzip.o
★★ 腿 zig-Os 构建失败 rc=12
★★ 判决不成立（0/1条腿量到）⇒ 退出码 3（不可判，不得当作通过）
```

## 根因（结构性）

- `link_full.sh:146`：`DIAG_XUNZIP="${DIAG_XUNZIP:-$ROOT/src/upstream/xunzip/XUnzip.o}"`
- `.gitignore:5`：`src/upstream/xunzip/*.o`（红线 3：**构建产物不入库**）
- ⇒ **任何新克隆 / 新云工作区都必然缺它** ⇒ 整轮构建报废
- ★ 而 `cnb_ladder.sh:99` 早就用 `UP="… src/upstream/xunzip/XUnzip.o"` **显式上传**
  ⇒ **同一个"预编译产物依赖"写了两处，其中一处漏了**（纪律：同一规则禁止写两处）

## 根治

`tools/build_upstream.sh` 新增第 6 段：**自己编出来**（任何环境可自举）。

| 要素 | 做法 |
|---|---|
| 编译器 | `$CC` 形如 `<zig> cc` ⇒ `sed` 换成 `<zig> c++`；`gcc` ⇒ `g++` |
| flag | `-O2 -w -fno-exceptions -fno-rtti` + `CGM_FID_EXTRA`（与主链同款，否则机器码不可比） |
| 头路径 | `src/upstream/xunzip` + `src/upstream/xunzip/posix` |
| 新鲜度 | 源（`unzip.cpp/zip.cpp/operator_shim.cpp/unzip.h/zip.h`）**不比 `.o` 新**才跳过；否则重编（防"改了源码用旧 .o"的静默假绿） |
| 符号自检 | 必须提供 `OpenZipU/FindZipItemA/GetZipItemA/UnzipItem/CloseZipU`；缺则 `exit 12` **响亮失败**，不靠下游 undefined 兜底 |
| 失败处理 | 编译失败则 `rm -f` 半成品 `.o`（不毒化下一次） |

## 判据

- **X1** `sh -n tools/build_upstream.sh` 通过
- **X2** 云端**删除** `XUnzip.o` 后跑 `build_upstream.sh` ⇒ 能重新生成且 5 个入口符号齐全
- **X3** 云端 `toolchain_ab.sh` `zig-Os` 腿 rc=0、产出 `build/ab/zig-Os.elf`
- **X4** `abi_check.py` rc=0

**反证条件**：X2/X3 任一不成立 ⇒ 自举 flag 不对，须回`link_full.sh` 的 `FIDELITY/ARCH`
逐项对齐，**不得**退回"上传 .o"。

## 实测结果

（待回填）
