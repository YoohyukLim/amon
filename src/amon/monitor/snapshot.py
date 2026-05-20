from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

from ..host import _process_state
from .tail import _format_event_detail


def snapshot_status(
    session_path: str,
    agent: str,
    sid_short: str,
    idle_threshold: float,
    color: str = "never",
    pid: Optional[int] = None,
    process_state: Optional[str] = None,
    *,
    now_func=None,
) -> tuple[int, str]:
    path = Path(session_path)
    if not path.exists():
        return (1, f"ERROR session path missing: {session_path}")

    last_event = None
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            detail = _format_event_detail(event, agent, color="never")
            if detail:
                last_event = detail

    now = time.time() if now_func is None else now_func()
    idle_seconds = max(0, int(now - path.stat().st_mtime))
    resolved_process_state = process_state or _process_state(pid)
    if resolved_process_state not in {"alive", "exited", "unknown"}:
        resolved_process_state = "unknown"

    if resolved_process_state == "exited":
        status = "exited"
        code = 4
    else:
        status = "working" if idle_seconds < idle_threshold else "idle"
        code = 0 if status == "working" else 2

    clock = time.strftime("%H:%M:%S", time.localtime(now))
    last = last_event or "(no events)"
    process = f"process={resolved_process_state}"
    if pid is not None:
        process = f"{process} pid={pid}"
    return (
        code,
        f"{clock} [{agent}/{sid_short}] status={status} "
        f"idle={idle_seconds}s {process} last={last}",
    )


def run_snapshot(
    session_path: str,
    agent: str,
    sid_short: str,
    idle_threshold: float,
    color: str = "never",
    pid: Optional[int] = None,
    process_state: Optional[str] = None,
    *,
    now_func=None,
    output=None,
    error=None,
) -> int:
    code, line = snapshot_status(
        session_path,
        agent,
        sid_short,
        idle_threshold,
        color=color,
        pid=pid,
        process_state=process_state,
        now_func=now_func,
    )
    stream = (error or sys.stderr) if code == 1 else (output or sys.stdout)
    print(line, file=stream)
    return code
