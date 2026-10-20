#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_mirror —— 把本项目同步到「镜像远端」（CNB / AC Git），一行命令。

为什么存在
----------
手工镜像必然漂移。所以这里**复用 `push_1to1.py --list-only` 的同一份文件清单**，
绝不另写挑选规则（历史上"静默漏推 / 多发"的根源就是两套规则并存）。

平台分工（用户口径：cnb 托管 + cnb 云开发 + github 构建）
----------------------------------------------------------
| remote  | 仓库                                    | 用途 |
|---------|-----------------------------------------|------|
| `cnb`   | cnb.cool/lieguch/cubeGM                 | **主托管 + 云开发**（qemu 环境在此） |
| `acgit` | git.acwing.com/lieguch/cubegm-rkgame    | 归档镜像（实例无 Runner，只托管不构建） |

★ 构建与门禁**始终**由上游 GitHub Actions（`Lieguch/cubegm-build-monkey`）承担。

凭据
----
* `cnb`  ：走 git 凭据助手 `credential.https://cnb.cool.helper = cnb git-credential`
           （CNB CLI 已登录，token 存于 `~/.cnb/token`），URL 用明文即可。
* `acgit`：走环境变量 `ACGIT_TOKEN`（project access token，注入 URL）。

用法
----
    python tools/sync_mirror.py --remote cnb --dry-run      # 只列差异
    python tools/sync_mirror.py --remote cnb                # 同步并推送
    ACGIT_TOKEN=<...> python tools/sync_mirror.py --remote acgit

