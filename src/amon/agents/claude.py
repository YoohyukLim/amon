from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .base import AgentAdapter
from ..host import _split_cmdline, process_cwd
from ..jsonl import pick_latest_jsonl
from ..text import _tool_detail, _truncate


CLAUDE_NON_AGENT_COMMANDS = {"config", "doctor", "help", "mcp", "update"}
CLAUDE_NON_AGENT_FLAGS = {"--help", "-h", "--version", "-v"}


def cwd_to_claude_slug(cwd: str) -> str:
    return "".join("-" if char in "/." else char for char in cwd)


def resolve_claude_session_path(
    pid: int,
    cmdline: str = "",
    cwd: Optional[str] = None,
) -> Optional[str]:
    cwd = process_cwd(pid) if cwd is None else cwd
    if not cwd:
        return None
    directory = Path.home() / ".claude" / "projects" / cwd_to_claude_slug(cwd)
    session_id = claude_session_id_from_cmdline(cmdline)
    if session_id:
        session_path = directory / f"{session_id}.jsonl"
        return str(session_path) if session_path.is_file() else None
    return pick_latest_jsonl(str(directory))


def claude_session_id_from_cmdline(cmdline: str) -> Optional[str]:
    argv = _split_cmdline(cmdline)
    for idx, arg in enumerate(argv):
        if os.path.basename(arg) != "claude":
            continue
        args = argv[idx + 1 :]
        for arg_idx, candidate in enumerate(args):
            if candidate == "--session-id" and arg_idx + 1 < len(args):
                return args[arg_idx + 1]
            if candidate.startswith("--session-id="):
                session_id = candidate.split("=", 1)[1]
                return session_id or None
        return None
    return None


def is_claude_noninteractive(cmdline: str) -> bool:
    argv = _split_cmdline(cmdline)
    for idx, arg in enumerate(argv):
        if os.path.basename(arg) != "claude":
            continue
        args = argv[idx + 1 :]
        return "-p" in args or "--print" in args
    return False


def is_claude_agent(cmdline: str) -> bool:
    argv = _split_cmdline(cmdline)
    for idx, arg in enumerate(argv):
        if os.path.basename(arg) != "claude":
            continue
        args = argv[idx + 1 :]
        if not args:
            return True
        first = args[0]
        return first not in CLAUDE_NON_AGENT_COMMANDS and first not in CLAUDE_NON_AGENT_FLAGS
    return False


def _format_claude_event(ev: dict) -> Optional[tuple[str, str]]:
    if ev.get("type") == "assistant":
        message = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        content = message.get("content")
        if not isinstance(content, list):
            return None
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                name = str(item.get("name") or "tool")
                detail = _tool_detail(item.get("input"))
                return ("Tool", _truncate(f"{name} {detail}".strip()))
            if item.get("type") == "text" and item.get("text"):
                return ("Msg", _truncate(str(item["text"])))
        return None

    attachment = ev.get("attachment")
    if ev.get("type") == "attachment" and isinstance(attachment, dict):
        if attachment.get("type") == "tool_use":
            name = str(attachment.get("tool_name") or attachment.get("name") or "tool")
            detail = _tool_detail(attachment.get("input"))
            return ("Tool", _truncate(f"{name} {detail}".strip()))
    return None


class ClaudeAdapter(AgentAdapter):
    name = "claude"
    process_patterns = ("claude",)

    def is_agent_command(self, cmdline: str) -> bool:
        return is_claude_agent(cmdline)

    def is_inline_command(self, cmdline: str) -> bool:
        return is_claude_noninteractive(cmdline)

    def resolve_session_paths(
        self,
        pid: int,
        *,
        cmdline: str = "",
        cwd: Optional[str] = None,
        include_all: bool = False,
    ) -> list[str]:
        path = resolve_claude_session_path(pid, cmdline=cmdline, cwd=cwd)
        return [path] if path else []

    def owns_session_path(self, path: str) -> bool:
        return "/.claude/projects/" in path and path.endswith(".jsonl")

    def session_paths_for_id(self, session_id: str) -> list[Path]:
        if not session_id:
            return []
        root = Path.home() / ".claude" / "projects"
        return [path for path in root.glob("**/*.jsonl") if path.stem == session_id]

    def format_event(self, event: dict) -> Optional[tuple[str, str]]:
        return _format_claude_event(event)

    def is_exit_event(self, event: dict) -> bool:
        return event.get("type") == "result" or super().is_exit_event(event)
