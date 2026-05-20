from __future__ import annotations

import locale
import os
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional

from ..constants import ASCII_STATIC_STATUS_ICONS, ASCII_STATUS_ICON_FRAMES, DETAIL_DIRECT_EXIT_KEYS, LIST_STATUS_GROUPS, SCOPE_CURRENT, STATUS_COUNT_DISPLAY_ORDER, STATUS_ICON_FRAME_SECONDS, UNICODE_STATIC_STATUS_ICONS, UNICODE_STATUS_ICON_FRAMES
from ..host import _realpath
from ..models import RenderLine, SessionEntry
from ..sessions.summary import count_session_statuses, flatten_status_groups, group_session_entries_by_status
from ..text import _clip_line, _display_width, _encoding_supports_unicode, _fit_list_cell, _fit_list_cell_segments, _join_list_cell_segments, _segments_text, _take_display_width
from .state import SessionDetailState, SessionListState


LIST_PROJECT_WIDTH = 18
LIST_PROJECT_MIN_WIDTH = 8
LIST_STATUS_WIDTH = 1
LIST_ACTIVITY_WIDTH = 8
LIST_COUNTS_WIDTH = 11
LIST_LABEL_MIN_WIDTH = 8


def _clip_render_line(item: RenderLine, width: int) -> RenderLine:
    clipped = _clip_line(item.text, width)
    return RenderLine(
        clipped,
        item.style,
        status=item.status,
        selected=item.selected,
        highlighted=item.highlighted,
        segments=item.segments if clipped == item.text else None,
    )


def _scope_project_label(scope: str, cwd: Optional[str]) -> str:
    if scope == SCOPE_CURRENT:
        return Path(_realpath(cwd or os.getcwd())).name or _realpath(cwd or os.getcwd())
    return "all"


def _format_counts(counts: dict[str, int]) -> str:
    return " ".join(
        f"{status}={counts.get(status, 0)}"
        for status in STATUS_COUNT_DISPLAY_ORDER
    )


def _format_detail_exit_keys(exit_keys: tuple[str, ...]) -> str:
    labels = {"BACKSPACE": "Backspace", "ESC": "Esc"}
    return "/".join(labels.get(key, key) for key in exit_keys)


class ListColumnLayout:
    def __init__(
        self,
        *,
        project_width: int,
        label_width: int,
        show_agent: bool = True,
        show_session: bool = True,
        show_project: bool = True,
        show_activity: bool = True,
        show_counts: bool = True,
    ):
        self.project_width = project_width
        self.label_width = label_width
        self.show_agent = show_agent
        self.show_session = show_session
        self.show_project = show_project
        self.show_activity = show_activity
        self.show_counts = show_counts


def _char_display_width(char: str) -> int:
    if unicodedata.combining(char):
        return 0
    if unicodedata.category(char) in {"Cc", "Cf"}:
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


def _display_width(value: str) -> int:
    return sum(_char_display_width(char) for char in value)


def _take_display_width(value: str, width: int) -> str:
    if width <= 0:
        return ""
    used = 0
    chars = []
    for char in value:
        char_width = _char_display_width(char)
        if used + char_width > width:
            break
        chars.append(char)
        used += char_width
    return "".join(chars)


def _clip_cell(value: str, width: int) -> str:
    if width <= 0:
        return ""
    if _display_width(value) <= width:
        return value
    if width <= 3:
        return _take_display_width(value, width)
    return _take_display_width(value, width - 3) + "..."


def _fit_list_cell(value: str, width: int) -> str:
    if width <= 0:
        return ""
    clipped = _clip_cell(value, width)
    return clipped + " " * max(0, width - _display_width(clipped))


def _segments_text(segments: list[tuple[str, str]]) -> str:
    return "".join(text for text, _style in segments)


def _take_segments_display_width(
    segments: list[tuple[str, str]],
    width: int,
) -> list[tuple[str, str]]:
    if width <= 0:
        return []
    result: list[tuple[str, str]] = []
    used = 0
    for text, style in segments:
        part = _take_display_width(text, width - used)
        if part:
            result.append((part, style))
            used += _display_width(part)
        if used >= width:
            break
    return result


