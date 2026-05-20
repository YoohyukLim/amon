from __future__ import annotations

import curses
import time
from typing import Optional

from ..constants import DEFAULT_DETAIL_LINES, DETAIL_DIRECT_EXIT_KEYS, DETAIL_LIST_DETAIL_EXIT_KEYS, SESSION_STATUSES
from ..models import RenderLine, SessionEntry
from ..sessions.discovery import discover_active_sessions
from .render import _display_width, render_session_detail_layout, render_session_list_layout
from .state import SessionDetailState, SessionListState, handle_session_detail_key, handle_session_list_key


TUI_COLOR_PAIRS = {
    "header": 1,
    "subtle": 2,
    "failed": 3,
    "running": 4,
    "unknown": 5,
    "exited": 6,
    "tool": 7,
    "warn": 8,
}
TUI_MUTED_COLOR_BASE = 16
TUI_MUTED_RGB = {
    "header": (520, 680, 730),
    "subtle": (560, 580, 590),
    "failed": (760, 430, 360),
    "running": (500, 730, 650),
    "unknown": (700, 640, 420),
    "exited": (520, 620, 560),
    "tool": (500, 680, 710),
    "warn": (720, 590, 390),
}
TUI_BASIC_COLOR_FALLBACKS = {
    "header": curses.COLOR_CYAN,
    "subtle": curses.COLOR_WHITE,
    "failed": curses.COLOR_RED,
    "running": curses.COLOR_GREEN,
    "unknown": curses.COLOR_YELLOW,
    "exited": curses.COLOR_WHITE,
    "tool": curses.COLOR_CYAN,
    "warn": curses.COLOR_YELLOW,
}


def _curses_key_name(key: int) -> Optional[str]:
    if key == -1:
        return None
    if key == curses.KEY_UP:
        return "UP"
    if key == curses.KEY_DOWN:
        return "DOWN"
    if key == curses.KEY_PPAGE:
        return "PAGE_UP"
    if key == curses.KEY_NPAGE:
        return "PAGE_DOWN"
    if key in (curses.KEY_ENTER, 10, 13):
        return "ENTER"
    if key in (curses.KEY_BACKSPACE, 8, 127):
        return "BACKSPACE"
    if key == 27:
        return "ESC"
    if 0 <= key <= 255:
        return chr(key)
    return None


def _muted_curses_palette() -> dict[str, int]:
    can_change_color = getattr(curses, "can_change_color", lambda: False)
    color_count = getattr(curses, "COLORS", 0)
    if not can_change_color() or color_count < TUI_MUTED_COLOR_BASE + len(TUI_MUTED_RGB):
        return TUI_BASIC_COLOR_FALLBACKS

    palette: dict[str, int] = {}
    try:
        for offset, (name, rgb) in enumerate(TUI_MUTED_RGB.items()):
            color_id = TUI_MUTED_COLOR_BASE + offset
            curses.init_color(color_id, *rgb)
            palette[name] = color_id
    except curses.error:
        return TUI_BASIC_COLOR_FALLBACKS
    return palette


def _init_curses_colors(color: str) -> bool:
    if color == "never":
        return False
    try:
        if not curses.has_colors():
            return False
        curses.start_color()
        background = -1
        try:
            curses.use_default_colors()
        except curses.error:
            background = curses.COLOR_BLACK
        pairs = _muted_curses_palette()
        for name, foreground in pairs.items():
            curses.init_pair(TUI_COLOR_PAIRS[name], foreground, background)
    except curses.error:
        return False
    return True


def _color_pair_attr(name: Optional[str], color_enabled: bool) -> int:
    if not color_enabled or not name:
        return 0
    pair = TUI_COLOR_PAIRS.get(name)
    if pair is None:
        return 0
    try:
        return curses.color_pair(pair)
    except curses.error:
        return 0


def _curses_modifier_attr_for_line(line: RenderLine) -> int:
    attr = 0
    if line.style in {"subtle", "divider", "exited"}:
        attr |= getattr(curses, "A_DIM", 0)
    if line.highlighted:
        attr |= getattr(curses, "A_UNDERLINE", 0)
    if line.selected:
        attr |= getattr(curses, "A_REVERSE", 0)
    return attr


def _curses_color_name_for_line(line: RenderLine) -> str:
    if line.status and line.style in {"row", "subtle"}:
        return line.status
    return line.style


def _curses_color_name_for_segment(line: RenderLine, style_name: str) -> str:
    if style_name == line.style:
        return _curses_color_name_for_line(line)
    return style_name


def _is_row_count_segment(line: RenderLine, style_name: str) -> bool:
    return line.style == "row" and style_name in SESSION_STATUSES


def _curses_attr_for_line(line: RenderLine, color_enabled: bool) -> int:
    return _color_pair_attr(
        _curses_color_name_for_line(line),
        color_enabled,
    ) | _curses_modifier_attr_for_line(line)


def _curses_attr_for_segment(
    line: RenderLine,
    style_name: str,
    color_enabled: bool,
) -> int:
    if line.selected and _is_row_count_segment(line, style_name):
        return _curses_attr_for_line(line, color_enabled)
    return _color_pair_attr(
        _curses_color_name_for_segment(line, style_name),
        color_enabled,
    ) | _curses_modifier_attr_for_line(line)


