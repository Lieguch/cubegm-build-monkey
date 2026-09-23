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
import os
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
        token_env=None,          # 走 git 凭据助手
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

GITDIRS = [
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin',
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin',
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin',
]
ENV = dict(os.environ)
ENV['PATH'] = ';'.join(GITDIRS + [ENV.get('PATH', '')])
ENV['GIT_TERMINAL_PROMPT'] = '0'
ENV['GIT_ASKPASS'] = 'echo'


def git(args, cred=None, cwd=None, timeout=900, quiet=False, secrets=()):
    a = ['git'] + list(args)
    if cred:
        a = ['git', a[1], cred] + a[2:]
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
    """取与 GitHub 同一份清单（复用 push_1to1.py 的选择规则）。"""
    py = sys.executable
    r = subprocess.run([py, os.path.join(ROOT, 'tools', 'push_1to1.py'), '--list-only'],
                       capture_output=True, cwd=ROOT,
                       env={**os.environ, 'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN', 'x')})
    txt = r.stdout.decode('utf-8', 'replace')
    if r.returncode != 0 or 'FILELIST' not in txt:
        print('  ★ 取不到清单：rc=%d' % r.returncode)
        print('    ' + (r.stderr.decode('utf-8', 'replace')[-300:] or txt[-300:]))
        return None
    items, header = [], ''
    for l in txt.split('\n'):
        if l.startswith('FILELIST'):
            header = l
        elif '\t' in l:
            a, b = l.split('\t', 1)
            items.append((a.strip(), b.strip()))
    print('  %s' % header)
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--remote', choices=sorted(REMOTES), default='cnb')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    cfg = REMOTES[a.remote]
    HOST, PROJECT = cfg['host'], cfg['project']
    MIRROR = cfg['mirror']
    PLAIN = 'https://%s/%s.git' % (HOST, PROJECT)
    secrets = []

    print('== [0/5] 远端 = %s  (%s)' % (a.remote, PLAIN))
    if cfg['url_style'] == 'oauth2':
        tok = os.environ.get(cfg['token_env'] or '', '')
        if not tok:
            print('  ★ 缺 %s —— 前置不可用（不接受"没有密钥也能推"）' % cfg['token_env'])
            return 11
        CRED = 'https://oauth2:%s@%s/%s.git' % (tok, HOST, PROJECT)
        secrets.append(tok)
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
        return 1
    print('  ✓ 同步完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
