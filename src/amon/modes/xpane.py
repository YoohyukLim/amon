from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ..constants import SCOPE_ALL
from ..sessions import discovery as session_discovery
from ..sessions.resolve import encode_session_spec


def _self_command() -> str:
    argv0 = Path(sys.argv[0])
    if argv0.exists() and os.access(argv0, os.X_OK):
        return shlex.quote(str(argv0.resolve()))
    return f"{shlex.quote(sys.executable)} -m amon"


def run_mode_b(
    idle_threshold: float,
    codex_all: bool,
    color: str = "always",
    scope: str = SCOPE_ALL,
    cwd: Optional[str] = None,
    inline_only: bool = False,
    *,
    output=None,
    error=None,
) -> int:
    err = error or sys.stderr
    xpanes = shutil.which("xpanes")
    if not xpanes:
        print("amon: xpanes is required for multi-session mode", file=err)
        return 3

    sessions = session_discovery.discover_active_sessions(
        codex_all=codex_all,
        scope=scope,
        cwd=cwd,
        inline_only=inline_only,
    )
    if not sessions:
        kind = "inline agent" if inline_only else "agent"
        print(f"amon: no active {kind} sessions found", file=err)
        return 0

    specs = [encode_session_spec(session) for session in sessions]
    script = _self_command()
    template = (
        f"printf '\\033]2;%s\\033\\\\' \"$({script} --session-title {{}})\"; "
        f"{script} --session-spec {{}} --idle-threshold {idle_threshold:g} "
        f"--color={color}"
    )
    proc = subprocess.run([xpanes, "-t", "-c", template, *specs], check=False)
    return proc.returncode