def _safe_addnstr(stdscr, row: int, column: int, line: str, width: int, attr: int = 0) -> None:
    try:
        if attr:
            stdscr.addnstr(row, column, line, width, attr)
        else:
            stdscr.addnstr(row, column, line, width)
    except TypeError:
        try:
            stdscr.addnstr(row, column, line, width)
        except curses.error:
            pass
    except curses.error:
        pass


def _draw_render_line(
    stdscr,
    row: int,
    line: RenderLine,
    width: int,
    color_enabled: bool,
) -> None:
    if not line.segments:
        _safe_addnstr(
            stdscr,
            row,
            0,
            line.text,
            width,
            _curses_attr_for_line(line, color_enabled),
        )
        return

    column = 0
    for segment_text, style_name in line.segments:
        if column >= width:
            break
        _safe_addnstr(
            stdscr,
            row,
            column,
            segment_text,
            max(0, width - column),
            _curses_attr_for_segment(line, style_name, color_enabled),
        )
        column += _display_width(segment_text)


def _draw_session_list(
    stdscr,
    state: SessionListState,
    now: float,
    color_enabled: bool = False,
) -> None:
    height, width = stdscr.getmaxyx()
    lines = render_session_list_layout(state, width=max(1, width - 1), height=height, now=now)
    stdscr.erase()
    for row, line in enumerate(lines):
        _draw_render_line(
            stdscr,
            row,
            line,
            max(0, width - 1),
            color_enabled,
        )
    stdscr.refresh()


def _draw_session_detail(
    stdscr,
    state: SessionDetailState,
    *,
    exit_label: str = "back",
    exit_keys: tuple[str, ...] = DETAIL_DIRECT_EXIT_KEYS,
    color_enabled: bool = False,
) -> int:
    height, width = stdscr.getmaxyx()
    lines = render_session_detail_layout(
        state,
        width=max(1, width - 1),
        height=height,
        exit_label=exit_label,
        exit_keys=exit_keys,
    )
    stdscr.erase()
    for row, line in enumerate(lines):
        _draw_render_line(
            stdscr,
            row,
            line,
            max(0, width - 1),
            color_enabled,
        )
    stdscr.refresh()
    return max(1, height - 3)


def _run_session_detail_tui(
    stdscr,
    entry: SessionEntry,
    *,
    line_count: int,
    exit_label: str = "back",
    exit_keys: tuple[str, ...] = DETAIL_DIRECT_EXIT_KEYS,
    exit_on_end: bool = False,
    pid_alive_func=None,
    poll_interval: float = 1.0,
    color: str = "auto",
) -> int:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    color_enabled = _init_curses_colors(color)
    stdscr.timeout(100)

    state = SessionDetailState(entry, line_count=line_count, color="never")
    next_poll = 0.0

    try:
        while True:
            now = time.monotonic()
            if now >= next_poll:
                ended_status = state.poll_tail()
                if ended_status is None and exit_on_end:
                    ended_status = state.poll_process_end(pid_alive_func=pid_alive_func)
                next_poll = now + poll_interval
                if exit_on_end and ended_status:
                    return 0

            viewport_lines = _draw_session_detail(
                stdscr,
                state,
                exit_label=exit_label,
                exit_keys=exit_keys,
                color_enabled=color_enabled,
            )
            key = _curses_key_name(stdscr.getch())
            if (
                key
                and handle_session_detail_key(
                    state,
                    key,
                    viewport_lines,
                    exit_keys=exit_keys,
                )
                == "quit"
            ):
                return 0
    except KeyboardInterrupt:
        return 0


def _run_sessions_tui(
    stdscr,
    codex_all: bool,
    scope: str,
    cwd: Optional[str],
    *,
    line_count: int = DEFAULT_DETAIL_LINES,
    poll_interval: float = 1.0,
    color: str = "auto",
    inline_only: bool = False,
) -> int:
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    color_enabled = _init_curses_colors(color)
    stdscr.timeout(100)

    state = SessionListState(scope=scope, cwd=cwd, inline_only=inline_only)
    next_poll = 0.0

    try:
        while True:
            now = time.monotonic()
            if now >= next_poll:
                sessions = discover_active_sessions(codex_all=codex_all, scope=scope, cwd=cwd)
                state.merge_discovered(sessions, now)
                next_poll = now + poll_interval

            _draw_session_list(stdscr, state, now, color_enabled=color_enabled)
            key = _curses_key_name(stdscr.getch())
            if key:
                action = handle_session_list_key(state, key)
                if action == "quit":
                    return 0
                if action == "detail":
                    selected = state.selected_entry()
                    if selected is not None:
                        _run_session_detail_tui(
                            stdscr,
                            selected,
                            line_count=line_count,
                            exit_label="back",
                            exit_keys=DETAIL_LIST_DETAIL_EXIT_KEYS,
                            poll_interval=poll_interval,
                            color=color,
                        )
    except KeyboardInterrupt:
        return 0
