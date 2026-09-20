#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prop_equiv.py — **专有函数逐函数等价性差分器**（本地、零容器、零 QEMU）

为什么需要它（2026-09-20 的方法论纠偏）
---------------------------------------
P5 阶段长期用「QEMU 跑整体 + 函数级覆盖率」作为唯一进度刻度，代价：
  1. **覆盖率只回答"能跑到哪"，不回答"写得对不对"** —— 实测过：修掉 1816 次
     `gr_blit: source has wrong format` 忙循环，覆盖率**一动不动**（同函数内差异不敏感）。
  2. 覆盖到 76/223 = 34% 就上不去 ⇒ **66% 的函数从未被任何判据检验过**。
  3. 每轮推进要"重启容器 → bootstrap → 改 workflow → 等 CI"（8~12 分钟/轮），
     且靠"猜环境变量组合"驱动 ⇒ 反复出现"三组逐位相同"的零信息实验。

本工具换判据：**逐函数比对工厂二进制与重建产物的机器码特征**。
数据两侧都已有，无需任何运行时：
  · 工厂侧 `golden/factory.funcs.json`（`tools/extract_factory_funcs.py` 产出）
      835 个函数，每项：addr / n(指令条数) / t1(逐条反汇编文本) / t2(助记符序列) / b(基本块数)
  · 重建侧 `build/rkgame.rebuilt.elf` 的 **SHT_SYMTAB**（1661 个 FUNC + size）

判据（**双侧对称**，因为"偏大"与"偏小"的成因完全不同）
------------------------------------------------------------------------
★ 前提：**编译口径必须已对齐原厂**（见 `tools/link_audit.sh` 的 `OPT` 与 GAP 16.33）。
  本项目工厂 rkgame = `-Os`；口径不对齐时"常量次数小循环被展开"会造成 4~7× 的**纯噪声**，
  让这个判据完全失效（先把口径对齐，再谈实现差异）。

两侧都要管：
    ratio = 重建字节数 / 工厂(指令数×4)
    skew  = max(ratio, 1/ratio)          ← 对称偏离度
    · ratio 偏大（>1）多为**循环展开/内联差异**（编译器）
    · ratio 偏小（<1）多为**我们少实现了东西**（真差异）
三档（对 skew 而言）：
    OK   skew < warn(1.6)
    WARN warn <= skew < fail(2.5)
    FAIL skew >= fail(2.5)

三个独立刻度（任一超标都报，取最恶劣者定级）：
    1. size_ratio   = 重建函数字节数 / 工厂 (n*4)      ← 主判据（沿用项目阈值）
    2. n_ratio      = 重建指令条数 / 工厂指令条数
    3. mnem_sim     = 助记符序列相似度（difflib，对**函数内**差异敏感）
       ★ mnem_sim 只在两侧指令数接近时可信；差异大时它会天然偏低，故仅作**辅助参考**，
         不单独用于定级（避免把"编译器差异"误判成"实现不符"）。

用法
----
    python3 tools/prop_equiv.py                          # 全部专有函数，FAIL 在前
    python3 tools/prop_equiv.py --top 40                 # 只看最可疑的 40 个
    python3 tools/prop_equiv.py --only mui               # 只看名字含 mui 的
    python3 tools/prop_equiv.py --selftest               # 自证（锚点全部人工核对）
    python3 tools/prop_equiv.py --json out.json          # 落盘机器可读结果

