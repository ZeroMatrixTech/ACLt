# SPDX-License-Identifier: Apache-2.0
"""Fail-closed append-only per-attempt markers on a trusted local filesystem."""
import os
from pathlib import Path
from common import Rejected,HostFault

def sync_directory(directory):
    fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)

def durable_new(path,data):
    path=Path(path)
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    except FileExistsError as exc:raise Rejected('local launch slot already used') from exc
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        sync_directory(path.parent)
    except OSError as exc:raise HostFault('durable write failed; slot is not reusable') from exc

def state_directory(path):
    path=Path(path)
    if path.is_symlink():raise HostFault('symlink state directory')
    if not path.exists():
        path.mkdir(mode=0o700,parents=False,exist_ok=False);sync_directory(path.parent)
    if not path.is_dir():raise HostFault('invalid state directory')
    return path
