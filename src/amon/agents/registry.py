from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter


_ADAPTERS: tuple[AgentAdapter, ...] = (ClaudeAdapter(), CodexAdapter())
_ADAPTERS_BY_NAME = {adapter.name: adapter for adapter in _ADAPTERS}


def all_adapters() -> tuple[AgentAdapter, ...]:
    return _ADAPTERS


def agent_names() -> set[str]:
    return set(_ADAPTERS_BY_NAME)


def get_agent(name: str) -> AgentAdapter:
    try:
        return _ADAPTERS_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(f"unknown agent: {name}") from exc


def adapters_for_command(cmdline: str) -> list[AgentAdapter]:
    return [adapter for adapter in _ADAPTERS if adapter.is_agent_command(cmdline)]


def is_inline_agent_command(cmdline: str, agent: str = "") -> bool:
    if agent:
        return get_agent(agent).is_inline_command(cmdline)
    return any(adapter.is_inline_command(cmdline) for adapter in _ADAPTERS)


def candidate_process_patterns() -> list[str]:
    patterns: list[str] = []
    seen: set[str] = set()
    for adapter in _ADAPTERS:
        for pattern in adapter.process_patterns:
            if pattern in seen:
                continue
            patterns.append(pattern)
            seen.add(pattern)
    return patterns


def adapter_for_path(path: str) -> AgentAdapter | None:
    for adapter in _ADAPTERS:
        if adapter.owns_session_path(path):
            return adapter
    return None


def infer_agent_name_from_path(path: str) -> str:
    adapter = adapter_for_path(path)
    return adapter.name if adapter is not None else "claude"


def resolve_path_from_session_id(session_id: str) -> str | None:
    matches: list[Path] = []
    for adapter in _ADAPTERS:
        matches.extend(adapter.session_paths_for_id(session_id))
    existing = [path for path in matches if path.exists()]
    if not existing:
        return None
    return str(max(existing, key=lambda path: (path.stat().st_mtime, str(path))))