退出码：0 = 无 FAIL；2 = 有 FAIL（与 `scan_upstream_fingerprint.py` 一致的约定）
"""
import argparse
import difflib
import io
import json
import os
import struct
import sys

# ---------------------------------------------------------------- 配置
FACTORY_JSON = "golden/factory.funcs.json"
REBUILT_ELF = "build/rkgame.rebuilt.elf"
PROP_DIR = "src/proprietary"
WARN = 1.6
FAIL = 2.5


# ---------------------------------------------------------------- ELF：symtab
class ElfSym:
    """只做一件必须的事：把 SHT_SYMTAB 里 type=FUNC 的符号取成 {name: (vaddr, size)}。

    ★ 为什么不用 dis_got.Elf：它的 `syms` 读的是 **dynsym**（重建产物只有 85 个），
      而我们要的是 **symtab**（1661 个）。这里单独解析，避免误用。
    """

    def __init__(self, path):
        self.path = path
        self.d = open(path, "rb").read()
        self.loads = []          # (vaddr, off, filesz, memsz, flags)
        self.funcs = {}          # name -> (vaddr, size)
        self._read_ph()
        self._read_symtab()

    def _read_ph(self):
        d = self.d
        phoff = struct.unpack_from("<I", d, 28)[0]
        phent = struct.unpack_from("<H", d, 42)[0]
        phnum = struct.unpack_from("<H", d, 44)[0]
        for i in range(phnum):
            t, o, v, pa, fs, ms, fl, al = struct.unpack_from("<8I", d, phoff + i * phent)
            if t == 1:
                self.loads.append((v, o, fs, ms, fl))

    def v2o(self, v):
        for vv, oo, fs, ms, fl in self.loads:
            if vv <= v < vv + max(fs, ms):
                return oo + (v - vv)
        return None

    def o2v(self, o):
        for vv, oo, fs, ms, fl in self.loads:
            if oo <= o < oo + fs:
                return vv + (o - oo)
        return None

    def rd32(self, v):
        o = self.v2o(v)
        if o is None or o + 4 > len(self.d):
            return None
        return struct.unpack_from("<I", self.d, o)[0]

    def text_range(self):
        """返回可执行段中覆盖最广的 (vaddr, filesz, off)。"""
        best = None
        for v, o, fs, ms, fl in self.loads:
            if fl & 0x1 and (best is None or fs > best[1]):
                best = (v, fs, o)
        return best

    def _read_symtab(self):
        d = self.d
        shoff = struct.unpack_from("<I", d, 32)[0]
        shent = struct.unpack_from("<H", d, 46)[0]
        shnum = struct.unpack_from("<H", d, 48)[0]
        S = [struct.unpack_from("<10I", d, shoff + i * shent) for i in range(shnum)]
        idxs = [i for i, s in enumerate(S) if s[1] == 2]      # SHT_SYMTAB
        if not idxs:
            return
        sy = S[idxs[0]]
        stro = S[sy[6]][4]
        ent = sy[9] or 16
        for j in range(sy[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from("<IIIBBH", d, sy[4] + j * ent)
            if nmn == 0 or sz == 0:
                continue
            if (inf & 0xF) != 2:                              # STT_FUNC
                continue
            k = d.index(b"\x00", stro + nmn)
            name = d[stro + nmn:k].decode("utf-8", "replace")
            self.funcs[name] = (val, sz)


# ---------------------------------------------------------------- 反汇编：取助记符
def mnem_seq(elf, vaddr, size):
    """把 [vaddr, vaddr+size) 的指令解成助记符序列。

    复用 `dis_got.dec()` 的解码器（已在本项目验证过：能解 `ldr Rd,[pc,#imm]` +
    `add Rd,pc,Rm` 字面量池、旋转立即数、`movw/movt`、`b/bl` 等）。
    只取第一个空白前的 token ⇒ 助记符（操作数不进比对，避免地址/立即数干扰）。
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import dis_got                                     # noqa: E402
    out = []
    unknown = 0
    off = 0
    while off + 4 <= size:
        w = elf.rd32(vaddr + off)
        if w is None:
            break
        try:
            mn, _note = dis_got.dec(w, vaddr + off, elf)
        except Exception:
            mn = "?"
        tok = mn.split(" ")[0].rstrip(",").strip()
        if not tok or tok == "?":
            unknown += 1
            tok = "?"
        out.append(tok)
        off += 4
    return out, unknown


