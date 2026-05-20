from __future__ import annotations

from typing import Optional

from ..agents.registry import adapters_for_command, candidate_process_patterns
from ..constants import SCOPE_ALL
from ..host import _is_path_at_or_under, candidate_pids, process_command, process_cwd
from .resolve import _scope_root, _session_record


def discover_active_sessions(
    codex_all: bool = False,
    scope: str = SCOPE_ALL,
    cwd: Optional[str] = None,
    inline_only: bool = False,
) -> list[dict]:
    root = _scope_root(scope, cwd)
    sessions: list[dict] = []
    for pid in candidate_pids(candidate_process_patterns()):
        cmdline = process_command(pid)
        adapters = adapters_for_command(cmdline)
        if not adapters:
            continue

        current_cwd = process_cwd(pid)
        if root is not None:
            if not current_cwd or not _is_path_at_or_under(current_cwd, root):
                continue

        for adapter in adapters[:1]:
            inline = adapter.is_inline_command(cmdline)
            if inline_only and not inline:
                continue
            include_all = codex_all if adapter.name == "codex" else False
            for path in adapter.resolve_session_paths(
                pid,
                cmdline=cmdline,
                cwd=current_cwd,
                include_all=include_all,
            ):
                sessions.append(
                    _session_record(adapter.name, pid, path, current_cwd, cmdline, inline)
                )
    return sessions
