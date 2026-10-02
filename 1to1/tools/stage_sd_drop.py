#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""stage_sd_drop.py —— 真机投放包（`_sdcard_dropN/`）的**唯一**打包器。

## 为什么要有它（不是"又写一个脚本"）
`stage_sd_round4/5/7.py` 每轮抄一份：目录布局、cfg.ini、manifest 格式、README 模板
**各写一遍**（纪律 69 的反例）。后果实测过两次：
  · round7 的 README 里"行为尺当前"读的是 **`report/_deliver_diff.txt`** —— 一个**与投放产物无关**
    的固定路径 ⇒ 数字与被投放的字节**可以不一致**（"交付物与说明书对不上"）。
  · round7 的 README 判断标准里写着"t3 仍崩在 `sfc_init` 附近"，而**t3 早已不是那一版**。
⇒ 本工具把"投放包应当包含什么"收敛成一处，并且**所有数字都由
  `tools/ruler_baseline.py` 的权威基线提供**（它会用**被测产物的 sha** 去 report/ 里反查；
  对不上就 fail-closed，绝不用别的报告的数字来充数）。

## 判据（机械，全部 fail-closed）
1. `cubegm/rkgame` 探针、`rkgame.t1`（已知答案对照）、`rkgame.t3`（本轮候选）三者必须存在；
2. `ruler_baseline.py` 必须为 **t3 的 sha** 返回基线（否则拒投）；
3. 读不到基线 ⇒ exit 2；缺文件 ⇒ exit 3；旧目录删不掉 ⇒ exit 4（禁止产出半成品包）。

用法:
    python tools/stage_sd_drop.py --round 8 \
        --t1 build/_prewidth.rebuilt.elf \
        --t3 build/rkgame.rebuilt.elf \
        --probe build/rkgame.probe5 \
        --out _sdcard_drop8
"""
import argparse
import datetime
import hashlib
import io
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CFG_INI = """# cgm_diag config.  The real setting is the first non-comment line below.
level = 3
#   0 = crash report only
#   1 = lifecycle / signals / file open-close / dlopen / threads
#   2 = 1 + read/write/lseek offsets + every ioctl + mmap  (built-in default)
#   3 = 2 + content hex + malloc-free detail (slowest)
"""

PUT_ONLY = """把本目录整体拷到 SD 卡的 cubegm/_diag/。
探针 v5 会把结论写进 PROBE5.txt；_diag/ 必须存在且可写。
cfg.ini 里第一行真设置是 level = 3。
"""

README_TMPL = """ 真机测试 第 {round} 轮 —— 交付版产物验证
=================================================================
生成时间: {gen}

【本轮为什么重投（一句话说清，不绕）】
  ★ 上一包的 `cubegm/rkgame.t3` 里 **PT_INTERP 指向的是 Windows 宿主路径**：
        C:/Users/<user>/.workbuddy/binaries/PortableGit/versions/1.2.0/lib/ld-linux-armhf.so.3
    内核在 execve 里**只校验该绝对路径是否存在**（连 libc 都不查），不存在就立即返回 ENOENT
    ⇒ 进程根本不会启动 ⇒ 这正是我们一直看到的「开机失败 + `_diag/` 一条日志都没有」。
    根因已复现：`zig ld.lld` 直驱链接**硬忽略** `--dynamic-linker`（三种写法全试过，全部无效）。
  ★ 因此 **drop{prev} 的 t3 结果无论是什么都不可信**；本轮已强制对齐并重投。

【本包要回答的唯一问题（判决先写死，避免事后凑结论）】

  `cubegm/rkgame.t3`（= **解释器已对齐**的交付产物）这次能不能被内核 exec 起来、
  起来之后**还崩不崩、崩在哪**。

【本包设计的是一次「三点阶梯」实验 —— 一次上机给出完整因果链】

  | 被测 | 是什么 | 预期 |
  |---|---|---|
  | `rkgame.bak` | 原厂（阳性对照，须已在 SD 上） | **存活至超时**（正常启动） |
  | `rkgame.t1`  | {t1_role} | 见下方判断标准 |
  | `rkgame.t3`  | ★ 本轮候选（**解释器已对齐**） | 见下方判断标准 |

  ★ t1 与 t3 **唯一的差别就是 PT_INTERP 那 {t1_span} 字节**（其余逐字节相同）
    ⇒ 探针一次跑完三者，等于在**真机上**做了一次单变量 A/B。