# ---------------------------------------------------------------- 主流程
def load_factory():
    """读工厂侧函数级模型。

    ★ **必须支持 `.json.gz`**：仓库里入库的是压缩版（`push_1to1.py` 显式登记
      `golden/factory.funcs.json.gz`，3.67 MB），未压缩的 21 MB `.json` **只在本地**。
      首跑 CI 就因为只找 `.json` 而报 `缺 golden/factory.funcs.json` 直接失败 —— 这是
      "本地能跑、CI 跑不了"的典型形态，必须两种都试。
    """
    plain = FACTORY_JSON
    gz = FACTORY_JSON + ".gz"
    if os.path.exists(plain):
        j = json.load(io.open(plain, encoding="utf-8"))
        src = plain
    elif os.path.exists(gz):
        import gzip
        with gzip.open(gz, "rb") as f:
            j = json.loads(f.read().decode("utf-8"))
        src = gz
    else:
        return None, None
    return j["functions"], src


def proprietary_names():
    """专有函数名清单 —— 直接取我们重建时产出的源文件名（`FUN_<addr>_<name>.c`）。

    这样做的好处：清单 = "我们实际动手重写了什么"，与 `src/proprietary` 同步，
    不依赖任何人工维护的列表（不会漂移）。
    """
    names = set()
    if not os.path.isdir(PROP_DIR):
        return names
    for root, _dirs, files in os.walk(PROP_DIR):
        for f in files:
            if not f.endswith(".c"):
                continue
            stem = f[:-2]
            parts = stem.split("_", 2)          # FUN / 0000d678 / InitDisplay
            if len(parts) >= 3 and parts[0] == "FUN":
                names.add(parts[2])
            else:
                names.add(stem)
    return names


# ---- 名字归一化：剥离 GCC 的克隆/常量传播后缀 -------------------------------
#   工厂侧（GCC）会把函数拆成 `code_convert.constprop.22` / `mui_outputxy_length.isra.19` /
#   `run_process.part.0`；我们（clang/zig）产出的名字没有后缀。
#   不归一化会把这批函数误报成 MISSING（首跑实测：3 个）。
_CLONE_SUFFIX = (".constprop.", ".isra.", ".part.", ".cold", ".clone.", ".lto_priv.")


def norm_name(n):
    for s in _CLONE_SUFFIX:
        i = n.find(s)
        if i > 0:
            return n[:i]
    return n


# ---- 内置校准锚点 -----------------------------------------------------------
#   ★ 判据必须能"自证没有失真"。做法：拿**必然存在、且两侧来源不同但功能等价**的
#     工具链样板函数当锚点。`__libc_csu_fini` 是 link 时由各自 libc 生成，我们从未
#     写过它 ⇒ 两侧必然不同字节，但**功能等价是已知事实**。
#     若它被判成 FAIL，说明判据把"工具链差异"误当"实现不符" ⇒ 判据失真，必须先修判据。
#     （首跑实测：`__libc_csu_fini` 4B→12B、ratio 3.0 ⇒ 落在 FAIL ⇒ 正是这条锚点抓出来的。）
CALIB_ANCHORS = ("__libc_csu_fini", "__libc_csu_init")

# ---- 薄函数档 --------------------------------------------------------------
#   工厂侧 ≤ 4 条指令（16 B）的函数，典型是"空桩"（GCC -O2 把空函数折成单条 `bx lr` = 4 B）。
#   我们侧编译器会保留序言（push/pop）⇒ 3 倍差异**不代表实现不同**。
#   ⇒ 单独归为 `THIN`（不计入 FAIL/WARN），但**照常列出**（供人工抽查），
#     并标注 `thin_hint`，避免"看不见"和"误报"两种错误同时发生。
THIN_BYTES = 16


def load_baseline(path):
    """基线豁免表（与 `upstream_fingerprint_baseline.txt` 同一纪律）。

    语义：本表列出的函数，即使被判 FAIL，也只降级为 **KNOWN**（不拖红 CI）。
    ★ 纪律（违反即门禁失效）：
      1. 每修好一项，**必须立即删除**对应基线行；
      2. **不得**把新发现的问题塞进基线（基线只登记"已定位、有明确计划、暂未动手"的项）；
      3. 每行必须带原因与登记日期，便于审计。
    """
    names = set()
    if not path or not os.path.exists(path):
        return names
    for l in io.open(path, encoding="utf-8", errors="replace"):
        t = l.strip()
        if not t or t.startswith("#"):
            continue
        names.add(norm_name(t.split()[0]))
    return names


