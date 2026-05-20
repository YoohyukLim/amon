from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import AgentAdapter
from ..host import _run_lsof, _split_cmdline
from ..text import _tool_detail, _truncate


CODEX_NON_AGENT_COMMANDS = {
    "app-server",
    "completion",
    "debug",
    "help",
    "login",
    "logout",
    "mcp",
    "server",
}
CODEX_NON_AGENT_FLAGS = {"--help", "-h", "--version", "-V"}


def parse_lsof_codex_jsonls(output: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        path = parts[8]
        if path.endswith(".jsonl") and "/.codex/sessions/" in path and path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def resolve_codex_session_paths(pid: int, all_sessions: bool = False) -> list[str]:
    existing = [path for path in parse_lsof_codex_jsonls(_run_lsof(pid)) if Path(path).exists()]
    if all_sessions:
        return existing
    if not existing:
        return []
    newest = max(existing, key=lambda path: (Path(path).stat().st_mtime, path))
    return [newest]


def _format_codex_event(ev: dict) -> Optional[tuple[str, str]]:
    if ev.get("type") != "response_item":
        return None
    payload = ev.get("payload") or ev.get("item")
    if not isinstance(payload, dict):
        return None

    payload_type = payload.get("type")
    if payload_type == "function_call":
        name = str(payload.get("name") or "tool")
        detail = _tool_detail(payload.get("arguments"))
        return ("Tool", _truncate(f"{name} {detail}".strip()))

    if payload_type == "message" and payload.get("role") == "assistant":
        content = payload.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "output_text" and item.get("text"):
                    return ("Msg", _truncate(str(item["text"])))
        text = payload.get("text")
        if text:
            return ("Msg", _truncate(str(text)))
    return None


def is_codex_exec(cmdline: str) -> bool:
    argv = _split_cmdline(cmdline)
    return len(argv) >= 2 and os.path.basename(argv[0]) == "codex" and argv[1] == "exec"


def is_codex_agent(cmdline: str) -> bool:
    argv = _split_cmdline(cmdline)
    if not argv or os.path.basename(argv[0]) != "codex":
        return False
    if len(argv) == 1:
        return True
    return argv[1] not in CODEX_NON_AGENT_COMMANDS and argv[1] not in CODEX_NON_AGENT_FLAGS


class CodexAdapter(AgentAdapter):
    name = "codex"
    process_patterns = ("codex",)

    def is_agent_command(self, cmdline: str) -> bool:
        return is_codex_agent(cmdline)

    def is_inline_command(self, cmdline: str) -> bool:
        return is_codex_exec(cmdline)

    def resolve_session_paths(
        self,
        pid: int,
        *,
        cmdline: str = "",
        cwd: Optional[str] = None,
        include_all: bool = False,
    ) -> list[str]:
        return resolve_codex_session_paths(pid, all_sessions=include_all)

    def owns_session_path(self, path: str) -> bool:
        return "/.codex/sessions/" in path and path.endswith(".jsonl")

    def session_paths_for_id(self, session_id: str) -> list[Path]:
        if not session_id:
            return []
        root = Path.home() / ".codex" / "sessions"
        return [path for path in root.glob("**/*.jsonl") if session_id in path.stem]

    def format_event(self, event: dict) -> Optional[tuple[str, str]]:
        return _format_codex_event(event)
