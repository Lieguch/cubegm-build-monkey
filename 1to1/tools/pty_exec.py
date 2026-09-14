#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pty_exec.py — 在 pty 下运行命令，让被测程序的 stdout 被判为 TTY。

【为什么需要】
glibc 在 stdout 是**管道/文件**时用**全缓冲**（4 KB）。若被测程序 abort() 或被信号
杀死（SIGSEGV / SIGILL / SIGABRT），缓冲区**不 flush** ⇒ 崩溃现场之前的全部 printf 丢失。
实测：工厂 rkgame 在 qemu 下崩溃时 stdout 采集结果是 **0 字节**，连 main() 的第一句
`puts("rkgame v1.42")` 都没留下 —— 也就是说"没有输出"这个观测本身是**假象**，
它会直接把行为差分（behav_diff）的可观测性判成"空洞"。

pty 下 stdout 是 TTY ⇒ 行缓冲 ⇒ 崩溃前的内容都还在。

【与 script(1) 的区别】
`script(1)` 把 **stdin/stdout/stderr 全挂到 pty**，于是 qemu 自身的报错
（`qemu: uncaught target signal 11`）会混进 stdout 采集，破坏"guest 输出"的纯净性。
本工具**只把 fd 0/1 挂到 pty，fd 2 保持原样** —— stderr 仍独立可采、可比对。

【用法】
    pty_exec.py [--timeout SEC] <cmd> [args...]

退出码：子进程退出码；被信号杀死为 128+signo（与 shell 一致）；超时为 124。

【平台】
pty/termios/fcntl 是 POSIX 专有。Windows 上自动降级为普通执行（此时 stdout 恢复
全缓冲，仅影响"崩溃现场输出"的可见性，**不影响退出码与 stderr**）。
"""
import os
import sys
import time

TIMEOUT_RC = 124


def _parse(argv):
    """拆出 --timeout，返回 (timeout_seconds_or_None, cmd_list)。"""
    timeout = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--':
            i += 1
            break
        if a == '--timeout':
            if i + 1 >= len(argv):
                sys.stderr.write('pty_exec: --timeout 缺少参数\n')
                return None, None
            timeout = float(argv[i + 1])
            i += 2
            continue
        if a.startswith('--timeout='):
            timeout = float(a.split('=', 1)[1])
            i += 1
            continue
        if a.startswith('--'):
            sys.stderr.write('pty_exec: 未知参数 %s\n' % a)
            return None, None
        break
    cmd = argv[i:]
    if not cmd:
        sys.stderr.write('pty_exec: 缺少命令\n')
        return None, None
    return timeout, cmd


def _run_plain(cmd, timeout):
    """无 pty 可用时的降级路径（Windows 开发机 / 无 termios 环境）。"""
    import subprocess
    try:
        rc = subprocess.run(cmd, timeout=timeout).returncode
        # POSIX 下被信号杀死时 returncode 是**负数**；统一成 shell 语义 128+signo
        return 128 + (-rc) if rc < 0 else rc
    except subprocess.TimeoutExpired:
        return TIMEOUT_RC
    except FileNotFoundError as e:
        sys.stderr.write('pty_exec: %s\n' % e)
        return 127


def _run_pty(cmd, timeout):
    import errno
    import fcntl
    import pty
    import select
    import signal
    import termios

    master, slave = pty.openpty()
    # 关掉 OPOST：否则 pty 会把 "\n" 改写成 "\r\n"，污染逐字节比对。
    # 关掉 ECHO：避免任何回显混入采集。
    try:
        attrs = termios.tcgetattr(slave)
        attrs[1] &= ~termios.OPOST
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(slave, termios.TCSANOW, attrs)
    except Exception:
        pass

    pid = os.fork()
    if pid == 0:                                   # ---- 子进程 ----
        try:
            os.close(master)
            os.setsid()                            # 自成会话/进程组 ⇒ 便于整组收尸
            try:
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            except Exception:
                pass
            os.dup2(slave, 1)                      # ★ 只接管 stdout；stderr 保持原样
            # ★ 也**不接管 stdin**（early 版本这里还 dup2 了 fd0，是错的）：
            #   若 stdin 指向 pty 而父进程从不写入，被测程序一读 stdin 就会**永久阻塞**
            #   （pty 的 master 还开着 ⇒ 不会返回 EOF）⇒ 只能靠超时结束，
            #   于是"双方都超时"被误当成行为一致。stdin 保持调用者原样（CI 里是 /dev/null）。
            if slave > 2:
                os.close(slave)
            os.execvp(cmd[0], cmd)
        except Exception as e:                     # exec 失败
            try:
                sys.stderr.write('pty_exec: exec %s 失败: %s\n' % (cmd[0], e))
            except Exception:
                pass
            os._exit(127)
        os._exit(127)

    # ---- 父进程 ----
    os.close(slave)
    state = {'sig': 0}

    def _forward(signo, _frame):
        state['sig'] = signo
        try:
            os.kill(-pid, signo)                    # 打整组
        except OSError:
            pass

    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        try:
            signal.signal(s, _forward)
        except Exception:
            pass

    deadline = None if timeout is None else time.time() + timeout
    timed_out = False
    chunks = []

    while True:
        remain = None
        if deadline is not None:
            remain = deadline - time.time()
            if remain <= 0:
                timed_out = True
                break
        try:
            r, _, _ = select.select([master], [], [], remain)
        except InterruptedError:
            continue
        except OSError:
            break
        if not r:
            timed_out = True
            break
        try:
            data = os.read(master, 65536)
        except OSError as e:
            if e.errno == errno.EIO:                # 所有 slave 已关闭 ⇒ 子进程结束
                break
            raise
        if not data:
            break
        chunks.append(data)

    if timed_out:
        try:
            os.kill(-pid, signal.SIGTERM)
        except OSError:
            pass

    # 排空剩余输出（最多 1s），确保崩溃现场的最后一句话也能拿到
    drain_end = time.time() + 1.0
    while time.time() < drain_end:
        try:
            r, _, _ = select.select([master], [], [], 0.1)
        except (InterruptedError, OSError):
            break
        if not r:
            break
        try:
            data = os.read(master, 65536)
        except OSError as e:
            if e.errno == errno.EIO:
                break
            break
        if not data:
            break
        chunks.append(data)

    # 收尸（先给 SIGTERM 一点时间，仍不退则 SIGKILL）
    status = None
    for _ in range(40):
        try:
            wpid, st = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            status = 0
            break
        if wpid == pid:
            status = st
            break
        time.sleep(0.05)
    if status is None:
        try:
            os.kill(-pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            _, status = os.waitpid(pid, 0)
        except ChildProcessError:
            status = 0

    try:
        os.close(master)
    except OSError:
        pass

    sys.stdout.buffer.write(b''.join(chunks))
    sys.stdout.buffer.flush()
    sys.stderr.flush()

    if state['sig']:
        return 128 + state['sig']
    if timed_out:
        return TIMEOUT_RC
    if os.WIFSIGNALED(status):
        return 128 + os.WTERMSIG(status)
    return os.WEXITSTATUS(status)


def have_pty():
    try:
        import fcntl  # noqa: F401
        import pty  # noqa: F401
        import termios  # noqa: F401
        return True
    except Exception:
        return False


def main():
    timeout, cmd = _parse(sys.argv[1:])
    if cmd is None:
        return 2
    if have_pty():
        return _run_pty(cmd, timeout)
    return _run_plain(cmd, timeout)


if __name__ == '__main__':
    sys.exit(main())