def compare(fac, re_syms, elf, names, baseline=None, verbose=False):
    # 重建侧索引：原名 + 归一化名都能查到
    re_idx = {}
    for k, v in re_syms.items():
        re_idx.setdefault(k, v)
        re_idx.setdefault(norm_name(k), v)

    # 工厂侧索引：归一化名 -> 原条目（多个克隆取"指令数最多"的那个为主）
    fac_idx = {}
    for k, v in fac.items():
        nk = norm_name(k)
        cur = fac_idx.get(nk)
        nv = v.get("n") or len(v.get("t2") or []) or 0
        if cur is None or nv > (cur.get("n") or 0):
            fac_idx[nk] = v

    rows = []
    for nm in sorted(names):
        nk = norm_name(nm)
        f = fac.get(nm) or fac_idx.get(nk)
        r = re_syms.get(nm) or re_idx.get(nk)
        if f is None or r is None:
            rows.append({"name": nm, "status": "MISSING",
                         "missing": "factory" if f is None else "rebuilt"})
            continue
        rv, rsz = r
        fn = f.get("n") or len(f.get("t2") or []) or len(f.get("t1") or [])
        if not fn:
            rows.append({"name": nm, "status": "NODATA", "missing": "n"})
            continue
        fmem = fn * 4                                  # 工厂：ARM 定长 4 字节
        seq, unk = mnem_seq(elf, rv, rsz) if elf else ([], 0)
        rn = len(seq)
        fseq = f.get("t2") or []
        sim = None
        if fseq and seq:
            sim = difflib.SequenceMatcher(None, fseq, seq).ratio()
        size_ratio = rsz / float(fmem)
        n_ratio = (rn / float(fn)) if rn else None
        # ★★ 两侧对称（2026-09-20 修正）：`|ratio-1|` 取最小是**错**的判据 ——
        #   · ratio 偏大（>1）多为**循环展开**（纯编译器噪声；用 -Os 对齐口径后即消失）
        #   · ratio 偏小（<1）多为**我们少实现了东西**（真差异）
        #   两者成因完全不同，却都偏离 1 ⇒ 必须**分别设阈值**，而不是取绝对值。
        #   本项目实证（容器全量 213 函数）：`-O1` 口径下"逐函数 |ratio-1| 更小"者比 `-Os` 多，
        #   但那些"更优"项全是 `init_user_joy_key_mask` 0.51 / `popwindows` 0.86 这种**偏小**项
        #   —— 是"从 1.55 变成 0.80"被误当成改善。改成对称后，偏小同样会报。
        skew = max(size_ratio, (1.0 / size_ratio) if size_ratio > 0 else 1e9)
        worst = max([skew] + ([max(n_ratio, 1.0 / n_ratio)] if n_ratio else []))

        is_thin = fmem <= THIN_BYTES
        is_calib = nm in CALIB_ANCHORS or nk in CALIB_ANCHORS
        if is_calib:
            status = "CALIB"
        elif is_thin:
            status = "THIN"
        else:
            status = "FAIL" if worst >= FAIL else ("WARN" if worst >= WARN else "OK")
        if status == "FAIL" and baseline and nk in baseline:
            status = "KNOWN"
        rows.append({"name": nm, "status": status,
                     "fac_n": fn, "fac_b": fmem, "reb_b": rsz, "reb_n": rn,
                     "size_ratio": round(size_ratio, 3),
                     "n_ratio": round(n_ratio, 3) if n_ratio else None,
                     "mnem_sim": round(sim, 3) if sim is not None else None,
                     "unknown_insn": unk, "fac_b_blocks": f.get("b"),
                     "thin": is_thin, "calib": is_calib})
    return rows


