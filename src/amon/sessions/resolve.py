from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from ..agents.registry import agent_names, infer_agent_name_from_path
from ..agents.registry import resolve_path_from_session_id as registry_resolve_path_from_session_id
from ..constants import SCOPE_ALL, SCOPE_CURRENT, UUID_RE
from ..host import _realpath


def resolve_path_from_session_id(sid: str) -> Optional[str]:
    return registry_resolve_path_from_session_id(sid)


def _scope_root(scope: str, cwd: Optional[str]) -> Optional[str]:
    if scope == SCOPE_ALL:
        return None
    if scope == SCOPE_CURRENT:
        return _realpath(cwd or os.getcwd())
    raise ValueError(f"invalid discovery scope: {scope}")


def _session_record(
    agent: str,
    pid: int,
    path: str,
    cwd: Optional[str] = None,
    command: str = "",
    inline: bool = False,
) -> dict:
    session = {"agent": agent, "pid": pid, "path": path, "inline": inline}
    if cwd:
        session["cwd"] = cwd
    if command:
        session["command"] = command
    return session


def _normalized_session_path(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def resolve_active_session_record(session_path: str, agent: str) -> Optional[dict]:
    from .discovery import discover_active_sessions

    target = _normalized_session_path(session_path)
    for session in discover_active_sessions(codex_all=True):
        if session.get("agent") != agent:
            continue
        candidate = session.get("path")
        if not candidate:
            continue
        if _normalized_session_path(str(candidate)) != target:
            continue
        return session
    return None


def resolve_session_pid(session_path: str, agent: str) -> Optional[int]:
    session = resolve_active_session_record(session_path, agent)
    if session is not None:
        pid = session.get("pid")
        return pid if isinstance(pid, int) else None
    return None


def encode_session_spec(session: dict) -> str:
    payload = {
        "agent": session["agent"],
        "pid": session.get("pid"),
        "path": session["path"],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_session_spec(spec: str) -> dict:
    try:
        raw = base64.urlsafe_b64decode(spec.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError("invalid session spec") from exc
    if not isinstance(payload, dict):
        raise ValueError("invalid session spec")
    if payload.get("agent") not in agent_names():
        raise ValueError("invalid session agent")
    if not payload.get("path"):
        raise ValueError("invalid session path")
    return payload


def session_title(session: dict) -> str:
    agent = str(session.get("agent") or "session")
    stem = Path(str(session.get("path") or "")).stem or "session"
    match = UUID_RE.search(stem)
    return f"{agent}/{match.group(1) if match else stem}"


def session_id_from_path(path: str) -> str:
    stem = Path(path).stem
    match = UUID_RE.search(stem)
    return match.group(1) if match else (stem or "session")


def infer_agent_from_path(path: str) -> str:
    return infer_agent_name_from_path(path)


def short_session_id(path: str) -> str:
    stem = Path(path).stem
    return stem[:8] if stem else "session"
