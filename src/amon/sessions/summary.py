from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Optional

from ..agents.registry import get_agent, is_inline_agent_command
from ..constants import LIST_STATUS_GROUPS, SCOPE_ALL, SESSION_STATUSES, STATUS_PRIORITY
from ..host import _pid_alive, _realpath
from ..models import LogSummary, SessionEntry
from ..monitor.tail import _event_terminal_status
from ..text import _clean_text, _unique_preserve_order
from .resolve import infer_agent_from_path, session_id_from_path


def _metadata_values_from_event(ev: dict) -> list[str]:
    containers: list[dict] = []
    if ev.get("type") in {"session", "session_meta", "session_metadata"}:
        containers.append(ev)
    for key in ("metadata", "session"):
        value = ev.get(key)
        if isinstance(value, dict):
            containers.append(value)

    payload = ev.get("payload") or ev.get("item")
    if isinstance(payload, dict):
        if payload.get("type") in {"session", "session_meta", "session_metadata"}:
            containers.append(payload)
        for key in ("metadata", "session"):
            value = payload.get(key)
            if isinstance(value, dict):
                containers.append(value)

    values: list[str] = []
    for container in containers:
        for key in ("label", "name", "title"):
            text = _clean_text(container.get(key))
            if text:
                values.append(text)
    return values


def _command_summary_from_event(ev: dict, agent: str) -> str:
    return get_agent(agent).command_summary_from_event(ev)


def read_log_summary(session_path: str, agent: str) -> LogSummary:
    summary = LogSummary()
    adapter = get_agent(agent)
    path = Path(session_path)
    if not path.exists():
        return summary

    try:
        summary.activity_mtime = path.stat().st_mtime
    except OSError:
        return summary

    try:
        handle = path.open("r", encoding="utf-8")
    except OSError:
        return summary

    with handle:
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
            summary.metadata_values.extend(adapter.metadata_values_from_event(event))
            if not summary.command:
                summary.command = adapter.command_summary_from_event(event)
            terminal_status = adapter.terminal_status_from_event(event)
            if terminal_status == "failed":
                summary.terminal_status = "failed"
            elif terminal_status == "exited" and summary.terminal_status != "failed":
                summary.terminal_status = "exited"
    summary.metadata_values = list(_unique_preserve_order(summary.metadata_values))
    return summary


def _session_record_status(
    session: dict,
    summary: LogSummary,
    pid_alive_func=None,
) -> str:
    if summary.terminal_status:
        return summary.terminal_status

    pid = session.get("pid")
    if isinstance(pid, int):
        alive = (pid_alive_func or _pid_alive)(pid)
        return "running" if alive else "exited"

    if summary.activity_mtime is None:
        return "unknown"
    return "unknown"


def representative_status(statuses: list[str]) -> str:
    if not statuses:
        return "unknown"
    return max(statuses, key=lambda status: STATUS_PRIORITY.get(status, 1))


def _path_segments(path: str) -> list[str]:
    parts = []
    for part in Path(_realpath(path)).parts:
        if part and part != os.sep:
            parts.append(part)
    return parts or [os.sep]


def disambiguate_project_paths(paths: list[str]) -> dict[str, str]:
    unique_paths = sorted({_realpath(path) for path in paths if path})
    if not unique_paths:
        return {}

    segments_by_path = {path: _path_segments(path) for path in unique_paths}
    depths = {path: 1 for path in unique_paths}

    while True:
        labels = {
            path: "/".join(segments_by_path[path][-depths[path] :])
            for path in unique_paths
        }
        duplicates = {
            label
            for label in labels.values()
            if list(labels.values()).count(label) > 1
        }
        if not duplicates:
            return labels

        changed = False
        for path, label in labels.items():
            if label in duplicates and depths[path] < len(segments_by_path[path]):
                depths[path] += 1
                changed = True
        if not changed:
            return labels


def assign_project_displays(entries: list[SessionEntry], scope: str) -> None:
    if scope == SCOPE_ALL:
        mapping = disambiguate_project_paths([entry.cwd or "" for entry in entries])
        for entry in entries:
            entry.project_display = mapping.get(_realpath(entry.cwd), "-") if entry.cwd else "-"
        return

    for entry in entries:
        entry.project_display = Path(_realpath(entry.cwd)).name if entry.cwd else "-"


