#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sync_acgit —— 把本项目同步到 AC Git 镜像（git.acwing.com/lieguch/cubegm-rkgame）。

为什么存在
----------
AC Git 是本项目的**镜像 + 归档**目标（GitLab 14.2）。手工镜像容易漂移，
所以这里**复用 `push_1to1.py --list-only` 的同一份文件清单**，绝不另写挑选规则。

前提
----
AC Git 的 **CI 目前无法执行**（2026-09-23 实测：实例无任何 Runner）⇒
本工具只做"代码同步"，构建与门禁仍由上游 GitHub Actions 承担。

用法
----
    ACGIT_TOKEN=<project-access-token> python tools/sync_acgit.py            # 同步并推送
    ACGIT_TOKEN=<...> python tools/sync_acgit.py --dry-run                  # 只列出差异

退出码：0=同步完成(或无可同步) / 1=推送失败 / 11=前置不可用（缺 token / 缺清单）
"""
import argparse
import io
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIRROR = os.environ.get('ACGIT_MIRROR', 'D:/output/acgit-rkgame')
HOST = 'git.acwing.com'
PROJECT = 'lieguch/cubegm-rkgame'
PLAIN = 'https://%s/%s.git' % (HOST, PROJECT)
LF_EXT = ('.sh', '.yml', '.S', '.ld')
# 必须在仓库里带可执行位的文件（CI 会 exec 它；Windows 无 exec 位 ⇒ 走 index）
MODE755 = {'1to1/golden/factory.rkgame.bin'}
GITDIRS = [
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/usr/bin',
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/bin',
    'C:/Users/Administrator/.workbuddy/binaries/PortableGit/versions/1.2.0/mingw64/bin',
]
ENV = dict(os.environ)
ENV['PATH'] = ';'.join(GITDIRS + [ENV.get('PATH', '')])
ENV['GIT_TERMINAL_PROMPT'] = '0'
ENV['GIT_ASKPASS'] = 'echo'


def git(args, cred=None, cwd=MIRROR, timeout=900, quiet=False):
    a = ['git'] + list(args)
    if cred:
        a = ['git', a[1], cred] + a[2:]
    r = subprocess.run(a, capture_output=True, env=ENV, timeout=timeout, cwd=cwd)
    tok = os.environ.get('ACGIT_TOKEN', '')
    out = (r.stdout + r.stderr).decode('utf-8', 'replace').replace(tok, '***')
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
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    TOK = os.environ.get('ACGIT_TOKEN')
    if not TOK:
        print('  ★ 缺 ACGIT_TOKEN —— 前置不可用（不接受"没有密钥也能推"）')
        return 11
    CRED = 'https://oauth2:%s@%s/%s.git' % (TOK, HOST, PROJECT)

    print('== [1/5] 取文件清单 ==')
    items = file_list()
    if not items:
        return 11

    print('== [2/5] 准备镜像仓 %s ==' % MIRROR)
    if not os.path.isdir(os.path.join(MIRROR, '.git')):
        if os.path.isdir(MIRROR):
            import shutil
            shutil.rmtree(MIRROR)
        rc, _ = git(['clone', PLAIN, MIRROR], cred=CRED, cwd=os.path.dirname(MIRROR) or '.')
        if rc != 0:
            return 11
    git(['remote', 'set-url', 'origin', PLAIN], quiet=True)
    git(['config', 'user.email', 'agent@local'], quiet=True)
    git(['config', 'user.name', 'cgm-sync'], quiet=True)
    rc, _ = git(['fetch', '+refs/heads/main:refs/remotes/origin/main'], cred=CRED)
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

    print('== [4/5] 计算差异 ==')
    git(['reset', '--soft', 'origin/main'], quiet=True)
    git(['add', '-A'], quiet=True)
    rc, out = git(['diff', '--cached', '--name-only'], quiet=True)
    changed = [l for l in out.split('\n') if l.strip()]
    print('  与远端 main 的差异：%d 个文件' % len(changed))
    for f in changed[:12]:
        print('    %s' % f)
    if len(changed) > 12:
        print('    ...（另 %d 个）' % (len(changed) - 12))
    # 可执行位（index 层，绕开 Windows 无 exec 位）
    for p in MODE755:
        if os.path.exists(os.path.join(MIRROR, p)):
            git(['update-index', '--chmod=+x', p], quiet=True)

    if not changed:
        print('  无差异，无需推送。')
        return 0
    if a.dry_run:
        print('  --dry-run：不提交、不推送。')
        return 0

    print('== [5/5] 提交并推送 ==')
    rc, _ = git(['commit', '-m', 'sync: 从上游镜像（tools/sync_acgit.py，清单复用 push_1to1.py）'])
    if rc != 0:
        print('  ★ commit 失败')
        return 1
    rc, _ = git(['push', 'HEAD:main'], cred=CRED)
    if rc != 0:
        print('  ★ push 失败')
        return 1
    print('  ✓ 同步完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