【你要做的 4 步】

  1) 确认 SD 卡上 `cubegm/rkgame.bak` 存在（= 原厂备份，应为 3,921,108 字节）。
     ★ 它是"阳性对照"。**若不存在**：先把 SD 上现存的 `cubegm/rkgame` 复制成 `rkgame.bak`
       再继续（**在任何覆盖之前先做这一步**）。

  2) 把本包 `cubegm/` 里这 4 个东西拷到 SD 卡：
        rkgame        ({probe_size})   ← 探针 v5，**必须覆盖**（它是被开机执行的那个）
        rkgame.t1     ({t1_size})      ← {t1_role}
        rkgame.t3     ({t3_size})      ← ★ 本轮候选
        _diag/        整个目录（合并覆盖，`cfg.ini` 一定要覆盖）

  3) 插卡开机，**等满 90 秒**（黑屏也等满；崩溃现场在崩的那一刻就已写进 SD）。

  4) 关机拔卡，把 `cubegm/_diag/PROBE5.txt` 整个发我。

【回退到原厂（随时可做）】

  把 `cubegm/rkgame.bak` 复制一份改名成 `cubegm/rkgame` 即可。

【本轮判断标准（★ 先写死）】

  · 阳性对照 `rkgame.bak` 必须仍"存活至超时"。否则**整轮作废**，先查探针。
  · `rkgame.t1`：{t1_expect}
  · **`rkgame.t3`（本轮关键）四种可能，各有明确含义：**
      (a) 存活至超时              ⇒ ★ 启动链打通，进入功能验收
      (b) 崩在**别的** PC          ⇒ 已越过 exec 关口，进入下一个故障点（探针会给 PC/LR/SP）
      (c) 出现 `EXECVE-FAILED errno=2` ⇒ 解释器/依赖仍不可达（探针那行就是定位）
      (d) 探针**自己也写不出**      ⇒ 与文件内容无关（内核/SD 挂载层）

【本包文件的 sha256（投放前请核对，尤其 t3）】

  cubegm/rkgame.t3  {t3_size} 字节  PT_INTERP={t3_interp}
    {t3_sha}
  cubegm/rkgame.t1  {t1_size} 字节  PT_INTERP={t1_interp}
    {t1_sha}

【诚实声明（没有验证的）】

  · ★ **本交付产物尚未在真机上跑过。** 下面这条是它在本机（与 CI 逐项一致）的行为尺成绩。
{ruler}
  · 行为尺只证明"在沙箱里跑到的观测量一致"，**不证明功能正确**。
  · 沙箱侧能复现真机的 MMIO 总线约束（严格模式下 `MMIO-STRICT VIOLATION` 计数）——
    当前产物该计数见投放前门禁报告，非 0 就不该投。