退出码：0=完成（或无差异） / 1=推送失败 / 11=前置不可用
"""
import argparse
import glob
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LF_EXT = ('.sh', '.yml', '.S', '.ld')
# 必须在仓库里带可执行位的文件（CI 会 exec 它；Windows 无 exec 位 ⇒ 走 index）
MODE755 = {'1to1/golden/factory.rkgame.bin'}

REMOTES = {
    'cnb': dict(
        host='cnb.cool',
        project='lieguch/cubeGM',
        mirror=os.environ.get('CNB_MIRROR', 'D:/output/cnb-cubeGM'),
        token_env=None,          # 环境变量（可选，CNB_TOKEN 也可）
        token_file='~/.cnb/token',   # ★ R214：直接读 CNB CLI 落盘的 access_token
        user='cnb',                  # token 作为 password 时的 userinfo 用户名
        url_style='plain',
    ),
    'acgit': dict(
        host='git.acwing.com',
        project='lieguch/cubegm-rkgame',
        mirror=os.environ.get('ACGIT_MIRROR', 'D:/output/acgit-rkgame'),
        token_env='ACGIT_TOKEN',
        url_style='oauth2',
    ),
}

def _read_token_file(path):
    """从 CNB CLI 的 token 文件读 `access_token`（不经过任何 credential helper）。

    ★★ 2026-10-20（R214）根因修复 —— 回答「为什么总弹窗要用户名密码」：

      弹窗**不是**因为没密钥，而是 **Git Credential Manager** 弹的：
        · `credential.https://cnb.cool.provider = generic`
          ⇒ GCM 的 `generic` provider 在 helper 链取不到凭据时**弹 GUI 对话框**；
        · 而 helper 链本身是坏的：
          `credential.helper = cnb git-credential`（全局，**少了 `!` 前缀**）
          ⇒ git 把它当成 helper 名，去找 `git-credential-cnb` 子命令
          ⇒ 实测报 `git: 'credential-cnb' is not a git command`；
        · 唯一正确的那条 `credential.https://cnb.cool.helper = !cnb git-credential`
          又因为本脚本原先的 PATH 拼接（MSYS `:` 混进 Windows `;`）找不到 `cnb` 可执行文件。

      但 CNB CLI **早就把长期 access_token 落盘了**（`~/.cnb/token` 的
      `auths["cnb.cool"]["access_token"]`，形如 `cnb_at_...`）。
      ⇒ 直接读它、拼进 URL 的 userinfo，**完全绕开 helper**：不弹窗、不依赖 PATH、
        不依赖 helper 配置，也不会受 GCM provider 影响。
    """
    import json
    try:
        with open(os.path.expanduser(path), encoding='utf-8') as fh:
            d = json.load(fh)
        tok = ((d.get('auths') or {}).get('cnb.cool') or {}).get('access_token', '')
        return (tok or '').strip()
    except Exception:
        return ''


def _winpath(v):
    """把 PATH 值归一化成 **Windows 形式**（`;` 分隔、`/c/...` -> `C:\\...`）。

    ★★ 2026-10-20（R214）根因修复 —— CNB push 长期 401/`Repository Not Found` 的真因：

      本脚本常从 **Git Bash** 启动。在 MSYS 里 `os.environ['PATH']` 是 **MSYS 形式**：
      `;` 不是分隔符、盘符写成 `/c/Users/...`。原实现是

          ENV['PATH'] = ';'.join(GITDIRS + [ENV.get('PATH', '')])

      于是拼出 `C:/.../usr/bin;C:/.../bin;C:/.../mingw64/bin;/c/Users/...:/usr/bin:...`
      ⇒ Windows 只认 `;`，**后面整段 MSYS PATH 变成"一个目录"** ⇒ `cnb`（凭据助手
      `!cnb git-credential`）找不到 ⇒ `git credential fill` **挂起 60s 超时**
      ⇒ 匿名推送 ⇒ CNB 对未授权私有仓返回 `remote: Repository Not Found.`
      （不是 403 —— 这是 CNB 的反枚举行为，极易被误读成"仓库没了/权限变了"）。

      实测对照（同一台机、同一份 token）：
        · `printf 'protocol=https\\nhost=cnb.cool\\n\\n' | cnb git-credential get`
          ⇒ **立刻返回** `username=cnb` + `password=cnb_at_...` ⇒ helper 本身是好的；
        · `sync_mirror.py` 内部 `git credential fill` ⇒ **60s 超时**。
      ⇒ 差别只在 PATH 形态，不在凭据/仓库/网络。

    另修一处硬编：`GITDIRS` 原写死 `PortableGit/versions/1.2.0`，而本机实际是 `1.3.0`
    ⇒ 那三个目录**根本不存在**，等于完全没有加 git 目录。
    """
    segs = []
    for chunk in (v or '').split(';'):
        if not chunk:
            continue
        if re.match(r'^[A-Za-z]:[\\/]', chunk):
            segs.append(chunk)          # 已是 Windows 盘符形式，不要再按 ':' 切
        else:
            segs.extend(x for x in chunk.split(':') if x)
    out = []
    for p in segs:
        p = p.strip()
        if not p:
            continue
        m = re.match(r'^/([A-Za-z])(/.*)?$', p)
        if m:
            p = m.group(1).upper() + ':' + (m.group(2) or '/').replace('/', '\\')
        out.append(p)
    return os.pathsep.join(out)


# ★ 版本号**动态发现**（原为硬编 `1.2.0`，本机实际 `1.3.0` ⇒ 三个目录都不存在、静默失效）。
_PG = sorted(glob.glob('C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/*'))
GITDIRS = []
if _PG:
    _pglast = _PG[-1]
    GITDIRS = [os.path.join(_pglast, 'usr', 'bin'),
               os.path.join(_pglast, 'bin'),
               os.path.join(_pglast, 'mingw64', 'bin')]
ENV = dict(os.environ)
ENV['PATH'] = os.pathsep.join(GITDIRS + [_winpath(ENV.get('PATH', ''))])
ENV['GIT_TERMINAL_PROMPT'] = '0'
ENV['GIT_ASKPASS'] = 'echo'


def _basic_auth_header(cred_url):
    """把 `https://user:token@host/...` 变成 `Authorization: Basic ...` 的头值。"""
    m = re.match(r'^https://([^:/@]+):([^@]+)@', cred_url or '')
    if not m:
        return None
    import base64
    raw = ('%s:%s' % (m.group(1), m.group(2))).encode('utf-8')
    return 'Authorization: Basic ' + base64.b64encode(raw).decode('ascii')


def git(args, cred=None, cwd=None, timeout=900, quiet=False, secrets=()):
    """★ 2026-10-20（R214）凭据注入方式修复（这是"弹窗"与技术性失败的第二层根因）：

      原实现 `a = ['git', a[1], cred] + a[2:]` 把带 token 的 URL **插在子命令后第一个参数位**。
      这只对 `git clone <url> <dir>` 成立；对它自己后面用的
        `git fetch <url> origin +refs/...`  ⇒ `origin` 被当成 refspec ⇒
          实测 `fatal: couldn't find remote ref origin`
        `git push  <url> origin HEAD:main`  ⇒ 同样错位
      都不成立。

      现在按子命令分流：
        · `clone`：URL 放参数位（一次性，随后 `remote set-url` 会换回明文）；
        · 其余  ：**URL 保持明文**（remote 里不落 token），认证走
          `-c http.extraHeader='Authorization: Basic <b64>'`，
          并同时 `-c credential.helper=` **清空 helper 链**
          ⇒ 既不调用坏掉的 `cnb git-credential`，也不触发 GCM 的 generic 弹窗。
    """
    a = ['git']
    hdr = _basic_auth_header(cred) if cred else None
    if cred and args and args[0] == 'clone':
        a += ['-c', 'credential.helper=', args[0], cred] + list(args[1:])
    else:
        a += ['-c', 'credential.helper=']
        if hdr:
            a += ['-c', 'http.extraHeader=' + hdr]
        a += list(args)
    r = subprocess.run(a, capture_output=True, env=ENV, timeout=timeout, cwd=cwd)
    out = (r.stdout + r.stderr).decode('utf-8', 'replace')
    for s in secrets:
        if s:
            out = out.replace(s, '***')
    if not quiet:
        for l in out.split('\n'):
            if l.strip():
                print('    ' + l[:158])
    return r.returncode, out


def file_list():
    """取清单 —— **唯一真源是 `tools/filelist.py`（不再 shell 调push_1to1.py）**。

    ★★ 2026-10-03（第 121 轮，判据 FILELIST-TOOLCHAIN.md F5）**根治循环依赖**：
       原来这里 `subprocess` 调 `push_1to1.py --list-only`，
       而 `push_1to1.py` 因 `EXCLUDE={'tools/push_1to1.py'}`（自身含 token）**永不入库**
       ⇒ **在云工作区必然失败**（实测 `can't open file .../push_1to1.py`）
       ⇒ 「本地改了 → 云上看不到」，上一轮 `default_core_list.c` 就这样差点漏掉。
       现在直接 `import filelist`（该文件**不含 token**⇒ 可入库可上云）。
    ★ 规则仍只写一处：`push_1to1.py`（GitHub）与本文件（CNB）**共同 import 它**。
    """
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    try:
        import filelist
    except ImportError as e:
        print('  ★ 取不到清单模块 tools/filelist.py：%s' % e)
        print('    （它必须入库才能在云端工作；若刚新增，先同步一次）')
        return None
    _k = filelist.kept()
    print('  FILELIST\t%d\t(跳过构建产物/备份 %d)'
          % (len(_k), len(filelist.FILES) - len(_k)))
    return [(a, b) for a, b in _k]


def detect_catastrophic_shrink(numstat_text, allow_shrink=False):
    """纯函数：`git diff --cached --numstat` 文本 -> `(bad, warn)`。

    * `bad`  追加型文件（PROJECT-MEMORY.md / .workbuddy/memory/*）**少了行** ⇒ 必须拦。
    * `warn` 其他文件缩水 > 30% 且原文件 >= 200 行 ⇒ 醒目告警（不拦，但必须可见）。

    ★ 为什么要有它（真实事故，见 PROJECT-MEMORY SS0.38）：
      1to1/PROJECT-MEMORY.md 在一次同步里被写成**约 35 轮前的旧版本**
      （+1 / -2424，3211 -> 788 行，SS0.30-SS0.36 全丢），而且**已经推到 CNB 与 GitHub**。
      旧代码只把差异**打印**成一行（9 个文件混在一起），**没有任何阈值** ⇒ 没人会去数。
      PROJECT-MEMORY.md 的政策是**只增不删** ⇒ 变短必然是事故，必须 fail-closed。
    """
    bad, warn = [], []
    for ln in (numstat_text or '').split(chr(10)):
        parts = ln.split(chr(9))
        if len(parts) != 3:
            continue
        try:
            add_n, del_n = int(parts[0]), int(parts[1])
        except ValueError:              # 二进制文件是 '-'/'-'
            continue
        path = parts[2]
        base = os.path.basename(path)
        append_only = (base == 'PROJECT-MEMORY.md') or ('.workbuddy/memory/' in path)
        # ★ 阈值必须**精化**（否则会把正当编辑判成事故）：
        #   真实历史对照（同一文件 PROJECT-MEMORY.md）：
        #     d81365e  +1400/-1   ⇒ 只是**头部指针**那一行被替换 ⇒ **不得拦**
        #     48153e6  +1/-2424   ⇒ 灾难性回退（3200 行 -> 788 行）⇒ **必须拦**
        #   判据：`del_n > 10 且 del_n >= add_n`（删的比加的多才算回退）。
        if append_only and del_n > 10 and del_n >= add_n:
            bad.append((path, add_n, del_n))
        elif del_n > 0 and (add_n + del_n) >= 200 and del_n > 0.3 * (add_n + del_n):
            warn.append((path, add_n, del_n))
    if allow_shrink:
        return [], warn
    return bad, warn


# 门禁必须能"分辨"，不只是"能跑"：锚点含**真实事故数字**。
SHRINK_SELFTEST_CASES = (
    ('真实事故：PROJECT-MEMORY.md +1/-2424 ⇒ 必须拦',
     '1' + chr(9) + '2424' + chr(9) + '1to1/PROJECT-MEMORY.md', 1, 0),
    ('正例：正常追加（+600/-0）⇒ 不得拦',
     '600' + chr(9) + '0' + chr(9) + '1to1/PROJECT-MEMORY.md', 0, 0),
    ('★ 真实历史 d81365e +1400/-1（头部指针行被替换）⇒ **不得拦**（防假阳）',
     '1400' + chr(9) + '1' + chr(9) + '1to1/PROJECT-MEMORY.md', 0, 0),
    ('反例：小范围替换（+20/-15）⇒ 不算回退，不得拦',
     '20' + chr(9) + '15' + chr(9) + '1to1/PROJECT-MEMORY.md', 0, 0),
    ('反例：删得比加得多（+5/-30）⇒ 必须拦',
     '5' + chr(9) + '30' + chr(9) + '1to1/PROJECT-MEMORY.md', 1, 0),
    ('反例：事故与正常追加混在同一批 ⇒ 仍必须准确拦 1 条',
     '1' + chr(9) + '2424' + chr(9) + '1to1/PROJECT-MEMORY.md' + chr(10)
     + '600' + chr(9) + '0' + chr(9) + '1to1/tools/diff_exec.py', 1, 0),
    ('正例：其它文件小幅缩水（+50/-5）⇒ 不拦不警',
     '50' + chr(9) + '5' + chr(9) + '1to1/tools/foo.py', 0, 0),
    ('正例：其它大文件缩水 40%（+120/-80）⇒ 只告警不拦',
     '120' + chr(9) + '80' + chr(9) + '1to1/tools/big.py', 0, 1),
    ('反例：二进制文件（-/-）不得被当文本判',
     '-' + chr(9) + '-' + chr(9) + '1to1/golden/factory.rkgame.bin', 0, 0),
    ('正例：记忆日志同样按追加型对待',
     '0' + chr(9) + '30' + chr(9) + '.workbuddy/memory/2026-09-29.md', 1, 0),
)


def shrink_selftest():
    chk = []
    for tag, text, want_bad, want_warn in SHRINK_SELFTEST_CASES:
        bad, warn = detect_catastrophic_shrink(text)
        chk.append((tag, (len(bad), len(warn)), (want_bad, want_warn)))
    bad, _ = detect_catastrophic_shrink('1' + chr(9) + '2424' + chr(9)
                                       + '1to1/PROJECT-MEMORY.md', allow_shrink=True)
    chk.append(('正例：--allow-shrink 后不拦（"删东西"必须是有意识动作）', len(bad), 0))
    bad_n = 0
    for tag, got, want in chk:
        ok = (got == want)
        bad_n += 0 if ok else 1
        print('   %s  %-62s got=%s' % ('v' if ok else 'x', tag[:62], got))
    print('   合计 %d 条，失败 %d 条' % (len(chk), bad_n))
    return 2 if bad_n else 0


def main():
    if '--self-test' in sys.argv[1:]:
        return shrink_selftest()
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote', choices=sorted(REMOTES), default='cnb')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--allow-shrink', action='store_true',
                    help='显式允许「追加型文件变短」（默认 fail-closed；'
                         'PROJECT-MEMORY.md 政策是只增不删，缩水一般是事故）')
    a = ap.parse_args()

    cfg = REMOTES[a.remote]
    HOST, PROJECT = cfg['host'], cfg['project']
    MIRROR = cfg['mirror']
    PLAIN = 'https://%s/%s.git' % (HOST, PROJECT)
    secrets = []

    print('== [0/5] 远端 = %s  (%s)' % (a.remote, PLAIN))
    # ★ R214：**先试 token**（环境变量 → token 文件），拿到就直接拼 userinfo URL，
    #   完全不走 credential helper ⇒ 不会弹窗、不会 60s 超时。
    tok = ''
    tok_src = ''
    if cfg.get('token_env'):
        tok = os.environ.get(cfg['token_env'], '')
        tok_src = cfg['token_env']
    if not tok and cfg.get('token_file'):
        tok = _read_token_file(cfg['token_file'])
        tok_src = cfg['token_file']
    if tok:
        CRED = 'https://%s:%s@%s/%s.git' % (cfg.get('user', 'oauth2'), tok, HOST, PROJECT)
        secrets.append(tok)
        print('    凭据: 直接使用 token（来源 %s）⇒ 绕过 credential helper，不会弹窗' % tok_src)
    elif cfg['url_style'] == 'oauth2':
        print('  ★ 缺 %s —— 前置不可用（不接受"没有密钥也能推"）' % cfg['token_env'])
        return 11
    else:
        # 明文 URL + 凭据助手。先验证助手在位（诚实失败，不猜）。
        rc, out = git(['config', '--get', 'credential.https://%s.helper' % HOST],
                      cwd=ROOT, quiet=True)
        if rc != 0 or 'cnb' not in out:
            print('  ★ 未配置凭据助手 credential.https://%s.helper（应为 cnb git-credential）' % HOST)
            print('     修：git config --global credential.https://%s.helper "cnb git-credential"' % HOST)
            return 11
        print('    凭据助手: cnb git-credential ✓')
        CRED = None

    print('== [1/5] 取文件清单 ==')
    items = file_list()
    if not items:
        return 11

    print('== [2/5] 准备镜像仓 %s ==' % MIRROR)
    if not os.path.isdir(os.path.join(MIRROR, '.git')):
        if os.path.isdir(MIRROR):
            import shutil
            shutil.rmtree(MIRROR)
        rc, _ = git(['clone', PLAIN, MIRROR], cred=CRED,
                    cwd=os.path.dirname(MIRROR) or '.', secrets=secrets)
        if rc != 0:
            return 11
    git(['remote', 'set-url', 'origin', PLAIN], cwd=MIRROR, quiet=True)
    git(['config', 'user.email', 'agent@local'], cwd=MIRROR, quiet=True)
    git(['config', 'user.name', 'cgm-sync'], cwd=MIRROR, quiet=True)
    # ★ 必须显式给远端名 + 具体 refspec。`git fetch <refspec>`（只给一个参数）会被 git
    #   按 `git fetch [<repository> [<refspec>...]]` 语法当成**仓库名**
    #   ⇒ 报 "... does not appear to be a git repository"。
    rc, _ = git(['fetch', 'origin', '+refs/heads/main:refs/remotes/origin/main'], cred=CRED,
                cwd=MIRROR, secrets=secrets)
    if rc != 0:
        print('  ★ fetch 失败（凭据/网络）—— 中止，不做半吊子推送')
        return 11

    print('== [3/5] 落地文件（LF 修正 + 按清单）==')
    n_copy = n_lf = n_miss = 0
    for rel, remote in items:
        src = os.path.join(ROOT, rel)
        if not os.path.exists(src):
            print('  ★ 源缺失: %s' % rel)
            n_miss += 1
            continue
        dst = os.path.join(MIRROR, remote)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        data = open(src, 'rb').read()
        if rel.endswith(LF_EXT) and b'\r\n' in data:
            data = data.replace(b'\r\n', b'\n')
            n_lf += 1
        with open(dst, 'wb') as fh:
            fh.write(data)
        n_copy += 1
    print('  落地 %d 个（LF 修正 %d，源缺失 %d）' % (n_copy, n_lf, n_miss))

    print('== [4/5] 计算差异（相对 origin/main）==')
    git(['reset', '--soft', 'origin/main'], cwd=MIRROR, quiet=True)
    git(['add', '-A'], cwd=MIRROR, quiet=True)
    rc, out = git(['diff', '--cached', '--name-status'], cwd=MIRROR, quiet=True)
    changed = [l for l in out.split('\n') if l.strip()]
    nonadd = [l for l in changed if not l.startswith('A\t')]
    print('  与 origin/main 差异：%d 项（其中非"纯新增" %d 项 —— 这几项最需要盯）'
          % (len(changed), len(nonadd)))
    for f in changed[:14]:
        print('    %s' % f[:140])
    if len(changed) > 14:
        print('    ...（另 %d 项）' % (len(changed) - 14))
    # 可执行位（index 层，绕开 Windows 无 exec 位）
    for p in MODE755:
        if os.path.exists(os.path.join(MIRROR, p)):
            git(['update-index', '--chmod=+x', p], cwd=MIRROR, quiet=True)

    # 2026-09-30 「灾难性缩水」门禁（真实事故换来的，见 PROJECT-MEMORY SS0.38）
    print('== [4b/5] 灾难性缩水门禁 ==')
    _rc, _ns = git(['diff', '--cached', '--numstat'], cwd=MIRROR, quiet=True)
    _bad, _warn = detect_catastrophic_shrink(_ns or '',
                                            allow_shrink=getattr(a, 'allow_shrink', False))
    for _p, _an, _dn in _warn:
        print('  [warn] 缩水告警：%s  +%d / -%d（大于 30%%）—— 请确认是有意删改'
              % (_p, _an, _dn))
    if _bad:
        print('  ** 拒绝推送：追加型文件相对 origin/main 变短了 ——')
        for _p, _an, _dn in _bad:
            print('       %s  +%d / -%d' % (_p, _an, _dn))
        print('     为什么：PROJECT-MEMORY.md 的政策是只增不删，变短必然是事故')
        print('       （2026-09-30 真实事故：3211 行 -> 788 行，SS0.30-SS0.36 全丢并已推送）。')
        print('     处置：(1) 先确认本地文件是否被旧副本覆盖（与远端比对行数 / 小节）；')
        print('           (2) 确属有意删改，才加 --allow-shrink 重跑。')
        return 13

    if not changed:
        print('  无差异，无需推送。')
        return 0
    if a.dry_run:
        print('  --dry-run：不提交、不推送。')
        return 0

    print('== [5/5] 提交并推送 ==')
    rc, _ = git(['commit', '-m',
                 'sync: 从上游镜像（tools/sync_mirror.py --remote %s，清单复用 push_1to1.py）' % a.remote],
                cwd=MIRROR)
    if rc != 0:
        print('  ★ commit 失败')
        return 1
    # ★ push 也必须显式给远端名。`git push HEAD:main`（只给一个非选项参数）会被 git
    #   按 `git push [<repository> [<refspec>...]]` 当成**仓库名** ⇒ 拼成 SSH 主机 "head"
    #   ⇒ 报 `ssh: Could not resolve hostname head`（极易被误读成"网络/权限"问题）。
    rc, _ = git(['push', 'origin', 'HEAD:main'], cred=CRED, cwd=MIRROR, secrets=secrets)
    if rc != 0:
        print('  ★ push 失败')
        # ★ 失败可见性诊断（2026-10-06 第 153 轮）：这里失败过两次（Repository Not Found），
        #   两次都浪费了一整轮去追，第二次定位到「helper 在场但凭据没送达」是可能的瞬时态。
        #   「推送失败」背后至少有四类互斥成因：凭据没取到 / helper 未装配 / 服务端 404 /
        #   网络层。每种不一样，下面把能测的**当场测掉**并打印，把人力留给真正的根因。
        probe = [p for p in os.environ.get('PATH', '').split(os.pathsep) if p]
        probe = [p for p in probe
                 if 'PortableGit' in p and os.path.isdir(p)]
        pe = dict(os.environ)
        pe['PATH'] = os.pathsep.join(GITDIRS + [_winpath(pe.get('PATH', ''))])
        try:
            cr = subprocess.run(
                ['git', 'credential', 'fill'],
                input=b'protocol=https\nhost=cnb.cool\n\n',
                capture_output=True, env=pe, timeout=60, cwd=MIRROR)
            got = (cr.stdout).decode('utf-8', 'replace')
            has_pw = 'password=' in got
            print('    [诊断] helper 链是否可取凭据：%s（rc=%d）'
                  % ('可取到' if has_pw else '取不到（失败点=凭据链路，不是仓库/网络）', cr.returncode))
        except Exception as e:                                # noqa: BLE001
            print('    [诊断] helper 链探测异常：%s' % e)
        try:
            import urllib.request, ssl
            with urllib.request.urlopen(
                    'https://%s/%s.git/info/refs?service=git-receive-pack' % (HOST, PROJECT),
                    timeout=20,
                    context=ssl._create_unverified_context()) as rsp:
                pass
            print('    [诊断] 服务端 refs 端点可达（说明仓库存在、TLS 通）')
        except urllib.error.HTTPError as e:
            print('    [诊断] 服务端 refs 端点 HTTP %d（无凭据访问 → 401 属正常）' % e.code)
        except Exception as e:                                # noqa: BLE001
            print('    [诊断] 服务端 refs 端点不可达：%s' % e)
        return 1
    print('  ✓ 同步完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
