from __future__ import annotations

from typing import Optional

from .constants import SESSION_STATUSES


class LogSummary:
    def __init__(self):
        self.metadata_values: list[str] = []
        self.command = ""
        self.terminal_status: Optional[str] = None
        self.activity_mtime: Optional[float] = None


class SessionEntry:
    def __init__(
        self,
        *,
        session_id: str,
        agent: str,
        path: str,
        status: str,
        label: str,
        project_display: str = "-",
        cwd: Optional[str] = None,
        command: str = "",
        metadata_values: tuple[str, ...] = (),
        search_text: str = "",
        activity_mtime: Optional[float] = None,
        paths: tuple[str, ...] = (),
        pids: tuple[int, ...] = (),
        inline: bool = False,
        status_counts: Optional[dict[str, int]] = None,
        first_seen: float = 0.0,
        last_seen: float = 0.0,
        highlight_until: float = 0.0,
    ):
        self.session_id = session_id
        self.agent = agent
        self.path = path
        self.status = status
        self.label = label
        self.project_display = project_display
        self.cwd = cwd
        self.command = command
        self.metadata_values = metadata_values
        self.search_text = search_text
        self.activity_mtime = activity_mtime
        self.paths = paths
        self.pids = pids
        self.inline = inline
        self.status_counts = status_counts or {
            status: (1 if status == self.status else 0) for status in SESSION_STATUSES
        }
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.highlight_until = highlight_until


class RenderLine:
    def __init__(
        self,
        text: str,
        style: str = "normal",
        *,
        status: Optional[str] = None,
        selected: bool = False,
        highlighted: bool = False,
        segments: Optional[list[tuple[str, str]]] = None,
    ):
        self.text = text
        self.style = style
        self.status = status
        self.selected = selected
        self.highlighted = highlighted
        self.segments = segments