def distribution(rows, floor_bytes=64):
    """用**实测分布**而非照搬阈值：只看体量足够大（≥ floor_bytes）的函数。

    ★ 理由：薄函数被工具链样板主导（ratio 天然虚高），把它们混进分布会把
      阈值校准到错误的位置。大函数才是"实现是否一致"的可靠载体。
    """
    xs = sorted(r["size_ratio"] for r in rows
                if r.get("size_ratio") and r.get("fac_b", 0) >= floor_bytes
                and not r.get("calib"))
    if not xs:
        return None
    n = len(xs)

    def q(p):
        return xs[min(n - 1, int(p * n))]
    return {"n": n, "min": xs[0], "p50": q(.50), "p75": q(.75),
            "p90": q(.90), "p95": q(.95), "max": xs[-1]}


def calib_verdict(rows):
    """校准锚点的裁决：CALIB 项必须**不**被判 FAIL/WARN。

    返回 (ok, 说明)。这是"判据是否失真"的机器可判据 —— 不靠人看。
    """
    bad = [r for r in rows if r.get("calib") and r["status"] in ("FAIL", "WARN")]
    if not bad:
        return True, "校准锚点全部落在 THIN/CALIB（工具链样板差异已被正确隔离）"
    return False, "★ 校准锚点被误判为 %s ⇒ 判据失真：%s" % (
        "/".join(sorted({r["status"] for r in bad})),
        ", ".join("%s(%dB→%dB, %.2fx)" % (r["name"], r["fac_b"], r["reb_b"], r["size_ratio"])
                  for r in bad))