def _fit_list_cell_segments(
    segments: list[tuple[str, str]],
    width: int,
    pad_style: str,
) -> list[tuple[str, str]]:
    if width <= 0:
        return []
    text = _segments_text(segments)
    if _display_width(text) <= width:
        fitted = list(segments)
    elif width <= 3:
        fitted = _take_segments_display_width(segments, width)
    else:
        fitted = _take_segments_display_width(segments, width - 3)
        fitted.append(("...", fitted[-1][1] if fitted else pad_style))
    pad_width = width - _display_width(_segments_text(fitted))
    if pad_width > 0:
        fitted.append((" " * pad_width, pad_style))
    return fitted


def _rstrip_segments(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    result = list(segments)
    while result:
        text, style = result[-1]
        stripped = text.rstrip(" ")
        if stripped:
            result[-1] = (stripped, style)
            break
        result.pop()
    return result


def _join_list_cell_segments(
    cells: list[list[tuple[str, str]]],
    separator_style: str,
) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    for index, cell in enumerate(cells):
        if index:
            segments.append((" ", separator_style))
        segments.extend(cell)
    return _rstrip_segments(segments)


def _encoding_supports_unicode(encoding: Optional[str]) -> bool:
    return bool(encoding and "utf" in encoding.lower())


def _use_unicode_status_icons() -> bool:
    if os.environ.get("AMON_ASCII_ICONS"):
        return False
    stdout_encoding = getattr(sys.stdout, "encoding", None)
    if stdout_encoding:
        return _encoding_supports_unicode(stdout_encoding)
    return _encoding_supports_unicode(locale.getpreferredencoding(False))


def _status_icon_frame_index(now: float) -> int:
    return int(now / STATUS_ICON_FRAME_SECONDS)


def _status_icon(
    status: str,
    now: float,
    *,
    unicode_icons: Optional[bool] = None,
) -> str:
    use_unicode = _use_unicode_status_icons() if unicode_icons is None else unicode_icons
    icon_frames = UNICODE_STATUS_ICON_FRAMES if use_unicode else ASCII_STATUS_ICON_FRAMES
    frames = icon_frames.get(status, icon_frames["unknown"])
    icon = frames[_status_icon_frame_index(now) % len(frames)]
    if _display_width(icon) == 1:
        return icon

    fallback_frames = ASCII_STATUS_ICON_FRAMES.get(status, ASCII_STATUS_ICON_FRAMES["unknown"])
    return fallback_frames[_status_icon_frame_index(now) % len(fallback_frames)]


def _static_status_icon(status: str, *, unicode_icons: Optional[bool] = None) -> str:
    use_unicode = _use_unicode_status_icons() if unicode_icons is None else unicode_icons
    icons = UNICODE_STATIC_STATUS_ICONS if use_unicode else ASCII_STATIC_STATUS_ICONS
    icon = icons.get(status, icons["unknown"])
    if _display_width(icon) == 1:
        return icon

    fallback_icons = ASCII_STATIC_STATUS_ICONS
    return fallback_icons.get(status, fallback_icons["unknown"])


def _session_activity_label(activity_mtime: Optional[float], wall_now: float) -> str:
    if activity_mtime is None:
        return "-"
    age = max(0, int(wall_now - activity_mtime))
    if age < 60:
        return "now" if age < 5 else f"{age}s ago"
    if age < 3600:
        return f"{age // 60}m ago"
    if age < 86400:
        return f"{age // 3600}h ago"
    days = age // 86400
    if days < 1000:
        return f"{days}d ago"
    return time.strftime("%Y-%m", time.localtime(activity_mtime))


def _session_counts_label(counts: dict[str, int], now: float) -> str:
    return " ".join(
        f"{_static_status_icon(status)}{counts.get(status, 0)}"
        for status in STATUS_COUNT_DISPLAY_ORDER
    )


def _session_counts_segments(
    counts: dict[str, int],
    *,
    separator_style: str = "header",
    style_by_status: Optional[dict[str, str]] = None,
) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    for index, status in enumerate(STATUS_COUNT_DISPLAY_ORDER):
        if index:
            segments.append((" ", separator_style))
        style = style_by_status.get(status, status) if style_by_status else status
        segments.append((f"{_static_status_icon(status)}{counts.get(status, 0)}", style))
    return segments


def _session_status_label(status: str, now: float) -> str:
    return _status_icon(status, now)


def _list_row_width(layout: ListColumnLayout, label_width: int) -> int:
    columns = [(1, "sel"), (1, "new"), (LIST_STATUS_WIDTH, "status")]
    if layout.show_agent:
        columns.append((6, "agent"))
    if layout.show_session:
        columns.append((8, "session"))
    if layout.show_project:
        columns.append((layout.project_width, "project"))
    columns.append((label_width, "label"))
    if layout.show_activity:
        columns.append((LIST_ACTIVITY_WIDTH, "activity"))
    if layout.show_counts:
        columns.append((LIST_COUNTS_WIDTH, "counts"))
    return sum(column_width for column_width, _ in columns) + len(columns) - 1


def _list_project_width(entries: list[SessionEntry]) -> int:
    project_widths = [_display_width(entry.project_display) for entry in entries]
    content_width = max([_display_width("project"), *project_widths])
    return min(LIST_PROJECT_WIDTH, max(LIST_PROJECT_MIN_WIDTH, content_width))


def _list_column_layout(
    width: int,
    *,
    project_width: int = LIST_PROJECT_WIDTH,
) -> ListColumnLayout:
    project_width = min(LIST_PROJECT_WIDTH, max(LIST_PROJECT_MIN_WIDTH, project_width))
    layout = ListColumnLayout(project_width=project_width, label_width=0)

    while True:
        label_width = width - _list_row_width(layout, 0)
        if label_width >= LIST_LABEL_MIN_WIDTH:
            break
        if layout.show_project and layout.project_width > LIST_PROJECT_MIN_WIDTH:
            layout.project_width = max(
                LIST_PROJECT_MIN_WIDTH,
                layout.project_width - (LIST_LABEL_MIN_WIDTH - label_width),
            )
            continue
        if layout.show_project:
            layout.show_project = False
            continue
        if layout.show_counts:
            layout.show_counts = False
            continue
        if layout.show_activity:
            layout.show_activity = False
            continue
        if layout.show_agent:
            layout.show_agent = False
            continue
        if layout.show_session:
            layout.show_session = False
            continue
        break

    layout.label_width = max(0, width - _list_row_width(layout, 0))
    return layout


def _format_session_list_columns(
    *,
    selected: str,
    highlight: str,
    status: str,
    agent: str,
    session_id: str,
    project: str,
    label: str,
    activity: str,
    counts: str,
    layout: ListColumnLayout,
) -> str:
    return _segments_text(
        _format_session_list_column_segments(
            selected=selected,
            highlight=highlight,
            status=status,
            agent=agent,
            session_id=session_id,
            project=project,
            label=label,
            activity=activity,
            counts=counts,
            layout=layout,
        )
    )


def _format_session_list_column_segments(
    *,
    selected: str,
    highlight: str,
    status: str,
    agent: str,
    session_id: str,
    project: str,
    label: str,
    activity: str,
    counts: str,
    layout: ListColumnLayout,
    count_segments: Optional[list[tuple[str, str]]] = None,
    segment_style: str = "row",
) -> list[tuple[str, str]]:
    cells = [
        [(_fit_list_cell(selected, 1), segment_style)],
        [(_fit_list_cell(highlight, 1), segment_style)],
        [(_fit_list_cell(status, LIST_STATUS_WIDTH), segment_style)],
    ]
    if layout.show_agent:
        cells.append([(_fit_list_cell(agent, 6), segment_style)])
    if layout.show_session:
        cells.append([(_fit_list_cell(session_id, 8), segment_style)])
    if layout.show_project:
        cells.append([(_fit_list_cell(project, layout.project_width), segment_style)])
    cells.append([(_fit_list_cell(label, layout.label_width), segment_style)])
    if layout.show_activity:
        cells.append([(_fit_list_cell(activity, LIST_ACTIVITY_WIDTH), segment_style)])
    if layout.show_counts:
        if count_segments is None:
            cells.append([(_fit_list_cell(counts, LIST_COUNTS_WIDTH), segment_style)])
        else:
            cells.append(
                _fit_list_cell_segments(
                    count_segments,
                    LIST_COUNTS_WIDTH,
                    segment_style,
                )
            )
    return _join_list_cell_segments(cells, segment_style)


def _format_session_list_row(
    entry: SessionEntry,
    *,
    selected: bool,
    current: float,
    wall_now: float,
    layout: ListColumnLayout,
) -> RenderLine:
    count_segments = _session_counts_segments(
        entry.status_counts,
        separator_style="row",
    )
    line_segments = _format_session_list_column_segments(
        selected=">" if selected else " ",
        highlight="*" if entry.highlight_until > current else " ",
        status=_session_status_label(entry.status, current),
        agent=entry.agent,
        session_id=entry.session_id[:8],
        project=entry.project_display,
        label=entry.label,
        activity=_session_activity_label(entry.activity_mtime, wall_now),
        counts=_session_counts_label(entry.status_counts, current),
        layout=layout,
        count_segments=count_segments if layout.show_counts else None,
    )
    line = _segments_text(line_segments)
    return RenderLine(
        line,
        "row",
        status=entry.status,
        selected=selected,
        highlighted=entry.highlight_until > current,
        segments=line_segments if layout.show_counts else None,
    )


def _selected_group_position(
    groups: list[tuple[str, str, list[SessionEntry]]],
    cursor: int,
) -> tuple[int, int]:
    remaining = cursor
    for group_index, (_status, _title, entries) in enumerate(groups):
        if remaining < len(entries):
            return group_index, remaining
        remaining -= len(entries)
    return 0, 0


def _render_session_group_block(
    status: str,
    title: str,
    entries: list[SessionEntry],
    *,
    row_start: int,
    row_count: int,
    selected_group_index: int,
    selected_entry_index: int,
    group_index: int,
    current: float,
    wall_now: float,
    layout: ListColumnLayout,
) -> list[RenderLine]:
    lines = [RenderLine(f"{title} ({len(entries)})", "subtle", status=status)]
    visible_entries = entries[row_start : row_start + row_count]
    for entry_index, entry in enumerate(visible_entries, start=row_start):
        lines.append(
            _format_session_list_row(
                entry,
                selected=(
                    group_index == selected_group_index
                    and entry_index == selected_entry_index
                ),
                current=current,
                wall_now=wall_now,
                layout=layout,
            )
        )
    return lines


def _minimum_nonempty_group_lines(
    groups: list[tuple[str, str, list[SessionEntry]]],
) -> int:
    return sum(2 for _status, _title, entries in groups if entries)


def _allocated_group_row_windows(
    groups: list[tuple[str, str, list[SessionEntry]]],
    *,
    selected_group: int,
    selected_entry: int,
    row_capacity: int,
) -> dict[int, tuple[int, int]]:
    windows = {group_index: (0, 0) for group_index in range(len(groups))}
    if row_capacity <= 0:
        return windows

    entries = groups[selected_group][2]
    selected_count = min(len(entries), row_capacity)
    if selected_count:
        selected_start = min(
            selected_entry,
            max(0, len(entries) - selected_count),
        )
        windows[selected_group] = (selected_start, selected_count)
        row_capacity -= selected_count

    group_order = [
        *range(selected_group + 1, len(groups)),
        *range(0, selected_group),
    ]
    for group_index in group_order:
        if row_capacity <= 0:
            break
        entries = groups[group_index][2]
        row_count = min(len(entries), row_capacity)
        if row_count:
            windows[group_index] = (0, row_count)
            row_capacity -= row_count
    return windows


def _session_group_body_blocks(
    groups: list[tuple[str, str, list[SessionEntry]]],
    *,
    cursor: int,
    row_budget: int,
) -> list[tuple[int, int, int]]:
    if row_budget <= 0 or not groups:
        return []

    if not flatten_status_groups(groups):
        return [
            (group_index, 0, 0)
            for group_index in range(min(row_budget, len(groups)))
        ]

    selected_group, selected_entry = _selected_group_position(groups, cursor)

    if row_budget >= len(groups):
        windows = _allocated_group_row_windows(
            groups,
            selected_group=selected_group,
            selected_entry=selected_entry,
            row_capacity=row_budget - len(groups),
        )
        return [
            (group_index, *windows[group_index])
            for group_index in range(len(groups))
        ]

    _status, _title, entries = groups[selected_group]
    selected_rows_budget = row_budget - 1
    row_start = min(selected_entry, max(0, len(entries) - selected_rows_budget))
    row_count = min(len(entries) - row_start, selected_rows_budget)
    blocks = [(selected_group, row_start, row_count)]

    remaining = row_budget - (1 + row_count)
    group_index = selected_group + 1
    while remaining > 0 and group_index < len(groups):
        _status, _title, entries = groups[group_index]
        minimum_lines = 1 + (1 if entries else 0)
        if not entries and remaining <= _minimum_nonempty_group_lines(
            groups[group_index + 1 :]
        ):
            group_index += 1
            continue
        if remaining < minimum_lines:
            break
        row_count = min(len(entries), remaining - 1)
        blocks.append((group_index, 0, row_count))
        remaining -= 1 + row_count
        group_index += 1

    group_index = selected_group - 1
    while remaining > 0 and group_index >= 0:
        _status, _title, entries = groups[group_index]
        minimum_lines = 1 + (1 if entries else 0)
        if not entries and remaining <= _minimum_nonempty_group_lines(
            groups[:group_index]
        ):
            group_index -= 1
            continue
        if remaining < minimum_lines:
            break
        row_count = min(len(entries), remaining - 1)
        row_start = len(entries) - row_count
        blocks = [(group_index, row_start, row_count)] + blocks
        remaining -= 1 + row_count
        group_index -= 1

    return blocks


def _session_group_body_entries(
    groups: list[tuple[str, str, list[SessionEntry]]],
    blocks: list[tuple[int, int, int]],
) -> list[SessionEntry]:
    entries: list[SessionEntry] = []
    for group_index, row_start, row_count in blocks:
        group_entries = groups[group_index][2]
        entries.extend(group_entries[row_start : row_start + row_count])
    return entries


def _render_session_group_body(
    groups: list[tuple[str, str, list[SessionEntry]]],
    *,
    cursor: int,
    row_budget: int,
    current: float,
    wall_now: float,
    layout: ListColumnLayout,
    blocks: Optional[list[tuple[int, int, int]]] = None,
) -> list[RenderLine]:
    if blocks is None:
        blocks = _session_group_body_blocks(
            groups,
            cursor=cursor,
            row_budget=row_budget,
        )
    if not blocks:
        return []

    if flatten_status_groups(groups):
        selected_group, selected_entry = _selected_group_position(groups, cursor)
    else:
        selected_group, selected_entry = 0, 0

    body = []
    for group_index, row_start, row_count in blocks:
        status, title, entries = groups[group_index]
        body.extend(
            _render_session_group_block(
                status,
                title,
                entries,
                row_start=row_start,
                row_count=row_count,
                selected_group_index=selected_group,
                selected_entry_index=selected_entry,
                group_index=group_index,
                current=current,
                wall_now=wall_now,
                layout=layout,
            )
        )

    return body[:row_budget]


def render_session_list_layout(
    state: SessionListState,
    width: int = 100,
    height: int = 24,
    now: Optional[float] = None,
) -> list[RenderLine]:
    current = time.monotonic() if now is None else now
    visible = state.visible_entries()
    groups = group_session_entries_by_status(visible)
    counts = count_session_statuses(visible)
    total = len(visible)
    hidden = len(state.hidden_session_ids)
    search = f"/{state.query}" if state.query else "-"
    inline = "on" if state.inline_only else "off"
    header_line_count = 3
    row_budget = max(0, height - header_line_count - 1)
    cursor = min(
        state.cursor,
        max(0, len(flatten_status_groups(groups)) - 1),
    )
    body_blocks = _session_group_body_blocks(
        groups,
        cursor=cursor,
        row_budget=row_budget,
    )
    project_width = _list_project_width(
        _session_group_body_entries(groups, body_blocks)
    )
    layout = _list_column_layout(width, project_width=project_width)
    header_prefix = f"amon sessions total={total} "
    header_counts = _session_counts_label(counts, current)
    lines = [
        RenderLine(
            f"{header_prefix}{header_counts}",
            "header",
            segments=[
                (header_prefix, "header"),
                *_session_counts_segments(counts),
            ],
        ),
        RenderLine(
            f"scope={state.scope} project={_scope_project_label(state.scope, state.cwd)} "
            f"inline={inline} search={search} hidden={hidden}",
            "subtle",
        ),
        RenderLine(
            _format_session_list_columns(
                selected=">",
                highlight="*",
                status="",
                agent="agent",
                session_id="session",
                project="project",
                label="label",
                activity="activity",
                counts="counts",
                layout=layout,
            ),
            "subtle",
        ),
    ]

    if row_budget:
        wall_now = time.time()
        lines.extend(
            _render_session_group_body(
                groups,
                cursor=cursor,
                row_budget=row_budget,
                current=current,
                wall_now=wall_now,
                layout=layout,
                blocks=body_blocks,
            )
        )

    if state.searching:
        status_line = f"search: /{state.query}"
    else:
        status_line = state.status_message
    lines.append(RenderLine(status_line, "subtle"))
    return [_clip_render_line(line, width) for line in lines[:height]]


def render_session_list_lines(
    state: SessionListState,
    width: int = 100,
    height: int = 24,
    now: Optional[float] = None,
) -> list[str]:
    return [
        line.text
        for line in render_session_list_layout(
            state,
            width=width,
            height=height,
            now=now,
        )
    ]


def _detail_body_style(line: str) -> str:
    if "AGENT FAILED" in line:
        return "failed"
    if "AGENT EXITED" in line:
        return "exited"
    if "] IDLE" in line or " IDLE " in line:
        return "warn"
    if "] Tool " in line:
        return "tool"
    return "normal"


def render_session_detail_layout(
    state: SessionDetailState,
    width: int = 100,
    height: int = 24,
    *,
    exit_label: str = "back",
    exit_keys: tuple[str, ...] = DETAIL_DIRECT_EXIT_KEYS,
) -> list[RenderLine]:
    counts = _format_counts(state.entry.status_counts)
    header = [
        RenderLine(f"amon detail {state.entry.label}", "header"),
        RenderLine(
            (
                f"session={state.entry.session_id} agent={state.entry.agent} "
                f"project={state.entry.project_display} status={state.entry.status} {counts}"
            ),
            "row",
            status=state.entry.status,
        ),
        RenderLine(
            (
                f"tail={'live' if state.tail_enabled else 'static'} "
                f"follow={'on' if state.follow else 'off'} lines={state.line_count} "
                f"{_format_detail_exit_keys(exit_keys)} {exit_label}"
            ),
            "subtle",
        ),
    ]
    log_budget = max(1, height - len(header))
    state.clamp_scroll(log_budget)
    if state.lines:
        body = [
            RenderLine(line, _detail_body_style(line))
            for line in state.lines[state.scroll_top : state.scroll_top + log_budget]
        ]
    else:
        body = [RenderLine("(no log events)", "subtle")]
    return [_clip_render_line(line, width) for line in (header + body)[:height]]


def render_session_detail_lines(
    state: SessionDetailState,
    width: int = 100,
    height: int = 24,
    *,
    exit_label: str = "back",
    exit_keys: tuple[str, ...] = DETAIL_DIRECT_EXIT_KEYS,
) -> list[str]:
    return [
        line.text
        for line in render_session_detail_layout(
            state,
            width=width,
            height=height,
            exit_label=exit_label,
            exit_keys=exit_keys,
        )
    ]
