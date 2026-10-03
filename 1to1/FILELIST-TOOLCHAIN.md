# 判据：抽出 `tools/filelist.py`，让云端也能取清单

**预登记**：动手改`push_1to1.py` / `sync_mirror.py` 之前（2026-10-03，第 121 轮）。
**反证条件**：若抽出后`push_1to1.py --list-only` 的输出与抽出**前逐行相同**，
且 `sync_mirror.py` 在**云端**能成功取到清单 ⇒ 判据不成立（说明原路径本来就够用），
则本轮改动应回退。

## 病灶（实测，云端 `cnb-a2n-1k40p84gg`）

```
$ python3 tools/push_1to1.py --list-only
python3: can't open file '/workspace/1to1/tools/push_1to1.py': [Errno 2] No such file
```

**根因链**：
1. `push_1to1.py` 的 `EXCLUDE = {'tools/push_1to1.py'}`（脚本自身含 token，永不推送）
   ⇒ **它不会同步到云端/远端**
2. `sync_mirror.py` 的 `file_list()` 复用 `push_1to1.py --list-only` 取清单
   ⇒ **在云端必然失败**（结构性循环依赖，不是偶发）

**危害**：`sync_mirror.py` 只能在**本机**跑；云工作区里无法把本地改动同步回去，
于是"本地改了 → 云上看不到" ⇒ 上一轮 `default_core_list.c` 就是这样差点漏掉。

## 根治（不是绕过）

把**挑选规则**抽成 `tools/filelist.py`（**不含任何 token**），
由 `push_1to1.py`（GitHub 推送）与 `sync_mirror.py`（CNB 镜像）**共同 import**：

| 文件 | 职责变化 |
|---|---|
| `tools/filelist.py`（新） | **唯一真源**：walk 目录、排除规则、token 自检、`--list-only` 输出 |
| `tools/push_1to1.py` | 保留 GitHub API 推送；清单改为 `from filelist import build` |
| `tools/sync_mirror.py` | 不再 shell 调`push_1to1.py`，改 `import filelist` |

★ `filelist.py` **不含 token** ⇒ 可以入库、可以上云 ⇒ 循环依赖解除。
★ 规则仍**只写一处**（纪律：同一规则禁止写两处），两边不会漂移。

## 判据

- **F1** 抽出后，本机 `push_1to1.py --list-only` 输出与抽出**前逐行相同**
  （基线：首行 `FILELIST\t881\t(跳过构建产物/备份 653)`）
- **F2** `filelist.py` 内**不含** `ghp_` / token 读取（`grep -c 'ghp_' tools/filelist.py` = 0）
- **F3** `filelist.py` **不在** `EXCLUDE` 里 ⇒ 能随`push_1to1.py` 一起同步
- **F4** 云端 `python3 tools/filelist.py --list-only` 成功，FILELIST 计数与本机一致
- **F5** `sync_mirror.py` 在云端可跑（不再依赖缺失的 `push_1to1.py`）

**反证条件**：F1 不成立（清单变了）⇒ 抽取过程中引入了规则漂移，**必须回退**。

## 实测结果

（待回填）
