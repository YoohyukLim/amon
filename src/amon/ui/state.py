from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..constants import DEFAULT_DETAIL_LINES, DETAIL_DIRECT_EXIT_KEYS, SESSION_HIGHLIGHT_SECONDS, SESSION_STATUSES, SCOPE_ALL
from ..host import _pid_alive
from ..jsonl import JsonlTail
from ..models import SessionEntry
from ..monitor.tail import _event_terminal_status, _format_detail_event, _format_exit_line, read_recent_log_lines
from ..sessions.resolve import session_id_from_path, short_session_id
from ..sessions.summary import _session_record_status, aggregate_sessions, assign_project_displays, filter_session_entries, flatten_status_groups, group_session_entries_by_status, read_log_summary
from ..sessions.summary import count_session_statuses
from ..text import _clean_text, _unique_preserve_order


class SessionListState:
    def __init__(
        self,
        scope: str = SCOPE_ALL,
        cwd: Optional[str] = None,
        inline_only: bool = False,
    ):
        self.scope = scope
        self.cwd = cwd
        self.inline_only = inline_only
        self.entries: dict[str, SessionEntry] = {}
        self.hidden_session_ids: set[str] = set()
        self.query = ""
        self.searching = False
        self.cursor = 0
        self.status_message = "Enter detail; i toggles inline; q quits"

    def merge_discovered(
        self,
        sessions: list[dict],
        now: float,
        *,
        pid_alive_func=None,
    ) -> None:
        discovered = aggregate_sessions(
            sessions,
            scope=self.scope,
            pid_alive_func=pid_alive_func,
        )
        discovered_ids = {entry.session_id for entry in discovered}

        for entry in discovered:
            previous = self.entries.get(entry.session_id)
            if previous is None:
                entry.first_seen = now
                entry.highlight_until = now + SESSION_HIGHLIGHT_SECONDS
            else:
                entry.first_seen = previous.first_seen
                entry.highlight_until = previous.highlight_until
            entry.last_seen = now
            self.entries[entry.session_id] = entry

        for session_id, entry in self.entries.items():
            if session_id in discovered_ids:
                continue
            if entry.status == "running":
                entry.status = "exited"
                entry.status_counts = {status: 0 for status in SESSION_STATUSES}
                entry.status_counts["exited"] = 1
            entry.pids = ()

        assign_project_displays(list(self.entries.values()), self.scope)
        self._clamp_cursor()

    def visible_entries(self) -> list[SessionEntry]:
        entries = [
            entry
            for entry in self.entries.values()
            if entry.session_id not in self.hidden_session_ids
            and (not self.inline_only or entry.inline)
        ]
        return filter_session_entries(entries, self.query)

    def grouped_visible_entries(self) -> list[SessionEntry]:
        return flatten_status_groups(group_session_entries_by_status(self.visible_entries()))

    def selected_entry(self) -> Optional[SessionEntry]:
        entries = self.grouped_visible_entries()
        if not entries:
            return None
        return entries[min(self.cursor, len(entries) - 1)]

    def visible_counts(self) -> dict[str, int]:
        return count_session_statuses(self.visible_entries())

    def hide_visible_finished(self) -> int:
        finished = [
            entry.session_id
            for entry in self.visible_entries()
            if entry.status in {"exited", "failed"}
        ]
        self.hidden_session_ids.update(finished)
        self.status_message = f"hid {len(finished)} exited/failed session(s)"
        self._clamp_cursor()
        return len(finished)

    def toggle_inline_only(self) -> None:
        selected = self.selected_entry()
        selected_id = selected.session_id if selected is not None else None
        self.inline_only = not self.inline_only
        if not (selected_id and self._move_cursor_to_session_id(selected_id)):
            self.cursor = 0
            self._clamp_cursor()
        state = "on" if self.inline_only else "off"
        self.status_message = f"Inline only {state}"

    def _move_cursor_to_session_id(self, session_id: str) -> bool:
        for idx, entry in enumerate(self.grouped_visible_entries()):
            if entry.session_id == session_id:
                self.cursor = idx
                return True
        return False

    def _clamp_cursor(self) -> None:
        visible_count = len(self.grouped_visible_entries())
        if visible_count == 0:
            self.cursor = 0
        else:
            self.cursor = min(max(0, self.cursor), visible_count - 1)


def should_tail_detail_status(status: str) -> bool:
    return status in {"running", "unknown"}


def _single_status_counts(status: str) -> dict[str, int]:
    counts = {candidate: 0 for candidate in SESSION_STATUSES}
    counts[status if status in counts else "unknown"] = 1
    return counts


def build_session_detail_entry(
    session_path: str,
    agent: str,
    *,
    session: Optional[dict] = None,
    pid_alive_func=None,
) -> SessionEntry:
    source = dict(session or {"agent": agent, "path": session_path})
    source.setdefault("agent", agent)
    source.setdefault("path", session_path)
    summary = read_log_summary(session_path, agent)
    status = _session_record_status(source, summary, pid_alive_func=pid_alive_func)
    metadata_values = _unique_preserve_order(summary.metadata_values)
    command = _clean_text(source.get("command")) or summary.command
    session_id = session_id_from_path(session_path)
    label = metadata_values[0] if metadata_values else (command if command else session_id)
    pid = source.get("pid")
    pids = (pid,) if isinstance(pid, int) else ()
    entry = SessionEntry(
        session_id=session_id,
        agent=agent,
        path=session_path,
        status=status,
        label=label,
        cwd=source.get("cwd"),
        command=command,
        metadata_values=metadata_values,
        search_text=" ".join([*metadata_values, command, session_id]).lower(),
        activity_mtime=summary.activity_mtime,
        paths=(session_path,),
        pids=pids,
        status_counts=_single_status_counts(status),
    )
    assign_project_displays([entry], SCOPE_ALL)
    return entry


