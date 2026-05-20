from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..text import _clean_text


class AgentAdapter:
    """Runtime-specific behavior for one monitored agent."""

    name = ""
    process_patterns: tuple[str, ...] = ()

    def is_agent_command(self, cmdline: str) -> bool:
        raise NotImplementedError

    def is_inline_command(self, cmdline: str) -> bool:
        return False

    def resolve_session_paths(
        self,
        pid: int,
        *,
        cmdline: str = "",
        cwd: Optional[str] = None,
        include_all: bool = False,
    ) -> list[str]:
        raise NotImplementedError

    def owns_session_path(self, path: str) -> bool:
        return False

    def session_paths_for_id(self, session_id: str) -> list[Path]:
        return []

    def session_id_matches_path(self, session_id: str, path: Path) -> bool:
        return path.stem == session_id

    def format_event(self, event: dict) -> Optional[tuple[str, str]]:
        return None

    def is_exit_event(self, event: dict) -> bool:
        event_type = event.get("type")
        if event_type in {"agent_exit", "session_exit"}:
            return True
        payload = event.get("payload") or event.get("item")
        return isinstance(payload, dict) and payload.get("type") in {"agent_exit", "session_exit"}

    def metadata_values_from_event(self, event: dict) -> list[str]:
        return _metadata_values_from_event(event)

    def command_summary_from_event(self, event: dict) -> str:
        formatted = self.format_event(event)
        if formatted and formatted[0] == "Tool":
            return formatted[1]
        return ""

    def terminal_status_from_event(self, event: dict) -> Optional[str]:
        return _event_terminal_status(event, self)


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


def _failure_marker(container: dict) -> bool:
    if container.get("is_error") is True:
        return True
    for key in ("status", "subtype", "outcome", "result"):
        value = container.get(key)
        if value is None:
            continue
        lowered = str(value).lower()
        if any(token in lowered for token in ("fail", "error", "exception", "abort")):
            return True
    for key in ("exit_code", "code"):
        value = container.get(key)
        if isinstance(value, int) and value != 0:
            return True
    return False


def _event_terminal_status(ev: dict, adapter: AgentAdapter) -> Optional[str]:
    payload = ev.get("payload") or ev.get("item")
    payload_type = payload.get("type") if isinstance(payload, dict) else None
    containers = [ev]
    if isinstance(payload, dict):
        containers.append(payload)

    if any(_failure_marker(container) for container in containers):
        if (
            adapter.is_exit_event(ev)
            or ev.get("type") in {"error", "failure", "failed"}
            or payload_type in {"error", "failure", "failed"}
        ):
            return "failed"

    return "exited" if adapter.is_exit_event(ev) else None