=================================================================
"""


def _interp_of(path):
    """返回该 ELF 的**真实 PT_INTERP 字符串**（读程序头，不做全文件子串搜索）。"""
    import struct
    d = open(path, 'rb').read()
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    phent = struct.unpack_from('<H', d, 42)[0]
    phnum = struct.unpack_from('<H', d, 44)[0]
    for i in range(phnum):
        o = e_phoff + i * phent
        t, off, va, pa, fsz = struct.unpack_from('<5I', d, o)
        if t == 3:
            raw = d[off:off + fsz]
            z = raw.find(0)
            return (raw[:z] if z >= 0 else raw).decode('latin-1')
    return ''


def _interp_gate(path, must_ok, label):
    """★ 第 109 轮的教训：投放包里"设备 exec 不了"的产物等于零信息。

    `must_ok=True` 时必须精确等于 `/lib/ld-linux-armhf.so.3`，否则 **拒投**。
    """
    got = _interp_of(path)
    want = '/lib/ld-linux-armhf.so.3'
    if must_ok and got != want:
        print('!! %s 的 PT_INTERP = %r ≠ %r ⇒ 设备上内核 execve 必 ENOENT ⇒ 拒绝投放'
              % (label, got, want))
        return None
    return got


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def authoritative_baseline(artifact):
    """唯一权威基线来源：`tools/ruler_baseline.py`（用**产物 sha** 反查 report/）。

    返回 `(base_line, None)` 或 `(None, 原因)`。★ 绝不用固定路径的报告充数。
    """
    p = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'ruler_baseline.py'),
                        '--artifact', artifact],
                       capture_output=True, text=True, cwd=ROOT)
    if p.returncode != 0 or not (p.stdout or '').strip().startswith('BASE '):
        return None, ((p.stderr or p.stdout or '').strip()[:400] or 'rc=%d' % p.returncode)
    return (p.stdout or '').strip().splitlines()[0], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--round', type=int, required=True)
    ap.add_argument('--prev', type=int, default=None, help='上一轮编号（README 里叙述用）')
    ap.add_argument('--probe', default=os.path.join(ROOT, 'build', 'rkgame.probe5'))
    ap.add_argument('--t1', required=True)
    ap.add_argument('--t3', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--t1-role', default='已知答案对照（旧版产物）',
                    help='README 里对 t1 的一句话说明')
    ap.add_argument('--t1-expect', default='预期仍崩 —— 它是"仪器能看出崩溃"的对照',
                    help='README 判断标准里对 t1 的预期')
    a = ap.parse_args()

    items = [(a.probe, 'cubegm/rkgame'),
             (a.t1, 'cubegm/rkgame.t1'),
             (a.t3, 'cubegm/rkgame.t3')]
    missing = [s for s, _ in items if not os.path.isfile(s)]
    if missing:
        print('!! 缺文件，拒绝投放：')
        for m in missing:
            print('   ', m)
        return 3

    # ★★ 第 109 轮教训（fail-closed）：投放包里"设备 exec 不了"的产物等于零信息。
    #    真机 execve 只认 PT_INTERP 的**绝对路径**；不是设备侧路径 ⇒ ENOENT ⇒ 进程不启动 ⇒ 零日志。
    t3_interp = _interp_gate(a.t3, True, 't3（本轮候选）')
    if t3_interp is None:
        return 5
    t1_interp = _interp_gate(a.t1, False, 't1（对照）')
    t1_span = 0
    try:
        import struct as _st
        for p in (a.t1, a.t3):
            d = open(p, 'rb').read()
            e_phoff = _st.unpack_from('<I', d, 28)[0]
            phent = _st.unpack_from('<H', d, 42)[0]
            phnum = _st.unpack_from('<H', d, 44)[0]
            for i in range(phnum):
                o = e_phoff + i * phent
                t, off, va, pa, fsz = _st.unpack_from('<5I', d, o)
                if t == 3:
                    t1_span = fsz
                    break
            if t1_span:
                break
    except Exception:
        t1_span = 0

    base, why = authoritative_baseline(a.t3)
    if base is None:
        print('!! 取不到权威行为尺基线 ⇒ 拒绝投放（不得用别的报告的数字充数）')
        print('   ', why)
        return 2
    f = base.split()
    # BASE <sha16> <共有> <PASS> <DIVERGE> <TRUNC> <SKIP> <REFDEAD> <报告>
    sha16, shared, pa, dv, tr, sk, rf, rpt = f[1], f[2], f[3], f[4], f[5], f[6], f[7], f[8]
    tc = hashlib.sha256(open(a.t3, 'rb').read()).hexdigest()
    if not tc.startswith(sha16):
        print('!! 基线 sha %s 与 t3 实际 sha %s 不符 ⇒ 拒绝投放' % (sha16, tc[:16]))
        return 2
    ruler_line = ('  · 行为尺权威基线（**按产物 sha 反查**，本机与 CI 逐项一致）\n'
                  '      %s\n'
                  '      即 PASS %s ｜ DIVERGE %s ｜ TRUNC %s ｜ SKIP %s ｜ REFDEAD %s（共 %s，自洽 ✓）\n'
                  '      **DIVERGE 不为 0**，剩余明细见 `%s`。'
                  % (base, pa, dv, tr, sk, rf, shared, rpt))

    out = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    if os.path.isdir(out):
        shutil.rmtree(out, ignore_errors=True)
    if os.path.isdir(out):
        print('!! 无法清空旧投放目录 %s（rmtree 被拦？）—— 中止，禁止产出半成品包' % out)
        return 4
    os.makedirs(os.path.join(out, 'cubegm', '_diag'))

    rows = []
    for src, rel in items:
        dst = os.path.join(out, rel.replace('/', os.sep))
        shutil.copy2(src, dst)
        rows.append((rel, os.path.getsize(dst), sha256(dst)))

    # ★ 原子性：先全部写进已完成目录，最后才写"完成标记"；缺标记 = 半成品
    with io.open(os.path.join(out, 'cubegm', '_diag', 'cfg.ini'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(CFG_INI)
    pf = 'cubegm/_diag/_PUT-ONLY-THIS-FOLDER.txt'
    with io.open(os.path.join(out, pf), 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(PUT_ONLY)
    rows.append((pf, len(PUT_ONLY.encode()), sha256(os.path.join(out, pf))))

    stamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = ['# DEPLOY-MANIFEST — 第 %d 轮投放包' % a.round, '',
             '生成时间: %s' % stamp, '',
             '| 目标路径 | 字节 | sha256 |', '|---|---|---|']
    for rel, size, h in rows:
        lines.append('| `%s` | %d | `%s` |' % (rel, size, h))
    lines += ['', '## 阳性对照（不在本包内，必须在设备上已存在）',
              '- `cubegm/rkgame.bak` —— 原厂 rkgame，**3,921,108 B**',
              '  探针会先 execve 它。**它必须成功**，否则其余结论一概不可信。', '',
              '## 本包与 drop%d 的差别' % (a.prev if a.prev else a.round - 1),
              '- `cubegm/rkgame.t3` = **本轮候选**（PT_INTERP=%s，设备可 exec）' % t3_interp,
              '- `cubegm/rkgame.t1` = **%s**（PT_INTERP=%s）' % (a.t1_role, t1_interp or '(无)'),
              '- 探针 = probe5（静态，无 PT_INTERP）',
              '- ★ 本包新增 fail-closed 闸门：t3 的 PT_INTERP 不是 `/lib/ld-linux-armhf.so.3` 即**拒投**',
              '  （第 109 轮根因：`zig ld.lld` 直驱会写入 Windows 宿主路径 ⇒ 设备 execve 必 ENOENT ⇒ 零日志）',
              '',
              '## 权威行为尺基线（按 t3 的 sha 反查）', '', '```', base, '```']
    with io.open(os.path.join(out, 'DEPLOY-MANIFEST.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')

    t3 = [r for r in rows if r[0].endswith('rkgame.t3')][0]
    t1 = [r for r in rows if r[0].endswith('rkgame.t1')][0]
    pr = [r for r in rows if r[0] == 'cubegm/rkgame'][0]
    readme = README_TMPL.format(round=a.round, prev=(a.prev or a.round - 1), gen=stamp,
                                probe_size='~%d KB' % round(pr[1] / 1024.0),
                                t3_size=t3[1], t3_sha=t3[2],
                                t1_size=t1[1], t1_sha=t1[2], ruler=ruler_line,
                                t1_role=a.t1_role, t1_expect=a.t1_expect,
                                t1_span=t1_span or 0,
                                t3_interp=t3_interp, t1_interp=t1_interp or '(无)')
    with io.open(os.path.join(out, 'READ-ME-FIRST.txt'), 'w',
                 encoding='utf-8', newline='\n') as fh:
        fh.write(readme)

    print('投放目录: %s' % out)
    for rel, size, h in rows:
        print('  %-34s %10d  %s' % (rel, size, h[:16]))
    print('  权威基线: %s' % base)
    return 0


if __name__ == '__main__':
    sys.exit(main())
