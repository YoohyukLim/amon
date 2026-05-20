from __future__ import annotations

import os
import shlex
import subprocess
from typing import Optional


def parse_lsof_cwd(output: str) -> Optional[str]:
    for line in output.splitlines():
        parts = line.split(None, 8)
        if len(parts) >= 9 and parts[3] == "cwd":
            return parts[8]
    return None


def _run_lsof(pid: int) -> str:
    proc = subprocess.run(
        ["lsof", "-p", str(pid)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.stdout


def process_cwd(pid: int) -> Optional[str]:
    return parse_lsof_cwd(_run_lsof(pid))


def candidate_pids(patterns: list[str]) -> list[int]:
    pids: list[int] = []
    seen: set[int] = set()
    for pattern in patterns:
        proc = subprocess.run(
            ["pgrep", "-f", pattern],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for line in proc.stdout.splitlines():
            try:
                pid = int(line.strip())
            except ValueError:
                continue
            if pid not in seen:
                pids.append(pid)
                seen.add(pid)
    return pids


def process_command(pid: int) -> str:
    proc = subprocess.run(
        ["ps", "-o", "command=", "-p", str(pid)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.stdout.strip()


def _split_cmdline(cmdline: str) -> list[str]:
    try:
        return shlex.split(cmdline)
    except ValueError:
        return []


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _process_state(pid: Optional[int]) -> str:
    if pid is None:
        return "unknown"
    return "alive" if _pid_alive(pid) else "exited"


def _realpath(path: str) -> str:
    return os.path.realpath(os.path.expanduser(path))


def _is_path_at_or_under(path: str, root: str) -> bool:
    path_real = _realpath(path)
    root_real = _realpath(root)
    try:
        return os.path.commonpath([path_real, root_real]) == root_real
    except ValueError:
        return False
