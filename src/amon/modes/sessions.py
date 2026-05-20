from __future__ import annotations

import curses
import sys
import time
from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_DETAIL_LINES, SCOPE_ALL
from ..monitor.tail import _format_exit_line
from ..sessions.discovery import discover_active_sessions
from ..sessions.resolve import resolve_active_session_record
from ..ui.curses_view import _run_session_detail_tui, _run_sessions_tui
from ..ui.render import render_session_detail_lines, render_session_list_lines
from ..ui.state import SessionDetailState, SessionListState, _single_status_counts, build_session_detail_entry


def run_sessions_mode(
    idle_threshold: float,
    codex_all: bool,
    scope: str = SCOPE_ALL,
    cwd: Optional[str] = None,
    lines: int = DEFAULT_DETAIL_LINES,
    color: str = "auto",
    inline_only: bool = False,
    *,
    output=None,
    error=None,
) -> int:
    stream = output or sys.stdout
    if output is not None or not stream.isatty():
        state = SessionListState(scope=scope, cwd=cwd, inline_only=inline_only)
        state.merge_discovered(
            discover_active_sessions(codex_all=codex_all, scope=scope, cwd=cwd),
            time.monotonic(),
        )
        for line in render_session_list_lines(state):
            print(line, file=stream)
        return 0

    return curses.wrapper(
        lambda stdscr: _run_sessions_tui(
            stdscr,
            codex_all=codex_all,
            scope=scope,
            cwd=cwd,
            line_count=lines,
            color=color,
            inline_only=inline_only,
        )
    )


def run_session_detail(
    entry: SessionEntry,
    lines: int = DEFAULT_DETAIL_LINES,
    color: str = "auto",
    *,
    output=None,
) -> int:
    stream = output or sys.stdout
    if output is not None or not stream.isatty():
        state = SessionDetailState(entry, line_count=lines, color=color)
        for line in render_session_detail_lines(state):
            print(line, file=stream)
        return 0

    return curses.wrapper(
        lambda stdscr: _run_session_detail_tui(
            stdscr,
            entry,
            line_count=lines,
            exit_label="quit",
            exit_on_end=True,
            color=color,
        )
    )


def run_session_detail_path(
    session_path: str,
    agent: str,
    lines: int = DEFAULT_DETAIL_LINES,
    color: str = "auto",
    *,
    output=None,
    error=None,
) -> int:
    err = error or sys.stderr
    if not Path(session_path).exists():
        print(f"amon: session path missing: {session_path}", file=err)
        return 1
    active_session = resolve_active_session_record(session_path, agent)
    entry = build_session_detail_entry(session_path, agent, session=active_session)
    if active_session is None and entry.status == "unknown":
        entry.status = "exited"
        entry.status_counts = _single_status_counts("exited")
    return run_session_detail(entry, lines=lines, color=color, output=output)