def aggregate_sessions(
    sessions: list[dict],
    scope: str = SCOPE_ALL,
    *,
    pid_alive_func=None,
) -> list[SessionEntry]:
    groups: dict[str, dict] = {}
    summaries: dict[tuple[str, str], LogSummary] = {}

    for session in sessions:
        path = str(session.get("path") or "")
        if not path:
            continue
        agent = str(session.get("agent") or infer_agent_from_path(path))
        session_id = session_id_from_path(path)
        summary_key = (path, agent)
        summary = summaries.get(summary_key)
        if summary is None:
            summary = read_log_summary(path, agent)
            summaries[summary_key] = summary

        status = _session_record_status(session, summary, pid_alive_func=pid_alive_func)
        command = _clean_text(session.get("command")) or summary.command
        inline_value = session.get("inline")
        inline = (
            bool(inline_value)
            if inline_value is not None
            else is_inline_agent_command(command, agent)
        )
        pid = session.get("pid")
        group = groups.setdefault(
            session_id,
            {
                "session_id": session_id,
                "agent": agent,
                "path": path,
                "paths": [],
                "pids": [],
                "statuses": [],
                "metadata_values": [],
                "commands": [],
                "inline": False,
                "cwd": session.get("cwd"),
                "activity_mtime": summary.activity_mtime,
            },
        )
        group["paths"].append(path)
        if isinstance(pid, int):
            group["pids"].append(pid)
        group["statuses"].append(status)
        group["metadata_values"].extend(summary.metadata_values)
        if inline:
            group["inline"] = True
        if command:
            group["commands"].append(command)
        if not group["cwd"] and session.get("cwd"):
            group["cwd"] = session.get("cwd")
        if summary.activity_mtime is not None:
            current_mtime = group["activity_mtime"]
            if current_mtime is None or summary.activity_mtime > current_mtime:
                group["activity_mtime"] = summary.activity_mtime
                group["path"] = path
                group["agent"] = agent

    entries: list[SessionEntry] = []
    for group in groups.values():
        metadata_values = _unique_preserve_order(group["metadata_values"])
        commands = _unique_preserve_order(group["commands"])
        label = metadata_values[0] if metadata_values else (commands[0] if commands else group["session_id"])
        search_parts = list(metadata_values) + list(commands) + [group["session_id"]]
        status_counts = {status: 0 for status in SESSION_STATUSES}
        for status in group["statuses"]:
            status_counts[status if status in status_counts else "unknown"] += 1
        entries.append(
            SessionEntry(
                session_id=group["session_id"],
                agent=group["agent"],
                path=group["path"],
                status=representative_status(group["statuses"]),
                label=label,
                cwd=group["cwd"],
                command=commands[0] if commands else "",
                metadata_values=metadata_values,
                search_text=" ".join(search_parts).lower(),
                activity_mtime=group["activity_mtime"],
                paths=_unique_preserve_order(group["paths"]),
                pids=tuple(sorted(set(group["pids"]))),
                inline=group["inline"],
                status_counts=status_counts,
            )
        )

    assign_project_displays(entries, scope)
    return sort_session_entries(entries)


def sort_session_entries(entries: list[SessionEntry]) -> list[SessionEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            entry.activity_mtime is None,
            -(entry.activity_mtime or 0.0),
            entry.session_id,
        ),
    )


def count_session_statuses(entries: list[SessionEntry]) -> dict[str, int]:
    counts = {status: 0 for status in SESSION_STATUSES}
    for entry in entries:
        counts[entry.status if entry.status in counts else "unknown"] += 1
    return counts


def filter_session_entries(entries: list[SessionEntry], query: str) -> list[SessionEntry]:
    ordered = sort_session_entries(entries)
    query = query.strip().lower()
    if not query:
        return ordered
    return [entry for entry in ordered if query in entry.search_text]


def group_session_entries_by_status(
    entries: list[SessionEntry],
) -> list[tuple[str, str, list[SessionEntry]]]:
    grouped = {status: [] for status, _title in LIST_STATUS_GROUPS}
    for entry in entries:
        status = entry.status if entry.status in grouped else "unknown"
        grouped[status].append(entry)
    return [(status, title, grouped[status]) for status, title in LIST_STATUS_GROUPS]


def flatten_status_groups(
    groups: list[tuple[str, str, list[SessionEntry]]],
) -> list[SessionEntry]:
    return [entry for _status, _title, entries in groups for entry in entries]
