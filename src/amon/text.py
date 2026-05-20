from __future__ import annotations

import json
import unicodedata
from typing import Optional


def _truncate(text: str, n: int = 80) -> str:
    collapsed = " ".join(str(text).split())
    if len(collapsed) <= n:
        return collapsed
    if n <= 3:
        return collapsed[:n]
    return collapsed[: n - 3] + "..."


def _tool_detail(data: object) -> str:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return _truncate(data)
    if not isinstance(data, dict):
        return ""

    for key in ("command", "cmd", "file_path", "path"):
        value = data.get(key)
        if value:
            return _truncate(str(value))
    for key in ("description", "query", "url", "workdir"):
        value = data.get(key)
        if value:
            return _truncate(str(value))
    return ""


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _unique_preserve_order(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return tuple(unique)


def _clip_line(line: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(line) <= width:
        return line
    if width <= 3:
        return line[:width]
    return line[: width - 3] + "..."


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
