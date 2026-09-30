# 上游库版本取证与对齐（P0-C）— 2026-09-27

> 触发：第 68 轮问责审计发现 **75 个 DIVERGE 里约 45% 集中在上游库**（mxml 28 / libiconv 6 …），
> 而"上游库版本"此前是用**没有判别力的判据**钉的。本文用**可判别指纹**重新取证并实测。

---

## 〇、一句话结论

| 库 | 工厂实际版本（取证） | 我方原版本 | 状态 |
|---|---|---|---|
| mini-XML | **2.7 ~ 2.9**（夹逼） | 3.2 / 3.3.1 | ★ **已换 2.9，实测 DIVERGE 75 → 57（−18）** |
| GNU libiconv | **1.16**（`.data` 实测 0x0110） | 1.17 | 本轮实测中（见 §四） |
| stb_truetype | **≤ 1.22**（缺 1.23 才有的 SVG/整表 kerning API） | 1.26 | 已登记，待换 |
| Helix MP3 | 早于引入 `MP3ClearBadFrame` 的版本 | 较新 | 已登记，待定版本 |

---

## 一、方法论：**先证明判据有判别力，再用它下结论**

本项目此前两次"版本已对齐"的结论都建立在**不会失败的判据**上：

| 旧判据 | 为什么无效（实测） |
|---|---|
| 「工厂 16 个静态函数全集比对」→ 判定 mxml = v3.3.1 | `tools/mxml_version_fingerprint.py` 实测：**库本体静态函数名集合在 release-2.6 → v3.1 之间完全一致**（21/21 命中，未命中项全是我的正则漏抓 `static inline` 与 `#define _MXML_FINI _mxml_fini`）。判据**恒真** ⇒ 无判别力。 |
| 「`_libiconv_version` 两侧都读到 272 ⇒ 版本一致」 | 我方 `libiconv17/iconv.c` 把该对象改成了 **`extern`，定义由工厂数据镜像供给** ⇒ 我方产物里这个值**必然等于工厂值**。判据**恒定通过** ⇒ 无判别力，是**假对齐**。 |

**有效判据（本文采用，均可复现、且能失败）**

1. **函数入口自调用**：`bl <自身入口>` 存在 ⇒ 真递归（`b <自身入口>` 才是循环回边）。
2. **静态符号存在性**：file-scope static 会进 symtab，名字与源码逐字相同（不受 `-O2` 改名，
   只加 `.part.N/.isra.N` 后缀）。
3. **公有 API 存在性 + 官方 CHANGES 的引入版本**（联网核到官方变更日志）。
4. **数据对象初值**：如 `.data` 里的版本号常量。
5. **★ 交叉验证（最强）**：换版本后**是否多出工厂侧独有的符号** —— 这只有 pin 对了才会发生。

---

## 二、mini-XML：3.x → **2.9**（已落地，实测有效）

### 2.1 夹逼取证

| 证据 | 方法 | 结论 |
|---|---|---|
| 工厂 `mxmlDelete` 内含 `bl 0x2c2f44`（= 自身入口） | capstone 反汇编 + 区分 `bl`/`b` | **真递归** ⇒ 早于 2.10（2.10 为 CVE-2016-4570 改成迭代） |
| 工厂**没有** `mxml_free` 静态函数 | 符号集比对 | 2.10 才引入 ⇒ 再次 ⇒ **< 2.10** |
| 工厂**没有** `mxmlElementGetAttrCount/ByIndex`、`mxmlNewOpaquef/SetOpaquef` | 符号集 + 官方 CHANGES（2.11 条目） | ⇒ **< 2.11** |
| 工厂**有** `mxmlFindPath`、`mxmlGet*` 访问器 | 符号集 + 官方 CHANGES（2.7 条目） | ⇒ **≥ 2.7** |

⇒ 工厂 mxml ∈ **{2.7, 2.8, 2.9}**（三者的库本体差异只在 load 路径的 bug 修复）。

### 2.2 落地与实测

- 源码：`gitee.com/yuhang2__2/mxml`（完整 git 历史，含 `release-2.7/2.8/2.9/2.10`、`v2.11…v3.1` 标签）
  → 取 `release-2.9` 的 12 个库本体文件写入 `src/upstream/mxml/`，并按 2.9 的 `config.h.in` 重写 `config.h`。
- 回退：`build/_mxml_bak/`（原 3.x 全套）。

| 指标 | 换前（3.x） | 换后（2.9） | Δ |
|---|---|---|---|
| 共有函数 | 741 | **744** | **+3** |
| PASS | 661 | **682** | +21 |
| **DIVERGE** | **75** | **57** | **−18（−24%）** |
| TRUNC | 5 | 5 | 0 |
| ABI 门禁 | PASS | PASS | — |

**★ 交叉验证（决定性的旁证）**：换版本后**新增的 3 个共有符号**
`mxml_file_putc` / `mxml_string_putc` / `mxml_write_string`，
**正是换版本前"工厂有、我方没有"的那批名字**。pin 错版本时不可能出现这种补充。
⇒ 版本判定被独立证实，不是"试出来的巧合"。

**台账已按棘轮纪律删除 6 行**（`tools/upstream_api_pending.txt`），每行都可在新版产物里验证已不存在。

---

## 三、stb_truetype / Helix MP3：已取证，待落地

| 库 | 证据 | 目标版本 |
|---|---|---|
| stb_truetype | 我方 1.26 有、工厂**没有**：`stbtt_GetGlyphSVG` / `stbtt_GetCodepointSVG` / `stbtt_FindSVGDoc` / `stbtt_GetKerningTable` / `stbtt_GetKerningTableLength`。官方版本历史：**"1.23 (2020-02-02) query SVG data for glyphs; query whole kerning table"** ⇒ 这 5 个是 1.23 新增 ⇒ 工厂 **≤ 1.22** | ≤ 1.22（下一步用同法夹逼 1.20/1.21/1.22） |
| Helix MP3 | 我方有、工厂没有 `MP3ClearBadFrame`；且我方多 `mp3_unused_GetNextFrameInfo` | 待定（同上法） |

---

## 四、GNU libiconv：1.17 → **1.16**（本轮实测中）

- **硬证据**：工厂 `.data` 里 `_libiconv_version` @0x3b1cf8（4 B）= **272 = 0x0110 = 1.16**。
- 1.16 与 1.17 的 `lib/` 差异：1.17 **多出 56 个 EBCDIC/zos 相关表**（`ebcdic*.h` / `canonical_zos.h` / `aliases_zos.h`）。
- 我方补丁只有 **1 行**（`int _libiconv_version = _LIBICONV_VERSION;` → `extern`，由工厂镜像供给）
  ⇒ 换版成本低、风险可控。
- 判据：换后 §四 的 `cns11643_*_mbtowc` / `hkscs*_wctomb` / `big5_wctomb` / `cp1255/1258_wctomb` /
  `iso2022_jp2_wctomb` / `locale_charset` 这些分歧必须消失，且 **DIVERGE 必须继续下降**。
- 回退：`build/_lic17_bak/`、`build/_liccharset_bak/`。

---

## 五、纪律沉淀（新增）

> **26. 判据必须先自证"有判别力"**：一个对所有候选都返回同一结果的判据 = 没有判据。
> 任何"版本对齐""口径一致"的结论，必须能给出一条**能让它失败**的反例。
> **27. 凡是"由镜像/桩供给"的观测值，不得用作对齐证据**（`_libiconv_version` 假对齐教训）。
> **28. 换上游版本的正确性旁证 = 符号集向工厂收敛**（多出→消失、缺失→补齐），不是体积或自评。