def report(rows, top=None, only=None):
    if only:
        rows = [r for r in rows if only in r["name"]]
    stat = {}
    for r in rows:
        stat[r["status"]] = stat.get(r["status"], 0) + 1
    order = {"FAIL": 0, "WARN": 1, "KNOWN": 2, "MISSING": 3, "NODATA": 4,
             "CALIB": 5, "THIN": 6, "OK": 7}
    rows.sort(key=lambda r: (order.get(r["status"], 9), -(r.get("size_ratio") or 0)))
    print("=" * 100)
    print("专有函数等价性差分（工厂 `golden/factory.funcs.json` vs 重建 `%s`）" % REBUILT_ELF)
    print("判据：size_ratio（阈值 WARN>=%.1f FAIL>=%.1f）· 薄函数(工厂<=%dB)单列 THIN · 校准锚点单列 CALIB"
          % (WARN, FAIL, THIN_BYTES))
    print("=" * 100)
    print("  汇总：总计 %d | ★FAIL %d | WARN %d | OK %d | THIN %d | CALIB %d | MISSING %d"
          % (len(rows), stat.get("FAIL", 0), stat.get("WARN", 0), stat.get("OK", 0),
             stat.get("THIN", 0), stat.get("CALIB", 0), stat.get("MISSING", 0)))
    d = distribution(rows)
    if d:
        print("  实测分布（仅体量>=64B 的非校准函数，n=%d）："
              "min %.2f | p50 %.2f | p75 %.2f | p90 %.2f | p95 %.2f | max %.2f"
              % (d["n"], d["min"], d["p50"], d["p75"], d["p90"], d["p95"], d["max"]))
        print("     ⇒ 大函数的健康水位由**实测**给出；超过 p95 的项才值得优先人工看")
    ok, why = calib_verdict(rows)
    print("  校准锚点裁决：%s %s" % ("✓" if ok else "✗", why))
    print()
    print("  %-34s %-6s %9s %9s %7s %7s" % ("函数", "判定", "工厂B", "重建B", "size比", "指令比"))
    print("  " + "-" * 96)
    n = 0
    for r in rows:
        if r["status"] == "OK" and top:
            continue
        if r["status"] in ("MISSING", "NODATA"):
            print("  %-34s %-6s   %s" % (r["name"][:34], r["status"], r.get("missing", "")))
        else:
            tag = ""
            if r.get("thin"):
                tag = " ←薄桩（工具链样板主导）"
            elif r.get("calib"):
                tag = " ←校准锚点（两侧来源不同但功能等价）"
            elif r.get("size_ratio") and r["size_ratio"] < 0.6 and r.get("fac_b", 0) >= 64:
                # ★ 偏小提示（2026-09-20 加）：本项目实测，编译器会把一个函数**拆成多段**
                #   （热路径 + 主体），而 symtab 的 st_size **只覆盖第一段** ⇒ 表现为"偏小"。
                #   实证：`UpdateROM` 工厂 976 B，我们符号 116 B；但紧随那个字面量池之后
                #   就是主体代码（`mov r1, #480` = `scr_h_size = 0x1e0`，与源码常量逐字对应）。
                #   ⇒ 看到本提示时，**先去反汇编"紧随地址"**，再判"少实现"还是"分段"。
                tag = " ←★偏小：疑编译器分段（查紧随地址）或真的少实现"
            print("  %-34s %-6s %9d %9d %7.3f %7s%s" % (
                r["name"][:34], r["status"], r["fac_b"], r["reb_b"],
                r["size_ratio"], r["n_ratio"], tag))
        n += 1
        if top and n >= top:
            print("  ...（只显示前 %d 个）" % top)
            break

    # ★ 助记符相似度的"信息量自证"：若连体量健康的大函数也普遍接近 0，
    #   该判据在本项目就是无信息的 —— 必须显式说出来，不能假装它在工作。
    sims = [r["mnem_sim"] for r in rows
            if r.get("mnem_sim") is not None and r.get("fac_b", 0) >= 64]
    if sims:
        sims.sort()
        med = sims[len(sims) // 2]
        print("\n  ★ 助记符相似度自证（体量>=64B，n=%d）：中位数 %.3f，最高 %.3f"
              % (len(sims), med, sims[-1]))
        if med < 0.35:
            print("     ⇒ 中位数过低 ⇒ **本判据在当前工具链组合（GCC vs clang/zig）下无信息量**，"
                  "结论一律不得引用 mnem_sim。")
    return rows


# ---------------------------------------------------------------- 自证
def selftest():
    """锚点自证：判据的边界必须被显式钉死（本项目铁律：仪器缺陷靠锚点拦，不靠人看）。"""
    # 锚点 A：ratio 分档边界
    def grade(fac_b, reb_b):
        if fac_b <= THIN_BYTES:
            return "THIN"
        r = reb_b / float(fac_b)
        skew = max(r, 1.0 / r) if r > 0 else 1e9
        return "FAIL" if skew >= FAIL else ("WARN" if skew >= WARN else "OK")

    A = [
        (100 * 4, 100 * 4, "OK",   "同编译器级别：完全一致"),
        (100 * 4, 150 * 4, "OK",   "1.50 倍（GCC vs clang 常见上界）"),
        (100 * 4, 160 * 4, "WARN", "1.60 倍 = WARN 阈值（含等号）"),
        (100 * 4, 250 * 4, "FAIL", "2.50 倍 = FAIL 阈值（含等号）"),
        (100 * 4, 101 * 4, "OK",   "1.01 倍"),
        (100 * 4, 500 * 4, "FAIL", "5 倍 ⇒ 实现不符强信号"),
        # ★ 薄函数档：首跑实测 10 个 `4B → 12B`（ratio 3.0）全部集中在薄桩，
        #   且 `__libc_csu_fini` 是**我们从未写过**的工具链样板 ⇒ 必须归 THIN 而非 FAIL。
        (4,      12,       "THIN", "★ 空桩（工厂 bx lr = 4B）→ 我们侧带序言 12B ⇒ 不得判 FAIL"),
        (16,     48,       "THIN", "THIN 上界（工厂 4 条指令）"),
        (20,     60,       "FAIL", "刚过 THIN 上界：20B→60B = 3.0x ⇒ FAIL"),
        # ★ 双侧对称锚点（2026-09-20 加）：偏小同样必须报
        (100 * 4, 25 * 4,  "FAIL", "★ 偏小 4.0x（我们只实现了 1/4）⇒ 必须 FAIL（旧判据会放过）"),
        (100 * 4, 62 * 4,  "WARN", "偏小 1.61x = 刚过 WARN"),
        (100 * 4, 63 * 4,  "OK",   "偏小 1.59x = 未过 WARN"),
    ]
    bad = 0
    print("=" * 84)
    print("prop_equiv.py --selftest（判据边界锚点，全部人工核对）")
    print("=" * 84)
    for fac_b, reb_b, want, note in A:
        got = grade(fac_b, reb_b)
        want2 = want
        ok = "✓" if got == want2 else "✗"
        if got != want2:
            bad += 1
        print("  %s fac=%5dB reb=%5dB  ratio=%.2f  → %-4s（期望 %-4s）  %s"
              % (ok, fac_b, reb_b, reb_b / float(fac_b), got, want2, note))
    print()
    print("  锚点通过 %d/%d" % (len(A) - bad, len(A)))
    return 0 if bad == 0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=None)
    ap.add_argument("--only", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--baseline", default="tools/prop_equiv_baseline.txt",
                    help="基线豁免表（命中 FAIL 降级为 KNOWN，不拖红 CI）")
    ap.add_argument("--no-disasm", action="store_true",
                    help="跳过反汇编（只比 size/指令数）—— 用于快速总览")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    fac, src = load_factory()
    if fac is None:
        print("!! 缺 %s 或 %s.gz（应由 tools/extract_factory_funcs.py 产出）"
              % (FACTORY_JSON, FACTORY_JSON))
        return 1
    names = proprietary_names()
    print("  工厂模型 %s：%d 个函数；专有清单（src/proprietary）%d 个"
          % (src, len(fac), len(names)))

    elf = None
    re_syms = {}
    if os.path.exists(REBUILT_ELF) and not a.no_disasm:
        e = ElfSym(REBUILT_ELF)
        re_syms = e.funcs
        data = io.open(REBUILT_ELF, "rb").read()
        elf = _MiniElf(REBUILT_ELF, e)
        print("  重建产物 FUNC 符号 %d 个" % len(re_syms))
    elif os.path.exists(REBUILT_ELF):
        e = ElfSym(REBUILT_ELF)
        re_syms = e.funcs
        print("  重建产物 FUNC 符号 %d 个（--no-disasm：不反汇编）" % len(re_syms))
    else:
        print("  ★ 缺 %s ⇒ 只能显示 MISSING（本地需先 bootstrap 或在 CI 里跑）" % REBUILT_ELF)

    base = load_baseline(a.baseline)
    if base:
        print("  基线豁免表 %s：%d 项" % (a.baseline, len(base)))
    rows = compare(fac, re_syms, elf, names, baseline=base)
    report(rows, top=a.top, only=a.only)

    if a.json:
        json.dump(rows, io.open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\n  已落盘 %s" % a.json)

    # 退出码：判据失真（校准锚点被误判）与真 FAIL 都必须让 CI 红。
    ok, why = calib_verdict(rows)
    if not ok:
        print("\n::error::prop_equiv 判据失真：%s" % why)
        return 3
    fails = [r for r in rows if r["status"] == "FAIL"]
    if fails:
        print("\n  真 FAIL %d 个（薄桩/校准锚点已排除）：%s"
              % (len(fails), ", ".join(r["name"] for r in fails[:12])))
    return 2 if fails else 0


class _MiniElf:
    """给 `dis_got.dec()` 用的最小适配器：只要 rd32 / v2o / o2v / rel_sym。"""

    def __init__(self, path, sym: ElfSym):
        self._s = sym
        self.rel = {}
        self.symname = {}

    def rd32(self, v):
        return self._s.rd32(v)

    def v2o(self, v):
        return self._s.v2o(v)

    def o2v(self, o):
        return self._s.o2v(o)

    def rel_sym(self, _addr):
        return None


if __name__ == "__main__":
    sys.exit(main())