class SessionDetailState:
    def __init__(
        self,
        entry: SessionEntry,
        line_count: int = DEFAULT_DETAIL_LINES,
        color: str = "never",
    ):
        if line_count <= 0:
            raise ValueError("line_count must be positive")
        self.entry = entry
        self.line_count = line_count
        self.color = color
        self.sid_short = short_session_id(entry.path)
        self.lines = read_recent_log_lines(
            entry.path,
            entry.agent,
            self.sid_short,
            line_count,
            color=color,
        )
        self.follow = True
        self.scroll_top = 0
        self.tail_enabled = should_tail_detail_status(entry.status) and Path(entry.path).exists()
        self.tail = JsonlTail(entry.path) if self.tail_enabled else None
        if self.tail is not None:
            self.tail.read_new_lines()
        self.status_message = "live tail" if self.tail_enabled else "static log"

    def max_scroll_top(self, viewport_lines: int) -> int:
        return max(0, len(self.lines) - max(1, viewport_lines))

    def clamp_scroll(self, viewport_lines: int) -> None:
        maximum = self.max_scroll_top(viewport_lines)
        if self.follow:
            self.scroll_top = maximum
        else:
            self.scroll_top = min(max(0, self.scroll_top), maximum)
            if self.scroll_top >= maximum:
                self.follow = True

    def scroll_up(self, amount: int, viewport_lines: int) -> None:
        self.follow = False
        self.scroll_top = max(0, self.scroll_top - amount)
        self.clamp_scroll(viewport_lines)

    def scroll_down(self, amount: int, viewport_lines: int) -> None:
        self.scroll_top = min(self.max_scroll_top(viewport_lines), self.scroll_top + amount)
        self.clamp_scroll(viewport_lines)

    def poll_tail(self) -> Optional[str]:
        if self.tail is None or not self.tail_enabled:
            return None

        appended = False
        ended_status = None
        for event in self.tail.read_new_lines():
            line = _format_detail_event(
                event,
                self.entry.agent,
                self.sid_short,
                color=self.color,
            )
            if line:
                self.lines.append(line)
                appended = True
            terminal_status = _event_terminal_status(event, self.entry.agent)
            if terminal_status:
                self.entry.status = terminal_status
                self.entry.status_counts = _single_status_counts(terminal_status)
                self.tail_enabled = False
                self.tail = None
                self.status_message = "session ended"
                ended_status = terminal_status
                break

        if appended and self.follow:
            self.scroll_top = self.max_scroll_top(1)
        return ended_status

    def poll_process_end(self, pid_alive_func=None) -> Optional[str]:
        if not self.entry.pids or self.entry.status not in {"running", "unknown"}:
            return None
        alive = pid_alive_func or _pid_alive
        if any(alive(pid) for pid in self.entry.pids):
            return None

        self.entry.status = "exited"
        self.entry.status_counts = _single_status_counts("exited")
        self.entry.pids = ()
        self.tail_enabled = False
        self.tail = None
        self.status_message = "process ended"
        exit_line = _format_exit_line(self.entry.agent, self.sid_short, self.color)
        if not self.lines or self.lines[-1] != exit_line:
            self.lines.append(exit_line)
        if self.follow:
            self.scroll_top = self.max_scroll_top(1)
        return "exited"


def handle_session_list_key(state: SessionListState, key: str) -> Optional[str]:
    if state.searching:
        if key == "ENTER":
            state.searching = False
            state.status_message = f"search=/{state.query}" if state.query else "search cleared"
        elif key == "ESC":
            state.searching = False
            state.status_message = "search cancelled"
        elif key == "BACKSPACE":
            state.query = state.query[:-1]
            state._clamp_cursor()
        elif len(key) == 1 and key.isprintable():
            state.query += key
            state._clamp_cursor()
        return None

    if key == "q":
        return "quit"
    if key == "/":
        state.searching = True
        state.status_message = "search mode"
        return None
    if key == "r":
        state.hide_visible_finished()
        return None
    if key == "i":
        state.toggle_inline_only()
        return None
    if key == "UP":
        state.cursor = max(0, state.cursor - 1)
        return None
    if key == "DOWN":
        state.cursor = min(max(0, len(state.grouped_visible_entries()) - 1), state.cursor + 1)
        return None
    if key == "ENTER":
        if state.selected_entry() is not None:
            return "detail"
        state.status_message = "no session selected"
        return None
    return None


def handle_session_detail_key(
    state: SessionDetailState,
    key: str,
    viewport_lines: int,
    *,
    exit_keys: tuple[str, ...] = DETAIL_DIRECT_EXIT_KEYS,
) -> Optional[str]:
    if key in exit_keys:
        return "quit"
    if key == "UP":
        state.scroll_up(1, viewport_lines)
        return None
    if key == "DOWN":
        state.scroll_down(1, viewport_lines)
        return None
    if key == "PAGE_UP":
        state.scroll_up(max(1, viewport_lines - 1), viewport_lines)
        return None
    if key == "PAGE_DOWN":
        state.scroll_down(max(1, viewport_lines - 1), viewport_lines)
        return None
    return None
