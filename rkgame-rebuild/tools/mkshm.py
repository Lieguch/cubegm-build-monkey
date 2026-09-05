#!/usr/bin/env python3
"""Create a SysV shm segment to simulate icube launcher's shm behavior.

Used by CI test-emu stage to verify hb_detect_icube_shm() finds the
segment. Runs on the host (amd64), not under qemu.

The script creates a 4096-byte shm segment via shmget(IPC_PRIVATE,...)
and attaches to it via shmat to keep it alive. When the script exits,
the attachment is released but the segment remains in the system's IPC
namespace (visible to other processes via shmctl IPC_STAT) until
shmctl(IPC_RMID) is called — which nobody does in this test.

Prints SHM_CREATED / SHM_ATTACHED markers so the CI script can verify
the setup succeeded.
"""
import ctypes
import sys

LIBC = ctypes.CDLL(None)
IPC_PRIVATE = 0
SHM_R = 0o600

shmid = LIBC.shmget(IPC_PRIVATE, 4096, SHM_R | 0o600)
if shmid < 0:
    sys.exit('shmget failed: errno=%d' % ctypes.get_errno())

print('SHM_CREATED shmid=%d' % shmid)

ptr = LIBC.shmat(shmid, None, 0)
if ptr == -1:
    sys.exit('shmat failed: errno=%d' % ctypes.get_errno())

print('SHM_ATTACHED ptr=%d' % ptr)
